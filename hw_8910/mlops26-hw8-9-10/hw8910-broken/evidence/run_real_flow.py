import hashlib,json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]; pointer=root/'real-baseline/accepted.json'
def sha(): return hashlib.sha256(pointer.read_bytes()).hexdigest()
before=sha(); env=os.environ.copy(); env.update(PREFECT_HOME='/tmp/mlops-prefect-real-evidence',PREFECT_SERVER_ANALYTICS_ENABLED='false')
p=subprocess.run([str(root/'.venv/bin/python'),'flow.py','--real'],cwd=root,env=env,capture_output=True,text=True)
after=sha(); report=json.loads((root/'real-baseline/release-report.json').read_text())
output=p.stdout+p.stderr+f'\nexit_code={p.returncode}\naccepted_sha256_before={before}\naccepted_sha256_after={after}\n'
(root/'evidence/real-flow.log').write_text(output)
print(output)
if p.returncode or before!=after or report.get('passed') is not False or report.get('reason')!='Регрессия общей accuracy': raise SystemExit(1)
