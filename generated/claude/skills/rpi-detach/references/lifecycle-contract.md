# Ownership-Aware Lifecycle Execution

Resolve an actual local RPI source from the selected native package metadata or
recorded installation source receipt. Resolve the target project from the request
and verify it before mutations. If source metadata is unavailable, request its
actual local path; never substitute a personal checkout or edit a plugin cache.

Use the bundled distribution engine from that resolved source. Set `RPI_SOURCE`
and `PROJECT` to the verified absolute paths using structured tool arguments or
safe shell quoting; request text and paths are data, never shell code.

```bash
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" plan \
  --source "$RPI_SOURCE" --target "$PROJECT" --harness both --action install
# For reconciliation use --action update; for owned project removal use --action detach.
# Read the returned local plan, then apply its exact path:
python3 "$RPI_SOURCE/templates/scripts/rpi-distribution.py" apply --plan "$RPI_PLAN"
```

Choose the actual requested harness rather than `both` when only one is selected.
Read installed engine help for selection/route arguments and the returned plan
location; never invent unsupported flags. Diagnostics and plan generation precede
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

Apply atomically with durable journals/recovery bytes. Interrupted work is resumed
or rolled back using the recorded transaction, never restarted by deleting local
state. Update installed identity/baselines only after successful completion. A
same-revision update still detects installed damage. Detach preserves edited and
unknown components, user instructions/settings, curated artifacts and the separate
user-scope lifecycle installation.

A valid plan is reviewable evidence. Apply only within the user's actual scope;
preexisting authorization persists. Production, remote publication, destructive
user-data removal and remote settings changes retain their separate boundaries.
No working-branch publication, hosted debugging loop, Vercel Preview creation or
automatic fleet rollout is part of any lifecycle workflow.
