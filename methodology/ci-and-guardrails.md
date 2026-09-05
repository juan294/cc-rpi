# CI & Development Guardrails

Guardrails are automated enforcement layers that catch mistakes before they reach the repository. They work at three levels: editor-time, commit-time, and push-time.

## The Enforcement Stack

```
Level 0: Agent-time (PreToolUse hooks)
├── Intercepts commands BEFORE they execute
├── Blocks known-bad patterns (dirty pull, --tags)
├── Agent sees the block reason and self-corrects
└── Prevention depends on matched events and native registration/trust

Level 1: Editor-time (PostToolUse hooks on file edit)
├── Claude Code: verify-edit.sh post-Write/Edit (emoji + markdownlint on .md)
├── Editors: formatter/linter on save (Prettier, Black, rustfmt, ESLint, Ruff)
└── Agent sees violations immediately and fixes them

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

PreToolUse hooks can intercept matched agent commands before execution. Their policy evaluation is deterministic, but enforcement depends on the native adapter being registered, trusted and invoked for that tool. Report those states separately; a copied hook file is not proof of protection.

### Why Hooks Beat Rules

Documented rules fail because of a fundamental mismatch: LLMs don't have procedural memory. A rule read 200 turns ago has near-zero influence on the decision being made right now. In one observed batch of 16 agent errors, 10 were duplicates of already-documented patterns — the rules existed, the agent "knew" them, and it violated them anyway. Error #33 (commit before git pull --rebase) alone appeared 6 times despite being documented since v1.0.

Hooks fix this by moving enforcement from "remember the rule" to "the command is blocked." The agent doesn't need to remember — the system prevents the mistake.

### Setup

Use the ownership-aware lifecycle engine to plan the native settings diff and
apply it within existing setup authorization. Preserve project/user hooks, deny
rules and ordering. Claude native `permissions.deny` and `permissions.ask` form
the structural boundary; the stateful hook checks the documented branch,
Preview, tag and local-verification conditions. Broad git/gh allows are not a
substitute. Codex gets its own native schema and trust process.

The shared policy implementation is
[`templates/scripts/rpi-policy.py`](../templates/scripts/rpi-policy.py), with
[`guard-bash.sh`](../templates/hooks/guard-bash.sh) as the compatible Claude
wrapper. Supported command shapes are explicit in the implementation and its
fixtures. A shell substring match cannot establish arbitrary command safety.
Malformed guarded shell events, missing policy prerequisites and ambiguous
policy-sensitive forms block with `BLOCKED / WHY / FIX`; ordinary unrelated
tools remain unaffected. See the [migration note](../docs/migrations/v2.md).

A structural pass does not authorize publication. The active owner instruction
and native trusted permission boundary carry authorization. Never use a
model-written receipt, release skill invocation or `--follow-tags` as proof of
consent. When the client cannot provide the required native approval boundary,
keep remote automation blocked and provide the exact owner-executed commands at
release review.

### What to Enforce via Hooks

Only promote a rule to hook enforcement when:
1. **Observed 3+ times** despite being documented
2. **Mechanically detectable** — a shell script can identify the bad pattern
3. **Has a clear fix** — the block message tells the agent exactly what to do instead

The stateful policy preserves dirty-pull, named-tag and protected-branch
checks, and adds the owner's working-branch and Preview restrictions. Completed
integration and named-tag publication must satisfy the documented local evidence
and target checks before reaching the separate native approval boundary.

### Block messages are corrective hints

Criterion 3 above ("has a clear fix") is not advice — it is a required output
format. Every block a hook emits follows the same shape so a block is a guided
correction, not just a stop:

```
BLOCKED by <hook> — <Rule/Error #N>: <one-line reason>

WHY: <one sentence on the consequence if allowed>

FIX:
  <copy-pasteable command or concrete instruction>
