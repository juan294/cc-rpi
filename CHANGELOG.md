# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.10.0] - 2026-03-19

### Added

- **Rule #59: Wrap context-specific CLAUDE.md sections in `<important if="condition">` tags** -- as CLAUDE.md grows, conditional blocks give the agent explicit activation signals so domain-specific rules (testing, deployment, CI) only fire when relevant. Keeps universal content unwrapped. Added to `patterns/quick-reference.md` (Rule #59) and `templates/CLAUDE.md.template` (new "Conditional Blocks" section with examples and authoring guidance).
- **Session stability and prompt caching guidance** in `methodology/context-engineering.md` -- don't switch models mid-session (cache is per-model, switching to Haiku mid-Opus-session is more expensive, not less -- use subagents instead) and don't add/remove MCP tools mid-session (tools are part of the cached prefix, loading/unloading invalidates the cache). Both are counterintuitive behaviors that silently increase cost and latency.
- **Expanded skills authoring guide** in `methodology/agent-design.md` -- skills are folders (not just markdown files) with scripts, references, assets, and examples. Covers folder structure with progressive disclosure, SKILL.md format with gotchas section, 5 authoring principles (description for triggering, lead with gotchas, don't state the obvious, avoid railroading, include scripts), 9-category skill taxonomy (library reference, product verification, data fetching, business process, code scaffolding, code quality, CI/CD, runbooks, infrastructure ops), and on-demand hooks for situational guardrails. Updated `templates/setup-checklist.md` to reference the taxonomy and folder pattern.

## [1.9.0] - 2026-03-16

### Added

- **`/remediate` command** -- post-pre-launch remediation automation. Parses the pre-launch audit report, creates GitHub issues for every finding (100% coverage regardless of priority), spawns parallel worktree agents that follow TDD (write failing test, implement fix, verify, `/simplify`), merges PRs sequentially with test verification after each merge, runs a final `/simplify` on the integrated result, monitors CI, cleans up all worktrees and branches, and generates a remediation report. Completes the release cycle: `/pre-launch` -> `/remediate` -> `/update-docs` -> `/release`.
- **`/triage` command** -- morning agent report processing. Three-layer exhaustive discovery (git status + Glob + cross-reference) to find every report -- never misses one. Checks `logs/` for agent failures before analyzing reports. Reads all reports completely, synthesizes findings, drafts action plan for ALL items (fix everything, Rule #58), implements fixes, commits reports as historical artifacts separately from code fixes, updates shared-context.md, pushes, and monitors CI.
- **`morning-triage.sh` script template** -- multi-project orchestration. Configurable list of project directories, runs `/triage` in each sequentially, produces a cross-project summary. Archy-compatible for higher-level orchestration.
- **Rule #58: Fix everything, always** -- new core tenet and operational rule. Categorize findings by severity, but fix 100% of them. With AI agents, the cost of fixing is near-zero -- the old prioritization model of deferring low-priority items no longer applies. Added to `methodology/philosophy.md` (core tenet #9, key lesson #17) and `patterns/quick-reference.md` (Rule #58).

## [1.8.0] - 2026-03-14

### Added

- **`/release` command** -- project-type-flexible release automation. Detects project type (npm, Rust, Python, Go, docs-only) and branching strategy (main-only vs feature-branch). Bumps versions in all manifest files and references, generates CHANGELOG entry from categorized commits, creates release commit and annotated tag, publishes GitHub release, and advises on registry publish (npm/cargo/twine -- advisory only, never runs publish automatically). Bakes in error pattern guards (#20, #44, #53) and 3 human confirmation gates.
- **`/update-docs` command** -- comprehensive documentation refresh. Spawns 4 parallel read-only discovery agents (change analyst, documentation inventory, diagram analyzer, version reference scanner) to build an update plan from changes since the last release. After user approval, sequentially updates all markdown files, Mermaid diagrams, version badges/references, counts, and inline code docs (JSDoc, Python docstrings, Rust doc comments). Flags uncertain diagrams as `[NEEDS REVIEW]`. Saves report to `docs/agents/update-docs-report.md`.

## [1.7.0] - 2026-03-14

### Added

- **`/detach` command** -- clean removal of cc-rpi from a project. Inventories all blueprint artifacts in 4 tiers (scaffolding files, CLAUDE.md sections, configuration entries, user work products), previews exactly what will be removed, asks for confirmation, then executes in a single atomic commit. Preserves project-specific config and research/plan documents by default. Flags customized files for review before deletion. User-level command installed in `~/.claude/commands/detach.md`.

## [1.6.2] - 2026-03-14

### Fixed

- **Hooks schema in settings.json.template** -- PreToolUse entries used a flat `"command"` field instead of the required nested `"hooks"` array with `{"type": "command", "command": "..."}`. Every project bootstrapped since v1.4.0 had an invalid hook config that was silently ignored. Fixed in `templates/settings.json.template` and `methodology/ci-and-guardrails.md`.

### Added

- **Self-adoption** -- cc-rpi now follows its own RPI methodology. Added `.claude/commands/` (8 workflow commands), `.claude/hooks/guard-bash.sh` (Tier 1 enforcement), `.claude/settings.json`, and `docs/research/` + `docs/plans/` directories. CLAUDE.md rewritten to serve as both repo description and operational rules. Error #48 guard disabled in the local hook copy (main-only workflow).

## [1.6.1] - 2026-03-14

### Added

- **Error #53: Agent runs `gh pr create` without checking for existing PR** — `gh pr create` fails when a PR already exists for the head-to-base branch pair. Check with `gh pr list --head <branch>` first; if one exists, use `gh pr edit` to update it.

## [1.6.0] - 2026-03-13

### Added

- **Error #51: CI explosion from parallel agent pushes** — when N agents push independently, every push triggers M CI workflows (N x M x retries runs). New rule: worktree agents commit locally, main agent batch-pushes all branches in one command, creates all PRs, and monitors CI centrally. Added to `agent-errors.md` (Error #51), `quick-reference.md` (Rule #55), and `agent-design.md` (Parallel Agent Push Strategy section + worktree agent row in Central Commit Rule table).
- **Error #52: Agent assumes GitHub labels exist when creating issues** — `gh issue create --label "chore"` fails if label doesn't exist. Check with `gh label list` or create first. Especially common after `/pre-launch` audits creating multiple issues with category labels.
- **Project File Locations table** in `CLAUDE.md.template` — consolidated all fixed-path references (agent reports, logs, scripts, ADRs, PR descriptions, research docs, plans) into a single scannable table with a one-time "do not search" directive. Eliminates per-session token waste from agents searching for known locations.

## [1.5.0] - 2026-03-08

### Added

- **Errors #46–#50** — five new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #50–#54):
  - **#46:** Scaffolding tool fails on non-empty directory — `create-next-app` and similar tools abort when CLAUDE.md or `.claude/` already exists. Scaffold first, configure second.
  - **#47:** Piping API response to JSON parser without error checking — `curl | jq` crashes with unhelpful parse errors when API returns non-JSON. Save response and check HTTP status first.
  - **#48:** Agent commits or pushes to the wrong branch — doesn't verify current branch before committing. Guard hook now blocks direct push to main/master.
  - **#49:** Sub-agents create git conflicts from parallel work — overlapping file edits and orphaned references. Central commit rule: only the main agent handles git commit/push.
  - **#50:** Agent skips test suite after config changes — config changes have broader blast radius than code. Always run full suite immediately after config/infrastructure changes.
- **`/status` command** — quick 5-line project orientation (branch, last commit, working tree, CI status, open items). Addresses the ~40% empty session problem by giving users a fast check without starting a full task.
- **`/fix-ci` command** — self-healing CI that parses failure logs, spawns parallel fix agents per failure category, and iterates until green (max 3 cycles). Automates the manual diagnose-fix-verify loop.
- **Protected branch guard** in `guard-bash.sh` — blocks `git push origin main/master` unless it's a release flow with `--follow-tags`. Enforces Error #48 at Tier 1.
- **Git Protocol for Multi-Agent Work** section in `agent-design.md` — central commit rule, branch verification, file ownership for parallel agents, and branch strategy for agent orchestration.
- **Self-Healing CI** section in `push-accountability.md` — parallel fix agent pattern for multi-failure CI with retry budget and rules.
- **Branch verification and post-config test rules** in `CLAUDE.md.template` — two new Git Workflow rules and a sub-agent git centralization rule.

## [1.4.0] - 2026-03-05

### Added

- **Three-tier error prevention model** — documented in `methodology/ci-and-guardrails.md`. Rules graduate from Document (advisory) to Prompt (command recipes) to Enforce (hooks). Addresses the core architectural flaw: passive rules in CLAUDE.md don't prevent errors the agent has already been told about.
- **Agent tool hooks (Level 0 enforcement)** — `templates/hooks/guard-bash.sh` PreToolUse hook that blocks known-bad Bash patterns before execution. Currently enforces Error #33 (git pull --rebase with uncommitted changes) and Error #44 (git push --tags). Configured in `settings.json.template`.
- **Git command recipes** in `CLAUDE.md.template` — compound command sequences the agent copies as a unit instead of composing individual commands. Covers push sequence, first push, tag push, and worktree cleanup.
- **Errors #44–#45** — two new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #48–#49):
  - **#44:** `git push --tags` pushes ALL local tags — old tags cause push failure. Use specific tag names or `--follow-tags`.
  - **#45:** Agent fabricates filesystem paths — guesses directory names like `GenAI_Projects` instead of using working directory or discovering with `ls`.

## [1.3.0] - 2026-03-01

### Added

- **`/simplify` integration** — Anthropic's native code quality command (reuse, quality, efficiency) integrated into the RPI workflow. Runs after reviewer approval in `/implement`, recommended after `/pre-launch` audit, and suggested by `/validate` for quality findings. Added to the atomic loop, agent-design catalog, and quick-reference rules (39, 42).
- **`/batch` integration** — Anthropic's native parallel execution command integrated into the planning and implementation workflow. Plans now mark independent phases as `[batch-eligible]`, and `/implement` offers `/batch` for parallel phase execution. Added to agent-design catalog and quick-reference rules (40, 41).
- **Two-layer review model** — Implementation phases now separate plan-compliance review (reviewer subagent) from code-quality review (`/simplify`). Documented in `four-phases.md`, `agent-design.md`, and `CLAUDE.md.template`.
- **Batch eligibility assessment** — Plans must evaluate phase independence and mark `[batch-eligible]` where applicable. Added to plan completion criteria in `four-phases.md` and example in `implementation-plan.md`.
- **Rules #39–#42** in `quick-reference.md` — Native Command Rules covering `/simplify` and `/batch` usage patterns.
- **Post-adoption baseline audit** — `/adopt` now recommends running `/pre-launch` after setup for a full codebase quality baseline, followed by `/simplify` for auto-fixes.
- **Errors #39–#43** — five new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #43–#47):
  - **#39:** `gh` CLI fails with "Projects (classic) deprecated" GraphQL error — upgrade `gh` to latest version
  - **#40:** Agent uses bare `python3` instead of `uv run python` — bypasses venv, causes ModuleNotFoundError
  - **#41:** Over-escaping `!=` as `\!=` in inline Python — SyntaxError from line continuation character
  - **#42:** Python script fails with ModuleNotFoundError — package-relative imports need `-m` flag
  - **#43:** Agent indexes JSON list with string key — TypeError from assuming dict structure

### Changed

- **Emoji removal** — all emoji characters removed from documentation, replaced with text equivalents.

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
