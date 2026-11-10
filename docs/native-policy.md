# Native policy boundary

The shared pre-action hook is a small, best-effort guardrail. It is not an approval system and it is not a security boundary. Exit 2 with `BLOCKED / WHY / FIX` on stderr blocks one of the few clearly destructive operations listed below. Every other command exits 0 without a native allow decision, so the client's own permission rules, permission mode and user decide it. Repository settings, verification reports and explicit skill invocation never prove consent, and the hook never grants it. The real boundaries are the client's native permissions and the forge's branch protection.

## What is blocked

| Operation | Rule |
| --- | --- |
| Force-push (`--force`, `-f`, `--force-with-lease`, `+ref`) or deletion (`--delete`, `-d`, `:ref`) of a protected branch, including a push without a refspec from a protected branch and a forced or deleting refspec glob that can match one (`refs/heads/*`) | `protected-branch` |
| The same with a destination known only at run time, such as `"$BRANCH"` (`"feature-$N"` cannot be `main` and passes; `"$(git branch --show-current)"` resolves to the current branch) | `protected-branch` |
| Deleting or force-moving a version tag: `git push --delete`/`-d`/`:refs/tags/v1`/`+refs/tags/v1`/`-f origin v1.0`, `git push --force --tags`, `gh api -X DELETE .../git/refs/tags/v1`, a forced `gh api -X PATCH` of a tag ref, `gh release delete v1 --cleanup-tag`. A version tag uses the receipt gate's pattern; a destination that spells a version (`v1.0`, `2.0`, `release-v1`) is a tag unless written `refs/heads/NAME` | `protected-tag` |
| `git push --mirror`, `--prune`, and `--all`/`--branches` with force or deletion | `destructive-push` |
| Vercel Preview creation: bare `vercel`/`vc`, `vercel deploy`, or a path deploy without `--prod`/`--target production`, including `npx`, `bunx`, `pnpm dlx/exec` and `yarn dlx/exec` and pinned `vercel@version` packages | `preview` |
| `gh repo delete` (`--help` passes), `gh api` DELETE of a repository or of a protected branch ref, a forced PATCH of a protected branch ref, and a `gh api graphql` call that names `deleteRepository` or `deleteRef` | `destructive-remote`, `protected-branch` |

Protected branches are `main`, `master` and `develop`, plus the project's `integration_branch` and `production_branches` from `.rpi/policy.json`, each written as a bare name or as `refs/heads/NAME`, compared without case. Force-pushing or deleting a working branch is allowed, and a `--dry-run`/`-n` push passes.

Everything else passes: ordinary `git push` of any branch or tag, `gh pr create/merge/update-branch`, `gh workflow run`, `gh run rerun`, other `gh api` calls, releases, issues, Vercel production deploys and other Vercel subcommands. Those outward-facing actions belong to the project's native permission rules and the user. `git pull` is never blocked.

## How commands are read

Shell text is read and never executed. The hook splits a command line at `;`, `&&`, `||`, `|`, `&`, parentheses and newlines, and also inspects `$(...)` and backtick substitutions, `bash`/`sh`/`zsh`/`dash`/`ksh`/`fish -c` scripts (with options before or after `-c`), `eval`, `su -c`, `runuser -c` and `env -S`. It skips variable assignments, shell keywords and the common wrappers `env`, `command`, `builtin`, `exec`, `sudo`, `doas`, `time`, `timeout`, `nice`, `nohup`, `stdbuf`, `caffeinate`, `watch`, `xargs` and `setsid`. It follows `cd`, `pushd` and `git -C` to find the repository, and it reads `git push`, `gh` and `vercel` arguments as written. Quotes and escapes are removed as the shell removes them. Comments, redirections and here-document bodies are dropped. Literal text (`echo`, `printf`, `grep`, a commit message) never triggers a block.

## Accepted limits

The hook is deliberately simple. These forms are not recognised, and that is accepted, not a defect to chase:

- Git and gh aliases, `git -c` and environment configuration (`alias.*`, `remote.*.push`, `push.default`, `remote.*.mirror`, `GIT_CONFIG_*`), and configured push destinations. A push without a refspec is judged against the current branch.
- Abbreviated `git push` options (`--forc`), brace expansion, and quote splits of a command name (`g\it`).
- Arguments supplied at run time (`echo main | xargs git push -f origin`), scripts piped or fed to a shell (`cat <<'EOF' | bash`), scripts in files, and commands run through `ssh`, `docker`, `find -exec` or similar launchers.
- Variables exported by an earlier command, shell functions and aliases defined elsewhere, and `..` tricks in `gh api` paths.

