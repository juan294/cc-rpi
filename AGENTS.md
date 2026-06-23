# Project: cc-rpi

## Codex Compatibility

This repository is the cc-rpi blueprint. It is authored for Claude Code,
but this `AGENTS.md` file makes the same methodology operable in Codex.

Source of truth for this repo:

- `CLAUDE.md` -- repo overview, workflow, commands, git conventions
- `.claude/commands/*.md` -- active project-level workflow commands
- `templates/commands/*.md` -- canonical exported command templates
- `.claude/rules/*.md` -- repo-local rules
- `templates/rules/*.md` -- canonical exported rule templates
- `.claude/skills/*/SKILL.md` and `templates/skills/*/SKILL.md` --
  skill content
- `.codex/skills/*/SKILL.md` -- Codex-only skills that intentionally
  stay outside `.claude/skills/`

## Command Dispatch

When the user invokes a slash-style command:

- Use `.claude/commands/<name>.md` when it exists in this repo
- For blueprint-lifecycle commands that only exist in templates
  (`/bootstrap`, `/adopt`, `/update`, `/detach`), use the matching file
  in `templates/commands/`
- Read the command file completely before acting
- Follow it as the workflow spec, translating Claude-specific mechanics
  to Codex equivalents when needed

## Claude-to-Codex Translation

- `/simplify` -- prefer `codex-simplify` when available; otherwise run a
  dedicated post-implementation quality pass for reuse, cleanliness, and
  efficiency
- `/batch` -- use parallel agents and isolated worktrees for
  `[batch-eligible]` work
- `/worktree` or `EnterWorktree` -- implement in an isolated worktree
- `Task` / `Explore` agents -- use Codex subagents or equivalent
  parallel exploration with the same role split
- `AskUserQuestion` -- ask the user directly only when the repo cannot
  answer safely
- `/clear` and `/compact` -- treat as context-management guidance

## Rules and Skills

- Always follow `CLAUDE.md`
- Always read `.claude/rules/rpi-workflow.md`
- Read `.claude/rules/git-recipes.md` for git-heavy tasks
- Read `.claude/rules/contributing.md` when changing docs, templates, or
  patterns
- Load `.claude/skills/drawio/SKILL.md` when diagram work is requested
- Load `.codex/skills/codex-simplify/SKILL.md` when a Codex session
  needs a `/simplify`-style cleanup pass

## Repo-Specific Notes

- `main` is the long-lived canonical branch for this repo
- Implementation still happens in isolated worktrees or temporary branches
- Direct pushes to `main` are high-stakes and require explicit user confirmation
- `templates/` is the exported blueprint; keep it canonical
- `.claude/` is the repo's own self-applied installation of the
  blueprint
- `.codex/skills/` holds blueprint-shipped Codex-only skills; sync them
  into `~/.codex/skills/` for local Codex discovery
- Research and plan docs in `docs/research/` and `docs/plans/` are
  committed history; `docs/agents/` is operational output whose commit
  policy depends on repo visibility (Rule #70) -- gitignored on public
  repos, tracked on private repos as a historical audit trail
- **Contract layer.** The `PostToolUse` hook `verify-edit.sh` (emoji +
  markdownlint on `.md` edits) is Claude-Code-specific -- Codex will not run
  it, so apply Rule #77 (no emojis in docs) by hand. The validator
  `.claude/scripts/validate-findings.py` IS portable: run it on any
  pre-launch report before parsing in a `/remediate`-style flow, and STOP if
  it exits non-zero. When a guard blocks, phrase the reason as
  `BLOCKED / WHY / FIX` with a runnable fix.
- **Contract metrics.** The hook telemetry log is written by the Claude-Code
  hooks, so Codex sessions won't populate it. But `contract-metrics.py` is
  portable stdlib: if a Codex harness writes the same JSONL shape
  (`{ts, session_id, hook, decision, rule, file}`) to
  `.claude/metrics/contract-events.jsonl`, the aggregator and the weekly
  `contract-metrics-agent.sh` snapshot work unchanged.
