# The Four Phases

> Optional pre-step: when the work starts as a vague idea rather than a spec,
> `/brainstorm` precedes Research. It is an interactive Socratic intake that
> produces a design brief in `docs/research/`, not a phase of the pipeline
> below. Skip it whenever the task is already well-specified.

## Architecture Overview

```
User
 │
 ├── /brainstorm ────► Brainstorm Facilitator (optional pre-step)
 │                       └── Socratic Q&A with user → design brief
 │
 ├── /research  ─────► Research Orchestrator
 │                       ├── Codebase Locator (find WHERE)
 │                       ├── Codebase Analyzer (understand HOW)
 │                       ├── Pattern Finder (find EXAMPLES)
 │                       ├── Docs Locator (find historical docs)
 │                       ├── Docs Analyzer (extract INSIGHTS)
 │                       └── Web Researcher (external sources)
 │
 ├── /plan  ──────────► Plan Orchestrator
 │                       ├── Same research subagents (for discovery)
 │                       └── Interactive Q&A with user
 │
 ├── /implement  ─────► Implementation Orchestrator
 │                       ├── Implementer subagents (up to 3)
 │                       ├── Reviewer subagent (plan compliance)
 │                       ├── /simplify (native — code quality)
 │                       └── /batch (native — parallel phases)
 │
 ├── /validate  ──────► Validation Orchestrator
 │                       └── Research subagents (for verification)
 │
 └── /describe-pr  ───► PR Description Generator
```

**Key architectural decisions:**

- **Orchestrator + specialist** pattern: Each command is an orchestrator that delegates to focused subagents running in parallel.
- **Read-only research agents**: Research-phase agents have no write/edit/bash access — they can only read and search.
- **Separation of concerns**: Locators find *where* things are. Analyzers explain *how* things work. Pattern finders show *examples*. They don't overlap.
- **Phase gates**: Implementation stops between phases. Validation is a separate explicit step.

### Mapping to Claude Code

| Concept | Claude Code Equivalent |
|---------|----------------------|
| Command definitions | Custom slash commands via `.claude/commands/` directory |
| Subagent delegation | `Task` tool with `subagent_type` (Explore, Plan, general-purpose, Bash) |
| Explore delegation | `Task` tool with `subagent_type: "Explore"` |
| Todo tracking | `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` |
| Thoughts directory | Any project-local docs directory (e.g., `docs/`, `plans/`, `.claude/research/`) |

---

## Phase Handoffs

Each RPI phase runs in its own conversation with a fresh context window. Context does NOT carry over automatically — the handoff artifact is what transfers knowledge between phases.

### What Carries Over vs What Starts Fresh

| Carries Over (via artifacts) | Starts Fresh |
|------------------------------|-------------|
| Research documents, plan files, phase files | The Claude Code conversation/session |
| Task status, action items, next steps | Tool output, intermediate search results |
| Key learnings and discoveries | File content (agent re-reads as needed) |
| Git state (branch, commit hash) | Permission approvals (re-granted per session) |
| File references with `file:line` | Exploration paths and dead ends |

### How Each Phase Receives Context

| Transition | What the receiving phase reads |
|------------|-------------------------------|
| Research → Plan | The research document. The planner reads it fully, then spawns targeted subagents for deeper investigation. The planner does NOT re-do the research — it trusts the document but verifies claims through code when something seems off. |
| Plan → Implement | The plan file + phase files. The implementer reads the current phase file and follows it step by step. It does NOT need to read the research document — the plan already distilled research into actionable steps. |
| Implement → Validate | The plan file (for success criteria) + git diff + test results. The validator checks the plan's criteria against the actual codebase state. |
| Any phase → Resume later | A handoff document (see template below). When you pause work mid-phase and resume in a new session, the handoff carries the critical context. |

### The Handoff Document

When pausing work and resuming later (whether between phases or within a long phase), create a handoff document. Its purpose is to compact and summarize context so a fresh session can continue without loss.

