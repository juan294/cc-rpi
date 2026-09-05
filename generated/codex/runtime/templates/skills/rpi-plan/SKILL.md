---
name: rpi-plan
description: "Create a cited phased implementation specification with behavioral oracles, explicit scope and measurable automated and manual acceptance criteria."
---

Create an implementation plan for: the request

Process:
1. Read ALL mentioned files completely.
2. Find relevant code, patterns and docs. Use bounded independent research
   assignments when they help resolve the scope; staffing follows the task.
3. Read everything those investigations identify.
4. Present your understanding with focused questions — only ask what code can't answer.
5. After clarifications, spawn deeper research if needed.
6. Present design options with trade-offs.
7. Propose phase structure, get feedback.
8. Write detailed plan with separate phase files.
9. Read [the pseudocode notation](references/pseudocode-notation.md) and use it
   for nontrivial changes. Ground acceptance in executable or checkable evidence.
10. When the plan specifies behavior, prefer pointing at an executable or checkable
    artifact (a failing test, a module with the semantics to match, a mockup, a rubric)
    over describing the behavior in prose.
11. Separate automated vs. manual success criteria.
12. Identify batch-eligible phases: phases that are independent (no file overlap, no
    dependency on another phase's output) get marked `[batch-eligible]` in the plan.
    This permits local worktree parallelism in `rpi-implement`, with one
    integration owner and no working-branch push/PR creation.
13. Use at most three temporary [NEEDS CLARIFICATION] markers and resolve
    every one before final acceptance. Do not fill unknowns with placeholders.
14. Iterate with user until all questions resolved.

Save to docs/plans/YYYY-MM-DD-[description].md
Phase files: docs/plans/YYYY-MM-DD-[description]-phases/phase-N.md

No unresolved questions in the final plan. Present the saved plan and phase-file
paths, acceptance criteria and remaining decisions, then stop at the planning
boundary. Do not implement unless the user explicitly authorized that next workflow.

## Execution and acceptance

Use the scope and authorization already supplied in the request. Resolve routine
implementation choices from repository evidence. Complete authorized local work,
review, repair and applicable verification before its acceptance gate. An explicit
instruction can authorize continuation across phases; otherwise stop at the stated
phase boundary. Production, publication, destructive actions and new scope retain
their actual authorization requirements. Preserve durable artifacts before cleanup.
