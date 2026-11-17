"""Open-loop HTTP/1.1 client for the HW11 NDJSON API. Uses only the stdlib."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def payload_digest(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def http_lines(reader: asyncio.StreamReader, headers: dict[str, str]):
    """Yield NDJSON lines regardless of HTTP chunk boundaries."""
    if 'chunked' not in headers.get('transfer-encoding', '').lower():
        while line := await reader.readline():
            yield line
        return
    pending = b''
    while True:
        size_line = await reader.readline()
        if not size_line:
            raise EOFError('missing final HTTP chunk')
        size = int(size_line.partition(b';')[0].strip(), 16)
        if size == 0:
            if pending:
                yield pending
            return
        pending += await reader.readexactly(size)
        if await reader.readexactly(2) != b'\r\n':
            raise ValueError('invalid HTTP chunk delimiter')
        split = pending.split(b'\n')
        pending = split.pop()
        for line in split:
            yield line


async def attempt(url: str, row: dict, start_mono: float, start_wall: float, timeout: float) -> dict:
    offset = float(row['offset_s'])
    payload = row['payload']
    deadline = start_mono + offset
    await asyncio.sleep(max(0, deadline - time.monotonic()))
    actual_start = time.monotonic()
    request_id = row.get('request_id') or str(uuid.uuid4())
    result = {
        'request_id': request_id,
        'sequence': row.get('sequence'),
        'client': os.environ.get('CLIENT_NAME', os.environ.get('HOSTNAME', 'local')),
        'client_ip': os.environ.get('CLIENT_IP'),
        'session_id': payload.get('session_id'),
        'prompt_chars': len(payload.get('prompt', '')),
        'prefix': payload.get('prefix'),
        'requested_parts': payload.get('parts', payload.get('max_new_tokens')),
        'payload_sha256': payload_digest(payload),
        'planned_offset_s': offset,
        'planned_wall_s': start_wall + offset,
        'planned_monotonic_s': deadline,
        'attempt_monotonic_s': actual_start,
        'attempt_late_ms': (actual_start - deadline) * 1000,
        'actual_send_monotonic_s': None,
        'actual_wall_s': None,
        'first_monotonic_s': None,
        'first_wall_s': None,
        'end_monotonic_s': None,
        'completed_wall_s': None,
        'send_late_ms': None,
        'ttfc_ms': None,
        'e2e_ms': None,
        'queue_ms': None,
        'inter_chunk_ms': [],
        'status': None,
        'pod': None,
        'source_ip_seen': None,
        'version': None,
        'model_id': None,
        'artifact_sha256': None,
        'backend_mode': None,
        'parts': 0,
        'warmed': None,
        'cache_hit': None,
        'outcome': 'not_sent',
        'error': None,
    }
    if row.get('capture_content'):
        result['text_parts'] = []
    writer = None
    completed_marker = False
    previous_chunk = None
    target = urlsplit(url)
    path = target.path.rstrip('/')
    if not path.endswith('/generate'):
        path += '/generate'
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    request = (
        f'POST {path} HTTP/1.1\r\nHost: {target.netloc}\r\n'
        f'Connection: close\r\nContent-Type: application/json\r\n'
        f'Content-Length: {len(body)}\r\nX-Request-ID: {request_id}\r\n\r\n'
    ).encode() + body
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(target.hostname, target.port or 80)
            writer.write(request)
            result['actual_send_monotonic_s'] = time.monotonic()
            result['actual_wall_s'] = time.time()
            await writer.drain()
            status_line = await reader.readline()
            if not status_line:
                raise EOFError('no HTTP status received')
            result['status'] = int(status_line.split()[1])
            headers = {}
            while header := await reader.readline():
                if not header.strip():
                    break
                key, value = header.decode('latin1').split(':', 1)
                headers[key.lower()] = value.strip()
            result.update(
                response_request_id=headers.get('x-request-id'),
                pod=headers.get('x-pod-name'),
                source_ip_seen=headers.get('x-client-ip'),
                version=headers.get('x-model-version') or headers.get('x-model-id'),
                model_id=headers.get('x-model-id'),
                artifact_sha256=headers.get('x-artifact-sha256'),
                backend_mode=headers.get('x-backend-mode'),
            )
            if result['status'] != 200:
                result['outcome'] = 'rejected' if result['status'] in {400, 409, 422, 429, 503} else 'error'
                result['error'] = f'HTTP {result["status"]}'
            else:
                async for raw in http_lines(reader, headers):
                    if not raw.strip():
                        continue
                    event = json.loads(raw)
                    if event.get('event') == 'done':
                        completed_marker = event.get('parts') == result['parts'] == result['requested_parts']
                        continue
                    if event.get('event') != 'chunk':
                        continue
                    now = time.monotonic()
                    if result['first_monotonic_s'] is None:
                        result.update(first_monotonic_s=now, first_wall_s=time.time())
                        for key in ('pod', 'version', 'artifact_sha256', 'backend_mode', 'cache_hit', 'queue_ms', 'warmed'):
                            if key in event:
                                result[key] = event[key]
                    if previous_chunk is not None:
                        result['inter_chunk_ms'].append((now - previous_chunk) * 1000)
                    previous_chunk = now
                    result['parts'] += 1
                    if 'text_parts' in result:
                        result['text_parts'].append(event.get('text'))
                result['outcome'] = 'completed' if completed_marker else 'aborted'
                if not completed_marker:
                    result['error'] = 'missing or mismatched terminal NDJSON event'
    except TimeoutError:
        result.update(outcome='timeout', error='client deadline exceeded')
    except (OSError, EOFError, ValueError, IndexError) as exc:
        sent = result['actual_send_monotonic_s'] is not None
        result.update(outcome='aborted' if sent else 'not_sent', error=f'{type(exc).__name__}: {exc}')
    finally:
        result['end_monotonic_s'] = time.monotonic()
        result['completed_wall_s'] = time.time()
        sent = result['actual_send_monotonic_s']
        if sent is not None:
            result['send_late_ms'] = (sent - deadline) * 1000
            result['e2e_ms'] = (result['end_monotonic_s'] - sent) * 1000
            if result['first_monotonic_s'] is not None:
                result['ttfc_ms'] = (result['first_monotonic_s'] - sent) * 1000
        if writer is not None:
            writer.close()
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


async def run(args: argparse.Namespace) -> None:
    if args.single:
        payload = {'prompt': args.prompt, 'parts': args.parts}
        payload.update({key: value for key, value in {
            'prefix': args.prefix, 'chunk_ms': args.chunk_ms, 'session_id': args.session_id,
            'history': json.loads(args.history) if args.history else None,
        }.items() if value is not None})
        rows = [{'offset_s': 0, 'payload': payload, 'capture_content': True}]
    else:
        rows = json.load(sys.stdin) if args.schedule == '-' else json.loads(Path(args.schedule).read_text())
    now_wall = time.time()
    start_wall = args.start_at if args.start_at is not None else now_wall
    start_mono = time.monotonic() + start_wall - now_wall
    await asyncio.gather(*(attempt(args.url, row, start_mono, start_wall, args.timeout) for row in rows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--schedule', help='JSON list of offset_s/payload records, or - for stdin')
    source.add_argument('--single', action='store_true')
    parser.add_argument('--start-at', type=float, help='common Unix wall time for dispatch')
    parser.add_argument('--timeout', type=float, default=12)
    parser.add_argument('--prompt', default='HW11 test')
    parser.add_argument('--parts', type=int, default=5)
    parser.add_argument('--prefix')
    parser.add_argument('--chunk-ms', type=int)
    parser.add_argument('--session-id')
    parser.add_argument('--history', help='JSON list of role/content records')
    args = parser.parse_args()
    target = urlsplit(args.url)
    if target.scheme != 'http' or target.hostname is None or args.timeout <= 0:
        parser.error('use an http:// URL and a positive timeout')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
