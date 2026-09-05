# Ownership-Aware Lifecycle Execution

Resolve an actual local RPI source from the selected native package metadata or
recorded installation source receipt. The Codex package carries its runnable
source under `runtime/`; the Claude package and a source checkout use their
package/checkout root. Direct installations resolve the recorded user-local
source receipt. Verify `templates/distribution.json` and the engine beneath the
resolved source. Resolve the target project from the request and verify it before
mutations. If source metadata is unavailable, request its actual local path;
never substitute a personal checkout or edit a plugin cache.

For a plugin invocation, first obtain this skill's actual installed directory
from the native invocation metadata or the file being read, and bind it to
`RPI_SKILL_DIR` with safe quoting. Resolve relative to that verified directory,
never relative to the shell's current working directory. Use only the matching
package layout below.

Codex: the installed `skills/rpi-update/` directory resolves its source as:

```bash
RPI_SOURCE=$(cd -- "$RPI_SKILL_DIR/../../runtime" && pwd -P)
```

Claude: the installed `generated/claude/skills/rpi-update/` directory resolves
the package root as:

```bash
RPI_SOURCE=$(cd -- "$RPI_SKILL_DIR/../../../.." && pwd -P)
```

The same relative layouts apply to the other lifecycle skill directories.
Direct installations use the explicit user-local source receipt instead of
either cache layout. Verify the resolved files before invoking anything:

```bash
test -f "$RPI_SOURCE/templates/distribution.json" &&
  test -f "$RPI_SOURCE/templates/scripts/rpi-distribution.py"
```

Use the bundled distribution engine from that resolved source. Set `RPI_SOURCE`
and `PROJECT` to verified absolute paths, `RPI_ROUTE` to the selected native
route (`plugin` or `direct`), and `RPI_PLAN` to a task-owned ignored local plan
path under the target's `.rpi/local/plans/`. `--output` is required; choose a
concrete plan filename and preserve any existing file. Use structured tool arguments or safe shell quoting; request text and
paths are data, never shell code.

```bash
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" plan \
  --source "$RPI_SOURCE" --target "$PROJECT" --harness both \
  --route "$RPI_ROUTE" --action install --output "$RPI_PLAN"
# For reconciliation use --action update; for owned project removal use --action detach.
# Read the returned local plan, then apply its exact path:
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" apply --plan "$RPI_PLAN"
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" check \
  --source "$RPI_SOURCE" --target "$PROJECT" --harness both --route "$RPI_ROUTE"
```

Choose the actual requested harness rather than `both` when only one is selected.
Use the verified route decision: Claude whole-package plugin installation cannot
exclude individual domain skills, so use direct installation when conditional
domain selection is required. Codex native module controls may express a selected
domain set. Inspect actual native package identity and enabled modules; file
presence alone does not prove registration. Read installed engine help for
selection arguments; never invent unsupported flags. Diagnostics and plan generation precede
apply. An unavailable engine or missing resource is a blocker, not permission to
fall back to recursive copying, heading-based deletion or untracked overwrites.

The project manifest owns selected components and nonsecret content-addressed
baseline bytes. Shared user lifecycle state is separately owned under the user's
configuration directory. Native package managers own plugin caches; the engine
never three-way merges those caches or claims package update/rollback ownership.

Before apply, inspect source/target identity, component selection, all path/block/key
changes, precondition hashes, conflicts, recovery location and instruction budgets.
A filename or section title alone does not establish ownership. Preserve local
edits and unknown data. Confirm actual root/nested rule access and no duplicate
user/project or direct/plugin registrations.

For v1 migration, a sync metadata file is only a hint. Supply `--legacy-base`
only with a verified immutable commit available in the local source history and
known rendering parameters. Without that evidence, retain custom/unknown legacy
files and review the concrete reconciliation rather than asserting ownership.

Read the plan's status before applying: `ready` is a reviewable change, `noop`
needs no mutation, and `conflict` blocks the selected operation set. Exit 0 means
healthy/success/no-op, exit 2 reports action-needed drift or conflicts, and exit 1
reports invalid input or dependencies. Preserve the diagnostic and recovery path;
do not turn a nonzero result into an apparently successful setup.

Apply atomically with durable journals/recovery bytes. Interrupted work is resumed
or rolled back using the recorded transaction, never restarted by deleting local
state. Update installed identity/baselines only after successful completion. A
same-revision update still detects installed damage. Detach preserves edited and
unknown components, user instructions/settings, curated artifacts and the separate
user-scope lifecycle installation.

For recovery, read the recorded transaction's journal and bind its verified
path to `RPI_JOURNAL`. Rollback rechecks current hashes and must preserve
concurrent user edits:

```bash
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" rollback \
  --journal "$RPI_JOURNAL"
```

If rollback reports a conflict, retain the journal and affected files for
reconciliation; do not force restoration or delete recovery state.

A valid plan is reviewable evidence. Apply only within the user's actual scope;
preexisting authorization persists. Production, remote publication, destructive
user-data removal and remote settings changes retain their separate boundaries.
No working-branch publication, hosted debugging loop, Vercel Preview creation or
automatic fleet rollout is part of any lifecycle workflow.