A new spelling that slips past the hook is at most an S3 finding and never blocks a release; see the [release playbook](../templates/e2e-pro-playbook-template.md).

## Failure behavior

The hook never blocks work because it failed. Shell text it cannot read (an unclosed quote, for example) passes. A malformed native event, an unknown adapter argument or an unexpected error passes with a `POLICY UNAVAILABLE` warning; an error in one command of a chain does not hide a later destructive command. A `.rpi/policy.json` that cannot be used prints a `POLICY NOTE` and only the default branches stay protected. Missing Git leaves the repository unknown, so the default branches stay protected and nothing else is looked up. The wrapper prefers `python3.14` through `python3.11` over an older default `python3` (macOS ships 3.9); with no supported runtime, a missing policy script or a bad registration it prints `RPI POLICY SKIPPED` and passes. The opt-in receipt gate is a separate Git hook and does not depend on this wrapper.

Each block is recorded in `.rpi/local/contract-events.jsonl` at the repository root when `.rpi/` exists.

## Native permissions

Claude registers `PreToolUse` for `Bash` and ships a short native rule set:
`permissions.ask` for `gh release create/edit/upload` and the Vercel forms, and
`permissions.deny` for bare `vercel`/`vc` and `git push --mirror`. It ships no
ask rule for `git push`, `gh pr create` or `gh workflow run`, so a project's own
allow rules and the active permission mode apply unchanged. Codex uses its own
`hooks.json` and execpolicy rules: prompts for `gh release`, `vercel` and `vc`,
and a forbidden `git push --mirror` prefix. Codex relies on the hook for bare
Vercel Preview forms. Codex's hook `ask` response is unsupported and is never used as an
approval mechanism.

Review native changes separately with `--allow-capabilities config:claude-policy`,
`--allow-capabilities config:codex-hooks` and, for Codex permission files,
`--allow-capabilities resource:codex-permissions`. The installation engine keeps
unknown hooks, settings and explicit Agent Teams opt-ins. A capability change or
retirement, such as removing the former `git push` ask rule, needs that setup
scope; explicitly selected detach may remove unchanged owned content.

Both adapters consume `hook_event_name`, `tool_name`, `tool_input.command` and
`cwd`. The registration finds the installed wrapper in the working directory or
its ancestors. When no wrapper is found, it passes through with a warning.

## Optional verification receipt gate

A project can opt in to exact-candidate publication evidence:

```json
{
  "schema_version": 1,
  "integration_branch": "main",
  "require_verification_receipt": true,
  "verification_command": ["python3", ".rpi/scripts/rpi-verify.py"],
  "verification_checks": [{"name": "tests", "argv": ["npm", "test"]}]
}
```

The gate is a Git `pre-push` hook, `.rpi/scripts/rpi-prepush.py`, not part of the
pre-action shell parser. A parser cannot reliably know which refs a push
publishes (`--all`, globs, `remote.<name>.push`, `push.default`, aliases,
`cd "$(...)"` and `git -C "$VAR"` all hide them); Git hands the pre-push hook the
exact local and remote refs and commits. The engine installs the script but
never writes into `.git`. Enable it once per clone, from the repository root of
the integration checkout. The wrapper selects its interpreter like the
pre-action adapter (`python3.14` through `python3.11`, then `python3`) and
refuses with `BLOCKED / WHY / FIX` when that interpreter is older than 3.11, so
macOS's stock `python3` 3.9 is never used:

