# cc-rpi — Claude Code Reference & Project Intelligence

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)

A blueprint repository for setting up and running projects with [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Contains the RPI (Research-Plan-Implement) methodology, a catalog of known agent errors, and operational rules learned from hundreds of real sessions.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed and configured
- Git

## Quick Start

Clone the repository:

```bash
git clone https://github.com/juan294/cc-rpi.git
```

Then tell Claude Code in your target project:

> Go read the cc-rpi repository and set up this project following all the best practices. Read the quick reference, error catalog, and methodology, then configure CLAUDE.md and slash commands for this project.

## What's Inside

### Methodology (`methodology/`)

The full Research-Plan-Implement pattern adapted for Claude Code, based on HumanLayer's opencode-rpi and ACE-FCA framework. Organized by topic (10 files, in reading order):

- **Philosophy** — Core tenets, error amplification principle, mental alignment
- **Context Engineering** — The foundational discipline: compaction, context quality, settings & permissions
- **Four Phases** — Research, Plan, Implement, Validate with detailed processes
- **Agent Design** — Documentarian rule, tool restrictions, subagent catalog, agent teams, autonomy principles
- **Pseudocode Notation** — Compact notation for writing implementation plans
- **Testing** — Automated-first verification hierarchy, TDD protocol
- **Push Accountability** — Post-push CI ownership, background polling, fix-and-repush cycle
- **CI & Guardrails** — Pre-commit hooks, CI workflows, development guardrails, enforcement stack
- **Scheduled Agents** — Recurring quality agents on cron/launchd, shared context system
- **Error & Success Logging** — Framework for systematic improvement

### Known Error Patterns (`patterns/`)

A catalog of recurring Claude Code agent errors documented from real sessions. Each entry includes the symptom, root cause, correct approach, and what to avoid:

- Shell behavior (parallel calls, cwd resets, tilde paths)
- Git operations (worktrees, pre-commit hooks, push rejections)
- GitHub CLI (`gh` field names, CI status checking)
- Node.js/TypeScript (ESM shebangs, Buffer vs string)
- CI & workflow (push-and-forget, skipping TDD, suggesting manual steps)

### Templates (`templates/`)

Ready-to-use starting points for new projects:

- **CLAUDE.md template** — Comprehensive project configuration with all operational rules baked in
- **Setup checklist** — Step-by-step guide including pre-commit hooks, CI setup, push accountability, and scheduled agents
- **Slash commands** — `/research`, `/plan`, `/implement`, `/validate`, `/describe-pr`, `/pre-launch`

## Adding New Patterns

When you discover a new recurring error or best practice:

1. Add it to `patterns/agent-errors.md` (detailed entry with symptom/root cause/solution)
2. Add a one-liner to `patterns/quick-reference.md`
3. Keep entries generic — no project-specific references

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## Community

- [GitHub Discussions](https://github.com/juan294/cc-rpi/discussions) — Ask questions, share ideas, discuss the methodology
- [Contributing Guide](CONTRIBUTING.md) — How to report patterns, propose improvements, submit PRs
- [Code of Conduct](CODE_OF_CONDUCT.md) — Expected behavior for all participants

## Credits

- [HumanLayer](https://humanlayer.dev/) — ACE-FCA framework and opencode-rpi implementation
- Adapted for Claude Code's native capabilities (CLAUDE.md, Task tool, slash commands)

## License

[MIT](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.
