---
description: Git recipes and push sequences for cc-rpi -- canonical main branch, high-stakes main pushes, worktree cleanup
---

# Git Recipes

Hooks enforce critical steps (Errors #33, #44, #48).

```bash
# Normal implementation branch push sequence
git add <files> && git commit -m "msg"
git pull --rebase && git push

# High-stakes push to main -- only after validation / explicit approval
git checkout main && git pull --rebase
git merge --ff-only <implementation-branch>
git push origin main

# Push with tag -- NEVER use --tags
git push origin main && git push origin v1.0.0
# Or: git push origin main --follow-tags

# Worktree cleanup
git worktree remove --force <path>; git branch -D <branch>
```

## Shell & Tools

- Chain verification commands sequentially,
  never as parallel Bash calls
- Never use `~` in file tool paths --
  use full absolute paths starting with `/`

## GitHub CLI

- Don't guess `gh --json` field names --
  query available fields first
- Check CI per-PR with `--json`,
  not chained human-readable output
