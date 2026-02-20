# Push Accountability

> Every push to the development branch requires CI verification. No exceptions. No matter how small the change.

## The Problem

Without push accountability, the most common failure mode is "push and forget" — the agent pushes code, moves on to the next task, and never checks whether CI passed. By the time someone notices, multiple commits may have piled on top of a broken build.

## The Protocol

After ANY push to the development branch, the agent must verify that CI passes. This happens as a **background task** so the main terminal stays unblocked.

### Sequence

```
1. Agent pushes to develop
   └─> Immediately spawns a background verification agent

2. Background agent polls CI status
   └─> gh run list --branch develop --limit 5
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
  prompt="Monitor CI for the latest push to develop. Poll gh run list --branch develop --limit 1 every 30 seconds until it completes. If it fails, run gh run view <id> --log-failed, diagnose the issue, fix it, and push again. If it passes, report success. Never push to main."
)
```

## Rules

1. **Every push gets a monitor.** No exceptions. Even single-line changes can break CI if they affect types, imports, or test fixtures.
2. **Background, not blocking.** The main terminal continues working on the next task immediately. The background agent owns the push outcome.
3. **Fix and re-push.** If CI fails, the background agent fixes the issue and pushes again. It doesn't report back and wait — it acts.
4. **Never touch production.** Even if a fix seems urgent, background agents only operate on the development branch.
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
gh run list --branch develop --limit 3 --json conclusion,status,name,databaseId
gh run view <run-id> --log-failed 2>&1 | tail -100
```

## Integration with RPI

Push accountability sits between the Implement and Validate phases:

1. **Implement** — Write code, run local checks, commit, push
2. **Push accountability** — Background agent verifies CI (this file)
3. **Validate** — Human reviews the implementation against the plan

The background agent ensures that by the time the human reviews, CI is already green.