```bash
hooks_common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
top=$(git rev-parse --show-toplevel 2>/dev/null)
if hooks=$(git config --type=path --get core.hooksPath 2>/dev/null); then hooks_set=1; else hooks="$hooks_common/hooks"; hooks_set=; fi
case $hooks in /*) ;; *) hooks="$top/$hooks" ;; esac
if [ -z "$hooks_common" ]; then
  echo "BLOCKED / WHY: the current directory is not inside a Git repository, so there is no hooks directory to write. / FIX: cd to the repository root of the integration checkout, then run this command again." >&2
  false
elif [ "$hooks_set" = 1 ] && [ -z "$(git config --type=path --get core.hooksPath)" ]; then
  echo "BLOCKED / WHY: core.hooksPath is set to an empty value, which Git reads as the working tree root: a hook written to the hooks directory would not run, and one written to the root would be an untracked file. / FIX: git config --unset core.hooksPath (to use the clone's hooks directory), or point it at a directory (git config core.hooksPath PATH), then run this command again." >&2
  false
elif [ -z "$top" ]; then
  echo "BLOCKED / WHY: this is a bare repository or the inside of a .git directory: it has no working tree, so there is no integration checkout whose receipt the gate could read, and a relative core.hooksPath has no root to resolve against. / FIX: cd to the repository root of the integration checkout, then run this command again." >&2
  false
elif [ -e "$hooks" ] && [ ! -d "$hooks" ]; then
  echo "BLOCKED / WHY: the hooks path $hooks (core.hooksPath, or the clone's hooks directory) exists and is not a directory. / FIX: point core.hooksPath at a directory (git config core.hooksPath PATH) or move that file away, then run this command again." >&2
  false
elif [ -L "$hooks/pre-push" ]; then
  if [ -f "$hooks/pre-push" ] && awk '/^[[:space:]]*#/ || /^[[:space:]]*(echo|printf|:)[[:space:]]/ { next } /^[[:space:]]*exit([[:space:]]|;|$)/ { stopped = 1 } /rpi-prepush\.py/ && stopped == 0 { found = 1 } END { exit found ? 0 : 1 }' "$hooks/pre-push"; then
    echo "$hooks/pre-push is a symbolic link to a hook that runs rpi-prepush.py; left unchanged. WARNING: if an earlier line can end the hook, or the hook drops the gate's exit status, the gate cannot refuse; check one refusal."
  else
    echo "BLOCKED / WHY: $hooks/pre-push is a symbolic link, and this command never writes through a link. / FIX: add this line to the hook the link points to, or replace the link with a regular file that contains it, before any command that reads standard input (replace python3.13 with any Python 3.11 or newer on PATH), then push again: python3.13 \"\$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py\" \"\$@\" || exit 1" >&2
    false
  fi
elif [ -e "$hooks/pre-push" ] && ! grep -q 'cc-rpi receipt gate wrapper' "$hooks/pre-push"; then
  if awk '/^[[:space:]]*#/ || /^[[:space:]]*(echo|printf|:)[[:space:]]/ { next } /^[[:space:]]*exit([[:space:]]|;|$)/ { stopped = 1 } /rpi-prepush\.py/ && stopped == 0 { found = 1 } END { exit found ? 0 : 1 }' "$hooks/pre-push"; then
    echo "$hooks/pre-push runs rpi-prepush.py; left unchanged. WARNING: if an earlier line can end the hook, or the hook drops the gate's exit status, the gate cannot refuse; check one refusal."
  else
    echo "BLOCKED / WHY: $hooks/pre-push already exists and does not run rpi-prepush.py (a comment, an echo or a line after an exit does not count), and this command never overwrites an existing hook. / FIX: add this line near the top of that hook, before any exit and before any command that reads standard input (replace python3.13 with any Python 3.11 or newer on PATH), then push again: python3.13 \"\$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py\" \"\$@\" || exit 1" >&2
    false
  fi
else
  find "$hooks" -maxdepth 1 -type f -name '.pre-push.[0-9]*' -exec sh -c 'for stale; do pid=${stale##*/.pre-push.}; case $pid in *[!0-9]*) continue ;; esac; kill -0 "$pid" 2>/dev/null && continue; command -v ps >/dev/null 2>&1 && ! ps -p "$pid" >/dev/null 2>&1 && rm -f "$stale"; done' sh {} + 2>/dev/null
  tmp="$hooks/.pre-push.$$"
  if mkdir -p "$hooks" 2>/dev/null && cat 2>/dev/null > "$tmp" <<'EOF'
#!/bin/sh
# cc-rpi receipt gate wrapper: written by the documented enable command; run it again to update.
top=$(git rev-parse --show-toplevel 2>/dev/null)
gate="$top/.rpi/scripts/rpi-prepush.py"
case $0 in /*) hook=$0 ;; *) hook=$PWD/$0 ;; esac
if [ -z "$top" ]; then
  echo "BLOCKED / WHY: this push runs in a repository without a working tree (a bare repository), so there is no .rpi/scripts/rpi-prepush.py receipt gate to run and no checkout to attest the pushed commit. / FIX: push from a working checkout of the integration branch; or, for this repository only, the owner pushes with git push --no-verify, or removes this hook: rm \"$hook\"" >&2
  exit 1
fi
if [ ! -f "$gate" ]; then
  echo "BLOCKED / WHY: this checkout has no .rpi/scripts/rpi-prepush.py receipt gate. / FIX: push from a checkout that contains it, such as the integration worktree; or restore it with a reviewed update (RPI_SOURCE is your cc-rpi checkout): bash \"\$RPI_SOURCE/scripts/install.sh\" --target \"$top\" --action update --output \"$top/.rpi/local/plans/restore.json\"; review it, then bash \"\$RPI_SOURCE/scripts/install.sh\" --apply \"$top/.rpi/local/plans/restore.json\"; or, if this project no longer opts in, remove this hook: rm \"$hook\"" >&2
  exit 1
fi
for python in python3.14 python3.13 python3.12 python3.11 python3; do
  command -v "$python" >/dev/null 2>&1 && break
  python=
done
if [ -z "$python" ] || ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  echo "BLOCKED / WHY: the receipt gate needs Python 3.11 or newer; the first of python3.14, python3.13, python3.12, python3.11 and python3 on PATH is ${python:-missing}. / FIX: install Python 3.11 or newer so python3.11 (or newer) is on PATH (brew install python@3.13, or sudo apt-get install python3.11), then push again." >&2
  exit 1
fi
exec "$python" "$gate" "$@"
EOF
  then
    chmod +x "$tmp" 2>/dev/null && mv -f "$tmp" "$hooks/pre-push" 2>/dev/null || { rm -f "$tmp"; echo "BLOCKED / WHY: cannot write the receipt gate wrapper into $hooks. / FIX: make that directory writable by this user (ls -ld \"$hooks\"), then run this command again; an existing hook there was not changed." >&2; false; }
  else
    rm -f "$tmp" 2>/dev/null
    echo "BLOCKED / WHY: cannot write the receipt gate wrapper into $hooks. / FIX: make that directory writable by this user (ls -ld \"$hooks\"), then run this command again; an existing hook there was not changed." >&2
    false
  fi
fi
```

