# Phase 3: safe installation and v1 migration

[Main plan](../2026-09-05-cc-rpi-v2.md). Depends on Phase 2. Not batch-eligible. Outcome: fresh projects and existing v1 installations can adopt v2 without losing local knowledge, resources, or recovery options.

## Lifecycle interface and state

Use Phase 2's recorded per-harness route. A plugin manager owns its immutable package, cache, update and native version selection; the cc-rpi engine records the expected package identity and checks compatibility but never edits or merges its cached files. Baselines/journals apply only to project-managed instructions, rules/settings/registrations, customized legacy files, and direct-install fallback content. This narrows the engine without pretending plugin updates migrate project intelligence or undo mixed-file v1 customizations. Project detach removes only owned registration entries within scope, not an unrelated global plugin install.

Extend the same `rpi-distribution.py` engine with `check`, `plan`, `apply`, `rollback`, and `detach`. `scripts/install.sh` remains the user-facing wrapper: retain read-only `--check`, add explicit harness/route/destination options, and delegate rather than maintaining a second inventory. Respect the proven plugin route; direct fallback installs lifecycle skills into documented user locations. Test with explicit fake user roots; do not repurpose HOME or edit the user's real installations during fixture tests.

Project bootstrap/adopt/update/detach workflows call this engine using a concrete local source, target and proposed operation plan. The engine does not launch models, fetch/pull source, run remote git, install dependencies, or enable schedules. Clone installations use an explicit user-local source receipt; the Claude plugin bundles the source/resources and resolves them from its own installed path. No personal absolute source path belongs in committed project outputs.

Use schema version 1 for `.rpi/manifest.json`. Entries record component ID, source revision, adapter identity, relative destination, ownership type, exact rendered-base hash and status. Retain base bytes under `.rpi/baselines/<sha256>` for managed non-secret files/blocks. Mixed configuration records only exact owned entries and fingerprints; never preserve complete settings files as committed baselines. Staging/backups/receipts live in ignored `.rpi/local/`.

User installs use `~/.config/cc-rpi/installations/user/{manifest.json,baselines/,local/}` with a user-local source receipt. The installation request binds destination-root IDs to `~/.claude/skills` and `~/.agents/skills`; the distribution manifest supplies relative paths under those IDs, never arbitrary absolute destinations. One state-root lock/journal coordinates both roots. Tests pass explicit temporary state/skill roots. Read legacy user locations for diagnosis, but do not populate or delete them automatically. Reject path escape separately within each bound root; do not weaken containment to “anything under HOME.”

Managed instruction blocks use stable markers such as `<!-- cc-rpi:begin policy -->` and matching end markers. Project facts, vendor/generated blocks, unmarked custom instructions and user hooks remain project-owned. Migration must not infer ownership merely from a heading or filename.

## Update algorithm

```text
inventory target using lstat; resolve declared local source
load proven old base, local bytes, new rendered bytes
for each owned component:
    local == base -> eligible for new content
    new == base   -> retain local customization
    local == new  -> no-op
    otherwise     -> present three-way conflict/reconciliation
unknown ownership or unavailable base -> preserve and report
stage complete operation set; validate all mandatory dependencies
acquire target lock; recheck preimage hashes
apply with journal and atomic replacements; write manifest last
```

Default application is all-or-nothing for the selected component/dependency set. An unresolved conflict blocks that set; it does not leave a half-upgraded install marked current. Successful repeat operations produce no timestamp-only diffs. Rollback checks current hashes before restoring so it cannot overwrite concurrent user edits.

For v1, `.claude/cc-rpi-sync.json` is only a provenance hint. Reconstruct the old rendered baseline from locally available immutable history plus known rendering parameters where possible. If that cannot prove ownership, retain the file and provide a concrete reconciliation diff. Recognize partial `.Codex`/`source-command-*` imports as migration candidates, not native configuration or automatically disposable files.

Migrate AGENTS/CLAUDE atomically: preserve project facts and custom/generated sections, introduce the shared contract, remove reverse loading, and add the import. Separate permissions, environment entries, MCP access, schedules, hook registration and trust from ordinary content updates. Those require their actual setup scope and native trust process; a content-update flag does not grant new capabilities.

## Detach and recovery

Detach removes only unchanged owned files/blocks/registrations. Preserve modified or unknown content and all plans, research, reports, runbooks, user skills and project hooks. Keep AGENTS when project knowledge remains; keep its CLAUDE import when still useful. Remove a symlink entry only, never its external target. Detaching one project cannot remove user-level lifecycle skills or unrelated schedules/plugins.

Reject traversal/absolute manifest destinations and writes through symlink parents escaping the selected root. Recheck paths and hashes immediately before mutation. Retain the recovery journal through successful verification; clean only task-owned temporary state. A second detach is a no-op. Diagnostic exits distinguish healthy/no-op, action-needed drift/conflicts, and invalid input/dependency errors, with actionable BLOCKED / WHY / FIX output.

## Required tests and acceptance

Write failing filesystem tests before implementing each transition. Cover clean v1; missing base; source-only/local-only/both changed; upstream rename/delete; missing dependency; unchanged upstream with local damage; interrupted apply; concurrent edits; escape/dangling symlinks; paths with Unicode and shell punctuation; mixed AGENTS detach; altered hook; malformed configuration; and repeated operations. Outside-root sentinel bytes and unknown content must remain unchanged.

Use synthetic Roots-incomplete, Archy-release-override, Coach-partial-policy, generated-Next and partial-Codex-import fixtures. Full directories must retain optional references and mandatory scripts/playbooks. Project-specific release semantics must survive. No actual adopter under ~/code is an apply target.

Automated acceptance: lifecycle matrix passes, generated artifact works outside the maintainer checkout, `--check` is byte-for-byte read-only, full local gate passes. Human acceptance: inspect a clean migration diff, a conflict report, and a mixed-ownership detach preview. Handoff manifests, fixture outcomes, recovery commands and unchanged custom-content proofs.

## Execution status

- [x] Transactional lifecycle and explicit root/config ownership.
- [x] Immutable v1 migration, conflicts, recovery and per-harness preservation.
- [x] Independent review and local full gate: 10 checks, 121 tests.
- [x] Final extracted-package Linux and native discovery acceptance.
- [x] Clean migration, conflict report and mixed detach preview inspected.

Completed locally in `9fe3da7`; native trust/enforcement and complete instruction
chain diagnostics remain the explicitly assigned Phase 4/6 acceptance work.