```

Adapters preserve this corrective format from the shared policy result. The
`FIX` block must identify the missing prerequisite or malformed input and provide
a runnable repair or exact safe next action.
This mirrors the deterministic "retry hint" idea from contract-driven agent
designs — when enforcement moves out of the prompt and into code, the code still
has to tell the agent exactly how to comply. (Idea source:
`cristhianrivera/contract-driven-llm-agent` — convention only, no machinery ported.)

### Three-Tier Error Prevention Model

| Tier | Mechanism | Reliability | When to Use |
|------|-----------|-------------|-------------|
| **Enforce** | PreToolUse hooks, PostToolUse verification, pre-commit hooks, CI | Mechanical for matched, active and trusted boundaries | Top repeat offenders. Rules that keep getting violated despite documentation. |
| **Prompt** | Command recipes in CLAUDE.md | Medium — agent copies the pattern | Frequent operations. Give compound commands to copy instead of compose. |
| **Document** | agent-errors.md, quick-reference.md | Low — advisory only | Long tail. Reference for when things go wrong. |

Rules graduate upward: a pattern documented in tier 3 that keeps recurring gets promoted to tier 2 (recipe in CLAUDE.md) or tier 1 (hook). The error processing routine should track repeat offenders across batches and promote accordingly.

Skills can extend this model with **on-demand hooks** — guardrails that activate only when a specific skill is invoked and last for the session. Use these for rules too restrictive to run permanently but essential in certain contexts (e.g., blocking destructive commands when touching production). See [agent-design.md](agent-design.md) "On-Demand Hooks" for examples.

## Agent Tool Hooks (Level 1: post-edit verification)

Level 0 hooks prevent bad commands *before* they run. The harness realizes
**Level 1 (editor-time)** with a `PostToolUse` hook on `Write`/`Edit`:
`templates/hooks/verify-edit.sh`. After an edit lands, it checks the file and
surfaces violations as a corrective hint so the agent fixes them immediately —
instead of discovering them at CI.

This is post-action verification: a deterministic check that runs *after*
generation, the most transferable idea from contract-driven agent designs. Two
properties matter:

- **It cannot un-write the file.** The edit already happened; `exit 2` feeds the
  hint back to the agent as "fix this now". Prevention still belongs to CI and
  pre-commit — this layer closes the feedback loop fast.
- **It is supplemental feedback.** Missing optional post-edit tooling can leave
  a check unobserved; report that limitation. The pre-action policy guard has a
  separate fail-closed contract, so post-edit behavior cannot authorize a shell
  action.

The shipped checks on edited `.md` files:

1. **No emojis in documentation** (always on). Flags emoji/pictographs while
   deliberately allowing arrows (`->` and U+2192), em-dash, and box-drawing that
   docs use legitimately. Per-file opt-out: a line containing
   `<!-- contract:allow-emoji -->`.
2. **markdownlint** — runs only when the project ships a markdownlint config
   (`.markdownlint.json` and friends). Without a config, default rules would flood
   false positives, so the check stays dormant rather than noisy.

Wire it in `.claude/settings.json` alongside the Level 0 hook:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/verify-edit.sh" }
        ]
      }
    ]
  }
}
```

Add project-specific post-edit checks at the bottom of `verify-edit.sh`, following
the emoji check's structure.

### Measuring whether enforcement works

Enforcement you can't measure is enforcement you trust blindly. Available hook adapters append
one best-effort JSONL row per evaluated command/edit to
`.claude/metrics/contract-events.jsonl` — `{ts, session_id, hook, decision, rule,
file}`. They never log command text or file contents (guard-bash sees commands
that may carry tokens), and any logging error is swallowed so telemetry can never
break policy evaluation. A missing telemetry stream means unobserved coverage,
not zero violations; logs alone do not prove every native tool path is guarded.

`templates/scripts/contract-metrics.py` aggregates that log into:

- **block rate** per hook and per rule (how much the layer is catching),
- **self-correction rate** — a verify-edit block followed by a clean re-edit of the
  same file in the same session, i.e. the corrective-hint loop actually closing,
