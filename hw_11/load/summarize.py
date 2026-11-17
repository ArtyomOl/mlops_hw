"""Summaries of request attempts. Latency distributions include completed requests only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path


def distribution(values):
    samples = sorted(v for v in values if v is not None)
    if not samples:
        return {'n': 0, 'p50': None, 'p95': None}
    return {'n': len(samples), **{f'p{int(q*100)}': round(samples[math.ceil(q * len(samples))-1], 4)
                                for q in (.50, .95)}}


def summary(rows):
    success = [row for row in rows if row['outcome'] == 'completed']
    sent = sum(row.get('actual_send_monotonic_s') is not None for row in rows)
    counts = Counter(row['outcome'] for row in rows)
    return {
        'planned': len(rows), 'sent': sent, 'completed': len(success),
        'rejected': counts['rejected'], 'aborted': counts['aborted'], 'timeout': counts['timeout'],
        'not_sent': counts['not_sent'], 'other_error': counts['error'],
        'error_fraction': (sent-len(success))/sent if sent else None,
        'timeout_fraction': counts['timeout']/len(rows) if rows else None,
        'statuses': dict(Counter(str(row.get('status')) for row in rows)),
        'warmup_incomplete': sum(row.get('warmed') is False for row in rows),
        'cache_hits': sum(row.get('cache_hit') is True for row in success),
        'cache_misses': sum(row.get('cache_hit') is False for row in success),
        **{key: distribution(row.get(key) for row in success) for key in ('ttfc_ms', 'e2e_ms', 'queue_ms')},
        'send_late_ms': distribution(row.get('send_late_ms') for row in rows),
        'inter_chunk_ms': distribution(v for row in success for v in row.get('inter_chunk_ms', [])),
    }


def group_summary(rows):
    requests_by_pod = defaultdict(list)
    routes_by_client = defaultdict(Counter)
    source_addresses = set()
    for row in rows:
        pod = row.get('pod')
        client = row.get('client')
        address = row.get('source_ip_seen')
        if pod:
            requests_by_pod[pod].append(row)
        if client:
            routes_by_client[client][pod or 'unavailable'] += 1
        if address:
            source_addresses.add(address)

    return {
        'all': summary(rows),
        'by_pod': {pod: summary(requests_by_pod[pod]) for pod in sorted(requests_by_pod)},
        'client_to_pod': {client: dict(routes_by_client[client]) for client in sorted(routes_by_client)},
        'source_addresses_seen': sorted(source_addresses),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_log', nargs='+', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for file in args.request_log for line in file.read_text().splitlines() if line]
    print(json.dumps(group_summary(rows), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
