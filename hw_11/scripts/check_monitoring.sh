#!/bin/sh
set -eu
HW11_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$HW11_ROOT/scripts/environment.sh"
cd "$HW11_ROOT"
mkdir -p results

kubectl -n hw11 rollout status deployment/hw11-prometheus --timeout=90s
kubectl -n hw11 rollout status deployment/hw11-grafana --timeout=180s
kubectl -n hw11 exec deployment/hw11-prometheus -- promtool check config /etc/hw11/prometheus.yaml > results/platform-prom-config.txt
prom_proxy=/api/v1/namespaces/hw11/services/http:hw11-prometheus:http/proxy
grafana_proxy=/api/v1/namespaces/hw11/services/http:hw11-grafana:http/proxy
kubectl get --raw "$prom_proxy/api/v1/targets?state=active" > results/platform-prom-targets.json
kubectl get --raw "$grafana_proxy/api/health" > results/platform-grafana-health.json
kubectl get --raw "$grafana_proxy/api/dashboards/uid/hw11" > results/platform-grafana-dashboard.json
python3 - <<'PY'
import json
from pathlib import Path

results = Path("results")
targets = json.loads((results / "platform-prom-targets.json").read_text())["data"]["activeTargets"]
print("Prometheus pod targets:", [(target["labels"].get("pod"), target["health"]) for target in targets])
health = json.loads((results / "platform-grafana-health.json").read_text())
assert health["database"] == "ok", health
dashboard = json.loads((results / "platform-grafana-dashboard.json").read_text())["dashboard"]
assert len(dashboard["panels"]) == 8, dashboard["panels"]
print(f"Grafana {health['version']}: {dashboard['title']}, {len(dashboard['panels'])} panels")
PY
