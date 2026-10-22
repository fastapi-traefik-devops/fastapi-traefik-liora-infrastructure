#!/bin/sh
# Local/PR-only validation; never reads kubeconfig or applies manifests.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
rendered=$(mktemp -d)
trap 'rm -rf "$rendered"' EXIT HUP INT TERM
for environment in dev stage prod; do
    if command -v kustomize >/dev/null 2>&1; then
        kustomize build "$root/kubernetes/apps/liora/overlays/$environment" > "$rendered/$environment.yaml"
    else
        kubectl kustomize "$root/kubernetes/apps/liora/overlays/$environment" > "$rendered/$environment.yaml"
    fi
    python3 "$root/scripts/ci/validate_gitops.py" "$rendered/$environment.yaml" "$environment"
    if command -v kubeconform >/dev/null 2>&1; then
        kubeconform -strict -summary -kubernetes-version 1.35.0 "$rendered/$environment.yaml"
    elif [ "${REQUIRE_KUBECONFORM:-0}" = 1 ]; then
        printf '%s\n' 'kubeconform is required for CI schema validation' >&2
        exit 1
    else
        printf '%s\n' 'Schema validation not run: kubeconform unavailable locally' >&2
    fi
done
