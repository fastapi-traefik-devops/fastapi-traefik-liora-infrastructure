#!/usr/bin/env bash
# Parse recovery data without executing it or exposing values in diagnostics.
set +x
set -uo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="${RECOVERY_PYTHON:-python3}"
if ! command -v "$python" >/dev/null 2>&1; then
  printf 'ERROR: Python 3 is required (set RECOVERY_PYTHON if using a virtual environment).\n' >&2
  exit 2
fi
exec "$python" -I "$script_dir/check_credentials.py" "$@"
