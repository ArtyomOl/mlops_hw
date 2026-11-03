import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'lab'
        self.run_lab('init', ok=True)

    def run_lab(self, *args, ok=None):
        p = subprocess.run([sys.executable, str(ROOT/'lab.py'), '--workspace', str(self.root), *args], text=True, capture_output=True)
        if ok is not None: self.assertEqual(p.returncode == 0, ok, p.stdout+p.stderr)
        return p

    def start(self, warmup=0):
        sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
        p=subprocess.Popen([sys.executable,str(ROOT/os.environ.get('SERVICE_SCRIPT','service.py')),'--workspace',str(self.root),'--port',str(port),'--warmup-seconds',str(warmup)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def stop():
            if p.poll() is None: p.kill()
            p.wait()
            p.stdout.close(); p.stderr.close()
        self.addCleanup(stop)
        self.port=port
        for _ in range(100):
            try: self.http('/health'); return p
            except (OSError, urllib.error.URLError): time.sleep(.02)
        self.fail('server did not start')

    def http(self, path, payload=None):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=3) as response: return response.status,json.load(response)
        except urllib.error.HTTPError as e:
            with e: return e.code,json.load(e)

    def test_cache_recovery_and_changed_input(self):
        self.assertIn('PREPARED',self.run_lab('run','--fail-after-prepare',ok=False).stdout)
        self.assertIn('CACHE_HIT',self.run_lab('run',ok=True).stdout)
        (self.root/'input.txt').write_text('changed')
        self.assertIn('PREPARED',self.run_lab('run',ok=True).stdout)

    def test_rejected_and_foreign_report_preserve_pointer(self):
        before=(self.root/'accepted.json').read_bytes()
        for report in ('report-incomplete.json','report-reject.json','report-A.json'):
            self.run_lab('run','--report',report,ok=False)
            self.assertEqual(before,(self.root/'accepted.json').read_bytes())

    def test_recovery_after_pointer_and_repeat(self):
        self.run_lab('run',ok=True); self.run_lab('run',ok=True)
        self.assertEqual(len((self.root/'publications.jsonl').read_text().splitlines()),1)
        self.run_lab('run','--fail-after-publish',ok=False)
        self.run_lab('run',ok=True)
        lines=(self.root/'publications.jsonl').read_text().splitlines()
        self.assertEqual(len(lines),1)

    def test_failed_replace_keeps_pointer(self):
        code = """import json, sys
from pathlib import Path
from unittest.mock import patch
import release
root=Path(sys.argv[1]); m=json.loads((root/'manifest-B.json').read_text()); r=json.loads((root/'report-B.json').read_text())
try:
    with patch('os.replace', side_effect=OSError('disk error')): release.publish(m,r,root/'accepted.json')
except OSError: pass
else: raise AssertionError('atomic replace was not attempted')
"""
        before=(self.root/'accepted.json').read_bytes()
        p=subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(before,(self.root/'accepted.json').read_bytes())

    def test_readiness(self):
        self.start(1)
        self.assertEqual(self.http('/health')[0],200)
        self.assertEqual(self.http('/ready')[0],503)
        self.assertEqual(self.http('/generate',{'prompt':'hello'})[0],503)
        time.sleep(1.1); self.assertEqual(self.http('/ready')[0],200)

    def test_invalid_request_never_calls_backend(self):
        self.start(); time.sleep(.05)
        before=self.http('/debug')[1]['calls']
        for payload in ({'prompt':''},{'prompt':'x','max_new_tokens':0},{'prompt':'x','max_new_tokens':100000},{'prompt':'x','max_new_tokens':'2'}):
            self.assertTrue(400 <= self.http('/generate',payload)[0] < 500)
        self.assertEqual(self.http('/debug')[1]['calls'],before)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[0],200)
        self.assertEqual(self.http('/debug')[1]['calls'],before+1)

    def test_loaded_version_and_rollback(self):
        p=self.start(); time.sleep(.05)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-A')
        self.run_lab('run',ok=True)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-A')
        p.kill();p.wait(); self.start();time.sleep(.05)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-B')
        (self.root/'accepted.json').write_bytes((self.root/'manifest-A.json').read_bytes())
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-B')
        p.kill();p.wait(); self.start();time.sleep(.05)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-A')

    def test_rollback_restart(self):
        self.run_lab('run',ok=True)
        p=self.start();time.sleep(.05)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-B')
        (self.root/'accepted.json').write_bytes((self.root/'manifest-A.json').read_bytes())
        p.kill();p.wait();self.start();time.sleep(.05)
        self.assertEqual(self.http('/generate',{'prompt':'x'})[1]['model_id'],'fixture-A')

if __name__=='__main__': unittest.main()
