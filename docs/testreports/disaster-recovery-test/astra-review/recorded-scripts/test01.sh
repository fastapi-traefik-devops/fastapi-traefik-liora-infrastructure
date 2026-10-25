#!/bin/bash
set -euo pipefail
exec > >(tee disaster-recovery-local/evidence/real/01-kubernetes/verification-retry.log) 2>&1
trap 'printf "EXIT_CODE=%s\n" "$?"' EXIT
set -x
date --iso-8601=seconds
free -h
docker inspect --format '{{.Name}} memory_limit={{.HostConfig.Memory}}' k3d-liora-dr-20261024-server-0
k(){ docker exec -i k3d-liora-dr-20261024-server-0 kubectl "$@"; }
k cluster-info
k wait --for=condition=Ready nodes --all --timeout=90s
k get nodes -o wide
k get namespace kube-system -o custom-columns=NAME:.metadata.name,UID:.metadata.uid
k apply -f - < disaster-recovery-local/storage-test.yaml
k -n dr-storage rollout status deploy/persistence --timeout=120s
k -n dr-storage get pods,pvc -o wide
k -n dr-storage exec deploy/persistence -- cat /data/marker
k -n dr-storage rollout restart deploy/persistence
k -n dr-storage rollout status deploy/persistence --timeout=120s
k -n dr-storage exec deploy/persistence -- cat /data/marker
k -n dr-storage get pods,pvc -o wide
k -n dr-storage get events --sort-by=.lastTimestamp
k -n dr-storage scale deploy/persistence --replicas=0
free -h
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' k3d-liora-dr-20261024-server-0
