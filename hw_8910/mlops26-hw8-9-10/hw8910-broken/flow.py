"""Prefect orchestration: the artifact is an existing run, no training is performed."""
import argparse
from pathlib import Path
from prefect import flow, task, get_run_logger
import lab
import release

@task(persist_result=True, cache_key_fn=lambda context, parameters: release.cache_key(Path(parameters['root'])/'input.txt', lab.read(Path(parameters['root'])/'config.json')))
def prepare(root: str):
    return lab.prepare(Path(root))

@task
def artifact(root: str):
    root=Path(root); manifest=lab.read(root/'manifest-B.json')
    release.verify_files(manifest, root)
    get_run_logger().info('Read existing artifact; no training performed: %s', manifest['artifact_uri'])
    return {'manifest':str(root/'manifest-B.json')}

@task
def gate(root: str, artifact_description: dict, report_name: str):
    manifest=lab.read(artifact_description['manifest']); report=lab.read(Path(root)/report_name)
    release.validate_release(manifest, report)
    return {'report':str(Path(root)/report_name)}

@task
def publish(root: str, report_description: dict, fail_after_publish: bool, prepared: dict):
    # lab.run performs validation and crash recovery again immediately before publishing.
    lab.run(Path(root), Path(report_description['report']).name, fail_after_publish=fail_after_publish, prepared=prepared)

def real_key(context, parameters):
    import real_release
    cfg=real_release.read(real_release.PREVIOUS/'evaluation/params.json')
    return release.cache_key(real_release.PREVIOUS/cfg['golden'],real_release.preparation_config())

@task(persist_result=True, cache_key_fn=real_key)
def prepare_real():
    import real_release
    result=real_release.prepare_data()
    get_run_logger().info('PREPARED real golden: %s',result['sha256'])
    return result

@task
def real_artifact():
    import real_release
    manifest=real_release.build_manifest()
    path=real_release.HERE/'real-baseline/candidate-manifest.json'
    release.atomic_json(path,manifest)
    get_run_logger().info('Existing training run %s, no training; artifact hash %s',manifest['training_run_id'],manifest['model_sha256'])
    return str(path)

@task
def real_gate(manifest_path: str):
    import real_release
    manifest=real_release.read(manifest_path)
    try:
        report=real_release.evaluate(manifest)
    except Exception as exc:
        report={k:manifest[k] for k in ('model_id','model_sha256','protocol_sha256','golden_sha256','runtime_sha256')}
        report.update(status='failed',passed=False,reason=f'{type(exc).__name__}: {exc}')
    path=real_release.HERE/'real-baseline/release-report.json'
    release.atomic_json(path,report)
    get_run_logger().info('QUALITY_GATE passed=%s reason=%s',report['passed'],report.get('reason',''))
    return str(path)

@task
def real_publish(manifest_path: str, report_path: str, fail_after_publish: bool=False):
    import real_release
    manifest=real_release.read(manifest_path); report=real_release.read(report_path)
    if report['passed'] is not True:
        get_run_logger().info('REJECTED: accepted pointer unchanged')
        return 'REJECTED'
    real_release.verify_manifest_files(manifest)
    if real_release.evaluate(manifest) != report:
        raise ValueError('gate decision or evaluation sources changed')
    for name, expected in report['sources'].items():
        if release.file_sha(name)!=expected: raise ValueError('evaluation source changed: '+name)
    release.validate_release(manifest,report)
    root=real_release.HERE/'real-baseline'; release_id=release.sha(release.canonical({'manifest':manifest,'report':report}))
    release.publish(manifest,report,root/'accepted.json')
    if fail_after_publish: raise RuntimeError('Injected failure after pointer update')
    journal=root/'publications.jsonl'
    records=[__import__('json').loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
    if not any(row['release_id']==release_id for row in records):
        with journal.open('a') as f:
            f.write(__import__('json').dumps({'release_id':release_id,'model_id':manifest['model_id']})+'\n'); f.flush()
            import os; os.fsync(f.fileno())
    return 'PUBLISHED'

@flow(log_prints=True)
def release_flow(root: str, report: str='report-B.json', fail_after_prepare: bool=False, fail_after_publish: bool=False, real: bool=False):
    if real:
        import json, os, uuid
        from pathlib import Path
        import real_release
        attempt=str(uuid.uuid4()); journal=real_release.HERE/'real-baseline/attempts.jsonl'
        def log(status, detail=None):
            with journal.open('a') as f:
                f.write(json.dumps({'attempt_id':attempt,'status':status,'detail':detail},ensure_ascii=False)+'\n')
                f.flush(); os.fsync(f.fileno())
        log('started')
        try:
            prepare_real()
            if fail_after_prepare: raise RuntimeError('Injected failure after preparation')
            manifest_path=real_artifact()
            decision=real_gate(manifest_path)
            result=real_publish(manifest_path,decision,fail_after_publish)
        except Exception as exc:
            log('failed',f'{type(exc).__name__}: {exc}')
            raise
        log('completed',result)
        return result
    prepared=prepare(root)
    if fail_after_prepare: raise RuntimeError('Injected failure after preparation')
    description=artifact(root)
    decision=gate(root,description,report)
    publish(root,decision,fail_after_publish,prepared)
    return prepared

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path('.lab'));p.add_argument('--report',default='report-B.json');p.add_argument('--fail-after-prepare',action='store_true');p.add_argument('--fail-after-publish',action='store_true');p.add_argument('--real',action='store_true');a=p.parse_args()
    release_flow(str(a.workspace.resolve()),a.report,a.fail_after_prepare,a.fail_after_publish,a.real)
