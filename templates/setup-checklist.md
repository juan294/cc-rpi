# New Project Setup Checklist

Use this when setting up a new project to follow cc-rpi best practices.

## Directory Setup

- [ ] Create `CLAUDE.md` at project root (adapt from `CLAUDE.md.template`)
  - Manually craft every line — don't auto-generate with `/init`
  - Keep it lean: only universally applicable instructions
- [ ] Create `.claude/commands/` and copy slash commands from `templates/commands/`
- [ ] Create `.claude/skills/` for domain-specific knowledge (loaded on demand):
  - e.g., `api-conventions/SKILL.md`, `database-patterns/SKILL.md`
  - Skills keep CLAUDE.md lean while giving Claude access to specialized knowledge
- [ ] Create `.claude/agents/` for custom subagent definitions (optional):
  - e.g., `security-reviewer.md`, `performance-analyzer.md`
  - Define tool restrictions and model per agent
- [ ] Create `docs/` directory with subdirectories:
  - `docs/research/` — Research documents
  - `docs/plans/` — Implementation plans
  - `docs/decisions/` — Architecture decision records
- [ ] Configure `.claude/settings.json` for hooks:
  - Stop hook on file edit → run formatter/linter automatically
  - Stop hook before commit → run typecheck/lint
  - Hooks are deterministic (guaranteed to run), unlike CLAUDE.md instructions (advisory)

## CLAUDE.md Configuration

- [ ] Fill in project name, description, and stack
- [ ] Document build/test/lint commands
- [ ] Document deployment pipeline (which branch deploys where)
- [ ] Document git workflow (default branch, production branch)
- [ ] Include all Agent Operational Rules from the template
- [ ] Add project-specific context (key routes, data types, code ownership)

## Slash Commands

Copy and adapt from `templates/commands/`:
- [ ] `/research` — Codebase research with parallel subagents
- [ ] `/plan` — Interactive plan creation with phases
- [ ] `/implement` — Phase-by-phase execution with review gates
- [ ] `/validate` — Post-implementation verification
- [ ] `/describe-pr` — PR description generation

Adjust file paths in each command to match your project's docs directory.

**Slash commands vs skills:** Commands (`.claude/commands/`) are user-invoked workflows. Skills (`.claude/skills/`) are knowledge + workflows that Claude can also auto-detect. Use commands for RPI phases; use skills for domain conventions and reusable task patterns.

## Pre-Commit Hooks

- [ ] Install a hook framework (e.g., Husky for Node.js, pre-commit for Python)
- [ ] Configure pre-commit to run typecheck + lint:
  ```bash
  # Example: Husky
  npx husky init
  echo "pnpm run typecheck && pnpm run lint" > .husky/pre-commit
  ```
- [ ] Test that the hook rejects a commit with a deliberate type error
- [ ] Add a note to CLAUDE.md reminding agents to run checks before committing

## CI Setup

- [ ] Create a CI workflow (GitHub Actions, etc.) that runs on push and PR:
  - Typecheck
  - Lint
  - Unit tests
  - Build verification
  - (Optional) Security audit, E2E tests
- [ ] Mark critical CI jobs as required for PR merges
- [ ] Enable branch protection on the production branch (require CI + review)
- [ ] Verify CI runs successfully on the development branch

## Git Setup

- [ ] Initialize repo with `main` as production branch
- [ ] Create `develop` as default working branch
- [ ] Set up branch protection rules on GitHub
- [ ] Configure pre-commit hooks (typecheck, lint, test) — see Pre-Commit Hooks above

## Push Accountability

- [ ] Add push accountability instructions to CLAUDE.md or CLAUDE.local.md:
  - After every push to develop, spawn a background CI monitor
  - Background agent polls, investigates failures, fixes, and re-pushes
  - Main terminal stays unblocked
- [ ] Test the workflow: push a deliberate failure, verify the background agent catches it

## Scheduled Agents (Optional)

- [ ] Create `scripts/agents/` directory for agent shell scripts
- [ ] Create `docs/agents/` directory for agent reports and shared context
- [ ] Create `logs/` directory for agent output capture
- [ ] Write at least one agent script (e.g., test-health, security-audit)
- [ ] Schedule with launchd (macOS) or cron (Linux)
- [ ] Verify the agent runs successfully and produces a report
- [ ] Add `/pre-launch` slash command for multi-agent production audit

## Workflow Habits

- [ ] Always `/research` before `/plan`
- [ ] Always `/plan` before `/implement`
- [ ] Always review plans before approving
- [ ] Never skip the human confirmation gate between implementation phases
- [ ] Use `/validate` after implementation
- [ ] Use `/clear` between unrelated tasks to reset context
- [ ] Run each RPI phase in its own conversation
- [ ] Research and plan on the default branch; implement in worktrees
- [ ] Read research output critically — throw out and redo if wrong
- [ ] Invest most review time on research and plans, not generated code
- [ ] For large features, have Claude interview you before planning (AskUserQuestion)
- [ ] Follow TDD: write failing tests before implementation code
- [ ] Monitor CI after every push — never push and forget

## Thoughts Directory Structure

```
docs/
├── research/                  # Research documents
│   └── YYYY-MM-DD-topic.md
├── plans/                     # Implementation plans
│   ├── YYYY-MM-DD-feature.md  # Main plan
│   └── YYYY-MM-DD-feature-phases/
│       ├── phase-1.md
│       └── phase-2.md
├── decisions/                 # ADRs / decision records
└── prs/                       # PR descriptions
    └── {number}_description.md
```
