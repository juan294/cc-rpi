# Adopt cc-rpi Best Practices into Existing Project

You are auditing and migrating an existing project to follow the cc-rpi blueprint. The blueprint lives at `<path-to-your-cc-rpi-clone>/`.

This project already exists and may already follow some, all, or none of these practices. Your job is to assess what's in place, identify gaps, and create a migration plan — NOT to blindly overwrite what's already working.

## Phase 1: Learn the Rules

Read these files from cc-rpi IN ORDER. Do not skip any.

1. `patterns/quick-reference.md` — Internalize every operational rule.
2. `patterns/agent-errors.md` — Know every error pattern and its solution.
3. `methodology/README.md` — Read the one-paragraph summary and reading order.
4. `templates/setup-checklist.md` — Understand the target state for a fully set up project.
5. `templates/CLAUDE.md.template` — Know what a well-configured CLAUDE.md looks like.
6. `templates/settings.json.template` — Know what settings.json should contain.

## Phase 2: Audit This Project

Now investigate THIS project. Spawn parallel Explore agents to assess the current state:

**Agent 1 — Configuration Audit:**
- Does CLAUDE.md exist? If so, read it fully. How complete is it vs the template?
- Does `.claude/settings.json` exist? What permissions and env vars are configured?
- Does `.claude/commands/` exist? Which slash commands are present?
- Does `.claude/skills/` exist?
- Does `.claude/agents/` exist?
- Is `.claude/settings.local.json` in `.gitignore`?

**Agent 2 — Infrastructure Audit:**
- What's the project type? (web app, library, CLI, monorepo, Python, static site)
- What's the stack? (language, framework, package manager, test runner, linter)
- Are pre-commit hooks set up? What do they run?
- Is there CI? What does it check?
- What's the git workflow? (branches, protection rules)
- Does the README follow the standard header format?

**Agent 3 — Workflow Audit:**
- Does `docs/` exist? What's the directory structure?
- Are there research documents, plans, or decision records?
- Is there an error/success logging structure?
- Are there any existing slash commands? What do they do?
- How is testing set up? (test runner, coverage, TDD patterns)

Wait for all agents to complete, then synthesize their findings.

## Phase 3: Present the Audit Report

Present a structured report to the user with these sections:

### What's Already In Place
List everything that already aligns with cc-rpi practices. Give credit — don't suggest changing things that work.

### What's Missing
List gaps organized by priority:

**HIGH — Core workflow (blocks effective RPI usage):**
- Missing or incomplete CLAUDE.md
- No slash commands for /research, /plan, /implement, /validate
- No settings.json or Agent Teams not enabled
- No docs/ directory structure

**MEDIUM — Quality infrastructure (improves reliability):**
- No pre-commit hooks
- No CI or incomplete CI
- No push accountability workflow
- README doesn't follow standard header
- `.claude/settings.local.json` not gitignored

**LOW — Advanced features (nice to have):**
- No skills directory
- No custom agent definitions
- No scheduled agents
- No error/success logging structure

### What Needs Adaptation (Not Replacement)
List things that exist but differ from the blueprint. For each, explain the gap and ask whether the user wants to adapt it or keep their current approach. Examples:
- CLAUDE.md exists but is missing operational rules
- CI exists but doesn't run typecheck
- Pre-commit hooks exist but only run lint (no typecheck)
- Slash commands exist but use different conventions

### Recommended Migration Order
Propose a phased order for the migration. Always start with the highest-leverage items:
1. CLAUDE.md (affects every session)
2. settings.json + Agent Teams (affects agent capabilities)
3. Slash commands (affects daily workflow)
4. docs/ directory structure (affects research/plan storage)
5. Pre-commit hooks and CI (affects quality enforcement)
6. README header, logging, scheduled agents (polish)

## Phase 4: Get Approval and Execute

After presenting the report:

1. **Ask the user** which items they want to adopt and which they want to skip or defer.
2. **Ask about conflicts** — if the project has conventions that differ from the blueprint, ask which to keep.
3. **Create a migration plan** as a checklist based on their decisions.
4. **Execute the plan item by item**, confirming after each major change.

## Phase 5: Save to Memory

After completing the migration:

5. Save the following to auto memory so future sessions start with full awareness:
    - Project name, type, and stack
    - What was already in place vs what was migrated
    - Key decisions made during adoption (what the user chose to keep, skip, or adapt)
    - Any project-specific conventions or constraints discovered during the audit
    - CI/CD pipeline behavior, deployment targets, environment quirks
    - The operational rules and error patterns you internalized from Phase 1

This ensures the next session doesn't start from zero — the agent already knows the project context, the rules, and the migration decisions.

## Rules for This Process

- **Audit first, change nothing.** Phase 2 and 3 are entirely read-only. No files are modified until the user approves the plan.
- **Respect what exists.** This project has history. Don't overwrite working configurations without asking.
- **Merge, don't replace.** If CLAUDE.md already exists with useful content, add the missing pieces — don't replace the whole file.
- **Preserve project identity.** The project's name, description, stack choices, and conventions are theirs. The blueprint provides structure, not opinions about technology choices.
- **Ask before assuming.** When in doubt about whether to change something, ask.
- **Keep CLAUDE.md lean.** When updating it, only add instructions that would cause mistakes if missing.
- **One thing at a time.** Don't batch all changes into one massive commit. Make logical, reviewable changes.
- **Always save to memory.** Phase 5 is not optional. Every adoption must end with a memory save.
