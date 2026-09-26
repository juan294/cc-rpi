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
| The same with a target the parser cannot resolve (for example `"$BRANCH"` or a substitution) | `protected-branch` |
| `git push --mirror`, `--prune`, or `--all`/`--branches` combined with force or deletion | `destructive-push` |
| Vercel Preview creation: bare `vercel`/`vc`, `vercel deploy` or a path deploy without `--prod`/`--target production`, including npx/pnpm/yarn wrappers | `preview` |
| `gh repo delete` | `destructive-remote` |

Protected branches are `main`, `master` and `develop`, plus the project's
`integration_branch` and `production_branches` from `.rpi/policy.json` when they
are declared. Force-pushing or deleting a working branch is allowed.

Everything else passes through: ordinary `git push` of any branch or tag,
`gh pr create/merge/update-branch`, `gh workflow run`, `gh run rerun`, `gh api`,
releases, issues, Vercel production deploys and other Vercel subcommands. Those
are outward-facing actions, so the project's native permission rules and the
user govern them. `git pull` is never blocked.

## Pass-through by design

Shell text is parsed and never executed. Chains, pipes, subshells, command and
process substitutions, `bash -c`, `eval`, `env`/`command`/`sudo` wrappers,
`timeout`/`nice`/`nohup` wrappers, redirections such as `2>&1`, `git -C`,
`git -c` and loop bodies are inspected for the blocked forms above.
Literal `echo`, `printf`, `cat`, `grep` and `rg` arguments and quoted `cat`/`tee`
here-document bodies are text.

Anything the parser cannot read, including unterminated quotes, unknown wrappers,
package scripts, Git aliases and deeply nested shells, passes to native
permissions. A missing working directory or missing Git passes silently. A
missing Python runtime or policy script prints `RPI POLICY SKIPPED`, and an
unexpected evaluation error prints `POLICY UNAVAILABLE`; both exit 0. This hook
is not a complete shell security boundary. A defect in it must not block ordinary
work. Only a malformed native event or an unknown adapter argument, which
indicate a broken installation, fail closed for every command. An invalid
`.rpi/policy.json` blocks the commands that read it (see below).

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

With the gate on, a push of the integration branch, of an existing version tag or
of tags in bulk (`--tags`, `--follow-tags`),
`gh release create` for an existing version tag, and a Vercel production deploy
each require a clean tree and a passing `.rpi/local/verification.json` receipt.
That receipt must cover every declared `verification_checks` name/argv pair, the
exact candidate identity and the runtime identity. The pushed ref or tag must
also point at the verified commit. Working-branch pushes are never gated. The
gate validates local evidence, not user authorization. Without the key, or
without `.rpi/policy.json` at all, there is no receipt gate. A present but
invalid `.rpi/policy.json` blocks only `git push`, Vercel production and
`gh release create`, and the repair names the file. See
[migration setup](migrations/v2.md).

The runner executes the declared inventory sequentially. Starting a new
verification attempt supersedes the prior success before checks execute.
Interrupted attempts remain unusable. Runtime identity includes a digest of
locale, timezone and Python execution settings.

## Evidence

Blocks and gated publications are appended to `.rpi/local/contract-events.jsonl`
as `{ts, session_id, hook, decision, rule, file}`. Pass-through commands are not
recorded. Optional telemetry failure does not change the decision. Direct native
event fixtures establish the adapter contract; they do not establish actual
client trust or invocation. See [compatibility evidence](compatibility.md).
Registration, trust and observed enforcement remain separate states for every
adopter.
