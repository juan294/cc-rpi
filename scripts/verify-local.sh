#!/usr/bin/env bash
# One local/CI selection. No remote reporting or dependency installation occurs.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 "$script_dir/verify-local.py" "$@"
