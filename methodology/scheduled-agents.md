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

Agent scripts source a shared utility library (`lib/agent-utils.sh`) that handles environment setup, file descriptor limits, authentication, logging, and shared context management. This eliminates boilerplate duplication across agents.

```bash
#!/bin/bash
# scripts/agents/my-agent.sh
# SCHEDULE: daily 06:00

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/agent-utils.sh"

AGENT_KEY="my_agent"
REPORT_FILE="${AGENTS_DIR}/my-agent-report.md"
LOG_FILE="${LOGS_DIR}/my-agent-$(date '+%Y-%m-%d').log"

preflight_claude
log_info "=== My Agent starting ==="

# ── Read shared context from other agents ──
SHARED_CONTEXT=$(read_shared_context "${AGENT_KEY}")

# ── Build the prompt ──
PROMPT="You are the my-agent scheduled agent for this project.

Your responsibilities:
[Define agent-specific responsibilities here]

## Context from Other Agents
${SHARED_CONTEXT}

Write your report. Include a shared context block at the end:

SHARED_CONTEXT_START
## My Agent -- $(date '+%Y-%m-%d')
- **Status**: GREEN / YELLOW / RED
- Key findings
SHARED_CONTEXT_END"

# ── Run Claude CLI in headless mode ──
cd "${PROJECT_DIR}"
"${CLAUDE_BIN}" -p "${PROMPT}" \
  --allowedTools "Read,Glob,Grep,Bash(npm run *),Bash(pnpm run *)" \
  --output-format text \
  > "${REPORT_FILE}" 2>>"${LOG_FILE}" || {
    log_error "Claude execution failed. Check ${LOG_FILE}"
    exit 1
  }

log_info "Report written to ${REPORT_FILE}"
extract_and_write_shared_context "${AGENT_KEY}" "${REPORT_FILE}"
log_info "=== My Agent complete ==="
```

The `# SCHEDULE:` comment is read by `install-agents.sh` to auto-generate launchd plists.

### Key Design Choices

- **`source lib/agent-utils.sh`** — Shared library handles env setup, fd limits, auth preflight, logging, and shared context read/write/prune. No boilerplate duplication.
- **`# SCHEDULE: daily HH:MM`** — Declares the agent's schedule in the script itself. `install-agents.sh` reads this to generate launchd plists automatically.
- **`--allowedTools`** — Restrict what the agent can do. Scheduled agents should be read-only or narrowly scoped.
- **`--output-format text`** — Write the report as plain markdown.
- **`SHARED_CONTEXT_START/END`** — Agents include a shared context block in their report output. `extract_and_write_shared_context` extracts it and appends to `shared-context.md`, auto-pruning to the last 3 entries per agent.
- **Separate log files** — stdout goes to the report file, stderr goes to a dated log file for debugging.

## Scheduling

### macOS (launchd) — Automated Installation

The `install-agents.sh` script (in `templates/scripts/agents/`) auto-discovers agent scripts and generates launchd plists. It reads the `# SCHEDULE:` comment from each script to determine when it runs.

For bundle-local setup and verification, keep the colocated manifests
next to the reusable bundle:

- `templates/scripts/agents/INSTALL.md`
- `templates/scripts/agents/VERIFY.md`

```bash
# Install all agents (auto-discovers scripts with SCHEDULE comments):
bash scripts/agents/install-agents.sh

# Check status:
bash scripts/agents/install-agents.sh --status

# Test a specific agent (don't test from terminal — it masks launchd issues):
launchctl start com.project-name.my-agent

# Uninstall all:
bash scripts/agents/install-agents.sh --unload
```

The installer handles all four launchd gotchas automatically (fd limits, env vars, ProgramArguments wrapper, log paths). No manual plist authoring needed.

### macOS (launchd) — Manual Plist

If you need custom plist configuration beyond what the installer generates:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.project.agent.my-agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>exec /bin/bash /absolute/path/to/project/scripts/agents/my-agent.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
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
    <string>/Users/YOUR_USERNAME</string>
    <key>TERM</key>
    <string>xterm-256color</string>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/Users/YOUR_USERNAME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>/absolute/path/to/project/logs/my-agent.log</string>
  <key>StandardErrorPath</key>
  <string>/absolute/path/to/project/logs/my-agent.error.log</string>
