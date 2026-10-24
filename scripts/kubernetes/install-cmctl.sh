#!/usr/bin/env bash
# Install the checksum-pinned Linux amd64 renewal CLI without global changes.
set -euo pipefail
[[ "$(uname -sm)" == 'Linux x86_64' ]] || { echo 'Linux amd64 required' >&2; exit 1; }
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
tool_dir="$repo_dir/.local-work/tools"
mkdir -p "$tool_dir"
target="$tool_dir/cmctl-v2.6.1"
checksum=0af054c26a2b64ce286fa868d029164867695a93c3eb893662ce16f35e708db0
if [[ -f "$target" ]] && printf '%s  %s\n' "$checksum" "$target" | sha256sum -c --status; then
    echo 'cmctl v2.6.1 already installed; checksum verified'
    exit 0
fi
download="$(mktemp "$tool_dir/.cmctl.XXXXXX")"
trap 'rm -f -- "$download"' EXIT
curl --fail --location --silent --show-error --max-time 120 \
    https://github.com/cert-manager/cmctl/releases/download/v2.6.1/cmctl_linux_amd64 -o "$download"
printf '%s  %s\n' "$checksum" "$download" | sha256sum -c --status
chmod 0755 "$download"
mv -- "$download" "$target"
echo 'cmctl v2.6.1 installed; checksum verified'
