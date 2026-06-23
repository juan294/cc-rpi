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
# Block messages use the corrective-hint convention (BLOCKED / WHY / FIX) via
# emit_block — a block is a guided correction, not just a stop. See
# methodology/ci-and-guardrails.md "Block messages are corrective hints".
#
# Add project-specific guards at the bottom of this file.

# Intentionally no `set -e` — this script is fail-open by design.
# If any check fails unexpectedly (jq missing, git not in PATH, etc.),
# execution falls through to exit 0 and the command is allowed.
# A guard hook must never block legitimate work due to its own bugs.
set -uo pipefail

# emit_block <hook> <reason> <why> <fix> — print a corrective-hint block.
# $4 (fix) may be multi-line; keep its own indentation.
emit_block() {
  printf 'BLOCKED by %s — %s\n\nWHY: %s\n\nFIX:\n%s\n' "$1" "$2" "$3" "$4"
}

# Require jq for JSON parsing — allow through if unavailable
if ! command -v jq &>/dev/null; then
  exit 0
fi

read -r -d '' INPUT || true
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0

# Fast path: skip all guards for non-git commands (~90% of invocations)
[[ "$COMMAND" != *git* ]] && exit 0


# ─── Guard: git pull --rebase with uncommitted changes (Error #33) ────────
# The #1 most-repeated agent error (37% of all observed errors in one batch).
# Agent edits files, then runs git pull --rebase without committing first.
if [[ "$COMMAND" == *"git pull"* ]] && [[ "$COMMAND" == *"--rebase"* ]]; then
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    emit_block "guard-bash.sh" "Error #33: uncommitted changes" \
      "git pull --rebase fails with a dirty working tree." \
      "  git add <files> && git commit -m \"msg\"
  git pull --rebase && git push"
    exit 2
  fi
fi


# ─── Guards: git push risks (Error #44, Error #48) ───────────────────────
# Consolidated: both guards share the outer "git push" check.
if [[ "$COMMAND" == *"git push"* ]]; then

  # Error #44: --tags pushes ALL local tags, not just the new one.
  # Old tags that already exist on remote cause a non-zero exit code.
  if [[ "$COMMAND" == *"--tags"* ]] && [[ "$COMMAND" != *"--follow-tags"* ]]; then
    emit_block "guard-bash.sh" "Error #44: --tags pushes all local tags" \
      "--tags pushes every tag, not just new ones; old tags cause failures." \
      "  git push origin main && git push origin v1.0.0
  git push origin main --follow-tags"
    exit 2
  fi

  # Error #48: direct push to main/master instead of a non-production path.
  # Matches "main" or "master" anywhere in the push args (handles flags like -u
  # appearing before the remote name: git push -u origin main).
  # Allows --follow-tags (release flow).
  if [[ "$COMMAND" =~ (^|[[:space:]])(main|master)($|[[:space:]]|:) ]] \
     && [[ "$COMMAND" != *"--follow-tags"* ]]; then
    emit_block "guard-bash.sh" "Error #48: direct push to protected branch" \
      "Pushing directly to main/master is a high-stakes action." \
      "  git push origin develop                 # develop/main topology
  git push -u origin feature/my-change    # main-only or PR flow
  git push origin main --follow-tags      # releases with tags (ask first)"
    exit 2
  fi

fi


# ─── Project-specific guards below this line ──────────────────────────────

# Example: block bare python3 (uncomment for Python/uv projects)
# if [[ "$COMMAND" =~ ^python3?[[:space:]] ]] && [[ "$COMMAND" != *"uv run"* ]] && [[ "$COMMAND" != *"poetry run"* ]]; then
#   emit_block "guard-bash.sh" "Rule #44: bare python3" \
#     "System Python doesn't have project dependencies." \
#     "  uv run python <args>"
#   exit 2
# fi


exit 0
