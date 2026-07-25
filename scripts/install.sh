#!/usr/bin/env bash
# install.sh -- install cc-rpi's user-level commands into ~/.claude/commands/.
#
# /bootstrap, /adopt, /update and /detach live in your home directory so they
# work in every project, including ones not yet set up. Each ships with a
# `<path-to-your-cc-rpi-clone>` placeholder, because the blueprint cannot know
# where you cloned it. Substituting those by hand means 12 edits across 4 files
# with nothing checking the result -- and the installed copies then go stale
# silently on every cc-rpi release, which is how the command whose job is
# keeping projects current ends up being the thing that is out of date.
#
# This script does the copy, the substitution, and the verification, deriving
# the clone path from its own location. Run it after cloning, and again after
# every `git pull` of cc-rpi.
#
#   ./scripts/install.sh            install or refresh
#   ./scripts/install.sh --check    report drift, change nothing (exit 1 if stale)
#
# Exit: 0 = installed / up to date, 1 = problem (see BLOCKED/WHY/FIX)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_COMMANDS_DIR:-$HOME/.claude/commands}"
COMMANDS="bootstrap adopt update detach"
CHECK_ONLY=0

case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "") ;;
  -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
  *) echo "unknown argument: $1 (use --check or no argument)" >&2; exit 1 ;;
esac

# emit_block <what> <why> <fix> -- corrective-hint convention.
# See methodology/ci-and-guardrails.md "Block messages are corrective hints".
emit_block() {
  printf 'BLOCKED: %s\n\nWHY: %s\n\nFIX:\n%s\n\n' "$1" "$2" "$3"
}

# render <template> -- emit the template with the clone path substituted.
# Deliberately not `sed -i`: BSD sed (macOS) needs `-i ''` and GNU sed needs
# bare `-i`, so in-place editing is the one thing that breaks across platforms.
# We are writing a copy anyway, so stream it instead.
render() {
  sed -e "s|<path-to-your-cc-rpi-clone>|$REPO_ROOT|g" \
      -e "s|<cc-rpi-path>|$REPO_ROOT|g" "$1"
}

FAILED=0
INSTALLED=0
STALE=0

for c in $COMMANDS; do
  src="$REPO_ROOT/templates/commands/$c.md"
  dst="$DEST/$c.md"

  if [[ ! -f "$src" ]]; then
    emit_block "Blueprint command $src is missing" \
      "install.sh is being run from something that is not a complete cc-rpi clone, so the installed commands would be incomplete." \
      "  Re-clone cc-rpi and run ./scripts/install.sh from inside it."
    FAILED=1
    continue
  fi

  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    if [[ ! -f "$dst" ]]; then
      printf '  MISSING   /%s -- not installed\n' "$c"
      STALE=1
    elif ! render "$src" | diff -q - "$dst" >/dev/null 2>&1; then
      printf '  STALE     /%s -- differs from this clone\n' "$c"
      STALE=1
    else
      printf '  ok        /%s\n' "$c"
    fi
    continue
  fi

  mkdir -p "$DEST"
  # Keep one backup of a pre-existing copy, so a bad install is recoverable.
  [[ -f "$dst" ]] && cp "$dst" "$dst.bak"
  render "$src" > "$dst"

  # A surviving placeholder means the substitution missed a spelling. Fail
  # loudly rather than shipping a command that half-works.
  if grep -q 'path-to-your-cc-rpi-clone\|<cc-rpi-path>' "$dst"; then
    emit_block "Placeholder still present in $dst after substitution" \
      "A command containing an unsubstituted path will send Claude to a directory that does not exist, and the failure appears only when you run the command." \
      "  Report this as a cc-rpi bug -- install.sh's substitution patterns are out of sync with templates/commands/$c.md."
    FAILED=1
  else
    INSTALLED=$((INSTALLED + 1))
  fi
done

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  if [[ "$STALE" -ne 0 ]]; then
    emit_block "Installed user-level commands do not match this cc-rpi clone" \
      "They were installed from an older version. /update and friends would sync your projects using obsolete instructions -- silently, because nothing else checks this." \
      "  $REPO_ROOT/scripts/install.sh"
    exit 1
  fi
  echo "PASS: all user-level commands match this clone ($REPO_ROOT)."
  exit 0
fi

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "Installed $INSTALLED user-level commands into $DEST"
echo "  blueprint path: $REPO_ROOT"
echo
echo "Re-run this after every 'git pull' of cc-rpi, or check with:"
echo "  $REPO_ROOT/scripts/install.sh --check"
echo
echo "Note: the nightly sync agent (templates/scripts/cc-rpi-update-agent.sh) is"
echo "installed per-project, not here. Set its CC_RPI_PATH to $REPO_ROOT"
echo "if you use it -- see templates/setup-checklist.md."
exit 0
