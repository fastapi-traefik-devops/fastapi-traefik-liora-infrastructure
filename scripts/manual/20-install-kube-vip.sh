#!/usr/bin/env bash
set -euo pipefail

KUBE_VIP_VERSION="${KUBE_VIP_VERSION:-v1.2.3}"
API_VIP="${API_VIP:-192.168.77.10}"
VIP_INTERFACE="${VIP_INTERFACE:-ens18}"
IMAGE="ghcr.io/kube-vip/kube-vip:${KUBE_VIP_VERSION}"
RBAC_MANIFEST="${RBAC_MANIFEST:-https://kube-vip.io/manifests/rbac.yaml}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo env API_VIP=... VIP_INTERFACE=... $0"
  exit 1
fi

echo "Interface check:"
ip -br link show "$VIP_INTERFACE"

echo "[1/4] Apply kube-vip RBAC"
k3s kubectl apply -f "$RBAC_MANIFEST"

echo "[2/4] Pull pinned kube-vip image"
k3s ctr --namespace k8s.io images pull "$IMAGE"

echo "[3/4] Generate control-plane-only DaemonSet"
mkdir -p /var/lib/rancher/k3s/server/manifests

k3s ctr --namespace k8s.io run --rm --net-host \
  "$IMAGE" kube-vip-generator \
  /kube-vip manifest daemonset \
    --interface "$VIP_INTERFACE" \
    --address "$API_VIP" \
    --inCluster \
    --taint \
    --controlplane \
    --arp \
    --leaderElection \
  > /var/lib/rancher/k3s/server/manifests/kube-vip.yaml

echo "[4/4] Apply generated manifest"
k3s kubectl apply -f /var/lib/rancher/k3s/server/manifests/kube-vip.yaml

k3s kubectl -n kube-system rollout status daemonset/kube-vip-ds --timeout=120s || true

echo
echo "API VIP test:"
curl -k --fail --max-time 5 "https://${API_VIP}:6443/livez"
echo
