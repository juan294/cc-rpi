# Update Project from cc-rpi Blueprint

You are syncing this project with the latest cc-rpi blueprint. The blueprint lives at `<path-to-your-cc-rpi-clone>/`.

This command works for both interactive use (`/update`) and headless scheduled agents.

## Prerequisites

Before starting, verify this project was bootstrapped or adopted from cc-rpi:
- If `.claude/commands/` exists with RPI commands (research, plan, implement, validate) → proceed.
- If CLAUDE.md exists with "RPI Workflow" section → proceed.
- If neither exists → this project hasn't been set up with cc-rpi. Tell the user to run `/adopt` first and stop.

## Phase 1: Check for Updates

1. Pull the latest cc-rpi: `git -C <cc-rpi-path> pull --rebase`
2. Check if `.claude/cc-rpi-sync.json` exists in THIS project.
   - If YES: read it and note the `lastSyncCommit` hash.
   - If NO: this is the first sync. Treat everything as new.

3. If `lastSyncCommit` exists:
   - Run `git -C <cc-rpi-path> log --oneline <lastSyncCommit>..HEAD` to see what changed.
   - Run `git -C <cc-rpi-path> diff --name-only <lastSyncCommit>..HEAD` to get changed files.
   - If nothing changed, report "Already up to date" and stop.

## Phase 2: Internalize New Knowledge

Read these files from cc-rpi to internalize the latest rules and patterns:

4. `patterns/quick-reference.md` — All operational rules.
5. `patterns/agent-errors.md` — All known error patterns.
6. `methodology/README.md` — Methodology overview.

On incremental syncs (lastSyncCommit exists), prioritize reading files that appear in the git diff. You can skip unchanged methodology files.

## Phase 3: Update Slash Commands

7. Compare each file in cc-rpi `templates/commands/` against this project's `.claude/commands/`:
   - **Skip** `bootstrap.md`, `adopt.md`, and `update.md` — these are user-level commands, not project-level.
   - For each remaining command (research, plan, implement, validate, describe-pr, pre-launch):
     - If it exists in both locations and the cc-rpi version is different → replace the project version.
     - If it exists in cc-rpi but not in this project → add it.
     - If it exists only in this project → leave it (project-specific command).

## Phase 4: Update CLAUDE.md

8. Read this project's CLAUDE.md fully.
9. Read cc-rpi's `templates/CLAUDE.md.template`.
10. Identify **blueprint-managed sections** by their headers. These sections come from the template and should be kept in sync:
    - `## RPI Workflow` (and all `###` subsections under it)
    - `## Agent Operational Rules` (and all `###` subsections under it)
    - `## Push Accountability`
    - `## TDD Protocol`
    - `## Agent Autonomy`
    - `## Memory Management`
11. For each blueprint-managed section:
    - If the project's version differs from the template → update to match.
    - If the project has added project-specific content *within* a blueprint section (e.g., extra rules), preserve it — only update the parts that came from the template.
    - If a section doesn't exist in the project → skip it (don't add sections, that's `/adopt`'s job).
12. **Do NOT touch** project-specific sections: One-liner, Stack, Key Commands, Git Workflow, Deployment, Commit Messages, Research Documents, Implementation Plans, or any custom section.
13. The `### CRITICAL: Run verification commands sequentially` section under Key Commands is blueprint-originated — update it if it exists.

## Phase 5: Update settings.json

14. Read this project's `.claude/settings.json`.
15. Compare against cc-rpi's `templates/settings.json.template`.
16. Add any new `permissions.allow` entries from the template that are missing in the project.
17. Add any new `env` entries from the template that are missing.
18. **Never remove** project-specific permissions, env vars, hooks, or deny rules.

## Phase 6: Write Sync Metadata

19. Get the current HEAD commit hash of cc-rpi: `git -C <cc-rpi-path> rev-parse HEAD`
20. Get the current version tag: `git -C <cc-rpi-path> describe --tags --abbrev=0 2>/dev/null`
21. Write/update `.claude/cc-rpi-sync.json`:
    ```json
    {
      "lastSyncCommit": "<commit-hash>",
      "lastSyncDate": "YYYY-MM-DD",
      "blueprintVersion": "<version-tag>"
    }
    ```

## Phase 7: Report and Commit

22. If any project files were changed (commands, CLAUDE.md, settings.json):
    - Stage only the changed files (not unrelated changes).
    - Commit with: `chore: sync with cc-rpi blueprint <version-tag>`
    - Always update the sync metadata even if no other files changed.

23. Present a summary:
    - cc-rpi version synced to (tag + commit hash)
    - Commands updated/added (list them)
    - CLAUDE.md sections updated (list them)
    - settings.json changes (list them)
    - Notable new content: new error patterns, new rules, methodology changes
    - "Already up to date" if nothing changed

## Rules

- **Never delete project content.** Only add or update blueprint-managed sections.
- **Preserve project identity.** Stack, deployment, key commands, commit conventions — these are the project's own.
- **Be idempotent.** Running twice with no cc-rpi changes should produce zero file changes.
- **Commit atomically.** All sync changes go in one commit with the sync metadata.
- **If unsure, skip and report.** When a section has been heavily customized beyond the template, leave it alone and note it in the report as "skipped — heavily customized."
- **No interactive prompts.** This command must work headlessly for scheduled agents. Don't ask for confirmation — just apply safe updates and report what you did.
