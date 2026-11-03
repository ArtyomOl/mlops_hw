"""FastAPI serving with an injected stub or a local Transformers backend."""
import argparse
import json
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
import release
from service import StubBackend

def check_runtime(manifest):
    """Only load generation settings implemented by this serving backend."""
    runtime=manifest['runtime']; gen=runtime['generation']; files=manifest['file_hashes']
    if release.sha(release.canonical(runtime)) != manifest['runtime_sha256']:
        raise ValueError('runtime hash mismatch')
    if gen.get('do_sample') is not False or gen.get('enable_thinking') is not False or type(gen.get('max_new_tokens')) is not int or gen['max_new_tokens'] != 32 or not isinstance(gen.get('system'),str) or not gen['system']:
        raise ValueError('unsupported generation runtime')
    if runtime.get('dtype') not in ('float32','float16','bfloat16'):
        raise ValueError('unsupported dtype')
    template='chat_template.jinja' if manifest.get('artifact_kind')=='peft' else 'tokenizer_config.json'
    if files.get('tokenizer.json') != runtime.get('tokenizer_sha256') or files.get(template) != runtime.get('template_sha256'):
        raise ValueError('tokenizer or template mismatch')
    base=Path(manifest['base_uri'] if manifest.get('artifact_kind')=='peft' else manifest['artifact_uri'])
    if base.name != runtime.get('base_revision'):
        raise ValueError('base revision mismatch')

class RealBackend:
    def __init__(self, manifest, root):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        runtime=manifest['runtime']; self.loaded_id=manifest['model_id']; self.runtime_sha256=manifest['runtime_sha256']; self.calls=0
        source=str(Path(manifest['artifact_uri']).resolve())
        if manifest.get('artifact_kind') == 'peft':
            base=Path(manifest['base_uri'])
            release.verify_files({'file_hashes':manifest['base_file_hashes'],'model_sha256':manifest['base_sha256']},base)
            self.tokenizer=AutoTokenizer.from_pretrained(source,local_files_only=True)
            model=AutoModelForCausalLM.from_pretrained(str(base),dtype=getattr(torch,runtime['dtype']),local_files_only=True)
            from peft import PeftModel
            self.model=PeftModel.from_pretrained(model,source,local_files_only=True).eval()
        else:
            self.tokenizer=AutoTokenizer.from_pretrained(source, local_files_only=True)
            self.model=AutoModelForCausalLM.from_pretrained(source, dtype=getattr(torch,runtime['dtype']), local_files_only=True).eval()
        self.system=runtime['generation']['system']; self.lock=threading.Lock()
    def generate(self,prompt,limit):
        import torch
        messages=[{'role':'system','content':self.system},{'role':'user','content':prompt}]
        text=self.tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inputs=self.tokenizer(text,return_tensors='pt')
        if inputs['input_ids'].shape[-1]>2048: raise ValueError('input exceeds token limit')
        with self.lock:
            self.calls+=1; started=time.perf_counter()
            with torch.inference_mode(): output=self.model.generate(**inputs,max_new_tokens=limit,do_sample=False,pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)
            duration=time.perf_counter()-started
            tokens=output[0,inputs['input_ids'].shape[-1]:]
            return {'answer':self.tokenizer.decode(tokens,skip_special_tokens=True),'output_tokens':len(tokens),'generation_seconds':duration}

class Request(BaseModel):
    model_config=ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1,max_length=16384)
    max_new_tokens: StrictInt = Field(default=32,ge=1,le=32)
    @field_validator('prompt')
    @classmethod
    def nonempty(cls,v):
        if not v.strip(): raise ValueError('empty prompt')
        return v

def create_app(root: Path, backend_factory=StubBackend, warmup_seconds=0):
    @asynccontextmanager
    async def lifespan(app):
        manifest=json.loads((root/'accepted.json').read_text())
        artifact_root = Path(manifest['artifact_uri']) if backend_factory is not StubBackend else root
        release.verify_files(manifest,artifact_root)
        if backend_factory is not StubBackend: check_runtime(manifest)
        elif release.sha(release.canonical(manifest['runtime'])) != manifest['runtime_sha256']: raise ValueError('runtime hash mismatch')
        app.state.backend=backend_factory(manifest) if backend_factory is StubBackend else backend_factory(manifest,root)
        app.state.ready=False
        def warm():
            time.sleep(warmup_seconds)
            if backend_factory is not StubBackend: app.state.backend.generate('Warmup.',32)
            app.state.ready=True
        threading.Thread(target=warm,daemon=True).start()
        yield
    app=FastAPI(lifespan=lifespan)
    @app.get('/health')
    def health(): return {'alive':True}
    @app.get('/ready')
    def ready():
        if not app.state.ready: raise HTTPException(503,'not ready')
        return {'ready':True}
    @app.get('/debug')
    def debug():
        b=app.state.backend; return {'loaded_id':b.loaded_id,'calls':b.calls,'warmup_finished':app.state.ready}
    @app.post('/generate')
    def generate(req: Request):
        if not app.state.ready: raise HTTPException(503,'not ready')
        if backend_factory is not StubBackend and req.max_new_tokens != 32: raise HTTPException(422,'evaluated runtime requires 32 tokens')
        b=app.state.backend; started=time.perf_counter()
        try: result=b.generate(req.prompt,req.max_new_tokens)
        except ValueError as e: raise HTTPException(422,str(e))
        result.setdefault('generation_seconds',time.perf_counter()-started)
        result.update(model_id=b.loaded_id,runtime_sha256=b.runtime_sha256,request_id=str(uuid.uuid4()),total_seconds=time.perf_counter()-started)
        return result
    return app

if __name__=='__main__':
    import uvicorn
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path('.lab'));p.add_argument('--port',type=int,default=8091);p.add_argument('--warmup-seconds',type=float,default=0);p.add_argument('--backend',choices=['stub','real'],default='stub');a=p.parse_args()
    uvicorn.run(create_app(a.workspace,StubBackend if a.backend=='stub' else RealBackend,a.warmup_seconds),host='127.0.0.1',port=a.port)
