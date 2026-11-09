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
# Python, which takes a non-blocking flock on .rpi/local/update-runs/launcher.lock and keeps the open
# file for the script. Only the launcher and its supervisor hold that descriptor. Every provider call (probe,
# update, Codex fallback) runs through the supervisor, a small Python process in its own session that
# starts the provider with every other descriptor closed, so neither the provider nor a helper it detaches into
# its own session can pin the lock. The supervisor keeps the lock until the provider's process group is gone: it
# stops whatever the provider leaves in that group (SIGTERM, then SIGKILL) when the provider exits. When the
# launcher receives SIGINT, SIGTERM or SIGHUP, or is killed, the supervisor stops that group the same way and the
# run records it in status.txt and report.md, worded by phase (nothing changed before the update starts). When
# the supervisor is killed instead, the launcher notices that its end record is missing, stops the provider group
# from the recorded pid and ends the run as an abort without running check. A signal the caller ignored (nohup
# ignores SIGHUP, a background start ignores SIGINT) stays ignored by the launcher, the supervisor and the
# provider. Only SIGKILL of the launcher and the supervisor together, or of the machine, leaves a provider running.
# The kernel releases the lock at the last exit, so there is no pid, start time or stale-lock logic. An
# overlapping run exits without calling a provider.
# The probe stops after RPI_UPDATE_PROBE_TIMEOUT_SECONDS (default 300, 0 disables); the update itself has
# no timeout. A hung update is stopped by finding its process with lsof on the lock file and killing it.
# No here-document, here-string or mktemp: bash 3.2 writes those to a temporary file, and scheduler
# environments may have no writable temporary directory. Intermediate output lives in the run directory.
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
command -v git >/dev/null || blocked 'Git is missing' 'configure Git on the scheduler PATH'
git_root=$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null) || blocked 'target is not inside a Git work tree' 'bind RPI_PROJECT_ROOT to the actual intended repository root'
[[ $git_root == "$PROJECT_ROOT" ]] || blocked 'target is not the Git root' 'bind RPI_PROJECT_ROOT to the actual intended repository root'
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
    [[ -f "$RPI_UPDATE_SKILL_DIR/$resource" ]] || blocked "direct lifecycle skill resource is missing: $RPI_UPDATE_SKILL_DIR/$resource" 'install the user-scope rpi-update skill from the selected source, or set RPI_UPDATE_SKILL_DIR to the directory native discovery reports'
    cmp -s "$RPI_UPDATE_SKILL_DIR/$resource" "$NATIVE_SKILL/$resource" || blocked 'direct lifecycle skill/resources differ from selected source' 'review the separate user-scope update before scheduling; never overwrite it implicitly'
  done
  invocation='/rpi-update'
fi

REPORT_ROOT="$PROJECT_ROOT/.rpi/local/update-runs"
# The reports and the lock live in real directories inside the project. A link in the path would send them elsewhere
# (or make git refuse to say whether they are ignored), so it is named as what it is.
for owned_dir in "$PROJECT_ROOT/.rpi" "$PROJECT_ROOT/.rpi/local" "$REPORT_ROOT"; do
  [[ ! -L "$owned_dir" ]] || blocked "$owned_dir is a symbolic link" "replace the link with a real directory inside the project (or remove it) so reports and the launcher lock stay in the project"
done
python3 -c 'from pathlib import Path; import sys; sys.exit(0 if Path(sys.argv[2]).resolve().is_relative_to(Path(sys.argv[1])) else 1)' "$PROJECT_ROOT" "$REPORT_ROOT" \
  || blocked 'report path escapes project' 'restore owned .rpi/local directories'
RUN_ID=$(python3 -c 'import secrets; print(secrets.token_hex(8))')
RUN_DIR="$REPORT_ROOT/run.$RUN_ID"
LOCK_FILE="$REPORT_ROOT/launcher.lock"
# One call: check-ignore prints each ignored path, so all four must come back.
ignored_outputs=$(git -C "$PROJECT_ROOT" check-ignore -- "$RUN_DIR/report.md" "$RUN_DIR/check.json" "$RUN_DIR/status.txt" "$LOCK_FILE" || true)
[[ $(printf '%s\n' "$ignored_outputs" | grep -c .) -eq 4 ]] || blocked 'scheduled output is not ignored' 'review .rpi/local exclusions before scheduling (reports and the launcher.lock file must be ignored); existing ignore rules are preserved'
mkdir -p -- "$REPORT_ROOT"

