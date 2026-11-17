#!/bin/sh
set -eu
HW11_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$HW11_ROOT/scripts/environment.sh"
case "$#" in
  0) ;;
  1) [ "$1" = --remove-image ] || exit 2 ;;
  *) exit 2 ;;
esac
kind delete cluster --name "$HW11_CLUSTER" --kubeconfig "$KUBECONFIG"
if [ "$#" -eq 1 ]; then
  "$KIND_EXPERIMENTAL_PROVIDER" image rm "$HW11_APP_IMAGE"
fi
