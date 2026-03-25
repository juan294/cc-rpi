# The cc-rpi Guide

A practical guide to using the cc-rpi blueprint for AI-assisted software development with Claude Code.

## What Is This?

cc-rpi is a blueprint repository. You clone it once, and every time you start a new project, you point Claude Code at it and say "set this project up." The agent reads the blueprint, learns the rules, and configures your new project with battle-tested practices — slash commands, error prevention rules, CI setup, the works.

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

**3. Humans gate every transition.** The agent stops between phases and waits for you. You read the research before approving the plan. You read the plan before approving implementation. You confirm each implementation phase before the next one starts.

**4. Context is your only lever.** Every time the AI takes a turn, it's a stateless function: the context window goes in, the next action comes out. There's no hidden memory. The quality of what's in that window is literally the only thing that determines output quality. The entire methodology is designed around this constraint.

**5. Specs are the new code.** In AI-assisted development, your plans and research documents are effectively your source code. The generated code is more like a compiled artifact. Treat your specs with the same rigor you'd treat source files — review them carefully, version them in git, iterate on them until they're right.

## Getting Started

### Step 1: Clone the Blueprint and Install Commands

```bash
git clone https://github.com/juan294/cc-rpi.git
```

Keep this repository somewhere permanent on your machine. You'll reference it from every project.

Then install the two user-level commands that make everything work. These go in your home directory, so they're available in every project — even ones that haven't been set up yet:

```bash
mkdir -p ~/.claude/commands
cp cc-rpi/templates/commands/bootstrap.md ~/.claude/commands/bootstrap.md
cp cc-rpi/templates/commands/adopt.md ~/.claude/commands/adopt.md
cp cc-rpi/templates/commands/update.md ~/.claude/commands/update.md
cp cc-rpi/templates/commands/detach.md ~/.claude/commands/detach.md
```

Edit all four files to set the correct path to where you cloned cc-rpi on your machine.

Now you have four commands available everywhere:

| Command | Use Case |
|---------|----------|
| `/bootstrap` | **New project.** Empty or freshly created repo. Sets everything up from scratch. |
| `/adopt` | **Existing project.** Already has code, maybe some practices in place. Audits what exists and migrates incrementally. |
| `/update` | **Keep in sync.** Pulls latest cc-rpi changes and updates your project's commands, rules, and settings. Run manually or schedule nightly. |
| `/detach` | **Part ways.** Cleanly removes all cc-rpi artifacts while preserving your project-specific config and work products. |

### Step 2: Set Up Your Project

**Starting a new project?** Open Claude Code in the project directory and type:

```
/bootstrap
```

The agent reads the blueprint, asks you about your project (type, stack, conventions), then creates CLAUDE.md, settings.json, slash commands, directory structure, and walks you through CI and git setup.

**Migrating an existing project?** Open Claude Code in the project directory and type:

```
/adopt
```

The agent reads the blueprint, then audits your project with three parallel agents — checking configuration, infrastructure, and workflow. It presents a report showing what's already in place, what's missing (prioritized HIGH/MEDIUM/LOW), and what needs adaptation rather than replacement. You choose what to adopt, and it migrates item by item.

The key difference: `/bootstrap` creates from templates. `/adopt` respects what exists and merges in what's missing.

### Step 3: Start Working

Once your project is set up (by either command), your daily workflow uses four slash commands:

```
/research [topic]     →  Understand the codebase
/plan [feature]       →  Create an implementation plan
/implement [plan]     →  Execute the plan phase by phase
/validate [plan]      →  Verify everything works
```

That's it. Those four commands are 90% of your interaction with the methodology.

## Command Cheat Sheet

### Setup Commands

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/bootstrap` | Reads the cc-rpi blueprint, asks about your project, creates CLAUDE.md, settings, slash commands, and full directory structure. | New projects. Run once at the start. |
| `/adopt` | Reads the blueprint, audits the existing project with parallel agents, presents a gap report, then migrates what you approve. | Existing projects you want to bring up to standard. |
| `/update` | Pulls latest cc-rpi, diffs changes since last sync, updates commands and blueprint-managed CLAUDE.md sections, adds new settings. | Manually or via nightly scheduled agent. |
| `/detach` | Inventories all cc-rpi artifacts, previews what will be removed, asks for confirmation, then cleanly removes commands, hooks, CLAUDE.md sections, and sync metadata. Preserves project config and work products. | When you want to stop using the RPI methodology and remove all blueprint artifacts. |

### The Core Four

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/research [question]` | Spawns parallel agents to explore the codebase. Produces a research document at `docs/research/`. | Before any change. Understanding comes first. |
| `/plan [feature]` | Creates a phased implementation plan with pseudocode, success criteria, and test requirements. Saves to `docs/plans/`. | After research is reviewed and approved. |
| `/implement [plan path]` | Executes the plan one phase at a time. Reviewer checks plan compliance, then `/simplify` handles code quality. Stops after each phase. | After the plan is reviewed and approved. |
| `/validate [plan path]` | Runs every automated check from the plan, verifies all phases are complete, produces a validation report. Recommends `/simplify` for quality findings. | After implementation is done. |

