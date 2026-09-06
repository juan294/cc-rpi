# Version 2 compatibility evidence

This is a version-bound compatibility assessment, not a model benchmark or a
claim that existing adopter projects have been migrated. The release acceptance
record is in the [implementation handoff](plans/2026-09-05-cc-rpi-v2-notes.md).

## Evaluated surfaces

| Surface | Evaluated contract | Boundary |
|---|---|---|
| Claude Code 2.1.261 | Plugin metadata, fresh discovery, namespaced menu and Tab selection; primary workflows, direct adapter installation, extracted resources and native permission/hook controls | Use `/cc-rpi:rpi-plan` for the plugin or `/rpi-plan` for direct installation. Primary acceptance and economy limitations are separate. |
| Codex CLI 0.153.4 | Actual plugin installation, native `/skills` selection of `$cc-rpi:rpi-research`, root/nested instructions, eight workflow cases, trusted hook and accepted/declined approval | Use the actual native selector; direct directory fallback uses `$rpi-plan`. Hook trust is a separate native action. |
| Portable lifecycle | Nine extracted-package combinations: three adopter types across Claude, Codex and dual installation | Tests cover local ownership, collisions, update/no-op/conflict, resources and repeated detach; they do not migrate real adopters. |
| macOS arm64 | Python 3.11+ runtime and filesystem contract; native Claude checks | Final full-gate results are recorded with exact runtime and candidate identity in the handoff. |
| Local Ubuntu 24.04 amd64 | Offline CI-equivalent selection with Python 3.11 and 3.13 | The pinned local image supplies platform evidence; hosted CI is not a debugging loop. |
| Windows, Desktop clients, Copilot, OpenCode | No native support acceptance in this release | See [scoped follow-ups](compatibility-followups.md); ordinary generated files avoid relying on symlink installation, but do not prove Windows support. |

Parse, load, invoke and enforce are separate claims. Static validation deliberately
rejects malformed inputs. Native inventories establish discovery; successful
resource reads and produced artifacts establish invocation. A hook denial must
leave its execution marker absent, while its allowed control executes. Native
approval is tested separately from that hook. Registration alone proves neither.

## Models and instructions

Workflow defaults inherit the user's model and effort. Evaluated primary profiles
were Claude Fable 5.1 with high effort and Codex `gpt-6-astra` with high effort;
comparison profiles were Claude Haiku and Codex `gpt-5.6-sol` with medium effort.
Requested configuration and session-observed identity are recorded separately.
Haiku did not expose an effort selection in the evaluated native catalog.
Comparison cases establish compatibility, not quality rankings or cost savings.

The Haiku research trial failed to resolve its two required bundled references
and continued anyway; it is unsuccessful, not accepted unattended research
coverage. Its first implementation trial passed behavioral tests but exceeded
the one-reviewer fixture limit after invoking native `/simplify`. A bounded
repeat used native permissions to deny that helper and limit review delegation;
one reviewer and the requested local simplify lenses completed with passing
tests. These observations do not establish general autonomous economy-workflow
reliability. Keep explicit owner model choices and native resource controls;
instruction text alone does not enforce an agent budget.

Codex's default instruction byte limit truncated a synthetic 40,026-byte owner
file; a separately configured 65,536-byte limit included its final marker. The
file remained unchanged. The managed root block has its own smaller budget;
it does not grant a larger native instruction window. Claude imports and nested
rules follow its native loader, with diagnostic gaps reported as unknown.

Legacy `plan` and `status` registrations are not shipped into native-name
collisions. Retained explicit-only legacy commands display rename notices;
they do not forward a workflow or add model-facing workflow descriptions.
Unrecognized owner aliases and instruction content are preserved.

## Evidence limits and migration

Native cases use disposable projects and real client inference. Ambient native
and account-provided skills are recorded rather than assumed absent. Remote
permission controls use fake transport executables; no fixture publishes code.
Controller failures, guarded denials and bounded reruns remain in the local audit
record and are not counted as successful workflow attempts.

Lifecycle mutation and verification serialization require POSIX advisory locks
and no-follow file opens on the tested macOS/Linux runtimes. Process termination,
write failures and explicit recovery are tested; this release does not claim
physical power-loss or storage-hardware fault certification. Scheduler rehearsals
use actual plist files with a fake launchctl in a disposable container. They prove
CLI state/reporting behavior, not a new real-launchd deployment on the owner's Mac.

Read the [migration guide](migrations/v2.md) before updating an existing project.
Native managers own plugin caches and version selection. The reconciliation
engine owns only receipt-backed project or explicitly selected user content.
Conflict resolution, capability setup and rollback remain explicit operations.
See the [policy boundary](native-policy.md) for supported native execution modes.
