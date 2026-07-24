# Update Project from cc-rpi Blueprint

Model tier: **sonnet** — Sonnet 5 (1M context) session.

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
5. `methodology/README.md` — Methodology overview.

The error-patterns skill provides condensed error reference on demand.
On incremental syncs, read the full catalog
(`patterns/agent-errors.md`) only when the diff changes error-pattern
content and the added detail is needed.

On incremental syncs (lastSyncCommit exists), prioritize reading files that appear in the git diff. You can skip unchanged methodology files.

## Phase 3: Update Slash Commands

7. Compare each file in cc-rpi `templates/commands/` against this project's `.claude/commands/`:
   - **Skip** `bootstrap.md`, `adopt.md`, and `update.md` — these are user-level commands, not project-level.
   - For each remaining command (research, plan, implement, validate, describe-pr, pre-launch, explore-release):
     - If it exists in both locations and the cc-rpi version is different → replace the project version.
     - If it exists in cc-rpi but not in this project → add it.
     - If it exists only in this project → leave it (project-specific command).

## Phase 4: Update Skills

8. Compare each skill directory in cc-rpi `templates/skills/` against this project's `.claude/skills/`:
   - For each skill in the blueprint:
     - If it exists in both locations and the cc-rpi SKILL.md is different -> replace the project's SKILL.md.
     - If it exists in cc-rpi but not in this project -> create the directory and copy SKILL.md (new skill from blueprint).
     - If it exists only in this project -> leave it (project-specific skill).
   - Blueprint skills: `git-workflow/`, `multi-agent/`, `deployment-safety/`, `ci-workflow/`, `github-cli/`, `error-patterns/`, `python-rules/`, `macos-rules/`, `supabase/`
   - Skip stack-irrelevant skills: if this is not a Python project, skip `python-rules/`. If not using Supabase, skip `supabase/`. If not on macOS, skip `macos-rules/`.

## Phase 4b: Update Rules

9. Compare each file in cc-rpi `templates/rules/` against this project's `.claude/rules/`:
   - Blueprint rules: `rpi-details.md`, `push-accountability.md`, `deployment-safety.md`, `supabase.md`, `testing.md`
   - For each blueprint rule:
     - If it exists in both and the cc-rpi version is different → update the content but **preserve custom `paths`** the project may have adapted.
     - If it exists in cc-rpi but not in this project → add it (new rule from blueprint). Adapt `paths` to match project structure.
     - If it exists only in this project → leave it (project-specific rule).
   - Skip stack-irrelevant rules: if not using Supabase, skip `supabase.md`. If no test framework, skip `testing.md`. If no deployment pipeline, skip `deployment-safety.md`.
   - **Never delete** project-added custom rule files.

## Phase 4c: Update AGENTS.md

10. Read this project's `AGENTS.md` if it exists.
11. Read cc-rpi's `templates/AGENTS.md.template`.
12. If `AGENTS.md` does not exist, create it from the template.
13. If it exists:
    - Update the compatibility sections so Codex still points at
      `CLAUDE.md`, `.claude/commands/`, `.claude/rules/`, and
      `.claude/skills/`
    - Preserve project-specific sections such as stack notes or custom
      Codex guidance
    - If the file has been heavily customized beyond recognition, skip
      and report: "skipped — heavily customized"

## Phase 5: Update CLAUDE.md

14. Read this project's CLAUDE.md fully.
15. Read cc-rpi's `templates/CLAUDE.md.template`.
16. Identify **blueprint-managed sections** by their headers. These sections come from the template and should be kept in sync:
    - `## RPI Workflow`
    - `## Agent Behavior` (was `## Agent Autonomy` + `## Memory` in older templates)
    - `## Project File Locations`
    - If the project has older sections now moved to `.claude/rules/` (`## Working Patterns`, `## TDD Protocol`, `## Push Accountability`, `<important if>` blocks), remove them and ensure the corresponding rule file exists in `.claude/rules/`.
17. For each blueprint-managed section:
    - If the project's version differs from the template → update to match.
    - If the project has added project-specific content *within* a blueprint section (e.g., extra rules), preserve it — only update the parts that came from the template.
    - If a section doesn't exist in the project → **add it** from the template. Place it after the last existing blueprint-managed section, preserving the order from the template. New blueprint sections are new knowledge — `/update` is responsible for delivering them.
18. **Do NOT touch** project-specific sections: One-liner, Stack, Key Commands, Git Workflow, Deployment, Commit Messages, Research Documents, Implementation Plans, or any custom section.
19. If CLAUDE.md still contains `<important if>` blocks, migrate them to `.claude/rules/` files with `paths` frontmatter and remove the blocks from CLAUDE.md.
20. The verification sequencing rule ("Run verification sequentially with `;` or `&&`") should be a one-liner in the Git Workflow section, not a separate subsection.

## Phase 6: Update settings.json

21. Read this project's `.claude/settings.json`.
22. Compare against cc-rpi's `templates/settings.json.template`.
23. Add any new `permissions.allow` entries from the template that are missing in the project.
24. Add any new `env` entries from the template that are missing.
25. **Never remove** project-specific permissions, env vars, hooks, or deny rules.

## Phase 7: Write Sync Metadata

26. Get the current HEAD commit hash of cc-rpi: `git -C <cc-rpi-path> rev-parse HEAD`
27. Get the current version tag: `git -C <cc-rpi-path> describe --tags --abbrev=0 2>/dev/null`
28. Write/update `.claude/cc-rpi-sync.json`:
    ```json
    {
      "lastSyncCommit": "<commit-hash>",
      "lastSyncDate": "YYYY-MM-DD",
      "blueprintVersion": "<version-tag>",
      "agentsTemplateSynced": true,
      "rulesSynced": ["rpi-details.md", "push-accountability.md"],
      "rulesCustom": []
    }
    ```

## Phase 8: Report and Commit

29. If any project files were changed (commands, skills, rules, AGENTS.md, CLAUDE.md, settings.json):
    - Stage only the changed files (not unrelated changes).
    - Commit with: `chore: sync with cc-rpi blueprint <version-tag>`
    - Always update the sync metadata even if no other files changed.

30. Present a summary:
    - cc-rpi version synced to (tag + commit hash)
    - Commands updated/added (list them)
    - Skills updated/added (list them)
    - Rules updated/added (list them)
    - AGENTS.md updated/added (state whether Codex compatibility was installed or synced)
    - CLAUDE.md sections updated/added (list them)
    - settings.json changes (list them)
    - Notable new content: new error patterns, new rules, methodology changes
    - "Already up to date" if nothing changed

## Rules

- **Never delete project content.** Only add or update blueprint-managed sections.
- **Preserve project identity.** Stack, deployment, key commands, commit conventions — these are the project's own.
- **Preserve Codex compatibility.** `AGENTS.md` is part of the blueprint-managed compatibility layer.
- **Be idempotent.** Running twice with no cc-rpi changes should produce zero file changes.
- **Commit atomically.** All sync changes go in one commit with the sync metadata.
- **If unsure, skip and report.** When a section has been heavily customized beyond the template, leave it alone and note it in the report as "skipped — heavily customized."
- **No interactive prompts.** This command must work headlessly for scheduled agents. Don't ask for confirmation — just apply safe updates and report what you did.
