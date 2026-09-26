# Native policy boundary

The shared pre-action hook is a small supplemental denylist, not an approval
system. Exit 2 with nonempty `BLOCKED / WHY / FIX` stderr blocks one of the few
positively identified destructive operations listed below. Every other command
exits 0 without a native allow decision, so the client's own permission rules,
permission mode and user decide it. Repository settings, verification reports
and explicit skill invocation never prove consent, and the hook never grants it.

## What is blocked

| Operation | Rule |
| --- | --- |
| Force-push (`--force`, `-f`, `--force-with-lease`, `+ref`) or deletion (`--delete`, `-d`, `:ref`) of a protected branch | `protected-branch` |
| The same with a target the parser cannot resolve (for example `"$BRANCH"`, a substitution or a glob such as `refs/heads/*`) | `protected-branch` |
| `gh api` with method DELETE on a repository or on a protected branch ref (`repos/O/R/git/refs/heads/main`) | `destructive-remote`, `protected-branch` |
| `git push --mirror`, `--prune`, or `--all`/`--branches` combined with force or deletion | `destructive-push` |
| Vercel Preview creation: bare `vercel`/`vc`, `vercel deploy`, or a path deploy (any first word that is not a Vercel subcommand) without `--prod`/`--target production`, including npx/pnpm/yarn wrappers and pinned `vercel@version` packages | `preview` |
| `gh repo delete` | `destructive-remote` |

Protected branches are `main`, `master` and `develop`, plus the project's
`integration_branch` and `production_branches` from `.rpi/policy.json` when they
are declared. Force-pushing or deleting a working branch is allowed, and so is
any `--dry-run`/`-n` push. A push that names no refspec is resolved from Git's
configuration: `remote.<name>.push`, and `push.default` `upstream`, `matching`
or the current branch.

Everything else passes through: ordinary `git push` of any branch or tag,
`gh pr create/merge/update-branch`, `gh workflow run`, `gh run rerun`, other `gh api` calls,
releases, issues, Vercel production deploys and other Vercel subcommands. Those
are outward-facing actions, so the project's native permission rules and the
user govern them. `git pull` is never blocked.

## Pass-through by design

Shell text is parsed and never executed. Chains, pipes, subshells, command and
process substitutions, `bash`/`sh`/`zsh -c` (including forms such as `-ec`,
`-e -c` and `-o pipefail -c`), `eval`, `env` (including `-S`)/`command`/`builtin`/
`sudo`/`doas`/`timeout`/`nice`/`nohup`/`stdbuf`/`caffeinate`/`xargs` wrappers,
redirections such as `2>&1`, `git -C`, `git -c`, literal `cd`/`pushd` and loop
bodies are inspected for the blocked forms above. After `cd "$DIR"` or `popd` the
repository is unknown, so only the default protected branches apply. Each command
segment is evaluated on its own: a segment the policy cannot evaluate prints
`POLICY UNAVAILABLE` and never hides a later destructive segment.
Literal `echo`, `printf`, `cat`, `grep` and `rg` arguments and quoted `cat`/`tee`
here-document bodies are text.

Anything the parser cannot read, including unterminated quotes, unknown wrappers,
package scripts, Git aliases and deeply nested shells, passes to native
permissions. A missing working directory or missing Git passes silently. The
wrapper prefers `python3.14` through `python3.11` over an older default `python3`
(macOS ships 3.9). With no supported runtime, or a missing policy script, it
prints `RPI POLICY SKIPPED`. The opt-in receipt gate is a separate Git hook and
does not depend on this wrapper. An
unexpected evaluation error prints `POLICY UNAVAILABLE`; both exit 0. This hook
is not a complete shell security boundary. A defect in it must not block ordinary
work. Only a malformed native event or an unknown adapter argument, which
indicate a broken installation, fail closed for every command. An invalid
`.rpi/policy.json` blocks only the commands that read it: force-pushes and
deleting pushes, and `gh api` DELETE of a branch ref.

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
hooks=$(git config --type=path --get core.hooksPath || echo "$(git rev-parse --path-format=absolute --git-common-dir)/hooks")
mkdir -p "$hooks" && cat > "$hooks/pre-push" <<'EOF'
#!/bin/sh
top=$(git rev-parse --show-toplevel 2>/dev/null)
gate="$top/.rpi/scripts/rpi-prepush.py"
case $0 in /*) hook=$0 ;; *) hook=$PWD/$0 ;; esac
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
chmod +x "$hooks/pre-push"
```

Where the wrapper lands depends on `core.hooksPath`:

- Unset: the clone's common `hooks` directory
  (`git rev-parse --git-common-dir`), outside every working tree. All linked
  worktrees of that clone share this one wrapper; each fresh clone runs the
  command again.
- Absolute: that directory. Worktrees and clones that use the same setting
  share it.
- Relative, such as `.githooks`: Git resolves it inside each worktree, so the
  command writes an untracked `.githooks/pre-push`. Commit it with the
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
When a `pre-push` hook already exists (for example one managed by a hook
tool), add the wrapper's command to it instead of replacing it. `git push --no-verify` skips every
pre-push hook, so the gate is a guard against mistakes, not a security boundary.

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
`integration_branch` may be written `main` or `refs/heads/main`. Each gated
update of `refs/heads/<integration_branch>` or of a version tag (`vX.Y.Z` or
`X.Y.Z`, optionally with a suffix) requires a clean tree and a passing
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
branches, other tags and tag deletions pass. The receipt must cover every
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
authorization. `gh release create` and Vercel production deploys are not gated;
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
