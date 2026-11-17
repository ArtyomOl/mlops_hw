"""Run isolated repeat blocks concurrently, recording node pressure and driver lag."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from cluster import ROOT, Cluster, write_json


def observe(cluster):
    sample = {'ts_wall_s': time.time()}
    for key, args in [('nodes', ('get', 'nodes', '-o', 'json')),
                      ('usage', ('get','--raw','/apis/metrics.k8s.io/v1beta1/nodes'))]:
        try:
            sample[key] = json.loads(cluster.kubectl(*args))
        except Exception as error:
            sample[key] = {'capture_error': str(error)}
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/b')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cluster = Cluster(context=args.context)
    repeat_namespaces = ('hw11', 'hw11-b2', 'hw11-b3')
    proxy = cluster.json('get', 'configmap', 'kube-proxy', '-n', 'kube-system')
    write_json(out/'network.json', {'proxy_mode_config': proxy['data']['config.conf'],
                                  'http': 'HTTP/1.1 Connection: close', 'context': cluster.context})
    logs = {}
    processes = {}
    with (out/'node-pressure.jsonl').open('a') as pressure:
        try:
            for repeat, namespace in enumerate(repeat_namespaces, 1):
                logs[repeat] = (out/f'controller-r{repeat}.log').open('a')
                cmd = [sys.executable, '-u', str(ROOT/'experiments/experiment_b.py'), '--namespace', namespace,
                       '--only-repeat', str(repeat), '--context', cluster.context, '--out', str(out), '--resume']
                processes[repeat] = subprocess.Popen(cmd, cwd=ROOT, stdout=logs[repeat], stderr=subprocess.STDOUT)
            known = set()
            next_pressure = 0
            while True:
                if time.monotonic() >= next_pressure:
                    pressure.write(json.dumps(observe(cluster)) + '\n')
                    pressure.flush()
                    next_pressure = time.monotonic() + 20
                result = {}
                for file in sorted(out.glob('*-r[123]/summary.json')):
                    try:
                        data = json.loads(file.read_text())
                        result[data['trial']['trial']] = data
                    except (ValueError, KeyError):
                        continue  # a child may be writing this file
                if result.keys() != known:
                    write_json(out/'summary.json',list(result.values()))
                    print('Finished trials:', ', '.join(sorted(result)), flush=True)
                    known = set(result)
                states = {i: p.poll() for i,p in processes.items()}
                if all(code is not None for code in states.values()):
                    if any(states.values()) or len(result) != 12:
                        raise RuntimeError(f'Experiment B incomplete ({states}); inspect controller logs in {out}')
                    return
                time.sleep(3)
        finally:
            for p in processes.values():
                if p.poll() is None:
                    p.terminate()
            for stream in logs.values():
                stream.close()


if __name__ == '__main__':
    main()
