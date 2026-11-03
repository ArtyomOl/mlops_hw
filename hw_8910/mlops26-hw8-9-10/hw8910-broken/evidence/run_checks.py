"""Capture genuine baseline and fixed test runs; no tests are changed in baseline."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def run(name, cmd, cwd, env=None):
    p=subprocess.run(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (root/'evidence'/name).write_text(p.stdout+'\nexit_code='+str(p.returncode)+'\n')
    print('\n###', name, 'exit_code=', p.returncode, flush=True)
    print(p.stdout, flush=True)
with tempfile.TemporaryDirectory() as d:
    target=Path(d); (target/'tests').mkdir()
    for name in ('lab.py','service.py','release.py'): shutil.copy(root/'original'/name,target/name)
    shutil.copy(root/'tests/test_integration.py',target/'tests/test_integration.py')
    run('original-red.log',[sys.executable,'-m','unittest','discover','-s','tests','-v'],target)
run('fixed-green.log',[sys.executable,'-m','unittest','discover','-s','tests','-v'],root)
env=os.environ.copy();env['SERVICE_SCRIPT']='api.py'
run('fastapi-green.log',[str(root/'.venv/bin/python'),'-m','unittest','discover','-s','tests','-v'],root,env)
