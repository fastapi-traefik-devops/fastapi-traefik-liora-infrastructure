#!/usr/bin/env bash
# Recover pruned local CI images using the preserved Dockerfiles and tool locks.
set -euo pipefail
umask 077
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
source_dir="$repo_dir/kubernetes/platform/upstream/infra/jenkins-host"
work_dir="$repo_dir/.local-work/phase9"
builder_name=liora-phase9-agent-recovery
mkdir -p "$work_dir"
cat > "$work_dir/buildkit-ci-recovery.toml" <<'CONFIG'
[worker.oci]
  max-parallelism = 1
CONFIG
if ! docker buildx inspect "$builder_name" >/dev/null 2>&1; then
  docker buildx create --name "$builder_name" --driver docker-container \
    --driver-opt memory=3g,memory-swap=3g,cpu-period=100000,cpu-quota=150000 \
    --buildkitd-config "$work_dir/buildkit-ci-recovery.toml" >/dev/null
fi
for component in dind agent; do
  docker buildx build --builder "$builder_name" --load --progress plain \
    --file "$source_dir/Dockerfile.$component" --tag "phase1/jenkins-$component:local" \
    "$source_dir" 2>&1 | tee "$work_dir/rebuild-$component.log"
done
docker image inspect phase1/jenkins-agent:local phase1/jenkins-dind:local \
  --format '{{.Id}}' > "$work_dir/rebuilt-image-ids.txt"
# These are recovered builds, not a claim of the original byte-identical images.
# Record image provenance; vulnerability handling follows the operator's
# current decision in runbook 17, including the educational-project deferral.
