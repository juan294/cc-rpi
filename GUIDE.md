# The cc-rpi Guide

A practical guide to using the cc-rpi blueprint for AI-assisted software development with Claude Code, with Codex compatibility via `AGENTS.md`.

## What Is This?

cc-rpi is a blueprint repository. You clone it once, and every time you start a new project, you point Claude Code at it and say "set this project up." The agent reads the blueprint, learns the rules, and configures your new project with battle-tested practices — slash commands, error prevention rules, CI setup, the works.

That setup now includes an `AGENTS.md` compatibility layer so the same
project can be operated from Codex without changing the
underlying methodology. Claude Code still handles bootstrap and adopt,
but the resulting project is portable across agent harnesses.

At its core, cc-rpi teaches Claude Code to work the way experienced developers have found works best: research first, plan second, implement third. This sounds obvious, but without explicit structure, AI coding agents tend to skip straight to writing code — and that's where things go wrong.

## The Big Idea: Research-Plan-Implement

The methodology is called RPI, and it's built on one insight that changes everything:

**Errors amplify as they move downstream.**

A mistake in your research becomes a wrong assumption in your plan, which becomes hundreds of lines of code solving the wrong problem. But a mistake in a single line of code is just... a bug. So the system is designed to focus your attention where it matters most: reviewing the research and the plan, not reading every line of generated code.

Here's what the pipeline looks like:

```
Research  ──human reviews──▶  Plan  ──human reviews──▶  Implement  ──human reviews──▶  Validate
   │                           │                           │                            │
   ▼                           ▼                           ▼                            ▼
 "What exists?"           "What do we change?"        "Make the changes"         "Did it work?"
```

Each phase runs in its own Claude Code conversation. This is intentional — it keeps the AI's context window clean. A fresh conversation reading a well-written plan performs dramatically better than a long conversation that's been going for an hour.

## The Philosophy in Five Minutes

**1. Research before you act.** Never modify code you haven't read. Every change starts with understanding what exists today, described factually — no opinions, no suggestions, just "here's how the code works right now."

**2. Plan before you implement.** Write a phased plan with explicit success criteria before touching production code. Plans are broken into phases, and each phase has automated tests that prove it works.

**3. Keep acceptance boundaries visible.** Review research and plans before
implementation, and inspect each phase's review and verification evidence. The
agent continues through phases you already authorized; it pauses only for a
necessary new decision, not to repeat permission.

**4. Keep context grounded in current state.** Tools, repositories and native
memory can persist outside a conversation. Handoffs make the objective, approved
scope, decisions and verification evidence retrievable; the next session checks
actual files and refs before relying on them.

**5. Specs are the new code.** In AI-assisted development, your plans and research documents are effectively your source code. The generated code is more like a compiled artifact. Treat your specs with the same rigor you'd treat source files — review them carefully, version them in git, iterate on them until they're right.

## Local verification and publication

Keep implementation branches and worktrees local. Finish the applicable local
gates and integrate locally before the single authorized integration push.
Inspect workflow/deployment triggers; never create Vercel Previews or use hosted
CI as a debugging loop. Observe the exact pushed SHA and required check set.
A remote-only failure returns to local diagnosis and any new required approval.
Production and publication retain explicit authorization boundaries. Preserve
project knowledge, dirty files and unintegrated work through worktree cleanup.

## Getting Started

### Step 1: Choose an Explicit Installation Scope

Keep a local cc-rpi source checkout or a supported native package. The shared
engine plans before applying changes; it never infers permission to overwrite
mixed project instructions or install global settings. Python 3.11+ is required.
From the source checkout, inspect the package without changing an installation:

```bash
bash scripts/install.sh --check
bash scripts/install.sh --help
```

For an explicitly chosen user-scope skill installation:

```bash
bash scripts/install.sh --scope user --harness both --output /tmp/rpi-user-plan.json
# Review the exact local plan and any conflicts before applying:
bash scripts/install.sh --apply /tmp/rpi-user-plan.json
```