Where the wrapper lands depends on `core.hooksPath`:

- Unset: the clone's common `hooks` directory
  (`git rev-parse --git-common-dir`), outside every working tree. All linked
  worktrees of that clone share this one wrapper; each fresh clone runs the
  command again.
- Absolute: that directory. Worktrees and clones that use the same setting
  share it.
- Relative, such as `.githooks`: Git resolves it inside each worktree, so the
  command writes an untracked `.githooks/pre-push` at the root of the worktree it runs in, from any subdirectory of it. Commit it with the
  integration branch (`git add .githooks/pre-push`) so every worktree checked
  out from that commit has the file. `core.hooksPath` itself is local
  configuration: a fresh clone has none and runs no hook until the enable
  command runs once in it (it resolves the same path and rewrites the same
  wrapper). A worktree checked out from an older commit without the wrapper
  runs no hook at all.

The wrapper runs the pushing worktree's own gate. When that checkout has no
`.rpi/scripts/rpi-prepush.py` (a worktree checked out before adoption, or after
`detach`), every push from it is refused with `BLOCKED / WHY / FIX`, and the
printed fix names the three ways out: push from a checkout that has the gate,
restore it with a reviewed update, or, when the project no longer opts in,
remove the hook file at its printed absolute path.
The enable command never overwrites a `pre-push` hook it did not write. When one
already exists (for example one managed by a hook tool) and does not run
`rpi-prepush.py`, the command leaves it untouched, prints `BLOCKED / WHY / FIX`
with the exact line to add near the top of that hook (before any `exit`), and exits nonzero. A hook counts as running
the gate when a line that is not a comment, an `echo`, a `printf` or a `:` names `rpi-prepush.py` before any line that
starts with `exit`; a comment, a printed name or a line after an `exit` does not count. Such a hook, or a symbolic link
to one, is left alone and the command prints a `WARNING`: the check is textual, so a hook that ends earlier by other
means (`[ -z "$X" ] && exit 0`) or drops the gate's exit status still lets a push through; check one refusal. A file that this command wrote earlier (it carries a
`cc-rpi receipt gate wrapper` comment) is rewritten in place, so running the
command again is safe. Any other symbolic link is refused, so the command never
writes through a link. A file with that comment counts as the
generated wrapper and is rewritten in place, so edits to it are not kept; to add
your own checks, use a hook file without the comment that calls `rpi-prepush.py`
(the line the refusal prints). The wrapper is written to a temporary file in the hooks directory and renamed over
`pre-push`, so a stale read-only wrapper is replaced too. Every failure to write ends the command with a nonzero
status and a `BLOCKED / WHY / FIX` line: outside a Git repository, in a bare repository or inside a `.git` directory
(there is no integration checkout to gate), when the hooks path exists and is not a directory,
and when the hooks directory cannot be written (an existing hook is then left unchanged). A run killed between creating
`.pre-push.PID` and renaming it leaves that file behind; the next run removes every `.pre-push.<digits>` whose process is gone (a file such as `.pre-push.1.bak` is not ours and stays, and a process that exists but belongs to another user counts as alive). A `core.hooksPath` set to an empty value is refused: Git reads it as the working tree root, so neither the hooks directory nor the root is a place for the wrapper.
The wrapper itself refuses every push from a bare repository with `BLOCKED / WHY / FIX` (the fix names pushing from a
working checkout, `git push --no-verify` and the `rm` of the hook at its absolute path); the gate script, called
directly from a bare repository, refuses a gated update (the integration branch, a version tag) the same way and passes
the rest, because no receipt can exist without a checkout.
`git push --no-verify` skips every
pre-push hook, so the gate is a guard against mistakes, not a security boundary.