**Storage:** `docs/handoffs/YYYY-MM-DD-description.md`

**Template:**

```markdown
---
date: [ISO datetime]
branch: [current branch]
git_commit: [current HEAD hash]
status: [in-progress | paused | blocked]
---

# Handoff: [Description]

## Tasks
- [x] Task 1 — completed
- [ ] Task 2 — in progress (describe current state)
- [ ] Task 3 — planned

## Critical References
- `src/auth/login.ts:8` — main entry point
- `docs/plans/2025-12-16-rate-limiting.md` — implementation plan

## Recent Changes
- `src/auth/rate-limiter.ts` — new file, rate limiter core
- `tests/auth/rate-limiter.test.ts:15-48` — 6 unit tests added

## Learnings
- The Redis INCR+EXPIRE pattern must be atomic (use MULTI/EXEC)
- Existing session storage at `src/auth/session.ts` uses the same Redis instance

## Next Steps
1. Implement the middleware wrapper (Phase 2 of the plan)
2. Wire the middleware into `src/routes/auth.ts:12`

## Blockers
(None currently — or describe what's blocking progress)
```

### Resume Scenarios

When resuming from a handoff, the agent should classify the situation before acting:

| Scenario | What to do |
|----------|-----------|
| **Clean continuation** — all changes present, no conflicts | Pick up from the next step in the handoff |
| **Diverged codebase** — other changes merged since handoff | Verify handoff changes still apply, reconcile if needed |
| **Incomplete work** — tasks marked in-progress | Complete the in-progress work before moving to next steps |
| **Stale handoff** — significant time passed | Re-verify critical assumptions through targeted research before continuing |

**Rule:** Never assume handoff state matches current state. Always verify before continuing.

---

## Phase 1: Research

**Purpose:** Build a complete, accurate map of the codebase as it exists today.

**Applicability:** This phase requires an existing codebase. For greenfield projects with no code yet, skip directly to Phase 2 (Plan). Once the first implementation phase produces code, /research becomes the starting point for every subsequent task.

**Process:**

1. **Read mentioned files first** — fully, no truncation, before spawning any subagents. This gives the orchestrator full context for decomposition.
2. **Decompose** the research question into parallel search areas.
3. **Spawn parallel subagents:**
   - Codebase locator -> find all relevant files grouped by purpose
   - Codebase analyzer -> trace data flow and explain implementation
   - Pattern finder -> find similar implementations with code snippets
   - Docs locator -> discover relevant historical documents
   - Docs analyzer -> extract key insights from the most relevant docs
   - Web researcher -> (only if user explicitly asks) find external resources
4. **Wait for ALL subagents** before synthesizing. Never synthesize partial results.
5. **Synthesize** into a structured research document with YAML frontmatter.
6. **Add permalinks** to code references when on a pushed branch.

**Critical rules:**
- All agents document what *is*, never what *should be*.
- Every claim must include a `file:line` reference.
- Codebase findings are primary source of truth; historical docs are supplementary context.
- Research documents must be self-contained.

**Output format:**

```markdown
---
date: [ISO datetime with timezone]
researcher: [name]
git_commit: [hash]
branch: [branch]
repository: [repo]
topic: "[Research question]"
tags: [relevant, tags]
status: complete
last_updated: [YYYY-MM-DD]
last_updated_by: [name]
---

# Research: [Topic]

## Research Question
## Summary
## Detailed Findings
### [Component/Area 1]
### [Component/Area 2]
## Code References
## Architecture Documentation
## Historical Context
## Related Research
## Open Questions
```

### Phase Completion Criteria

