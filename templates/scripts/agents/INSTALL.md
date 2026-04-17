# Scheduled Agents Bundle — INSTALL

This bundle contains the reusable pieces for project-local scheduled
agents:

- `install-agents.sh` — installs launchd jobs from `# SCHEDULE:` comments
- `lib/agent-utils.sh` — shared runtime helpers for agent scripts
- example scripts such as `cc-rpi-update-agent.sh` and
  `morning-triage.sh`

## Prerequisites

- macOS with `launchd` if you want to use `install-agents.sh`
- Claude CLI installed and authenticated with `claude setup-token`
- Project directories:
  - `scripts/agents/`
  - `scripts/agents/lib/`
  - `docs/agents/`
  - `logs/`

## Install Steps

1. Copy `lib/agent-utils.sh` into `scripts/agents/lib/`.
2. Copy `install-agents.sh` into `scripts/agents/`.
3. Copy or author one or more agent scripts into `scripts/agents/`.
4. Add a `# SCHEDULE:` comment to each script you want auto-installed.
5. Make the scripts executable.
6. Run:

```bash
bash scripts/agents/install-agents.sh
```

## Notes

- The installer only picks up scripts with a `# SCHEDULE:` comment.
- The installer skips itself and the multi-project `morning-triage.sh`
  orchestrator.
- For Linux or custom scheduling, use this bundle as reference and adapt
  the scripts to cron or your own scheduler.
