#!/bin/bash
# scripts/agents/morning-triage.sh
#
# Multi-project morning triage orchestrator.
# Runs /triage in each configured project directory sequentially.
# Designed for launchd/cron or manual invocation. Archy-compatible.
#
# ── Setup ──
#
# 1. Copy this script to a central location (e.g., ~/scripts/morning-triage.sh)
# 2. Edit PROJECTS array below with your project directories
# 3. Make executable: chmod +x morning-triage.sh
# 4. Create summary directory: mkdir -p ~/docs
# 5. (Optional) Schedule with launchd/cron -- see examples below
#
# ── Manual usage ──
#
#   ./morning-triage.sh                    # Run all configured projects
#   ./morning-triage.sh /path/to/project   # Run a single project (override)
#
# ── macOS launchd ──
#
#   Create ~/Library/LaunchAgents/com.morning-triage.plist:
#   (Replace YOUR_USERNAME with your macOS username)
#
#   <?xml version="1.0" encoding="UTF-8"?>
#   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
#     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
#   <plist version="1.0">
#   <dict>
#     <key>Label</key>
#     <string>com.morning-triage</string>
#     <key>ProgramArguments</key>
#     <array>
#       <string>/bin/bash</string>
#       <string>-c</string>
#       <string>exec /bin/bash /absolute/path/to/morning-triage.sh</string>
#     </array>
#     <key>StartCalendarInterval</key>
#     <dict>
#       <key>Hour</key>
#       <integer>7</integer>
#       <key>Minute</key>
#       <integer>0</integer>
#     </dict>
#     <key>HardResourceLimits</key>
#     <dict>
#       <key>NumberOfFiles</key>
#       <integer>122880</integer>
#     </dict>
#     <key>SoftResourceLimits</key>
#     <dict>
#       <key>NumberOfFiles</key>
#       <integer>122880</integer>
#     </dict>
#     <key>EnvironmentVariables</key>
#     <dict>
#       <key>HOME</key>
#       <string>/Users/YOUR_USERNAME</string>
#       <key>TERM</key>
#       <string>xterm-256color</string>
#       <key>PATH</key>
#       <string>/opt/homebrew/bin:/usr/local/bin:/Users/YOUR_USERNAME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
#     </dict>
#     <key>StandardOutPath</key>
#     <string>/Users/YOUR_USERNAME/logs/morning-triage.log</string>
#     <key>StandardErrorPath</key>
#     <string>/Users/YOUR_USERNAME/logs/morning-triage.error.log</string>
#   </dict>
#   </plist>
#
#   One-time setup (run interactively before scheduling):
#     claude setup-token
#
#   Install: launchctl load ~/Library/LaunchAgents/com.morning-triage.plist
#   Test:    launchctl start com.morning-triage
#   Remove:  launchctl unload ~/Library/LaunchAgents/com.morning-triage.plist
#
# ── Linux cron ──
#
#   # Run daily at 7:00 AM (after overnight agents finish):
#   0 7 * * * /absolute/path/to/morning-triage.sh \
#     >> /absolute/path/to/logs/morning-triage.log 2>&1
#

set -euo pipefail

# ── Configuration ──
# Add your project directories here:
PROJECTS=(
  # "/Users/you/projects/project-a"
  # "/Users/you/projects/project-b"
  # "/Users/you/projects/project-c"
)

CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"
SUMMARY_FILE="${SUMMARY_FILE:-$HOME/docs/morning-triage-summary.md}"
MAX_RETRIES=2

