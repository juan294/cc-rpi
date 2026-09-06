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
xml_text() {
  printf '%s' "$1" | sed -e 's/\&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

generate_plist() {
  local script_path="$1"
  local agent_name="$2"
  local label="${LABEL_PREFIX}.${agent_name}"
  local quoted_script
  printf -v quoted_script '%q' "$script_path"
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
  <string>$(xml_text "$label")</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>$(xml_text "exec /bin/bash $quoted_script")</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
${calendar_interval}
  </dict>

  <key>StandardOutPath</key>
  <string>$(xml_text "${SYSTEM_LOGS_DIR}/${agent_name}.log")</string>

  <key>StandardErrorPath</key>
  <string>$(xml_text "${SYSTEM_LOGS_DIR}/${agent_name}.error.log")</string>

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
    <string>$(xml_text "$HOME")</string>
    <key>TERM</key>
    <string>xterm-256color</string>
    <key>PATH</key>
    <string>$(xml_text "/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin")</string>
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

setup_mutation_paths() {
  if [[ ${HOME:-} != /* ]]; then
    echo 'BLOCKED / WHY: scheduler installation requires an absolute HOME / FIX: use the owner-supported scheduler environment' >&2
    return 1
  fi
  LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
  SYSTEM_LOGS_DIR="${HOME}/Library/Logs/${PROJECT_NAME}"
}

cmd_install() {
  setup_mutation_paths
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
      unload_if_loaded "$label"
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
  local quoted_installer
  printf -v quoted_installer '%q' "${SCRIPT_DIR}/install-agents.sh"
  echo "  bash ${quoted_installer} --unload"
}

cmd_unload() {
  setup_mutation_paths
  echo "Unloading ${PROJECT_NAME} agents..."

  local count=0
  for plist in "${LAUNCH_AGENTS_DIR}/${LABEL_PREFIX}."*.plist; do
    [ -f "$plist" ] || continue
    local label
    label=$(basename "$plist" .plist)
    unload_if_loaded "$label"
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

scheduler_inventory() {
  # A successful all-jobs inventory confirms absence. A failed per-label lookup
  # cannot distinguish an unloaded job from an unavailable scheduler. Keep one
  # snapshot for every row and retain signed signal exits (launchctl(1) list).
  local query_status=0
  SCHEDULER_INVENTORY=$(launchctl list 2>&1) || query_status=$?
  if [ "$query_status" -ne 0 ]; then
    printf 'UNKNOWN: scheduler query failed (exit %s)\n%s\n' "$query_status" "$SCHEDULER_INVENTORY" >&2
    return "$query_status"
  fi
  if ! printf '%s\n' "$SCHEDULER_INVENTORY" | awk '
    NR == 1 { if (NF != 3 || $1 != "PID" || $2 != "Status" || $3 != "Label") exit 1; next }
    NF != 3 || ($1 != "-" && $1 !~ /^[0-9]+$/) || $2 !~ /^-?[0-9]+$/ { exit 1 }
    END { if (NR == 0) exit 1 }
  '; then
    printf 'UNKNOWN: unrecognized scheduler inventory\n%s\n' "$SCHEDULER_INVENTORY" >&2
    return 1
  fi
}

unload_if_loaded() {
  local label="$1"
  scheduler_inventory
  if printf '%s\n' "$SCHEDULER_INVENTORY" | awk -v label="$label" '
    NR > 1 && $3 == label { found=1 }
    END { exit !found }
  '; then
    # Preserve the plist and native diagnostic on failure. A later explicit
    # retry can reconcile it; deleting/replacing it is not proof of unloading.
    launchctl bootout "gui/$(id -u)/${label}"
  fi
}

cmd_status() {
  echo "${PROJECT_NAME} scheduled agents:"
  echo ""
  scheduler_inventory
  local found=false
  while IFS='|' read -r agent_name script_path; do
    local label="${LABEL_PREFIX}.${agent_name}"
    local schedule
    schedule=$(parse_schedule "${script_path}")
    local status="NOT LOADED"
    local exit_code
    exit_code=$(printf '%s\n' "$SCHEDULER_INVENTORY" | awk -v label="$label" 'NR > 1 && $3 == label { print $2 }')
    if [ -n "$exit_code" ]; then
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

if [ "$#" -gt 1 ]; then
  echo "Usage: $(basename "$0") [--unload|--status|--list|--help]" >&2
  exit 2
fi

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
  '')
    cmd_install
    ;;
  *)
    echo "Usage: $(basename "$0") [--unload|--status|--list|--help]" >&2
    exit 2
    ;;
esac
