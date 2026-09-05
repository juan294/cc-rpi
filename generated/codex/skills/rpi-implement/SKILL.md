---
name: "rpi-implement"
description: "Execute an approved phased plan through implementation, review, repair, simplify and complete local verification before each acceptance boundary."
---

# Implement the Approved Plan

Use the plan path and selected phases in the request. Read the entire plan and
current phase specifications, existing checkmarks and deviation/handoff notes.

## Process

1. Gather the relevant code, tests and project rules. Use bounded independent
   research assignments when helpful; do not repeat completed research without a
   concrete uncertainty.
2. Track tasks and work in an isolated local branch/worktree. Research and planning
   start from the documented integration branch. Verify branch identity before
   every commit and preserve unrelated work.
3. Check `[batch-eligible]` markings. Parallel phases require no file overlap or
   dependencies and explicit continuation scope. Keep each worktree local. Disable
   native batch publication or coordinate local worktrees directly when it cannot
   be disabled. One integration owner manages commits/merges; no feature PRs.
4. For the current authorized phase, select bounded implementation assignments
   with distinct file ownership and at most three concurrent implementers. A single
   implementer is sufficient when parallelism adds no value.
5. For behavioral code changes, write a failing test first, verify that it captures
   the required behavior and preserves affected invariants, then implement the
   minimum correct change. Never weaken a valid test to hide a defect.
6. Review plan compliance independently: every planned item, acceptance criterion
   and confirmed actionable finding must be accounted for. Repair findings and
   repeat review until approved. Reject false positives with concrete evidence;
   architectural/new-scope decisions remain explicit unresolved dispositions.
7. Run the harness-native simplify pass (or the Codex simplify helper), reviewing reuse, quality and efficiency.
   Apply confirmed improvements and verify any changed tested inputs.
8. Run the complete applicable local gate: tests, coverage, typechecks, lint, build,
   repository invariants and deployment preflight. Sequence resource-intensive
   checks and preserve every exit status. Reuse valid evidence only when the
   candidate inputs and check selection are unchanged.
9. Mark completed items and save a durable handoff with commit identity, touched
   components, test results, finding disposition and next-phase entry conditions.
   Record deviations in `docs/plans/<plan-name>-notes.md` under `## Deviations`:
   plan said / found / chose / why. Preserve approved plans, phase files and notes
   as curated history; raw operational evidence follows visibility policy.
10. Integrate completed work locally and verify the combined result. Inspect
    hosted triggers before any single authorized integration push. Never create
    Vercel Previews, publish working branches/PRs or debug through hosted CI.

## Phase boundary and preservation

Complete implement -> review -> fix -> approve -> simplify -> verify before the
phase acceptance report. Stop after that phase unless the user explicitly
requested continuation. Retain per-phase evidence and handoffs even during an
all-phases run. Do not remove a worktree until changes, plans, handoffs, untracked
files and ignored evidence are preserved and integration/ownership established.

If reality invalidates the plan, explain Expected / Found / Why it matters and
record the necessary plan adjustment before dependent work. Routine path/name
corrections do not require a new approval; an unresolved architecture or scope
decision does. Never silently bypass a failed acceptance requirement.
