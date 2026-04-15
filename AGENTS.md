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

- `/simplify` -- run a dedicated post-implementation quality pass for
  reuse, cleanliness, and efficiency
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

## Repo-Specific Notes

- `main` is the only branch for this repo
- `templates/` is the exported blueprint; keep it canonical
- `.claude/` is the repo's own self-applied installation of the
  blueprint
- Research and plan docs in `docs/research/` and `docs/plans/` are
  committed history; `docs/agents/` is operational output and remains
  local-only
