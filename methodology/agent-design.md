# Agent Design Principles

## The Documentarian Rule

Every research-phase agent follows one absolute constraint:

> **Describe what EXISTS. Never suggest what SHOULD BE.**

This means:
- No improvement suggestions
- No problem identification
- No root cause analysis (unless explicitly asked)
- No code quality commentary
- No performance concerns
- No security warnings
- No refactoring recommendations
- No "better approaches"

**Why:** Research agents that mix observation with opinion produce noisy, biased output. Keeping them purely descriptive ensures the human gets clean, factual data to make their own decisions.

### Good vs Bad Examples

**Authentication research — GOOD (describes what IS):**
> The login endpoint at `src/auth/login.ts:8` accepts email and password in the request body. Passwords are hashed with bcrypt at cost factor 12 (`src/auth/password.ts:6`). There is no rate limiting middleware on this route — requests go directly from the router to the handler. The test suite covers 12 cases for login (`tests/auth/login.test.ts`) and 0 cases for logout.

**Same topic — BAD (suggests what SHOULD BE):**
> The login endpoint lacks rate limiting, which is a security vulnerability that should be addressed. The bcrypt cost factor of 12 is adequate but could be increased to 14 for better security. The test coverage is poor — the logout flow has no tests and needs them urgently.

**Why the bad version is harmful:**
- "Security vulnerability" is a judgment, not an observation. The human may already know and have reasons.
- "Could be increased to 14" is a recommendation the human didn't ask for.
- "Poor" and "urgently" are opinions that bias the human before they've formed their own assessment.
- The good version gives the same facts — the human can draw the same conclusions themselves.

**Database patterns — GOOD:**
> Queries use the repository pattern. `UserRepository` at `src/repos/user.ts:12` wraps Prisma calls. All read queries go through `findUnique` or `findMany` (lines 15-48). Write queries use `prisma.$transaction` (lines 52-78). There are 3 raw SQL queries in `src/repos/analytics.ts:20-45` that bypass the repository pattern.

**Same topic — BAD:**
> The repository pattern is used inconsistently — most queries go through the proper abstraction but there are 3 raw SQL queries in analytics that break the pattern and should be refactored to use the repository. The transaction handling is good but could benefit from a shared helper.

**API research — GOOD:**
> The `/api/orders` endpoint returns all orders for the authenticated user with no pagination. The response includes the full order object with nested line items. Average response size for a user with 50 orders is approximately 45KB based on the schema at `src/types/order.ts:8-32`.

**Same topic — BAD:**
> The orders endpoint has a performance problem — it returns all orders without pagination, which will cause issues at scale. The response is bloated because it includes nested line items that could be loaded lazily. This should be refactored to add pagination and sparse fieldsets.

## Tool Restrictions by Role

| Role | Can Read/Search | Can Write/Edit | Can Run Shell | Can Access Web |
|------|:-:|:-:|:-:|:-:|
| Codebase Locator | Yes | No | No | No |
| Codebase Analyzer | Yes | No | No | No |
| Pattern Finder | Yes | No | No | No |
| Docs Locator | Yes (no deep reads) | No | No | No |
| Docs Analyzer | Yes | No | No | No |
| Web Researcher | Yes | No | No | Yes |
| Implementer | Yes | Yes | Yes | No |
| Reviewer | Yes | Yes (plan edits only) | Yes (tests only) | No |

**In Claude Code terms:** When spawning Task agents for research, instruct them to only use Glob, Grep, and Read tools. When spawning implementers, they get the full tool set.

## Subagent Prompting Best Practices

1. **Be specific about what to search for**, not how to search. The agent knows its tools.
2. **Specify the output format** you expect.
3. **Remind agents of the documentarian constraint** in every research prompt.
4. **Request file:line references** in every response.
5. **Spawn multiple agents in parallel** when they search for independent things.
6. **Wait for ALL agents** before synthesizing.
7. **Verify subagent results** — if something seems off, spawn a follow-up.

