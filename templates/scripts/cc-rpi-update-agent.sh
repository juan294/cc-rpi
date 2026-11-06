#!/usr/bin/env bash
# Explicitly opted-in, project-scoped local update launcher.
# Configure RPI_UPDATE_ENABLED=1, absolute CC_RPI_PATH and RPI_PROJECT_ROOT,
# RPI_HARNESS=claude|codex|both, and RPI_ROUTE=direct|plugin in the scheduler.
# For direct invocation also bind RPI_UPDATE_SKILL_DIR to the actual discovered
# user-scope rpi-update skill. Plugin invocation loads the local source package
# for this session only. Do not mix direct and plugin registrations.
#
# Requires Python 3.11+, Git and a Claude CLI supporting --plugin-dir,
# --permission-mode dontAsk and --permission-prompts none (verified in 2.1.261).
# Configure native authentication/permissions through the owner's supported
# setup before opting in. A read-only inference probe detects quota before any
# update starts; no permission bypass is used.
# A quota-blocked Claude preflight can use the installed Codex subscription.
# An update that already began never retries through another provider.
# A started update reports both CLI/check exits, including provider failure.
#
# Optional launchd/cron schedules are installed separately. Diagnose their actual
# PATH, authentication and resource limits; historical launchd workarounds are not
# universal requirements. Never rewrite HOME or source an interactive rc file.
# Reports use unique task-owned .rpi/local/update-runs directories. Preserve these
# and lifecycle journals on failure; there is no blind retry of partial mutation.
# One launcher run per project at a time: an atomic mkdir lock in
# .rpi/local/update-runs/launcher.lock holds the owner's start time and pid. An
# overlapping run exits without calling a provider. A lock whose holder is gone
# (no such pid, or a pid with a different start time) is recovered.
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
CODEX_BIN=${CODEX_BIN:-$(command -v codex || printf '%s' /opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex)}
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
LOCK_DIR="$REPORT_ROOT/launcher.lock"
for artifact in "$RUN_DIR/report.md" "$RUN_DIR/check.json" "$RUN_DIR/status.txt" "$LOCK_DIR/pid"; do
  git -C "$PROJECT_ROOT" check-ignore --quiet -- "$artifact" || blocked 'scheduled output is not ignored' 'review .rpi/local exclusions before scheduling (reports and the launcher.lock directory must be ignored); existing ignore rules are preserved'
done
mkdir -p -- "$REPORT_ROOT"

# Single-flight: mkdir is atomic. The holder records its start time and then its pid; every
# exit path releases the lock only while the pid file still names this process. A holder counts
# as live while its pid exists (even one this user cannot signal) and, when a start time was
# recorded, that start time still matches, so a reused pid is not mistaken for the holder.
probe_output=
release_lock() {
  [[ -z "$probe_output" ]] || rm -f "$probe_output"
  if [[ $(cat "$LOCK_DIR/pid" 2>/dev/null || true) == "$$" ]]; then
    rm -rf -- "$LOCK_DIR"
  fi
}
process_start() {
  LC_ALL=C ps -o lstart= -p "$1" 2>/dev/null | sed -e 's/^ *//' -e 's/ *$//' || true
}
holder_live() {
  local pid=$1 recorded=$2 current
  kill -0 "$pid" 2>/dev/null || ps -p "$pid" >/dev/null 2>&1 || return 1
  [[ -n $recorded ]] || return 0
  current=$(process_start "$pid")
  [[ -z $current || $current == "$recorded" ]]
}
# Remove the lock a run judged stale. A second mkdir mutex serializes recovery, and the lock is
# removed only if it still holds exactly what that run judged, so a fresh lock is never touched
# and nothing is ever moved back over a live one.
recover_stale() {
  local seen_pid=$1 seen_started=$2 mutex="$LOCK_DIR.recover" waited=0 err pid started
  until err=$(mkdir -- "$mutex" 2>&1); do
    [[ -d $mutex ]] || blocked "cannot create the launcher recovery lock $mutex: $err" "make $REPORT_ROOT writable by this user (check its owner and mode), then run again"
    sleep 0.1
    if (( ++waited > 50 )); then rm -rf -- "$mutex"; waited=0; fi  # Left behind by a recoverer that died.
  done
  pid=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  started=$(cat "$LOCK_DIR/started" 2>/dev/null || true)
  if [[ -d $LOCK_DIR && ! -L $LOCK_DIR && $pid == "$seen_pid" && $started == "$seen_started" ]]; then
    rm -rf -- "$LOCK_DIR"
  fi
  rmdir -- "$mutex" 2>/dev/null || true
}
acquire_lock() {
  local err pid started pending=0 rounds=0
  while :; do
    if (( ++rounds > 200 )); then
      blocked "could not take the launcher lock $LOCK_DIR after $rounds attempts" "inspect $LOCK_DIR and the run that holds it, then run again"
    fi
    if err=$(mkdir -- "$LOCK_DIR" 2>&1); then
      break
    fi
    if [[ ! -e $LOCK_DIR && ! -L $LOCK_DIR ]]; then
      blocked "cannot create the launcher lock $LOCK_DIR: $err" "make $REPORT_ROOT writable by this user (check its owner and mode), then run again"
    fi
    if [[ ! -d $LOCK_DIR || -L $LOCK_DIR ]]; then
      blocked "the launcher lock path $LOCK_DIR exists and is not a directory" "after confirming no update run is active, move that path aside, then run again"
    fi
    pid=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    started=$(cat "$LOCK_DIR/started" 2>/dev/null || true)
    if [[ -z $pid ]]; then
      # Another run may be between mkdir and writing its pid; a lock that never gets one is stale.
      if (( ++pending <= 10 )); then sleep 0.2; continue; fi
    elif [[ $pid =~ ^[0-9]+$ ]] && holder_live "$pid" "$started"; then
      blocked "another update run (pid $pid) holds the project lock $LOCK_DIR" "wait for pid $pid to finish and run again, or investigate it with: ps -p $pid"
    fi
    recover_stale "$pid" "$started"
    pending=0
  done
  process_start "$$" > "$LOCK_DIR/started"
  printf '%s\n' "$$" > "$LOCK_DIR/pid"
}
trap release_lock EXIT
trap 'exit 143' TERM
trap 'exit 130' INT HUP
acquire_lock
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
probe_output=$(mktemp)
probe_status=0
env -u ANTHROPIC_API_KEY "$CLAUDE_BIN" -p 'Reply READY only. Do not use tools or change files.' \
  --tools '' --strict-mcp-config --permission-mode dontAsk \
  --permission-prompts none --output-format text \
  > "$probe_output" 2>&1 || probe_status=$?
