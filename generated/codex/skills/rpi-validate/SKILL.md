---
name: "rpi-validate"
description: "Verify each implementation phase against its approved plan, deviation notes, actual changes and valid automated acceptance evidence."
---

Validate the implementation against the plan.

Process:
1. Locate the plan (provided path or search recent git history).
   Read `docs/plans/<plan-name>-notes.md` if it exists — `rpi-implement` logs its
   deviations there, so cite them rather than reconstructing intent from the diff.
2. Gather evidence: git log, git diff, run test suites.
3. For each phase:
   - Verify marked-complete items are actually done.
   - Run every applicable automated verification command, or reuse valid
     evidence when candidate inputs and check selection are unchanged.
   - Think about edge cases.
4. Save `docs/agents/validation-report.md` with:
   - Implementation status per phase
   - Automated verification results
   - Code review findings (matches, deviations, issues)
   - Manual testing required (only if automation impossible — explain WHY)
   - Recommendations
5. If code quality issues are found (reuse opportunities, inefficiencies,
   dead code), recommend running the harness-native simplify pass (or the Codex simplify helper), reviewing reuse, quality and efficiency to fix them in one pass.
6. Then offer — do not force — a short explainer of what changed and why,
   with the non-obvious behavior called out, for whoever reviews the merge.
   Produce it only if the human asks.

## Execution and acceptance

Use the scope and authorization already supplied in the request. Resolve routine
implementation choices from repository evidence. Complete authorized local work,
review, repair and applicable verification before its acceptance gate. An explicit
instruction can authorize continuation across phases; otherwise stop at the stated
phase boundary. Production, publication, destructive actions and new scope retain
their actual authorization requirements. Preserve durable artifacts before cleanup.
