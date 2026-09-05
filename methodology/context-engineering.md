# Context Engineering

## Context and Persistent State

Good decisions need current, relevant evidence in the active context or in
artifacts the agent can retrieve. Repositories, tool sessions, native memory
and configuration can persist outside the conversation. Their existence does
not guarantee that a later turn has loaded or verified them. RPI uses explicit
handoffs and state checks to make that boundary visible.

## Context Quality Hierarchy

Optimize your context window for these properties, in priority order:

| Priority | Property | Worst Case |
|----------|----------|------------|
| 1 (highest) | **Correctness** | Incorrect information leads to confidently wrong output |
| 2 | **Completeness** | Missing information leads to incomplete or misguided output |
| 3 | **Size / Noise** | Too much irrelevant content drowns the signal |
| 4 | **Trajectory** | Poor trajectory (conversation going off-track) compounds with each turn |

This hierarchy is a working heuristic, not a quantitative quality equation.

## What Eats Context

These activities consume large amounts of context window space:

- **File searching** — Glob/Grep results, directory listings
- **Code understanding** — Reading file contents, tracing data flow
- **Applying edits** — Diffs, edit confirmations, error-retry cycles
- **Test/build logs** — Verbose compiler output, test runner output
- **Large tool responses** — JSON blobs, API responses

This is why subagents are so valuable: they consume context in THEIR window and return only the distilled result to yours.

## Frequent Intentional Compaction

The core technique that makes RPI work at scale.

**What is compaction?** Distilling raw context (file searches, code reads, test logs) into structured artifacts (research documents, plans, status summaries).

**Three forms of compaction:**

### 1. Ad-hoc compaction
When your context starts filling up mid-session, pause and write progress to a markdown file:

> "Write everything we did so far to progress.md — note the end goal, the approach, steps completed, and the current issue we're working on."

Then start a fresh conversation pointing at that file.

### 2. Subagent compaction
Subagents do file searching, code reading, and analysis in THEIR context window and return only the structured summary to yours. This is NOT about "role-playing" — subagents are a **context control mechanism**.

### 3. Phase compaction (the RPI workflow itself)
Each phase produces a compact artifact:
- Research -> research document (compact summary of codebase state)
- Plan -> implementation spec (compact description of what to change)
- Implement -> committed code + updated plan checkboxes
- Validate -> validation report

Prefer separate phase conversations using the handoff plus controlling contracts
and targeted current-state verification. Reuse valid prior reads; do not reload
all raw exploration or assume the handoff alone proves current state.

**The ideal compacted output includes:**
- What we're trying to accomplish (goal)
- What we've learned so far (findings with file:line refs)
- What approach we're taking (decisions made)
- What's been done (completed steps)
- What's next (remaining work)
- What's currently blocking (if anything)
- Approved scope, base/current commit, worktree path and dirty/untracked state
- Check receipts and tested identity, deviations, retained risks and next phase

On resume, compare the actual state with this record before relying on any
completion claim. Invalidated check evidence must be rerun. Existing owner
authorization persists within its scope; a handoff cannot grant native trust.

### Good vs Bad Compaction

**Good compaction — preserves signal, discards noise:**

> **Goal:** Add rate limiting to the login endpoint.
> **Approach:** Redis sliding window, per-IP (20/15min) and per-email (5/15min). Fail-open on Redis outage.
> **Done:** Phase 1 complete — `src/auth/rate-limiter.ts` implemented with 6 passing unit tests. Uses atomic INCR+EXPIRE via MULTI/EXEC.
> **Key learning:** Redis session storage at `src/auth/session.ts:5` uses the same connection — reuse it instead of creating a new client.
> **Next:** Phase 2 — middleware wrapper at `src/middleware/rate-limit.ts`. Wire into `src/routes/auth.ts:12`.
> **Blocking:** Nothing.

This is 6 lines that let a fresh session continue from exactly where we left off. Every line is actionable.

**Bad compaction — loses critical details:**

> We worked on rate limiting. Made good progress on the first phase. Tests are passing. Need to do the middleware next.

This is useless to a fresh session. No file paths, no design decisions, no specific state. The new session would need to re-research everything.

**Bad compaction — too much noise:**

> [500 lines of test output, full file contents of rate-limiter.ts, conversation about whether to use INCR vs ZADD, 3 failed approaches before the working one, the full Redis documentation we read...]

This defeats the purpose. A compaction that preserves everything is not a compaction — it's a copy. Discard exploration paths, failed approaches, and raw tool output. Keep only the structured findings.

### What Gets Discarded vs Preserved

