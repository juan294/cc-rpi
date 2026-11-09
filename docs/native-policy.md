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
| `gh api` with method DELETE on a repository or on a protected branch ref (`repos/O/R/git/refs/heads/main`), and method PATCH of a protected branch ref with `force=true` (`-F force=true`, `--field`, `--raw-field`) or with a body read from `--input` | `destructive-remote`, `protected-branch` |
| `gh api graphql` with a `deleteRepository` or `deleteRef` mutation, or an `updateRef` mutation with `force: true` or a variable (the query may come from `-f`, `-F`, `-F query=@FILE` or `--input FILE`). A query that is not known statically (a `query` field built from a variable or substitution, `@-`, `--input -`, a file whose path is dynamic) is blocked as well, because a `deleteRef` cannot be ruled out; a file that does not exist is left to gh | `destructive-remote`, `protected-branch` |
| Deleting or force-moving a version tag: `git push --delete`/`-d`/`:refs/tags/v1`/`+refs/tags/v1`/`-f origin v1.0`, `git push --force --tags`, `gh api -X DELETE .../git/refs/tags/v1`, `gh api -X PATCH .../git/refs/tags/v1 -F force=true`, `gh release delete v1 --cleanup-tag`. A version tag is a tag the receipt gate below calls one. A destination that spells a version (`v1.0`, `2.0`, `release-v1`) is a tag whatever its source is, because git matches the destination against the remote's refs first and a branch source can move a tag (`feat:v1.0`); only `refs/heads/NAME` and `heads/NAME` are branches for sure. Names that are not versions (`issue-42`, `fix-123`, `feature-2`, `release-1`) are branches | `protected-tag` |
| `git push --mirror`, `--prune`, `--all`/`--branches` combined with force or deletion, and a plain `git push` to a remote with `remote.<name>.mirror` set | `destructive-push` |
| A command that names git, gh or vercel (in any spelling the parser resolves) and cannot be evaluated: an unexpected error, a recursion, or the time budget | `policy-error`, `policy-budget` |
| Vercel Preview creation: bare `vercel`/`vc`, `vercel deploy`, or a path deploy (any first word that is not a Vercel subcommand) without `--prod`/`--target production`, including npx/pnpm/yarn wrappers and pinned `vercel@version` packages | `preview` |
| `gh repo delete` (`--help` and `-h` print help and pass), also through a `gh` alias | `destructive-remote` |

Blocking version-tag deletion and forced tag moves (the `protected-tag` rule) is an owner policy extension of the
v2.1.0 line: a published release tag is the one ref consumers pin. The receipt gate below keeps its behavior: it
validates what a push publishes and a deletion publishes nothing, so a tag deletion still passes the gate (and the
hook blocks it).

Protected branches are `main`, `master` and `develop`, plus the project's
`integration_branch` and `production_branches` from `.rpi/policy.json` when they
are declared, each written as a bare name or as `refs/heads/NAME` (both mean the
same branch), compared without case: on a case-insensitive remote `Main` is `main`, so `refs/heads/Main` is protected too.
Force-pushing or deleting a working branch is allowed. This hook
also lets any `--dry-run`/`-n` push through; the optional receipt gate below does
not (Git runs the pre-push hook for a dry run and does not tell it, so the gate
evaluates a dry-run push of the integration branch or a version tag like a real
one). A push that names no refspec is resolved from Git's
configuration, with the `git -c` settings of the same command line applied: the remote is `branch.<name>.pushRemote`,
then `remote.pushDefault`, then `branch.<name>.remote`, then `origin`; its `remote.<name>.push` refspecs apply, and a
remote with `remote.<name>.mirror` set mirrors every ref. Without refspecs `push.default` decides: `upstream` (or
`tracking`), `matching`, `nothing` (nothing is pushed) or the current branch. A detached HEAD pushes nothing unless a
refspec is configured. A refspec glob such as `refs/heads/feature/*:refs/heads/feature/*` is blocked only when it can
match a protected branch (`refs/heads/*` can, `refs/heads/feature/*` cannot); `git push --force --tags` pushes no
branch and is blocked only for the tag rule. A destination built from a variable is a wildcard in the same way:
`"$BRANCH"` can be anything and is blocked, `"feature-$N"` cannot be `main` and passes.

