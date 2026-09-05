#!/usr/bin/env bash
# Thin compatibility entry point. The shared engine owns inventory and writes.
set -euo pipefail

rpi_source=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rpi_engine="$rpi_source/templates/scripts/rpi-distribution.py"
rpi_operation=plan
rpi_arguments=()
rpi_destination=false

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh --check
       scripts/install.sh --target PROJECT [--harness both|claude|codex]
          [--route direct|plugin] [--action install|update|detach] --output PLAN
          [--allow-capabilities CONFIG_COMPONENT_ID]
       scripts/install.sh --scope user [--state-root STATE]
          [--claude-skill-root DIR] [--codex-skill-root DIR] --output PLAN
       scripts/install.sh --apply PLAN
       scripts/install.sh --rollback JOURNAL

Planning reports conflicts and preserves current installation bytes. Review the
plan, then apply that exact file. --check with a destination inspects installation
state; without one it validates only this source package. User scope defaults to
~/.config/cc-rpi/installations/user, ~/.claude/skills and ~/.agents/skills.
Plugin installation/update/trust remains the native manager's responsibility.
USAGE
}
blocked() {
  printf 'BLOCKED / WHY: %s / FIX: bash %q --help\n' "$1" "$rpi_source/scripts/install.sh" >&2
  exit 1
}
value_required() {
  [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || blocked "missing value for $1"
}
runtime_required() {
  if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    printf '%s\n' 'BLOCKED / WHY: installation requires Python 3.11 or newer / FIX: uv python install 3.13 && uv run --python 3.13 bash scripts/install.sh --help; rerun the intended command through uv run --python 3.13' >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --check) rpi_operation=check; shift ;;
    --apply|--rollback)
      [[ $# -eq 2 && ${#rpi_arguments[@]} -eq 0 && "$rpi_operation" == plan ]] || blocked 'apply/rollback requires only its receipt path'
      value_required "$@"
      runtime_required
      if [[ "$1" == --apply ]]; then
        exec python3 "$rpi_engine" apply --plan "$2"
      fi
      exec python3 "$rpi_engine" rollback --journal "$2"
      ;;
    --target|--scope|--state-root|--claude-skill-root|--codex-skill-root|--harness|--route|--action|--output|--domain|--legacy-base|--allow-capabilities)
      value_required "$@"
      if [[ "$1" == --target || ( "$1" == --scope && "$2" == user ) ]]; then
        rpi_destination=true
      fi
      rpi_arguments+=("$1" "$2")
      shift 2
      ;;
    *) blocked "unsupported argument: $1" ;;
  esac
done

if [[ "$rpi_operation" == check && "$rpi_destination" == false ]]; then
  [[ ${#rpi_arguments[@]} -eq 0 ]] || blocked 'source-only check does not accept installation options without a destination'
  runtime_required
  python3 "$rpi_engine" validate --source "$rpi_source"
  exec python3 "$rpi_engine" check-generated --source "$rpi_source"
fi
[[ "$rpi_destination" == true ]] || blocked 'choose --target PROJECT or --scope user'
runtime_required
exec python3 "$rpi_engine" "$rpi_operation" --source "$rpi_source" "${rpi_arguments[@]}"
