"""Check the saved evaluation without loading any model weights."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import real_release

ROOT=Path(__file__).resolve().parents[1]

class RealBinding(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.copy=Path(self.tmp.name)/'inputs67'
        shutil.copytree(ROOT/'inputs67',self.copy,ignore=shutil.ignore_patterns('__pycache__'))
        self.manifest=json.loads((ROOT/'real-baseline/candidate-manifest.json').read_text())
        self.patch=patch.object(real_release,'PREVIOUS',self.copy);self.patch.start();self.addCleanup(self.patch.stop)

    def test_saved_gate_rejects_and_binds_run(self):
        report=real_release.evaluate(self.manifest)
        self.assertIs(report['passed'],False)
        self.assertEqual(report['reason'],'Регрессия общей accuracy')
        self.assertEqual(report['model_id'],'94a484907fdd4275ab911cb26b7eec06')

    def test_changed_raw_answer_is_rejected(self):
        path=self.copy/'metrics/candidate-outputs.json'
        value=json.loads(path.read_text()); value[0]['raw']='changed';path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'raw output hash mismatch'):real_release.evaluate(self.manifest)

    def test_changed_generation_protocol_is_rejected(self):
        path=self.copy/'evaluation/params.json'; value=json.loads(path.read_text());value['max_new_tokens']=16;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'protocol or model changed'):real_release.evaluate(self.manifest)

if __name__=='__main__':unittest.main()
