#!/usr/bin/env bash
# verify-skills.sh -- enforce the Agent Skills authoring contract.
#
# Skills load in three levels: frontmatter always (so every skill's name and
# description costs context in every session), the SKILL.md body when the
# description matches, and sibling files only when the model reaches for them.
# That makes the frontmatter the expensive part and the body the part that has
# to stay skimmable. This script enforces both, plus the sibling-file wiring:
# a references/ file no SKILL.md names is a file the model will never open.
#
# Usage: templates/scripts/verify-skills.sh [skills-dir ...]
#        (defaults to templates/skills and .claude/skills)
# Exit:  0 = contract satisfied, 1 = at least one violation (BLOCKED/WHY/FIX)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
}
cd "$REPO_ROOT"

# Documented ceilings from the Agent Skills guidance.
MAX_BODY_LINES=500
MAX_DESC_CHARS=1024

# emit_block <what> <why> <fix> -- corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
#
# Deliberately duplicated in each script and hook rather than sourced from a
# shared lib: these files are copied into downstream projects individually, and
# .claude/ reaches them through symlinks, so `dirname "$BASH_SOURCE"` does not
# point anywhere a lib/ would live. Self-contained is the repo's convention --
# guard-bash.sh and verify-edit.sh carry their own copies for the same reason.
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n\n' "$1" "$2" "$3"
}

FAILED=0
CHECKED=0

if [[ $# -gt 0 ]]; then
  SKILL_DIRS=("$@")
else
  SKILL_DIRS=(templates/skills .claude/skills)
fi

# frontmatter_value <file> <key> -- read a key from the YAML frontmatter block,
# tolerating an optionally quoted value.
frontmatter_value() {
  awk -v key="$2" '
    NR == 1 && $0 != "---" { exit }
    NR > 1 && $0 == "---" { exit }
    NR > 1 {
      if (index($0, key ":") == 1) {
        sub("^" key ": *", "")
        gsub(/^"|"$/, "")
        print
        exit
      }
    }
  ' "$1"
}

while IFS= read -r skill; do
  CHECKED=$((CHECKED + 1))
  dir="$(dirname "$skill")"
  slug="$(basename "$dir")"

  name="$(frontmatter_value "$skill" name)"
  desc="$(frontmatter_value "$skill" description)"

  # --- name: present, lowercase-hyphen, matches its directory ---------------
  if [[ ! "$name" =~ ^[a-z0-9-]{1,64}$ ]]; then
    emit_block "Skill name '$name' in $skill is not a valid skill identifier" \
      "Skill names must be lowercase letters, digits, and hyphens, 1-64 characters. A display-cased name with spaces is not the identifier the harness matches on." \
      "  Set the frontmatter to:  name: $slug"
    FAILED=1
  elif [[ "$name" != "$slug" ]]; then
    emit_block "Skill name '$name' does not match its directory '$slug' ($skill)" \
      "The directory is how the skill is referenced from the rule index and from other docs; a divergent name makes those pointers unresolvable." \
      "  Either rename the directory to '$name', or set the frontmatter to:  name: $slug"
    FAILED=1
  fi

  # A skill named after the vendor collides with built-in skills.
  case "$name" in
    *claude*|*anthropic*)
      emit_block "Skill name '$name' contains a reserved vendor word ($skill)" \
        "Skill names containing 'claude' or 'anthropic' collide with built-in skills and are not reliably dispatched." \
        "  Rename the skill and its directory to something describing the domain, not the vendor."
      FAILED=1
      ;;
  esac

  # --- description: present and within the frontmatter budget ---------------
  if [[ -z "$desc" ]]; then
    emit_block "Skill $slug has no description ($skill)" \
      "The description is the ONLY part of a skill loaded in every session; without it the skill can never be triggered." \
      "  Add a description naming the triggers -- the symptoms and tools that should pull this skill in."
    FAILED=1
  elif [[ "${#desc}" -gt "$MAX_DESC_CHARS" ]]; then
    emit_block "Skill $slug description is ${#desc} chars, limit is $MAX_DESC_CHARS ($skill)" \
      "Descriptions over the cap are truncated, so the trailing triggers silently stop matching." \
      "  Trim the description to under $MAX_DESC_CHARS characters, keeping the trigger words at the front."
    FAILED=1
  fi

  # --- body: under the documented ceiling ------------------------------------
  body_lines=$(awk 'NR==1 && $0=="---" {infm=1; next} infm && $0=="---" {infm=0; next} !infm' "$skill" | wc -l | tr -d ' ')
  if [[ "$body_lines" -gt "$MAX_BODY_LINES" ]]; then
    emit_block "Skill $slug body is $body_lines lines, ceiling is $MAX_BODY_LINES ($skill)" \
      "An oversized SKILL.md is loaded whole on every match, which defeats progressive disclosure -- the long tail should be a sibling file read on demand." \
      "  Move the long-tail detail into $dir/references/<topic>.md and add a ## References section to $skill naming it and saying when to read it."
    FAILED=1
  fi

  # --- sibling files: each one named by its parent SKILL.md ------------------
  if [[ -d "$dir/references" ]]; then
    while IFS= read -r sibling; do
      base="$(basename "$sibling")"
      if ! grep -q "$base" "$skill"; then
        emit_block "Sibling file $sibling is not named by its parent SKILL.md" \
          "Level-3 files load only when the model is told they exist and when to read them. An unnamed sibling is dead weight the model never opens." \
          "  Add a ## References entry to $skill naming references/$base and the condition under which to read it."
        FAILED=1
      fi
    done < <(find "$dir/references" -maxdepth 1 -name '*.md')
  fi
done < <(find "${SKILL_DIRS[@]}" -maxdepth 2 -name SKILL.md 2>/dev/null | sort)

if [[ "$CHECKED" -eq 0 ]]; then
  emit_block "No SKILL.md files found under: ${SKILL_DIRS[*]}" \
    "verify-skills.sh silently passing on an empty set would hide a moved or deleted skills tree." \
    "  Check the skills directory path, or pass it explicitly: templates/scripts/verify-skills.sh <dir>"
  exit 1
fi

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "PASS: $CHECKED skills -- names valid and matching their directories,"
echo "      descriptions present and under $MAX_DESC_CHARS chars,"
echo "      bodies under $MAX_BODY_LINES lines, all sibling files referenced."
exit 0
