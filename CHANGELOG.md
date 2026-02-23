# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

## [1.2.0] - 2026-02-23

### Added

- **`/update` command** — user-level slash command for syncing projects with the latest cc-rpi blueprint. Uses incremental git-diff detection via `.claude/cc-rpi-sync.json`, updates commands (direct replacement), CLAUDE.md (smart merge of blueprint-managed sections), and settings.json (additive merge). Works both interactively and headlessly for scheduled agents.
- **Blueprint sync scheduled agent** (`templates/scripts/cc-rpi-update-agent.sh`) — shell script template for nightly automated syncing. Reads update instructions from cc-rpi at runtime (self-updating). Includes retry logic, launchd scheduling templates, and preflight checks.
- **Blueprint Sync section** in `setup-checklist.md` — step-by-step setup for nightly syncing with explanation of the three-tier update strategy.
- **Memory Management section** in `CLAUDE.md.template` — new blueprint-managed section that instructs agents to proactively save operational lessons (CI patterns, workarounds, environment quirks) to auto memory without being asked.
- **Memory-save phase** in `/bootstrap` and `/adopt` commands — Phase 4 (bootstrap) and Phase 5 (adopt) now require agents to save all key decisions, project context, and internalized rules to auto memory after setup, so future sessions start with full awareness.
- **Errors #22–#25** — four new agent error patterns added to `agent-errors.md` and `quick-reference.md`:
  - **#22:** `rm` fails on stale file list — agent operates on memorized filenames without re-reading directory
  - **#23:** `gh` commands fail when agent fabricates/guesses repo names, branch names, or identifiers
  - **#24:** Cross-project `../` relative paths fail because Bash cwd resets between calls
  - **#25:** `git pull --rebase` fails on branches with no upstream tracking — use `git push -u` first

## [1.1.0] - 2026-02-23

### Added

- **Errors #16–#21** — six new agent error patterns added to `agent-errors.md` and `quick-reference.md`:
  - **#16:** Commands fail because dependencies aren't installed (fresh worktrees/clones missing node_modules)
  - **#17:** jq syntax error from over-escaping `!=` as `\!=` inside single-quoted filters
  - **#18:** Git commands fail on repos with no commits yet (bootstrap scenario)
  - **#19:** API content filter blocks parallel boilerplate file creation
  - **#20:** `gh release create` uses `--notes`, not `--body` (wrong flag name across subcommands)
  - **#21:** `pip3 install` fails on macOS with Homebrew Python 3.12+ (externally-managed-environment)

### Fixed

- Removed hardcoded local paths from template commands (`/bootstrap`, `/adopt`)
- Replaced hardcoded GitHub username in template Chapa badge URLs with `[OWNER]` placeholder
- Genericized personal references in `CLAUDE.md` for public consumption
- Removed unused GitHub Sponsors configuration

## [1.0.0] - 2026-02-21

### Added

