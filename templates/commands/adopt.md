# Adopt cc-rpi Best Practices into Existing Project

Model tier: **sonnet** — Sonnet 5 (1M context) session.

You are auditing and migrating an existing project to follow the cc-rpi blueprint. The blueprint lives at `<path-to-your-cc-rpi-clone>/`.

This project already exists and may already follow some, all, or none of these practices. Your job is to assess what's in place, identify gaps, and create a migration plan — NOT to blindly overwrite what's already working.

## Phase 1: Learn the Rules

Read these files from cc-rpi IN ORDER. Do not skip any.

1. `patterns/quick-reference.md` — The INDEX of operational rules: one line per rule naming the skill, rule file, or command that holds its body. Read it to learn what exists and where it lives, not to memorize rule text.
2. `methodology/README.md` — Read the one-paragraph summary and reading order.

The error-patterns skill provides condensed error reference on demand.
The full catalog (`patterns/agent-errors.md`) is available when the
audit uncovers a debugging pattern that needs deeper detail, but it is
not required for onboarding.
3. `templates/setup-checklist.md` — Understand the target state for a fully set up project.
4. `templates/CLAUDE.md.template` — Know what a well-configured CLAUDE.md looks like.
5. `templates/AGENTS.md.template` — Know what the Codex compatibility layer should contain.
6. `templates/settings.json.template` — Know what settings.json should contain.

## Phase 2: Audit This Project

Now investigate THIS project. Spawn parallel Explore agents to assess the current state:

**Agent 1 — Configuration Audit:**
- Does CLAUDE.md exist? If so, read it fully. How complete is it vs the template?
- Does AGENTS.md exist? If so, read it fully. Does it bridge Codex to the existing `.claude/*` structure?
- Does `.claude/settings.json` exist? What permissions and env vars are configured?
- Does `.claude/commands/` exist? Which slash commands are present?
- Does `.claude/skills/` exist? Which skills are installed?
- Does `.claude/rules/` exist? Which rules are installed? (New in blueprint v2)
- Does `.claude/agents/` exist?
- Is `.claude/settings.local.json` in `.gitignore`?
- Does CLAUDE.md contain `<important if>` blocks? (These should migrate to `.claude/rules/`)

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
- Missing or incomplete AGENTS.md Codex compatibility layer
- No slash commands for /research, /plan, /implement, /validate
- No settings.json or Agent Teams not enabled
- No docs/ directory structure
- Missing `.claude/skills/` or missing blueprint-provided skills
- Missing `.claude/rules/` (conditional and modular rules)
- CLAUDE.md contains `<important if>` blocks (should be `.claude/rules/` with `paths`)

**MEDIUM — Quality infrastructure (improves reliability):**
- No pre-commit hooks
- No CI or incomplete CI
- No push accountability workflow
- README doesn't follow standard header
- `.claude/settings.local.json` not gitignored

**LOW — Advanced features (nice to have):**
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
2. AGENTS.md (makes the same workflow operable in Codex)
3. settings.json + Agent Teams (affects Claude agent capabilities)
4. Slash commands (affects daily workflow)
5. docs/ directory structure (affects research/plan storage)
6. Pre-commit hooks and CI (affects quality enforcement)
7. Release verification (E2E Pro) — Wave A truthful-gate first, structural waves by risk
8. Logging, scheduled agents (polish)

## Phase 4: Get Approval and Execute

After presenting the report:

1. **Ask the user** which items they want to adopt and which they want to skip or defer.
2. **Ask about conflicts** — if the project has conventions that differ from the blueprint, ask which to keep.
3. **Create a migration plan** as a checklist based on their decisions.
4. **Execute the plan item by item**, confirming after each major change.
5. **Create or update `AGENTS.md`** — adapt from `cc-rpi/templates/AGENTS.md.template`:
   - Point Codex at `CLAUDE.md`, `.claude/commands/`, `.claude/rules/`, and `.claude/skills/`
   - Preserve any project-specific Codex notes already present
   - Unless the user explicitly opts out, always make the adopted project Codex compatible
   - If the user says "make this Codex compatible", treat that as explicit approval to create or repair this layer
6. **Install `.claude/rules/`** — copy rule templates from `cc-rpi/templates/rules/`:
   - Always: `rpi-details.md`, `push-accountability.md`
   - If deployment pipeline: `deployment-safety.md`
   - If Supabase: `supabase.md`
   - If tests: `testing.md`
   - Adapt `paths` in frontmatter to match the project's file structure.
7. **Migrate `<important if>` blocks** — if the project's CLAUDE.md has `<important if>` blocks:
   - Extract each block's content
   - Create a `.claude/rules/` file with `paths` frontmatter
   - Remove the block from CLAUDE.md
   - Verify path globs match the project's actual files
8. **Install release verification (E2E Pro)** — copy
   `cc-rpi/templates/e2e-pro-playbook-template.md` into the project (e.g.
   `docs/release/e2e-pro-playbook.md`) and complete its Project Adaptation Profile
   with verified values. Adopt **Wave A always** (the truthful release gate that
   `/release` can then enforce); adopt Waves C–H by project risk, deleting
   inapplicable sections and recording why. Install `/explore-release` (Wave B) once
   a deployed candidate exists to test.

## Phase 5: Save to Memory

After completing the migration:

1. Save the following to auto memory so future sessions start with full awareness:
    - Project name, type, and stack
    - What was already in place vs what was migrated
    - Key decisions made during adoption (what the user chose to keep, skip, or adapt)
    - Any project-specific conventions or constraints discovered during the audit
    - CI/CD pipeline behavior, deployment targets, environment quirks
    - Whether the project is now Codex compatible via `AGENTS.md`
    - The operational rules and error patterns you internalized from Phase 1

This ensures the next session doesn't start from zero — the agent already knows the project context, the rules, and the migration decisions.

## Recommended Next Step

After adoption is complete, suggest the user run `/pre-launch` in a new session to baseline their codebase quality. `/pre-launch` spawns 8 specialist agents (Principal Architect, Staff FE, Staff BE, Performance Engineer, DevOps/SRE Lead, Security Reviewer, QA/Reliability Lead, Product Designer/UX Lead) that audit the entire codebase and produce a launch-readiness report.

For code quality findings (dead code, duplicates, inefficiencies), `/simplify` handles the bulk of fixes automatically. Security, infrastructure, and accessibility findings require manual implementation or a targeted `/implement` cycle.

This is optional but recommended — it gives adopters a clear picture of their codebase health under the new methodology.

## Rules for This Process

- **Audit first, change nothing.** Phase 2 and 3 are entirely read-only. No files are modified until the user approves the plan.
- **Respect what exists.** This project has history. Don't overwrite working configurations without asking.
- **Merge, don't replace.** If CLAUDE.md already exists with useful content, add the missing pieces — don't replace the whole file.
- **Keep the methodology portable.** Unless the user opts out, add the Codex compatibility layer via `AGENTS.md`.
- **Preserve project identity.** The project's name, description, stack choices, and conventions are theirs. The blueprint provides structure, not opinions about technology choices.
- **Ask before assuming.** When in doubt about whether to change something, ask.
- **Keep CLAUDE.md lean.** Target ~70 lines. Domain rules go in `.claude/rules/` and `.claude/skills/`, not CLAUDE.md.
- **One thing at a time.** Don't batch all changes into one massive commit. Make logical, reviewable changes.
- **Always save to memory.** Phase 5 is not optional. Every adoption must end with a memory save.
