# CI & Development Guardrails

Guardrails are automated enforcement layers that catch mistakes before they reach the repository. They work at three levels: editor-time, commit-time, and push-time.

## The Enforcement Stack

```
Level 0: Agent-time (PreToolUse hooks)
├── Intercepts commands BEFORE they execute
├── Blocks known-bad patterns (dirty pull, --tags)
├── Agent sees the block reason and self-corrects
└── Most reliable layer — prevents errors, not just consequences

Level 1: Editor-time (hooks on file edit)
├── Formatter runs on save (Prettier, Black, rustfmt)
├── Linter runs on save (ESLint, Ruff, clippy)
└── Agent sees errors immediately and fixes them

Level 2: Commit-time (pre-commit hooks)
├── Typecheck across the project
├── Lint across the project
├── Tests (unit, optionally integration)
└── Commit is rejected if any check fails

Level 3: Push-time (CI workflows)
├── Full test suite (unit + integration + e2e)
├── Type checking
├── Lint
├── Build verification
├── Security audit (dependency vulnerabilities)
└── Push accountability agent monitors results
```

Each level catches progressively harder-to-detect issues. The goal: **no broken code ever reaches the shared branch.**

## Agent Tool Hooks (Level 0)

PreToolUse hooks intercept agent commands before they execute. Unlike CLAUDE.md rules (which are advisory), hooks are deterministic — they always run, they can't be forgotten, and they block the command with an explanation.

### Why Hooks Beat Rules

Documented rules fail because of a fundamental mismatch: LLMs don't have procedural memory. A rule read 200 turns ago has near-zero influence on the decision being made right now. In one observed batch of 16 agent errors, 10 were duplicates of already-documented patterns — the rules existed, the agent "knew" them, and it violated them anyway. Error #33 (commit before git pull --rebase) alone appeared 6 times despite being documented since v1.0.

Hooks fix this by moving enforcement from "remember the rule" to "the command is blocked." The agent doesn't need to remember — the system prevents the mistake.

### Setup

Configure in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/guard-bash.sh"
          }
        ]
      }
    ]
  }
}
```

The guard script (`.claude/hooks/guard-bash.sh`) receives the command as JSON on stdin, checks for known-bad patterns, and exits non-zero with a message to block. Exit 0 allows the command through. Copy from `templates/hooks/guard-bash.sh` and add project-specific guards.

### What to Enforce via Hooks

Only promote a rule to hook enforcement when:
1. **Observed 3+ times** despite being documented
2. **Mechanically detectable** — a shell script can identify the bad pattern
3. **Has a clear fix** — the block message tells the agent exactly what to do instead

The current guard script enforces:
- **Error #33**: `git pull --rebase` with uncommitted changes (checks `git status --porcelain`)
- **Error #44**: `git push --tags` instead of specific tag names (pattern match)

### Three-Tier Error Prevention Model

| Tier | Mechanism | Reliability | When to Use |
|------|-----------|-------------|-------------|
| **Enforce** | PreToolUse hooks, pre-commit hooks, CI | High — mechanically prevented | Top repeat offenders. Rules that keep getting violated despite documentation. |
| **Prompt** | Command recipes in CLAUDE.md | Medium — agent copies the pattern | Frequent operations. Give compound commands to copy instead of compose. |
| **Document** | agent-errors.md, quick-reference.md | Low — advisory only | Long tail. Reference for when things go wrong. |

Rules graduate upward: a pattern documented in tier 3 that keeps recurring gets promoted to tier 2 (recipe in CLAUDE.md) or tier 1 (hook). The error processing routine should track repeat offenders across batches and promote accordingly.

## Pre-Commit Hooks

Pre-commit hooks run automatically before every commit and reject the commit if any check fails.

### Setup

Use a framework like [Husky](https://typicode.github.io/husky/) (Node.js), [pre-commit](https://pre-commit.com/) (Python), or native git hooks:

```bash
# Example: Husky (Node.js projects)
npx husky init
echo "pnpm run typecheck && pnpm run lint" > .husky/pre-commit
```

### What to Run in Pre-Commit

| Check | Why | Speed |
|-------|-----|-------|
| **Typecheck** | Catches type errors before they hit CI | Medium |
| **Lint** | Catches style violations and common bugs | Fast |
| **Unit tests** | Catches regressions immediately | Fast-Medium |
| **Format check** | Ensures consistent formatting | Fast |

**Don't include in pre-commit:** E2E tests (too slow), full builds (too slow), dependency audits (too slow for every commit). Save these for CI.

### Agent Interaction

Agents must run the same checks pre-commit hooks run **before** attempting to commit (see [quick-reference.md rule #5](../patterns/quick-reference.md)). This avoids the wasted cycle of: commit → hook fails → fix → re-commit.

```bash
# Agent workflow before committing:
pnpm run typecheck 2>&1; pnpm run lint 2>&1  # Run checks first
# Fix any errors
git add <files> && git commit -m "..."         # Then commit (hook will pass)
```

## CI Workflows

CI workflows run on every push and PR. They are the authoritative verification — if CI is green, the code is shippable.

### Recommended CI Pipeline

```yaml
# Conceptual workflow (adapt to your CI system):
on: [push, pull_request]

jobs:
  quality:
    steps:
      - Install dependencies
      - Run typecheck
      - Run lint
      - Run unit tests
      - Run integration tests

  build:
    steps:
      - Install dependencies
      - Build the project
      - Check bundle sizes (optional threshold)

  security:
    steps:
      - Run dependency audit
      - Check for hardcoded secrets (optional)

  e2e:
    needs: build
    steps:
      - Run E2E tests against the built artifact
```

### CI Design Principles

1. **Fast feedback.** Parallelize independent jobs. Typecheck, lint, and tests can run simultaneously.
2. **Fail fast.** Put the quickest checks first. A lint error found in 10 seconds is better than waiting 5 minutes for the build to fail.
3. **Required checks.** Mark critical jobs as required for PR merges. Don't let broken code merge.
4. **Artifact caching.** Cache `node_modules`, build outputs, and test fixtures across runs to speed up CI.
5. **Branch protection.** Require CI to pass before merging PRs. Require at least one review approval.

## Development Guardrails

Beyond automated checks, guardrails include process rules that prevent common mistakes:

### Branch Protection

- **Production branch** (`main`/`master`) — Protected. No direct pushes. PRs only, with required CI and review.
- **Development branch** (`develop`) — Semi-protected. Agents can push directly, but push accountability monitors CI.
- **Feature branches** — Unprotected. Agents create, push, and clean up freely.

### Environment Safety

- **Secrets in `.env`** — Never committed. Gitignored.
- **No secrets in `NEXT_PUBLIC_*`** (or equivalent) — Client-visible env vars must never contain secrets.
- **Documented required variables** — CLAUDE.md lists every required env var so agents know what's available.

### Dependency Safety

- **Lock files committed** — `pnpm-lock.yaml`, `package-lock.json`, etc. must be in version control.
- **Regular audits** — `pnpm audit` / `npm audit` in CI catches known vulnerabilities.
- **License compliance** — No copyleft dependencies in proprietary projects.

## Guardrails and Agent Autonomy

Guardrails are what make agent autonomy safe. When pre-commit hooks catch errors, CI verifies builds, and branch protection prevents unauthorized merges, agents can operate with high autonomy on the development branch without risk of damage.

The relationship is:
- **More guardrails** → more agent autonomy is safe
- **Fewer guardrails** → more human oversight is needed

Invest in guardrails early. They pay for themselves by enabling faster, more autonomous agent workflows.
