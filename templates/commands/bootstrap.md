# Bootstrap New Project from cc-rpi Blueprint

You are setting up a new project using Juan's cc-rpi blueprint repository. The blueprint lives at `/Users/juan/Documents/GenAI_Projects/cc-rpi/`.

## Phase 1: Learn the Rules

Read these files from cc-rpi IN ORDER. Do not skip any.

1. `patterns/quick-reference.md` — Internalize every operational rule. These apply to ALL your work from now on.
2. `patterns/agent-errors.md` — Know every error pattern and its solution. Never rediscover these.
3. `methodology/README.md` — Read the one-paragraph summary and the reading order. You do NOT need to read every methodology file right now — you'll reference them as needed during actual work.

## Phase 2: Understand the Templates

Read these files to understand what you'll be creating:

4. `templates/setup-checklist.md` — This is your step-by-step guide. You'll execute it in Phase 3.
5. `templates/CLAUDE.md.template` — The starting point for this project's CLAUDE.md.
6. `templates/settings.json.template` — The starting point for .claude/settings.json.
7. `templates/README-header.md` — The standard README header structure.

## Phase 3: Set Up This Project

Now execute the setup checklist against THIS project. Work through it section by section:

1. **Ask me** what type of project this is (web app, library, CLI, monorepo, Python, static site) so you can adapt accordingly.
2. **Ask me** for the project name, description, stack, and any specifics you need to fill in the templates.
3. Create the CLAUDE.md — adapt from the template, manually crafting every line for this project's needs.
4. Create `.claude/settings.json` — adapt from the template.
5. Create `.claude/commands/` — copy slash commands from `cc-rpi/templates/commands/` and adjust file paths.
6. Create the directory structure (`docs/research/`, `docs/plans/`, `docs/decisions/`).
7. Set up the README with the standard header.
8. Add `.claude/settings.local.json` to `.gitignore`.
9. Walk through the remaining checklist items (pre-commit hooks, CI, git setup) — ask me for decisions where needed.

## Rules for This Process

- **Ask before assuming.** Every project is different. Don't guess the stack, conventions, or workflow.
- **Adapt, don't copy.** The templates are starting points. Tailor everything to this specific project.
- **Keep CLAUDE.md lean.** Only include instructions that would cause mistakes if missing. If Claude can infer it from code, don't add it.
- **Don't read methodology files unless needed.** You have the rules and error patterns memorized from Phase 1. Reference methodology files only when you need depth on a specific topic during setup.