User scope defaults to `~/.claude/skills`, `~/.agents/skills` and a separate
user receipt under `~/.config/cc-rpi/installations/user`; explicit root options
are available. Project install/update/detach never silently manages these roots.
The installed source receipt resolves lifecycle updates to an actual local
source. `--check` with a target or user scope inspects that installation;
source-only `--check` validates the source package.

The workflow names are `rpi-*` skills in both harnesses. Claude retains native
`/simplify`; Codex uses the separately named `codex-simplify` helper. Legacy
`plan` and `status` aliases are discontinued to avoid native collisions; retained
legacy aliases are migration notices, not automatic forwarding.

#### Native Package Routes

Native package installation and trust belong to the harness's native manager.
Claude supports the complete package; use direct installation when conditional
domain selection is needed. Codex supports native module selection. Inspect the
actual installed client/package discovery before claiming skills or hooks are
active. A copied package or receipt alone is not native discovery or trust.
Project rules, ownership and capability setup still use the lifecycle contract.
Do not install both direct and plugin copies of the same workflow in one harness.

See [migration guidance](docs/migrations/v2.md) and
[native model profiles](docs/model-profiles.md) for setup boundaries.

### Step 2: Set Up Your Project

**Starting a new project?** Open Claude Code in the project directory and type:

```
/rpi-bootstrap
```

The agent reads the blueprint and existing project facts, resolves missing
project decisions, and prepares an explicit lifecycle plan. It applies the
reviewable authorized change while preserving owner content. Native permission
and hook capability setup remains a separate choice.

**Migrating an existing project?** Open Claude Code in the project directory and type:

```
/rpi-adopt
```

The agent reads the blueprint, then audits configuration, infrastructure and
workflow using bounded independent assignments when useful. It presents a report showing what's already in place, what's missing (prioritized HIGH/MEDIUM/LOW), and what needs adaptation rather than replacement. You choose what to adopt, and it migrates item by item.

The key difference: `rpi-bootstrap` creates from templates. `rpi-adopt` respects what exists and merges in what's missing.

Both commands now install `AGENTS.md` by default, so after setup the
same `rpi-research`, `rpi-plan`, `rpi-implement`, `rpi-pre-launch`, `rpi-update-docs`,
and `rpi-release` workflows can be driven from Codex too.

### Step 3: Start Working

Once your project is set up (by either command), your daily workflow uses four portable skills:

```
rpi-research [topic]     →  Understand the codebase
rpi-plan [feature]       →  Create an implementation plan
rpi-implement [plan]     →  Execute the plan phase by phase
rpi-validate [plan]      →  Verify everything works
```

That's it. Those four commands are 90% of your interaction with the methodology.

If you switch to Codex, the workflow names stay the same. `AGENTS.md`
provides shared root facts and an explicit conditional-rule map. Codex discovers
its native skills from the selected direct or package route; Claude uses its own
adapter. Neither harness depends on interpreting the other's command files.

For the `/simplify` step specifically, keep Claude Code on the native
command and invoke `codex-simplify` from your selected Codex skill
installation when you want the same cleanup pass in Codex.

## Command Cheat Sheet

### Setup Commands

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `rpi-bootstrap` | Reads the cc-rpi blueprint, asks about your project, creates CLAUDE.md, AGENTS.md, settings, slash commands, and full directory structure. | New projects. Run once at the start. |
| `rpi-adopt` | Reads the blueprint, audits the existing project with parallel agents, presents a gap report, then migrates what you approve, including the Codex compatibility layer. | Existing projects you want to bring up to standard. |
| `rpi-update` | Pulls latest cc-rpi, diffs changes since last sync, updates commands, AGENTS.md, blueprint-managed CLAUDE.md sections, and settings. | Manually or via nightly scheduled agent. |
| `rpi-detach` | Inventories all cc-rpi artifacts, previews what will be removed, asks for confirmation, then cleanly removes commands, hooks, CLAUDE.md sections, and sync metadata. Preserves project config and work products. | When you want to stop using the RPI methodology and remove all blueprint artifacts. |

