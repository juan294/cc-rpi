# Workflow: Bootstrapping a New Project

A step-by-step walkthrough of setting up a new project from scratch using the cc-rpi blueprint. This example uses a Node.js REST API, but the workflow is the same for any stack.

---

## Prerequisites

- Claude Code CLI installed
- cc-rpi cloned on your machine
- `/bootstrap` and `/adopt` commands installed in `~/.claude/commands/` (see [GUIDE.md](../../GUIDE.md))

---

## Step 1: Create the repo and open Claude Code

```bash
mkdir my-api && cd my-api
git init
claude
```

You now have an empty repo with Claude Code open.

---

## Step 2: Run /bootstrap

```
You: /bootstrap
```

The agent reads the entire cc-rpi blueprint (methodology, error patterns, operational rules, templates) and then asks you about your project:

```
Claude: I've read the cc-rpi blueprint. A few questions before I set things up:

1. What type of project is this? (web app, library, CLI tool, monorepo, Python, static site)
2. What's your stack? (e.g., Node.js + Express + TypeScript, Python + FastAPI)
3. Any conventions I should know? (naming, folder structure preferences, test framework)
```

```
You: It's a web app. Node.js, Express, TypeScript. Jest for testing. Standard src/ folder structure.
```

The agent then creates everything:

```
Claude: Setting up your project. Here's what I'm creating:

- CLAUDE.md — project configuration with all operational rules
- .claude/settings.json — permissions, Agent Teams, hooks
- .claude/commands/ — all 6 slash commands (research, plan, implement, validate, describe-pr, pre-launch)
- package.json with TypeScript, Jest, ESLint, Prettier
- tsconfig.json
- .github/workflows/ci.yml
- Pre-commit hooks via Husky + lint-staged
- docs/ directory structure (research, plans, decisions)
- src/ with a minimal Express server
- Initial test setup

Should I proceed?
```

```
You: Yes, go ahead.
```

The agent creates all files, installs dependencies, runs the initial typecheck and tests to verify everything works, then makes the initial commit.

```
Claude: Done. Your project is set up:

- All checks pass (typecheck, lint, tests)
- Initial commit created
- 6 slash commands ready to use

You can start with /research to explore any existing patterns,
or /plan to design your first feature.
```

---

## Step 3: Your first feature — designing the API

Now you want to add your first real feature. Since this is a fresh project, research is light — there's not much code to explore yet. You can go straight to planning:

```
You: /plan create a REST API for managing a todo list with CRUD endpoints,
     PostgreSQL storage, and input validation
```

The agent enters planning mode:

```
Claude: I'll design this feature. Let me explore what /bootstrap set up...

[reads CLAUDE.md, src/ structure, existing config]

Before I write the plan, a few questions:

1. Do you want an ORM (Prisma, TypeORM) or raw SQL queries?
2. Authentication — skip for now or include from the start?
3. Should I set up database migrations?
```

```
You: Prisma. No auth for now, we'll add it later. Yes on migrations.
```

The agent writes the plan:

```
Claude: Plan saved to docs/plans/2026-02-22-todo-api.md

3 phases:
- Phase 1: Database schema + Prisma setup + migrations
- Phase 2: CRUD endpoints with input validation (zod)
- Phase 3: Error handling middleware + integration tests

Each phase has specific success criteria. Ready to review?
```

**This is where you stop and read the plan.** Open `docs/plans/2026-02-22-todo-api.md`, review the pseudocode for each phase, check the file changes, verify the success criteria make sense. This is your highest-leverage review — catching a wrong assumption here saves hours.

```
You: Looks good. Phase 2 — use express-validator instead of zod, I prefer it
     for Express projects. Otherwise approved.
```

```
Claude: Updated the plan. express-validator replaces zod in Phase 2.
```

---

## Step 4: Implement phase by phase

```
You: /implement docs/plans/2026-02-22-todo-api.md
```

The agent reads the plan and starts with Phase 1 only:

```
Claude: Starting Phase 1: Database schema + Prisma setup

[installs prisma, creates schema, runs migration, writes seed script]
[reviewer: plan compliance PASS]
[/simplify: clean]
[runs typecheck, lint, tests]

Phase 1 complete. All checks pass:
- [x] Prisma schema created with Todo model
- [x] Migration applied successfully
- [x] Seed script works
- [x] TypeScript compiles
- [x] Tests pass (3 new tests for database connection and model)

Ready for Phase 2?
```

You verify — maybe run the seed script yourself, check the migration looks right.

```
You: Good, continue.
```

```
Claude: Starting Phase 2: CRUD endpoints with input validation

[creates routes, controllers, validation middleware]
[reviewer: plan compliance PASS]
[/simplify: extracted duplicated validation pattern into shared helper. Fixed.]
[runs typecheck, lint, tests]

Phase 2 complete. All checks pass:
- [x] GET /todos, GET /todos/:id, POST /todos, PUT /todos/:id, DELETE /todos/:id
- [x] Input validation with express-validator
- [x] /simplify: 1 fix applied (validation pattern reuse)
- [x] 12 new tests (endpoint + validation)

Ready for Phase 3?
```

```
You: Continue.
```

```
Claude: Starting Phase 3: Error handling + integration tests

[creates error middleware, adds integration tests with supertest]
[reviewer: plan compliance PASS]
[/simplify: clean]
[runs full test suite]

Phase 3 complete. All checks pass:
- [x] Centralized error handling middleware
- [x] 8 integration tests covering happy paths and error cases
- [x] Full suite: 23 tests, all passing
- [x] TypeScript compiles, lint clean

All phases complete.
```

---

## Step 5: Validate

```
You: /validate docs/plans/2026-02-22-todo-api.md
```

```
Claude: Running validation against the plan...

- [x] Phase 1: All success criteria met
- [x] Phase 2: All success criteria met
- [x] Phase 3: All success criteria met
- [x] TypeScript: No errors
- [x] Lint: Clean
- [x] Tests: 23/23 passing
- [x] No TODO/FIXME markers left in code

Verdict: All plan objectives achieved. Ready for PR.
```

---

## Step 6: Create the PR

```
You: /describe-pr
```

```
Claude: PR description generated. Creating PR...

→ https://github.com/yourname/my-api/pull/1
```

---

## What just happened

You went from an empty directory to a production-structured API in one session:

1. `/bootstrap` — set up the entire project infrastructure in one command
2. `/plan` — designed the feature with your input on key decisions
3. `/implement` — built it phase by phase, with you approving each phase
4. `/validate` — verified everything against the original plan
5. `/describe-pr` — opened a PR with auto-generated description

The agent did the heavy lifting. You made the strategic decisions (Prisma over TypeORM, express-validator over zod, no auth yet) and reviewed at the phase boundaries where your attention had the highest leverage.
