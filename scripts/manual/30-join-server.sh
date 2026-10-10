#!/usr/bin/env bash
set -euo pipefail

K3S_VERSION="${K3S_VERSION:-v1.36.4+k3s1}"
NODE_IP="${NODE_IP:?Set NODE_IP to this node LAN IP}"
API_VIP="${API_VIP:-192.168.77.10}"

: "${K3S_TOKEN:?Export K3S_TOKEN before running this script}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo -E so K3S_TOKEN is preserved."
  exit 1
fi

install -d -m 0755 /etc/rancher/k3s

cat >/etc/rancher/k3s/config.yaml <<EOF
server: "https://${API_VIP}:6443"
token: "${K3S_TOKEN}"
node-ip: "${NODE_IP}"
tls-san:
  - "${API_VIP}"
write-kubeconfig-mode: "0640"
EOF

curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="${K3S_VERSION}" sh -s - server

systemctl --no-pager --full status k3s || true
k3s kubectl get nodes -o wide
