#!/usr/bin/env bash
# templates/scripts/agents/lib/agent-utils.sh
#
# Shared utilities for scheduled agents.
# Source this from each agent script: source "${SCRIPT_DIR}/lib/agent-utils.sh"
#
# Provides:
#   - Environment setup (fd limits, PATH, launchd compatibility)
#   - Logging helpers (log_info, log_warn, log_error)
#   - Shared context read/write/prune
#   - Claude CLI preflight checks
#
# Expects the sourcing script to set SCRIPT_DIR before sourcing:
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "${SCRIPT_DIR}/lib/agent-utils.sh"

set -euo pipefail

# ---------------------------------------------------------------------------
# Project root — two levels up from scripts/agents/
# ---------------------------------------------------------------------------
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"

# ---------------------------------------------------------------------------
# File descriptor limit
# launchd enforces a hard cap of 256 by default. Claude CLI needs 100K+.
# The plist must set HardResourceLimits/SoftResourceLimits — ulimit alone
# can't exceed the hard limit. This raises it as high as the OS allows,
# with a fallback for environments where the full raise isn't possible.
# ---------------------------------------------------------------------------
ulimit -n 2147483646 2>/dev/null || ulimit -n 122880 2>/dev/null || ulimit -n 10240 2>/dev/null || true
FD_LIMIT=$(ulimit -n)
if [ "$FD_LIMIT" -lt 10000 ]; then
  echo "[$(date)] FATAL: File descriptor limit too low ($FD_LIMIT)."
  echo "  Fix: Add HardResourceLimits/SoftResourceLimits to your .plist"
  exit 1
fi

# ---------------------------------------------------------------------------
# Prevent nested Claude session errors
# If this script is triggered from inside an active Claude Code session
# (e.g., manual testing), the CLAUDECODE env var causes conflicts.
# Under launchd this is a no-op.
# ---------------------------------------------------------------------------
unset CLAUDECODE 2>/dev/null || true

# ---------------------------------------------------------------------------
# Environment setup (required for launchd)
# launchd provides a minimal env — no PATH, no TERM, possibly no HOME.
# These are no-ops in a normal terminal but critical under launchd.
# ---------------------------------------------------------------------------
export HOME="${HOME:-$(eval echo ~"$(whoami)")}"
export TERM="${TERM:-xterm-256color}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
LOGS_DIR="${PROJECT_DIR}/logs"
AGENTS_DIR="${PROJECT_DIR}/docs/agents"
SHARED_CONTEXT_FILE="${AGENTS_DIR}/shared-context.md"
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

mkdir -p "${LOGS_DIR}"
mkdir -p "${AGENTS_DIR}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
log_warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }

# ---------------------------------------------------------------------------
# Claude CLI preflight
# ---------------------------------------------------------------------------

# Verify Claude CLI is available and authenticated.
# Under launchd, there's no TTY for OAuth — must use `claude setup-token`.
preflight_claude() {
  if [ ! -x "$CLAUDE_BIN" ]; then
    log_error "Claude binary not found at $CLAUDE_BIN"
    log_error "Set CLAUDE_BIN or install Claude CLI"
    exit 1
  fi

  if ! "$CLAUDE_BIN" -p "echo ok" --output-format text >/dev/null 2>&1; then
    log_error "Claude CLI auth failed in non-interactive mode."
    log_error "Fix: Run 'claude setup-token' from an interactive terminal."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Shared context — cross-agent intelligence
# ---------------------------------------------------------------------------

# read_shared_context [exclude_agent]
# Reads shared context file. Optionally excludes entries from a specific
# agent (useful to avoid reading your own stale entries).
read_shared_context() {
  local exclude="${1:-}"

  if [ ! -f "${SHARED_CONTEXT_FILE}" ]; then
    echo ""
    return
  fi

  if [ -z "${exclude}" ]; then
    cat "${SHARED_CONTEXT_FILE}"
  else
    # Remove entries from the excluded agent
    python3 -c "
import sys, re
content = open('${SHARED_CONTEXT_FILE}').read()
pattern = r'<!-- ENTRY:START agent=${exclude} .*?-->.*?<!-- ENTRY:END -->\n?'
cleaned = re.sub(pattern, '', content, flags=re.DOTALL)
print(cleaned.strip())
" 2>/dev/null || cat "${SHARED_CONTEXT_FILE}"
  fi
}

# extract_and_write_shared_context <agent_key> <report_file>
# Extracts the SHARED_CONTEXT block from a report and appends it to
# shared-context.md. The report must contain a block delimited by:
#   SHARED_CONTEXT_START
#   ...content...
#   SHARED_CONTEXT_END
extract_and_write_shared_context() {
  local agent_key="$1"
  local report_file="$2"

  if [ ! -f "${report_file}" ]; then
    log_warn "Report file not found: ${report_file}"
    return
  fi

  local entry
  entry=$(python3 -c "
import re, sys
content = open('${report_file}').read()
match = re.search(r'SHARED_CONTEXT_START\n(.*?)SHARED_CONTEXT_END', content, re.DOTALL)
if match:
    print(match.group(1).strip())
else:
    sys.exit(1)
" 2>/dev/null) || true

  if [ -z "${entry}" ]; then
    log_warn "No shared context block found in ${report_file}"
    return
  fi

  local timestamp
  timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

  # Append new entry
  {
    echo ""
    echo "<!-- ENTRY:START agent=${agent_key} timestamp=${timestamp} -->"
    echo "${entry}"
    echo "<!-- ENTRY:END -->"
  } >> "${SHARED_CONTEXT_FILE}"

  # Prune old entries (keep last 3 per agent)
  prune_shared_context "${agent_key}"

  log_info "Shared context updated for ${agent_key}"
}

# prune_shared_context <agent_key>
# Keeps only the last 3 entries per agent type. Oldest are removed.
prune_shared_context() {
  local agent_key="$1"

  python3 -c "
import re

with open('${SHARED_CONTEXT_FILE}', 'r') as f:
    content = f.read()

pattern = r'(<!-- ENTRY:START agent=${agent_key} .*?-->.*?<!-- ENTRY:END -->)'
entries = re.findall(pattern, content, re.DOTALL)

if len(entries) <= 3:
    exit(0)

# Remove oldest entries (keep last 3)
for old_entry in entries[:-3]:
    content = content.replace(old_entry, '')

# Clean up extra blank lines
content = re.sub(r'\n{3,}', '\n\n', content)

with open('${SHARED_CONTEXT_FILE}', 'w') as f:
    f.write(content.strip() + '\n')
" 2>/dev/null || log_warn "Failed to prune shared context for ${agent_key}"
}