The receipt covers the files on disk, so the gate also refuses a push when a tracked file marked `skip-worktree` or
`assume-unchanged` differs from the pushed commit (`git status` cannot show such a change; a flagged file that is absent,
as in a sparse checkout, or equal to the commit is fine). The refusal lists the paths and prints
`git update-index --no-skip-worktree -- PATHS && git update-index --no-assume-unchanged -- PATHS`. The integration
branch name is compared without case, so a push of `refs/heads/Main` is gated like `main`.

A branch update is gated when the pushing checkout's `.rpi/policy.json`, the
policy committed in the pushed commit, or the policy committed in the remote
commit it replaces (when that object is local, for example after a fetch) opts
in; the stricter wins. A worktree on a pre-opt-in branch therefore cannot
publish an opted-in integration branch, and a commit that removes
`.rpi/policy.json` or sets `require_verification_receipt` to false cannot reach
an opted-in integration branch unverified. Turning the gate off takes one
verified push of the commit that sets the key to false (a policy file removed
outright leaves nothing to verify with, so remove it after that push), or the
owner's own `git push --no-verify`. A version tag is gated only by the policy
committed in the tagged commit and in the tag's replaced remote target, never by
the checkout's, so tags on commits from before opt-in (for example
`git push <new-mirror> --tags`) publish unchanged.
A version tag is a tag whose whole name matches
`(?:[A-Za-z][A-Za-z0-9]*+[-_])?(?:[vV]\d++(?:\.\d++)*+|\d++(?:\.\d++)++)(?:[-+_A-Za-z][-+._0-9A-Za-z]*+)?`: an optional word
prefix (`release-`), then either a `v` or `V` and numbers (`v1`, `v1.0`) or numbers with at least one dot (`2.0`,
`1.2.3.4`), and an optional suffix that starts with a letter, `-`, `+` or `_` (`-rc.1`, `rc1`, `_x`, `+build.5`). A bare
number or a word and a number (`1`, `issue-42`, `fix-123`, `feature-2`, `release-1`, `2026-11-09`) is a branch name, and
tags that start with a word and carry no number, such as `nightly`, `latest` or `release-candidate`, are not version tags
and pass ungated. A rolling tag such as `v1` publishes a commit as surely as `v1.2.3` does, so `v1` is a version. The pattern
uses possessive quantifiers and cannot backtrack; the pre-action hook uses the same pattern and a test keeps them equal.
`integration_branch` may be written `main` or `refs/heads/main`. Each gated
update of `refs/heads/<integration_branch>` or of a version tag requires a clean tree and a passing
`.rpi/local/verification.json` whose commit is the pushed commit; an annotated
tag is peeled to its commit. The clean-tree check ignores `.rpi/local/`, and the
runner creates `.rpi/local/.gitignore` (`*`) when it is absent, so receipts never
dirty a fresh clone or linked worktree. A mismatched tag is refused with a fix
that checks out the tag, verifies it and pushes it. A mismatched integration
branch update is refused with a fix that never repeats the refused command: it
publishes the verified HEAD (`git push <remote> HEAD:refs/heads/<branch>`) or
checks out the pushed commit, verifies it and pushes it. A bulk push such as `--all`, `--tags`
or a glob is checked line by line, so it passes only when every gated ref points
at the verified commit. Deleting the integration branch is refused. Working
branches, other tags and tag deletions pass the gate (the pre-action hook above blocks deleting or force-moving a version tag). The receipt must cover every
declared `verification_checks` name/argv pair, the exact candidate identity and
the runtime identity. The runtime binds the resolved interpreter, so `python3`
and `python3.13` naming one binary match; when only the interpreter differs,
the refusal names both and prints the exact command, with the hook's own
interpreter path, that produces an acceptable receipt:
`<hook interpreter> .rpi/scripts/rpi-verify.py`. A `verification_command`
whose program is `python`, `python3` or `python3.N` is printed with the hook's
interpreter in every fix for the same reason. A difference only in the
`python3` first on `PATH` (a shim, for example) names both paths; run the
printed command in the shell that runs `git push`. When `rpi-verify.py` itself
runs on Python older than 3.11, its fix names the first available 3.11+
interpreter in the wrapper's order, or `uv run --no-project --python 3.13`.
Other runtime differences name the changed keys, and a
locale, timezone or Python settings difference prints the gate's current
`LANG`, `LC_*`, `TZ` and `PYTHON*` values. The gate ignores the Git exec-path entry that Git
prepends to `PATH` for hooks. It validates local evidence, not user
authorization: `.rpi/local/verification.json` is an ordinary file in the working
tree, so a receipt edited by hand is accepted whenever its candidate identity and
runtime identity match the pushed commit and the environment. The gate guards
against mistakes and stale evidence; it does not prove that the checks ran, and
it is neither an approval nor a security boundary. `gh release create` and Vercel production deploys are not gated;
push the verified tag first.

