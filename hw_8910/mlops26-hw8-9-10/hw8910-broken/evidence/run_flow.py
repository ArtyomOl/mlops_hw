import os, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]; python=root/'.venv/bin/python'
with tempfile.TemporaryDirectory() as d:
    work=Path(d)/'lab'; env=os.environ.copy();env.update(PREFECT_HOME=str(Path(d)/'prefect'),PREFECT_SERVER_ANALYTICS_ENABLED='false',PREFECT_LOGGING_LEVEL='INFO')
    results=[]
    def run(name,*args):
        p=subprocess.run([str(python),*map(str,args)],cwd=root,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=f'### {name} exit={p.returncode}\n{p.stdout}\n'
        results.append(log); print(log,flush=True); return p.returncode
    run('init','lab.py','--workspace',work,'init')
    run('failure','flow.py','--workspace',work,'--fail-after-prepare')
    run('recovery','flow.py','--workspace',work)
    (work/'input.txt').write_text('changed input at same path\n')
    run('changed input','flow.py','--workspace',work)
    (root/'evidence/prefect.log').write_text('\n'.join(results))
