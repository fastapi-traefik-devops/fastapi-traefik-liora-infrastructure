#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get -y dist-upgrade
apt-get install -y \
  ca-certificates \
  curl \
  jq \
  openssl \
  qemu-guest-agent \
  vim \
  tcpdump \
  conntrack \
  socat

systemctl enable --now qemu-guest-agent || true

# Kubernetes expects swap to be disabled unless explicitly configured otherwise.
swapoff -a
sed -ri '/\sswap\s/s/^/# disabled-for-k3s: /' /etc/fstab

cat >/etc/modules-load.d/k3s.conf <<'EOF'
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

cat >/etc/sysctl.d/99-k3s.conf <<'EOF'
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF

sysctl --system >/dev/null

echo "Prepared $(hostname)"
echo
ip -br address
echo
ip route