</dict>
</plist>
```

#### macOS launchd Gotchas

launchd provides a minimal execution environment that breaks Claude CLI in four ways. All four must be fixed together — any single missing fix causes silent failure. See [Error #37](../patterns/agent-errors.md#error-37-scheduled-agent-silently-fails-under-macos-launchd) and [Error #38](../patterns/agent-errors.md#error-38-claude-cli-crashes-with-unexpected-when-plist-runs-script-directly) for full details.

**1. File descriptor limit (hard cap 256).** launchd sets a hard limit of 256 open files. Claude CLI needs 100K+ for Node.js. `ulimit -n` in the script cannot raise above the hard limit — the fix must be in the plist via `HardResourceLimits` and `SoftResourceLimits` (shown in the plist template above).

**2. Missing environment variables.** launchd doesn't source shell profiles (`~/.zshrc`, `~/.bash_profile`). PATH is minimal (`/usr/bin:/bin:/usr/sbin:/sbin`), HOME may be unset, TERM is absent. The fix is `EnvironmentVariables` in the plist (shown above), supplemented by fallback exports in the script.

**3. No interactive authentication.** Claude CLI's default OAuth flow opens a browser. Under launchd there's no TTY and no browser. Fix: run `claude setup-token` once from an interactive terminal to create a persistent API token. The script should verify auth works before attempting the main task.

**4. ProgramArguments must use `/bin/bash -c exec`.** When launchd directly executes a script located inside a project directory (via shebang), Claude CLI crashes with "An unknown error occurred (Unexpected)". The fix is to use `/bin/bash -c "exec /bin/bash /path/to/script.sh"` in ProgramArguments (shown in the plist template above). This changes the process context so Claude doesn't misidentify the project root from the initial process arguments.

**Testing:** Always test with `launchctl start <label>`, never by running the script from a terminal. Terminal execution has full env vars, high fd limits, and interactive auth — it masks all four problems.

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

## Concrete Agent Prompts

### Test Health Agent

```bash
PROMPT="You are the test-health scheduled agent.

Run the full test suite 3 times to detect flaky tests:
1. Run: pnpm run test --reporter json 2>&1
2. Record which tests pass/fail on each run
3. Flag any test that fails on at least 1 of 3 runs as FLAKY
4. Report: total tests, pass rate, flaky tests (with file:line), coverage if available

Write your report to docs/agents/test-health-report.md with sections:
- Summary (1 line: GREEN/YELLOW/RED + pass rate)
- Flaky Tests (file:line + failure message for each)
- Failed Tests (consistently failing)
- Coverage Changes (if measurable)

Append to shared-context.md:
- Overall status
- Any flaky tests that other agents should know about"
```

### Security Audit Agent

```bash
PROMPT="You are the security-audit scheduled agent.

Perform these checks:
1. Run: pnpm audit --json 2>&1 (or npm audit / pip audit)
2. Search for hardcoded secrets: grep for API keys, tokens, passwords in source files
3. Check .env.example against actual env var usage — flag undocumented vars
4. Check for injection vectors: unsanitized user input in SQL, shell commands, HTML
5. Verify CORS configuration if applicable

Write your report to docs/agents/security-audit-report.md with sections:
- Summary (1 line: GREEN/YELLOW/RED + critical count)
- Dependency Vulnerabilities (severity, package, recommendation)
- Hardcoded Secrets (file:line — DO NOT include the actual secret)
- Injection Risks (file:line + type)
- Configuration Issues

Append to shared-context.md:
- Critical vulnerabilities count
- Any findings that affect other agents' domains"
```

### Code Quality Agent

```bash
PROMPT="You are the code-quality scheduled agent.

Perform these checks:
1. Run: pnpm run lint --format json 2>&1
2. Run: pnpm run typecheck 2>&1
3. Search for TODO/FIXME/HACK comments and count by category
4. Identify dead code: exported functions with zero import references
5. Check for files over 500 lines (complexity indicator)

Write your report to docs/agents/code-quality-report.md with sections:
- Summary (1 line: GREEN/YELLOW/RED + issue count)
- Lint Issues (count by rule, top 5 most frequent)
- Type Errors (count + file:line for each)
- Technical Debt (TODO/FIXME/HACK counts + examples)
- Large Files (path + line count)
- Dead Code Candidates (exported but never imported)

Append to shared-context.md:
- Issue counts by category
- New issues since last run (if previous report exists)"
```

### Dependency Health Agent

```bash
PROMPT="You are the dependency-health scheduled agent.

Perform these checks:
1. Check for outdated packages: pnpm outdated --format json 2>&1
2. Identify major version bumps available (breaking changes)
3. Verify lockfile integrity: pnpm install --frozen-lockfile 2>&1
4. Check for duplicate packages in the dependency tree
5. Flag packages with no recent updates (>2 years, possible abandonment)

Write your report to docs/agents/dependency-health-report.md with sections:
- Summary (1 line: GREEN/YELLOW/RED + outdated count)
- Critical Updates (security patches, major versions behind)
- Outdated Packages (name, current, latest, type of update)
- Lockfile Status (clean or issues found)
- Abandoned Packages (no updates in 2+ years)