| Discard (noise) | Preserve (signal) |
|-----------------|-------------------|
| File search results (Glob/Grep output) | Which files are relevant and why |
| Raw file contents | Key findings with `file:line` references |
| Failed approaches and dead ends | The working approach and why it was chosen |
| Test output on success | Pass/fail status of each verification step |
| Full test output on failure | The specific error message and root cause |
| Conversation about alternatives | The decision made and its rationale |
| Tool invocation details | The structured result of the investigation |

### Micro-Compaction: The `run_silent` Pattern

For implementation phases, test and build output should be compressed at the tool level, not after the fact. Wrap verification commands so that:
- **On success:** return a single checkmark or "PASS" line
- **On failure:** return the full error output

This prevents test suites from consuming thousands of tokens on success while preserving full diagnostic information on failure. Configure this via hooks or shell wrappers in your project.

## Compaction via Commit Messages

Git commit messages are another compaction surface. Well-written commits serve as a compressed log of what changed and why, which future research agents can use to quickly understand project history without reading every file.

## When to Compact

There is no universal utilization percentage or context-slot budget. Use actual
native warnings, missed constraints, retrieval noise and task progress to decide
when context needs attention. Use native compaction within a long phase and a
durable handoff between conversations. A new conversation does not erase the
approved objective or remove its acceptance gates.

Instruction budgets are separate: cc-rpi checks its managed root bytes, while
read-only diagnostics report the full effective chain and any unverified native
limit. Never truncate owner instructions or raise a native limit automatically.

## Research on the Integration Branch, Implement in Worktrees

Research and planning should happen against the repo's long-lived
integration branch because they don't modify code. Implementation should
happen in a git worktree or temporary implementation branch, keeping the
shared branch clean and making parallel work safe.

Separate these concerns explicitly:

- **Integration branch** -- the long-lived branch used to absorb reviewed
  work. This might be `main`, `develop`, or another shared branch.
- **Production branch** -- the branch that triggers production release,
  if the repo uses a separate one.
- **Implementation branch/worktree** -- the temporary isolated workspace
  where code changes are made before review or merge.

This means a repo can be `main-only` and still require worktree-based
implementation, or it can use a `develop` -> `main` flow while keeping
the same isolation rule.

In Claude Code: use the `/worktree` command or `EnterWorktree` tool when starting implementation.

## Multiple Research Passes

Sometimes the first research pass is wrong or incomplete. This is expected. The right response is to:

1. Read the research critically
2. If it's off-base, throw it out entirely
3. Start a new research session with more specific steering
4. Repeat until the research accurately reflects reality

Plans built with accurate research fix problems in the *right* place and prescribe testing aligned with codebase conventions.

## Progressive Disclosure

Not all context is needed at all times. CLAUDE.md is loaded every session, so it should contain only **universally applicable** instructions. Everything else should live in supplementary files that the agent loads on demand.

**The hierarchy:**

| Layer | When Loaded | What Goes Here |
|-------|-------------|----------------|
| **Shared root instructions** | Native root discovery | Build/test commands, workflow, stack and the essential conditional-rule map; Claude imports the shared AGENTS.md block |
| **Skills** (`.claude/skills/`) | On demand, when relevant | Domain knowledge, reusable workflows, API conventions |
| **Conditional domain rules** | Claude native matching; Codex explicit root map and selected skills | Domain rules scoped to relevant files; do not assume Claude globs are native Codex instructions |
| **Supplementary docs** (`docs/`, `agent_docs/`) | When agent decides to read | Architecture details, database schemas, service patterns |
| **Research artifacts** (`docs/research/`) | When starting a related task | Previous investigation results, codebase maps |

`.claude/rules/` files carry a `paths:` frontmatter list of globs (for example
deployment rules on `.github/**`, test rules on `**/*.test.*`); the rule body
loads only when Claude is working with a file matching one of those globs.
This is infrastructure-level conditional loading, and it replaces the older
`<important if>` block convention — the condition is enforced by the harness
reading the frontmatter, not by an instruction the model has to notice and
apply itself.

**Why this matters:** Claude Code's system prompt injects a reminder that CLAUDE.md content "may or may not be relevant." The more non-universal content in the file, the higher the chance Claude deprioritizes your actual instructions. Keep CLAUDE.md lean; put specialized knowledge in skills and docs.

**In supplementary files:** Use `file:line` references instead of code snippets. Snippets go stale; references can be verified at read time.

### A Spec Doesn't Have to Be Prose

Specs are the source of truth (see [GUIDE.md](../GUIDE.md) and [philosophy.md](philosophy.md)), and `file:line` references beat pasted snippets. Both point at the same underlying preference: point at something that can be executed or diffed, rather than describing it in words that can't be checked. Prose is the fallback, not the default — reach for it only when nothing sharper exists.

