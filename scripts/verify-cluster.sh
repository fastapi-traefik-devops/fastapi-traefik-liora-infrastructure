#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-kubectl}"

echo "== Nodes =="
$KUBECTL get nodes -o wide

echo
echo "== System Pods =="
$KUBECTL get pods -n kube-system -o wide

echo
echo "== Traefik =="
$KUBECTL -n kube-system get svc traefik -o wide

echo
echo "== ServiceLB pods =="
$KUBECTL -n kube-system get pods -o wide | grep -E '(^NAME|svc-)' || true

echo
echo "== kube-vip =="
$KUBECTL -n kube-system get ds kube-vip-ds -o wide || true
$KUBECTL -n kube-system get pods -l name=kube-vip-ds -o wide || true

echo
echo "== etcd snapshot capability =="
echo "Run on a server: sudo k3s etcd-snapshot save --name manual-checkpoint"
