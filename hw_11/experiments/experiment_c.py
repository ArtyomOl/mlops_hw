"""Experiment C: CPU HPA and latency/rejection alerts on a dedicated release."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading
import time

from cluster import CLIENTS, ROOT, Cluster, assign_ids, wait_until, write_json
from experiment_b import schedule
sys.path.insert(0, str(ROOT))
from load.summarize import group_summary

SETTINGS = {
    'hpa.enabled': 'true', 'hpa.minReplicas': 2, 'hpa.maxReplicas': 3,
    'hpa.cpuUtilization': 60, 'hpa.downscaleSeconds': 90,
    'backend.warmupSeconds': 12, 'backend.probeMode': 'correct',
    'backend.cpuWorkMs': 110, 'backend.processConcurrency': 2,
    'backend.queueCapacity': 4, 'backend.chunkDelayMs': 50,
    'monitoring.enabled': 'true', 'monitoring.grafanaEnabled': 'false',
    'monitoring.retentionVolume': '96Mi', 'monitoring.retentionSize': '50MB',
}


def save_snapshot(cluster, now, phase):
    def safe(fn):
        try:
            return fn()
        except Exception as error:
            return {'capture_error': str(error)}
    hpa = safe(lambda: cluster.json('get', 'hpa', cluster.release))
    pods = safe(lambda: cluster.json('get', 'pods', '-l', cluster.selector))
    metrics = safe(lambda: json.loads(cluster.kubectl('get', '--raw',
        f'/apis/metrics.k8s.io/v1beta1/namespaces/{cluster.namespace}/pods')))
    alerts = safe(lambda: cluster.prom('alerts'))
    endpoints = safe(lambda: cluster.json('get', 'endpointslice', '-l',
                                          f'kubernetes.io/service-name={cluster.release}'))
    pod_status = [
        {'name': p['metadata']['name'], 'created': p['metadata']['creationTimestamp'],
         'deleting': p['metadata'].get('deletionTimestamp'), 'phase': p['status'].get('phase'),
         'ready': next((c for c in p['status'].get('conditions', []) if c['type'] == 'Ready'), None)}
        for p in pods.get('items', [])
    ]
    return {'ts_wall_s': now, 'phase': phase, 'hpa': hpa.get('status', hpa), 'pods': pod_status,
            'cpu_metrics': metrics, 'alerts': alerts.get('data', alerts), 'endpoints': endpoints}


def collect(cluster, state, stop, output):
    with output.open('w') as stream:
        while not stop.is_set():
            start = time.time()
            sample = save_snapshot(cluster, start, state['phase'])
            stream.write(json.dumps(sample, ensure_ascii=False) + '\n')
            stream.flush()
            stop.wait(max(0.2, 4 - (time.time() - start)))


def mode(cluster, out, name, duration, rps, profile, policy):
    rows = assign_ids(schedule(duration, rps, profile), name)
    write_json(out / f'schedule-{name}.json', rows)
    start = time.time() + 5
    suffix = '-affinity' if policy == 'affinity' else ''
    url = f'http://{cluster.release}{suffix}'
    phase = {'name': name, 'duration_s': duration, 'rps': rps, 'policy': policy, 'profile': profile,
             'start_at_unix_s': start, 'stop_dispatch_at_unix_s': start + duration}
    write_json(out / f'phase-{name}.json', phase)
    print(f'{name}: {url}, {rps} requests/s for {duration}s', flush=True)
    attempts = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        commands = [pool.submit(cluster.dispatch, client, url, [row for row in rows if row['client'] == client],
                                start, duration) for client in CLIENTS]
        for command in commands:
            attempts.extend(json.loads(line) for line in command.result().splitlines() if line)
    if len(attempts) != len(rows) or {r['request_id'] for r in attempts} != {r['request_id'] for r in rows}:
        raise RuntimeError(f'{name}: client data lacks scheduled request ids')
    with (out / 'requests.jsonl').open('a') as stream:
        for row in sorted(attempts, key=lambda r: r['sequence']):
            stream.write(json.dumps({**row, 'phase': name}, ensure_ascii=False) + '\n')
    phase['summary'] = group_summary(attempts)
    print(f'{name}: {phase["summary"]["all"]["completed"]}/{len(rows)} successful', flush=True)
    return phase


def capture_histograms(cluster, out, phases):
    result = {}
    for phase in phases:
        duration = phase['duration_s']
        start = phase['start_at_unix_s']
        end = phase['stop_dispatch_at_unix_s']
        sample = {}
        for label, metric in [('ttfc', 'hw11_ttfc_seconds'), ('duration', 'hw11_request_duration_seconds')]:
            query = f'histogram_quantile(0.95, sum by (le) (increase({metric}_bucket[{duration}s])))'
            counts = f'sum(increase({metric}_count[{duration}s]))'
            sample[label] = {'promql': query, 'count_promql': counts,
                             'p95': cluster.prom('query', query=query, time=end),
                             'samples': cluster.prom('query', query=counts, time=end)}
        # Compare by completion inside the exact scrape query window.
        rows = [json.loads(line) for line in (out/'requests.jsonl').read_text().splitlines()]
        eligible = [r for r in rows if start <= r['completed_wall_s'] <= end and r['outcome'] == 'completed']
        sample['client_same_completion_window'] = group_summary(eligible)['all']
        result[phase['name']] = sample
    write_json(out / 'histograms.json', result)


def summarize_observations(samples):
    events = {'desired_changes': [], 'ready_changes': [], 'first_seen_pods': {},
              'first_ready_pods': {}, 'alerts': {name: [] for name in ('HighTTFC', 'HighRejectRatio')}}
    previous = {}
    for sample in samples:
        t = sample['ts_wall_s']; phase = sample['phase']
        hpa = sample['hpa']
        desired = hpa.get('desiredReplicas')
        ready = sum((pod['ready'] or {}).get('status') == 'True' and not pod['deleting'] for pod in sample['pods'])
        for field, value in [('desired', desired), ('ready', ready)]:
            if value is not None and value != previous.get(field):
                events[f'{field}_changes'].append({'ts_wall_s': t, 'replicas': value, 'phase': phase})
                previous[field] = value
        for pod in sample['pods']:
            events['first_seen_pods'].setdefault(pod['name'], {'observed_at': t, 'created': pod['created']})
            if (pod['ready'] or {}).get('status') == 'True':
                events['first_ready_pods'].setdefault(pod['name'], pod['ready']['lastTransitionTime'])
        if 'capture_error' in sample['alerts']:
            continue
        alert_states = {a['labels']['alertname']: a['state'] for a in sample['alerts'].get('alerts', [])}
        for name in set(alert_states) | set(events['alerts']):
            state = alert_states.get(name, 'inactive')
            changes = events['alerts'].setdefault(name, [])
            if not changes or changes[-1]['state'] != state:
                changes.append({'ts_wall_s': t, 'state': state, 'phase': phase})
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context')
    parser.add_argument('--namespace', default='hw11-c')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/c')
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'requests.jsonl').exists():
        parser.error('choose a new --out directory for a fresh run')
    cluster = Cluster(namespace=args.namespace, context=args.context)
    cluster.kubectl('get', '--raw', '/apis/metrics.k8s.io/v1beta1')
    cluster.helm('upgrade', '--install', cluster.release, './chart', '--create-namespace', '--set',
                 ','.join(f'{k}={v}' for k,v in SETTINGS.items()))
    write_json(out / 'values.json', SETTINGS)
    addresses = cluster.start_clients()
    write_json(out / 'client-ips.json', addresses)
    cluster.kubectl('rollout', 'status', 'deployment/'+cluster.release, '--timeout=120s', timeout=126)
    def primed():
        try:
            hpa = cluster.json('get', 'hpa', cluster.release)
            status = hpa.get('status', {})
            deployment = cluster.json('get', 'deployment', cluster.release)
            return (status.get('currentMetrics') and status.get('desiredReplicas') == 2
                    and deployment.get('status', {}).get('availableReplicas') == 2
                    and cluster.prom('alerts').get('status') == 'success')
        except Exception:
            return False
    wait_until(primed, 100)
    write_json(out / 'hpa-before.json', cluster.json('get', 'hpa', cluster.release))
    stop = threading.Event(); state = {'phase': 'baseline'}
    poll = threading.Thread(target=collect, args=(cluster, state, stop, out / 'timeline.jsonl'))
    poll.start()
    phases = []
    planned = [
        ('baseline', 35, 1, 'uniform', 'affinity'),
        ('hot-scale-up', 80, 10, 'skew80', 'affinity'),
        ('overload-alerts', 65, 25, 'skew80', 'affinity'),
        ('recover-scale-down', 145, 1, 'uniform', 'affinity'),
    ]
    try:
        for name, duration, rps, profile, policy in planned:
            state['phase'] = name
            phases.append(mode(cluster, out, name, duration, rps, profile, policy))
            write_json(out / 'summary.json', phases)
    finally:
        stop.set(); poll.join()
    samples = [json.loads(line) for line in (out / 'timeline.jsonl').read_text().splitlines()]
    write_json(out / 'observations.json', summarize_observations(samples))
    write_json(out / 'hpa-after.json', cluster.json('get', 'hpa', cluster.release))
    capture_histograms(cluster, out, phases)
    print('HPA and alert observations:', out / 'observations.json', flush=True)


if __name__ == '__main__':
    main()
