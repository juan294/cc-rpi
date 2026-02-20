# Scheduled Agents

Scheduled agents run outside of interactive sessions on a recurring schedule. They perform maintenance, audits, and health checks automatically — catching issues before humans or interactive agents encounter them.

## Architecture

```
┌─────────────────────┐
│  OS Scheduler        │  cron (Linux) / launchd (macOS)
│  (fires on schedule) │  Catches up after sleep/shutdown
└────────┬────────────┘
         │ spawns
         ▼
┌─────────────────────┐     ┌──────────────────────┐
│  Agent Shell Script  │────▶│  Claude CLI (headless) │
│  (bash)              │     │  claude -p "prompt"    │
└────────┬────────────┘     └──────────┬─────────────┘
         │                             │ writes
         ▼                             ▼
┌─────────────────────┐     ┌──────────────────────┐
│  docs/agents/        │     │  docs/agents/          │
│  agent-report.md     │     │  shared-context.md     │
│  (individual report) │     │  (cross-agent intel)   │
└─────────────────────┘     └──────────────────────┘
```

**Key idea:** Each agent is a standalone bash script that invokes the Claude CLI in headless mode (`claude -p "prompt"`). Agents write markdown reports to disk. An optional admin panel reads those reports and displays health status.

## Agent Shell Script Template

```bash
#!/bin/bash
# scripts/agents/my-agent.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

AGENT_NAME="my-agent"
REPORT_FILE="docs/agents/${AGENT_NAME}-report.md"

# ── 1. Read shared context from other agents ──
SHARED_CONTEXT=""
if [ -f "$PROJECT_ROOT/docs/agents/shared-context.md" ]; then
  SHARED_CONTEXT=$(cat "$PROJECT_ROOT/docs/agents/shared-context.md")
fi

# ── 2. Build the prompt ──
PROMPT="You are the $AGENT_NAME scheduled agent for this project.

Your responsibilities:
[Define agent-specific responsibilities here]

## Context from Other Agents
$SHARED_CONTEXT

After completing your analysis, append a SHARED_CONTEXT block to docs/agents/shared-context.md with your key findings and any cross-agent recommendations."

# ── 3. Run Claude CLI in headless mode ──
cd "$PROJECT_ROOT"
echo "[$(date)] Starting $AGENT_NAME agent..."

claude -p "$PROMPT" \
  --allowedTools "Read,Glob,Grep,Bash(npm run *),Bash(pnpm run *)" \
  --output-format text \
  > "$REPORT_FILE" 2>&1

echo "[$(date)] $AGENT_NAME complete. Report: $REPORT_FILE"
```

### Key Design Choices

- **`set -euo pipefail`** — Fail fast on errors. Don't silently continue if Claude CLI crashes.
- **`--allowedTools`** — Restrict what the agent can do. Scheduled agents should be read-only or narrowly scoped.
- **`--output-format text`** — Write the report as plain markdown.
- **Shared context** — Agents read other agents' findings before starting, building on each other's intelligence.

## Scheduling

### macOS (launchd)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.project.agent.my-agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/absolute/path/to/project/scripts/agents/my-agent.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/absolute/path/to/project/logs/my-agent.log</string>
  <key>StandardErrorPath</key>
  <string>/absolute/path/to/project/logs/my-agent.error.log</string>
</dict>
</plist>
```

```bash
# Install:
cp com.project.agent.my-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.project.agent.my-agent.plist

# Uninstall:
launchctl unload ~/Library/LaunchAgents/com.project.agent.my-agent.plist
```

### Linux (cron)

```bash
# Run daily at 6:00 AM:
0 6 * * * /absolute/path/to/project/scripts/agents/my-agent.sh >> /absolute/path/to/project/logs/my-agent.log 2>&1
```

## Common Agent Types

| Agent | Schedule | Focus |
|-------|----------|-------|
| **Test health** | Daily | Run full test suite, check for flaky tests (run 3x), report coverage |
| **Security audit** | Weekly | Dependency vulnerabilities, secret scanning, license compliance |
| **Code quality** | Daily | Lint, dead code, TODO/FIXME count, TypeScript strict violations |
| **Dependency health** | Weekly | Outdated packages, version conflicts, lockfile integrity |
| **Performance check** | Weekly | Bundle sizes, build times, regression detection |
| **Documentation sync** | Weekly | Stale docs, undocumented public APIs, broken links |

## Shared Context System

The shared context file (`docs/agents/shared-context.md`) is a cross-agent intelligence workspace. Every scheduled agent:

1. **Reads** it before starting — to build on other agents' findings
2. **Writes** to it after finishing — to share discoveries

### Format

```markdown
<!-- ENTRY:START agent=agent-name timestamp=2024-01-15T06:00:00Z -->
## Agent Name — 2024-01-15
- **Status**: GREEN / YELLOW / RED
- Key findings (bullet points)
- Metrics (numbers, percentages)

**Cross-agent recommendations:**
- [Other Agent]: specific actionable recommendation
<!-- ENTRY:END -->
```

### Rules

1. **Maximum 3 entries per agent type.** Oldest entry is removed when a new one is added.
2. **Cross-agent recommendations are mandatory.** If findings affect another agent's domain, say so explicitly.
3. **Be specific.** "Security looks fine" is useless. "No injection vectors found — all user input escaped via `sanitize()`" is useful.

## Prerequisites

- Claude CLI installed and authenticated (`claude --version`)
- Project dependencies installed (agents may run test/build commands)
- `docs/agents/` directory exists in the project
- `logs/` directory exists for output capture
