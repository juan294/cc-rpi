# Local PostgreSQL recipe resources

This contract applies to the project-owned `tests/recipes/check_postgres.py`
fixture. It does not change distributed templates or authorize cleanup of other
projects, inherited containers, reusable stacks, or unknown data. Read the
installed `.rpi/rules/resource-lifecycle.md` before allocating local resources.

Run the recipe with an already present PostgreSQL image:

```sh
python3 tests/recipes/check_postgres.py --image postgres:17
```

The supplied reference is inspected locally and the run uses its immutable image
ID with `--pull never`. An unavailable image is a failure; the command does not
pull it. Only a local Unix Docker endpoint is accepted. The resolved endpoint and
daemon identity are recorded and checked again before disposal. No provider or
remote database is involved.

The fixture is disposable. Each invocation generates a nonce, unique container
name, ownership labels, private CID file and receipt before allocation. The
container keeps `--rm --network none`, has no published ports, and runs as
`postgres`. It initializes `/tmp/rpi-pg`, uses the `/tmp` PostgreSQL socket and
keeps the existing 30-second readiness window. SQL assembly, grants and RLS
assertions remain the documented recipe. No shared or inherited database is
reset or adopted.

## Ownership and evidence

Receipts live under `$HOME/.local/state/cc-rpi/postgres-recipes/`. The directory
is private; receipts and task output logs are mode `0600`. A persistent sibling
`.lock` file protects each receipt with an exclusive, nonblocking OS lock. Do not
remove the lock file to recover a task. Lock release after process death does not
clear an unresolved command intent.

The versioned receipt records the task nonce, repository and source checkout,
source commit, owner PID and start identity, Docker endpoint and daemon, immutable
image ID, creation timestamps, exact container ID and anonymous mount identities.
The command records its launch intent before spawning each mutating or workload
CLI and records the child process group before proceeding. Task output is kept
separately from ownership data; protected-container environments and full inspect
responses are not printed or archived.

Image-declared volumes are checked against the actual container mounts. An
omitted image `Config.Volumes` field means no declared volumes. It does not permit
undeclared mounts. Only the recorded anonymous volumes are disposable; bind
mounts, unexpected or replaced mounts, and volumes with other consumers block
disposal. Stopped containers count as consumers. Native container inventories use
full IDs, never the CLI's abbreviated defaults.

## Completion and recovery

Success requires both successful SQL and verified disposal. The final JSON line
reports separate `workload` and `cleanup` results, the receipt path, recorded
resources and the exact next finish command when retained. SQL or startup failure
keeps its original nonzero exit status even if cleanup also fails. A cleanup-only
failure makes the invocation fail. `--rm` removes the owned container and its
anonymous data; the script verifies both are absent and does not independently
remove a leftover volume.

The public projection includes the recorded `source_commit`. Its `invocation`
result reports interruption and receipt-publication errors separately from SQL:
a signal after successful SQL does not rewrite that SQL result. An observed SQL
failure keeps its original exit status even if later receipt publication fails.
When publication fails, the command still emits the in-memory result and a finish
handoff, but does not claim that this newer result was durably saved. It refuses
cleanup under lost lock ownership or unpublished command evidence. If resource
absence was already verified, that disposal result remains true; only evidence
publication and the invocation fail. A signal during final publication is checked
again and its invocation result is corrected without changing successful SQL.
Lock admission compares the held descriptor with the named inode before
publication and mutation.

SIGINT or SIGTERM is forwarded to the invocation's recorded CLI process group.
The supervisor waits for settlement before cleanup, with a 30-second settlement
bound. Unknown settlement, missing child identity, or an owner killed between
intent publication and completion leaves the receipt retained. Absence of the
old owner or root process group alone does not clear an orphan launch.

A failed allocator can still have created a container. Cleanup is permitted only
when the live supervisor observed the allocator settle and the CID plus fresh
container, nonce, image, creation and complete mount proofs reconcile. Missing or
corrupt CID evidence, incomplete mounts, unresolved daemon allocation, or an
orphan command remains retained. Empty immediate inventory is not proof that an
interrupted daemon request cannot publish a resource later.

Use the exact command printed in `next_action` to retry disposal. Its form is:

```text
python3 tests/recipes/check_postgres.py --finish /absolute/private/task-receipt.json
```

Finish validates the private receipt path, schema, source checkout, owner
liveness, lock, command settlement, actual daemon and resource identities before
acting. It never starts a container, runs readiness commands, or executes SQL.
Known absence is accepted only from successful fresh inventories; an inspection
failure is uncertainty. A same-name replacement is protected. Repeating finish
after verified disposal is safe. Live owners, unknown birth identities and orphan
intents remain protected and require review of the retained receipt and exact
resources; editing a receipt or deleting a lock is not a supported recovery path.