---

## Subagent Catalog

### Quick Reference

All subagent roles mapped to Claude Code's `Task` tool parameters:

| Role | `subagent_type` | Phase | Can Write | Purpose |
|------|-----------------|-------|-----------|---------|
| Codebase Locator | `Explore` | Research | No | Find WHERE files live |
| Codebase Analyzer | `Explore` | Research | No | Understand HOW code works |
| Pattern Finder | `Explore` | Research | No | Find EXAMPLES of similar patterns |
| Docs Locator | `Explore` | Research | No | Find relevant historical docs |
| Docs Analyzer | `Explore` or `general-purpose` | Research | No | Extract INSIGHTS from docs |
| Web Researcher | `general-purpose` | Research | No | Find external documentation |
| Implementer | `general-purpose` | Implement | Yes | Write code per plan |
| Reviewer | `general-purpose` | Implement | Yes (tests/plan only) | Review plan compliance |
| Specialist (audit) | `general-purpose` | Pre-launch | No | Domain-specific audit (security, performance, etc.) |
| Teammate | Agent Teams (native) | Any | Yes | Independent parallel worker with own context |
| `/simplify` (native) | Anthropic skill | Implement, Validate, Pre-launch | Yes | 3 parallel agents: code reuse, code quality, efficiency |
| `/batch` (native) | Anthropic skill | Implement, Standalone | Yes | Decompose work into 5-30 units, parallel worktree execution |

**Key distinctions:**
- `Explore` agents are fast, read-only, and optimized for codebase navigation. Use for all research tasks.
- `general-purpose` agents have full tool access including web search. Use when the task needs writing, shell commands, or web access.
- `Bash` agents are command-execution specialists. Use for CI monitoring, build scripts, and shell-heavy tasks.
- **Teammates** (via Agent Teams) are full independent Claude Code sessions, not subagents. They don't inherit conversation history and communicate via mailbox.

### Anthropic-Native Commands

These are bundled slash commands maintained by Anthropic. They improve automatically with Claude Code updates — prefer them over custom equivalents.

#### `/simplify`

**Purpose:** Review changed code for reuse, quality, and efficiency, then fix issues found.

**Mechanics:** Spawns 3 parallel review agents — one for code reuse, one for code quality, one for efficiency. Aggregates findings and applies fixes automatically. Optional focus text: `/simplify focus on memory efficiency`.

**Where it runs in RPI:**
- **Implement (Phase 3)** — after the reviewer subagent approves plan compliance, before automated verification. This separates concerns: reviewer checks "does the code match the plan?", `/simplify` checks "is the code good?"
- **Pre-launch** — after the audit report, as the first fix action for code quality blockers/warnings
- **Validate (Phase 4)** — when code quality findings surface
- **Standalone** — anytime after significant code changes

**Relationship to our reviewer subagent:** Complementary, not a replacement. The reviewer checks plan compliance (did you implement what was specified?). `/simplify` checks code quality (is the implementation clean?). Run the reviewer first, then `/simplify`.

#### `/batch`

**Purpose:** Orchestrate large-scale parallel changes across a codebase.

**Mechanics:** Takes an instruction, researches the codebase, decomposes work into 5-30 independent units, presents a plan for approval. Once approved, spawns one background agent per unit in an isolated git worktree. Each agent implements its unit, runs tests, and opens a PR. Requires a git repository.

