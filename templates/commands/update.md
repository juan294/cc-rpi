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
5. `methodology/README.md` — Methodology overview.

The error-patterns skill provides condensed error reference on demand. The full catalog (`patterns/agent-errors.md`) is available on incremental syncs when error patterns changed in the diff.

On incremental syncs (lastSyncCommit exists), prioritize reading files that appear in the git diff. You can skip unchanged methodology files.

## Phase 3: Update Slash Commands

7. Compare each file in cc-rpi `templates/commands/` against this project's `.claude/commands/`:
   - **Skip** `bootstrap.md`, `adopt.md`, and `update.md` — these are user-level commands, not project-level.
   - For each remaining command (research, plan, implement, validate, describe-pr, pre-launch):
     - If it exists in both locations and the cc-rpi version is different → replace the project version.
     - If it exists in cc-rpi but not in this project → add it.
     - If it exists only in this project → leave it (project-specific command).
   - If command-bundle behavior is unclear, use `templates/commands/INSTALL.md`
     and `templates/commands/VERIFY.md` as the local bundle reference.

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

## Phase 4c: Update AGENTS.md and OpenCode Layer

10. Read this project's `AGENTS.md` if it exists.
11. Read cc-rpi's `templates/AGENTS.md.template`.
12. Read this project's `opencode.json` if it exists.
13. Read any files in this project's `.opencode/commands/` if they exist.
14. Read cc-rpi's `templates/opencode.json.template`.
15. Read the wrapper command files in `cc-rpi/templates/opencode/commands/`.
16. If `AGENTS.md` does not exist, create it from the template.
17. If it exists:
    - Update the compatibility sections so Codex still points at
      `CLAUDE.md`, `.claude/commands/`, `.claude/rules/`, and
      `.claude/skills/`, and OpenCode still points at the same sources
    - Preserve project-specific sections such as stack notes or custom
      compatibility guidance
    - If the file has been heavily customized beyond recognition, skip
      and report: "skipped — heavily customized"
18. If `opencode.json` does not exist, create it from the template.
19. If it exists, ensure it still loads `CLAUDE.md` and `.claude/rules/*.md` while preserving project-specific OpenCode config.
20. Compare each file in `cc-rpi/templates/opencode/commands/` against this project's `.opencode/commands/`:
    - If it exists in both and the cc-rpi version is different → replace the project version.
    - If it exists in cc-rpi but not in this project → add it.
    - If it exists only in this project → leave it (project-specific wrapper).

For scheduled-agent sync work, use
`templates/scripts/agents/INSTALL.md` and
`templates/scripts/agents/VERIFY.md` as the local reference for what
the reusable bundle is expected to provide.

## Phase 5: Update CLAUDE.md

21. Read this project's CLAUDE.md fully.
22. Read cc-rpi's `templates/CLAUDE.md.template`.
23. Identify **blueprint-managed sections** by their headers. These sections come from the template and should be kept in sync:
    - `## RPI Workflow`
    - `## Agent Behavior` (was `## Agent Autonomy` + `## Memory` in older templates)
    - `## Project File Locations`
    - If the project has older sections now moved to `.claude/rules/` (`## Working Patterns`, `## TDD Protocol`, `## Push Accountability`, `<important if>` blocks), remove them and ensure the corresponding rule file exists in `.claude/rules/`.
24. For each blueprint-managed section:
    - If the project's version differs from the template → update to match.
    - If the project has added project-specific content *within* a blueprint section (e.g., extra rules), preserve it — only update the parts that came from the template.
    - If a section doesn't exist in the project → **add it** from the template. Place it after the last existing blueprint-managed section, preserving the order from the template. New blueprint sections are new knowledge — `/update` is responsible for delivering them.
25. **Do NOT touch** project-specific sections: One-liner, Stack, Key Commands, Git Workflow, Deployment, Commit Messages, Research Documents, Implementation Plans, or any custom section.
26. If CLAUDE.md still contains `<important if>` blocks, migrate them to `.claude/rules/` files with `paths` frontmatter and remove the blocks from CLAUDE.md.
27. The verification sequencing rule ("Run verification sequentially with `;` or `&&`") should be a one-liner in the Git Workflow section, not a separate subsection.

## Phase 6: Update settings.json

28. Read this project's `.claude/settings.json`.
29. Compare against cc-rpi's `templates/settings.json.template`.
30. Add any new `permissions.allow` entries from the template that are missing in the project.
31. Add any new `env` entries from the template that are missing.
32. **Never remove** project-specific permissions, env vars, hooks, or deny rules.

## Phase 7: Write Sync Metadata

33. Get the current HEAD commit hash of cc-rpi: `git -C <cc-rpi-path> rev-parse HEAD`
34. Get the current version tag: `git -C <cc-rpi-path> describe --tags --abbrev=0 2>/dev/null`
35. Write/update `.claude/cc-rpi-sync.json`:
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

36. If any project files were changed (commands, wrapper commands, skills, rules, AGENTS.md, opencode.json, CLAUDE.md, settings.json):
    - Stage only the changed files (not unrelated changes).
    - Commit with: `chore: sync with cc-rpi blueprint <version-tag>`
    - Always update the sync metadata even if no other files changed.

37. Present a summary:
    - cc-rpi version synced to (tag + commit hash)
    - Commands updated/added (list them)
    - Skills updated/added (list them)
    - Rules updated/added (list them)
    - AGENTS.md updated/added (state whether Codex/OpenCode compatibility was installed or synced)
    - opencode.json updated/added and wrapper commands updated/added
    - CLAUDE.md sections updated/added (list them)
    - settings.json changes (list them)
    - Notable new content: new error patterns, new rules, methodology changes
    - "Already up to date" if nothing changed

## Rules

- **Never delete project content.** Only add or update blueprint-managed sections.
- **Preserve project identity.** Stack, deployment, key commands, commit conventions — these are the project's own.
- **Preserve Codex/OpenCode compatibility.** `AGENTS.md`, `opencode.json`, and `.opencode/commands/` are part of the blueprint-managed compatibility layer.
- **Be idempotent.** Running twice with no cc-rpi changes should produce zero file changes.
- **Commit atomically.** All sync changes go in one commit with the sync metadata.
- **If unsure, skip and report.** When a section has been heavily customized beyond the template, leave it alone and note it in the report as "skipped — heavily customized."
- **No interactive prompts.** This command must work headlessly for scheduled agents. Don't ask for confirmation — just apply safe updates and report what you did.
