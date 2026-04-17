# Push Accountability

> Every push that triggers shared CI requires verification. No
> exceptions. No matter how small the change.

## The Problem

Without push accountability, the most common failure mode is "push and forget" — the agent pushes code, moves on to the next task, and never checks whether CI passed. By the time someone notices, multiple commits may have piled on top of a broken build.

## The Protocol

After any push to the branch currently under CI verification, the agent
must verify that CI passes. In repos with a dedicated integration branch
such as `develop`, this usually means every push to that branch. In
`main-only` repos, the same accountability applies to the temporary
implementation branch or PR branch before asking for merge. This happens
as a **background task** so the main terminal stays unblocked.

### Sequence

```
1. Agent pushes to the branch under test
   └─> Immediately spawns a background verification agent

2. Background agent polls CI status
   └─> gh run list --branch <branch-under-test> --limit 5
   └─> Repeat every 30-60 seconds until the run completes

3a. CI passes
    └─> Log success, no interruption needed

3b. CI fails
    └─> Investigate: gh run view <run-id> --log-failed
    └─> Diagnose the root cause from the logs
    └─> Fix the issue in the same branch
    └─> Push the fix
    └─> Return to step 2 (poll again)
```

### Background Agent Pattern

```bash
# Spawn as a background Task agent after every push:
# - Polls CI until completion
# - On failure: reads logs, fixes, re-pushes
# - On success: logs and exits
# - Never touches production branches
```

In Claude Code, this maps to `Task` with `run_in_background: true`:

```
Task(
  subagent_type="Bash",
  run_in_background=true,
  prompt="Monitor CI for the latest push to <branch-under-test>. Poll gh run list --branch <branch-under-test> --limit 1 every 30 seconds until it completes. If it fails, run gh run view <id> --log-failed, diagnose the issue, fix it, and push again. If it passes, report success. Never modify the protected production branch from this loop."
)
```

## Rules

1. **Every push gets a monitor.** No exceptions. Even single-line changes can break CI if they affect types, imports, or test fixtures.
2. **Background, not blocking.** The main terminal continues working on the next task immediately. The background agent owns the push outcome.
3. **Fix and re-push.** If CI fails, the background agent fixes the issue and pushes again. It doesn't report back and wait — it acts.
4. **Never touch production from a fix loop.** Even if a fix seems
   urgent, background agents operate on the branch under test, not the
   protected production branch.
5. **Conflict awareness.** If the background fix requires changes that conflict with the main terminal's current work, notify the user before applying.
6. **Retry budget.** If CI fails 3 times after 3 fix attempts, the background agent stops and reports the issue clearly.

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

Push accountability's background fix loop handles simple CI failures — a single failing test, a lint error, a type mismatch. But when CI fails with multiple unrelated failures (common after config changes, dependency updates, or multi-agent work), a more aggressive approach is needed.

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

6. Commit and push when green
```

### Rules

1. **Never weaken a test to make it pass.** Fix the source code, not the test. Deleting or weakening a test to pass CI defeats the purpose.
2. **Fix agents read both the test and the source.** A fix agent that only reads the error message will produce shallow fixes. It must understand the intent of the failing test.
3. **Run the full suite after combining fixes.** Individual fix agents verify their own changes, but the combined result may introduce new failures. Always run a full verification pass.
4. **Retry budget: 3 cycles.** If the suite isn't green after 3 fix-and-verify cycles, stop and report what remains broken. Infinite loops are worse than a failing CI.
5. **Never push to production from a fix loop.** Self-healing operates
   on the branch under test only. In repos where the production branch
   is also the long-lived integration branch, do the repair work on a
   temporary branch or worktree and merge with human approval.

### Slash Command

The `/fix-ci` command (see `templates/commands/fix-ci.md`) implements this pattern as a single invocation. It gets the latest CI failure, parses it, spawns fix agents, and iterates until green or the retry budget is exhausted.

---

## Integration with RPI

Push accountability sits between the Implement and Validate phases:

1. **Implement** — Write code, run local checks, commit, push
2. **Push accountability** — Background agent verifies CI (this file)
3. **Validate** — Human reviews the implementation against the plan

The background agent ensures that by the time the human reviews, CI is already green.
