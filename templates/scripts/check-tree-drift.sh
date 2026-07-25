#!/usr/bin/env bash
# check-tree-drift.sh -- validate .claude/DIVERGENCE.md against the filesystem.
#
# templates/ is the product; .claude/ is this repo's self-application of it.
# Files that are identical are symlinks into templates/, so one edit updates
# both. Files that must differ stay real, and the manifest records why.
#
# The manifest is the load-bearing part. A symlink someone later replaced with
# a copy, or a divergence nobody recorded, is worse than the honest duplication
# this replaced -- both look fine until the two trees quietly disagree. This
# script is what makes either one loud.
#
# Usage: templates/scripts/check-tree-drift.sh
# Exit:  0 = manifest matches reality, 2 = drift (see BLOCKED/WHY/FIX)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
}
cd "$REPO_ROOT"

MANIFEST=".claude/DIVERGENCE.md"

# emit_block <what> <why> <fix> -- corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n\n' "$1" "$2" "$3"
}

FAILED=0

if [[ ! -f "$MANIFEST" ]]; then
  emit_block "$MANIFEST is missing" \
    "Without the manifest there is no record of which shared files are linked and which intentionally differ, so drift between templates/ and .claude/ cannot be detected at all." \
    "  git checkout $MANIFEST    # restore it, or recreate it from the two trees"
  exit 2
fi

# Parse the manifest. Rows are markdown table cells whose first column is a
# backticked path; the section heading decides which set the row belongs to.
parse_section() {
  awk -v want="$1" '
    /^## / { section = substr($0, 4) }
    section == want && /^\| `/ {
      line = $0
      sub(/^\| `/, "", line)
      sub(/`.*$/, "", line)
      print line
    }
  ' "$MANIFEST"
}

LINKED=$(parse_section "Linked")
DIVERGENT=$(parse_section "Divergent")

if [[ -z "$LINKED" && -z "$DIVERGENT" ]]; then
  emit_block "$MANIFEST lists no files in either the Linked or Divergent table" \
    "An empty manifest passes every check while describing nothing, which is the silent failure this script exists to prevent." \
    "  Populate the Linked and Divergent tables in $MANIFEST with one backticked path per row."
  exit 2
fi

# --- Linked entries must be symlinks resolving into templates/ ---------------
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  src=".claude/$path"
  tgt="templates/$path"

  # -e follows symlinks, so test -L first: a dangling link is a different
  # failure from an absent file and needs a different fix.
  if [[ ! -e "$src" && ! -L "$src" ]]; then
    emit_block "$src is listed as linked but does not exist" \
      "The manifest promises a self-application of this template that is not there, so the repo is not actually running the guidance it ships." \
      "  ln -s ../../templates/$path $src"
    FAILED=1
    continue
  fi

  if [[ ! -L "$src" ]]; then
    if cmp -s "$src" "$tgt"; then
      emit_block "$src is listed as linked but is a real file (a materialized copy)" \
        "Its content matches today, so nothing looks wrong -- but the next edit to either side forks the two trees silently. This is also what a Windows checkout without symlink support produces." \
        "  rm $src && ln -s ../../templates/$path $src"
    else
      emit_block "$src is listed as linked but is a real file whose content has ALREADY diverged from $tgt" \
        "The two trees have forked. Whichever copy you read, the other one says something different, and nothing recorded the split." \
        "  diff $tgt $src
  # then either reconcile and relink:
  #   rm $src && ln -s ../../templates/$path $src
  # or, if the difference is deliberate, move $path to the Divergent table in $MANIFEST with the reason."
    fi
    FAILED=1
    continue
  fi

  resolved="$(cd "$(dirname "$src")" && readlink "$(basename "$src")")"
  if [[ "$resolved" != "../../templates/$path" ]]; then
    emit_block "$src points at '$resolved', expected '../../templates/$path'" \
      "A symlink into an unexpected location means the self-application is running something other than the template it claims to mirror." \
      "  rm $src && ln -s ../../templates/$path $src"
    FAILED=1
    continue
  fi

  if [[ ! -e "$tgt" ]]; then
    emit_block "$src is a symlink to a target that does not exist: $tgt" \
      "A dangling symlink makes the command, hook, or script silently unavailable rather than failing loudly at the point of use." \
      "  Restore $tgt, or remove $src and drop its row from $MANIFEST."
    FAILED=1
  fi
done <<< "$LINKED"

# --- Divergent entries must be real files that still actually differ ---------
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  src=".claude/$path"
  tgt="templates/$path"

  if [[ ! -e "$src" || ! -e "$tgt" ]]; then
    emit_block "$path is listed as divergent but one side is missing" \
      "A divergence needs two files to be a divergence; the manifest is describing a pair that no longer exists." \
      "  Restore the missing side, or remove $path from the Divergent table in $MANIFEST."
    FAILED=1
    continue
  fi

  if [[ -L "$src" ]]; then
    emit_block "$src is listed as divergent but is a symlink" \
      "The recorded reason for the divergence says this file must differ from the template; a symlink means it no longer can." \
      "  Restore the real file with its repo-specific content, or move $path to the Linked table in $MANIFEST."
    FAILED=1
    continue
  fi

  if cmp -s "$src" "$tgt"; then
    emit_block "$src is listed as divergent but is now byte-identical to $tgt" \
      "The divergence is stale. Keeping two identical copies means the next edit to one silently fails to reach the other -- the exact drift the manifest exists to prevent." \
      "  rm $src && ln -s ../../templates/$path $src
  # and move $path from the Divergent table to the Linked table in $MANIFEST"
    FAILED=1
  fi
done <<< "$DIVERGENT"

# --- Every shared filename appears in the manifest exactly once ---------------
# A file present in both trees but in neither table is unrecorded drift.
LISTED="$(printf '%s\n%s\n' "$LINKED" "$DIVERGENT" | sed '/^$/d' | sort)"

DUPES="$(printf '%s\n' "$LISTED" | uniq -d)"
if [[ -n "$DUPES" ]]; then
  emit_block "Path(s) listed more than once in $MANIFEST: $(printf '%s' "$DUPES" | tr '\n' ' ')" \
    "A path in both tables makes the manifest self-contradictory, and the checks below will disagree about what the file should be." \
    "  Remove the duplicate row so each shared path appears in exactly one table."
  FAILED=1
fi

while IFS= read -r src; do
  path="${src#.claude/}"
  [[ -e "templates/$path" ]] || continue
  if ! printf '%s\n' "$LISTED" | grep -qxF "$path"; then
    emit_block "$path exists in both templates/ and .claude/ but is in neither table of $MANIFEST" \
      "An unrecorded shared file is drift waiting to happen: nothing says whether it is meant to track the template or deliberately differ." \
      "  Add \`$path\` to the Linked table (and symlink it) or to the Divergent table (with the reason) in $MANIFEST."
    FAILED=1
  fi
done < <(find .claude/commands .claude/hooks .claude/scripts .claude/rules .claude/skills \
           -type f -o -type l 2>/dev/null | sort)

if [[ "$FAILED" -ne 0 ]]; then
  exit 2
fi

LINK_N=$(printf '%s\n' "$LINKED" | sed '/^$/d' | wc -l | tr -d ' ')
DIV_N=$(printf '%s\n' "$DIVERGENT" | sed '/^$/d' | wc -l | tr -d ' ')
echo "PASS: $LINK_N linked files resolve into templates/, $DIV_N divergent files"
echo "      are real and still differ, no unrecorded shared files."
exit 0
