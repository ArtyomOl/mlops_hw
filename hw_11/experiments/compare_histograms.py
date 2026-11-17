"""Compare exact Prometheus counter snapshots at the quiet edges of experiment C."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

from cluster import ROOT, Cluster, write_json
sys.path.insert(0, str(ROOT))
from load.summarize import group_summary


def snapshot_delta(metric, start, end, labels):
    # Fall back to zero for Pods which did not exist before the phase. A full-window
    # last sample includes a Pod that disappeared on the HPA downscale.
    before = f'last_over_time({metric}[8s] @ {start:.3f})'
    lookback = math.ceil(end - start) + 8
    after = f'last_over_time({metric}[{lookback}s] @ {end:.3f})'
    matching = f'on ({", ".join(labels)})'
    return f'({after} - {matching} ({before} or {matching} ({after} * 0)))'


def compare(cluster, directory):
    phases = json.loads((directory/'summary.json').read_text())
    attempts = [json.loads(line) for line in (directory/'requests.jsonl').read_text().splitlines()]
    result = {}
    for i, phase in enumerate(phases):
        selected = [row for row in attempts if row['phase'] == phase['name']]
        start = phase['start_at_unix_s'] - .10
        if i + 1 < len(phases):
            end = phases[i+1]['start_at_unix_s'] - .10
        else:
            end = max(row['completed_wall_s'] for row in selected) + 5.5
        time.sleep(max(0, end - time.time()))
        entry = {'start_at_unix_s': start, 'end_at_unix_s': end,
                 'client': group_summary(selected)['all'], 'prometheus': {}}
        for metric in ('hw11_ttfc_seconds', 'hw11_request_duration_seconds'):
            expr = snapshot_delta(metric+'_bucket', start, end, ('pod', 'le'))
            count = snapshot_delta(metric+'_count', start, end, ('pod',))
            p95 = f'histogram_quantile(0.95, sum by (le) ({expr}))'
            total = f'sum({count})'
            results = {}
            for label, query in [('p95_seconds', p95), ('samples', total), ('count_by_pod', count)]:
                response = cluster.prom('query', query=query, time=end)
                results[label] = {'promql': query, 'result': response['data']['result']}
            entry['prometheus'][metric] = results
        result[phase['name']] = entry
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context')
    parser.add_argument('--namespace', default='hw11-c')
    parser.add_argument('--results', type=Path, default=ROOT/'results/c')
    args = parser.parse_args()
    cluster = Cluster(context=args.context, namespace=args.namespace)
    write_json(args.results/'histograms-quiet-edges.json', compare(cluster,args.results))


if __name__ == '__main__':
    main()
