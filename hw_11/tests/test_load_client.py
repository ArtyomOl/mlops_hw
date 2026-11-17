"""Regression checks for request accounting across HTTP and stream outcomes."""
import asyncio
from contextlib import redirect_stdout
import io
import time
import unittest
from unittest.mock import patch

from load.client import attempt
from load.summarize import summary


class Writer:
    def write(self, body):
        self.body = body

    async def drain(self):
        pass

    def close(self):
        pass


def chunk(data):
    return f'{len(data):x}\r\n'.encode() + data + b'\r\n'


class RequestAccounting(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, response):
        async def connect(*_):
            reader = asyncio.StreamReader()
            reader.feed_data(response)
            reader.feed_eof()
            return reader, Writer()

        payload = {'prompt': 'accounting probe', 'parts': 1}
        with patch('asyncio.open_connection', side_effect=connect), redirect_stdout(io.StringIO()):
            return await attempt('http://127.0.0.1', {'offset_s': 0, 'payload': payload},
                                 time.monotonic(), time.time(), 1)

    async def test_rejections_and_empty_terminators_are_accounted_separately(self):
        rejected = await self.fetch(b'HTTP/1.1 429 Too Many Requests\r\nX-Pod-Name: hw11-pod\r\n\r\n')
        interrupted = await self.fetch(
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' +
            chunk(b'{"event":"chunk","text":"partial"}\n') + b'0\r\n\r\n'
        )
        completed = await self.fetch(
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' +
            chunk(b'{"event":"chunk","text":"full"}\n{"event":"done",') +
            chunk(b'"parts":1}\n') + b'0\r\n\r\n'
        )
        counts = summary([rejected, interrupted, completed])
        self.assertEqual((counts['planned'], counts['sent'], counts['completed']), (3, 3, 1))
        self.assertEqual((counts['rejected'], counts['aborted'], counts['timeout']), (1, 1, 0))
        self.assertEqual(interrupted['parts'], 1)
        self.assertEqual(completed['inter_chunk_ms'], [])
        self.assertEqual(counts['ttfc_ms']['n'], 1)
