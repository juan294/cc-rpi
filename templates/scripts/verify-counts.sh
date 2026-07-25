#!/usr/bin/env bash
# verify-counts.sh — reconcile hardcoded error/rule counts against the catalogs.
#
# patterns/agent-errors.md and patterns/quick-reference.md are the source of
# truth for the error and rule counts. Every other file that states those
# counts in prose or JSON must agree, or it silently drifts (the same failure
# mode as the release version-scan gap). Run this from anywhere; it resolves
# the repo root itself.
#
# Usage: templates/scripts/verify-counts.sh   (or the .claude/scripts/ copy)
# Exit:  0 = all counts agree, 1 = at least one mismatch (see BLOCKED/WHY/FIX)

set -euo pipefail

# Resolve the repo root regardless of which copy is invoked from
# (templates/scripts/ and .claude/scripts/ live at different depths).
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
}
cd "$REPO_ROOT"

ERRORS_FILE="patterns/agent-errors.md"
RULES_FILE="patterns/quick-reference.md"

# emit_block <what> <why> <fix> — corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n' "$1" "$2" "$3"
}

FAILED=0

# --- Compute the true counts from the catalogs ---------------------------
ERROR_COUNT=$(grep -c '^## Error #' "$ERRORS_FILE")
RULE_COUNT=$(grep -cE '^[0-9]+\.' "$RULES_FILE")
SKILL_COUNT=$(find templates/skills -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')

# --- check_count <file> <pattern> <label> ---------------------------------
# Extracts the first number matched by <pattern> in <file> and compares it
# against the expected count captured in the pattern's own match (the
# caller passes the expected value separately for the message).
check_count() {
  local file="$1" pattern="$2" expected="$3" label="$4"

  if [[ ! -f "$file" ]]; then
    emit_block "$label expected in $file, but the file does not exist" \
      "A count location was renamed or removed without updating verify-counts.sh." \
      "  Update templates/scripts/verify-counts.sh (and the .claude/scripts/ copy) to match the new location, or restore $file."
    FAILED=1
    return
  fi

  local found
  found=$(grep -oE "$pattern" "$file" | grep -oE '[0-9]+' | head -1 || true)

  if [[ -z "$found" ]]; then
    emit_block "$label not found in $file" \
      "The count reference was removed or reworded past what verify-counts.sh matches, so drift here would go undetected." \
      "  Restore a line matching pattern: $pattern
  in $file, or update verify-counts.sh's pattern for this location."
    FAILED=1
    return
  fi

  if [[ "$found" != "$expected" ]]; then
    emit_block "$label in $file says $found, catalog says $expected" \
      "A stale hardcoded count misleads anyone reading $file about the size of the catalog." \
      "  sed -i '' 's/\\b'\"$found\"'\\b/'\"$expected\"'/' $file   # macOS
  sed -i 's/\\b'\"$found\"'\\b/'\"$expected\"'/' $file      # Linux
  # then re-check the edit didn't touch an unrelated number in the same file"
    FAILED=1
  fi
}

# --- Known hardcoded locations ---------------------------------------------
check_count "CLAUDE.md" '[0-9]+ errors' "$ERROR_COUNT" "Error count"
check_count "CLAUDE.md" '[0-9]+ rules' "$RULE_COUNT" "Rule count"

check_count "GUIDE.md" '[0-9]+ operational rules' "$RULE_COUNT" "Rule count (philosophy section)"
check_count "GUIDE.md" '[0-9]+ documented errors' "$ERROR_COUNT" "Error count (Where to Go Deeper)"
check_count "GUIDE.md" 'Index of [0-9]+ rules' "$RULE_COUNT" "Rule count (Where to Go Deeper)"

check_count "$ERRORS_FILE" '^[0-9]+ documented error patterns' "$ERROR_COUNT" "Error count (catalog header)"

check_count ".claude-plugin/plugin.json" '[0-9]+-pattern' "$ERROR_COUNT" "Error count (plugin manifest)"
check_count ".claude-plugin/marketplace.json" '[0-9]+-pattern' "$ERROR_COUNT" "Error count (marketplace manifest)"

check_count "templates/skills/error-patterns/SKILL.md" '[0-9]+-error catalog' "$ERROR_COUNT" "Error count (error-patterns skill)"

# Skill count -- adding a skill directory without updating the prose is the
# same drift class as the rule and error counts.
check_count "GUIDE.md" 'The [0-9]+ blueprint-provided skills' "$SKILL_COUNT" "Skill count (progressive disclosure section)"
check_count "GUIDE.md" '[0-9]+ blueprint-provided skills for progressive disclosure' "$SKILL_COUNT" "Skill count (Where to Go Deeper)"
check_count "CLAUDE.md" '[0-9]+ domain skills' "$SKILL_COUNT" "Skill count (file locations table)"

# Bonus location found by a whole-repo sweep, not in the original nine —
# kept here so it can't silently drift again.
check_count "templates/commands/bootstrap.md" '[0-9]+-error catalog' "$ERROR_COUNT" "Error count (bootstrap command)"

# --- No duplicate rule numbers ----------------------------------------------
DUPES=$(grep -oE '^[0-9]+\.' "$RULES_FILE" | tr -d '.' | sort -n | uniq -d || true)
if [[ -n "$DUPES" ]]; then
  emit_block "Duplicate rule number(s) in $RULES_FILE: $DUPES" \
    "Two rules sharing one number makes cross-references (agent-errors.md, commands, CHANGELOG.md) ambiguous." \
    "  Renumber the newer rule to one past the current maximum, per .claude/rules/contributing.md's retirement/renumbering guidance."
  FAILED=1
fi

# --- Every index destination resolves ---------------------------------------
# patterns/quick-reference.md is an index: each rule line ends in
# "-> <destination>". If a destination stops existing, the rule has silently
# lost its home and no longer loads anywhere. That is the failure mode
# relocation introduces, so it is checked mechanically.
UNRESOLVED=""
while IFS= read -r dest; do
  case "$dest" in
    hook:*) target="templates/hooks/${dest#hook: }" ;;
    skills/*) target="templates/${dest}/SKILL.md" ;;
    rules/*|commands/*) target="templates/${dest}" ;;
    methodology/*) target="$dest" ;;
    *) target="$dest" ;;
  esac
  [[ -e "$target" ]] || UNRESOLVED="$UNRESOLVED
  $dest -> $target"
done < <(
  grep -oE '^[0-9]+\..* -> .*$' "$RULES_FILE" \
    | sed 's/.* -> //' \
    | tr '+' '\n' \
    | sed 's/^ *//; s/ *$//' \
    | sort -u
)

if [[ -n "$UNRESOLVED" ]]; then
  emit_block "Rule index destination(s) do not exist:$UNRESOLVED" \
    "A rule whose destination is missing has no surface that loads it -- the rule is effectively deleted without going through the retirement ledger." \
    "  Either restore the destination file, or retire the rule properly per the 'Retiring a Rule or Error' section of .claude/rules/contributing.md and remove its index line."
  FAILED=1
fi

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "PASS: $ERROR_COUNT errors, $RULE_COUNT rules, $SKILL_COUNT skills, no duplicates,"
echo "      all hardcoded locations agree, all index destinations resolve."
exit 0
