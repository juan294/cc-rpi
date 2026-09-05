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
- Phase 1: implementation, independent plan-compliance review and simplify
  review completed; final local acceptance is being recorded.
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
