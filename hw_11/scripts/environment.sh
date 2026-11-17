#!/bin/sh
# Source at the top of each platform script after resolving the repository path.
export PATH="$HW11_ROOT/.tools:$PATH"
export KUBECONFIG="$HW11_ROOT/.state/kubeconfig"
export KIND_EXPERIMENTAL_PROVIDER="${KIND_EXPERIMENTAL_PROVIDER:-podman}"
HW11_CLUSTER=hw11
HW11_APP_IMAGE=docker.io/library/hw11:dev
HW11_NODE_IMAGE=kindest/node:v1.34.0@sha256:7416a61b42b1662ca6ca89f02028ac133a309a2a30ba309614e8ec94d976dc5a
HW11_METRICS_VERSION=v0.8.0