### The Core Four

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `rpi-research [question]` | Explores the codebase with bounded assignments when useful. Produces a research document at `docs/research/`. | Before any change. Understanding comes first. |
| `rpi-plan [feature]` | Creates a phased implementation plan with pseudocode, success criteria, and test requirements. Saves to `docs/plans/`. | After research is reviewed and approved. |
| `rpi-implement [plan path]` | Executes the plan one phase at a time. Reviewer checks plan compliance, then `/simplify` handles code quality. Stops after each phase. | After the plan is reviewed and approved. |
| `rpi-validate [plan path]` | Runs every automated check from the plan, verifies all phases are complete, produces a validation report. Recommends `/simplify` for quality findings. | After implementation is done. |

### Supporting Commands

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `rpi-brainstorm [idea]` | Optional front end to RPI. Refines a vague or greenfield idea through one-question-at-a-time Socratic intake into a design brief at `docs/research/`. Feeds `rpi-plan`. | When the request is a goal, not a spec — and there's no existing code to `rpi-research`. |
| `rpi-tool-design [goal]` | WebMCP: turns a stated user goal into a tool contract plus seed evals by role-playing the conversation twice (clean and vague) against the codebase's real initial state. Saves to `docs/plans/`. Feeds `rpi-plan`. | When a project exposes (or plans to expose) an agent-facing tool surface and the goal is already stated. Sits between `rpi-brainstorm` and `rpi-plan`. |
| `rpi-describe-pr` | Generates a PR description from the current branch's diff and commit history. | Before opening or updating a PR. |
| `rpi-pre-launch` | Covers 8 core audit domains plus the conditional Agent Surface domain, with independent coverage and staffing based on available resources. Produces a 16-section report with 5-tier severity findings, finding IDs, and Before/After/Later time horizons. | Before any production release. Run `rpi-remediate` to resolve findings with complete disposition coverage. |
| `rpi-remediate` | Validates finding IDs and domain coverage, resolves confirmed findings through TDD, independent review, simplification and local verification; records evidence for rejected findings and scope decisions. | After `rpi-pre-launch` when findings exist. |
| `rpi-triage` | Discovers overnight agent reports via timestamp-based scanning, checks for agent failures in logs, queries GitHub Security & Quality Alerts (code scanning/CodeQL, Dependabot security, secret scanning) every run, scans open Dependabot PRs (Rule #84), and extracts `leanness-report.md` items individually. Synthesizes findings, proposes action plan, implements fixes, then prepares local dependency fixes; remote merges require authorization. Public repos: reports stay local. Private repos: reports are committed alongside fixes. | Every morning. First command of the day for each project. |
| `rpi-explore-release` | Wave B of E2E Pro: diff-driven, fresh-context exploratory release charters run as parallel agents, each completing the mandatory eight-maneuver table under a synthetic-fixture safety contract. Blocks on any failure or skipped high-risk area. Feeds evidence to `rpi-release`; never tags. | Once there's a deployed release candidate to test, before `rpi-release`. |
| `/status` | Quick 5-line project orientation: branch, last commit, working tree, CI status, open items. | Start of session. Quick check without starting a full task. |
| `rpi-update-docs` | Uses bounded discovery as useful, then updates all documentation, Mermaid diagrams, version references, and inline code docs based on changes since last release. | After features/fixes are done, before releasing. Refreshes everything in one pass. |
| `rpi-release` | Detects project type and branching strategy, bumps versions everywhere, generates CHANGELOG entry, creates release commit and tag, publishes GitHub release, advises on registry publish. | When ready to cut a new version. Run `rpi-update-docs` first. |
| `rpi-fix-ci` | Reads CI failure evidence, reproduces and repairs locally, and runs full local gates before an authorized integration push. | When CI is red. Automates the diagnose-fix-verify loop. |

### Model and Effort Selection

RPI workflows and their helpers inherit the owner's active pane model and
effort. Shared skills omit native model/effort overrides; a workflow name does
not determine the difficulty of its tasks.

For an explicit Claude research/planning pane:

```bash
claude --model best --effort high
```

Keep your chosen implementation pane selection. Optional economy launches apply
only to a bounded mechanical task you select, such as formatting or locating
files. Architectural research, validation and stateful diagnosis retain the
owner's selection. See [model selection](methodology/context-engineering.md#model-selection--inherit-the-owner-pane)
and [cost monitoring](methodology/cost-monitoring.md) for explicit profiles,
native precedence and requested-versus-observed identity.

The recommended daily workflow:

```
rpi-triage -> fix all findings -> continue development
```

For multi-project orchestration, use `morning-triage.sh` to run `rpi-triage` across all projects automatically.

The recommended pre-release sequence:

```
rpi-pre-launch -> rpi-remediate -> rpi-update-docs -> rpi-release
```

### Native Claude Code Commands Used in the Workflow

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/simplify` | Reviews reuse, quality and efficiency and applies fixes; native staffing is version-specific. In Codex, use `codex-simplify` instead of defining a project skill named `simplify`. | After reviewer approval in `rpi-implement`. After `rpi-pre-launch` audit. Anytime after significant code changes. |
| `/batch [instruction]` | Runs bounded independent assignments in local worktrees within the current phase, at most three implementers, with one integration owner. | For `[batch-eligible]` assignments within an approved phase; no automatic cross-phase launch. |
| `/clear` | Resets the conversation context. | Between unrelated tasks. The most underused command. |
| `/compact [focus]` | Summarizes the current conversation with a focus area. | Same task, but context is getting heavy. |
| `/worktree` | Creates an isolated git worktree for implementation. | When starting `rpi-implement`. Keep main clean. |
| `Esc` + `Esc` | Rewinds to a previous checkpoint (restores conversation, code, or both). | When an approach fails and you want to undo. |

## How the Four Phases Actually Work

### Phase 1: Research

You type `rpi-research how does authentication work in this app?` and the agent:

1. Investigates the question locally or assigns bounded locator, analyzer and pattern-finding work when independent coverage benefits from delegation.
2. Waits for all of them to finish.
3. Synthesizes their findings into a structured research document.
4. Saves it to `docs/research/YYYY-MM-DD-auth-flow.md`.

The critical rule here is **documentarian, not critic**. The research describes what exists — it doesn't suggest improvements or identify problems. This keeps the research factual and prevents the agent from jumping to solutions before understanding the problem.

Note: rpi-research is for projects that already have code. If you just bootstrapped a new project and have no code yet, skip rpi-research and start with rpi-plan — there's nothing to research. When the idea itself is still vague (a goal, not a spec), run rpi-brainstorm first to turn it into a design brief, then rpi-plan. Once you have code from your first implementation, rpi-research becomes your starting point for every subsequent task.

**Your job:** Read the research document. If it's wrong or incomplete, throw it out and run `rpi-research` again with more specific steering. Multiple passes are normal. Don't approve bad research — it poisons everything downstream.

### Phase 2: Plan

You type `rpi-plan add rate limiting to the login endpoint` and the agent:

1. Reads the research document.
2. Explores the codebase for additional context.
3. Asks you focused questions (only things the code can't answer).
4. Proposes design options with trade-offs.
5. Writes a phased implementation plan with pseudocode, file-by-file changes, and success criteria.
6. Saves it to `docs/plans/` with separate files for each phase.

Plans use a compact pseudocode notation so you can see exactly what changes in each file without reading full code blocks. Each phase has automated success criteria — tests that prove the phase works.

**Your job:** Read the plan carefully. This is where your time has the highest leverage. A bad plan leads to hundreds of bad lines of code. Push back, ask questions, iterate until the plan is right.

### Phase 3: Implement

You type `rpi-implement docs/plans/2026-02-21-rate-limiting.md` and the agent:

1. Reads the plan.
2. Identifies bounded independent assignments within the current approved phase, with one owner per file set/worktree and one integration owner.
3. Starts the next incomplete authorized phase.
4. Implements locally or uses at most three implementers as useful, then obtains independent **plan compliance** review (does the code match the spec?).
5. Runs `/simplify` — Anthropic's native code quality pass (reuse, quality, efficiency). This catches things the plan-compliance reviewer doesn't check.
6. Runs all automated verification (tests, typecheck, lint).
7. Updates the plan's checkboxes.
8. **Records phase acceptance and continues when your request already authorizes the next phase.**

Each phase completes its review and verification before the next begins.
An instruction such as "all phases" authorizes continuation without repeated
confirmation; newly required scope or architecture decisions still need review.

**Your job:** Review acceptance evidence and steer when needed. You can authorize
all phases upfront; that never removes independent review or verification.

### Phase 4: Validate

You type `rpi-validate docs/plans/2026-02-21-rate-limiting.md` and the agent:

1. Re-reads the plan.
2. Runs every automated verification command.
3. Checks that all marked-complete items are actually done.
4. Thinks about edge cases.
5. Produces a validation report.

**Your job:** Review the report. If there are manual testing items (there should be very few), do them. Then you're done.

## Key Concepts

### Context Engineering

The entire methodology is a context management strategy. Here's why: Claude Code has a fixed-size context window. Everything the agent needs to make a good decision must fit in that window. If the window fills up with noise (old test output, failed approaches, irrelevant file searches), the agent's decisions degrade.

RPI manages this by:
- **Running each phase in its own conversation.** Fresh context every time.
- **Producing compact artifacts between phases.** A research doc is a compressed summary of hours of exploration.
- **Using subagents for exploration.** They consume context in their own window and return only the distilled result to yours.
- **Clearing context between unrelated tasks.** `/clear` is your friend.

There is no universal utilization target. Use native compaction during a long
phase and durable handoffs between conversations. Record objective, approved
scope, exact repo/worktree state, findings, decisions, check receipts and tested
identity, deviations, risks and next step; revalidate actual state on resume.

### The Documentarian Rule

During `rpi-research`, agents describe what IS — never what SHOULD BE. Use the
separate `rpi-assess` workflow for evaluative research and alternatives. No improvement suggestions, no code critiques, no "this could be refactored." Just factual descriptions with file and line references.

This sounds restrictive, but it's the single most impactful rule for research quality. Without it, agents produce noisy research full of opinions that bias the planning phase.

### Error Prevention

The blueprint includes 89 operational rules learned from real sessions. These aren't theoretical — they're patterns that caused actual failures and wasted time. Rather than loading all rules into every session, the blueprint uses **progressive disclosure** across three layers: a compact shared AGENTS.md root block imported by Claude, an explicit Codex root rule map alongside Claude native conditional rules, and selected native skills for detailed domain knowledge. This keeps the agent's context window clean and focused.

`patterns/quick-reference.md` is the **index** to those rules, not a catalog of them: each rule body lives in the skill, rule file, command, or methodology doc that needs it, and the index is one line per rule naming where it went. Rule numbers are permanent — a gap means the number was retired, and the ledger in `.claude/rules/contributing.md` records the ground.

Domain skills cover shell/tools, Git, CI, deployment, multi-agent coordination,
GitHub CLI, Python, macOS, Supabase, WebMCP, errors and debugging. The manifest
defines workflow/domain/helper/rule inventory; inspect current counts with
`python3 templates/scripts/rpi-distribution.py counts --source . --json` rather
than relying on a copied resource count.

### Agent Teams

Claude Code has an experimental feature called Agent Teams that lets the main agent spawn long-running teammate agents that work in parallel. Agent Teams is an explicit opt-in; new installations use ordinary subagents. Updates preserve an existing user opt-in. The blueprint provides guidance on when to use teams vs. regular subagents:

- **Subagents** (quick, focused): Read-only research, file exploration, code analysis. Seconds to minutes.
- **Agent Teams** (long-running, parallel): Independent bounded work within the current approved phase. Keep ownership and resource limits explicit.

### Pre-Launch Audit

Before production release, `rpi-pre-launch` covers 8 core audit domains:

1. **Principal Architect** — System-wide architecture, module boundaries,
   dependency health, dead code, typecheck
2. **Staff Frontend Engineer** — Component structure, state, routing,
   client-side perf, hydration, bundle composition
3. **Staff Backend Engineer** — API design, validation, DB access,
   transactions, queues, background jobs, service boundaries
4. **Performance Engineer** — Bundle sizes, p95/p99 latency risks,
   cache strategy, hot paths
5. **DevOps / SRE Lead** — Deployment safety, rollback, CI, env config,
   observability, runbook readiness
6. **Security Reviewer** — Dependency audit, secrets, auth/authz,
   injection vectors
7. **QA / Reliability Lead** — Test suite, coverage, graceful degradation,
   failure modes, retry/idempotency coverage
8. **Product Designer / UX Lead** — Visual hierarchy, design-system gaps,
   component reuse, messaging/voice consistency, a11y
9. **Agent Surface Engineer** (conditional) — Tool inventory and naming,
   input schemas vs. handler validation, error recovery text,
   registration lifecycle. Required when the project exposes tools to
   an agent (WebMCP, an MCP server); otherwise record its non-applicability.

The eight core domains remain required regardless of agent count. One reviewer
may cover compatible domains; missing results are explicit coverage gaps, never
successful checks. Preserve project-specific stricter release charters. Findings
retain stable IDs, severity, time horizon and evidence/inference labels, and
synthesize into the required report with READY, CONDITIONAL or NOT READY verdict.

`rpi-remediate` validates the report and resolves every confirmed actionable
finding. Severity and time horizon order work without automatically dropping low
or strategic findings. False positives need evidence; a new architectural
choice receives an explicit local disposition and owner review. External issue
creation requires authorization. Review, repair, simplify and verify before
acceptance; existing authorization is sufficient to continue.

### Release Verification (E2E Pro)

Where `rpi-pre-launch` audits the code as written, **E2E Pro** verifies the
*deployed candidate's behavior* and proves that every required check
actually ran and passed against the exact artifact being tagged. The
template at `templates/e2e-pro-playbook-template.md` is copied into each
project and adapted. Its mandatory floor is **Wave A** — a release gate
that cannot lie: zero-pass fails, a required skip or failure blocks (even
quarantined), candidate identity is fixed and verified, and the tag is the
last action (delegated to `rpi-release`). The structural waves (capability
registry, combination engine, plan compiler, staging fidelity, model-based
tests, cadence/TTL) are adopted by project risk. Wave B —
fresh-context exploratory charters — runs via the `rpi-explore-release`
command.

## Project Structure After Setup

A direct installation adds the selected native workflow/domain skills under
`.claude/skills/` and `.agents/skills/`, shared root instructions, and only the
selected managed rules/resources. Native plugin routes load package skills from
the native package roots instead. The public `.rpi/manifest.json` records
component ownership and per-harness routes/domains; private plans, baselines,
journals and evidence live under `.rpi/local/`. Project research, plans and
handoffs remain owner work products. Capability setup writes only explicitly
selected native config entries; registration, trust and observed enforcement
are separate diagnostics states.

## Tips for Getting the Most Out of It

**Start every task with `rpi-research` — except for greenfield projects with no code yet, where you start with `rpi-plan`.** Once you have code, the research phase takes a couple of minutes and often reveals things you didn't expect.

**Read your research and plans critically.** This is where your time has 10x leverage compared to reviewing code. A bad plan wastes hours; catching it early saves them.

**Use `/clear` liberally.** Switching tasks? `/clear`. Finished a phase? Start a new conversation. Context hygiene is the single biggest factor in output quality.

**Don't fight the phases.** It feels slower to research-then-plan-then-implement than to just say "add this feature." But the phased approach produces better results in less total time because you avoid the rework cycles that come from misunderstood requirements.

**Throw out bad research.** If the research document doesn't accurately describe the codebase, don't try to salvage it. Run `rpi-research` again with better steering. Multiple passes are normal and expected.

**Keep phase acceptance visible.** Review the evidence at each boundary; an
already-authorized multi-phase run continues without repeating permission.

**Invest in your CLAUDE.md.** This file is the highest-leverage configuration point in the entire system. Every session reads it. Craft every line manually. If removing a line wouldn't cause mistakes, remove it.

**Log your errors and successes.** When something goes wrong, write it down. When something goes perfectly, write it down. After 3 instances of the same pattern, promote it to a rule. This is how the blueprint itself was built.

## Advanced Setup

### Lifecycle Skills: `rpi-bootstrap`, `rpi-adopt`, `rpi-update`, `rpi-detach`

These explicitly invoked skills resolve an actual local source and target, then
use the shared lifecycle engine to plan and apply a concrete transaction.
Bootstrap handles a new project; adopt assesses existing content; update compares
recorded bases with local and source state; detach removes only proven ownership.
Mixed, modified or unproven owner content is retained with a conflict/disposition,
and recovery records support rollback. Project detach leaves separate user
installations alone. No lifecycle action silently pulls remote changes or grants
native trust. Reuse the user's authorization for the concrete scope; request only
new decisions needed by the planned diff.

### Nightly Blueprint Sync

Scheduled updates are optional and require explicit setup and resource
authorization. The ordinary lifecycle never installs a scheduler. If selected,
review the script and scope it to an explicit local source/target:

1. Copy `templates/scripts/cc-rpi-update-agent.sh` to your project's `scripts/agents/`
2. Set the `CC_RPI_PATH` variable to your cc-rpi clone location
3. Schedule it with launchd (macOS) or cron (Linux) — the script has templates in its comments

The shell script reads update instructions from cc-rpi at runtime, so when you improve the `rpi-update` command in cc-rpi, all projects automatically get the new logic on their next scheduled run.

### Scheduled Agents

For production projects, you can set up agents that run on a schedule (daily or weekly) to monitor code quality, run security audits, check dependency health, and detect flaky tests. These run headlessly via `claude -p "prompt"` and produce markdown reports. See `methodology/scheduled-agents.md` for templates.

### Adapting for Different Project Types

The blueprint adapts to six project archetypes: web applications, libraries, CLI tools, monorepos, Python projects, and static sites. Each has specific adjustments for git workflow, CI configuration, testing strategy, and CLAUDE.md content. The setup checklist walks you through the differences.

## Where to Go Deeper

The blueprint repository contains detailed documentation on every topic mentioned in this guide:

| Topic | File | What You'll Learn |
|-------|------|-------------------|
| Core philosophy | `methodology/philosophy.md` | Error amplification, mental alignment, key lessons |
| Context management | `methodology/context-engineering.md` | Compaction, progressive disclosure, session lifecycle |
| The four phases | `methodology/four-phases.md` | Detailed process for each phase, handoffs, failure recovery |
| Agent design | `methodology/agent-design.md` | Subagent catalog, autonomy boundaries, Agent Teams |
| Plan notation | `methodology/pseudocode-notation.md` | How to write and read implementation plans |
| Testing approach | `methodology/testing.md` | TDD protocol, verification hierarchy |
| CI ownership | `methodology/push-accountability.md` | Local gates and exact-candidate CI observation |
| Model economics | `methodology/cost-monitoring.md` | Session inheritance, explicit economy choices, cost per outcome |
| Error patterns | `patterns/agent-errors.md` | 64 documented errors with symptoms and solutions |
| Operational rules | `patterns/quick-reference.md` | Index of 89 rules, each pointing to the surface that holds it |
| Domain skills | `templates/skills/` | Manifest-declared workflows and domain knowledge |
| Rule templates | `templates/rules/` | Canonical rules rendered through harness adapters |
| Deployment safety | `patterns/deployment-safety.md` | Resource efficiency and production deployment rules |
| Release verification | `templates/e2e-pro-playbook-template.md` | E2E Pro: auditable release-evidence system (Wave A gate + structural waves) |
| Worked examples | `examples/README.md` | Sample research docs, plans, logs, pseudocode |

## Credits

The RPI methodology is adapted from HumanLayer's opencode-rpi implementation and their ACE-FCA (Advanced Context Engineering for Coding Agents) framework, tailored for Claude Code's native capabilities.