## Owner review of a retained orphan

`--finish` prints `retained: Unsettled or orphan command intent requires preservation` when the receipt still
records a command that never settled, for example after the recipe was killed with SIGKILL. The recorded child
process being gone does not clear that intent, because the daemon may still hold a resource that request created.
Only the owner of the task decides. Run these from the repository root; every command is read-only until step 5.

1. Read the receipt. Bind its path and fields (the receipt is in `$HOME/.local/state/cc-rpi/postgres-recipes/`):

   ```sh
   RECEIPT=$HOME/.local/state/cc-rpi/postgres-recipes/TASK.json   # the path --finish printed
   python3 -m json.tool "$RECEIPT"
   ENDPOINT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["docker"]["endpoint"])' "$RECEIPT")
   NONCE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["nonce"])' "$RECEIPT")
   NAME=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$RECEIPT")
   ```

2. Confirm the recorded owner and command child are gone (no output means gone; a live process means wait for it):

   ```sh
   python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r["owner"]["pid"], (r["command"] or {}).get("child"))' "$RECEIPT"
   ps -p OWNER_PID            # the first number printed above
   ps -p CHILD_PID            # only when a child pid was printed
   ```

3. Find what the daemon holds under this task's identity. The container name is `$NAME` and every resource carries
   the label `com.cc-rpi.postgres-recipe.nonce=$NONCE`; list by both and compare with the receipt's `container.id`
   (full IDs only, never abbreviations):

   ```sh
   docker --host "$ENDPOINT" container ls -a --no-trunc --filter "name=^/$NAME\$" --filter "label=com.cc-rpi.postgres-recipe.nonce=$NONCE"
   docker --host "$ENDPOINT" volume ls --filter "label=com.cc-rpi.postgres-recipe.nonce=$NONCE"
   ```

4. Confirm project identity before touching anything. The container must carry `nonce=$NONCE`, `repository=cc-rpi` and
   `workdir=` this checkout's absolute path, use the receipt's `image_id`, and expose only the receipt's anonymous
   volumes. Anything else is not this task's resource: stop here and leave it:

   ```sh
   CID=FULL_CONTAINER_ID   # from step 3
   docker --host "$ENDPOINT" container inspect "$CID" --format '{{json .Config.Labels}} {{.Image}} {{json .Mounts}}'
   git rev-parse --show-toplevel
   ```

5. Only when step 4 matches, stop and remove exactly that container by its full ID (the recipe starts it with `--rm`, so
   stopping it removes it and its anonymous volumes), then verify nothing remains:

   ```sh
   docker --host "$ENDPOINT" container stop "$CID"
   docker --host "$ENDPOINT" container ls -a --no-trunc --filter "name=^/$NAME\$"
   docker --host "$ENDPOINT" volume ls --filter "label=com.cc-rpi.postgres-recipe.nonce=$NONCE"
   ```

6. Record the disposition. The recipe has no command that clears an orphan intent, on purpose, and editing the receipt
   is not supported. Keep the receipt and write a retained-resource handoff in the task notes: receipt path, owner,
   the commands above with their output, and the result ("container <full id> stopped and verified absent on
   <date>; no volumes remain"). Then `--finish` on the same receipt still reports the retained intent; that is the
   expected final state for an orphan, and the handoff is the record that lets the source worktree be removed.

If step 3 shows nothing under the name and label, nothing was created that this task can find; the handoff still
records that, and a daemon request that was in flight when the recipe died may publish a resource later, so repeat
step 3 once more after a minute before removing the worktree.

Do not delete the source worktree until every owned receipt is disposed or has an
explicit retained-resource handoff naming its owner, reason and next review
action. No machine-wide prune or broad name-based cleanup is part of this recipe.

## Verification

`tests/test_postgres_recipe_lifecycle.py` runs the real recipe with a fake external
Docker boundary and real disposable fixture subprocesses. It covers unchanged
SQL, immutable image use, anonymous mounts, partial allocation, signals, orphan
launches, delayed daemon publication, replacements, daemon drift, consumers,
independent workload/cleanup failures and finish admission. Run it with:

```sh
python3 -m unittest discover -s tests -p test_postgres_recipe_lifecycle.py -v
```

The portable repository gate remains `bash scripts/verify-local.sh`. Native
Docker verification is a separate, serialized proof using a specifically
approved already present image and an entry/exit inventory of protected resources.
