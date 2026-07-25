#!/usr/bin/env bash
# verify-version.sh -- keep every hand-maintained version string in agreement.
#
# CHANGELOG.md is the source of truth: its newest released `## [X.Y.Z]` header
# is the version this repo currently claims to be. Every other version string is
# hand-maintained, which is why they drift -- this repo has repeatedly shipped
# with the README badge and the plugin manifests one to two releases stale.
#
# /release hardened the PROMPT against that (a mandatory `git grep` before and
# after the bump). This script is the Tier 1 backstop: counts have had a
# mechanical CI gate since verify-counts.sh, and version strings now have one
# too, so a release done by hand or by an agent that skimmed the instructions
# still cannot ship stale.
#
# Three checks:
#   1. Declared locations match the CHANGELOG version exactly.
#   2. The PREVIOUS released version appears nowhere outside CHANGELOG history
#      -- this is what catches "bumped some files, missed one".
#   3. The Retirement Ledger does not pre-commit to more than one unreleased
#      version, and only does so while a release is actually pending.
#
# Usage: templates/scripts/verify-version.sh [--self-test]
# Exit:  0 = every version string agrees, 1 = drift (see BLOCKED/WHY/FIX)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
}
cd "$REPO_ROOT"

CHANGELOG="CHANGELOG.md"
LEDGER=".claude/rules/contributing.md"

# emit_block <what> <why> <fix> -- corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
#
# Deliberately duplicated in each script and hook rather than sourced from a
# shared lib: these files are copied into downstream projects individually, and
# .claude/ reaches them through symlinks, so `dirname "$BASH_SOURCE"` resolves
# to .claude/scripts/ where no lib/ exists. Self-contained is the repo's
# convention -- guard-bash.sh and verify-edit.sh carry their own copies too.
# Keep the verify scripts' copies byte-identical.
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n\n' "$1" "$2" "$3"
}

FAILED=0

# released_versions -- newest first, excluding [Unreleased].
released_versions() {
  grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' "$1" | tr -d '#[] '
}

# --- Source of truth ---------------------------------------------------------
VERSION="$(released_versions "$CHANGELOG" | head -1)"
PREV_VERSION="$(released_versions "$CHANGELOG" | sed -n '2p')"

if [[ -z "$VERSION" ]]; then
  emit_block "No released version header found in $CHANGELOG" \
    "The newest '## [X.Y.Z]' header is the version this repo claims to be; without it there is nothing to check the other files against." \
    "  Add a released section header to $CHANGELOG, e.g.:  ## [1.0.0] - YYYY-MM-DD"
  exit 1
fi

# --- Check 1: declared locations ---------------------------------------------
# check_version <file> <grep-pattern> <label> [expected-occurrences]
# Every occurrence must match; the README badge repeats the version three times
# on one line (label text, shields.io URL, releases/tag href) and partial bumps
# there are the single most common form of this bug.
check_version() {
  local file="$1" pattern="$2" label="$3" want_n="${4:-}"

  if [[ ! -f "$file" ]]; then
    emit_block "$label expected in $file, but the file does not exist" \
      "A version location was renamed or removed without updating verify-version.sh, so drift there would go undetected." \
      "  Restore $file, or update templates/scripts/verify-version.sh to match the new location."
    FAILED=1
    return
  fi

  local found_all bad n
  found_all="$(grep -oE "$pattern" "$file" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"

  if [[ -z "$found_all" ]]; then
    emit_block "$label not found in $file" \
      "The version reference was removed or reworded past what verify-version.sh matches, so it would silently stop being checked." \
      "  Restore a version string matching pattern: $pattern
  in $file, or update verify-version.sh's pattern for this location."
    FAILED=1
    return
  fi

  n="$(printf '%s\n' "$found_all" | wc -l | tr -d ' ')"
  if [[ -n "$want_n" && "$n" != "$want_n" ]]; then
    emit_block "$label in $file has $n version strings, expected $want_n" \
      "This location is known to repeat the version (a shields.io badge carries it in the label, the image URL, and the release link). A changed count means the shape changed and a partial bump could now hide here." \
      "  Check $file and update verify-version.sh's expected occurrence count if the change is intentional."
    FAILED=1
  fi

  bad="$(printf '%s\n' "$found_all" | grep -v "^${VERSION}$" || true)"
  if [[ -n "$bad" ]]; then
    emit_block "$label in $file says $(printf '%s' "$bad" | tr '\n' ' '), $CHANGELOG says $VERSION" \
      "A stale version string tells users and the plugin marketplace that they are on a release they are not on." \
      "  sed -i '' 's/$(printf '%s' "$bad" | head -1)/$VERSION/g' $file   # macOS
  sed -i 's/$(printf '%s' "$bad" | head -1)/$VERSION/g' $file      # Linux
  # then re-run this script -- the badge repeats the version more than once"
    FAILED=1
  fi
}

