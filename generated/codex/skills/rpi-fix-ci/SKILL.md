---
name: "rpi-fix-ci"
description: "Diagnose existing CI failures and repair them locally with complete verification, without hosted reruns or iterative publication."
---

Self-healing CI: diagnose and fix all failing tests autonomously.

Process:

1. Identify the failed run or candidate in the request, then discover the actual
   branch and commit. Inspect existing runs using `gh run list --branch <branch>
   --commit <sha> --json databaseId,headSha,conclusion,status,name`. Distinguish
   missing/pending runs from passed checks. If no failure exists, report and stop.

2. Get the failure logs:
   `gh run view <run-id> --log-failed 2>&1 | tail -200`

3. Parse failures into individual test/check failures. Group by:
   - Type errors (typecheck)
   - Lint errors
   - Test failures (list each failing test)
   - Build failures

4. Group failures by root cause and file ownership. Use bounded independent
   local fix assignments when useful, up to three concurrent implementers. Each
   assignment must:
   a. Read the failing test file and the source file it covers
   b. Identify the root cause from the error message
   c. Fix the SOURCE code (never weaken or delete a test)
   d. Verify that specific test passes locally

5. For typecheck/lint/build failures, fix them directly (these are usually straightforward).

6. After all fixes, run the full test suite locally:
   the project's complete local CI-equivalent gate, including applicable coverage, typechecks, lint and build. Use `&&` or aggregate failures explicitly.

7. If new failures appear, repeat the fix cycle (max 3 iterations).

8. When all checks pass, commit with message:
   `fix: resolve CI failures [auto]`
   Keep the repair branch local. Integrate only the complete verified result
   locally. Inspect triggers before any single authorized integration push;
   never create Previews, rerun hosted jobs, or re-push as a debugging loop.

Rules:
- Never weaken a test to make it pass — fix the source code.
- Never delete a test.
- If a failure is flaky (passes locally, fails in CI), note it but don't skip.
- If stuck after 3 fix cycles, stop and report what remains broken.
- Verify the current branch before committing.
- CI repair happens in a task-owned local branch/worktree based on the failed
  candidate; no remote branch writes or hosted debugging loops.
  Never push directly to a protected production branch without explicit
  approval.

## Execution and acceptance

Use the scope and authorization already supplied in the request. Resolve routine
implementation choices from repository evidence. Complete authorized local work,
review, repair and applicable verification before its acceptance gate. An explicit
instruction can authorize continuation across phases; otherwise stop at the stated
phase boundary. Production, publication, destructive actions and new scope retain
their actual authorization requirements. Preserve durable artifacts before cleanup.
