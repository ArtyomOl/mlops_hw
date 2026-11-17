"""Shared helpers for the HW11 experiments; all actions target the dedicated namespace."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = [f'hw11-load-{i}' for i in range(4)]


class Cluster:
    def __init__(self, namespace='hw11', context=None, image='hw11:dev', release=None):
        self.namespace = namespace
        self.context = context or os.environ.get('HW11_CONTEXT', 'kind-hw11')
        self.image = image
        self.release = release or namespace
        self.selector = f'app.kubernetes.io/name=hw11,app.kubernetes.io/instance={self.release}'

    def kubectl(self, *args, data=None, check=True, timeout=45):
        return subprocess.run(
            ['kubectl', '--context', self.context, '-n', self.namespace, *args],
            input=data, check=check, text=True, capture_output=True, timeout=timeout,
        ).stdout

    def json(self, *args):
        return json.loads(self.kubectl(*args, '-o', 'json'))

    def apply(self, obj):
        return self.kubectl('apply', '-f', '-', data=json.dumps(obj))

    def helm(self, *args):
        return subprocess.run(
            ['helm', '--kube-context', self.context, '-n', self.namespace, *args],
            cwd=ROOT, check=True, text=True, capture_output=True, timeout=160,
        ).stdout

    def start_clients(self):
        self.apply({
            'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': 'hw11-load-driver'},
            'data': {'client.py': (ROOT / 'load/client.py').read_text()},
        })
        for name in CLIENTS:
            self.apply({
                'apiVersion': 'v1', 'kind': 'Pod',
                'metadata': {'name': name, 'labels': {'hw11-purpose': 'load-driver'}},
                'spec': {
                    'automountServiceAccountToken': False,
                    'terminationGracePeriodSeconds': 2,
                    'containers': [{
                        'name': 'driver', 'image': self.image, 'imagePullPolicy': 'Never',
                        'command': ['python', '-c', 'import time; time.sleep(86400)'],
                        'env': [{'name': env, 'valueFrom': {'fieldRef': {'fieldPath': field}}}
                                for env, field in [('CLIENT_NAME', 'metadata.name'), ('CLIENT_IP', 'status.podIP')]],
                        'resources': {'requests': {'cpu': '25m', 'memory': '24Mi'},
                                      'limits': {'cpu': '300m', 'memory': '96Mi'}},
                        'volumeMounts': [{'name': 'driver', 'mountPath': '/driver', 'readOnly': True}],
                    }],
                    'volumes': [{'name': 'driver', 'configMap': {'name': 'hw11-load-driver'}}],
                },
            })
        self.kubectl('wait', '--for=condition=Ready', 'pod', '-l', 'hw11-purpose=load-driver', '--timeout=60s', timeout=66)
        pods = self.json('get', 'pods', '-l', 'hw11-purpose=load-driver')['items']
        addresses = {item['metadata']['name']: item['status']['podIP'] for item in pods}
        if set(addresses) != set(CLIENTS) or len(set(addresses.values())) != 4:
            raise RuntimeError(f'Expected four different client IPs, got {addresses}')
        return addresses

    def dispatch(self, client, url, rows, start_at, duration, timeout=12):
        return self.kubectl('exec', '-i', client, '--', 'python', '/driver/client.py',
                            '--url', url, '--schedule', '-', '--start-at', str(start_at),
                            '--timeout', str(timeout), data=json.dumps(rows),
                            timeout=duration + timeout + 25)

    def prom(self, path, **params):
        suffix = f'?{urlencode(params)}' if params else ''
        code = 'import sys, urllib.request; print(urllib.request.urlopen(sys.argv[1], timeout=8).read().decode())'
        return json.loads(self.kubectl('exec', CLIENTS[0], '--', 'python', '-c', code,
                                       f'http://{self.release}-prometheus:9090/api/v1/' + path + suffix))


def write_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    Path(stream.name).replace(path)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def assign_ids(rows, trial):
    for row in rows:
        row['request_id'] = f'{trial}-{row["sequence"]:05d}'
    return rows


def wait_until(predicate, limit, interval=3):
    deadline = time.monotonic() + limit
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(f'condition not reached in {limit}s')
        time.sleep(interval)
