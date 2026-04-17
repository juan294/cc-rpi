# Project: cc-rpi

## Codex and OpenCode Compatibility

This repository is the cc-rpi blueprint. It is authored for Claude Code,
but this `AGENTS.md` file makes the same methodology operable in Codex
and OpenCode.

Source of truth for this repo:

- `CLAUDE.md` -- repo overview, workflow, commands, git conventions
- `.claude/commands/*.md` -- active project-level workflow commands
- `templates/commands/*.md` -- canonical exported command templates
- `.opencode/commands/*.md` -- OpenCode command shims that dispatch to
  the canonical `.claude/commands/*.md` workflow files
- `templates/opencode/commands/*.md` -- exported OpenCode command shims
- `.claude/rules/*.md` -- repo-local rules
- `templates/rules/*.md` -- canonical exported rule templates
- `.claude/skills/*/SKILL.md` and `templates/skills/*/SKILL.md` --
  skill content
- `.codex/skills/*/SKILL.md` -- Codex-only skills that intentionally
  stay outside `.claude/skills/`
- `opencode.json` and `templates/opencode.json.template` -- OpenCode
  instruction loading for `CLAUDE.md` and `.claude/rules/*.md`

## Command Dispatch

When the user invokes a slash-style command:

- Use `.claude/commands/<name>.md` when it exists in this repo
- For blueprint-lifecycle commands that only exist in templates
  (`/bootstrap`, `/adopt`, `/update`, `/detach`), use the matching file
  in `templates/commands/`
- Read the command file completely before acting
- Follow it as the workflow spec, translating Claude-specific mechanics
  to Codex equivalents when needed

## Claude-to-Codex/OpenCode Translation

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

## OpenCode Command Dispatch

When the user invokes a slash-style command in OpenCode:

- Use the matching file in `.opencode/commands/` when it exists
- Treat that file as a thin wrapper around the canonical
  `.claude/commands/<name>.md` workflow, or the matching
  `templates/commands/<name>.md` file for blueprint lifecycle commands
- Preserve the existing slash command names; do not fork the workflow
  into OpenCode-specific copies unless the command surface itself must
  change

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
- `.opencode/commands/` contains OpenCode wrappers only; the workflow
  source of truth remains `.claude/commands/`
- Research and plan docs in `docs/research/` and `docs/plans/` are
  committed history; `docs/agents/` is operational output and remains
  local-only
