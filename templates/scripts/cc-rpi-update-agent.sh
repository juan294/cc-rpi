#!/usr/bin/env bash
# Explicitly opted-in, project-scoped local update launcher.
# Configure RPI_UPDATE_ENABLED=1, absolute CC_RPI_PATH and RPI_PROJECT_ROOT,
# RPI_HARNESS=claude|codex|both, and RPI_ROUTE=direct|plugin in the scheduler.
# For direct invocation also bind RPI_UPDATE_SKILL_DIR to the actual discovered
# user-scope rpi-update skill. Plugin invocation loads the local source package
# for this session only. Do not mix direct and plugin registrations.
#
# The update provider is always Claude unless the read-only probe reports a quota or
# authentication limit, in which case the installed Codex subscription runs it instead.
# RPI_HARNESS only scopes which installation (claude, codex or both) is updated.
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
# One launcher run per project at a time: after validation the script re-executes itself through
# Python, which takes a non-blocking flock on .rpi/local/update-runs/launcher.lock and passes the
# open file to the script and every child it starts (the provider included). The kernel holds the
# lock until the last of them exits, for any reason, so there is no pid, start time or stale-lock
# logic. An overlapping run exits without calling a provider. A launcher killed while its provider
# still runs keeps the lock until that provider exits.
# The probe stops after RPI_UPDATE_PROBE_TIMEOUT_SECONDS (default 300, 0 disables); the update itself has
# no timeout. A hung update is stopped by finding its process with lsof on the lock file and killing it.
set -euo pipefail

# A block after the run directory exists is also written there (report.md, status.txt), so a scheduler that
# discards stderr still keeps the reason.
blocked() {
  printf 'BLOCKED / WHY: %s / FIX: %s\n' "$1" "$2" >&2
  if [[ -n ${RUN_DIR:-} && -d $RUN_DIR ]]; then
    printf 'BLOCKED / WHY: %s / FIX: %s\n' "$1" "$2" 2>/dev/null >> "$RUN_DIR/report.md" || true
    printf 'native_exit=1 check_exit=not-run blocked=%s\n' "$1" 2>/dev/null > "$RUN_DIR/status.txt" || true
  fi
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
lock_reexecuted=0
[[ ${RPI_UPDATE_LOCK_OWNER:-} == "$$" ]] && lock_reexecuted=1
if [[ $lock_reexecuted == 0 ]]; then  # The re-executed pass validated already; it verifies the lock instead.
  python3 "$ENGINE" validate --source "$CC_RPI_PATH"
  python3 "$ENGINE" check-generated --source "$CC_RPI_PATH"
fi

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
LOCK_FILE="$REPORT_ROOT/launcher.lock"
# One call: check-ignore prints each ignored path, so all four must come back.
ignored_outputs=$(git -C "$PROJECT_ROOT" check-ignore -- "$RUN_DIR/report.md" "$RUN_DIR/check.json" "$RUN_DIR/status.txt" "$LOCK_FILE" || true)
[[ $(printf '%s\n' "$ignored_outputs" | grep -c .) -eq 4 ]] || blocked 'scheduled output is not ignored' 'review .rpi/local exclusions before scheduling (reports and the launcher.lock file must be ignored); existing ignore rules are preserved'
mkdir -p -- "$REPORT_ROOT"

# Single-flight. LOCK_ACQUIRE opens the lock file, takes flock(LOCK_EX | LOCK_NB) and execs this script
# again with the descriptor inherited. LOCK_VERIFY runs in that second pass and proves the descriptor
# is the lock file and is still held; an inherited RPI_UPDATE_LOCK_OWNER is trusted only for the process
# whose pid it names (exec keeps the pid), so a copied environment never skips the lock.
read -r -d '' LOCK_ACQUIRE <<'PY' || true
import errno, fcntl, os, shlex, stat, sys
path, argv = sys.argv[1], sys.argv[2:]
def blocked(why, fix):
    sys.stderr.write('BLOCKED / WHY: %s / FIX: %s\n' % (why, fix))
    sys.exit(1)
try:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
except OSError as error:
    blocked('cannot open the launcher lock %s: %s' % (path, error.strerror),
            'make its directory writable by this user, or remove whatever else is at that path (it must be a regular file), then run again')
if not stat.S_ISREG(os.fstat(fd).st_mode):
    blocked('the launcher lock %s is not a regular file' % path, 'remove whatever is at that path, then run again')
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError as error:
    if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
        blocked('another update run for this project is active, or a process it started still holds the lock %s' % path,
                'wait for it to finish, then run again; to see which process holds the lock run: lsof %s' % shlex.quote(path))
    blocked('cannot lock the launcher lock %s: %s' % (path, error.strerror), 'use a local filesystem that supports flock for .rpi/local')
os.set_inheritable(fd, True)
os.environ['RPI_UPDATE_LOCK_OWNER'] = str(os.getpid())
os.environ['RPI_UPDATE_LOCK_FD'] = str(fd)
os.execv(argv[0], argv)
PY
read -r -d '' LOCK_VERIFY <<'PY' || true
import fcntl, os, sys
try:
    fd = int(sys.argv[2])
    held, named = os.fstat(fd), os.stat(sys.argv[1])
    if held.st_nlink == 0 or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino):
        sys.exit(1)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Succeeds only when this descriptor holds, or nobody does.
