# Compatibility Follow-ups

Recorded 2026-09-05 during the v2 bounded-workflow review. These are local
follow-up descriptions, not evidence of changes to sibling projects or support
for additional harnesses. Existing native evidence is version-bound to Claude
Code 2.1.261 and Codex 0.153.4; later clients require revalidation.

## Native Evidence Still Required

- **Claude cwd behavior (Errors #2/#24):** inspect the actual native Bash tool
  contract and reproduce consecutive calls in a disposable worktree, including
  explicit cwd changes and a failed directory change. Record client version,
  inputs and observed directories. Current Codex `exec_command` tool metadata
  states default turn cwd and per-call `workdir`; it is not evidence about Claude.
- **Tilde expansion (Error #8):** verify each relevant file API separately before
  narrowing its guidance. Shell expansion does not prove file-tool expansion.
- **Sibling cancellation / blocked boilerplate (Errors #1/#19):** preserve each
  result and bind any reproduction to client/model/tool versions. The historical
  observations do not prove universal cancellation or filename restrictions.
- **launchd (Errors #37/#38):** compare direct and exec-wrapper launches with
  identical arguments, cwd, environment and measured limits in an explicitly
  authorized disposable scheduler job. Capture version and sanitized logs.
  No scheduled inference or background service was started for this review.

These checks can support a future harness-fixed ledger entry. No error or rule
ID is retired now, and no model-capability safeguard is removed.

## Sibling Project Intake

- **Desktop project:** when separately authorized, inventory existing owner
  instructions, native discovery roots, capability settings and source receipts.
  Produce a reviewable migration/conflict plan preserving all project-specific
  release charters and unknown content. Do not infer setup authority from this
  blueprint implementation.
- **Copilot and OpenCode:** treat as separate compatibility investigations.
  Verify native instruction/skill discovery, argument delivery, resource layout,
  permissions, hooks, model inheritance and artifact handoffs on named versions.
  Require executable positive/negative discovery and authorization fixtures
  before advertising an adapter; Claude/Codex success does not establish support.

## Optional Native Capabilities

Native goals, advisors, documentation helpers and Agent Teams may be useful for
an explicit task. Verify current client support and concrete side effects first.
Do not enable them, install schedulers, mutate global profiles or start services
as an implicit part of ordinary RPI. Preserve an existing owner opt-in and keep
model inheritance and native trust separate from package installation.
