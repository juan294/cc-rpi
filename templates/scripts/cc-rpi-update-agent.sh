#!/usr/bin/env bash
# Explicitly opted-in, project-scoped local update launcher for Claude Code.
# Configure RPI_UPDATE_ENABLED=1, absolute CC_RPI_PATH and RPI_PROJECT_ROOT,
# RPI_HARNESS=claude|codex|both, and RPI_ROUTE=direct|plugin in the scheduler.
# For direct invocation also bind RPI_UPDATE_SKILL_DIR to the actual discovered
# user-scope rpi-update skill. Plugin invocation loads the local source package
# for this session only. Do not mix direct and plugin registrations.
#
# Requires Python 3.11+, Git and a Claude CLI supporting --plugin-dir,
# --permission-mode dontAsk and --permission-prompts none (verified in 2.1.261).
# Configure native authentication/permissions through the owner's supported
# setup before opting in. There is no inference auth probe or permission bypass.
# A blocked update remains blocked; the process reports both CLI/check exits.
#
# Optional launchd/cron schedules are installed separately. Diagnose their actual
# PATH, authentication and resource limits; historical launchd workarounds are not
# universal requirements. Never rewrite HOME or source an interactive rc file.
# Reports use unique task-owned .rpi/local/update-runs directories. Preserve these
# and lifecycle journals on failure; there is no blind retry of partial mutation.
set -euo pipefail

blocked() {
  printf 'BLOCKED / WHY: %s / FIX: %s\n' "$1" "$2" >&2
  exit 1
}
[[ ${RPI_UPDATE_ENABLED:-} == 1 ]] || blocked 'scheduled updates are not opted in' 'set RPI_UPDATE_ENABLED=1 only for the authorized project scope'
[[ ${CC_RPI_PATH:-} == /* && -d "$CC_RPI_PATH" ]] || blocked 'source must be an existing absolute directory' 'set CC_RPI_PATH to the verified local source'
[[ ${RPI_PROJECT_ROOT:-} == /* && -d "$RPI_PROJECT_ROOT" ]] || blocked 'target must be an existing absolute directory' 'set RPI_PROJECT_ROOT to the intended Git root'
case ${RPI_HARNESS:-} in claude|codex|both) ;; *) blocked 'harness scope is missing or invalid' 'set RPI_HARNESS=claude, codex or both' ;; esac
case ${RPI_ROUTE:-} in direct|plugin) ;; *) blocked 'installation route is missing or invalid' 'set RPI_ROUTE=direct or plugin to match installed ownership' ;; esac
CC_RPI_PATH=$(cd -- "$CC_RPI_PATH" && pwd -P)
PROJECT_ROOT=$(cd -- "$RPI_PROJECT_ROOT" && pwd -P)
[[ $(git -C "$PROJECT_ROOT" rev-parse --show-toplevel) == "$PROJECT_ROOT" ]] || blocked 'target is not the Git root' 'bind RPI_PROJECT_ROOT to the actual intended repository root'
command -v python3 >/dev/null || blocked 'Python is missing' 'configure Python 3.11+ on the scheduler PATH'
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || blocked 'Python is older than 3.11' 'configure a supported interpreter on PATH'
CLAUDE_BIN=${CLAUDE_BIN:-$(command -v claude || true)}
[[ -n "$CLAUDE_BIN" && -x "$CLAUDE_BIN" ]] || blocked 'Claude CLI is unavailable' 'set CLAUDE_BIN to its actual executable path'
ENGINE="$CC_RPI_PATH/templates/scripts/rpi-distribution.py"
NATIVE_SKILL="$CC_RPI_PATH/generated/claude/skills/rpi-update"
for required in "$ENGINE" "$CC_RPI_PATH/templates/distribution.json" "$NATIVE_SKILL/SKILL.md" "$NATIVE_SKILL/references/lifecycle-contract.md"; do
  [[ -f "$required" ]] || blocked "missing source resource: $required" 'restore the complete verified local package before scheduling'
done
python3 "$ENGINE" validate --source "$CC_RPI_PATH"
python3 "$ENGINE" check-generated --source "$CC_RPI_PATH"

native_args=("$CLAUDE_BIN")
if [[ "$RPI_ROUTE" == plugin ]]; then
  [[ -f "$CC_RPI_PATH/.claude-plugin/plugin.json" ]] || blocked 'Claude package metadata is missing' 'restore the native package manifest'
  native_args+=(--plugin-dir "$CC_RPI_PATH")
  invocation='/cc-rpi:rpi-update'
else
  [[ ${RPI_UPDATE_SKILL_DIR:-} == /* ]] || blocked 'direct native skill path is missing' 'set RPI_UPDATE_SKILL_DIR from actual user-scope native discovery'
  for resource in SKILL.md references/lifecycle-contract.md; do
    cmp -s "$RPI_UPDATE_SKILL_DIR/$resource" "$NATIVE_SKILL/$resource" || blocked 'direct lifecycle skill/resources differ from selected source' 'review the separate user-scope update before scheduling; never overwrite it implicitly'
  done
  invocation='/rpi-update'
fi

REPORT_ROOT="$PROJECT_ROOT/.rpi/local/update-runs"
python3 - "$PROJECT_ROOT" "$REPORT_ROOT" <<'PY'
from pathlib import Path
import sys
if not Path(sys.argv[2]).resolve().is_relative_to(Path(sys.argv[1])):
    raise SystemExit('BLOCKED / WHY: report path escapes project / FIX: restore owned .rpi/local directories')
PY
RUN_ID=$(python3 -c 'import secrets; print(secrets.token_hex(8))')
RUN_DIR="$REPORT_ROOT/run.$RUN_ID"
for artifact in report.md check.json status.txt; do
  git -C "$PROJECT_ROOT" check-ignore --quiet -- "$RUN_DIR/$artifact" || blocked 'scheduled output is not ignored' 'review .rpi/local exclusions before scheduling; existing ignore rules are preserved'
done
mkdir -p -- "$REPORT_ROOT"
mkdir -- "$RUN_DIR"
REPORT_FILE="$RUN_DIR/report.md"
PROMPT="$invocation
Update only this explicitly authorized project installation.
Source: $CC_RPI_PATH
Target: $PROJECT_ROOT
Harness: $RPI_HARNESS
Route: $RPI_ROUTE
Read the installed lifecycle contract and bind these literal paths safely.
Generate/review/apply a safe project-scoped update plan and verify actual results.
Preserve custom content, unknown ownership, conflicts and recovery journals.
Do not change user-scope installations, plugin caches, model defaults or schedules.
Do not fetch/pull source, push, create PRs, deploy, trigger hosted runs or change remote settings.
Never create Vercel Previews. Required unavailable permissions remain blocked.
Return concrete changes, conflicts and verification; never claim success from prose alone."
cd -- "$PROJECT_ROOT"
native_status=0
"${native_args[@]}" -p "$PROMPT" --permission-mode dontAsk \
  --permission-prompts none --output-format text > "$REPORT_FILE" 2>&1 || native_status=$?
check_status=0
python3 "$ENGINE" check --source "$CC_RPI_PATH" --target "$PROJECT_ROOT" \
  --harness "$RPI_HARNESS" --route "$RPI_ROUTE" > "$RUN_DIR/check.json" 2>&1 || check_status=$?
printf 'native_exit=%s check_exit=%s report=%s\n' "$native_status" "$check_status" "$REPORT_FILE" | tee "$RUN_DIR/status.txt"
[[ $native_status -eq 0 ]] || exit "$native_status"
exit "$check_status"