except (ValueError, OSError):
    sys.exit(1)
PY
# Deleting or renaming the ignored lock file (git clean, rm -rf update-runs) would let a new run lock a new
# inode. Before every provider call the run proves its descriptor still is the file at the lock path and
# stops otherwise; only the call already in flight when the file disappeared can overlap.
require_lock() {
  python3 -c "$LOCK_VERIFY" "$LOCK_FILE" "${RPI_UPDATE_LOCK_FD:-}" || blocked 'the launcher lock file was removed or replaced while this run was active' 'no further provider call was made; do not delete .rpi/local/update-runs while a run is active (git clean -X and rm -rf remove the ignored lock file), then run the launcher again'
}
if [[ $lock_reexecuted == 1 ]]; then
  python3 -c "$LOCK_VERIFY" "$LOCK_FILE" "${RPI_UPDATE_LOCK_FD:-}" || blocked 'this run does not hold the launcher lock' 'run the launcher again'
else
  unset RPI_UPDATE_LOCK_OWNER RPI_UPDATE_LOCK_FD
  SCRIPT_PATH=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")
  exec python3 -c "$LOCK_ACQUIRE" "$LOCK_FILE" "$BASH" "$SCRIPT_PATH" "$@"
fi
mkdir_error=$(mkdir -- "$RUN_DIR" 2>&1) || blocked "cannot create the run directory $RUN_DIR: $mkdir_error" "make $REPORT_ROOT writable by this user (check its owner and mode), then run again"
REPORT_FILE="$RUN_DIR/report.md"
BODY="Update only this explicitly authorized project installation.
Source: $CC_RPI_PATH
Target: $PROJECT_ROOT
Harness: $RPI_HARNESS
Read the installed lifecycle contract and bind these literal paths safely.
Generate/review/apply a safe project-scoped update plan and verify actual results.
Preserve custom content, unknown ownership, conflicts and recovery journals.
Do not change user-scope installations, plugin caches, model defaults or schedules.
Do not fetch/pull source, push, create PRs, deploy, trigger hosted runs or change remote settings.
Never create Vercel Previews. Required unavailable permissions remain blocked.
Return concrete changes, conflicts and verification; never claim success from prose alone."
PROMPT="$invocation
Route: $RPI_ROUTE
$BODY"
cd -- "$PROJECT_ROOT"
native_status=0
probe_output=$(mktemp)
# Every exit before the final one is a failure: bash 3.2 reports status 0 for an abort under set -u when an
# EXIT trap is set, so the trap turns a zero status into 1 unless the script reached its end.
finished=0
on_exit() {
  local status=$?
  rm -f "$probe_output"
  [[ $finished == 1 || $status -ne 0 ]] || status=1
  if [[ $status -ne 0 && ! -s "$RUN_DIR/status.txt" ]]; then
    printf 'native_exit=%s check_exit=not-run aborted\n' "$status" 2>/dev/null > "$RUN_DIR/status.txt" || true
  fi
  exit "$status"
}
trap on_exit EXIT
probe_status=0
require_lock
PROBE_TIMEOUT=${RPI_UPDATE_PROBE_TIMEOUT_SECONDS:-300}
[[ $PROBE_TIMEOUT =~ ^[0-9]+$ ]] || blocked "RPI_UPDATE_PROBE_TIMEOUT_SECONDS must be a whole number of seconds, not $PROBE_TIMEOUT" 'set it to a number such as 300, or 0 for no probe timeout'
read -r -d '' WITH_TIMEOUT <<'PY' || true
import os, signal, subprocess, sys
seconds, command = int(sys.argv[1]), sys.argv[2:]
child = subprocess.Popen(command, start_new_session=True, close_fds=False)  # Its own process group; it keeps the lock descriptor.
try:
    sys.exit(child.wait(timeout=seconds or None))
