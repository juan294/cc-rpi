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

## Compaction via Commit Messages

Git commit messages are another compaction surface. Well-written commits serve as a compressed log of what changed and why, which future research agents can use to quickly understand project history without reading every file.

## Context Utilization Target

Aim to keep context utilization at **40-60%** of the window. Above 60%, output quality degrades noticeably. If you're approaching this threshold:

1. Compact current progress to a markdown file
2. Start a fresh conversation
3. Point the new conversation at the compacted artifact

This is why the RPI phases are separate conversations, not one long session.

## Research on Main, Implement in Worktrees

Research and planning should happen on the `main`/`develop` branch — they don't modify code, so there's no risk. Implementation should happen in a git worktree or feature branch, keeping the default branch clean. This also means multiple research/planning sessions can happen in parallel without conflicts.

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

## You Need a Domain Expert

For complex codebases, at least one person on the team should be an expert in the codebase (or the relevant area). The RPI pattern amplifies expert knowledge — it doesn't replace it. When both participants are unfamiliar with the codebase, research tends to miss critical dependency chains and architectural constraints.
