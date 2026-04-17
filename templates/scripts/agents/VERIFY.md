# Scheduled Agents Bundle — VERIFY

Use this after installing the scheduled-agents bundle into a project.

## Verify the Bundle Exists

- `scripts/agents/install-agents.sh` exists
- `scripts/agents/lib/agent-utils.sh` exists
- at least one agent script exists in `scripts/agents/`

## Verify Schedules Are Discoverable

Run:

```bash
bash scripts/agents/install-agents.sh --list
```

Expected result:
- each scheduled agent appears once
- scripts without `# SCHEDULE:` comments are skipped

## Verify Installation

Run:

```bash
bash scripts/agents/install-agents.sh --status
```

Expected result:
- launchd labels appear for installed agents
- no immediate bootstrap/load failure is reported

## Verify Runtime Output

1. Start one agent manually with `launchctl start <label>`.
2. Confirm it produces:
   - a report in `docs/agents/`
   - a log file in `logs/` or `~/Library/Logs/<project>/`

## Manual Exceptions

- Linux/cron projects will verify scheduling differently.
- Agents that require project dependencies or external services may need
  a project-specific smoke run after installation.
