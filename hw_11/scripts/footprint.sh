#!/bin/sh
set -eu
HW11_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$HW11_ROOT/scripts/environment.sh"
cd "$HW11_ROOT"
mkdir -p results
try() {
  if ! "$@"; then
    printf 'Unavailable at sampling time: %s
' "$*"
  fi
}
{
  date -u '+%FT%TZ'
  df -k .
  kind version
  helm version --short
  kubectl version
  kubectl get nodes -o wide
  kubectl -n hw11 get pods -o wide
  kubectl -n hw11 get endpointslices
  kubectl get apiservice v1beta1.metrics.k8s.io
  try kubectl top nodes
  try kubectl -n hw11 top pods
  "$KIND_EXPERIMENTAL_PROVIDER" system df
  if [ "$KIND_EXPERIMENTAL_PROVIDER" = podman ]; then
    podman image inspect "$HW11_APP_IMAGE" --format '{{.Id}} {{.Size}}'
    podman image inspect docker.io/library/python:3.12.12-slim-bookworm --format '{{.Digest}} {{.Size}}'
    podman image inspect kindest/node:v1.34.0 --format '{{.Digest}} {{.Size}}'
    if [ "$(uname -s)" = Darwin ]; then
      podman machine ssh free -m
      podman machine ssh df -k /var
    fi
    podman exec hw11-control-plane crictl images
    podman exec hw11-control-plane du -sh /var/lib/containerd /var/lib/kubelet
  fi
  try kubectl -n hw11 exec deploy/hw11-prometheus -- du -sh /prometheus
  try kubectl -n hw11 exec deploy/hw11-grafana -- du -sh /var/lib/grafana
  try kubectl -n kube-system logs daemonset/kube-proxy --tail=120
} > results/platform-after.txt
cat results/platform-after.txt
