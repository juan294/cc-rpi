# The Four Phases

## Architecture Overview

```
User
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
 │                       └── Reviewer subagent
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

## Phase 1: Research

**Purpose:** Build a complete, accurate map of the codebase as it exists today.

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
    → Review (subagent)
    → Fix if needed
    → Re-review
    → Approve
    → Run verification
    → Mark complete
    → STOP — wait for human
```

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
