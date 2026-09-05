#!/usr/bin/env bash
# Validate the canonical distribution and independently parse native metadata.
set -euo pipefail
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"
if [[ $# -gt 0 ]]; then
  arguments=()
  for directory in "$@"; do arguments+=(--skill-dir "$directory"); done
  exec python3 templates/scripts/rpi-distribution.py check-local-skills "${arguments[@]}"
fi
python3 templates/scripts/rpi-distribution.py validate
python3 templates/scripts/rpi-distribution.py check-native
python3 templates/scripts/rpi-distribution.py check-local-skills
