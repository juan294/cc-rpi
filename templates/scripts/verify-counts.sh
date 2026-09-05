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

# emit_block <what> <why> <fix> -- corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
#
# Deliberately duplicated in each script and hook rather than sourced from a
# shared lib: these files are copied into downstream projects individually, and
# .claude/ reaches them through symlinks, so `dirname "$BASH_SOURCE"` resolves
# to .claude/scripts/ where no lib/ exists. Self-contained is the repo's
# convention -- guard-bash.sh and verify-edit.sh carry their own copies too.
# Keep the three verify scripts' copies byte-identical.
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n\n' "$1" "$2" "$3"
}

FAILED=0

# --- Compute the true counts from the catalogs ---------------------------
ERROR_COUNT=$(grep -c '^## Error #' "$ERRORS_FILE")
RULE_COUNT=$(grep -cE '^[0-9]+\.' "$RULES_FILE")
MANIFEST_COUNTS=$(python3 templates/scripts/rpi-distribution.py counts --json)
COUNT_VALUES=$(python3 -c 'import json,sys; c=json.loads(sys.argv[1]); print(c["workflow"], c["domain"], c["helper"], c["rule"])' "$MANIFEST_COUNTS")
read -r WORKFLOW_COUNT SKILL_COUNT HELPER_COUNT RULE_TEMPLATE_COUNT <<< "$COUNT_VALUES"

# Audit coverage counts domains, independently of staffing or model instances.
DOMAIN_TOTAL=$(grep -cE '^\*\*.* domain ' templates/skills/rpi-pre-launch/SKILL.md || true)
DOMAIN_CONDITIONAL=$(grep -cE '^\*\*.* domain .*-- conditional' templates/skills/rpi-pre-launch/SKILL.md || true)
DOMAIN_COUNT=$((DOMAIN_TOTAL - DOMAIN_CONDITIONAL))

# --- check_count <file> <pattern> <expected> <label> -----------------------
# Extracts the first number matched by <pattern> in <file> and compares it
# against <expected>, which the caller computed from the catalogs
# (ERROR_COUNT / RULE_COUNT / SKILL_COUNT). <label> only names the location
# in the failure message.
#
# A pattern that matches nothing is a FAILURE, not a skip: it means the prose
# was reworded past what this script looks for, and drift there would go
# undetected from then on.
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

check_count "GUIDE.md" '[0-9]+ operational rules' "$RULE_COUNT" "Rule count (philosophy section)"
check_count "GUIDE.md" '[0-9]+ documented errors' "$ERROR_COUNT" "Error count (Where to Go Deeper)"
check_count "GUIDE.md" 'Index of [0-9]+ rules' "$RULE_COUNT" "Rule count (Where to Go Deeper)"

check_count "$ERRORS_FILE" '^[0-9]+ documented error patterns' "$ERROR_COUNT" "Error count (catalog header)"


check_count "templates/skills/error-patterns/SKILL.md" 'all [0-9]+ errors' "$ERROR_COUNT" "Error count (error-patterns skill)"
check_count "templates/skills/error-patterns/references/error-catalog.md" 'All [0-9]+ documented error patterns' "$ERROR_COUNT" "Error count (error-patterns level-3 catalog)"

# Component inventories are checked by the manifest/native renderer; GUIDE links
# that source instead of duplicating resource totals in prose.
check_count "GUIDE.md" 'Covers [0-9]+ core audit domains' "$DOMAIN_COUNT" "Audit domain count (workflow table)"
check_count "GUIDE.md" 'covers [0-9]+ core audit domains' "$DOMAIN_COUNT" "Audit domain count (audit introduction)"
check_count "methodology/agent-design.md" '[0-9]+ core audit domains' "$DOMAIN_COUNT" "Audit domain count (team design)"
check_count "methodology/cost-monitoring.md" '[0-9]+ core audit domains' "$DOMAIN_COUNT" "Audit domain count (cost guidance)"

# --- No duplicate rule numbers ----------------------------------------------
DUPES=$(grep -oE '^[0-9]+\.' "$RULES_FILE" | tr -d '.' | sort -n | uniq -d || true)
if [[ -n "$DUPES" ]]; then
  emit_block "Duplicate rule number(s) in $RULES_FILE: $DUPES" \
    "Two rules sharing one number makes cross-references (agent-errors.md, commands, CHANGELOG.md) ambiguous." \
    "  Renumber the newer rule to one past the current maximum, per .claude/rules/contributing.md's retirement/renumbering guidance."
  FAILED=1
fi

# --- Retired numbers agree between the index legend and the ledger -----------
# The legend answers "why is there a gap at 67?" inline, which is worth a
# reader's time; the ledger in contributing.md is the authority on WHY. Two
# statements of the same set is a drift risk, so they are cross-checked rather
# than one being deleted.
LEDGER=".claude/rules/contributing.md"
if [[ -f "$LEDGER" ]]; then
  # Legend line: "Retired so far: 67, 69, and 80 -- ..."
  LEGEND_RETIRED=$(
    grep -oE '^Retired so far:[^-]*' "$RULES_FILE" \
      | grep -oE '[0-9]+' | sort -n | tr '\n' ' '
  )
  # Ledger rows: "| 67   | vX.Y.Z | Merged | ... |"  (placeholder on purpose --
  # a real version here would look stale to verify-version.sh's sweep)
  LEDGER_RETIRED=$(
    awk '/^### Retirement Ledger/{f=1;next} f && /^## /{f=0} f && /^\| *[0-9]+ *\|/' "$LEDGER" \
      | awk -F'|' '{gsub(/ /,"",$2); print $2}' | sort -n | tr '\n' ' '
  )
  if [[ "$LEGEND_RETIRED" != "$LEDGER_RETIRED" ]]; then
    emit_block "Retired rule numbers disagree: $RULES_FILE legend says [${LEGEND_RETIRED% }], $LEDGER ledger says [${LEDGER_RETIRED% }]" \
      "A number retired in the ledger but still implied live by the index (or the reverse) makes a gap in the numbering unexplainable, which is exactly what the permanent-numbering convention exists to prevent." \
      "  Update the 'Retired so far:' line in $RULES_FILE to match the Retirement Ledger table in $LEDGER, or add the missing ledger row with its ground."
    FAILED=1
  fi
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
    # methodology/ paths are already repo-root-relative, as is anything else.
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

echo "PASS: $ERROR_COUNT errors, $RULE_COUNT rules, $WORKFLOW_COUNT workflows, $SKILL_COUNT domain skills, $HELPER_COUNT Codex helper, $RULE_TEMPLATE_COUNT rule templates,"
echo "      $DOMAIN_COUNT core audit domains (+ $DOMAIN_CONDITIONAL conditional),"
echo "      all hardcoded locations agree, all index destinations resolve."
exit 0