Append to shared-context.md:
- Packages needing urgent updates
- Any dependency conflicts that affect other agents"
```

## Resilience Patterns

### Failure Recovery

Scheduled agents should be resilient to common failure modes:

```bash
# Retry logic for the Claude CLI call
MAX_RETRIES=2
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if claude -p "$PROMPT" --allowedTools "Read,Glob,Grep" --output-format text > "$REPORT_FILE" 2>&1; then
    break
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  echo "[$(date)] Attempt $RETRY_COUNT failed. Retrying..."
  sleep 10
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "[$(date)] $AGENT_NAME FAILED after $MAX_RETRIES attempts" >> "$REPORT_FILE"
fi
```

### WIP Limits

For agents that produce work items requiring human review (like research or planning agents), enforce a WIP limit to prevent accumulating more unreviewed work than humans can handle:

```bash
# Check how many items are pending review before starting new work
PENDING_COUNT=$(ls docs/agents/pending-review/ 2>/dev/null | wc -l)
WIP_LIMIT=5

if [ "$PENDING_COUNT" -ge "$WIP_LIMIT" ]; then
  echo "[$(date)] WIP limit reached ($PENDING_COUNT/$WIP_LIMIT). Skipping run."
  exit 0
fi
```

### Stagger Schedules

Don't run multiple agents at the same time. If they write to the same shared context file, they can conflict. Stagger by at least 15 minutes:

| Agent | Schedule |
|-------|----------|
| Test health | Daily 6:00 AM |
| Code quality | Daily 6:15 AM |
| Security audit | Weekly Monday 6:30 AM |
| Dependency health | Weekly Monday 6:45 AM |

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

## Report Lifecycle

Agent reports are internal operational tools, not project artifacts. They follow a strict lifecycle that applies to all projects — open-source and closed-source alike (Rule #70):

1. **Agents write reports to `docs/agents/`** on disk during overnight runs.
2. **Reports accumulate historically** — never deleted, always available for review.
3. **Reports are never committed to version control.** `docs/agents/`, `logs/`, and `scripts/agents/` are gitignored.
4. **Triage discovers reports via timestamps** (Rule #71), not git status. A `.last-triage` marker file in `docs/agents/` tracks which reports have been processed.
5. **Only code fixes are committed.** When triage resolves findings, the fix goes into git. The report that triggered the fix stays local.

This separation means:
- Public repositories never expose operational details (security audit findings, internal metrics, agent status).
- Private repositories don't clutter git history with machine-generated reports.
- Historical reports remain on disk indefinitely for the operator to review.
- Triage works identically regardless of git tracking — no git status dependency.

### Required `.gitignore` entries

Every project using scheduled agents must gitignore these directories:

```gitignore
# Agent operational output (never committed)
docs/agents/
logs/
scripts/agents/
```

## Morning Triage

After scheduled agents finish their overnight runs, use `/triage` to process all reports:

1. Checks the `.last-triage` marker to discover reports modified since the last triage run
2. If no marker exists (first run), processes ALL reports in `docs/agents/`
3. Checks `logs/` for agent failures (a missing report might mean a crashed agent)
4. Reads all reports and shared-context.md
5. Synthesizes findings and drafts an action plan
6. Implements all fixes (fix everything — Rule #58)
7. Commits code fixes only — reports stay on disk (Rule #70)
8. Updates shared-context.md with triage results
9. Touches `docs/agents/.last-triage` to mark reports as processed

For multi-project orchestration, the `morning-triage.sh` script template (in `templates/scripts/`) runs `/triage` across all configured projects sequentially, producing a cross-project summary.

## Prerequisites

- Claude CLI installed and authenticated (`claude --version`)
- Non-interactive auth configured: run `claude setup-token` from an interactive terminal (required for launchd/cron — OAuth won't work without a browser)
- macOS launchd: use `install-agents.sh` (handles all four gotchas automatically), or ensure plist includes `HardResourceLimits`/`SoftResourceLimits` with `NumberOfFiles: 122880`, `EnvironmentVariables` with HOME, TERM, PATH, and `ProgramArguments` using `/bin/bash -c "exec /bin/bash <script>"` format (see [Error #37](../patterns/agent-errors.md#error-37-scheduled-agent-silently-fails-under-macos-launchd) and [Error #38](../patterns/agent-errors.md#error-38-claude-cli-crashes-with-unexpected-when-plist-runs-script-directly))
- `lib/agent-utils.sh` copied to `scripts/agents/lib/` (provides env setup, logging, shared context utilities)
- Project dependencies installed (agents may run test/build commands)
- `docs/agents/` and `logs/` directories exist (created automatically by `agent-utils.sh`)
- `docs/agents/`, `logs/`, and `scripts/agents/` gitignored (Rule #70)
