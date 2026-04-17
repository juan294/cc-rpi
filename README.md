# cc-rpi — Claude Code Reference & Project Intelligence

[![CI](https://github.com/juan294/cc-rpi/actions/workflows/validate.yml/badge.svg)](https://github.com/juan294/cc-rpi/actions/workflows/validate.yml)
[![Version: v1.17.0](https://img.shields.io/badge/Version-v1.17.0-orange.svg)](https://github.com/juan294/cc-rpi/releases/tag/v1.17.0)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)

A blueprint repository for setting up and running projects with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), with a Codex compatibility layer via `AGENTS.md`. Contains the RPI (Research-Plan-Implement) methodology, a catalog of known agent errors, and operational rules learned from hundreds of real sessions.

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed and configured
- Git

## Quick Start

Clone the repository:

```bash
git clone https://github.com/juan294/cc-rpi.git
```

Then tell Claude Code in your target project:

> Go read the cc-rpi repository and set up this project following all the best practices. Read the quick reference, error catalog, and methodology, then configure CLAUDE.md, AGENTS.md, and slash commands for this project.

Bootstrapped and adopted projects now also get an `AGENTS.md`
compatibility layer so the same methodology can be operated from Codex /
GPT-5.x without changing the workflow.

If you also use Codex, the blueprint ships a Codex-only
`codex-simplify` skill at `cc-rpi/.codex/skills/codex-simplify/`.
Copy it into `~/.codex/skills/codex-simplify/` if you want a reusable
equivalent of Claude Code's native `/simplify` without creating a
project skill named `simplify`.

## Guide

New here? Read **[GUIDE.md](GUIDE.md)** — a human-readable walkthrough of the philosophy, the workflow, and every command. It covers everything you need to know without diving into every file. Also works great as source material for NotebookLM podcasts or articles.

## What's Inside

### Methodology (`methodology/`)

The full Research-Plan-Implement pattern adapted for Claude Code, based on HumanLayer's opencode-rpi and ACE-FCA framework. Organized by topic (10 files, in reading order):

- **Philosophy** — Core tenets, error amplification principle, mental alignment
- **Context Engineering** — The foundational discipline: compaction, context quality, settings & permissions
- **Four Phases** — Research, Plan, Implement, Validate with detailed processes
- **Agent Design** — Documentarian rule, tool restrictions, subagent catalog, Anthropic-native commands (`/simplify`, `/batch`), agent teams, autonomy principles
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

### Examples (`examples/`)

Sample documents illustrating the methodology in practice — a research document, implementation plan with phase files, error/success log entries, and additional pseudocode notation examples. Use these as reference when producing your own RPI artifacts.

### Templates (`templates/`)

Ready-to-use starting points for new projects:

- **CLAUDE.md template** — Slim project configuration (~70 lines) with universal instructions
- **AGENTS.md template** — Codex compatibility layer that teaches Codex how to interpret the cc-rpi `.claude/` layout
- **Codex-only skills** — `.codex/skills/` holds personal Codex helpers
  that intentionally stay outside `.claude/skills/`; currently includes
  `codex-simplify`
- **Rule templates** — `.claude/rules/` files with conditional loading (deployment, Supabase, testing) and universal rules (RPI details, push accountability)
- **settings.json template** — `.claude/settings.json` with Agent Teams, hooks, and permissions
- **Setup checklist** — Step-by-step guide including rules, skills, hooks, CI, and scheduled agents
- **Slash commands** — `/bootstrap`, `/adopt`, `/update`, `/research`, `/plan`, `/implement`, `/validate`, `/describe-pr`, `/pre-launch`, `/remediate`, `/triage`, `/status`, `/fix-ci` — plus Anthropic-native `/simplify` and `/batch`
- **Scheduled agent scripts** — Nightly blueprint sync and multi-project morning triage with launchd/cron templates

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
