"""Load rejected candidate in isolation, never publish or serve it."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from api import RealBackend
import release
m=json.loads((root/'real-baseline/candidate-manifest.json').read_text())
release.verify_files(m,Path(m['artifact_uri']))
b=RealBackend(m,root)
prompt='Paper: synthetic test. Evidence: We evaluate the tagger using macro F1. Question: Which metric is used? Options: A: macro F1; B: accuracy; C: recall.'
result=b.generate(prompt,32);result.update(model_id=b.loaded_id,runtime_sha256=b.runtime_sha256,passed_gate=False,note='isolated loading test; rejected candidate is not served')
(root/'evidence/adapter-smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
