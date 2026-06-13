# Context Engineering

> "The contents of your context window are the ONLY lever you have to affect the quality of your output."

## The Stateless Function Mental Model

At every turn, a coding agent is a stateless function call: the full context window goes in, the next action comes out. There is no hidden memory, no persistent state beyond what's in the window. This means:

- Everything the agent needs to make a good decision must be IN the context window
- Everything that ISN'T needed is noise that degrades decision quality
- The entire RPI workflow is, at its core, a **context management strategy**

## Context Quality Hierarchy

Optimize your context window for these properties, in priority order:

| Priority | Property | Worst Case |
|----------|----------|------------|
| 1 (highest) | **Correctness** | Incorrect information leads to confidently wrong output |
| 2 | **Completeness** | Missing information leads to incomplete or misguided output |
| 3 | **Size / Noise** | Too much irrelevant content drowns the signal |
| 4 | **Trajectory** | Poor trajectory (conversation going off-track) compounds with each turn |

**The equation:** Quality is proportional to (Correctness x Completeness) / Noise.

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

Each phase starts with a fresh context window that reads only the compact artifact from the previous phase, not the raw exploration that produced it.

**The ideal compacted output includes:**
- What we're trying to accomplish (goal)
- What we've learned so far (findings with file:line refs)
- What approach we're taking (decisions made)
- What's been done (completed steps)
- What's next (remaining work)
- What's currently blocking (if anything)

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

## Context Utilization Target

Aim to keep context utilization at **40-60%** of the window. Above 60%, output quality degrades noticeably. If you're approaching this threshold:

1. Compact current progress to a markdown file
2. Start a fresh conversation
3. Point the new conversation at the compacted artifact

This is why the RPI phases are separate conversations, not one long session.

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
| **CLAUDE.md** | Every session | Build/test commands, git workflow, operational rules, stack overview |
| **Skills** (`.claude/skills/`) | On demand, when relevant | Domain knowledge, reusable workflows, API conventions |
| **Supplementary docs** (`docs/`, `agent_docs/`) | When agent decides to read | Architecture details, database schemas, service patterns |
| **Research artifacts** (`docs/research/`) | When starting a related task | Previous investigation results, codebase maps |

**Why this matters:** Claude Code's system prompt injects a reminder that CLAUDE.md content "may or may not be relevant." The more non-universal content in the file, the higher the chance Claude deprioritizes your actual instructions. Keep CLAUDE.md lean; put specialized knowledge in skills and docs.

**In supplementary files:** Use `file:line` references instead of code snippets. Snippets go stale; references can be verified at read time.

## CLAUDE.md as Context Surface

CLAUDE.md is your highest-leverage context engineering tool — it's the only file guaranteed to be in every conversation. Treat it accordingly:

**Capacity:** Frontier models can follow ~150-200 instructions with consistency. Claude Code's system prompt already uses ~50 of those. Budget wisely.

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

**When to clear vs compact:**
- Switching to an unrelated task → `/clear`
- Same task but context is heavy → `/compact`
- Tried an approach that failed → `/rewind` to before the failed attempt
- After two failed corrections on the same issue → `/clear` and write a better initial prompt

## Headless Mode and Fan-out

For CI pipelines, batch operations, and scaling beyond a single session:

- **`claude -p "prompt"`** — Run Claude headlessly without an interactive session. Use `--output-format json` for structured output.
- **Fan-out pattern** — Generate a task list, then loop: `for file in $(cat files.txt); do claude -p "Migrate $file" --allowedTools "Edit,Bash(git commit *)"; done`
- **Writer/Reviewer pattern** — Run two sessions: one implements, another reviews the implementation in fresh context (unbiased by having written it).

## Claude Settings & Permissions

Beyond CLAUDE.md content, the agent's operating environment is configured through Claude Code's settings and permission system. These control what tools the agent can use without asking.

### Permission Whitelisting