- **Human-readable guide** (`GUIDE.md`) — standalone walkthrough of philosophy, workflow, command cheat sheet, and practical tips. Designed for humans, articles, and NotebookLM podcasts.
- **`/bootstrap` command** — user-level slash command for setting up new projects from scratch. Reads the blueprint, asks about project type and stack, creates all configuration.
- **`/adopt` command** — user-level slash command for migrating existing projects. Audits configuration, infrastructure, and workflow with parallel agents, presents prioritized gap report, migrates incrementally with user approval.
- **Worked examples directory** (`examples/`) — sample research document, implementation plan with phase files, error/success log entries, and pseudocode notation examples.
- **Phase completion criteria** — "done when" / "NOT done if" checklists for all four RPI phases in `four-phases.md`.
- **Failure recovery decision trees** — 6 recovery flows (wrong research, plan-reality mismatch, CI failures, subagent conflicts, scheduled agent crashes, validation issues) in `four-phases.md`.
- **Phase handoff templates** — structured handoff documents with YAML frontmatter, what carries over vs starts fresh, and 4 resume scenarios (clean continuation, diverged codebase, incomplete work, stale handoff) in `four-phases.md`.
- **Function stakes framework** — 5-level classification (read-only through critical) with approval requirements and fallback behavior in `agent-design.md`.
- **Precise autonomy boundaries** — 14-action decision table for agent autonomy in `agent-design.md`.
- **Subagent quick reference table** — all 10 roles mapped to Claude Code `subagent_type` parameters in `agent-design.md`.
- **Documentarian rule examples** — 3 pairs of good/bad examples in `agent-design.md`.
- **Agent Teams as default** — enabled via `settings.json.template`, documented in `agent-design.md` and `context-engineering.md` with architecture, comparison to subagents, and limitations.
- **Compaction examples** — good/bad compaction, discard-vs-preserve table, and `run_silent` micro-compaction pattern in `context-engineering.md`.
- **Hooks documentation** — configuration examples and common patterns in `context-engineering.md`.
- **Error/success log storage** — directory structure, index file pattern, when to query logs, graduation-to-rules workflow, and compression philosophy in `error-success-logging.md`.
- **Concrete scheduled agent prompts** — test-health, security-audit, code-quality, dependency-health with full prompt templates in `scheduled-agents.md`.
- **Scheduled agent resilience** — retry logic, WIP limits, and stagger schedule table in `scheduled-agents.md`.
- **`settings.json.template`** — shared settings with Agent Teams, hooks, and permission whitelist.
- **`README-header.md`** — standard README header template with badges and Chapa embed.
- **Project-type adaptation** — setup guidance for 6 archetypes (web app, library, CLI, monorepo, Python, static site) in `setup-checklist.md`.
- **Shared vs local configuration** — documented CLAUDE.md/CLAUDE.local.md and settings.json/settings.local.json split pattern in `setup-checklist.md`.
- **Workflow walkthroughs** (`examples/workflows/`) — three end-to-end developer interaction examples showing exact commands, agent responses, and decision points: bootstrapping a new project, adding a new feature (rate limiting), and refactoring existing code (auth service extraction).
- **Error #15: `git branch -d` on worktree branches** — new pattern added to `agent-errors.md` and `quick-reference.md`. Always use uppercase `-D` for worktree branch cleanup.

## [0.1.0] - 2026-02-20

### Added

- RPI (Research-Plan-Implement) methodology adapted for Claude Code
  - Philosophy, context engineering, four phases, agent design
  - Pseudocode notation format for implementation plans
  - Testing and error/success logging frameworks
  - Push accountability — post-push CI ownership protocol with background polling and fix-and-repush cycle (`methodology/push-accountability.md`)
  - CI & guardrails — pre-commit hooks, CI workflows, development guardrails, enforcement stack (`methodology/ci-and-guardrails.md`)
  - Scheduled agents — recurring quality agents on cron/launchd with shared context system (`methodology/scheduled-agents.md`)
  - TDD protocol — Red-Green-Refactor cycle integrated into testing.md
  - Agent team patterns — 6 team scenarios (debug, pre-launch audit, self-healing, health check, feature implementation, code review) in agent-design.md
  - Agent autonomy principles — tool exhaustion rule, autonomy boundaries, self-correction over escalation in agent-design.md
  - Claude settings & permissions — permission whitelisting, environment variables, model selection in context-engineering.md
- Known agent error patterns catalog (`patterns/agent-errors.md`)
  - Errors 12-14: push-and-forget, skipping TDD, suggesting manual steps
- Quick reference operational rules (`patterns/quick-reference.md`)
  - Rules 12-14: CI monitoring, TDD, tool exhaustion
- Project templates
  - CLAUDE.md template with push accountability, TDD, and autonomy sections
  - Setup checklist with pre-commit hooks, CI setup, push accountability, and scheduled agents
  - Slash commands: `/research`, `/plan`, `/implement`, `/validate`, `/describe-pr`, `/pre-launch`
- Open source project scaffolding (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY)