if [[ $probe_status -ne 0 ]] || grep -qiE 'rate.?limit|usage limit|hit your (weekly )?limit|authentication_error|not logged in|oauth token has expired' "$probe_output"; then
  if grep -qiE 'rate.?limit|usage limit|hit your (weekly )?limit|authentication_error|not logged in|oauth token has expired' "$probe_output"; then
    [[ -x "$CODEX_BIN" ]] || blocked 'Claude quota or authentication blocked the update and Codex is unavailable' 'restore subscription authentication or set CODEX_BIN to the installed executable'
    CODEX_SKILL=${RPI_UPDATE_CODEX_SKILL_DIR:-$HOME/.agents/skills/rpi-update}
    [[ "$CODEX_SKILL" == /* ]] || blocked 'Codex skill path is not absolute' 'set RPI_UPDATE_CODEX_SKILL_DIR to the discovered user-scope skill'
    for resource in SKILL.md references/lifecycle-contract.md; do
      cmp -s "$CODEX_SKILL/$resource" "$CC_RPI_PATH/generated/codex/skills/rpi-update/$resource" || blocked 'Codex lifecycle skill/resources differ from selected source' 'review the separate user-scope update before scheduling; never overwrite it implicitly'
    done
    printf 'Claude preflight reported a quota or authentication limit; using Codex subscription fallback. Raw output withheld.\n' > "$REPORT_FILE"
    env -u OPENAI_API_KEY -u CODEX_API_KEY "$CODEX_BIN" exec --ephemeral \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=true \
      -m "${CODEX_MODEL:-gpt-5.5}" -C "$PROJECT_ROOT" \
      --output-last-message "$REPORT_FILE" - > /dev/null 2>/dev/null <<PROMPT || native_status=$?
Read $CODEX_SKILL/SKILL.md and its lifecycle contract fully. Follow the installed
rpi-update skill for this single project. Do not change the user-scope skill.

$PROMPT
PROMPT
    if [[ $native_status -eq 0 && ! -s "$REPORT_FILE" ]]; then
      printf 'Codex returned no final report.\n' > "$REPORT_FILE"
      native_status=1
    fi
  else
    printf 'Claude preflight failed (exit %s) without a quota or authentication signal. Raw output withheld.\n' "$probe_status" > "$REPORT_FILE"
    native_status=${probe_status:-1}
  fi
else
  env -u ANTHROPIC_API_KEY "${native_args[@]}" -p "$PROMPT" --permission-mode dontAsk \
    --permission-prompts none --output-format text > "$REPORT_FILE" 2>&1 || native_status=$?
fi
rm -f "$probe_output"
probe_output=
check_status=0
python3 "$ENGINE" check --source "$CC_RPI_PATH" --target "$PROJECT_ROOT" \
  --harness "$RPI_HARNESS" --route "$RPI_ROUTE" > "$RUN_DIR/check.json" 2>&1 || check_status=$?
printf 'native_exit=%s check_exit=%s report=%s\n' "$native_status" "$check_status" "$REPORT_FILE" | tee "$RUN_DIR/status.txt"
[[ $native_status -eq 0 ]] || exit "$native_status"
exit "$check_status"
