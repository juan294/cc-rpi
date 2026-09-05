# Version 2.0 implementation handoff

Plan: `2026-09-05-cc-rpi-v2.md`.

## Authorized scope

Implement all six phases without intermediate acceptance pauses, run update-docs,
and release v2.0.0. Working branches remain local. Release requires all local and
actual-harness acceptance evidence; remote publication uses only completed main
and the named tag/release, after trigger inspection. No fleet rollout is included.

## State

- Base: `18129ae36942166175faa9726f750f5b61bd7b9f`, canonical `main`.
- Local integration branch: `work/cc-rpi-v2` in a separate worktree.
- Phase 1 accepted in local commit `e9dad45`; full local gate passed.
- Phase 2 accepted in local commit `54b2fa8`: shared skills/adapters and native route gate passed.
- Phase 3 transactional lifecycle implementation in progress.
- Actual clients available: Claude Code 2.1.261; Codex CLI 0.153.4.
- Local verification prerequisites: Python 3.13.15, PyYAML 6.0.3,
  coverage.py 7.16.0, ShellCheck 0.11.0. Local Docker is available.
- Raw native schemas, catalog observations and verification receipts remain in
  ignored `.rpi/local/`. They are observations, not public compatibility claims.

## Decisions

- Use the existing approved continuation instruction at phase/docs gates.
- Preserve historical rule IDs and curated artifacts; no blanket retirement.
- Preserve current hosted Validate/Coverage triggers and Portfolio delivery until
  the final release trigger review; local checks never contact Portfolio.

## Deviations

- Plan said deterministic cleanup follows Phase 3; Phase 1's regression contract
  needs an executable safe cleanup recipe. Added a small repository helper now,
  using Git's non-forced removal after explicit branch/worktree identity, clean
  state (including ignored artifacts), and ancestor integration checks. This
  makes the Phase 1 sentinel tests meaningful without changing lifecycle scope.

## Phase 1 handoff

- Policy/recipes: local-only work and candidate-bound publication sequences;
  ownership-safe cleanup/detach prose; corrected gh, shell/Node/Python, WebMCP
  and database recipes; retained local Drawio source and quoting facts.
- Verification: shared 10-check local/CI entry point; 31 unit tests; nonempty
  candidate link/syntax inventories; every required exit captured; evidence
  constrained to owned local storage and bound to tested inputs.
- Independent review found and repaired linked-image, escaped-link, missing-input,
  source-symlink and evidence-output overwrite defects with regression tests.
- Database recipe: PostgreSQL 17.6, local Supabase image digest
  `sha256:b3bfedb107413abb3b8cb0d0874b0414a1dceb3d55bc0c778de6ad22d1f7dc86`;
  anon/nonowner/write/future-table denial and owner/service allow all passed.
- Rule/error IDs preserved. No retired rules this phase. Model/agent refinement,
  actual native invocation and lifecycle transactions remain their owner phases.
- Entry to Phase 2: use corrected canonical bodies, establish manifest/adapters
  and generated skill outputs, then prove the package routes before lifecycle work.

## Phase 2 handoff

- Canonical inventory: 20 workflows, 12 domain skills, one Codex-only helper,
  six rule sources. Remote budget is consolidated into push accountability.
- Deterministic renderer and native metadata validation; managed root policy is
  5,992 bytes. Direct self-application preserves the local Drawio extension.
- Shared bodies are byte-identical beneath declared adapter input preambles.
  Explicit workflow invocation controls were verified against native clients.
- Claude Code 2.1.261 discovered 32 packaged skills. Codex CLI 0.153.4 discovered
  33. Actual selector is `cc-rpi:rpi-research` in both clients. Research cases read
  installed bundled resources, preserved literal arguments, wrote only research
  artifacts, and stopped at the research boundary.
- Route decision: Claude plugin is suitable for the whole package; native
  `skillOverrides` does not exclude plugin skills, so conditional domain
  selection uses direct installation. Codex plugin supports per-skill native
  enable/disable. Both package update/revert resource checks passed. Plugin
  lifecycle source/runtime binding remains a required Phase 3 dependency.
- Native probes used disposable profiles/container and no personal marketplace
  changes. The first Codex inference encountered Docker seccomp blocking its
  sandbox; it was recorded failed, then rerun once after a no-inference preflight
  proved workspace access and outside-workspace denial. This is one extra failed
  infrastructure attempt beyond the 16 named acceptance cases.
- Renderer review repaired symlink escapes, resource aliases and undeclared
  nested resources. Full local gate passed all 10 checks and 53 unit tests.
- Legacy plan/status are removed only from this proven managed self-install;
  recovery bytes and receipt are local. Other managed aliases are rename notices,
  not claimed native forwarders. Unknown/custom aliases are migration candidates.
- Phase 5 must add executable triage scan-start/late-arrival/failed-retry coverage.

## Phase 3 work in progress

- Public interface: `plan --source --target --harness --route --action --output`,
  `apply --plan`, read-only `check`, and `rollback --journal`. User scope binds
  explicit state/Claude/Codex roots; fixture tests never repurpose HOME.
- Installer delegates literal argument arrays; six wrapper tests pass. Runtime
  bundling is an explicit manifest source closure, including ordinary copies of
  declared resource aliases so extracted Markdown/resource paths remain valid.
- Independent adopter and package tests were written failing before the core.
  The five named adopter fixtures are synthetic and preserve outside sentinels.
- Remote trigger preflight (read-only): Validate and Coverage on main, Portfolio
  webhook, and no cc-rpi link/name among 19 connected Vercel projects. No remote
  publication performed. Raw evidence is `.rpi/local/remote-trigger-review.json`.

## Phase 3 implementation handoff

- One offline lifecycle engine produces reviewable plans, verifies every preimage,
  and applies a locked, journaled transaction with the manifest written last.
  Recovery recognizes writes interrupted before checkpoints and resumes rollback
  without overwriting newer edits. Local private plans/journals are ignored.
- Immutable local v1 history proves only known v1 destinations and exact bytes;
  unchanged domain skills, resources, rules and aliases migrate with recovery.
  Missing provenance, modified copies and merely matching new paths are preserved.
- Native configuration owns individual scalar/array entries, never complete
  settings baselines. Adding, changing or retiring permission/hook boundaries
  requires setup scope; explicit detach can remove unchanged owned registrations.
  Existing explicit Agent Teams opt-ins and private/unknown settings survive.
- Per-harness installation records preserve independent routes and domains.
  Native plugin discovery stays explicitly unverified in an offline receipt.
- Codex packages contain a declared offline runtime/source closure with all
  resources. Extracted source identity cannot borrow an enclosing adopter's Git
  revision. Native caches remain manager-owned and are never reconciled by files.
- Independent reviews repaired ownership, rollback binding/resume, concurrent
  preimage, resource closure, typed JSON and duplicate-entry defects with tests.
  The 22 adopter cases and 13 configuration cases passed their focused reviews.
- Final local and frozen-package evidence will be recorded in
  `.rpi/local/phase-3-gates.log` and the native probe report before the phase commit.
- Phase 4 inherits the 40,026-byte project instruction fixture for complete chain
  diagnostics. Managed root content remains separately bounded at 8 KiB.