Pushes where neither the checkout nor the pushed commit opts in (no key, or no
`.rpi/policy.json`) exit 0 at once. In an
opted-in project the gate requires a declared `integration_branch` and a valid
verification declaration, and any error, including a missing
`rpi-candidate.py`, refuses the push with `BLOCKED / WHY / FIX`. An invalid
`.rpi/policy.json` (unparseable, unknown keys, a non-boolean
`require_verification_receipt`) in the checkout or in any commit the gate reads
fails closed for every pushed ref, working branches included, by design: fix
the file as the printed fix says, commit it, and push again (when the invalid
commit is already the fetched remote tip, only the owner's `git push --no-verify`
can replace it); an installation fault prints the
`bash "$RPI_SOURCE/scripts/install.sh" --check` command, where `RPI_SOURCE` is
your verified cc-rpi checkout. See [migration setup](migrations/v2.md).

The gate's cost follows the number of distinct commits in a push, not the number of refs: Git lookups are
cached for the run, so a push of thousands of refs that name a few commits costs a few lookups.
When it refuses a dirty tree the message gives the number of changed paths, lists the first 20 and says `and N more`;
a name with a control character, a comma, a double quote or a backslash is shown JSON-quoted (`"a\tb"`), so a name
never adds a line or a separator, and `git status --short` lists every path.

The runner executes the declared inventory sequentially. Starting a new
verification attempt supersedes the prior success before checks execute.
Interrupted attempts remain unusable. Runtime identity includes a digest of
locale, timezone and Python execution settings.

## Evidence

Pre-action blocks are appended to `.rpi/local/contract-events.jsonl`
at the repository root as `{ts, session_id, hook, decision, rule, file}`, only
when that repository has an installed `.rpi/` directory. Pass-through commands are not
recorded. Optional telemetry failure does not change the decision. Direct native
event fixtures establish the adapter contract; they do not establish actual
client trust or invocation. See [compatibility evidence](compatibility.md).
Registration, trust and observed enforcement remain separate states for every
adopter.
