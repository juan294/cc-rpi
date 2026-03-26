#!/usr/bin/env bash
# templates/scripts/agents/install-agents.sh
#
# Install/uninstall scheduled agents into macOS launchd.
#
# Auto-discovers agent scripts in scripts/agents/*.sh and generates
# launchd plists for each one. Schedule is read from a comment in
# each script:
#
#   # SCHEDULE: daily 03:00
#   # SCHEDULE: weekly monday 06:30
#
# Scripts without a SCHEDULE comment are skipped.
#
# Usage:
#   bash scripts/agents/install-agents.sh             # Install all agents
#   bash scripts/agents/install-agents.sh --unload     # Unload and remove all
#   bash scripts/agents/install-agents.sh --status     # Show agent status
#   bash scripts/agents/install-agents.sh --list       # List discoverable agents
#
# Prerequisites:
#   - macOS with launchd
#   - Claude CLI installed (claude setup-token for non-interactive auth)
#   - Agent scripts in scripts/agents/*.sh with SCHEDULE comments

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
SYSTEM_LOGS_DIR="${HOME}/Library/Logs/${PROJECT_NAME}"

# Plist label prefix — all agents for this project share it
LABEL_PREFIX="com.${PROJECT_NAME}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Parse "# SCHEDULE: daily 03:00" or "# SCHEDULE: weekly monday 06:30"
# Returns: type hour minute [weekday]
parse_schedule() {
  local script="$1"
  local schedule_line
  schedule_line=$(grep -m1 '^# SCHEDULE:' "$script" 2>/dev/null || true)

  if [ -z "$schedule_line" ]; then
    return 1
  fi

  # Strip "# SCHEDULE: " prefix
  local schedule="${schedule_line#\# SCHEDULE: }"

  local type hour minute weekday
  type=$(echo "$schedule" | awk '{print tolower($1)}')
  local time_str

  case "$type" in
    daily)
      time_str=$(echo "$schedule" | awk '{print $2}')
      hour=$(echo "$time_str" | cut -d: -f1 | sed 's/^0//')
      minute=$(echo "$time_str" | cut -d: -f2 | sed 's/^0//')
      echo "daily $hour $minute"
      ;;
    weekly)
      local day_name
      day_name=$(echo "$schedule" | awk '{print tolower($2)}')
      time_str=$(echo "$schedule" | awk '{print $3}')
      hour=$(echo "$time_str" | cut -d: -f1 | sed 's/^0//')
      minute=$(echo "$time_str" | cut -d: -f2 | sed 's/^0//')
      case "$day_name" in
        sunday|sun)    weekday=0 ;;
        monday|mon)    weekday=1 ;;
        tuesday|tue)   weekday=2 ;;
        wednesday|wed) weekday=3 ;;
        thursday|thu)  weekday=4 ;;
        friday|fri)    weekday=5 ;;
        saturday|sat)  weekday=6 ;;
        *) echo "Unknown day: $day_name" >&2; return 1 ;;
      esac
      echo "weekly $hour $minute $weekday"
      ;;
    *)
      echo "Unknown schedule type: $type" >&2
      return 1
      ;;
  esac
}

# Generate a launchd plist for an agent script
generate_plist() {
  local script_path="$1"
  local agent_name="$2"
  local label="${LABEL_PREFIX}.${agent_name}"
  local schedule
  schedule=$(parse_schedule "$script_path") || return 1

  local type hour minute weekday
  type=$(echo "$schedule" | awk '{print $1}')
  hour=$(echo "$schedule" | awk '{print $2}')
  minute=$(echo "$schedule" | awk '{print $3}')
  weekday=$(echo "$schedule" | awk '{print $4}')

  local calendar_interval
  if [ "$type" = "weekly" ] && [ -n "$weekday" ]; then
    calendar_interval="    <key>Weekday</key>
    <integer>${weekday}</integer>
    <key>Hour</key>
    <integer>${hour}</integer>
    <key>Minute</key>
    <integer>${minute}</integer>"
  else
    calendar_interval="    <key>Hour</key>
    <integer>${hour}</integer>
    <key>Minute</key>
    <integer>${minute}</integer>"
  fi

  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>exec /bin/bash ${script_path}</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
${calendar_interval}
  </dict>

  <key>StandardOutPath</key>
  <string>${SYSTEM_LOGS_DIR}/${agent_name}.log</string>

  <key>StandardErrorPath</key>
  <string>${SYSTEM_LOGS_DIR}/${agent_name}.error.log</string>

  <key>HardResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>122880</integer>
  </dict>

  <key>SoftResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>122880</integer>
  </dict>

  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>${HOME}</string>
    <key>TERM</key>
    <string>xterm-256color</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST
}