# Single-flight. LOCK_ACQUIRE opens the lock file, takes flock(LOCK_EX | LOCK_NB) and execs this script
# again with the descriptor kept open. LOCK_VERIFY runs in that second pass and proves the descriptor
# is the lock file and is still held; an inherited RPI_UPDATE_LOCK_OWNER is trusted only for the process
# whose pid it names (exec keeps the pid), so a copied environment never skips the lock.
# The programs are single-quoted strings, so they use double quotes inside.
LOCK_ACQUIRE='
import errno, fcntl, os, shlex, signal, stat, sys
path, argv = sys.argv[1], sys.argv[2:]
def blocked(why, fix):
    sys.stderr.write("BLOCKED / WHY: %s / FIX: %s\n" % (why, fix))
    sys.exit(1)
try:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
except OSError as error:
    if error.errno == errno.EACCES and os.path.isfile(path):
        blocked("the launcher lock %s exists but its mode does not let this user open it for writing" % path,
                "run: chmod u+rw %s   (or remove the file; it is recreated), then run again" % shlex.quote(path))
    blocked("cannot open the launcher lock %s: %s" % (path, error.strerror),
            "make its directory writable by this user, or remove whatever else is at that path (it must be a regular file), then run again")
if not stat.S_ISREG(os.fstat(fd).st_mode):
    blocked("the launcher lock %s is not a regular file" % path, "remove whatever is at that path, then run again")
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError as error:
    if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
        blocked("another update run for this project is active, or is still stopping its provider (it holds the lock %s)" % path,
                "wait for it to finish, then run again; to see which process holds the lock run: lsof %s" % shlex.quote(path))
    blocked("cannot lock the launcher lock %s: %s" % (path, error.strerror), "use a local filesystem that supports flock for .rpi/local")
os.set_inheritable(fd, True)
# Signals the caller ignored (nohup ignores SIGHUP, a background start ignores SIGINT) stay ignored for the whole run.
os.environ["RPI_UPDATE_LOCK_IGNORED"] = ",".join(name for name in ("SIGHUP", "SIGINT", "SIGTERM") if signal.getsignal(getattr(signal, name)) == signal.SIG_IGN)
os.environ["RPI_UPDATE_LOCK_OWNER"] = str(os.getpid())
os.environ["RPI_UPDATE_LOCK_FD"] = str(fd)
os.execv(argv[0], argv)
'
LOCK_VERIFY='
import fcntl, os, sys
try:
    fd = int(sys.argv[2])
    held, named = os.fstat(fd), os.stat(sys.argv[1])
    if held.st_nlink == 0 or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino):
        sys.exit(1)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Succeeds only when this descriptor holds, or nobody does.
except (ValueError, OSError):
    sys.exit(1)
'
# Deleting or renaming the ignored lock file (git clean, rm -rf update-runs) would let a new run lock a new
# inode. Before every provider call the run proves its descriptor still is the file at the lock path and
# stops otherwise; only the call already in flight when the file disappeared can overlap.
require_lock() {
  python3 -c "$LOCK_VERIFY" "$LOCK_FILE" "${RPI_UPDATE_LOCK_FD:-}" || blocked 'the launcher lock file was removed or replaced while this run was active' 'no further provider call was made; do not delete .rpi/local/update-runs while a run is active (git clean -X and rm -rf remove the ignored lock file), then run the launcher again'
}
if [[ $lock_reexecuted == 1 ]]; then
  python3 -c "$LOCK_VERIFY" "$LOCK_FILE" "${RPI_UPDATE_LOCK_FD:-}" || blocked 'this run does not hold the launcher lock' 'run the launcher again'
