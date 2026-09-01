# Bootstrap New Project from cc-rpi Blueprint

Model tier: **sonnet** — Sonnet 5 (1M context) session.

You are setting up a new project using the cc-rpi blueprint repository. The blueprint lives at `<path-to-your-cc-rpi-clone>/`.

## Phase 1: Learn the Rules

Read these files from cc-rpi IN ORDER. Do not skip any.

1. `patterns/quick-reference.md` — The INDEX of operational rules, one line each, naming the skill, rule file, or command that holds the rule body. Read it to learn what rules exist and where they live; you do not need to memorize them, because each body loads at its point of use once the skills and rules are installed.
2. `methodology/README.md` — Read the one-paragraph summary and the reading order. You do NOT need to read every methodology file right now — you'll reference them as needed during actual work.

The error-patterns skill provides condensed error reference on demand
during debugging. The full 64-error catalog
(`patterns/agent-errors.md`) is available but not required for
onboarding.

## Phase 2: Understand the Templates

Read these files to understand what you'll be creating:

3. `templates/setup-checklist.md` — This is your step-by-step guide. You'll execute it in Phase 3.
4. `templates/CLAUDE.md.template` — The starting point for this project's CLAUDE.md.
5. `templates/AGENTS.md.template` — The Codex compatibility layer for this project's AGENTS.md.
6. `templates/settings.json.template` — The starting point for .claude/settings.json.

## Phase 3: Set Up This Project

Now execute the setup checklist against THIS project. Work through it section by section:

1. **Ask me** what type of project this is (web app, library, CLI, monorepo, Python, static site) so you can adapt accordingly.
2. **Ask me** whether this project will expose tools to an AI agent (WebMCP tools in a web UI, or an MCP server) -- any project type can, so ask regardless of the answer to question 1.
3. **Ask me** for the project name, description, stack, and any specifics you need to fill in the templates.
4. Create the CLAUDE.md — adapt from the template, manually crafting every line for this project's needs.
5. Create the AGENTS.md — adapt from the template so Codex can follow this project's cc-rpi setup too.
6. Create `.claude/settings.json` — adapt from the template.
7. Create `.claude/commands/` — copy slash commands from `cc-rpi/templates/commands/` and adjust file paths.
8. Install skills from `cc-rpi/templates/skills/` to `.claude/skills/`:
   - Always install: `shell-tools/`, `git-workflow/`, `multi-agent/`, `deployment-safety/`, `ci-workflow/`, `github-cli/`, `error-patterns/`, `systematic-debugging/`
   - If Python project: also install `python-rules/`
   - If macOS development: also install `macos-rules/`
   - If using Supabase: also install `supabase/`
   - If the project exposes tools to an agent: also install `webmcp/`
   - Each skill is a directory with a SKILL.md file -- copy the entire directory.
9. Install rules from `cc-rpi/templates/rules/` to `.claude/rules/`:
   - Always copy: `rpi-details.md`, `push-accountability.md`
   - If deployment pipeline exists: copy `deployment-safety.md`
   - If using Supabase: copy `supabase.md`
   - If test framework detected: copy `testing.md`
   - If the project exposes tools to an agent: copy `webmcp.md`
   - Adapt `paths` in frontmatter to match the project's actual file structure.
10. Create the directory structure (`docs/research/`, `docs/plans/`, `docs/decisions/`).
11. Install release verification (E2E Pro) — copy `cc-rpi/templates/e2e-pro-playbook-template.md` into the project (e.g. `docs/release/e2e-pro-playbook.md`) and complete its Project Adaptation Profile with verified values. Adopt **Wave A always** (the truthful release gate); adopt Waves C–H by project risk. See the setup checklist's "Release Verification (E2E Pro)" section.
12. Set up the README with the standard header.
13. Add `.claude/settings.local.json` to `.gitignore`. If scheduled agents will be used, also check repo visibility with `gh repo view --json visibility --jq '.visibility'`: on `PUBLIC` (or no remote), add `docs/agents/`, `logs/`, and `scripts/agents/` to `.gitignore` (Rule #70); on `PRIVATE`/`INTERNAL`, leave them tracked.
14. Walk through the remaining checklist items (pre-commit hooks, CI, git setup) — ask me for decisions where needed.
15. Unless the user explicitly opts out, always make the project Codex compatible by creating `AGENTS.md`.
16. If the user says "make this Codex compatible", treat that as an explicit instruction to create or update `AGENTS.md` and verify the Codex compatibility layer is complete.

## Phase 4: Save to Memory

After completing all setup:

1. Save the following to auto memory so future sessions start with full awareness:
    - Project name, type, and stack
    - Key decisions made during setup (git workflow, CI choices, deployment targets)
    - Any project-specific conventions or constraints the user mentioned
    - Which optional features were adopted vs skipped
    - That the project is Codex compatible via `AGENTS.md`
    - The operational rules and error patterns you internalized from Phase 1

This ensures the next session doesn't start from zero — the agent already knows the project context, the rules, and the decisions that shaped the setup.

## Recommended Next Step

After bootstrap is complete, your project has structure but no code yet.
For your first feature, skip /research and start directly with /plan:

```text
/plan [your first feature]
```

There is nothing to research in an empty project. Once your first
implementation produces code, /research becomes your starting point
for every subsequent task.

## Rules for This Process

- **Ask before assuming.** Every project is different. Don't guess the stack, conventions, or workflow.
- **Adapt, don't copy.** The templates are starting points. Tailor everything to this specific project.
- **Keep CLAUDE.md lean.** Only include instructions that would cause mistakes if missing. If Claude can infer it from code, don't add it.
- **Create Codex compatibility by default.** Install `AGENTS.md` unless the user explicitly opts out.
- **Don't read methodology files unless needed.** You have the rules and error patterns memorized from Phase 1. Reference methodology files only when you need depth on a specific topic during setup.
- **Always save to memory.** Phase 4 is not optional. Every bootstrap must end with a memory save.
