#!/usr/bin/env bash
# scripts/agents/contract-metrics-agent.sh
# SCHEDULE: weekly monday 06:50
#
# Snapshots contract-layer hook telemetry into docs/agents/contract-metrics-report.md
# so the impact of the contract layer can be reviewed over time. Purely
# DETERMINISTIC — it runs the Python aggregator only; no Claude CLI, no API cost,
# no auth needed (unlike the other scheduled agents).
#
# Discovered by install-agents.sh via the SCHEDULE comment above. Staggered to
# 06:50 (after the documented agents at 06:30/06:45) per the stagger guidance in
# methodology/scheduled-agents.md.
#
# Report lifecycle follows Rule #70: docs/agents/ is gitignored on public repos
# (the report stays local) and tracked on private repos (committed by /triage).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

LOG="${PROJECT_DIR}/.claude/metrics/contract-events.jsonl"
METRICS_SCRIPT="${PROJECT_DIR}/.claude/scripts/contract-metrics.py"
OUT_DIR="${PROJECT_DIR}/docs/agents"
OUT="${OUT_DIR}/contract-metrics-report.md"

if [ ! -f "${METRICS_SCRIPT}" ]; then
  echo "contract-metrics.py not found at ${METRICS_SCRIPT}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

{
  echo "> Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by contract-metrics-agent"
  echo
  python3 "${METRICS_SCRIPT}" "${LOG}"
} > "${OUT}"

echo "Wrote ${OUT}"
