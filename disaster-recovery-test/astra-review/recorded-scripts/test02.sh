#!/bin/bash
set -u
exec > >(tee disaster-recovery-local/evidence/real/02-cloudnativepg-r2/dependencies.log) 2>&1
set -x
date --iso-8601=seconds
for component in cert-manager barman-cloud; do
 kubectl kustomize "infrastructure/kubernetes/platform/$component" > "disaster-recovery-local/$component.yaml" || exit 1
 docker exec -i k3d-liora-dr-20261024-server-0 kubectl apply --server-side -f - < "disaster-recovery-local/$component.yaml" || exit 1
 if [ "$component" = cert-manager ]; then ns=cert-manager; dep=cert-manager-webhook; else ns=cnpg-system; dep=barman-cloud; fi
 docker exec k3d-liora-dr-20261024-server-0 kubectl -n "$ns" rollout status "deployment/$dep" --timeout=90s
 printf 'ROLLOUT_EXIT_CODE=%s\n' "$?"
 docker exec k3d-liora-dr-20261024-server-0 kubectl -n "$ns" get pods -o wide
done
docker exec k3d-liora-dr-20261024-server-0 kubectl -n cnpg-system get certificates,issuers
free -h
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' k3d-liora-dr-20261024-server-0
