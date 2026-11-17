"""Experiment B: ClientIP versus ordinary Service, four controlled traffic cells."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import sys
import time

from cluster import CLIENTS, ROOT, Cluster, assign_ids, read_rows, wait_until, write_json
sys.path.insert(0, str(ROOT))
from load.summarize import group_summary

POLICIES = {'ordinary': '', 'affinity': '-affinity'}
TRAFFIC = ('uniform', 'skew80')
VALUES = {
    'hpa.enabled': 'false', 'replicaCount': 2, 'rollout.progressDeadlineSeconds': 180,
    'model.version': 'A', 'backend.warmupSeconds': 1, 'backend.probeMode': 'correct',
    'backend.warmupFail': 'false', 'backend.processConcurrency': 1,
    'backend.queueCapacity': 4, 'backend.cacheCapacity': 16,
    'backend.cacheHitMs': 15, 'backend.cacheMissMs': 100, 'backend.chunkDelayMs': 50,
    'backend.cpuWorkMs': 0,
}


def schedule(duration, rps, profile):
    payloads = random.Random(1729)
    routes = random.Random(3201)
    rows = []
    # Each 20 arrivals have exactly the target traffic mixture, shuffled in the block.
    for i in range(duration * rps):
        if i % 20 == 0:
            clients = [0] * 16 + [1, 2, 3, 1] if profile == 'skew80' else [0, 1, 2, 3] * 5
            routes.shuffle(clients)
        prefix = f'prefix-{payloads.randrange(6):02d}'
        rows.append({'offset_s': round(i / rps, 6), 'sequence': i,
                     'client': CLIENTS[clients[i % 20]], 'payload': {
                         'prompt': 'Continuation of a controlled request for Kubernetes lab ' + prefix,
                         'parts': 5, 'chunk_ms': 50, 'prefix': prefix,
                     }})
    return rows


def snapshots(cluster, directory, suffix):
    for kind, args in {
        'pods': ('get', 'pods', '-l', cluster.selector),
        'endpoints': ('get', 'endpointslice'),
        'services': ('get', 'service', cluster.release, cluster.release + '-affinity'),
    }.items():
        write_json(directory / f'{kind}-{suffix}.json', cluster.json(*args))


def experiment(cluster, out, trial, policy, profile, duration, rps, reset=True):
    directory = out / trial
    directory.mkdir(parents=True, exist_ok=False)
    deployment = 'deployment/' + cluster.release
    if reset:
        # Quiescent between trials. Scaling to zero before replacement also avoids surge
        # contention when running multiple isolated blocks on the same small node.
        cluster.kubectl('scale', deployment, '--replicas=0')
        wait_until(lambda: not cluster.json('get', 'pods', '-l', cluster.selector)['items'], 120)
        cluster.kubectl('scale', deployment, '--replicas=2')
    def ready():
        current = cluster.json('get', deployment)
        status = current.get('status', {})
        return (status.get('observedGeneration') == current['metadata']['generation']
                and status.get('availableReplicas') == 2 and status.get('updatedReplicas') == 2)
    wait_until(ready, 150)
    snapshots(cluster, directory, 'before')
    rows = assign_ids(schedule(duration, rps, profile), trial)
    write_json(directory / 'schedule.json', rows)
    start = time.time() + 5
    url = f'http://{cluster.release}{POLICIES[policy]}'
    context = {'trial': trial, 'policy': policy, 'profile': profile, 'duration_s': duration, 'rps': rps,
               'start_at_unix_s': start, 'stop_dispatch_at_unix_s': start + duration,
               'namespace': cluster.namespace, 'initial_cache': 'empty after quiescent scale to zero and replacement', 'http': 'HTTP/1.1 Connection: close',
               'service_url': url, 'requested_mix': '80/20' if profile == 'skew80' else '25/25/25/25'}
    write_json(directory / 'trial.json', context)
    print(f'{trial}: {duration}s, {rps} requests/s, {url}', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {client: pool.submit(cluster.dispatch, client, url, [row for row in rows if row['client'] == client],
                                       start, duration) for client in CLIENTS}
        for client, future in futures.items():
            (directory / f'{client}.jsonl').write_text(future.result())
    attempts = [row for client in CLIENTS for row in read_rows(directory / f'{client}.jsonl')]
    if len(attempts) != len(rows) or {r['request_id'] for r in attempts} != {r['request_id'] for r in rows}:
        raise RuntimeError(f'{trial}: client data lacks scheduled request ids')
    (directory / 'requests.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n'
        for row in sorted(attempts, key=lambda r: r['sequence'])))
    data = group_summary(attempts)
    data['trial'] = context
    write_json(directory / 'summary.json', data)
    snapshots(cluster, directory, 'after')
    for name in data['by_pod']:
        try:
            (directory / f'{name}.log').write_text(cluster.kubectl('logs', name, '--since=4m'))
        except Exception as error:
            (directory / f'{name}.error.txt').write_text(str(error)+'\n')
    print(f'{trial}: {data["all"]["completed"]}/{len(rows)} completed; '
          f'TTFC p95 {data["all"]["ttfc_ms"]["p95"]} ms; ' +
          ', '.join(f'{key}={val["planned"]}' for key, val in data['by_pod'].items()), flush=True)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context')
    parser.add_argument('--namespace', default='hw11')
    parser.add_argument('--only-repeat', type=int, choices=range(1, 4), help='run the four cells for this repeat only')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/b')
    parser.add_argument('--duration', type=int, default=120)
    parser.add_argument('--rps', type=int, default=6)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--smoke', action='store_true', help='permit short run for engineering verification')
    parser.add_argument('--resume', action='store_true', help='skip trials with completed summaries')
    args = parser.parse_args()
    if min(args.duration, args.rps, args.repeats) < 1:
        parser.error('duration, repeats and rps must be positive')
    if not args.smoke and (args.duration < 120 or args.repeats < 3):
        parser.error('the assignment requires at least 120 s and three trials per cell')
    cluster = Cluster(context=args.context, namespace=args.namespace)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.namespace == 'hw11':
        cluster.helm('upgrade', cluster.release, './chart', '--reuse-values', '--set',
                     ','.join(f'{key}={val}' for key, val in VALUES.items()))
    else:
        cluster.helm('upgrade', '--install', cluster.release, './chart', '--create-namespace', '--set',
                     ','.join(f'{key}={val}' for key, val in {**VALUES, 'monitoring.enabled':'false'}.items()))
    addresses = cluster.start_clients()
    meta = {'backend': VALUES, 'client_pod_ips': addresses, 'context': cluster.context,
            'kubernetes': cluster.json('version'), 'planned_duration_s': args.duration,
            'repeats': args.repeats, 'rps': args.rps, 'smoke': args.smoke}
    label = f'-r{args.only_repeat}' if args.only_repeat else ''
    write_json(args.out / f'environment{label}.json', meta)
    order = [('ordinary', 'uniform'), ('affinity', 'uniform'), ('affinity', 'skew80'), ('ordinary', 'skew80')]
    all_summaries = []
    repeats = [args.only_repeat] if args.only_repeat else range(1, args.repeats + 1)
    for repeat in repeats:
        cells = order if repeat % 2 else list(reversed(order))
        for policy, profile in cells:
            trial = f'{policy}-{profile}-r{repeat}'
            if args.resume and (args.out / trial / 'summary.json').is_file():
                data = json.loads((args.out / trial / 'summary.json').read_text())
                label = data['trial']
                if label['duration_s'] != args.duration or label['rps'] != args.rps:
                    raise RuntimeError(f'Parameters differ from existing {trial}')
            else:
                if args.resume and (args.out / trial).exists():
                    partial = args.out / trial
                    partial.rename(partial.with_name(f'{trial}-partial-{time.time_ns()}'))
                data = experiment(cluster, args.out, trial, policy, profile, args.duration, args.rps,
                                  reset=True)
            all_summaries.append(data)
            write_json(args.out / f'summary{label}.json', all_summaries)


if __name__ == '__main__':
    main()