**Where it runs in RPI:**
- **Implement (Phase 3)** — when the plan marks phases as `[batch-eligible]` (independent, no file overlap, no dependency on another phase's output), `/batch` executes them all in parallel instead of sequential phase-by-phase
- **Standalone** — for migrations, bulk refactors, multi-issue sprints, and any parallelizable work that doesn't need the full RPI cycle (e.g., `/batch migrate all test files from Jest to Vitest`)

**Relationship to Agent Teams:** `/batch` is higher-level. It handles decomposition, worktree isolation, and PR creation automatically. Agent Teams give you lower-level control (shared task list, direct messaging between agents). Use `/batch` when the work is clearly decomposable; use Agent Teams when agents need to coordinate.

---

### Detailed Role Definitions

### Codebase Locator

**Purpose:** Find WHERE files live. A "super find/grep" — given a topic or feature, returns all relevant file paths grouped by purpose.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding file locations.

**Output:** Organized list of files by category (implementation, tests, config, types, docs) with full paths and counts.

**Does NOT:** Read file contents, analyze code, critique organization.

### Codebase Analyzer

**Purpose:** Understand HOW code works. Traces data flow, explains implementation, maps component interactions.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on reading and explaining specific files/components.

**Output:** Structured analysis with entry points, core implementation breakdown, data flow trace, patterns, configuration, and error handling — all with `file:line` references.

**Does NOT:** Suggest improvements, identify problems, comment on quality.

**Analysis strategy:**
1. Read entry points (exports, public methods, route handlers).
2. Follow the code path step by step.
3. Document the logic as-is.

### Pattern Finder

**Purpose:** Find EXAMPLES of similar implementations. Shows concrete code snippets that can serve as templates.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding similar patterns with code examples.

**Output:** Code snippets with file:line references, usage context, variations, and testing examples.

**Does NOT:** Recommend one pattern over another, identify anti-patterns, suggest improvements.

**Pattern categories to search:**
- API patterns (routes, middleware, errors, auth, validation, pagination)
- Data patterns (queries, caching, transformation, migrations)
- Component patterns (organization, state, events, lifecycle)
- Testing patterns (unit, integration, mocks, assertions)

### Docs Locator

**Purpose:** Find relevant historical documents (plans, research, tickets, decisions).

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding markdown docs by topic.

**Output:** Categorized list of document paths with one-line descriptions.

**Does NOT:** Read documents deeply, analyze content.

### Docs Analyzer

**Purpose:** Extract HIGH-VALUE insights from historical documents. Aggressive filtering — only returns what's actionable and current.

**Claude Code:** `Task` with `subagent_type: "Explore"` or `subagent_type: "general-purpose"`.

**Output:** Document context, key decisions (with rationale), critical constraints, technical specs, actionable insights, open questions, relevance assessment.

**Filtering rules — include only if:**
- Answers a specific question
- Documents a firm decision
- Reveals a non-obvious constraint
- Provides concrete technical details
- Warns about a real gotcha

**Exclude if:**
- Just exploring possibilities
- Personal musing without conclusion
- Clearly superseded
- Too vague to act on
- Redundant with better sources

### Web Researcher

**Purpose:** Find external documentation, best practices, and solutions from the web.

**Claude Code:** `Task` with `subagent_type: "general-purpose"` using WebSearch and WebFetch tools.

**Search strategies by query type:**
- **API/Library docs:** Official docs first, then changelogs and release notes.
- **Best practices:** Recent articles from recognized experts, cross-reference multiple sources.
- **Technical solutions:** Specific error messages in quotes, Stack Overflow, GitHub issues.
- **Comparisons:** "X vs Y", migration guides, benchmarks.

**Output:** Summary, detailed findings organized by source with attribution and links, additional resources, gaps.

---

## Git Protocol for Multi-Agent Work

When multiple agents operate in parallel (sub-agents, teammates, or `/batch` units), git operations are the primary source of conflicts. These rules prevent wrong-branch pushes, merge conflicts, and orphaned references.

### Central Commit Rule

**Only the orchestrating agent (main session or team lead) handles git commit and push.** Sub-agents and teammates write code but do not commit.

| Agent Role | Can Edit Files | Can git commit | Can git push |
|------------|:-:|:-:|:-:|
| Main session / Team lead | Yes | Yes | Yes |
| Sub-agent (Task tool) | Yes | No | No |
| Worktree agent (`isolation: "worktree"`) | Yes | Yes (local only) | No — main agent batches |
| Teammate (Agent Teams) | Yes | No — write to task output | No |
| `/batch` unit | Yes (in worktree) | Yes (isolated branch) | Yes (opens PR) |

`/batch` is the exception — it creates isolated worktrees with their own branches, so each unit can safely commit and push without conflicts.

### Branch Verification Before Every Commit

Before any `git commit`, the agent must run `git branch --show-current` and verify the result matches the intended target. This applies even when the user said "push to develop" earlier in the conversation — git state is the source of truth, not conversation memory.

The `guard-bash.sh` hook blocks `git push origin main/master` as a last line of defense, but verification should happen before the commit, not after.

### File Ownership for Parallel Agents

When spawning parallel agents, assign distinct file sets to each:

```
Agent 1: src/auth/*.ts, tests/auth/*.ts
Agent 2: src/api/*.ts, tests/api/*.ts
Agent 3: src/utils/*.ts, tests/utils/*.ts
```

If two agents must touch the same file, run them sequentially or have the second agent read the first agent's output before starting.

### Branch Strategy for Agent Orchestration

For complex multi-agent work beyond `/batch`:

1. Each agent creates a branch: `agent/<task-slug>`
2. Each agent completes work with passing tests on its branch
3. The orchestrator merges agent branches into the target branch sequentially
4. After each merge, run the full test suite — if it breaks, fix before proceeding
5. Delete agent branches after successful merge

This pattern is more complex than central commit but necessary when agents need full git access (e.g., agents running in separate worktrees).

### Parallel Agent Push Strategy

When N agents each push independently, every push triggers M workflow runs (CI matrix + auxiliary workflows like Dependency Review, CodeQL). For 8 agents x 4 workflows = 32 workflow runs, most of which queue simultaneously and compete for runner minutes. On macOS runners (10x cost multiplier), this burns through Actions minutes fast.

**Strategy: agents commit locally, main agent pushes in batch.**

| Step | Who | What |
|------|-----|------|
| 1. Spawn | Main agent | Creates worktrees — each agent gets its own branch via `git worktree add` or `isolation: "worktree"` |
| 2. Implement | Worktree agents | Write code, run tests, commit — but never push or create PRs. Deliverable is a local commit on their branch |
| 3. Review | Main agent | Verifies each worktree has clean commits. Optionally runs cross-branch checks (type conflicts, shared file edits) |
| 4. Push | Main agent | Pushes all branches in one burst: `git push origin branch-1 branch-2 ... branch-N` |
| 5. PRs | Main agent | Creates all PRs sequentially via `gh pr create`, linking to corresponding issues |
| 6. Monitor | Background agent | Watches all CI runs: `gh run list --branch branch-1 --branch branch-2 ... --limit N`. If any fail, main agent fixes and re-pushes just that branch |

**Why it matters:**

| Approach | Pushes | CI triggers | Risk |
|----------|--------|-------------|------|
| Each agent pushes | N x retries | N x M x retries | Wrong-branch pushes, merge conflicts |
| Main agent batches | N (once) | N x M (once) | None — single point of control |

**Key benefits:**

- Fewer CI runs — agents debugging locally don't trigger CI on every attempt
- Lower API usage — no redundant GitHub API calls from parallel agents
- No wrong-branch pushes — only the main agent touches remote
- No merge conflicts — main agent can detect shared-file edits before pushing
- Cheaper GitHub Actions minutes — especially on macOS runners (10x cost multiplier)

---

## Claude Code Extension Points

Beyond subagent prompting, Claude Code provides three mechanisms for extending agent capabilities. These map to different levels of the progressive disclosure hierarchy (see [context-engineering.md](context-engineering.md)).

### Skills (`.claude/skills/`)

Skills are on-demand knowledge files that Claude loads when relevant, without bloating every conversation. Use skills for domain knowledge, API conventions, and reusable workflows.

```
.claude/skills/
├── api-conventions/
│   └── SKILL.md          # REST API patterns for this project
├── database-patterns/
│   └── SKILL.md          # Query patterns, migration conventions
└── fix-issue/
    └── SKILL.md          # Workflow: analyze and fix a GitHub issue
```

**SKILL.md format:**
```markdown
---
name: api-conventions
description: REST API design conventions for our services
---
# API Conventions
- Use kebab-case for URL paths
- Use camelCase for JSON properties
- Always include pagination for list endpoints
```

**When to use skills vs CLAUDE.md:**
- Universal across ALL tasks → CLAUDE.md
- Relevant to specific task types → Skills
- Workflow with side effects the user triggers manually → Skill with `disable-model-invocation: true`

Invoke skills with `/skill-name` or let Claude auto-detect relevance from the `description` field.

### Custom Agent Definitions (`.claude/agents/`)

Define reusable subagent specs with their own tool restrictions and model selection. These formalize the subagent catalog entries above into Claude Code's native format.

```markdown
# .claude/agents/security-reviewer.md
---
name: security-reviewer
description: Reviews code for security vulnerabilities
tools: Read, Grep, Glob, Bash
model: opus
---
You are a senior security engineer. Review code for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication and authorization flaws
- Secrets or credentials in code
- Insecure data handling

Provide specific line references and suggested fixes.
```

This maps directly to the tool restriction table above — the `tools` field enforces what each agent can access. Use custom agents for recurring review patterns, specialized analysis, or any task that benefits from isolated context with constrained tools.

### Hooks

Hooks are deterministic scripts that run automatically at specific points in Claude's workflow. Unlike CLAUDE.md instructions (which are advisory), hooks are **guaranteed** to execute.

**Common hook patterns:**
- **Stop hook on file edit** — Run formatter/linter after every file change. Claude sees the errors and fixes them.
- **Stop hook on commit** — Run typecheck/lint before the commit is created.
- **Notification hook** — Alert when a long task completes.

**Hooks vs CLAUDE.md instructions:**
- "Always run lint after editing" in CLAUDE.md → Claude might forget. Use a hook.
- "Prefer small functions" → Advisory guidance stays in CLAUDE.md.

Configure hooks in `.claude/settings.json` or use the `/hooks` command. Claude can write hooks for you: "Write a hook that runs eslint after every file edit."

---

## Agent Team Patterns

Beyond individual subagents, teams of parallel agents can tackle complex multi-domain problems. Each team member investigates independently, then results are synthesized.

### When to Use Teams

| Scenario | Team Shape | Example |
|----------|-----------|---------|
| **Debugging** | 3-5 parallel investigators, each testing a different hypothesis | API, cache, rendering, config, dependencies |
| **Pre-launch audit** | 6 parallel specialists, each auditing one domain | QA, security, architecture, performance, UX, infrastructure |
| **Self-healing pipeline** | Audit phase (parallel) → fix phase (parallel) → verify phase | Lint, tests, a11y, security, bundle size |
| **Health check** | 4 parallel checkers with optional auto-fix | Tests, code quality, CI health, dependency health |
| **Feature implementation** | Sequential workflow with parallel sub-steps | Read issue → TDD → implement → docs (parallel) → CI verify |
| **Code review** | 2-3 parallel reviewers with different lenses | Correctness, security, performance |

### Team Design Principles

1. **Read-only auditors.** Audit/investigation agents should never modify files — they report findings. A separate fix step (human or agent) acts on the report.
2. **Parallel by default.** If agents don't need each other's output, run them simultaneously. Time savings compound.
3. **Synthesize before acting.** Collect all agent findings into a single report before deciding what to fix. Prevents conflicting changes.
4. **Self-healing fallback.** If a sub-agent fails due to permissions or tool errors, the parent agent takes over manually using its own tools.
5. **Retry budget.** Failed agents get one retry with modified instructions. After that, report the failure and move on.
6. **Cross-agent recommendations.** Each agent should note findings that affect another agent's domain (e.g., security reviewer flagging a performance concern).

### Pre-Launch Audit Template

The most common team pattern. Spawn 6 parallel specialists before any production release:

| Specialist | Focus |
|------------|-------|
| **architect** | Dependency health, TypeScript config, circular deps, dead code |
| **qa-lead** | Full test suite, coverage gaps, graceful degradation |
| **security-reviewer** | Dependency audit, hardcoded secrets, auth flows, injection vectors |
| **performance-eng** | Bundle sizes, unused exports, code splitting, Core Web Vitals |
| **ux-reviewer** | ARIA/a11y, keyboard nav, error states, design consistency |
| **devops** | Build verification, CI status, env vars, error pages, git state |

Each produces findings categorized as **blockers** (must fix), **warnings** (should fix), or **recommendations** (nice to have). Results synthesize into a single report with a verdict: READY, CONDITIONAL, or NOT READY.

See [templates/commands/pre-launch.md](../templates/commands/pre-launch.md) for the slash command that triggers this team.

---

## Claude Code Agent Teams (Native Feature)

Claude Code has a native Agent Teams feature that implements the patterns above as a first-class capability. It is experimental and disabled by default — all cc-rpi projects enable it via `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### Architecture

| Component | Role |
|-----------|------|
| **Team lead** | The main Claude Code session. Creates the team, spawns teammates, coordinates work. |
| **Teammates** | Independent Claude Code instances, each with their own context window. |
| **Task list** | Shared work items that teammates claim and complete. Supports dependencies. |
| **Mailbox** | Direct messaging between any agents (not just back to the lead). |

### Teams vs Subagents

| Aspect | Subagents (Task tool) | Agent Teams |
|--------|----------------------|-------------|
| **Context** | Own window; results return to caller | Own window; fully independent |
| **Communication** | Report back to parent only | Message each other directly |
| **Coordination** | Parent manages all work | Shared task list with self-coordination |
| **Best for** | Focused tasks where only the result matters | Complex work requiring discussion and collaboration |
| **Token cost** | Lower (results summarized back) | Higher (each teammate is a separate instance) |

**Rule of thumb:** Use subagents for research and review. Use teams for implementation work that spans multiple files or domains.

### Best Practices

1. **Include full context in spawn prompts** — teammates don't inherit the lead's conversation history. They do read `CLAUDE.md`, skills, and MCP servers from the project.
2. **Break work by file ownership** — each teammate should own a distinct set of files to avoid merge conflicts.
3. **Size tasks appropriately** — aim for 5-6 tasks per teammate. Too small = coordination overhead exceeds benefit. Too large = risk of wasted effort.
4. **Pre-approve common operations** in `.claude/settings.json` permissions to reduce prompt interruptions for teammates.
5. **Start with research/review before implementation** — parallel review first, then parallel implementation.
6. **Monitor and steer** — check in on teammate progress, redirect approaches that aren't working.

### Display Modes

- **`in-process`** (default) — all teammates run in main terminal. Cycle with Shift+Down, toggle task list with Ctrl+T.
- **`tmux`** — split-pane mode, one pane per teammate. Requires tmux or iTerm2.

Configure via `settings.json`: `"teammateMode": "in-process"` or CLI: `claude --teammate-mode tmux`.

### Hooks for Quality Gates

- **`TeammateIdle`** — runs when a teammate finishes. Exit code 2 sends feedback and keeps the teammate working.
- **`TaskCompleted`** — runs when a task is marked complete. Exit code 2 blocks completion and sends feedback.

### Limitations

- No session resumption with in-process teammates (`/resume` won't restore them)
- One team per session; no nested teams (teammates can't spawn their own teams)
- Teammates sometimes fail to mark tasks complete — check manually if dependent tasks are blocked
- Significantly higher token usage — scales with number of active teammates

---

## Agent Autonomy Principles

Agents should maximize what they accomplish autonomously before requesting human intervention.

### The Tool Exhaustion Rule

**Before asking the user to perform any manual step, exhaust all available tools first.**

1. **CLI tools** — `gh`, `git`, project-specific CLIs
2. **Shell commands** — `curl`, `pnpm`, build scripts
3. **MCP servers** — check what tools are available in the session
4. **Web tools** — `WebSearch`, `WebFetch` for documentation
5. **File tools** — Read/Edit/Write for configuration changes

Only ask for manual intervention when genuinely required: OAuth consent flows, billing dashboards, hardware interaction, or actions that require elevated privileges the agent doesn't have.

### Autonomy Boundaries

#### The Function Stakes Framework

Classify every action by its risk level to determine autonomy:

| Stakes | Examples | Autonomy |
|--------|----------|----------|
| **Read-only** | Searching code, reading files, running tests, `git status`, `git log` | Fully autonomous |
| **Low** | Writing code per approved plan, creating branches, committing to feature branches | Fully autonomous |
| **Medium** | Pushing to `develop`, creating PRs, running `npm install` | Autonomous with post-action verification |
| **High** | Merging PRs, pushing to `main`/production, deploying, modifying external services | Human-gated — always ask first |
| **Critical** | Deleting branches, force-pushing, dropping databases, modifying CI/CD pipelines | Human-gated — explain consequences before asking |

#### Precise Boundaries

| Action | Autonomous? | Why |
|--------|------------|-----|
| Searching/reading code | Yes | Read-only, zero risk |
| Running tests and linters | Yes | Read-only verification |
| Writing code per approved plan | Yes | Plan was already human-approved |
| Creating git branches | Yes | Reversible, local scope |
| Committing to feature branches | Yes | Reversible, local scope |
| Pushing to `develop` | Yes, with CI monitor | Medium risk; background agent verifies |
| Creating PRs | Yes | PR creation is proposing, not acting |
| Adding PR descriptions | Yes | Informational, not destructive |
| Merging PRs to `develop` | Ask first | Affects shared branch |
| Merging PRs to `main`/production | Always ask | Affects production |
| Deploying to any environment | Always ask | External side effects |
| Modifying CI/CD workflows | Always ask | Affects all contributors |
| Deleting branches or worktrees | Ask if remote | Local cleanup is fine; remote deletion is permanent |

#### The Quality Cascade Principle

Human review belongs at the highest-leverage points. A bad line of research can lead to a bad plan, which leads to hundreds of bad lines of code. Therefore:

1. **Research output** — Human reviews critically. Throw out and redo if wrong.
2. **Implementation plan** — Human reviews and approves before any code is written.
3. **Generated code** — Automated verification (tests, types, lint) is primary. Human spot-checks.

Invest review time at the top of the cascade, not the bottom. Once a plan is approved and tests pass, the code is trusted.

#### Time-Bounded Autonomy

For scheduled or background agents, use time limits as a safety boundary. An agent running for 15 minutes autonomously is reasonable; an agent running for 6 hours without check-in risks "overbaking" — producing increasingly bizarre emergent behaviors as it goes further off-track.

See [push-accountability.md](push-accountability.md) for the post-push verification protocol and [scheduled-agents.md](scheduled-agents.md) for recurring agent patterns.

### Self-Correction Over Escalation

When an agent encounters an error:
1. **Diagnose** — read the error, understand the root cause
2. **Fix** — attempt the fix using available tools
3. **Verify** — run the relevant checks to confirm the fix works
4. **Escalate only if stuck** — after 3 failed attempts, report the issue clearly and ask for guidance

Don't ask "should I fix this?" — just fix it. Don't suggest the user run a command you could run yourself.