# Discover all agent scripts with SCHEDULE comments
discover_agents() {
  for script in "${SCRIPT_DIR}"/*.sh; do
    [ -f "$script" ] || continue
    local basename
    basename=$(basename "$script" .sh)
    # Skip this installer script and the morning-triage orchestrator
    [ "$basename" = "install-agents" ] && continue
    # Check for SCHEDULE comment
    if grep -q '^# SCHEDULE:' "$script" 2>/dev/null; then
      echo "${basename}|${script}"
    fi
  done
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_install() {
  echo "Installing ${PROJECT_NAME} scheduled agents..."
  echo "Project: ${PROJECT_DIR}"
  echo ""

  mkdir -p "${LAUNCH_AGENTS_DIR}"
  mkdir -p "${SYSTEM_LOGS_DIR}"
  mkdir -p "${PROJECT_DIR}/logs"
  mkdir -p "${PROJECT_DIR}/docs/agents"

  local count=0
  while IFS='|' read -r agent_name script_path; do
    local label="${LABEL_PREFIX}.${agent_name}"
    local target="${LAUNCH_AGENTS_DIR}/${label}.plist"

    # Unload if already loaded
    if [ -f "${target}" ]; then
      launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
    fi

    # Generate and install plist
    generate_plist "${script_path}" "${agent_name}" > "${target}"
    launchctl bootstrap "gui/$(id -u)" "${target}"
    local schedule
    schedule=$(parse_schedule "${script_path}")
    echo "  Installed ${agent_name} (${schedule})"
    count=$((count + 1))
  done < <(discover_agents)

  if [ "$count" -eq 0 ]; then
    echo "  No agent scripts with SCHEDULE comments found."
    echo "  Add '# SCHEDULE: daily HH:MM' to your scripts."
    exit 0
  fi

  echo ""
  echo "${count} agent(s) installed. Verify with:"
  echo "  launchctl list | grep ${LABEL_PREFIX}"
  echo ""
  echo "To trigger an agent manually:"
  echo "  launchctl start ${LABEL_PREFIX}.<agent-name>"
  echo ""
  echo "To uninstall all:"
  echo "  bash ${SCRIPT_DIR}/install-agents.sh --unload"
}

cmd_unload() {
  echo "Unloading ${PROJECT_NAME} agents..."

  local count=0
  for plist in "${LAUNCH_AGENTS_DIR}/${LABEL_PREFIX}."*.plist; do
    [ -f "$plist" ] || continue
    local label
    label=$(basename "$plist" .plist)
    launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
    rm -f "$plist"
    echo "  Removed ${label}"
    count=$((count + 1))
  done

  if [ "$count" -eq 0 ]; then
    echo "  No agents found for ${PROJECT_NAME}."
  else
    echo "${count} agent(s) removed."
  fi
}

cmd_status() {
  echo "${PROJECT_NAME} scheduled agents:"
  echo ""

  local found=false
  while IFS='|' read -r agent_name script_path; do
    local label="${LABEL_PREFIX}.${agent_name}"
    local schedule
    schedule=$(parse_schedule "${script_path}")
    local status="NOT LOADED"
    if launchctl list "${label}" >/dev/null 2>&1; then
      local exit_code
      exit_code=$(launchctl list "${label}" 2>/dev/null | grep '"LastExitStatus"' | grep -o '[0-9]*' || echo "?")
      status="LOADED (last exit: ${exit_code})"
    fi
    printf "  %-25s %-20s %s\n" "${agent_name}" "${schedule}" "${status}"
    found=true
  done < <(discover_agents)

  if [ "$found" = false ]; then
    echo "  No agent scripts with SCHEDULE comments found."
  fi
}

cmd_list() {
  echo "Discoverable agents in ${SCRIPT_DIR}:"
  echo ""
  while IFS='|' read -r agent_name script_path; do
    local schedule
    schedule=$(parse_schedule "${script_path}")
    printf "  %-25s %s\n" "${agent_name}" "${schedule}"
  done < <(discover_agents)
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "${1:-}" in
  --unload|--remove|--uninstall)
    cmd_unload
    ;;
  --status)
    cmd_status
    ;;
  --list)
    cmd_list
    ;;
  --help|-h)
    echo "Usage: $(basename "$0") [--unload|--status|--list|--help]"
    echo ""
    echo "  (no args)   Install/reload all scheduled agents"
    echo "  --unload    Unload and remove all agents"
    echo "  --status    Show agent load status and last exit codes"
    echo "  --list      List discoverable agent scripts"
    echo "  --help      Show this help"
    ;;
  *)
    cmd_install
    ;;
esac