Concrete alternatives to look for before writing prose:
- **A failing test suite** — the test IS the spec; making it pass is the definition of done, with no separate description of "correct behavior" to keep in sync.
- **An existing module with the semantics to port** — point at the module and say "match this," instead of re-deriving its behavior in prose that can drift from the thing it describes.
- **An HTML mockup or a schema** — a mockup pins down layout and interaction more precisely than a paragraph of UI description; a schema pins down shape more precisely than a paragraph of field descriptions.
- **A grading rubric** — for open-ended output (a report, a review), a rubric is checkable where "write a good report" is not.

Prose still has a place — as the fallback for behavior with no executable or diffable stand-in — but check for one of these first.

## CLAUDE.md as Context Surface

The managed root instruction block is the shared entry point. The effective
native instruction chain can also include user, override and nested project files;
verify actual discovery instead of assuming one file supplies the whole context.

**Capacity:** Measure the effective native instruction chain, including user, override and project files. Keep the managed root within its byte budget; preserve user content and report overflow rather than truncating it or silently raising the native limit.

**What to include vs exclude:**

| Include | Exclude |
|---------|---------|
| Bash commands Claude can't guess | Anything Claude can infer from code |
| Code style rules that differ from defaults | Standard language conventions |
| Test runners and verification commands | Detailed API docs (link instead) |
| Branch naming, PR conventions | Information that changes frequently |
| Architectural decisions specific to the project | Long explanations or tutorials |
| Environment quirks (required env vars) | File-by-file codebase descriptions |
| Common gotchas and non-obvious behaviors | Self-evident practices like "write clean code" |

**Authoring principles:**
- Manually craft every line. Don't auto-generate with `/init` — bad instructions compound through research, plans, and code.
- For each line, ask: "Would removing this cause Claude to make mistakes?" If not, cut it.
- Don't use Claude for linting — it's expensive and slow vs. deterministic tools. Use automated formatters + hooks instead.
- Use emphasis (IMPORTANT, CRITICAL, NEVER) sparingly for rules that truly matter. Overuse dilutes everything.
- Check CLAUDE.md into git. It compounds in value as the team contributes.
- Review it when things go wrong — if Claude ignores a rule, the file is probably too long.

## Session Lifecycle

Context doesn't have to be managed only through RPI phases. Claude Code provides session-level tools:

- **`/clear`** — Reset context between unrelated tasks. The single most underused technique.
- **`/compact <focus>`** — Summarize context with a focus. e.g., `/compact Focus on the API changes`. Customize compaction behavior in CLAUDE.md with instructions like "When compacting, always preserve the full list of modified files."
- **`/rewind` or `Esc+Esc`** — Restore conversation, code, or both to any previous checkpoint. Every Claude action creates a checkpoint.
- **`--continue`** — Resume the most recent conversation across terminal sessions.
- **`--resume`** — Select from recent conversations. Use `/rename` to give sessions descriptive names.
- **Native diagnostics** — inspect the installed client's help and documented scope
  before invoking a diagnostic. Prefer cc-rpi read-only `rpi-status` diagnostics
  for installation and instruction-chain evidence. A diagnostic observation does
  not authorize repairs, profile changes or external services.

**When to clear vs compact:**
- Switching to an unrelated task → `/clear`
- Same task but context is heavy → `/compact`
- Tried an approach that failed → `/rewind` to before the failed attempt
- When repeated corrections stop producing new evidence → record state, revisit
  the hypothesis and compact if needed; no fixed retry count determines failure

## Headless Mode and Fan-out

For CI pipelines, batch operations, and scaling beyond a single session:

- **`claude -p "prompt"`** — Run Claude headlessly without an interactive session. Use `--output-format json` for structured output.
- **Bounded assignments** — Identify independent work within the current phase,
  bind each assignment to owned files and explicit outputs, and use at most three
  implementers. Keep native permissions narrow and all worktrees local; do not
  create an unrestricted shell loop or implicit background service.
- **Writer/Reviewer pattern** — Run two sessions: one implements, another reviews the implementation in fresh context (unbiased by having written it).

## Claude Settings & Permissions

Beyond CLAUDE.md content, the agent's operating environment is configured through Claude Code's settings and permission system. These control what tools the agent can use without asking.

### Native Permission Boundaries

Use the harness-specific adapter for native permissions. Claude's deny rules
cover unconditionally forbidden forms; ask rules cover publication and deployment
entry points. The stateful policy hook supplements these rules with branch,
Preview and local-evidence checks. Do not add blanket `Bash(git *)` or
`Bash(gh *)` allows. Preserve unrelated owner permissions and ordering during
setup; permission changes are a separate reviewable diff.

