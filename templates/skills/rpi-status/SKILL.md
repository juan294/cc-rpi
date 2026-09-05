---
name: rpi-status
description: "Report concise project orientation, working tree, recent commits, known CI status and open items, then stop."
---

Quick project status check. Output a concise orientation and stop.

Run these commands and present the results in a compact summary:

1. `git branch --show-current` — current branch
2. `git log --oneline -3` — last 3 commits
3. `git status --short` — uncommitted changes (if any)
4. If available, inspect existing CI for the branch and candidate commit
   discovered above using `gh run list --branch <branch> --commit <sha>
   --json conclusion,status,name`. Label unavailable, missing and pending
   results distinctly; do not run hosted jobs.
5. Check shared AGENTS.md, the current handoff and open session tasks for items

Present as a 5-line summary:

```
Branch: <branch>
Last commit: <message> (<hash>)
Working tree: <clean / N files changed>
CI: <status or "not available">
Open items: <count or "none">
```

Do NOT start any other work. Just report status and stop.

## Execution and acceptance

Use the scope and authorization already supplied in the request. Resolve routine
implementation choices from repository evidence. Complete authorized local work,
review, repair and applicable verification before its acceptance gate. An explicit
instruction can authorize continuation across phases; otherwise stop at the stated
phase boundary. Production, publication, destructive actions and new scope retain
their actual authorization requirements. Preserve durable artifacts before cleanup.
