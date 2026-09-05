# Agent Design Principles

## The Documentarian Rule

Every `rpi-research` assignment follows the descriptive constraint below.
Use `rpi-assess` for evaluative investigation, comparisons and alternatives,
with evidence clearly distinguished from judgment:

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

The table describes role permissions, not a fixed provider tool list. Read-only
shell inspection is allowed when needed to answer an investigation; grant
implementers only the actions needed for their bounded assignment. Use the
current native tool schema rather than copying legacy spawn parameters.

## Subagent Prompting Best Practices

1. **Be specific about what to search for**, not how to search. The agent knows its tools.
2. **Specify the output format** you expect.
3. **Remind agents of the documentarian constraint** in every research prompt.
4. **Request file:line references** in every response.
5. **Delegate only when useful** for independent questions within the current phase; narrow work may stay with the parent.
6. **Resolve all required results** before final synthesis; missing results are coverage gaps.
7. **Verify subagent results** — if something seems off, spawn a follow-up.

---

## Subagent Catalog

### Quick Reference

These are responsibility options, not fixed model instances or native type names:

| Role | Phase | Permitted output | Purpose |
|------|-------|------------------|---------|
| Codebase Locator | Research | Read-only findings | Find WHERE files live |
| Codebase Analyzer | Research | Read-only findings | Understand HOW code works |
| Pattern Finder | Research | Read-only findings | Find similar implementations |
| Docs Locator / Analyzer | Research | Read-only findings | Locate and interpret historical evidence |
| Web Researcher | Research / Assess | Sourced findings | Verify current primary sources and label inferences |
| Implementer | Implement | Assigned files and tests | Execute the current phase contract |
| Reviewer | Implement | Findings and assigned test evidence | Independently verify plan compliance |
| Audit specialist | Pre-launch | Domain findings | Cover the assigned required audit domains |

Every assignment states objective, permitted actions, owned files, evidence/output,
resource budget and terminal condition. The parent may cover a narrow task;
otherwise use only useful independent assignments. At most three simultaneous
implementers are allowed, with lower native/resource limits taking precedence.
Inherit the owner session's model and effort by omitting native overrides unless
an explicit owner selection applies. Optional Agent Teams require existing opt-in.

### Anthropic-Native Commands

These are bundled slash commands maintained by Anthropic. They improve automatically with Claude Code updates — prefer them over custom equivalents.

#### `/simplify`

**Purpose:** Review changed code for reuse, quality, and efficiency, then fix issues found.

**Contract:** Review reuse, quality and efficiency independently, aggregate
findings and apply behavior-preserving fixes. Native staffing is version-specific;
the three lenses do not require three instances. Codex uses `codex-simplify`.
Standalone cleanup reruns invalidated checks; parent-owned cleanup returns exact
changed scope and invalidated evidence to the parent acceptance gate.

**Where it runs in RPI:**
- **Implement (Phase 3)** — after the reviewer subagent approves plan compliance, before automated verification. This separates concerns: reviewer checks "does the code match the plan?", `/simplify` checks "is the code good?"
- **Pre-launch** — after the audit report, as the first fix action for code quality blockers/warnings
- **Validate (Phase 4)** — when code quality findings surface
- **Standalone** — anytime after significant code changes

**Relationship to our reviewer subagent:** Complementary, not a replacement. The reviewer checks plan compliance (did you implement what was specified?). `/simplify` checks code quality (is the implementation clean?). Run the reviewer first, then `/simplify`.

#### `/batch`

**Purpose:** Orchestrate large-scale parallel changes across a codebase.

**Contract:** Bound independent assignments to the current approved phase,
distinct files/worktrees and available resources, with at most three implementers.
One owner integrates local results. Native batch behavior must honor these limits
and disable automatic push/PR behavior; otherwise use local worktrees directly.
Existing scope approval is sufficient; no fixed unit count or repeated gate.

