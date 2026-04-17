# Commands Bundle — VERIFY

Use this after installing the command bundle into a project.

## Verify Canonical Command Files

Check that the target project contains the expected files in
`.claude/commands/`, especially:

- `research.md`
- `plan.md`
- `implement.md`
- `validate.md`

## Verify Workflow Ownership

Confirm the project's `AGENTS.md` and `CLAUDE.md` still point agents to
`.claude/commands/` as the workflow spec.

## Verify OpenCode Wrappers

If the project uses OpenCode:

1. Confirm matching files exist in `.opencode/commands/`.
2. Confirm each wrapper points back to the canonical
   `.claude/commands/<name>.md` file instead of duplicating workflow
   logic.

## Verify Project Fit

- command paths match the project's actual `docs/` layout
- stack-specific commands (test/lint/build) reflect the target project
- no project-specific command was overwritten unintentionally

## Manual Exceptions

- User-level lifecycle commands (`bootstrap`, `adopt`, `update`,
  `detach`) are verified in `~/.claude/commands/`, not in a project
  repo.
