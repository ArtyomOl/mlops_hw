#!/bin/sh
set -eu
HW11_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$HW11_ROOT/scripts/environment.sh"
cd "$HW11_ROOT"

for tool in kind helm kubectl curl "$KIND_EXPERIMENTAL_PROVIDER"; do
  command -v "$tool" >/dev/null || {
    printf '%s\n' "Required command not installed: $tool" >&2
    exit 1
  }
done
mkdir -p .state results
if [ ! -f results/platform-before.txt ]; then
  {
    date -u '+%FT%TZ'
    df -k .
    kind version
    kubectl version --client
    helm version --short
    "$KIND_EXPERIMENTAL_PROVIDER" version
    "$KIND_EXPERIMENTAL_PROVIDER" system df
    if [ "$KIND_EXPERIMENTAL_PROVIDER" = podman ] && [ "$(uname -s)" = Darwin ]; then
      podman machine inspect --format '{{.State}} cpus={{.Resources.CPUs}} memory_MiB={{.Resources.Memory}} disk_GiB={{.Resources.DiskSize}}'
      podman machine ssh free -m
      podman machine ssh df -k /var
    fi
  } > results/platform-before.txt
fi

if kind get clusters | grep -Fxq "$HW11_CLUSTER"; then
  kind export kubeconfig --name "$HW11_CLUSTER" --kubeconfig "$KUBECONFIG"
else
  kind create cluster --name "$HW11_CLUSTER" --image "$HW11_NODE_IMAGE" --kubeconfig "$KUBECONFIG" --wait 90s
fi

"$KIND_EXPERIMENTAL_PROVIDER" build --tag "$HW11_APP_IMAGE" .
image_revision=$("$KIND_EXPERIMENTAL_PROVIDER" image inspect "$HW11_APP_IMAGE" --format "{{.Id}}")
archive_dir=$(mktemp -d "$HW11_ROOT/.state/hw11-image.XXXXXXXX")
image_archive="$archive_dir/app.tar"
trap 'rm -f "$image_archive"; rmdir "$archive_dir"' EXIT
if [ "$KIND_EXPERIMENTAL_PROVIDER" = podman ]; then
  podman save --format docker-archive -o "$image_archive" "$HW11_APP_IMAGE"
else
  docker save -o "$image_archive" "$HW11_APP_IMAGE"
fi
kind load image-archive "$image_archive" --name "$HW11_CLUSTER"

curl -fsSL --retry 2 "https://github.com/kubernetes-sigs/metrics-server/releases/download/$HW11_METRICS_VERSION/components.yaml" -o .state/metrics-server-source.yaml
awk '
  { print }
  /- --secure-port=10250/ { print "        - --kubelet-insecure-tls"; patched=1 }
  END { if (!patched) exit 1 }
' .state/metrics-server-source.yaml > .state/metrics-server-kind.yaml
kubectl apply -f .state/metrics-server-kind.yaml

helm upgrade --install hw11 ./chart --namespace hw11 --create-namespace --set-string "image.revision=$image_revision" --wait --timeout 5m
kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s
kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=60s
"$HW11_ROOT/scripts/footprint.sh"