else
  unset RPI_UPDATE_LOCK_OWNER RPI_UPDATE_LOCK_FD RPI_UPDATE_LOCK_IGNORED
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
native_label=
probe_note=
# The probe's output stays in the run directory (never a temporary file) and is removed before the run ends.
probe_output="$RUN_DIR/probe-output.tmp"
PROVIDER_LOG="$RUN_DIR/provider.log"
STATUS_FILE="$RUN_DIR/status.txt"
SUPERVISOR_PID=
PROVIDER_BASE=
aborted_by=
phase=start
# What an abort means depends on how far the run got: before the update starts nothing was changed.
abort_tail() {
  local check_command
  check_command="python3 $ENGINE check --source $CC_RPI_PATH --target $PROJECT_ROOT --harness $RPI_HARNESS --route $RPI_ROUTE"
  case $phase in
    start) printf 'no provider call had started; nothing was changed' ;;
    probe) printf 'the read-only probe was stopped; no update had started and the installation was not changed' ;;
    update|codex) printf 'the provider process group was stopped, so an update may be half applied: run %s and inspect %s/.rpi/local/transactions' "$check_command" "$PROJECT_ROOT" ;;
    *) printf 'the update call had ended but the installation check did not finish: run %s' "$check_command" ;;
  esac
}
# Every exit before the final one is a failure: bash 3.2 reports status 0 for an abort under set -u when an
# EXIT trap is set, so the trap turns a zero status into 1 unless the script reached its end.
finished=0
on_exit() {
  local status=$?
  rm -f "$probe_output"
  [[ $finished == 1 || $status -ne 0 ]] || status=1
  if [[ $status -ne 0 && ! -s "$STATUS_FILE" ]]; then
    if [[ -n $aborted_by ]]; then
      printf 'native_exit=%s check_exit=not-run aborted by %s; %s\n' "$status" "$aborted_by" "$(abort_tail)" 2>/dev/null > "$STATUS_FILE" || true
      printf 'The run was aborted by %s before it finished: %s. No installation check ran.\n' "$aborted_by" "$(abort_tail)" 2>/dev/null >> "$REPORT_FILE" || true
    else
      printf 'native_exit=%s check_exit=not-run aborted\n' "$status" 2>/dev/null > "$STATUS_FILE" || true
    fi
  fi
  exit "$status"
}
# SIGINT, SIGTERM and SIGHUP end the run in order: the supervisor stops the provider's process group, the status is
# written, the exit status is 128 plus the signal number. Repeated signals during that wait are ignored. A signal the
# caller ignored (nohup, a background start) cannot be trapped by bash and stays ignored.
on_signal() {
  trap '' INT TERM HUP
  aborted_by=$1
  if [[ -n $SUPERVISOR_PID ]]; then
    kill -TERM "$SUPERVISOR_PID" 2>/dev/null || true
    wait "$SUPERVISOR_PID" 2>/dev/null || true
    SUPERVISOR_PID=
  fi
  exit $((128 + $2))
}
trap on_exit EXIT
trap 'on_signal SIGINT 2' INT
trap 'on_signal SIGTERM 15' TERM
trap 'on_signal SIGHUP 1' HUP

# The supervisor. It runs one provider call in its own session and process group, with every descriptor except
# the standard ones closed, so the lock descriptor never reaches the provider or a helper the provider detaches.
# It holds the lock itself until that group is gone: when the provider exits, whatever is left in its group is
# stopped (SIGTERM, then SIGKILL) before the lock is released, so no straggler runs on without it. It stops the
# group the same way when the call exceeds its time limit, when it is told to by a signal, or when the launcher that
# started it has gone away (parent pid changes); in the last case it also writes status.txt and a note in
# report.md for the launcher that could not. It records the provider's pid in <base>.pid when it starts and writes
# <base>.end as its last act, so a missing .end tells the launcher the supervisor itself was killed.
# Signals the caller ignored at entry (RPI_UPDATE_LOCK_IGNORED) stay ignored here and in the provider.
SUPERVISE='
import os, signal, subprocess, sys, time
label, seconds, base, log, status, stdin_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
command = sys.argv[7:]
run_dir = os.path.dirname(status)
parent = os.getppid()
requested = []
def note(text):
    try:
        with open(log, "a") as handle:
            handle.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), text))
    except OSError:
        pass
def ask(number, frame):
    requested.append(signal.Signals(number).name)
ignored = os.environ.get("RPI_UPDATE_LOCK_IGNORED", "").split(",")
for name in ("SIGTERM", "SIGINT", "SIGHUP"):
    signal.signal(getattr(signal, name), signal.SIG_IGN if name in ignored else ask)
environment = {key: value for key, value in os.environ.items() if not key.startswith("RPI_UPDATE_LOCK_")}
def finish(code, detail):
    try:
        with open(base + ".end", "w") as handle:
            handle.write("exit=%d %s\n" % (code, detail))
    except OSError:
        pass
    sys.exit(code)
try:
    stdin = subprocess.DEVNULL if stdin_path == "-" else open(stdin_path, "rb")
    child = subprocess.Popen(command, stdin=stdin, env=environment, close_fds=True, start_new_session=True)
