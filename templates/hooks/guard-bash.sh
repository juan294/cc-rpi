#!/usr/bin/env bash
# guard-bash.sh — PreToolUse hook for Bash tool calls
# Blocks known-bad command patterns before they execute.
# Runs on every Bash tool call — keep guards fast.
#
# Location: .claude/hooks/guard-bash.sh (in projects)
# Config:   .claude/settings.json → hooks.PreToolUse
# Input:    JSON on stdin: { "tool_name": "Bash", "tool_input": { "command": "..." } }
# Output:   exit 0 = allow, exit 2 = block (stdout shown to agent as reason)
#
# Add project-specific guards at the bottom of this file.

set -uo pipefail

# Require jq for JSON parsing — allow through if unavailable
if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0


# ─── Guard: git pull --rebase with uncommitted changes (Error #33) ────────
# The #1 most-repeated agent error (37% of all observed errors in one batch).
# Agent edits files, then runs git pull --rebase without committing first.
if echo "$COMMAND" | grep -q 'git pull' && echo "$COMMAND" | grep -q -- '--rebase'; then
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "BLOCKED by guard-bash.sh — Error #33: uncommitted changes"
    echo ""
    echo "git pull --rebase will fail with a dirty working tree."
    echo "Commit or stash first, then pull:"
    echo ""
    echo "  git add <files> && git commit -m \"msg\""
    echo "  git pull --rebase && git push"
    exit 2
  fi
fi


# ─── Guard: git push --tags pushes ALL local tags (Error #44) ─────────────
# Agent uses --tags to push a release tag, but --tags pushes EVERY local tag.
# Old tags that already exist on remote cause a non-zero exit code.
if echo "$COMMAND" | grep -q 'git push' && echo "$COMMAND" | grep -q -- '--tags' && ! echo "$COMMAND" | grep -q -- '--follow-tags'; then
  echo "BLOCKED by guard-bash.sh — Error #44: --tags pushes all local tags"
  echo ""
  echo "--tags pushes every tag, not just new ones. Old tags cause failures."
  echo "Push specific tags or use --follow-tags:"
  echo ""
  echo "  git push origin main && git push origin v1.0.0"
  echo "  git push origin main --follow-tags"
  exit 2
fi


# ─── Project-specific guards below this line ──────────────────────────────

# Example: block bare python3 (uncomment for Python/uv projects)
# if echo "$COMMAND" | grep -qE '^python3?\s' && ! echo "$COMMAND" | grep -qE 'uv run|poetry run|pipenv run'; then
#   echo "BLOCKED — use 'uv run python' instead of bare 'python3'"
#   echo "System Python doesn't have project dependencies."
#   exit 2
# fi


exit 0
