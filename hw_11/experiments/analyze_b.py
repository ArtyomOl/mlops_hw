"""Condense experiment B results by policy and by replicate without pooling p95s."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from cluster import ROOT, write_json


def quantile(item, field, percentile='p95'):
    return item[field][percentile]


def observed_intervals(log, trial_id):
    if not log.is_file():
        return [], [], 0
    started = {}
    finished = {}
    waits = []
    for line in log.read_text().splitlines():
        tail = line.find('{')
        if tail == -1:
            continue
        try:
            item = json.loads(line[tail:])
        except ValueError:
            continue
        request_id = item.get('request_id', '')
        if not request_id.startswith(trial_id + '-'):
            continue
        stamp = item['ts_unix_ms']
        if item['event'] == 'request_admitted':
            started[request_id] = stamp
            waited = item['queue_ms']
            if waited > 1:
                waits.append((stamp - waited, stamp))
        elif item['event'] in ('request_completed', 'request_aborted'):
            finished[request_id] = stamp
    both = started.keys() & finished.keys()
    running = [(started[r], finished[r]) for r in both]
    return running, waits, len(started) - len(both)


def occupancy(directory, trial, pods):
    intervals = {name: observed_intervals(directory/f'{name}.log', trial['trial']) for name,item in pods.items()
                 if (directory/f'{name}.log').is_file() or not item['requests']}
    start = trial['start_at_unix_s'] * 1000
    rows = []
    for offset in range(trial['duration_s'] * 10):
        stamp = start + offset * 100
        rows.append({'offset_s': offset / 10, 'pods': {pod: {
                'running': sum(a <= stamp < b for a,b in running),
                'waiting_admitted': sum(a <= stamp < b for a,b in waiting),
            } for pod,(running,waiting,_) in intervals.items()}})
    (directory/'occupancy.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    total = len(rows)
    for pod, (running, waiting, unmatched) in intervals.items():
        pods[pod].update(log_admissions_with_outcome=len(running),
                         log_admissions_without_outcome=unmatched,
                         idle_fraction_sampled=sum(not r['pods'][pod]['running'] for r in rows) / total)
    simultaneous = sum(any(ob['waiting_admitted'] for ob in row['pods'].values())
                       and any(not ob['running'] for ob in row['pods'].values()) for row in rows)
    return {'sampling_interval_ms': 100, 'sample_count': total,
            'waiting_while_another_idle_samples': simultaneous if len(intervals) >= 2 else None,
            'pods_with_occupancy': sorted(intervals)}


def analyze(result_dir):
    summaries = json.loads((result_dir / 'summary.json').read_text())
    groups = defaultdict(list)
    for summary in summaries:
        trial = summary['trial']
        pod_info = json.loads((result_dir / trial['trial'] / 'pods-before.json').read_text())
        active_names = {pod['metadata']['name'] for pod in pod_info['items']
                        if not pod['metadata'].get('deletionTimestamp')}
        overall = summary['all']
        pods = {}
        for name in sorted(active_names | set(summary['by_pod'])):
            item = summary['by_pod'].get(name)
            pods[name] = {'requests': item['planned'] if item else 0,
                          'completed': item['completed'] if item else 0,
                          'ttfc_p95_ms': quantile(item, 'ttfc_ms') if item else None,
                          'queue_p95_ms': quantile(item, 'queue_ms') if item else None}
        occupied = occupancy(result_dir / trial['trial'], trial, pods)
        request_counts = [v['requests'] for v in pods.values()]
        share = max(request_counts, default=0)/sum(request_counts) if sum(request_counts) else None
        record = {'trial': trial['trial'], 'namespace': trial['namespace'], 'pods': pods,
                  'max_pod_share': share, 'n_ttfc': overall['ttfc_ms']['n'],
                  'ttfc_p95_ms': quantile(overall, 'ttfc_ms'),
                  'queue_p95_ms': quantile(overall, 'queue_ms'),
                  'e2e_p95_ms': quantile(overall, 'e2e_ms'),
                  'send_late_p95_ms': quantile(overall, 'send_late_ms'),
                  'rejected': overall['rejected'], 'error_fraction': overall['error_fraction'],
                  'cache_hits': overall['cache_hits'], 'cache_misses': overall['cache_misses'],
                  'occupancy': occupied,
                  'source_ips': summary['source_addresses_seen'],
                  'client_routes': summary['client_to_pod']}
        groups[f'{trial["policy"]}:{trial["profile"]}'].append(record)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_dir', type=Path, nargs='?', default=ROOT / 'results/b')
    args = parser.parse_args()
    result = analyze(args.result_dir)
    write_json(args.result_dir/'analysis.json', result)
    for group, trials in result.items():
        print(group)
        for row in trials:
            print(f'  {row["trial"]}: TTFC p95={row["ttfc_p95_ms"]} ms (n={row["n_ttfc"]}); '
                  f'rejected={row["rejected"]}; max pod share={row["max_pod_share"]:.1%}; '
                  f'send lag p95={row["send_late_p95_ms"]} ms')


if __name__ == '__main__':
    main()