except OSError as error:
    sys.stderr.write("RPI_PROVIDER_NOT_STARTED: %s: %s\n" % (command[0], error.strerror))
    note("%s provider not started: %s" % (label, error.strerror))
    finish(127, "not-started")
try:
    with open(base + ".pid", "w") as handle:
        handle.write("%d\n" % child.pid)
except OSError:
    pass
note("%s provider pid=%d started" % (label, child.pid))
def group_alive():
    try:
        os.killpg(child.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
def stop_group(grace):
    # SIGTERM the whole group, then SIGKILL what is left after the grace period.
    for number, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 5)):
        try:
            os.killpg(child.pid, number)
        except ProcessLookupError:
            return
        end = time.time() + wait
        while time.time() < end:
            if child.poll() is not None and not group_alive():
                return
            time.sleep(0.1)
deadline = time.time() + seconds if seconds else None
reason = None
while child.poll() is None:
    if requested:
        reason = "signal " + requested[0]
    elif os.getppid() != parent:
        reason = "launcher-exited"
    elif deadline is not None and time.time() > deadline:
        reason = "timeout"
    if reason:
        break
    time.sleep(0.1)
stragglers = False
if reason:
    stop_group(5 if reason == "timeout" else 10)
elif group_alive():
    stragglers = True
    stop_group(10)
child.wait()
code = child.returncode if child.returncode >= 0 else 128 - child.returncode
note("%s provider pid=%d ended exit=%d%s%s" % (label, child.pid, code, " after being stopped (%s)" % reason if reason else "",
     "; processes left in its group were stopped" if stragglers else ""))
detail = "reason=%s stragglers=%d" % (reason or "none", 1 if stragglers else 0)
if reason == "timeout":
    sys.stderr.write("RPI_PROBE_TIMEOUT: the probe did not answer within %d seconds and its process group was stopped\n" % seconds)
    finish(124, detail)
