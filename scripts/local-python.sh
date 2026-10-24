#!/usr/bin/env bash
# Use the checkout's Python environment and optional local browser libraries.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$repo_dir/.local-work"
python="$work_dir/venv/bin/python"
if [[ ! -x "$python" ]]; then
  printf 'Prepare .local-work/venv as described in runbooks/11-install-management-tools.md.\n' >&2
  exit 2
fi
export PLAYWRIGHT_BROWSERS_PATH="$work_dir/browsers"
browser_libs="$work_dir/browser-deps/root/usr/lib/x86_64-linux-gnu"
if [[ -d "$browser_libs" ]]; then
  export LD_LIBRARY_PATH="$browser_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec "$python" "$@"
