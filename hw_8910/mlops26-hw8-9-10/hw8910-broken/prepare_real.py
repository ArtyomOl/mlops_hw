"""Record provenance of the already accepted baseline and re-run the old gate."""
import argparse, json, sys
from pathlib import Path
import release

previous=Path(__file__).resolve().parent/'inputs67'
sys.path.insert(0,str(previous))
from evaluation.solution import quality_gate

snapshot=Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/c1899de289a04d12100db370d81485cdf75e47ca'
root=Path(__file__).resolve().parent/'real-baseline';root.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--rebind-baseline',action='store_true');args=parser.parse_args()
def load(p): return json.loads(p.read_text())
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
protocol=load(previous/'docs/protocol.json'); cfg=protocol['config']
files={p.name:release.file_sha(p) for p in sorted(snapshot.iterdir()) if p.is_file()}
runtime={'base_revision':protocol['baseline']['revision'],'tokenizer_sha256':files['tokenizer.json'],'template_sha256':files['tokenizer_config.json'],
         'generation':{'system':cfg['system'],'max_new_tokens':cfg['max_new_tokens'],'do_sample':False,'enable_thinking':cfg['enable_thinking'],'seed':cfg['seed']},'dtype':'bfloat16'}
m={'schema_version':1,'model_id':'Qwen/Qwen3-0.6B@'+runtime['base_revision'],'artifact_uri':str(snapshot),
   'file_hashes':files,'model_sha256':release.sha(release.canonical(files)),'protocol_sha256':protocol['protocol_sha256'],
   'golden_sha256':protocol['golden_sha256'],'runtime':runtime,'runtime_sha256':release.sha(release.canonical(runtime)),
   'provenance':'Existing baseline from homework 6+7; no new candidate release'}
if not (root/'accepted.json').exists():
    save(root/'accepted.json',m)
else:
    current=load(root/'accepted.json')
    if args.rebind_baseline:
        if current['model_id'] != m['model_id'] or current['model_sha256'] != m['model_sha256'] or current['runtime_sha256'] != m['runtime_sha256']:
            raise ValueError('Cannot rebind: accepted model or runtime differs from the known baseline')
        current['artifact_uri']=str(snapshot)
        release.atomic_json(root/'accepted.json',current)
        print('Baseline path rebound after checking model and runtime hashes')
    else:
        print('Existing accepted.json retained')
inputs=['metrics/baseline-eval.json','metrics/candidate-eval.json','metrics/baseline-outputs.json','metrics/candidate-outputs.json','docs/protocol.json']
source={p:{'path':str(previous/p),'sha256':release.file_sha(previous/p)} for p in inputs}
try:
    decision=quality_gate(load(previous/inputs[0]),load(previous/inputs[1]),cfg['critical_slices'])
except ValueError as e:
    decision={'passed':False,'reason':str(e)}
decision.update(sources=source,evaluation_run_id='aa00d482199544e1aa299cf11aa31d68')
save(root/'candidate-decision.json',decision)
print(json.dumps({'baseline':m['model_id'],'candidate_decision':decision['passed'],'reason':decision.get('reason')},ensure_ascii=False))