- a **week-over-week trend** (blocks per 100 events): a declining rate at stable
  volume is the signal that agents are internalizing the rules, not just being
  caught by them.

The raw log is gitignored; a weekly deterministic agent
(`contract-metrics-agent.sh`, no Claude CLI) snapshots the report to
`docs/agents/contract-metrics-report.md` for review over time. Because the feature
is new, the day it ships is a clean `t=0` — no pre-feature baseline to reconstruct.
Read the self-correction rate as the cleanest signal: it is within-session, so it
sidesteps confounds (model updates, changing project mix) that muddy the raw trend.

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

**Don't include in pre-commit:** E2E tests (too slow), full builds (too slow), dependency audits (too slow for every commit). Run these in the full local CI-equivalent gate before integration/publication.

### Agent Interaction

Agents must run the same checks pre-commit hooks run **before** attempting to commit (see [quick-reference.md rule #5](../patterns/quick-reference.md)). This avoids the wasted cycle of: commit → hook fails → fix → re-commit.

```bash
# Agent workflow before committing:
pnpm run typecheck 2>&1 && pnpm run lint 2>&1  # Run checks first
# Fix any errors
git add <files> && git commit -m "..."         # Then commit (hook will pass)
```

## CI Workflows

Inspect the actual workflow triggers. Run the complete applicable selection locally before the single authorized integration push. A green CI result is evidence for its checked commit and selection; it does not prove untested runtime behavior. Never use remote CI as an experimentation loop.

### Recommended CI Pipeline

```yaml
# Conceptual workflow (adapt to your CI system):
on:
  push:
    branches: [develop]  # use the documented integration branch

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
- **Integration branch** (for example `develop` or `main`) —
  Protected or semi-protected depending on topology. This is the shared
  branch that receives reviewed work and whose CI must stay green.
- **Implementation branches/worktrees** — Temporary, isolated branches
  where agents implement and verify before local integration. They remain
  local; do not open feature PRs or publish them.

### Environment Safety

- **Secrets in `.env`** — Never committed. Gitignored.
- **No secrets in `NEXT_PUBLIC_*`** (or equivalent) — Client-visible env vars must never contain secrets.
- **Documented required variables** — CLAUDE.md lists every required env var so agents know what's available.

### Dependency Safety

- **Lock files committed** — `pnpm-lock.yaml`, `package-lock.json`, etc. must be in version control.
- **Regular audits** — `pnpm audit` / `npm audit` in CI catches known vulnerabilities.
- **License compliance** — No copyleft dependencies in proprietary projects.

### Code Scanning Availability

Before adding a scanner, inspect repository visibility, enabled security product,
and caller permissions. A successful alerts query proves endpoint access for
that caller. An HTTP 403 can mean permissions, policy, rate limits or disabled
code security; a 404 can hide a private resource. Neither establishes product
availability on its own.

```bash
gh api repos/{owner}/{repo} --jq '{visibility, security_and_analysis}'
gh api --include repos/{owner}/{repo}/code-scanning/alerts
```

Inspect response status/message and permissions together. Code scanning is
available to public repositories and eligible private/internal repositories with
GitHub Code Security enabled. Do not enable a paid product or trigger scanning
without authorization. Read-only inspection of existing alerts remains allowed.
See [GitHub's code-scanning API](https://docs.github.com/en/rest/code-scanning/code-scanning)
and the github-cli skill for status interpretation.

## Guardrails and Agent Autonomy

Guardrails are what make agent autonomy safe. When pre-commit hooks
catch errors, CI verifies builds, and branch protection prevents
unauthorized merges, agents can operate with high autonomy on temporary
implementation branches and, where the topology allows it, on
non-production integration branches without risking production damage.

The relationship is:
- **More guardrails** → more agent autonomy is safe
- **Fewer guardrails** → more human oversight is needed

Invest in guardrails early. They pay for themselves by enabling faster, more autonomous agent workflows.