Everything else passes through: ordinary `git push` of any branch or tag,
`gh pr create/merge/update-branch`, `gh workflow run`, `gh run rerun`, other `gh api` calls,
releases, issues, Vercel production deploys and other Vercel subcommands. Those
are outward-facing actions, so the project's native permission rules and the
user govern them. `git pull` is never blocked.

## Pass-through by design

Shell text is parsed and never executed. Chains, pipes, subshells, command and
process substitutions, `bash`/`sh`/`zsh -c` (including forms such as `-ec`,
`-e -c`, `-c -e` and `-o pipefail -c`; options before and after `-c` are skipped
to the first non-option word, which is the script; `-o`, `-O`, `--rcfile` and
`--init-file` take a value and every other long option is a flag; `fish`, `csh` and `tcsh` too, and fish's
`--command`), `eval`, `su -c`, `runuser -c` and `runuser -u USER [--] CMD`, `flock FILE CMD` and `flock ... -c CMD`,
`trap 'CODE' SIGNAL`, `parallel CMD ::: ARGS` (its `{}` placeholders are unknown input), and the wrappers
`env`, `command`, `builtin`, `exec`, `sudo`, `doas`, `time`, `timeout`, `nice`, `nohup`, `stdbuf`, `caffeinate`, `xargs`,
`ionice`, `chrt`, `taskset`, `setsid`, `busybox`, `unbuffer`, `watch`, `arch` (also `-arch arm64`), `xcrun`, the
Homebrew g-prefixed `genv`, `gtimeout`, `gnice`, `gstdbuf`, `gnohup`, `gxargs` and `gtime`, and the zsh forms `noglob`,
`nocorrect`, `repeat N`, `coproc`, a leading `-` and `=git` with literal arguments, redirections such as `2>&1`, `git -C`, literal
`cd`/`pushd`/`popd` and loop bodies are inspected for the blocked forms above. A wrapper's options are read like the
tool reads them: each short option that takes a value (`sudo -u root`, `/usr/bin/time -o FILE`, `env -C DIR`) or long
option (`sudo --user root`, `nice --adjustment 5`, abbreviations included) consumes its value, a cluster such as `-nu`
ends in its value option, and the operands before the command (the `timeout` duration, the `chrt` priority, the
`taskset` mask unless `-c` or `--cpu-list` is given) are skipped. `env -S` and `env --split-string` (also attached,
`-S'...'`, or in a cluster such as `-iS` and `-vS`) are split with env's rules: blanks separate words, single and double
quotes group, `\_`, `\c` and the usual escapes work, `${NAME}` is a variable; a string env itself could not parse is
a block when it names git, gh or vercel. A directory change is kept only where the shell keeps it: not after a `cd`
that is a pipeline stage, runs in the background (`&`) or sits in a subshell `( ... )`, and `cd -` returns to the
previous directory. A command or process substitution runs where its word is: after the `cd` that precedes it, not at the start of the command line. `git -c` is applied
for these kinds of setting on the same command line: `alias.<name>` (a
plain alias expands to its command and the expansion is read again, so an alias
that begins with global options such as `-c`, `-C` or `-p` is handled, and chains of aliases are followed until
none matches, with a loop treated as not a push; a `!` alias is inspected as shell text and passes its `-c`
settings on to the git commands in it, as Git does to child processes, so chains of shell aliases are followed
too; the chain and the nesting are capped at 100, beyond which the command is unclassifiable and passes; an
alias named like a Git builtin such as `push` or `status` is ignored, as Git
ignores it, using `git --list-cmds=builtins` and a static list as fallback; an alias from the repository or user
configuration files is read the same way), `remote.<name>.push` (added to the configured push specs),
`remote.<name>.mirror`, `remote.pushDefault`, `branch.<name>.pushRemote`, `push.default`, `branch.<name>.remote` /
`branch.<name>.merge` (which replace the repository value) and `help.autocorrect` (when it is enabled, an unknown
command whose weighted edit distance to `push` is under Git's floor of 7 is read as a push, as Git would run it).
A value of a configuration variable that Git runs as a command (`core.sshCommand`, `core.pager`, `core.editor`,
`core.fsmonitor`, `core.askPass`, `diff.external`, `credential.helper` after `!`, `*.cmd`, `*.textconv`, `*.clean`,
`*.smudge` and similar) is inspected as shell text. Any other `-c` setting is ignored. Git's own options before the
command are skipped as Git reads them: `-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace`, `--super-prefix`,
`--config-env` and `--attr-source` take a value (the long ones also as `--name=value`) and every other option is a flag;
a test runs the installed Git against that table. Subcommands that run shell text are inspected as well: `git submodule
foreach`, `git rebase -x`/`--exec`, `git bisect run`, `git filter-branch --*-filter` and `--setup`, `git difftool -x`
and `--extcmd`, and `git for-each-repo --config=KEY ...` (as the git command it runs); `git send-pack` and
`git http-push` are pushes (without refs and with `--force` they push every matching branch). The same settings are read, with the same rules, from
environment variables assigned inline in the same command (`GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and
`GIT_CONFIG_VALUE_<n>`, `GIT_CONFIG_PARAMETERS`, also through `env`) and from `--config-env=NAME=VAR` when `VAR`
is assigned inline in that command. `gh api` DELETE is recognised as
`-X DELETE`, `-XDELETE`, `-X=DELETE`, `--method DELETE` and `--method=DELETE` in any case, and with `-X`
inside a cluster of `gh api`'s boolean `-i` flag (`-iX DELETE`, `-iXDELETE`). The endpoint may be a
relative or absolute path or an `https://HOST/` or `https://HOST/api/v3/` URL; a query string or
fragment is ignored and percent-encoding (`heads%2Fmain`), repeated slashes, `.` and `..` segments
and a trailing slash are normalised before the repository and branch-ref patterns are matched; a path
under `refs/heads` that still climbs out with `..` after normalisation is blocked as unclassifiable. After `cd "$DIR"` or `popd` the
repository is unknown, so only the default protected branches apply. A working directory that no longer exists leaves the
repository unknown in the same way. Literal `echo`, `printf`, `cat`, `grep` and `rg` arguments are text.

`gh` aliases are followed. `gh alias set NAME EXPANSION` (also `--shell`/`-s`, `--clobber`) is judged as the command
the expansion stands for, so defining an alias that deletes a repository is blocked, and `gh NAME ...` expands an
alias of the `aliases:` section of `config.yml` in `GH_CONFIG_DIR`, `$XDG_CONFIG_HOME/gh` or `~/.config/gh` (read without
a YAML parser; a `!` expansion is shell text). A `gh api` endpoint that is wholly a variable (`"$ENDPOINT"`) is
unclassifiable and passes; a branch or tag name inside a ref endpoint (`refs/heads/$BR`) is a wildcard, as for a push
target. Branch-protection and ruleset changes through `gh api` are not covered.

The tokenizer resolves the spellings the shell itself resolves before it looks for a command:

- Quote, escape and line-continuation splits of a command name (`g\it`, `gi"t"`, `ver\cel`) and `$'...'`
  words, which are decoded (`$'git'`, `$'\x69'`, octal and `\u` escapes), anywhere in the command line.
- Static brace lists such as `{main,x}`, `ma{in,}`, `{,+}main` and `{git,push}`, nested or repeated, are expanded
  when unquoted. A command that expands to more than 1024 words per word is blocked, because it cannot be inspected.
- A redirection glued to a word (`main>/dev/null`, `main>&2`, `main</dev/null`, `main>>log`) is not part of the word.
- A branch may be written `NAME`, `heads/NAME` or `refs/heads/NAME`, as Git resolves a short ref.
- `git push` options may be abbreviated to any prefix of a long option, as Git accepts (`--dele`, `--force-w`,
  `--mir`, `--al`). A prefix that is ambiguous is applied as every option it could mean, so `--forc` counts as a force.
  The option list is fixed in the script and a test compares it with the installed Git. `gh` options (cobra) are not
  abbreviated by their parser, and `gh` and `vercel` options are matched exactly as written.
- `$"..."` locale strings are double-quoted strings; `{x..y}` and `{x..y..step}` sequences of integers and single letters
  are expanded like lists (a numeric sequence over the cap is one unresolved word), so `ma{i..i}n` is `main` and
  `g{i..i}t` is `git`; `{main..main}` is not a sequence (bash keeps it literal) and stays a literal name. A command word is
  looked for in the brace expansions of each short word of the command text, so a brace-spelled command name is found
  in any command, and the long data words of a command (minified JSON) cost nothing.
- A redirection of the form `{fd}>file`, `{fd}<file` or `{fd}>&2` is a redirection, not a command word.
- `function NAME { ... }`, `NAME() { ... }` and `NAME() ( ... )` run their body like a command list when the rest of the
  command names the function again (a call, `export -f NAME`, `xargs ... NAME`, a use inside `$(...)`, a name spelled
  with quotes or `$'\x66'`); a definition that nothing uses is inert and passes, unless a command word is dynamic
  (`${X:-f}`, `$(echo f)`, `"$X"`) or a shell, `eval` or `xargs` is given dynamic text, because then any function may be called.

Here-documents are read where the shell reads them: a `<<` that is inside a comment, a quote or a string is not an
operator, and a body ends at its terminator line. A body is text, never parsed as commands, unless its consumer is
a shell (`bash`, `sh`, `zsh`, `dash`, `ksh`), `eval`, `source`, `.` or `xargs`, or its pipeline ends in one of
them (`cat <<'EOF' | bash`); then it is inspected like script text. Bodies fed to anything else (`cat`, `tee`,
`git commit -F -`, `gh pr create --body-file -`, an interpreter such as `ruby`) are text. The command substitutions in
the body of an unquoted here-document (`$(...)` and backticks) are always inspected, because the shell runs them.
A body that an interpreter or a script later executes is not seen (see the unclassifiable forms below).

One hook invocation is bounded. Git answers (branch lists, configuration, builtins) are cached for the invocation, so a
long command pays for each distinct lookup once. Alias chains and nesting are limited to 100 (a chain of exactly 100
expansions is still followed; the 101st makes the command unclassifiable), brace expansion to 1024 words, and the
whole evaluation to 10 seconds (`RPI_POLICY_BUDGET_SECONDS` changes it; a value that is not a number above 0 and at
most 20 is ignored with a `POLICY NOTE` line and the default applies: the Codex hook timeout is 30 seconds and the
budget, the report and the telemetry all fit inside it). The judging stops a quarter of a second to one second before the
budget so that the block report and its telemetry end inside it too. The bound is checked inside every loop whose
cost grows with the command, each `git` lookup has the remaining time as its timeout, and a hard timer (`SIGALRM`) ends
work the loops cannot check; the hook puts back the `SIGALRM` handler and timer it found and clears its caches. A command
that needs more than the time or brace budget is blocked, not passed, with a message that says to split it; a `git`
that does not answer in time is blocked with a message that says so and names `git rev-parse --show-toplevel` as the
check. A command that names git, gh or vercel and nests shells, `eval` or substitutions more than 100 levels deep is
blocked (`policy-error`, with a fix that says to write it without the nesting); without a policy word it costs nothing. Nesting is followed without recursion, so no command reaches the interpreter's limit.

Anything the parser cannot read, including unterminated quotes, unknown wrappers,
package scripts and a chain of more than 100 alias expansions pass to native permissions.
These forms are known to be unclassifiable and are not blocked, even when they
rewrite a protected branch: arguments supplied at run time, such as
`echo main | xargs git push -f origin`; scripts piped or fed to a shell, such as
`echo 'git push -f origin main' | bash` and `bash <<< '...'`; and commands run
through `ssh host '...'`, `script`, `at`, `nsenter`, `docker run` or `find . -exec git push -f origin main ';'` (a test pins each of them). Variables
exported by an earlier command (`export GIT_CONFIG_COUNT=1 ...` followed by a later
`git` call, or a `--config-env` variable set elsewhere) are not known to the parser, and neither is a configuration
written earlier in the same command (`git config alias.pf "push -f"; git pf`). A shell function or alias that is defined
elsewhere is never expanded. Missing Git passes silently. The
wrapper prefers `python3.14` through `python3.11` over an older default `python3`
(macOS ships 3.9). With no supported runtime, or a missing policy script, it
prints `RPI POLICY SKIPPED`. The opt-in receipt gate is a separate Git hook and
does not depend on this wrapper. An
unexpected evaluation error (a recursion, a defect) in a command that names git, gh or vercel in any spelling the
parser resolves blocks with `BLOCKED / WHY / FIX` (rule `policy-error`) and a fix that points to the installation
check; in a command that names none of them it prints `POLICY UNAVAILABLE` and passes. This hook
is not a complete shell security boundary. A malformed native event or an unknown adapter argument, which
indicate a broken installation, fail closed for every command. The hook reads its input as UTF-8 bytes and writes
escaped text, so a locale or `PYTHONIOENCODING` that cannot print non-ASCII text never turns a command into a
"malformed event". An invalid
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
