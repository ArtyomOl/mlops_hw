"""Binding of the real homework 6+7 evaluation to a release decision."""
import json
import os
import sys
from pathlib import Path
import release

HERE=Path(__file__).resolve().parent
PREVIOUS=HERE/'inputs67'
SNAPSHOT=Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/c1899de289a04d12100db370d81485cdf75e47ca'
ADAPTER=HERE/'artifacts/candidate'
sys.path.insert(0,str(PREVIOUS))
from evaluation.contract import fingerprint, read_rows, validate_golden
from evaluation.solution import score, quality_gate


def read(path): return json.loads(Path(path).read_text())

def preparation_config():
    cfg=read(PREVIOUS/'evaluation/params.json')
    return {'tokenizer_revision':release.file_sha(ADAPTER/'tokenizer.json'),
            'template_sha256':release.file_sha(ADAPTER/'chat_template.jinja'),
            'max_length':2048,'code_revision':'golden-validation-v2',
            'behavioral_sha256':release.file_sha(PREVIOUS/cfg['behavioral']),
            'training_index_sha256':release.file_sha(PREVIOUS/cfg['training_index'])}

def prepare_data():
    cfg=read(PREVIOUS/'evaluation/params.json')
    rows=read_rows(PREVIOUS/cfg['golden']); behavior=read_rows(PREVIOUS/cfg['behavioral']); train=read_rows(PREVIOUS/cfg['training_index'])
    proof=validate_golden(rows,train,behavior)
    return {'sha256':release.file_sha(PREVIOUS/cfg['golden']), 'proof':proof}

def build_manifest():
    config=read(PREVIOUS/'evaluation/params.json'); protocol=read(PREVIOUS/'docs/protocol.json')
    candidate=read(PREVIOUS/'metrics/candidate-model.json'); meta=read(ADAPTER/'manifest.json')
    if meta['model']['revision'] != protocol['baseline']['revision'] or candidate != protocol['candidate']:
        raise ValueError('training run and evaluation model do not match')
    files={p.name:release.file_sha(p) for p in sorted(ADAPTER.iterdir()) if p.is_file()}
    base_files={p.name:release.file_sha(p) for p in sorted(SNAPSHOT.iterdir()) if p.is_file()}
    runtime={'base_revision':meta['model']['revision'],'tokenizer_sha256':files['tokenizer.json'],
        'template_sha256':files['chat_template.jinja'],'generation':{'system':config['system'],
        'max_new_tokens':config['max_new_tokens'],'do_sample':False,'enable_thinking':config['enable_thinking'],'seed':config['seed']},
        'dtype':meta['model']['dtype']}
    manifest={'schema_version':1,'model_id':candidate['run_id'],'artifact_uri':str(ADAPTER),
        'artifact_kind':'peft','training_run_id':candidate['run_id'],'registry_uri':candidate['uri'],
        'base_uri':str(SNAPSHOT),'base_file_hashes':base_files,'base_sha256':release.sha(release.canonical(base_files)),
        'file_hashes':files,'model_sha256':release.sha(release.canonical(files)),
        'protocol_sha256':protocol['protocol_sha256'],'golden_sha256':protocol['golden_sha256'],
        'runtime':runtime,'runtime_sha256':release.sha(release.canonical(runtime))}
    verify_manifest_files(manifest)
    return manifest

def verify_manifest_files(manifest):
    release.verify_files(manifest,Path(manifest['artifact_uri']))
    base={'file_hashes':manifest['base_file_hashes'],'model_sha256':manifest['base_sha256']}
    release.verify_files(base,Path(manifest['base_uri']))

def evaluate(manifest):
    """Recompute the old scorer, check provenance, then invoke the original gate."""
    config=read(PREVIOUS/'evaluation/params.json'); baseline_spec=read(PREVIOUS/'evaluation/baseline.json')
    rows=read_rows(PREVIOUS/config['golden']); behavioral=read_rows(PREVIOUS/config['behavioral']); train=read_rows(PREVIOUS/config['training_index'])
    proof=validate_golden(rows,train,behavioral)
    # The protocol includes the exact evaluation code, as in evaluation.cli.inputs.
    protocol={'config':config,'golden':rows,'behavioral':behavioral,'training_index':train,
              'evaluation_code':{p.name:p.read_text() for p in sorted((PREVIOUS/'evaluation').glob('*.py'))}}
    protocol_hash=fingerprint(protocol)
    reports=[read(PREVIOUS/f'metrics/{role}-eval.json') for role in ('baseline','candidate')]
    expected_models=[baseline_spec,read(PREVIOUS/'metrics/candidate-model.json')]
    sources={}
    for role, report, model in zip(('baseline','candidate'), reports, expected_models):
        if report['model'] != model or report['protocol_sha256'] != protocol_hash or report['golden_sha256'] != fingerprint(rows) or report['baseline_spec_sha256'] != fingerprint(baseline_spec):
            raise ValueError('evaluation protocol or model changed')
        path=PREVIOUS/f'metrics/{role}-outputs.json'; outputs=read(path)
        if fingerprint(outputs) != report['outputs_sha256']: raise ValueError('raw output hash mismatch')
        by_id={o['id']:o for o in outputs}
        if len(by_id)!=len(outputs) or set(by_id)!={r['id'] for r in rows+behavioral}: raise ValueError('raw output ids mismatch')
        rescored=score(rows,[by_id[r['id']] for r in rows])
        if any(report[k]!=rescored[k] for k in ('overall','slices','per_item')) or report['behavioral']!=score(behavioral,[by_id[r['id']] for r in behavioral]):
            raise ValueError('evaluation does not match raw outputs')
        for p in (path,PREVIOUS/f'metrics/{role}-eval.json'):
            sources[str(p)] = release.file_sha(p)
    if protocol_hash != manifest['protocol_sha256'] or fingerprint(rows) != manifest['golden_sha256']: raise ValueError('manifest protocol mismatch')
    candidate=reports[1]
    result={k:manifest[k] for k in ('model_id','model_sha256','protocol_sha256','golden_sha256','runtime_sha256')}
    result.update(status='complete',evaluation_run_id=candidate['evaluation_run_id'],metrics={k:candidate['overall'][k] for k in ('accuracy','format_rate')},sources=sources,leakage=proof)
    try:
        decision=quality_gate(reports[0],candidate,config['critical_slices'])
        result.update(passed=decision['passed'],gate=decision)
    except ValueError as e:
        result.update(passed=False,reason=str(e))
    return result