### Supporting Commands

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/describe-pr` | Generates a PR description from the current branch's diff and commit history. | Before opening or updating a PR. |
| `/pre-launch` | Spawns 6 parallel specialist agents (QA, security, performance, architecture, UX, devops) for a production audit. | Before any production release. Run `/remediate` after to fix all findings. |
| `/remediate` | Parses the pre-launch report, creates GitHub issues for every finding, spawns parallel TDD agents in worktrees, merges sequentially, verifies CI, runs `/simplify` twice. | After `/pre-launch` when findings exist. Automates the full fix cycle. |
| `/triage` | Discovers all overnight agent reports exhaustively, checks for agent failures in logs, synthesizes findings, proposes action plan for all items, implements fixes, commits reports for history. | Every morning. First command of the day for each project. |
| `/status` | Quick 5-line project orientation: branch, last commit, working tree, CI status, open items. | Start of session. Quick check without starting a full task. |
| `/update-docs` | Spawns 4 parallel discovery agents, then updates all documentation, Mermaid diagrams, version references, and inline code docs based on changes since last release. | After features/fixes are done, before releasing. Refreshes everything in one pass. |
| `/release` | Detects project type and branching strategy, bumps versions everywhere, generates CHANGELOG entry, creates release commit and tag, publishes GitHub release, advises on registry publish. | When ready to cut a new version. Run `/update-docs` first. |
| `/fix-ci` | Self-healing CI: gets failure logs, spawns parallel fix agents per failure category, iterates until green or retry budget exhausted. | When CI is red. Automates the diagnose-fix-verify loop. |

The recommended daily workflow:

```
/triage -> fix all findings -> continue development
```

For multi-project orchestration, use `morning-triage.sh` to run `/triage` across all projects automatically.

The recommended pre-release sequence:

```
/pre-launch -> /remediate -> /update-docs -> /release
```

### Native Claude Code Commands Used in the Workflow

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/simplify` | Spawns 3 parallel agents (code reuse, code quality, efficiency) to review changed code and apply fixes. Anthropic-maintained. | After reviewer approval in `/implement`. After `/pre-launch` audit. Anytime after significant code changes. |
| `/batch [instruction]` | Decomposes work into 5-30 independent units, executes each in a parallel git worktree, opens a PR per unit. | For `[batch-eligible]` plan phases. Migrations, bulk refactors, multi-issue sprints. |
| `/clear` | Resets the conversation context. | Between unrelated tasks. The most underused command. |
| `/compact [focus]` | Summarizes the current conversation with a focus area. | Same task, but context is getting heavy. |
| `/worktree` | Creates an isolated git worktree for implementation. | When starting `/implement`. Keep main clean. |
| `Esc` + `Esc` | Rewinds to a previous checkpoint (restores conversation, code, or both). | When an approach fails and you want to undo. |

## How the Four Phases Actually Work

### Phase 1: Research

You type `/research how does authentication work in this app?` and the agent:

1. Spawns parallel subagents — a locator (finds WHERE relevant files are), an analyzer (understands HOW the code works), and a pattern finder (finds SIMILAR implementations elsewhere in the codebase).
2. Waits for all of them to finish.
3. Synthesizes their findings into a structured research document.
4. Saves it to `docs/research/YYYY-MM-DD-auth-flow.md`.

The critical rule here is **documentarian, not critic**. The research describes what exists — it doesn't suggest improvements or identify problems. This keeps the research factual and prevents the agent from jumping to solutions before understanding the problem.

**Your job:** Read the research document. If it's wrong or incomplete, throw it out and run `/research` again with more specific steering. Multiple passes are normal. Don't approve bad research — it poisons everything downstream.

### Phase 2: Plan

You type `/plan add rate limiting to the login endpoint` and the agent:

1. Reads the research document.
2. Explores the codebase for additional context.
3. Asks you focused questions (only things the code can't answer).
4. Proposes design options with trade-offs.
5. Writes a phased implementation plan with pseudocode, file-by-file changes, and success criteria.
6. Saves it to `docs/plans/` with separate files for each phase.

Plans use a compact pseudocode notation so you can see exactly what changes in each file without reading full code blocks. Each phase has automated success criteria — tests that prove the phase works.

**Your job:** Read the plan carefully. This is where your time has the highest leverage. A bad plan leads to hundreds of bad lines of code. Push back, ask questions, iterate until the plan is right.

### Phase 3: Implement

You type `/implement docs/plans/2026-02-21-rate-limiting.md` and the agent:

1. Reads the plan.
2. Checks for `[batch-eligible]` phases — if all remaining phases are independent, offers to use `/batch` to execute them in parallel (one worktree per phase, each opens a PR).
3. Otherwise, starts with Phase 1 only.
4. Delegates implementation to subagents, then sends the result to a reviewer subagent for **plan compliance** (does the code match the spec?).
5. Runs `/simplify` — Anthropic's native code quality pass (reuse, quality, efficiency). This catches things the plan-compliance reviewer doesn't check.
6. Runs all automated verification (tests, typecheck, lint).
7. Updates the plan's checkboxes.
8. **Stops and waits for your confirmation.**

You review, approve, and it moves to Phase 2. One phase at a time. Never auto-proceeding.

**Your job:** Confirm each phase. If something doesn't look right, say so. The cost of stopping is low; the cost of a runaway multi-phase implementation is high.

### Phase 4: Validate

You type `/validate docs/plans/2026-02-21-rate-limiting.md` and the agent:

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

The target is keeping context utilization between 40-60%. Above that, quality drops.

### The Documentarian Rule

During research, agents describe what IS — never what SHOULD BE. No improvement suggestions, no code critiques, no "this could be refactored." Just factual descriptions with file and line references.

This sounds restrictive, but it's the single most impactful rule for research quality. Without it, agents produce noisy research full of opinions that bias the planning phase.

### Error Prevention

The blueprint includes 67 operational rules learned from real sessions. These aren't theoretical — they're patterns that caused actual failures and wasted time. Examples:

- Never run verification commands in parallel (they interfere with each other)
- Always use absolute paths in worktree commands (relative paths resolve to the wrong directory)
- Run checks before committing (not after — catching errors after commit means amending, which is risky)
- Don't guess GitHub CLI field names (they change between versions — check the docs)

When your project is set up via the blueprint, these rules are baked into the CLAUDE.md file that Claude Code reads every session.

### Agent Teams

Claude Code has an experimental feature called Agent Teams that lets the main agent spawn long-running teammate agents that work in parallel. The blueprint enables this by default and provides guidance on when to use teams vs. regular subagents:

- **Subagents** (quick, focused): Read-only research, file exploration, code analysis. Seconds to minutes.
- **Agent Teams** (long-running, parallel): Independent implementation work, concurrent phase execution across packages, complex multi-file changes. Minutes to longer.

### Pre-Launch Audit

Before any production release, you can run `/pre-launch` to spawn 6 specialist agents in parallel:

1. **Architect** — Dependencies, dead code, type errors
2. **QA Lead** — Test suite, coverage, failure analysis
3. **Security Reviewer** — Vulnerabilities, secrets, injection vectors
4. **Performance Engineer** — Bundle sizes, build times, anti-patterns
5. **UX Reviewer** — Accessibility, keyboard navigation, error states
6. **DevOps** — CI status, environment variables, build verification

They all run simultaneously, read-only, and produce a combined report with a verdict: READY, CONDITIONAL, or NOT READY. No auto-fixing — you decide what to address. When findings exist, run `/remediate` to resolve them all — it creates GitHub issues, spawns parallel TDD agents in worktrees, merges sequentially, verifies CI, and runs `/simplify` twice (per-agent and final).

## Project Structure After Setup

After bootstrapping, your project will have:

```
your-project/
├── CLAUDE.md                    # Project configuration (Claude reads this every session)
├── .claude/
│   ├── settings.json            # Tool permissions, Agent Teams, hooks
│   ├── commands/                # Slash commands
│   │   ├── research.md          # /research
│   │   ├── plan.md              # /plan
│   │   ├── implement.md         # /implement
│   │   ├── validate.md          # /validate
│   │   ├── describe-pr.md       # /describe-pr
│   │   ├── pre-launch.md        # /pre-launch
│   │   ├── remediate.md         # /remediate
│   │   ├── triage.md            # /triage
│   │   ├── status.md            # /status
│   │   ├── fix-ci.md            # /fix-ci
│   │   ├── update-docs.md       # /update-docs
│   │   └── release.md           # /release
│   └── skills/                  # Domain-specific knowledge (optional)
├── docs/
│   ├── research/                # Research documents
│   ├── plans/                   # Implementation plans
│   └── decisions/               # Architecture decision records
└── ... your code ...
```

## Tips for Getting the Most Out of It

**Start every task with `/research`.** Even if you think you know the answer. The research phase takes a couple of minutes and often reveals things you didn't expect.

**Read your research and plans critically.** This is where your time has 10x leverage compared to reviewing code. A bad plan wastes hours; catching it early saves them.

**Use `/clear` liberally.** Switching tasks? `/clear`. Finished a phase? Start a new conversation. Context hygiene is the single biggest factor in output quality.

**Don't fight the phases.** It feels slower to research-then-plan-then-implement than to just say "add this feature." But the phased approach produces better results in less total time because you avoid the rework cycles that come from misunderstood requirements.

**Throw out bad research.** If the research document doesn't accurately describe the codebase, don't try to salvage it. Run `/research` again with better steering. Multiple passes are normal and expected.

**Let the agent stop between phases.** The human gates exist for a reason. Every time the agent pauses and asks for confirmation, that's your chance to course-correct before errors amplify.

**Invest in your CLAUDE.md.** This file is the highest-leverage configuration point in the entire system. Every session reads it. Craft every line manually. If removing a line wouldn't cause mistakes, remove it.

**Log your errors and successes.** When something goes wrong, write it down. When something goes perfectly, write it down. After 3 instances of the same pattern, promote it to a rule. This is how the blueprint itself was built.

## Advanced Setup

### User-Level Commands: `/bootstrap`, `/adopt`, `/update`, and `/detach`

These four commands live in `~/.claude/commands/` so they're available in every project. Install them as described in "Getting Started" above. All four reference the cc-rpi repository path — update that path in each file to match where you cloned the repo on your machine.

- **`/bootstrap`** reads the blueprint and creates everything from scratch. It asks you about your project type and stack before generating anything.
- **`/adopt`** reads the blueprint, then runs a full audit of the existing project (configuration, infrastructure, workflow) before proposing any changes. It presents a prioritized report and only migrates what you approve.
- **`/update`** pulls the latest cc-rpi, diffs changes since the last sync, and updates the project's commands, blueprint-managed CLAUDE.md sections, and settings. It tracks sync state in `.claude/cc-rpi-sync.json` so nightly runs are incremental and efficient. Works both interactively and headlessly.
- **`/detach`** cleanly removes all cc-rpi artifacts from a project. It inventories everything in four tiers (scaffolding files, CLAUDE.md sections, configuration entries, user work products), previews exactly what will be removed, asks for confirmation, then executes in a single atomic commit. Project-specific config and your research/plan documents are preserved by default. Customized files are flagged for review before deletion.

You can also run `/adopt` on a project that was previously bootstrapped — it works as a health check to verify everything is still aligned with the latest blueprint practices.

### Nightly Blueprint Sync

The `/update` command is designed to run as a scheduled agent. Set it up once per project:

1. Copy `templates/scripts/cc-rpi-update-agent.sh` to your project's `scripts/agents/`
2. Set the `CC_RPI_PATH` variable to your cc-rpi clone location
3. Schedule it with launchd (macOS) or cron (Linux) — the script has templates in its comments

The shell script reads update instructions from cc-rpi at runtime, so when you improve the `/update` command in cc-rpi, all projects automatically get the new logic on their next scheduled run.

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
| CI ownership | `methodology/push-accountability.md` | Background CI monitoring, fix-and-repush |
| Error patterns | `patterns/agent-errors.md` | 60 documented errors with symptoms and solutions |
| Operational rules | `patterns/quick-reference.md` | 67 rules to prevent known mistakes |
| Deployment safety | `patterns/deployment-safety.md` | Resource efficiency and production deployment rules |
| Worked examples | `examples/README.md` | Sample research docs, plans, logs, pseudocode |

## Credits

The RPI methodology is adapted from HumanLayer's opencode-rpi implementation and their ACE-FCA (Advanced Context Engineering for Coding Agents) framework, tailored for Claude Code's native capabilities.