**Where it runs in RPI:**
- **Implement (Phase 3)** — when the plan marks phases as `[batch-eligible]` (independent, no file overlap, no dependency on another phase's output), `/batch` executes them all in parallel instead of sequential phase-by-phase
- **Standalone** — for migrations, bulk refactors, multi-issue sprints, and any parallelizable work that doesn't need the full RPI cycle (e.g., `/batch migrate all test files from Jest to Vitest`)

**Relationship to Agent Teams:** `/batch` is higher-level. Use its decomposition and worktree isolation only when publication can be disabled; otherwise orchestrate local worktrees directly. Agent Teams give you lower-level control (shared task list, direct messaging between agents). Use `/batch` when the work is clearly decomposable; use Agent Teams when agents need to coordinate.

---

### Detailed Role Definitions

### Codebase Locator

**Purpose:** Find WHERE files live. A "super find/grep" — given a topic or feature, returns all relevant file paths grouped by purpose.

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

**Output:** Organized list of files by category (implementation, tests, config, types, docs) with full paths and counts.

**Does NOT:** Read file contents, analyze code, critique organization.

### Codebase Analyzer

**Purpose:** Understand HOW code works. Traces data flow, explains implementation, maps component interactions.

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

**Output:** Structured analysis with entry points, core implementation breakdown, data flow trace, patterns, configuration, and error handling — all with `file:line` references.

**Does NOT:** Suggest improvements, identify problems, comment on quality.

**Analysis strategy:**
1. Read entry points (exports, public methods, route handlers).
2. Follow the code path step by step.
3. Document the logic as-is.

### Pattern Finder

**Purpose:** Find EXAMPLES of similar implementations. Shows concrete code snippets that can serve as templates.

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

**Output:** Code snippets with file:line references, usage context, variations, and testing examples.

**Does NOT:** Recommend one pattern over another, identify anti-patterns, suggest improvements.

**Pattern categories to search:**
- API patterns (routes, middleware, errors, auth, validation, pagination)
- Data patterns (queries, caching, transformation, migrations)
- Component patterns (organization, state, events, lifecycle)
- Testing patterns (unit, integration, mocks, assertions)

### Docs Locator

**Purpose:** Find relevant historical documents (plans, research, tickets, decisions).

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

**Output:** Categorized list of document paths with one-line descriptions.

**Does NOT:** Read documents deeply, analyze content.

### Docs Analyzer

**Purpose:** Extract HIGH-VALUE insights from historical documents. Aggressive filtering — only returns what's actionable and current.

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

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

**Native binding:** Choose an available agent/tool using the current harness schema and the role permissions above.

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

**One integration owner handles shared-worktree commits and publication.**
Other agents write only their assigned files. An explicitly assigned isolated
worktree agent may create local commits; it never pushes its working branch.

| Agent Role | Can Edit Files | Can git commit | Can git push |
|------------|:-:|:-:|:-:|
| Main session / Team lead | Yes | Yes | Completed integration branch once, when authorized |
| Sub-agent (Task tool) | Yes | No | No |
| Isolated worktree agent | Yes | Yes (local only) | No |
| Teammate (Agent Teams) | Yes | No — write to task output | No |
| `/batch` unit | Yes (in worktree) | Yes (local isolated branch) | No |

No agent is exempt from the owner remote budget. Working branches and worktrees stay local; the orchestrator integrates and fully verifies before the single authorized integration push. Never create Vercel Previews.

### Branch Verification Before Every Commit

Before any `git commit`, the agent must run `git branch --show-current`
and verify the result matches the intended target. This applies even
when the user said "push to the integration branch" earlier in the
conversation — git state is the source of truth, not conversation
memory.

The `guard-bash.sh` hook should block direct pushes to protected
production branches as a last line of defense, but verification should
happen before the commit, not after.

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
5. Remove only task-owned branches/worktrees after verifying integration and preserving plans, handoffs, ignored evidence and untracked work; retain anything uncertain

This pattern is more complex than central commit but necessary when agents need full git access (e.g., agents running in separate worktrees).

### Parallel Agent Push Strategy

Agents commit locally. The orchestrator reviews each branch, integrates completed
work locally, and verifies the complete result before any publication.

| Step | Who | What |
|------|-----|------|
| 1. Spawn | Orchestrator | Assign bounded tasks with distinct file ownership and local worktrees where needed |
| 2. Implement | Worktree agents | Write, test and commit locally; no push or PR creation |
| 3. Integrate | Orchestrator | Review and integrate local commits sequentially, resolving failures locally |
| 4. Verify | Orchestrator | Run full applicable local CI selection, coverage, typechecks, lint, build and preflight |
| 5. Publish | Orchestrator | Inspect triggers; push only completed integration once when authorized; no Vercel Previews |
| 6. Monitor | Assigned monitor | Inspect expected runs for the pushed commit; diagnose failures locally without rerun/re-push loops |

A batch push of many branches still triggers work for each branch. Local
integration followed by one completed push avoids those paid experimental runs.
Production publication remains a separate explicitly authorized action.

### Scope Discipline and the Watchdog

The most expensive multi-agent failure is not a wrong fix — it is a **runaway
agent** that keeps working after its job is done, or a **duplicate agent** that
redoes work a sibling already committed. Both burn hours and tokens silently.

Three orchestrator obligations prevent it:

| Obligation | Rule |
|------------|------|
| **Scoped assignment** | State objective, permitted actions, owned files, evidence/output, resource budget and an explicit terminal condition. Investigations need a question and coverage boundary. |
| **Progress budget** | Choose checkpoints and resource limits from the task. At a missed checkpoint, inspect progress and coordinate ownership before interrupting; preserve partial work and unresolved evidence. No universal timeout proves an agent is stuck. |
| **Dedup gate** | Before an agent does or continues work, it checks real repo state (`git log`, `git status`, `grep` for the artifact). If the work already landed on the branch, it stops and reports instead of producing a duplicate. |

This pairs with the central-commit pattern: the main agent owns the watchdog
because it owns the merge. A worktree agent cannot see its siblings — so the
orchestrator, not the agent, is responsible for noticing redundant work.

---

## Claude Code Extension Points

Beyond subagent prompting, Claude Code provides three mechanisms for extending agent capabilities. These map to different levels of the progressive disclosure hierarchy (see [context-engineering.md](context-engineering.md)).

### Skills (`.claude/skills/`)

Skills are on-demand knowledge that Claude loads when relevant, without bloating every conversation. A skill is a **folder**, not just a markdown file — it can include scripts, reference code, assets, templates, and data that the agent discovers and uses.

**When to use skills vs CLAUDE.md:**
- Universal across ALL tasks → CLAUDE.md
- Relevant to specific task types → Skills
- Workflow with side effects the user triggers manually → Skill with `disable-model-invocation: true`

Invoke skills with `/skill-name` or let Claude auto-detect relevance from the `description` field.

#### Skill Folder Structure

```
.claude/skills/
├── api-conventions/
│   ├── SKILL.md              # Entry point — loaded when skill activates
│   ├── references/
│   │   ├── endpoints.md      # Full endpoint catalog
│   │   └── error-codes.md    # Error code reference
│   └── examples/
│       └── pagination.ts     # Reference implementation
├── checkout-verifier/
│   ├── SKILL.md              # Verification workflow instructions
│   └── scripts/
│       ├── run-checkout.sh   # Drives the checkout flow
│       └── assert-state.py   # Programmatic state assertions
└── new-migration/
    ├── SKILL.md              # Migration scaffolding instructions
    └── assets/
        └── template.sql      # Migration file template to copy
```

Use the file system for progressive disclosure: SKILL.md tells Claude what's available, and Claude reads deeper files when needed. This keeps initial context lean while giving the agent access to rich reference material.

#### SKILL.md Format

```markdown
---
name: api-conventions
description: When writing or modifying REST API endpoints, handlers, or middleware
---
# API Conventions
- Use kebab-case for URL paths
- Use camelCase for JSON properties
- Always include pagination for list endpoints

## Gotchas
- The `X-Request-Id` header is required on all responses — middleware adds it,
  but test helpers don't. Always use `createTestApp()` for integration tests.
- Rate limiting is per-user, not per-IP. Don't add IP-based rate limits.

## References
See `references/` for the full endpoint catalog and error codes.
See `examples/` for the canonical pagination pattern.
```

#### Skill Authoring Constraints

Three constraints are mechanical, not stylistic — cc-rpi enforces them in CI via `templates/scripts/verify-skills.sh`, and a violation fails the build with a runnable fix:

| Constraint | Why |
|---|---|
| `name` must match `^[a-z0-9-]{1,64}$` **and equal its directory name** | The name is the identifier the harness dispatches on, and the directory is how the skill is referenced from docs. A display-cased `"Git Workflow"` is not an identifier. |
| `description` under 1024 characters | This repository validates the declared adapter limit. Describe the capability and precise invocation triggers; do not add promotional wording or mandatory negative triggers. |
| `SKILL.md` body under 500 lines | This repository authoring budget is not a universal quality law. Split independent sub-workflows or useful detailed references, keep fragile constraints visible at invocation, and manifest every reachable dependency. |

A `references/` file that no `SKILL.md` names is also a failure: level-3 files load only when the model is told they exist and when to read them, so an unnamed sibling is dead weight.

#### Writing Effective Skills

**The description field is for triggering, not summarizing.** Claude scans skill descriptions to decide relevance. Write it as a condition: "When writing or modifying REST API endpoints" — not "REST API design conventions for our services."

**Lead with gotchas.** The highest-signal content in any skill is what Claude gets wrong without it. Build a gotchas section from real failures and keep adding to it over time. If Claude consistently makes a mistake in your domain, that mistake belongs in a skill.

**Don't state the obvious.** Claude already knows how to code. Focus on what pushes it out of its defaults — your team's specific conventions, internal library quirks, and domain-specific patterns that differ from common practice.

**Avoid railroading.** Give Claude the information it needs but let it adapt to the situation. Describe constraints and goals, not step-by-step procedures. Over-specified skills break when the situation doesn't match the script exactly.

**Include scripts and reference code.** Giving Claude composable helper functions lets it spend turns on composition rather than reconstructing boilerplate. A data analysis skill with a library of query helpers is far more powerful than one with just prose instructions.

#### Interface Design Over Worked Examples

The strongest lever for correct tool use is the interface itself, not a demonstration of it. Design parameters, enums, and file layouts so the correct path is implied by the shape of the interface — a parameter named `mode: "read" | "write" | "append"` teaches the three valid states and rules out a fourth, at a fraction of the context cost of three worked examples showing each mode in use. Reach for a worked example only when the interface genuinely cannot carry the meaning — an escaping quirk, an exact error string, an ordering constraint no type signature expresses.

The reason isn't just cost. A worked example is a demonstration, and a capable model tends to follow the demonstrated path literally — extrapolating from one shown shape constrains it to that shape instead of the full space the interface actually allows. A well-named enum with three valid values teaches more than three worked examples and leaves the model free to combine them in ways no single example showed.

This does not contradict the wrong/right example pairs used throughout this repo's skills, or `CHANGELOG.md:483`'s "examples beat rule lists" guidance, which was correct for the model generation it was written against. Those pairs mostly encode an **environment fact** — this exact flag, this exact escaping behavior, this exact error string a real tool actually produces — and a fact isn't something interface design can imply; it has to be stated. Keep those. The distinction to apply going forward: if an example merely demonstrates a shape a well-designed interface could have implied instead (which enum value to pass, which file goes where), replace it with better interface design; if it records a fact the model has no other way to learn, keep the example.

#### Skill Categories

Use this taxonomy to identify which skills your project needs:

| Category | Purpose | Examples |
|----------|---------|---------|
| **Library/API reference** | How to correctly use internal or tricky external libraries | billing-lib gotchas, design system usage, internal CLI docs |
| **Product verification** | How to test that code actually works end-to-end | signup flow driver, checkout verifier, CLI smoke test |
| **Data fetching** | How to connect to your data/monitoring stacks | funnel queries, cohort comparison, Grafana dashboard lookup |
| **Business process** | Automate repetitive team workflows | standup post, ticket creation, weekly recap |
| **Code scaffolding** | Generate framework boilerplate for your codebase | new service template, migration file, internal app scaffold |
| **Code quality** | Enforce org-specific quality standards | adversarial review, code style enforcement, testing practices |
| **CI/CD** | Fetch, push, deploy, and monitor | PR babysitter, deploy pipeline, cherry-pick workflow |
| **Runbooks** | Investigate symptoms and produce structured reports | service debugging, oncall runner, log correlator |
| **Infrastructure ops** | Routine maintenance with guardrails | orphan cleanup, dependency management, cost investigation |

Not every project needs all categories. Start with library reference and code quality (highest immediate value), then add verification and scaffolding as patterns emerge.

#### On-Demand Hooks

Skills can register hooks that activate only when the skill is invoked and last for the session. Use this for guardrails that would be too restrictive as permanent hooks:

- `/careful` — blocks `rm -rf`, `DROP TABLE`, force-push, `kubectl delete` via PreToolUse matcher. Activate when touching production.
- `/freeze` — blocks Edit/Write outside a specific directory. Activate when debugging to prevent accidental "fixes" to unrelated code.

This extends the three-tier enforcement model (see [ci-and-guardrails.md](ci-and-guardrails.md)) with a context-sensitive layer: permanent hooks for always-on protection, on-demand hooks for situational guardrails.

### Custom Agent Definitions (`.claude/agents/`)

Define reusable subagent specs with their own tool restrictions. Omit model and effort fields to inherit the owner pane; explicit economy choices belong in a separately selected launch or profile. These formalize the subagent catalog entries above into Claude Code's native format.

```markdown
# .claude/agents/security-reviewer.md
---
name: security-reviewer
description: Reviews code for security vulnerabilities
tools: Read, Grep, Glob, Bash
---
You are a senior security engineer. Review code for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication and authorization flaws
- Secrets or credentials in code
- Insecure data handling

Provide specific line references and suggested fixes.
```

The omitted model and effort fields preserve the active selection; do not add `best` or an invented `effort: inherit` to a subagent schema. See [model selection](context-engineering.md#model-selection--inherit-the-owner-pane) for native controls.

This maps directly to the tool restriction table above — the `tools` field enforces what each agent can access. Use custom agents for recurring review patterns, specialized analysis, or any task that benefits from isolated context with constrained tools.

### Hooks

Hooks are deterministic scripts that run automatically at specific points in Claude's workflow. Unlike advisory instructions, registered and trusted hooks can enforce a matched event deterministically. Registration alone does not prove execution; inspect native trust and invocation evidence.

**Common hook patterns:**
- **PostToolUse on Write/Edit** — Run formatter/linter after a matching edit and return corrective feedback; the write already occurred.
- **Git pre-commit hook** — Run typecheck/lint before the commit is created.
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
| **Debugging** | Bounded independent investigations of distinct hypotheses | API, cache, rendering, config, dependencies |
| **Pre-launch audit** | 8 core audit domains, plus the conditional agent-facing domain; staff by independent coverage | Principal Architect, Staff FE, Staff BE, Performance, DevOps/SRE, Security, QA/Reliability, UX Cohesion, (Agent Surface Engineer) |
| **Self-healing pipeline** | Audit phase (parallel) → fix phase (parallel) → verify phase | Lint, tests, a11y, security, bundle size |
| **Health check** | Bounded checks across required health areas | Tests, code quality, CI health, dependency health |
| **Feature implementation** | Sequential workflow with parallel sub-steps | Read issue → TDD → implement → docs (parallel) → CI verify |
| **Code review** | Independent required review lenses with useful staffing | Correctness, security, performance |

### Team Design Principles

1. **Read-only auditors.** Audit/investigation agents should never modify files — they report findings. A separate fix step (human or agent) acts on the report.
2. **Conditional staffing.** Parallelize independent work only when it helps and resources permit. Keep at most three implementers in the current phase; one reviewer may cover compatible audit domains.
3. **Synthesize before acting.** Collect all agent findings into a single report before deciding what to fix. Prevents conflicting changes.
4. **Self-healing fallback.** If a sub-agent fails due to permissions or tool errors, the parent agent takes over manually using its own tools.
5. **Coverage survives failure.** Inspect failed assignments and complete required evidence locally or reassign with a justified correction. Never mark missing output as passed or abandon a required domain after a fixed retry quota.
6. **Cross-agent recommendations.** Each agent should note findings that affect another agent's domain (e.g., security reviewer flagging a performance concern).

### Pre-Launch Audit Template

Cover 8 core audit domains before any production release, plus the conditional
agent-facing domain when applicable. Assign domains independently of agent count;
one reviewer may cover compatible domains, and stricter project charters remain
mandatory. Missing coverage blocks acceptance:

| Specialist | Focus |
|------------|-------|
| **Principal Architect** | System-wide architecture, module boundaries, dependency health, circular deps, dead code, typecheck |
| **Staff Frontend Engineer** | Component structure, state management, routing, client-side perf, hydration, bundle composition |
| **Staff Backend Engineer** | API design, validation, error handling, retry/idempotency, DB access, transactions, queues, background jobs |
| **Performance Engineer** | Bundle sizes, unused exports, code splitting, p95/p99 latency risks, cache strategy, hot-path identification |
| **DevOps / SRE Lead** | Deployment safety, rollback, env config, secrets, migrations, CI/CD, health checks, observability, runbook readiness |
| **Security Reviewer** | Dependency audit, hardcoded secrets, auth/authz, injection (SQL/XSS/SSRF/CSRF), unsafe defaults, CORS |
| **QA / Reliability Lead** | Full test suite, coverage of critical flows, graceful degradation, failure modes, retry/idempotency coverage |
| **Product Designer / UX Lead** | Visual hierarchy, design-system gaps, component reuse, messaging/voice, a11y, error/empty/loading states |
| **Agent Surface Engineer** (conditional) | Tool inventory and overlap, naming, input schemas vs. handler validation, error recovery text, registration lifecycle, adapter isolation, eval coverage |

Each produces findings carrying a 5-tier severity (launch-blocker / high /
medium / low / strategic), a 3-tier time horizon (Before launch / After
launch / Later), an evidence-or-inference label, a stable finding ID, and
file:line refs. Results synthesize into a 16-section report with a verdict:
READY, CONDITIONAL, or NOT READY. `rpi-remediate` preserves every finding ID
and resolves confirmed actionable findings through review, repair, simplification
and verification. Severity/time horizon order the work, not automatic deferral.
False positives need evidence; a genuine new architectural decision receives an
explicit local disposition and owner review. External issues require authorization.

See the canonical [rpi-pre-launch skill](../templates/skills/rpi-pre-launch/SKILL.md) for the full audit contract.

---

## Claude Code Agent Teams (Native Feature)

Claude Code has a native Agent Teams feature that implements the patterns above as a first-class capability. It is experimental and remains disabled in new cc-rpi installations. An owner who explicitly wants it can opt in through `.claude/settings.json`; updates preserve an existing opt-in:

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
3. **Size bounded assignments** around coherent ownership, evidence and terminal conditions. No fixed task count is required.
4. **Preserve native permissions** and existing owner authorization. Optional capability setup is a separate explicit choice; never add broad allows merely to suppress prompts.
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
| **Medium** | Publishing completed non-production integration, installing dependencies | Follow authorization and remote-budget boundaries |
| **High** | Merging PRs, pushing to `main`/production, deploying, modifying external services | Requires explicit authorization; reuse existing authorization within scope |
| **Critical** | Deleting branches, force-pushing, dropping databases, modifying CI/CD pipelines | Assess the concrete action and existing authority; destructive new scope needs an explicit decision |

#### Precise Boundaries

| Action | Autonomous? | Why |
|--------|------------|-----|
| Searching/reading code | Yes | Read-only, zero risk |
| Running tests and linters | Yes | Read-only verification |
| Writing code per approved plan | Yes | Plan was already human-approved |
| Creating git branches | Yes | Reversible, local scope |
| Committing to feature branches | Yes | Reversible, local scope |
| Pushing completed non-production integration | When authorized, after full local gates and trigger inspection | One completed push, no Preview deployments |
| Creating working-branch PRs | No | Working branches remain local |
| Adding external PR descriptions | When explicitly authorized | External communication |
| Merging PRs to a shared integration branch | Only when explicitly authorized | Shared remote mutation |
| Merging PRs to `main`/production | Requires explicit authorization | Affects production |
| Deploying production | Requires explicit authorization | Production side effects |
| Creating Vercel Previews | No | Owner remote budget |
| Modifying CI/CD workflows | Within the approved local scope | Verify locally; remote execution has a separate budget boundary |
| Deleting owned local branches/worktrees | After integration and preservation checks | Preserve unknown, unmerged and foreign work |

#### The Quality Cascade Principle

Human review belongs at the highest-leverage points. A bad line of research can lead to a bad plan, which leads to hundreds of bad lines of code. Therefore:

1. **Research output** — Human reviews critically. Throw out and redo if wrong.
2. **Implementation plan** — Human reviews and approves before any code is written.
3. **Generated code** — Automated verification (tests, types, lint) is primary. Human spot-checks.

Invest review time at the top of the cascade, not the bottom. Once a plan is approved and tests pass, the code is trusted.

#### Time-Bounded Autonomy

For scheduled or background agents, choose resource budgets and progress
checkpoints from the actual task. Stop at the assignment terminal condition;
inspect missing progress, preserve partial work and resolve ownership before
reassignment. Duration alone is not proof of correctness or failure.

See [push-accountability.md](push-accountability.md) for the post-push verification protocol and [scheduled-agents.md](scheduled-agents.md) for recurring agent patterns.

### Self-Correction Over Escalation

When an agent encounters an error:
1. **Diagnose** — read the error, understand the root cause
2. **Fix** — attempt the fix using available tools
3. **Verify** — run the relevant checks to confirm the fix works
4. **Change the approach when evidence warrants** — do not repeat unchanged failures. Escalate when progress requires a new decision or unavailable authority, preserving concrete evidence and local state

Don't ask "should I fix this?" — just fix it. Don't suggest the user run a command you could run yourself.
