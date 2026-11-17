#!/usr/bin/env python3
"""Exercise readiness, graceful rollout, rollback and abrupt failure via ClusterIP."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results' / 'a'
NAME = 'hw11-a'
SELECTOR = f'app.kubernetes.io/instance={NAME}'
SERVICE = f'http://{NAME}'
CLIENT = 'observer'
ENV = {**os.environ, 'PATH': f'{ROOT}/.tools:{os.environ["PATH"]}',
       'KUBECONFIG': os.environ.get('KUBECONFIG', str(ROOT / '.state/kubeconfig'))}


def run(*args, data=None, check=True):
    result = subprocess.run(args, input=data, text=True, capture_output=True, check=False,
                            cwd=ROOT, env=ENV, timeout=240)
    if check and result.returncode:
        raise RuntimeError(f'{args}: {result.stderr.strip()} {result.stdout.strip()}')
    return result.stdout


def kube(*args, **kwargs):
    return run('kubectl', '-n', NAME, *args, **kwargs)


def helm(*args):
    return run('helm', '-n', NAME, *args)


def deploy(version, warmup=20, mode='correct', fail=False):
    return helm('upgrade', '--install', NAME, 'chart', '--create-namespace',
                '--set', 'monitoring.enabled=false,hpa.enabled=false,replicaCount=2',
                '--set', f'model.version={version},backend.warmupSeconds={warmup},backend.probeMode={mode},backend.warmupFail={str(fail).lower()}',
                '--set', 'backend.enableExperimentFaults=true',
                '--set', 'resources.requests.cpu=50m,rollout.progressDeadlineSeconds=240', '--history-max', '12')


def rolled_out():
    return kube('rollout', 'status', f'deployment/{NAME}', '--timeout=210s')


def list_pods():
    return json.loads(kube('get', 'pods', '-l', SELECTOR, '-o', 'json'))['items']


def save_pod_logs(phase):
    for pod in list_pods():
        name = pod['metadata']['name']
        (OUT / f'{phase}-{name}.log').write_text(kube('logs', name, check=False))


def pod_ready(pod):
    return any(c['type'] == 'Ready' and c['status'] == 'True'
               for c in pod['status'].get('conditions', [])) and 'deletionTimestamp' not in pod['metadata']


def now():
    return time.time()


def record(path, payload):
    with path.open('a', encoding='utf8') as output:
        output.write(json.dumps(payload, ensure_ascii=False) + '\n')


def timeline(event, **data):
    record(OUT / 'events.jsonl', {'wall_s': now(), 'event': event, **data})
    print(event, data, flush=True)


@contextmanager
def observe(phase):
    stop = threading.Event()

    def watcher():
        while not stop.is_set():
            try:
                pods = list_pods()
                sl = json.loads(kube('get', 'endpointslices', '-l',
                                     f'kubernetes.io/service-name={NAME}', '-o', 'json'))
                endpoints = [{**e.get('conditions', {}), 'pod': e.get('targetRef', {}).get('name')}
                             for item in sl['items'] for e in item.get('endpoints', [])]
                record(OUT / 'timeline.jsonl', {'wall_s': now(), 'phase': phase,
                       'endpoints': endpoints, 'pods': [
                           {'pod': p['metadata']['name'], 'uid': p['metadata']['uid'],
                            'ready': pod_ready(p), 'created': p['metadata']['creationTimestamp'],
                            'terminating': 'deletionTimestamp' in p['metadata'],
                            'restarts': sum(c['restartCount'] for c in p['status'].get('containerStatuses', [])),
                            'version': p['metadata'].get('annotations', {}).get('hw11/model-version'),
                            'probe_mode': p['metadata'].get('annotations', {}).get('hw11/probe-mode')}
                           for p in pods]})
            except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                record(OUT / 'timeline.jsonl', {'wall_s': now(), 'phase': phase, 'observer_error': str(exc)})
            stop.wait(1.5)

    thread = threading.Thread(target=watcher)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=10)


def traffic(phase, count=18, interval=0.8, *, parts=1, chunk_ms=35, url=SERVICE, extra=None):
    path = OUT / f'{phase}.jsonl'
    payload = dict(prompt='Продолжи последний диалог', parts=parts, chunk_ms=chunk_ms, **(extra or {}))
    schedule = [{'offset_s': 0.5+i*interval, 'request_id': f'a-{phase}-{i}',
                 'payload': payload, 'capture_content': extra is not None} for i in range(count)]
    with path.open('w', encoding='utf8') as output, path.with_suffix('.stderr').open('w') as error:
        proc = subprocess.Popen(['kubectl', '-n', NAME, 'exec', '-i', CLIENT, '--', 'python',
                                 '/tmp/client.py', '--url', url, '--schedule', '-', '--timeout', '55'],
                                cwd=ROOT, env=ENV, stdin=subprocess.PIPE, stdout=output, stderr=error, text=True)
        proc.stdin.write(json.dumps(schedule)); proc.stdin.close()
    return proc, path


def collect(handle):
    proc, path = handle
    if proc.wait(timeout=110):
        raise RuntimeError(f'client exited with {proc.returncode}; see {path.with_suffix(".stderr")}')
    return [json.loads(line) for line in path.read_text().splitlines()]


def cold(mode):
    deploy('A', warmup=1)
    rolled_out()
    with observe(mode):
        handle = traffic(mode, count=65, interval=0.5)
        time.sleep(2)
        timeline(f'{mode}-upgrade')
        deploy('A', mode=mode)
        rolled_out()
        result = collect(handle)
        save_pod_logs(mode)
        return result


def wait_for_replacement(old_name):
    deadline = time.monotonic() + 80
    while time.monotonic() < deadline:
        pods = [p for p in list_pods() if p['metadata']['name'] != old_name and pod_ready(p)]
        if len(pods) == 2:
            return pods
        time.sleep(1)
    raise TimeoutError('replacement replica did not become ready')


def dialogue(name, url, marker):
    return collect(traffic(name, count=1, url=url, extra={'session_id': f'session-{marker}',
                   'history': [{'role': 'user', 'content': marker}]}))[0]


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / 'summary.json').unlink(missing_ok=True)
    for name in ('events.jsonl', 'timeline.jsonl'):
        (OUT / name).write_text('')
    timeline('start', utc=datetime.now(timezone.utc).isoformat())
    deploy('A', warmup=1)
    rolled_out()
    pod_spec = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': CLIENT},
                'spec': {'containers': [{'name': 'client', 'image': 'hw11:dev',
                         'imagePullPolicy': 'Never', 'command': ['python', '-c', 'import time; time.sleep(86400)'],
                         'resources': {'requests': {'cpu': '30m', 'memory': '32Mi'},
                                       'limits': {'cpu': '300m', 'memory': '128Mi'}}}]}}
    kube('apply', '-f', '-', data=json.dumps(pod_spec))
    kube('wait', '--for=condition=Ready', f'pod/{CLIENT}', '--timeout=60s')
    kube('exec', '-i', CLIENT, '--', 'python', '-c',
         'import sys; from pathlib import Path; Path("/tmp/client.py").write_text(sys.stdin.read())',
         data=(ROOT / 'load/client.py').read_text())

    early, corrected = cold('early'), cold('correct')
    with observe('rollout'):
        long = traffic('rollout-long', count=1, parts=40, chunk_ms=1000)
        broad = traffic('rollout', count=90, interval=0.55)
        time.sleep(4)
        start_roll = now()
        timeline('rollout-start', to='B')
        deploy('B')
        rolled_out()
        long_rows = collect(long)
        rollout_rows = collect(broad)
        after_b = collect(traffic('rollout-version', count=8, interval=0.2))
        save_pod_logs('rollout')

    deploy('A')
    rolled_out()
    history = json.loads(helm('history', NAME, '-o', 'json'))
    revision_a = history[-1]['revision']
    with observe('rollback'):
        timeline('bad-B-start', rollback_revision=revision_a)
        deploy('B', fail=True)
        during_bad = traffic('bad-B', count=60, interval=0.5)
        time.sleep(27)
        pending = [p for p in list_pods() if not pod_ready(p)
                   and p['metadata'].get('annotations', {}).get('hw11/model-version') == 'B']
        (OUT/'bad-B-pods.json').write_text(json.dumps(pending, indent=2))
        save_pod_logs('bad-B')
        helm('rollback', NAME, str(revision_a), '--wait', '--timeout', '90s')
        timeline('rollback-finished')
        bad_rows = collect(during_bad)
        after_a = collect(traffic('rollback-version', count=12, interval=0.25))

    names = list_pods()
    old = next(p for p in names if pod_ready(p))
    old_name, old_uid = old['metadata']['name'], old['metadata']['uid']
    old_url = f'http://{old["status"]["podIP"]}:8080'
    session_a = dialogue('session-a', old_url, 'CTRL-HW11-ALFA')
    session_b = dialogue('session-b', old_url, 'CTRL-HW11-BETA')
    with observe('kill'):
        killed = traffic('kill-stream', count=1, parts=32, chunk_ms=900, url=old_url)
        under_kill = traffic('kill-service', count=60, interval=0.5)
        time.sleep(4)
        timeline('forced-process-exit', pod=old_name)
        # The feature-flagged test endpoint exits the app before sending a response.
        kube('exec', old_name, '--', 'python', '-c',
             'from urllib.request import Request,urlopen; urlopen(Request("http://127.0.0.1:8080/fault/kill",method="POST"),timeout=4)',
             check=False)
        killed_rows = collect(killed)
        ambient_rows = collect(under_kill)
        rolled_out()
        (OUT / 'crashed-previous.log').write_text(kube('logs', old_name, '--previous', check=False))
        timeline('force-failure-recovered')

    # Independently replace the Pod, retain the same attached ConfigMap artifact.
    before = {p['metadata']['uid'] for p in list_pods()}
    with observe('replacement'):
        timeline('delete-pod', pod=old_name, uid=old_uid)
        kube('delete', f'pod/{old_name}', '--wait=false')
        replaced = next(p for p in wait_for_replacement(old_name) if p['metadata']['uid'] not in before)
        after = dialogue('session-a-after', f'http://{replaced["status"]["podIP"]}:8080', 'CTRL-HW11-ALFA')
        timeline('replacement-ready', pod=replaced['metadata']['name'], uid=replaced['metadata']['uid'])

    all_rollout = long_rows + rollout_rows + after_b
    checks = {
        'defect_reproduced': any(r.get('warmed') is False for r in early),
        'corrected_never_cold': all(r.get('warmed') is True for r in corrected if r['outcome'] == 'completed')
            and any(r['outcome'] == 'completed' for r in corrected),
        'graceful_rollout': all(r['outcome'] == 'completed' for r in all_rollout)
            and any(r['version'] == 'B' for r in after_b)
            and any((r.get('first_wall_s') or start_roll) < start_roll < r['completed_wall_s'] for r in long_rows),
        'bad_b_excluded_and_rollback': bool(pending) and all(r['version'] == 'A' and r['outcome'] == 'completed' for r in bad_rows + after_a),
        'abrupt_stream_aborted': any(r['outcome'] == 'aborted' and r['parts'] > 0 for r in killed_rows),
        'replaced_same_version': after['outcome'] == 'completed' and session_a['version'] == after['version'] == 'A'
            and session_a.get('artifact_sha256') == after.get('artifact_sha256')
            and bool(after.get('artifact_sha256')) and after['pod'] != session_a['pod'],
        'dialogues_isolated': all(marker in ''.join(row['text_parts']) and other not in ''.join(row['text_parts']) for row, marker, other in [
            (session_a, 'CTRL-HW11-ALFA', 'CTRL-HW11-BETA'),
            (session_b, 'CTRL-HW11-BETA', 'CTRL-HW11-ALFA'),
            (after, 'CTRL-HW11-ALFA', 'CTRL-HW11-BETA')]),
    }
    summary = {'checks': checks, 'early_requests': len(early),
               'early_cold': sum(r.get('warmed') is False for r in early),
               'corrected_requests': len(corrected), 'corrected_cold': sum(r.get('warmed') is False for r in corrected),
               'rollout_requests': len(all_rollout),
               'rollout_5xx': sum(500 <= (r['status'] or 0) for r in all_rollout),
               'rollout_unfinished': sum(r['outcome'] != 'completed' for r in all_rollout),
               'bad_b_requests': len(bad_rows), 'bad_b_unready_pods': len(pending),
               'kill_requests': [*killed_rows],
               'during_kill_success': sum(r['outcome'] == 'completed' for r in ambient_rows)}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    for pod in list_pods():
        name = pod['metadata']['name']
        (OUT / f'pod-{name}.log').write_text(kube('logs', name, check=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