Research is **done** when:
- [ ] Every component mentioned in the original question has been located and described
- [ ] All code references include `file:line` — no vague claims ("somewhere in the auth module")
- [ ] Data flow is traced end-to-end for the relevant paths (entry point → processing → output)
- [ ] Test coverage is documented (what tests exist, what's missing)
- [ ] Open questions are explicitly listed — not buried in findings text
- [ ] The document is self-contained: a reader who didn't attend the session can understand it

Research is **NOT done** if:
- Findings contain opinions, suggestions, or quality judgments
- Any section says "likely" or "probably" without a supporting code reference
- The open questions list is empty (there are always open questions)

---

## Phase 2: Plan

**Purpose:** Create a detailed, phase-based implementation specification through interactive dialogue.

**Process:**

0. **Interview (optional, for large features):**
   - If the scope is broad or requirements are unclear, have Claude interview you first using the AskUserQuestion tool.
   - Prompt: "I want to build [brief description]. Interview me about technical implementation, edge cases, and tradeoffs. Don't ask obvious questions — dig into the hard parts I might not have considered."
   - Continue until all key decisions are captured, then proceed to context gathering.
   - This front-loads alignment and surfaces hidden complexity before any code investigation.

1. **Context gathering:**
   - Read ALL mentioned files completely (tickets, docs, configs).
   - Spawn research subagents to find relevant code, patterns, and historical docs.
   - Read everything the subagents identify.
   - Present informed understanding with focused questions (only ask what code investigation can't answer).

2. **Research & discovery:**
   - If user corrects a misunderstanding, verify the correction through code — don't just accept it.
   - Spawn parallel subagents for deep investigation.
   - Present design options with trade-offs.

3. **Structure development:**
   - Propose phase outline and get feedback before writing details.

4. **Detailed plan writing:**
   - Write main plan file + separate file per phase.
   - Use pseudocode notation (see [pseudocode-notation.md](pseudocode-notation.md)).
   - Separate automated vs. manual success criteria.
   - Maximum 3 `[NEEDS CLARIFICATION]` markers; resolve all before finalizing.

5. **Review & iteration:**
   - Present draft, get feedback, iterate until user is satisfied.
   - No unresolved questions in the final plan.

**Key principles:**
- Be skeptical: question vague requirements, identify edge cases early.
- Be interactive: don't write the whole plan in one shot. Get buy-in at each step.
- Be thorough: include file:line references, measurable success criteria.
- Explicitly list what you are NOT doing (prevent scope creep).

### Phase Completion Criteria

A plan is **done** when:
- [ ] Every phase has specific files to create/modify (no "update relevant files")
- [ ] Every phase has automated success criteria with exact commands to run
- [ ] Pseudocode notation is used for non-trivial logic changes
- [ ] The scope exclusion list is explicit ("NOT doing: ...")
- [ ] Zero `[NEEDS CLARIFICATION]` markers remain
- [ ] The user has reviewed and approved the plan
- [ ] Phase files exist for every phase (separate files, not inline)

A plan is **NOT done** if:
- Any success criterion is subjective ("code should be clean")
- A phase modifies more than 5-7 files (split it)
- Dependencies between phases are not documented
- Manual testing is listed without explaining why automation is impossible
- Independent phases exist but aren't marked `[batch-eligible]` (check for `/batch` opportunities)

---

## Phase 3: Implement

**Purpose:** Execute the approved plan one phase at a time with review gates.

**Process:**

1. Read the plan completely. Check for existing checkmarks.
2. Gather context via Explore subagents.
3. Create a todo list to track progress.
4. For each phase:
   - Delegate implementation to subagent(s) (up to 3 concurrent).
   - When done, submit to a **reviewer subagent**.
   - If reviewer requests fixes -> send back to implementer -> re-review.
   - Repeat until reviewer approves.
   - Run ALL automated verification.
   - Mark phase complete in the plan file.
   - **STOP. Wait for human confirmation before next phase.**

**The atomic loop:**
```
Implement (atomic change)
    → Review (subagent — plan compliance)
    → Fix if needed
    → Re-review
    → Approve
    → /simplify (Anthropic-native code quality pass)
    → Run verification
    → Mark complete
    → STOP — wait for human
```

**Native command integration:**

- **`/simplify`** — runs after the reviewer approves plan compliance. Spawns 3 parallel agents (code reuse, code quality, efficiency) and applies fixes automatically. This separates concerns: reviewer checks plan compliance, `/simplify` handles code quality. Because `/simplify` is Anthropic-maintained, it improves without blueprint changes.
- **`/batch`** — when the plan marks phases as `[batch-eligible]` (independent, no file overlap), `/batch` can execute them all in parallel. Each phase runs in its own git worktree and opens a PR. Use this instead of sequential phase-by-phase when phases are truly independent.

**If stuck:**
- Get help from subagents for targeted debugging.
- If plan doesn't match reality, STOP and present the mismatch clearly:
  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]
  How should I proceed?
  ```

**Reviewer powers:** The reviewer subagent can add tests to the verification checks, strengthening quality.

### Phase Completion Criteria

An implementation phase is **done** when:
- [ ] All files listed in the phase plan are created/modified
- [ ] The reviewer subagent approves plan compliance (no open fix requests)
- [ ] `/simplify` has been run on changed files (code quality pass)
- [ ] Every automated success criterion passes (typecheck, lint, tests)
- [ ] Checkboxes in the plan file are updated
- [ ] No unrelated changes are included (atomic scope)
- [ ] Human has confirmed and approved before next phase

An implementation phase is **NOT done** if:
- Any automated check fails (even if the failure "looks unrelated")
- The reviewer subagent identified issues that weren't addressed
- `/simplify` was skipped (always run it — it's fast and catches real issues)
- The phase modified files not listed in the plan (scope creep)

---

## Phase 4: Validate

**Purpose:** Verify the implementation matches the plan and all success criteria pass.

**Process:**

1. Locate the plan (provided or discovered via git log).
2. Gather evidence: git log, git diff, run test suites.
3. For each phase:
   - Verify completion status matches reality.
   - Run every automated verification command.
   - Assess manual criteria.
   - Think about edge cases.
4. Generate a validation report.

**Validation report structure:**

```markdown
## Validation Report: [Plan Name]

### Implementation Status
- [x] Phase 1: [Name] — Fully implemented
- [!] Phase N: [Name] — Partially implemented

### Automated Verification Results
- [x] Build passes
- [ ] Linting issues (details)

### Code Review Findings
#### Matches Plan
#### Deviations from Plan
#### Potential Issues

### Manual Testing Required
(Only if automation is impossible; explain WHY for each item)

### Recommendations
```

### Phase Completion Criteria

Validation is **done** when:
- [ ] Every plan phase has been checked against the actual code
- [ ] All automated verification commands have been run and results recorded
- [ ] Deviations from the plan are documented with explanations
- [ ] The validation report is complete with a clear verdict
- [ ] Manual testing items (if any) are listed with justification for why automation is impossible

Validation is **NOT done** if:
- Any automated check was skipped
- Deviations were found but not explained
- The report omits phases or success criteria from the original plan

---

## Failure Recovery

When things go wrong during any phase, follow these decision trees instead of guessing.

### Research Comes Back Wrong or Incomplete

```
Research quality issue detected
├── Findings contain opinions/suggestions?
│   └── Strip them. Re-run the offending subagent with stricter documentarian prompt.
├── Missing file:line references?
│   └── Re-run the subagent. "Every claim needs file:line. No exceptions."
├── Key areas not covered?
│   └── Spawn targeted subagents for the missing areas. Don't redo everything.
├── Fundamentally wrong understanding?
│   └── Throw it out entirely. Start a fresh /research with more specific steering.
└── Open questions block planning?
    └── Present them to the user. Get answers before proceeding to /plan.
```

### Plan Doesn't Match Reality During Implementation

```
Mismatch discovered mid-implementation
├── Minor: file moved/renamed since plan was written?
│   └── Fix the reference. Note the correction in the plan file. Continue.
├── Moderate: API/interface differs from what plan assumed?
│   └── STOP. Report: Expected [X], Found [Y], Why it matters.
│       ├── User says "adapt the plan" → update plan file, continue
│       └── User says "go back to research" → /clear, new /research session
├── Major: the approach won't work (wrong architecture, missing dependency)?
│   └── STOP. Do NOT attempt a workaround.
│       Report what you found and why the plan can't proceed.
│       User decides: revise plan, new research, or abandon.
└── Tests reveal the plan's assumptions were wrong?
    └── STOP. Present the failing test with explanation.
        The plan needs revision before more code is written.
```

### CI Fails After Push (Background Agent)

```
CI failure detected
├── Attempt 1: Read the failure log
│   ├── Lint/format error → fix and re-push
│   ├── Type error → fix and re-push
│   ├── Test failure (test is correct) → fix the code and re-push
│   └── Test failure (test is wrong) → fix the test and re-push
├── Attempt 2: Different failure after fix?
│   └── Read the new failure. Fix and re-push.
├── Attempt 3: Still failing?
│   └── STOP. Report to the user:
│       - What failed (exact error)
│       - What you tried (all 3 attempts)
│       - Why you think it's stuck
│       Do NOT retry a 4th time. Do NOT force-push.
└── Failure is in unrelated code (not your changes)?
    └── Report to the user. Don't fix code you didn't change
        unless the user explicitly asks.
```

### Subagents Disagree or Return Conflicting Results

```
Conflicting subagent results
├── Both found different code paths for the same feature?
│   └── Both may be correct. Synthesize: "Path A handles X, Path B handles Y."
│       Spawn a follow-up agent to trace which path runs in which scenario.
├── One says a function exists, another says it doesn't?
│   └── Trust the one with file:line references. Discard the one without.
│       If both have references, read the files yourself to resolve.
├── Different agents recommend conflicting approaches?
│   └── Research agents shouldn't recommend anything (documentarian rule).
│       If they did, strip the recommendations. Present the facts to the user.
└── One agent failed/timed out?
    └── Use results from successful agents. Re-run the failed one once.
        If it fails again, proceed without it and note the gap.
```

### Scheduled Agent Crashes

```
Scheduled agent failure
├── Claude CLI crashed (non-zero exit)?
│   └── Check the log file. Common causes:
│       - Context too large → reduce the agent's scope
│       - Rate limited → increase the interval between runs
│       - Network timeout → add retry logic to the shell script
├── Agent ran but produced no report?
│   └── Check if the output directory exists and has write permissions.
│       Check if the agent prompt is correctly formatted.
├── Agent ran but report is empty/useless?
│   └── Review the prompt. The agent likely needs more specific instructions
│       or the shared context file is missing/stale.
└── Two agents ran simultaneously and conflicted?
    └── Stagger their schedules (don't run at the same time).
        If both write to the same file, use separate output files
        and a synthesis step.
```

### Validation Reveals Major Issues

```
Validation finds problems
├── Missing functionality (plan says implemented, code doesn't have it)?
│   └── Go back to /implement for the affected phase.
│       Do NOT start a new plan — the plan is correct, execution was incomplete.
├── Wrong behavior (code does something different from the plan)?
│   └── Determine: is the plan wrong or the code wrong?
│       ├── Plan was wrong (edge case not considered) → revise plan, then fix code
│       └── Code diverged from plan → fix code to match plan
├── Tests pass but behavior is wrong?
│   └── Tests are incomplete. Write the missing test (Red), then fix (Green).
├── Performance/security concern not in the plan?
│   └── Log it as a finding in the validation report.
│       User decides whether to address now or defer.
└── All automated checks pass but something feels off?
    └── Document the concern specifically. "Feels off" is not actionable.
        Either write a test that captures the concern or move on.
```