Configure `.claude/settings.json` to pre-approve common operations so the agent doesn't pause for permission on routine tasks:

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(pnpm run *)",
      "Bash(git *)",
      "Bash(gh *)",
      "Read",
      "Write",
      "Edit"
    ]
  }
}
```

**Principle:** Whitelist development tools aggressively. The agent should never be blocked mid-task by a permission prompt for `git status` or `pnpm run test`. Reserve permission gates for genuinely dangerous operations.

### Feature Flags

Enable experimental features via `env` in settings.json:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Agent Teams is the primary feature flag all cc-rpi projects enable by default. See [agent-design.md](agent-design.md) for full Agent Teams documentation.

### Hooks

Hooks run automatically at specific points in Claude's workflow. Unlike CLAUDE.md instructions (advisory), hooks are **guaranteed** to execute. Configure in `.claude/settings.json`:

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

### Model Selection — Tier Each Workflow

Model choice is the biggest single lever on your inference bill. The same task on a frontier model can cost 10-30x what it costs on the floor model, and for most of the RPI loop the frontier model buys you nothing — `/status` does not reason, it summarizes. The discipline: **explore once at frontier cost, then run the codified loop on the cheapest model that still does the job.**

Every command in this blueprint declares a **model tier** on the line directly under its title (e.g. `Model tier: **sonnet**`). Three tiers:

| Tier | Use for | Commands | Why |
|------|---------|----------|-----|
| **opus** (frontier) | Deep reasoning where a bad output amplifies downstream | `/research`, `/plan`, `/pre-launch` | A bad line of research → thousands of bad lines of code. Spend here. |
| **sonnet** (mid) | Building and executing against a reviewed plan | `/implement`, `/validate`, `/remediate`, `/fix-ci`, `/triage`, `/bootstrap`, `/adopt`, `/detach`, `/release`, `/update-docs`, `/update` | The plan already removed the ambiguity; this tier executes it reliably. |
| **haiku** (floor) | Mechanical read-and-summarize, no judgment | `/status`, `/describe-pr` | Deterministic-ish output. Frontier models are pure waste here. |

This blueprint is Claude-bound, so each tier maps to a concrete model already:

| Tier | Concrete model |
|------|----------------|
| opus | Claude Opus 4.x |
| sonnet | Claude Sonnet 4.x (1M context) |
| haiku | Claude Haiku 4.x |

Bind the tier per workflow, not per session: run each command in a session on its declared model, and in custom agent definitions (`.claude/agents/`) set the `model` field to the tier the agent serves. The tier travels with the workflow so the choice re-applies every time anyone runs it, rather than defaulting to whatever model happens to be selected.

**Subagents inherit the tier.** Fan-out commands spawn helpers — `/pre-launch`'s 8 specialists, `/remediate`'s parallel TDD agents, `/research`'s locator/analyzer/pattern agents. A frontier parent that spawns 8 frontier children multiplies the bill by 8. Pin spawned agents to the same tier as their workflow (or lower) — which is why each command's tier line says `All subagents: model: "..."`. Only raise a child above its parent's tier when it genuinely needs to reason harder.

**Override upward, never silently downward.** The tier is the default, not a ceiling. If a task turns out harder than its tier — a gnarly `/implement` phase, a `/validate` that uncovers a design flaw — bump that session up a tier and note why. Never quietly drop a workflow below its declared tier to save tokens; that trades a small bill for a large downstream error. See [cost-monitoring.md](cost-monitoring.md) for measuring whether a tier change actually paid back.

**Don't switch tiers mid-conversation to save money** — prompt caches are per-model (see [Session Stability](#session-stability-and-prompt-caching) below). Pick the tier when you start the session; if you need a cheaper model for a sub-task, spawn a subagent rather than switching the active model.

### Session Stability and Prompt Caching

Claude Code uses prompt caching to reuse computation from previous turns — the API caches everything from the start of the request as a prefix. This makes long sessions dramatically cheaper and faster, but the cache is fragile: any change to the prefix invalidates it.

Two common actions silently break the cache:

**Don't switch models mid-conversation.** Prompt caches are per-model. If you're 100k tokens into an Opus session and switch to Haiku for a "quick question," Haiku must rebuild the entire cache from scratch — making it *more* expensive than letting Opus answer. Use subagents for cheaper models instead: Opus prepares a focused handoff, the subagent runs on Haiku in its own context, and only the result returns.

**Don't add or remove MCP tools mid-session.** Tools are part of the cached prefix. Loading or unloading an MCP server during a conversation invalidates the cache for everything after it. Configure your MCP servers before starting work. If you need a tool you didn't load, it's cheaper to start a new session with the right tools than to add one and pay for a full cache rebuild.

## You Need a Domain Expert

For complex codebases, at least one person on the team should be an expert in the codebase (or the relevant area). The RPI pattern amplifies expert knowledge — it doesn't replace it. When both participants are unfamiliar with the codebase, research tends to miss critical dependency chains and architectural constraints.
