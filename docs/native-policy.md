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
never writes into `.git`. Enable it once per clone, from the repository root.
`git rev-parse --git-path hooks` honors `core.hooksPath`, and linked worktrees
share the clone's hooks directory; the wrapper runs the pushing worktree's own
gate:

```bash
hooks=$(git rev-parse --git-path hooks) && mkdir -p "$hooks"
printf '#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@"\n' > "$hooks/pre-push"
chmod +x "$hooks/pre-push"
```

When a `pre-push` hook already exists (for example one managed by a hook
tool), add the wrapper's command to it instead of replacing it. `git push --no-verify` skips every
pre-push hook, so the gate is a guard against mistakes, not a security boundary.

With the key on, each pushed update of `refs/heads/<integration_branch>` or of a
version tag (`vX.Y.Z` or `X.Y.Z`, optionally with a suffix) requires a clean tree
and a passing `.rpi/local/verification.json` whose commit is the pushed commit;
an annotated tag is peeled to its commit. A bulk push such as `--all`, `--tags`
or a glob is checked line by line, so it passes only when every gated ref points
at the verified commit. Deleting the integration branch is refused. Working
branches, other tags and tag deletions pass. The receipt must cover every
declared `verification_checks` name/argv pair, the exact candidate identity and
the runtime identity. The runtime binds the resolved interpreter, so `python3`
and `python3.13` naming one binary match; when only the interpreter differs,
the refusal names both. The gate ignores the Git exec-path entry that Git
prepends to `PATH` for hooks. It validates local evidence, not user
authorization. `gh release create` and Vercel production deploys are not gated;
push the verified tag first.

Projects without the key, or without `.rpi/policy.json`, exit 0 at once. In an
opted-in project the gate requires a declared `integration_branch` and a valid
verification declaration, and any error, including an invalid
`.rpi/policy.json` or a missing `rpi-candidate.py`, refuses the push with
`BLOCKED / WHY / FIX`. See [migration setup](migrations/v2.md).

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