if reason == "launcher-exited":
    try:
        os.unlink(os.path.join(run_dir, "probe-output.tmp"))  # Raw probe output is never kept.
    except OSError:
        pass
    if label == "probe":
        tail = "the probe process group was stopped; no update had started and the installation was not changed"
    else:
        tail = "the provider process group was stopped, so an update may be half applied: inspect .rpi/local/transactions and run the installation check"
    try:
        fd = os.open(status, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.write(fd, ("native_exit=%d check_exit=not-run aborted: the launcher ended during the %s call (it was killed); %s\n" % (code, label, tail)).encode())
        os.close(fd)
    except OSError:
        pass
    try:
        with open(os.path.join(run_dir, "report.md"), "a") as handle:
            handle.write("The run was cut off: the launcher ended during the %s call (it was killed); %s. No installation check ran.\n" % (label, tail))
    except OSError:
        pass
finish(code, detail)
'
# Stops the process group of a provider whose supervisor was killed (SIGTERM, then SIGKILL after a bounded wait).
STOP_GROUP='
import os, signal, sys, time
try:
    pid = int(sys.argv[1])
except (IndexError, ValueError):
    sys.exit(0)
if pid < 2:
    sys.exit(0)
for number, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
    try:
        os.killpg(pid, number)
    except (ProcessLookupError, PermissionError):
        sys.exit(0)
    end = time.time() + wait
    while time.time() < end:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            sys.exit(0)
        time.sleep(0.1)
'
# run_provider <label> <seconds> <stdin file or -> <command...> -- output redirections belong to the caller. The
# supervisor leaves <base>.end as its last act. Without it the supervisor itself was killed: the provider it started
# (pid in <base>.pid) is stopped here and the run ends as an abort, not as an update that exited 137.
run_provider() {
  local label=$1 seconds=$2 stdin_path=$3 supervised_status=0 provider_pid=
  shift 3
  phase=$label
  PROVIDER_BASE="$RUN_DIR/provider.$label"
  rm -f "$PROVIDER_BASE.pid" "$PROVIDER_BASE.end"
  python3 -c "$SUPERVISE" "$label" "$seconds" "$PROVIDER_BASE" "$PROVIDER_LOG" "$STATUS_FILE" "$stdin_path" "$@" &
  SUPERVISOR_PID=$!
  wait "$SUPERVISOR_PID" || supervised_status=$?
  SUPERVISOR_PID=
  if [[ ! -e "$PROVIDER_BASE.end" ]]; then
    [[ ! -s "$PROVIDER_BASE.pid" ]] || provider_pid=$(cat "$PROVIDER_BASE.pid")
    python3 -c "$STOP_GROUP" "$provider_pid" || true
    aborted_by='the loss of its supervisor (it was killed)'
    exit $(( supervised_status > 128 ? supervised_status : 1 ))
  fi
  return "$supervised_status"
}

probe_status=0
require_lock
PROBE_TIMEOUT=${RPI_UPDATE_PROBE_TIMEOUT_SECONDS:-300}
[[ $PROBE_TIMEOUT =~ ^[0-9]+$ ]] || blocked "RPI_UPDATE_PROBE_TIMEOUT_SECONDS must be a whole number of seconds, not $PROBE_TIMEOUT" 'set it to a number such as 300, or 0 for no probe timeout'
run_provider probe "$PROBE_TIMEOUT" - env -u ANTHROPIC_API_KEY "$CLAUDE_BIN" -p 'Reply READY only. Do not use tools or change files.' \
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
      [[ -f "$CODEX_SKILL/$resource" ]] || blocked "Codex lifecycle skill resource is missing: $CODEX_SKILL/$resource" 'install the user-scope rpi-update skill for Codex from the selected source, or set RPI_UPDATE_CODEX_SKILL_DIR to the directory Codex discovery reports'
      cmp -s "$CODEX_SKILL/$resource" "$CC_RPI_PATH/generated/codex/skills/rpi-update/$resource" || blocked 'Codex lifecycle skill/resources differ from selected source' 'review the separate user-scope update before scheduling; never overwrite it implicitly'
    done
    printf 'Claude preflight reported a quota or authentication limit; using Codex subscription fallback. Raw output withheld.\n' > "$RUN_DIR/preflight.txt"
    CODEX_PROMPT="Read $CODEX_SKILL/SKILL.md and its lifecycle contract fully. Follow the installed
rpi-update skill for this single project. Do not change the user-scope skill.

$BODY"
    printf '%s\n' "$CODEX_PROMPT" > "$RUN_DIR/codex-prompt.txt"
    require_lock
    # Network access stays off: the update reads and writes local files and runs local Git and engine commands, and the
    # prompt forbids fetching or pulling. The model's own connection is not a sandboxed command and does not need it.
    run_provider codex 0 "$RUN_DIR/codex-prompt.txt" env -u OPENAI_API_KEY -u CODEX_API_KEY "$CODEX_BIN" exec --ephemeral \
      --sandbox workspace-write -c sandbox_workspace_write.network_access=false \
      -m "${CODEX_MODEL:-gpt-5.5}" -C "$PROJECT_ROOT" \
      --output-last-message "$REPORT_FILE" - > /dev/null 2>/dev/null || native_status=$?
    if [[ ! -s "$REPORT_FILE" ]]; then
      { cat "$RUN_DIR/preflight.txt"; printf 'Codex returned no final report (exit %s).\n' "$native_status"; } > "$REPORT_FILE"
      [[ $native_status -ne 0 ]] || native_status=1
    fi
  else
    printf 'Claude preflight failed (exit %s) without a quota or authentication signal. Raw output withheld.\n' "$probe_status" > "$REPORT_FILE"
    native_status=${probe_status:-1}
    # No update ran: the exit code is the probe's, and the status line says so instead of calling it the update's.
    native_label=not-run
    probe_note=" probe_exit=$probe_status"
  fi
else
  require_lock
  run_provider update 0 - env -u ANTHROPIC_API_KEY "${native_args[@]}" -p "$PROMPT" --permission-mode dontAsk \
    --permission-prompts none --output-format text > "$REPORT_FILE" 2>&1 || native_status=$?
fi
rm -f "$probe_output"
check_status=0
phase=check
python3 "$ENGINE" check --source "$CC_RPI_PATH" --target "$PROJECT_ROOT" \
  --harness "$RPI_HARNESS" --route "$RPI_ROUTE" > "$RUN_DIR/check.json" 2>&1 || check_status=$?
printf 'native_exit=%s%s check_exit=%s report=%s\n' "${native_label:-$native_status}" "$probe_note" "$check_status" "$REPORT_FILE" | tee "$STATUS_FILE"
finished=1
[[ $native_status -eq 0 ]] || exit "$native_status"
exit "$check_status"
