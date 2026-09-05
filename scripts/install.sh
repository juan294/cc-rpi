#!/usr/bin/env bash
# Compatibility entry point for the native RPI distribution.
# --check validates the local package and checked-in generated output without
# modifying any user/project installation. Transactional user installation is
# added with the lifecycle engine; this milestone never uses the old copy loop.
set -euo pipefail

rpi_source=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rpi_engine="$rpi_source/templates/scripts/rpi-distribution.py"

case "${1:-}" in
  --check)
    python3 "$rpi_engine" validate --source "$rpi_source"
    exec python3 "$rpi_engine" check-generated --source "$rpi_source"
    ;;
  --help|-h)
    printf 'Usage: scripts/install.sh --check\n'
    printf 'Validate the native package locally; user/project files are unchanged.\n'
    ;;
  "")
    printf 'BLOCKED: transactional user installation is not available in this local milestone\n' >&2
    printf 'WHY: the v1 overwrite loop cannot preserve custom user commands safely\n' >&2
    printf 'FIX: run the read-only package validation first:\n  bash %q --check\n' "$rpi_source/scripts/install.sh" >&2
    exit 1
    ;;
  *)
    printf 'BLOCKED: unsupported installer argument\nWHY: expected --check or --help\nFIX: bash %q --help\n' "$rpi_source/scripts/install.sh" >&2
    exit 1
    ;;
esac