except subprocess.TimeoutExpired:
    for sent in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sent)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=5)
            break
        except subprocess.TimeoutExpired:
            continue
    print('RPI_PROBE_TIMEOUT: the probe did not answer within %d seconds and its process group was stopped' % seconds, file=sys.stderr)
    sys.exit(124)
PY
python3 -c "$WITH_TIMEOUT" "$PROBE_TIMEOUT" env -u ANTHROPIC_API_KEY "$CLAUDE_BIN" -p 'Reply READY only. Do not use tools or change files.' \
  --tools '' --strict-mcp-config --permission-mode dontAsk \
  --permission-prompts none --output-format text \
  > "$probe_output" 2>&1 || probe_status=$?
if grep -q '^RPI_PROBE_TIMEOUT:' "$probe_output"; then
  blocked "the Claude probe did not answer within $PROBE_TIMEOUT seconds and its process group was stopped; no update was started" 'check the Claude CLI authentication and network, then run again; RPI_UPDATE_PROBE_TIMEOUT_SECONDS changes the limit (0 disables it)'
fi
if [[ $probe_status -ne 0 ]] || grep -qiE 'rate.?limit|usage limit|hit your (weekly )?limit|authentication_error|not logged in|oauth token has expired' "$probe_output"; then
  if grep -qiE 'rate.?limit|usage limit|hit your (weekly )?limit|authentication_error|not logged in|oauth token has expired' "$probe_output"; then
    [[ -x "$CODEX_BIN" ]] || blocked 'Claude quota or authentication blocked the update and Codex is unavailable' 'restore subscription authentication or set CODEX_BIN to the installed executable'
    [[ -n ${RPI_UPDATE_CODEX_SKILL_DIR:-} || -n ${HOME:-} ]] || blocked 'HOME is not set and RPI_UPDATE_CODEX_SKILL_DIR is not given, so the Codex skill cannot be located' 'set RPI_UPDATE_CODEX_SKILL_DIR to the discovered user-scope rpi-update skill, or run the scheduler with HOME set'
    CODEX_SKILL=${RPI_UPDATE_CODEX_SKILL_DIR:-${HOME:-}/.agents/skills/rpi-update}
    [[ "$CODEX_SKILL" == /* ]] || blocked 'Codex skill path is not absolute' 'set RPI_UPDATE_CODEX_SKILL_DIR to the discovered user-scope skill'
    for resource in SKILL.md references/lifecycle-contract.md; do
      cmp -s "$CODEX_SKILL/$resource" "$CC_RPI_PATH/generated/codex/skills/rpi-update/$resource" || blocked 'Codex lifecycle skill/resources differ from selected source' 'review the separate user-scope update before scheduling; never overwrite it implicitly'
    done
    printf 'Claude preflight reported a quota or authentication limit; using Codex subscription fallback. Raw output withheld.\n' > "$RUN_DIR/preflight.txt"
    require_lock
    env -u OPENAI_API_KEY -u CODEX_API_KEY "$CODEX_BIN" exec --ephemeral \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=true \
      -m "${CODEX_MODEL:-gpt-5.5}" -C "$PROJECT_ROOT" \
      --output-last-message "$REPORT_FILE" - > /dev/null 2>/dev/null <<PROMPT || native_status=$?
Read $CODEX_SKILL/SKILL.md and its lifecycle contract fully. Follow the installed
rpi-update skill for this single project. Do not change the user-scope skill.

$BODY
PROMPT
    if [[ ! -s "$REPORT_FILE" ]]; then
      { cat "$RUN_DIR/preflight.txt"; printf 'Codex returned no final report (exit %s).\n' "$native_status"; } > "$REPORT_FILE"
      [[ $native_status -ne 0 ]] || native_status=1
    fi
  else
    printf 'Claude preflight failed (exit %s) without a quota or authentication signal. Raw output withheld.\n' "$probe_status" > "$REPORT_FILE"
    native_status=${probe_status:-1}
  fi
else
  require_lock
  env -u ANTHROPIC_API_KEY "${native_args[@]}" -p "$PROMPT" --permission-mode dontAsk \
    --permission-prompts none --output-format text > "$REPORT_FILE" 2>&1 || native_status=$?
fi
rm -f "$probe_output"
check_status=0
python3 "$ENGINE" check --source "$CC_RPI_PATH" --target "$PROJECT_ROOT" \
  --harness "$RPI_HARNESS" --route "$RPI_ROUTE" > "$RUN_DIR/check.json" 2>&1 || check_status=$?
printf 'native_exit=%s check_exit=%s report=%s\n' "$native_status" "$check_status" "$REPORT_FILE" | tee "$RUN_DIR/status.txt"
finished=1
[[ $native_status -eq 0 ]] || exit "$native_status"
exit "$check_status"
