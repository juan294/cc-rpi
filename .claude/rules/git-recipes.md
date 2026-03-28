---
description: Git recipes and push sequences for cc-rpi -- main-only workflow, tag management, worktree cleanup
---

# Git Recipes

Hooks enforce critical steps (Errors #33, #44, #48).

```bash
# Push sequence -- ALWAYS commit before pulling
git add <files> && git commit -m "msg"
git pull --rebase && git push

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
