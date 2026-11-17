"""Exercise the simulator over HTTP, including client cancellation."""
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class Server:
    def __init__(self, port):
        self.port = port

    def request(self, path, payload=None, method=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        connection.request(method or ('POST' if payload is not None else 'GET'), path,
                           body=json.dumps(payload) if payload is not None else None,
                           headers={'Content-Type': 'application/json', 'Connection': 'close'})
        return connection, connection.getresponse()

    def read(self, path, payload=None, method=None):
        connection, response = self.request(path, payload, method)
        try:
            return response.status, dict(response.headers), response.read().decode()
        finally:
            connection.close()

    def wait_for(self, condition, timeout=4):
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            try:
                if condition():
                    return
            except OSError:
                pass
            time.sleep(.02)
        raise AssertionError('server did not reach expected state')

    def counter(self, outcome):
        _, _, metrics = self.read('/metrics')
        value = re.search(rf'^hw11_requests_total\{{outcome="{outcome}"\}} (\S+)', metrics, re.MULTILINE)
        return float(value[1])


@contextmanager
def service(**overrides):
    env = dict(os.environ, WARMUP_SECONDS='0', CACHE_HIT_MS='0', CACHE_MISS_MS='0')
    env.update(overrides)
    with socket.socket() as assigned, tempfile.TemporaryFile() as log:
        assigned.bind(('127.0.0.1', 0))
        assigned.listen()
        port = assigned.getsockname()[1]
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app:app', '--fd', str(assigned.fileno())],
                                   cwd=ROOT, env=env, stdout=log, stderr=log, pass_fds=(assigned.fileno(),))
        server = Server(port)
        try:
            server.wait_for(lambda: server.read('/health')[0] == 200)
            yield server
        except Exception:
            log.seek(0)
            sys.stderr.write(log.read().decode())
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class SimulatorHttpTest(unittest.TestCase):
    def test_early_probe_admits_cold_requests_and_correct_probe_rejects(self):
        payload = {'prompt': 'hello', 'parts': 1}
        with service(WARMUP_SECONDS='1.5', PROBE_MODE='early') as server:
            self.assertEqual(server.read('/startup')[0], 200)
            self.assertEqual(server.read('/ready')[0], 200)
            status, _, raw = server.read('/generate', payload)
            self.assertEqual(status, 200)
            chunk = json.loads(raw.splitlines()[0])
            self.assertFalse(chunk['warmed'])
        with service(WARMUP_SECONDS='1.5', PROBE_MODE='correct') as server:
            self.assertEqual(server.read('/startup')[0], 503)
            self.assertEqual(server.read('/ready')[0], 503)
            self.assertEqual(server.read('/generate', payload)[0], 503)
            server.wait_for(lambda: server.read('/ready')[0] == 200)
            status, _, raw = server.read('/generate', payload)
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(raw.splitlines()[0])['warmed'])

    def test_isolation_and_bounded_cache(self):
        with service(CACHE_CAPACITY='1') as server:
            def ask(user, secret):
                status, headers, raw = server.read('/generate', {
                    'prompt': 'continue', 'session_id': user, 'prefix': user, 'parts': 1,
                    'history': [{'role': 'user', 'content': secret}]
                })
                self.assertEqual(status, 200)
                self.assertEqual(headers.get('x-backend-mode'), 'simulated')
                events = [json.loads(line) for line in raw.splitlines()]
                self.assertEqual(events[-1]['event'], 'done')
                return events[0]
            first = ask('first', 'private wording for first')
            same_prefix = ask('first', 'different independent history')
            second = ask('second', 'private wording for second')
            first_after_second = ask('first', 'new first turn')
            self.assertIn('private wording for first', first['text'])
            self.assertIn('different independent history', same_prefix['text'])
            self.assertNotIn('private wording for first', same_prefix['text'])
            self.assertNotIn('first', second['text'])
            self.assertFalse(first['cache_hit'])
            self.assertTrue(same_prefix['cache_hit'])
            self.assertFalse(first_after_second['cache_hit'])

    def test_refusal_and_aborted_stream_are_separate_outcomes(self):
        with service(PROCESS_CONCURRENCY='1', QUEUE_CAPACITY='0') as server:
            connection, response = server.request('/generate', {'prompt': 'long stream', 'parts': 5, 'chunk_ms': 500})
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.readline())['event'], 'chunk')
            self.assertEqual(server.read('/generate', {'prompt': 'must be rejected', 'parts': 1})[0], 429)
            response.close()
            connection.close()
            server.wait_for(lambda: server.counter('aborted') == 1)
            self.assertEqual(server.counter('rejected'), 1)
            self.assertEqual(server.counter('completed'), 0)
            self.assertEqual(server.read('/generate', {'prompt': 'slot returned', 'parts': 1})[0], 200)
            self.assertEqual(server.counter('completed'), 1)

    def test_drain_preserves_already_admitted_stream(self):
        with service() as server:
            connection, response = server.request('/generate', {'prompt': 'do not interrupt', 'parts': 3, 'chunk_ms': 150})
            try:
                self.assertEqual(json.loads(response.readline())['event'], 'chunk')
                self.assertEqual(server.read('/drain', method='POST')[0], 200)
                self.assertEqual(server.read('/health')[0], 200)
                self.assertEqual(server.read('/ready')[0], 503)
                self.assertEqual(server.read('/generate', {'prompt': 'new request', 'parts': 1})[0], 503)
                events = [json.loads(line) for line in response.read().splitlines()]
                self.assertEqual(events[-1]['event'], 'done')
                self.assertEqual(events[-1]['parts'], 3)
            finally:
                connection.close()


if __name__ == '__main__':
    unittest.main()
