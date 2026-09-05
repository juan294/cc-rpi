# Push Accountability

> Every push that triggers shared CI requires verification. No
> exceptions. No matter how small the change.

## The Problem

Without push accountability, the most common failure mode is "push and forget" — the agent pushes code, moves on to the next task, and never checks whether CI passed. By the time someone notices, multiple commits may have piled on top of a broken build.

## The Protocol

Keep working branches and worktrees local. Finish applicable tests, coverage,
typechecks, lint, build and deployment preflight locally, resolve failures,
and integrate completed work locally into the documented integration branch.
Inspect workflow and deployment triggers before the single authorized push of
that completed branch. Never create Vercel Preview deployments or publish
working branches/PRs for experimentation. If an integration push would create a
Preview, stop before pushing and use only a documented, non-destructive bypass.
Production publication remains separately and explicitly authorized. Read-only
inspection of existing runs and deployments is allowed.

### Sequence

1. Complete, review, simplify and verify the authorized local work.
2. Integrate completed local branches and verify the integrated candidate.
3. Inspect remote workflow/deployment triggers; publish only the authorized
   completed integration branch once. Production remains separately authorized.
4. Inspect every expected run for the exact pushed commit. A missing or pending
   run is not a pass. Read-only background monitoring may keep the main session
   available without granting the monitor publication rights.
5. On failure, read existing logs, reproduce and repair locally, and report the
   failed remote result. Do not rerun hosted jobs or push iterative fixes.
   Any follow-up publication requires authorization after full local gates.

### Background Agent Pattern

```text
Monitor expected workflows for <published-sha> on <integration-branch>.
Read existing statuses/logs only. Report pending, missing, failed and passed
runs accurately. Diagnose failures locally; do not push, rerun jobs, deploy,
create PRs or modify remote settings.
```

## Rules

1. **Monitor the commit, not just the latest run.** Concurrent remote work can
   make branch-only `--limit 1` queries report the wrong candidate.
2. **Local debugging only.** Existing remote logs are evidence; new hosted
   runs are not an experimentation mechanism.
3. **Preserve task scope and ownership.** Coordinate repairs that overlap other
   local work. Never clean up a worktree before preserving all its artifacts.
4. **Report failures honestly.** A local repair does not retroactively turn
   the already-failed remote run green.

## What CI Failure Looks Like

Common CI failure categories and how to investigate:

| Category | Investigation | Fix Pattern |
|----------|--------------|-------------|
| **Type errors** | Read the typecheck output line by line | Fix types in the reported files |
| **Lint errors** | Read the lint output | Apply autofix or manual corrections |
| **Test failures** | Run the specific failing test locally | Debug and fix the test or implementation |
| **Build failures** | Read the build log for the first error | Fix import/export issues, missing deps |
| **Dependency issues** | Check lockfile, run install | Regenerate lockfile, fix version conflicts |

```bash
# Investigation commands:
gh run list --branch <branch-under-test> --limit 3 \
  --json conclusion,status,name,databaseId
gh run view <run-id> --log-failed 2>&1 | tail -100
```

## Self-Healing CI

Existing CI failure logs may reveal multiple independent failures. Reproduce them locally and assign bounded fixes with distinct file ownership when useful. All repair and verification iterations remain local.

### The Pattern

Instead of fixing failures sequentially, spawn parallel fix agents — one per failure category:

```
1. Get CI failure logs
   └─> gh run view <run-id> --log-failed

2. Parse into failure categories
   ├─ Type errors (N files)
   ├─ Lint errors (N files)
   ├─ Test failures (N tests)
   └─ Build errors

3. Spawn parallel fix agents (one per category)
   ├─ Agent 1: Fix type errors
   ├─ Agent 2: Fix lint errors
   ├─ Agent 3: Fix test failures (one sub-agent per failing test)
   └─ Agent 4: Fix build errors

4. Combine fixes, run full suite locally

5. If new failures → repeat (max 3 cycles)

6. Commit and integrate locally when the full local gate is green; report the candidate
```

### Rules

1. **Never weaken a test to make it pass.** Fix the source code, not the test. Deleting or weakening a test to pass CI defeats the purpose.
2. **Fix agents read both the test and the source.** A fix agent that only reads the error message will produce shallow fixes. It must understand the intent of the failing test.
3. **Run the full suite after combining fixes.** Individual fix agents verify their own changes, but the combined result may introduce new failures. Always run a full verification pass.
4. **Retry budget: 3 cycles.** If the suite isn't green after 3 fix-and-verify cycles, stop and report what remains broken. Infinite loops are worse than a failing CI.
5. **No hosted fix loop.** Repair in local worktrees, run complete local
   gates, and integrate locally. Publication is a separate authorized action.

### Slash Command

The `/fix-ci` command (see `templates/commands/fix-ci.md`) implements this pattern as a single invocation. It gets the latest CI failure, parses it, spawns fix agents, and iterates until green or the retry budget is exhausted.

---

## Integration with RPI

Push accountability sits between the Implement and Validate phases:

1. **Implement** — Write code, review, simplify, verify, commit and integrate locally
2. **Validate** — Review the implementation and complete local gate evidence
3. **Authorized publication** — Inspect triggers, push once, monitor exact-commit runs

Remote status is reported independently from local acceptance evidence.
