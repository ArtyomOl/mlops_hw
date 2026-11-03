import concurrent.futures, json, os, socket, subprocess, time, urllib.error, urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
previous=root.parents[2]/'hw_SIXSEVEN/mlops26-hw6-7/hw67-broken'
python=previous/'.venv/bin/python'
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
env=os.environ.copy();env.update(OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false')
log=(root/'evidence/real-server.log').open('w')
p=subprocess.Popen([str(python),'api.py','--workspace','real-baseline','--port',str(port),'--backend','real'],cwd=root,stdout=log,stderr=subprocess.STDOUT,env=env)
def request(path,payload=None,timeout=180):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        with e: return e.code,json.load(e)
try:
    for i in range(240):
        if p.poll() is not None: raise RuntimeError('server stopped; see real-server.log')
        try:
            status,_=request('/ready',timeout=3)
            if status==200: break
        except Exception: pass
        time.sleep(1)
    else: raise TimeoutError('server not ready')
    prompts=[json.loads(line)['input'] for line in (previous/'data/eval/golden.jsonl').read_text().splitlines()[:4]]
    output=[]; summaries=[]
    for concurrency in (1,2):
        start=time.perf_counter()
        def one(pair):
            idx,prompt=pair;begin=time.perf_counter(); row={'id':idx,'concurrency':concurrency}
            try:
                status,data=request('/generate',{'prompt':prompt,'max_new_tokens':32})
                row.update(status=status,response=data,model_id=data.get('model_id'),generation_seconds=data.get('generation_seconds'),output_tokens=data.get('output_tokens'))
            except Exception as e: row.update(status='error',error=repr(e))
            row['client_seconds']=time.perf_counter()-begin
            return row
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool: rows=list(pool.map(one,enumerate(prompts)))
        elapsed=time.perf_counter()-start; output.extend(rows)
        good=[r for r in rows if r['status']==200]
        summaries.append({'concurrency':concurrency,'n':len(rows),'successes':len(good),'errors':len(rows)-len(good),'batch_seconds':elapsed,'successes_per_second':len(good)/elapsed,'mean_latency':sum(r['client_seconds'] for r in good)/len(good) if good else None,'max_latency':max((r['client_seconds'] for r in good),default=None)})
        (root/'evidence/real-requests.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output))
        (root/'evidence/real-summary.json').write_text(json.dumps(summaries,indent=2))
        print(json.dumps(summaries[-1],ensure_ascii=False),flush=True)
        if rows: print('Пример ответа:',json.dumps(rows[0],ensure_ascii=False),flush=True)
    print('invalid',request('/generate',{'prompt':'x','max_new_tokens':100000}),flush=True)
finally:
    p.terminate()
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:p.kill();p.wait()
    log.close()
