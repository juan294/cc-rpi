# Commands Bundle — INSTALL

This bundle is the canonical slash-command set for cc-rpi projects.

## Prerequisites

- A project with `.claude/commands/`
- For OpenCode compatibility, also create `.opencode/commands/`
- `AGENTS.md` should tell Codex/OpenCode to treat
  `.claude/commands/*.md` as the workflow source of truth

## Install Steps

1. Copy the command files you want from `templates/commands/` into the
   target project's `.claude/commands/`.
2. For project bootstrap/adopt/update/detach at user level, install
   those commands into `~/.claude/commands/` instead of the project.
3. Adjust any project-specific paths or stack-specific command details.
4. If the project supports OpenCode, copy the matching wrappers from
   `templates/opencode/commands/`.

## Bundle Scope

Common project-level commands:

- `research.md`
- `plan.md`
- `implement.md`
- `validate.md`
- `describe-pr.md`
- `pre-launch.md`
- `remediate.md`
- `triage.md`
- `status.md`
- `fix-ci.md`
- `update-docs.md`
- `release.md`

Blueprint lifecycle commands that usually live in `~/.claude/commands/`:

- `bootstrap.md`
- `adopt.md`
- `update.md`
- `detach.md`