# ── Environment setup (required for launchd) ──
# launchd provides a minimal environment — no PATH, no TERM, possibly no HOME.
# These lines are no-ops in a normal terminal but critical under launchd.
# Do NOT use `source ~/.zshrc` — too fragile for non-interactive shells.
export HOME="${HOME:-$(eval echo ~"$(whoami)")}"
export TERM="${TERM:-xterm-256color}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# ── Override: single project from CLI argument ──
if [ $# -ge 1 ]; then
  PROJECTS=("$@")
fi

# ── File descriptor check ──
# launchd enforces a hard limit of 256 file descriptors by default.
# Claude CLI needs 100K+ for its Node.js runtime. The plist must set
# HardResourceLimits/SoftResourceLimits — ulimit alone can't exceed
# the hard limit. This check catches a missing plist configuration.
ulimit -n 122880 2>/dev/null
FD_LIMIT=$(ulimit -n)
if [ "$FD_LIMIT" -lt 10000 ]; then
  echo "[$(date)] FATAL: File descriptor limit too low ($FD_LIMIT)."
  echo "  launchd hard limit is 256 by default — ulimit can't raise above it."
  echo "  Fix: Add HardResourceLimits + SoftResourceLimits to your .plist:"
  echo "    <key>HardResourceLimits</key>"
  echo "    <dict><key>NumberOfFiles</key><integer>122880</integer></dict>"
  echo "    <key>SoftResourceLimits</key>"
  echo "    <dict><key>NumberOfFiles</key><integer>122880</integer></dict>"
  echo "  Then: launchctl unload + load the plist to apply."
  exit 1
fi

# ── Preflight checks ──

if [ ! -x "$CLAUDE_BIN" ]; then
  echo "[$(date)] ERROR: claude binary not found at $CLAUDE_BIN"
  echo "[$(date)] Set CLAUDE_BIN in this script or export it as an env var."
  echo "[$(date)] Common locations: \$HOME/.local/bin/claude, /usr/local/bin/claude"
  exit 1
fi

# ── Authentication preflight ──
# Under launchd, there's no TTY and no browser for OAuth.
# Claude must be set up with a persistent token via `claude setup-token`.
if ! "$CLAUDE_BIN" -p "echo ok" --output-format text >/dev/null 2>&1; then
  echo "[$(date)] FATAL: Claude CLI auth failed in non-interactive mode."
  echo "  launchd has no TTY/browser — interactive OAuth won't work."
  echo "  Fix: Run 'claude setup-token' from an interactive terminal first."
  exit 1
fi

if [ ${#PROJECTS[@]} -eq 0 ]; then
  echo "[$(date)] ERROR: No projects configured. Edit the PROJECTS array in this script."
  exit 1
fi

# ── Ensure summary directory exists ──
mkdir -p "$(dirname "$SUMMARY_FILE")"

# ── Main loop ──
RESULTS=()
PASS=0
FAIL=0
TODAY=$(date +%Y-%m-%d)

echo "[$(date)] Morning triage starting for ${#PROJECTS[@]} project(s)..."

for PROJECT_DIR in "${PROJECTS[@]}"; do
  # Skip empty entries
  if [ -z "$PROJECT_DIR" ]; then
    continue
  fi

  # Verify directory exists
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "[$(date)] SKIP: Directory not found: $PROJECT_DIR"
    RESULTS+=("SKIP|$PROJECT_DIR|Directory not found")
    continue
  fi

  # Verify this is an agent-enabled project
  if [ ! -d "$PROJECT_DIR/docs/agents" ]; then
    echo "[$(date)] SKIP: No docs/agents/ directory: $PROJECT_DIR"
    RESULTS+=("SKIP|$PROJECT_DIR|No docs/agents/ directory")
    continue
  fi

  echo "[$(date)] ── Triaging: $PROJECT_DIR ──"

  # Build prompt — use the project's own /triage command if it exists,
  # otherwise use inline fallback instructions
  TRIAGE_CMD="$PROJECT_DIR/.claude/commands/triage.md"
  if [ -f "$TRIAGE_CMD" ]; then
    PROMPT="Read and follow the instructions in $TRIAGE_CMD.

Important: this is a non-interactive scheduled run.
- Process ALL reports. Approve all action items automatically.
- Fix everything — do not defer any items regardless of severity.
- Commit reports for historical record, then code fixes separately.
- Push when done.
- Write your final summary as your text output (it becomes the report)."
  else
    PROMPT="You are a morning triage agent for this project.

1. Check git status -- docs/agents/ for new/modified reports
2. Check logs/ for recent agent failures (error logs from last 24h)
3. Read every new/modified report in docs/agents/ completely
4. Implement ALL action items from every report — fix everything
5. Commit reports: git add docs/agents/ && git commit -m 'chore: commit overnight agent reports [$TODAY]'
6. Commit fixes: git add -A && git commit -m 'fix: resolve agent report findings [triage]'
7. Push and verify CI

Write your final summary as your text output."
  fi

  # Run with retry
  RETRY_COUNT=0
  PROJECT_PASS=false

  while [ $RETRY_COUNT -le $MAX_RETRIES ]; do
    if cd "$PROJECT_DIR" && "$CLAUDE_BIN" -p "$PROMPT" \
      --allowedTools "Read,Write,Edit,Glob,Grep,Bash(git *),Bash(gh *),Bash(npm *),Bash(pnpm *),Bash(npx *)" \
      --output-format text \
      > "docs/agents/triage-report.md" 2>&1; then
      echo "[$(date)] PASS: $PROJECT_DIR"
      RESULTS+=("PASS|$PROJECT_DIR|See docs/agents/triage-report.md")
      PASS=$((PASS + 1))
      PROJECT_PASS=true
      break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -le $MAX_RETRIES ]; then
      echo "[$(date)] Attempt $RETRY_COUNT failed for $PROJECT_DIR. Retrying in 10s..."
      sleep 10
    fi
  done

  if [ "$PROJECT_PASS" = false ]; then
    echo "[$(date)] FAIL: $PROJECT_DIR (after $MAX_RETRIES retries)"
    RESULTS+=("FAIL|$PROJECT_DIR|Failed after $MAX_RETRIES retries")
    FAIL=$((FAIL + 1))
  fi
done

# ── Cross-project summary ──
{
  echo "# Morning Triage Summary"
  echo "> Generated on $(date) | ${#PROJECTS[@]} projects | $PASS passed | $FAIL failed"
  echo ""
  echo "## Results"
  echo ""
  echo "| # | Project | Status | Details |"
  echo "|---|---------|--------|---------|"
  IDX=1
  for RESULT in "${RESULTS[@]}"; do
    IFS='|' read -r STATUS PROJECT DETAILS <<< "$RESULT"
    echo "| $IDX | \`$PROJECT\` | $STATUS | $DETAILS |"
    IDX=$((IDX + 1))
  done
  echo ""
  if [ "$FAIL" -gt 0 ]; then
    echo "## Failed Projects"
    echo ""
    for RESULT in "${RESULTS[@]}"; do
      IFS='|' read -r STATUS PROJECT DETAILS <<< "$RESULT"
      if [ "$STATUS" = "FAIL" ]; then
        echo "- \`$PROJECT\`: $DETAILS"
      fi
    done
    echo ""
  fi
  echo "---"
  echo "*Report generated by morning-triage.sh*"
} > "$SUMMARY_FILE"

echo "[$(date)] Morning triage complete: $PASS passed, $FAIL failed"
echo "[$(date)] Summary: $SUMMARY_FILE"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
