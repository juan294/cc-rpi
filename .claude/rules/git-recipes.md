---
description: Git recipes for cc-rpi -- local integration, authorized main publication, preserved worktree cleanup
---

# Git Recipes

`main` is cc-rpi's canonical integration branch. Working branches stay local.
Run `scripts/verify-local.sh` before integrating and publishing. Inspect remote
workflow/deployment triggers and obtain explicit authorization for the final
main push; never create Vercel Previews or use CI as a debugging loop.

```bash
# In the task-owned worktree, after local gates:
git branch --show-current
git add <files> && git commit -m "msg"
# Check that main has not moved, then integrate in its clean worktree:
git -C /absolute/path/to/main-worktree merge --ff-only <implementation-branch>
# Reuse matching test evidence or verify the integrated candidate locally.
# Only with explicit release/publication authorization:
git push origin main && git push origin <named-release-tag>
```

## Worktree cleanup

Confirm ownership, integration, and preservation of source, plans, handoffs,
untracked files and ignored evidence before removing anything:

```bash
git worktree list --porcelain
git -C /absolute/path/to/worktree status --short --untracked-files=all
git -C /absolute/path/to/worktree ls-files --others --ignored --exclude-standard
git merge-base --is-ancestor <implementation-branch> main
# Only after every precondition above is satisfied:
git worktree remove /absolute/path/to/worktree && git branch -d <implementation-branch>
```

If either operation refuses, retain and investigate. Do not force-remove,
force-delete, or clean up unrelated worktrees.

## Shell & Tools

- Run verification sequentially with `&&` or explicit failure aggregation.
- Use absolute paths in file tools.
- Query `gh` JSON fields from installed help; inspect existing CI by commit.