Codex uses its own native permissions and trusted hooks. Claude settings are not
a Codex adapter. A structurally accepted command still requires the owner's
authorization at the native boundary. See [guardrails](ci-and-guardrails.md) and
the [v2 migration note](../docs/migrations/v2.md).

### Feature Flags

Experimental features are explicit owner opt-ins. For Agent Teams, an owner may set `env` in settings.json:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

New installations leave Agent Teams disabled and use ordinary supported subagents. Ownership-aware updates preserve an existing explicit opt-in. See [agent-design.md](agent-design.md) for full Agent Teams documentation.

### Hooks

Hooks run automatically at specific points in Claude's workflow. Unlike advisory instructions, registered and trusted hooks can enforce matched events. Native registration, trust and observed invocation are separate checks. Configure in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'formatter will run on commit via pre-commit hook'"
          }
        ]
      }
    ]
  }
}
```

**Common patterns:**
- **Post-edit formatter** — run prettier/eslint-fix after file changes
- **Pre-commit check** — run typecheck/lint before commit creation
- **Notification** — alert when long tasks complete
- **Agent Teams quality gate** — `TeammateIdle` and `TaskCompleted` hooks enforce standards on teammate output

**Rule of thumb:** If the behavior must happen every time, use a hook. If it's guidance that allows judgment, use CLAUDE.md.

See `templates/settings.json.template` for a complete starting point.

### Environment Variables

Agents inherit environment variables from the shell. For projects that need API keys, database URLs, or service credentials:

- Store them in `.env` (gitignored) for local development
- Document required variables in CLAUDE.md so agents know what's available
- Never hardcode secrets in CLAUDE.md or skills — reference `.env` instead
- For headless/CI mode, pass variables via the environment: `API_KEY=xxx claude -p "prompt"`

### Model Selection — Inherit the Owner Pane

The default is native inheritance: omit model and effort overrides in shared
workflows and helper definitions. Do not encode provider generations or assign a
cheaper model to a workflow name. Research, implementation, validation and
stateful diagnosis use the owner's active choice unless the owner explicitly
selects another one for that work.

An explicit Claude research/planning launch is:

```bash
claude --model best --effort high
```

For an implementation pane, retain the owner's supported family selector and
effort choice. The launch alias `best` belongs to the CLI, not automatically to a
subagent schema. Native omission expresses inheritance; `effort: inherit` is not
a portable field value. This launch was verified with Claude Code 2.1.261 on 2026-09-05; see the
[official model configuration](https://code.claude.com/docs/en/model-config).

Economy is optional and explicit. For a bounded mechanical locator or summary,
an owner can start a separate Claude session with `claude --model haiku` when that
family is available and adequate. The verified Haiku capability does not expose
an effort setting, so this example omits it. Never silently reclassify
architectural research or validation as mechanical. An explicit user selection
wins over the economy preference.

Claude skill frontmatter model/effort controls can override an explicit session
selection. RPI therefore supplies no automatic economy frontmatter. Use a
separately selected launch/profile for the bounded task. Codex turn-level model
and effort overrides persist into later turns, so a temporary parent switch
cannot promise automatic restoration either. Optional native profiles belong to
the user; installers do not rewrite global profiles.

See [native model profiles](../docs/model-profiles.md) for verified client syntax
and the dated adapter descriptor. Catalog defaults are neither quality rankings
nor proof of account access. Offline catalog lookup preserves the explicit
request and reports unresolved identity as unavailable.

Record four fields when reporting selection:

1. Requested role, such as research, implementation or mechanical locator.
2. Requested model/effort and its source: owner request, launch, profile or inherited configuration.
3. Resolved model/effort, only when a supported session-bound observation exposes it.
4. Evidence source, client version, session binding and freshness.

In Claude session Bash, `CLAUDE_EFFORT` is an observed effort value when present.
There is no assumed generic model-ID environment variable. Model prose, a pane
title, an unrelated statusline cache or the newest rollout file does not identify
the active pane. Missing effort stays unavailable too. Optional native
statusline/event observations must match the session and be fresh; diagnostics
never install a global statusline or require a model-ID cache to run RPI.

### Session Stability and Prompt Caching

Keep the active pane stable while it owns a task. Cache reuse depends on provider,
model, request prefix and cache lifetime; a smaller model does not by itself prove
a cheaper complete outcome. Tool configuration changes can also affect cached
prefixes. Measure usage and rework rather than asserting a universal savings
ratio. When an explicit economy task needs a different model, give a separate
session a compact handoff and return its result to the owner pane.

## You Need a Domain Expert

For complex codebases, at least one person on the team should be an expert in the codebase (or the relevant area). The RPI pattern amplifies expert knowledge — it doesn't replace it. When both participants are unfamiliar with the codebase, research tends to miss critical dependency chains and architectural constraints.