check_version "README.md" 'Version[-: ]+v?[0-9]+\.[0-9]+\.[0-9]+|releases/tag/v[0-9]+\.[0-9]+\.[0-9]+' "Version badge" 3
check_version ".claude-plugin/plugin.json" '"version": *"[0-9]+\.[0-9]+\.[0-9]+"' "Plugin manifest version" 1
check_version ".claude-plugin/marketplace.json" '"version": *"[0-9]+\.[0-9]+\.[0-9]+"' "Marketplace manifest version" 1

# --- Check 2: the previous version lingers nowhere ---------------------------
# This is the check that catches a partial bump. After releasing X, any file
# still naming X-1 outside CHANGELOG history was missed. Illustrative versions
# in command examples (v1.0.0, v1.2.3) never collide with a real prior release.
if [[ -n "$PREV_VERSION" ]]; then
  STALE="$(git grep -n -F "$PREV_VERSION" -- \
             ':!CHANGELOG.md' ':!docs/' ':!*.lock' 2>/dev/null || true)"
  if [[ -n "$STALE" ]]; then
    emit_block "Previous version $PREV_VERSION still appears outside $CHANGELOG:
$(printf '%s' "$STALE" | sed 's/^/  /')" \
      "After a bump to $VERSION, any surviving reference to $PREV_VERSION is a file the release missed -- exactly the drift that shipped the README badge and plugin manifests stale in past releases." \
      "  Update each line above to $VERSION, or -- if the reference is deliberately historical -- move it into $CHANGELOG where history belongs."
    FAILED=1
  fi
fi

# --- Check 3: the Retirement Ledger does not invent versions -----------------
# The ledger records which release each retirement shipped in, and it is written
# BEFORE that release exists. One pending version is legitimate; two means an
# earlier pending entry was never reconciled when its release actually shipped.
if [[ -f "$LEDGER" ]]; then
  RELEASED_LIST="$(released_versions "$CHANGELOG")"
  LEDGER_VERSIONS="$(
    awk '/^### Retirement Ledger/{f=1;next} f && /^## /{f=0} f && /^\| *[0-9]+ *\|/' "$LEDGER" \
      | awk -F'|' '{gsub(/[ v]/,"",$3); print $3}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -u || true
  )"

  PENDING=""
  while IFS= read -r lv; do
    [[ -n "$lv" ]] || continue
    printf '%s\n' "$RELEASED_LIST" | grep -qxF "$lv" || PENDING="$PENDING $lv"
  done <<< "$LEDGER_VERSIONS"
  PENDING="${PENDING# }"

  PENDING_N="$(printf '%s' "$PENDING" | wc -w | tr -d ' ')"

  if [[ "$PENDING_N" -gt 1 ]]; then
    emit_block "Retirement Ledger references more than one unreleased version: $PENDING" \
      "A ledger entry names the release its retirement shipped in. More than one unreleased version means an earlier entry was never reconciled when that release actually went out, so the ledger now misstates when a rule was retired." \
      "  Correct the stale 'Retired in' values in $LEDGER to the versions those retirements actually shipped in (see $CHANGELOG)."
    FAILED=1
  elif [[ "$PENDING_N" -eq 1 ]] && ! grep -q '^## \[Unreleased\]' "$CHANGELOG"; then
    emit_block "Retirement Ledger references unreleased version $PENDING, but $CHANGELOG has no [Unreleased] section" \
      "The ledger is pre-committing to a release that is not pending, so either the release shipped under a different number or the entry was never updated." \
      "  Set the 'Retired in' value in $LEDGER to the release it actually shipped in, or restore the [Unreleased] section in $CHANGELOG."
    FAILED=1
  fi
fi

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

if [[ -n "${PENDING:-}" ]]; then
  echo "PASS: version $VERSION agrees across README badge and both plugin manifests;"
  echo "      $PREV_VERSION appears nowhere outside CHANGELOG."
  echo "NOTE: Retirement Ledger pre-commits to unreleased $PENDING -- if the next"
  echo "      release ships under a different number, update $LEDGER to match."
else
  echo "PASS: version $VERSION agrees across README badge and both plugin manifests;"
  echo "      no stale prior version outside CHANGELOG; ledger versions all released."
fi
exit 0
