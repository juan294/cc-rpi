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
- Phase 3 accepted in local commit `9fe3da7`: full 10-check gate and 121 tests passed.
- Phase 4 accepted in local commit `f8c4e22`: all ten gates and 297 tests passed;
  measured overall coverage was 88.79% lines and 84.37% branches.
- Phase 5 accepted in local commit `27144df`: all ten gates and 333 tests passed,
  with 88.54% measured line and 84.40% branch coverage.
- Phase 6 final acceptance is in progress; native cases use isolated snapshots.
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

## Historical Phase 3 progress

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

## Phase 3 accepted evidence

- Final isolated Linux extraction: five tests passed with the source checkout
  inaccessible and the extracted package read-only. Native discovery: exactly
  32 Claude skills and 33 Codex skills, no runtime skill leakage or aliases.
- Package inventory hashes: Codex
  `a7b85c7e2352897e986096fbc104813f6bb9257d16c7ad6a4037c379f72515ac`;
  Claude `a320c3c850f3c40c8e4e0f8d614fe69156a2638e4acc9fc88a9e9002fc365996`.
  Native checks used no inference. Task containers stopped.
- Inspected durable clean migration, three-way conflict diffs and mixed detach
  preview under `.rpi/local/phase3-review/`. Strict eight-maneuver project release
  requirements and modified skill content were preserved.

## Historical Phase 4 progress

- Model selection inherits the owner by default. Explicit economy profiles cover
  bounded mechanical work only, and explicit requests take precedence. Twenty
  model tests pass; native no-inference probes verified actual profile precedence.
- Read-only diagnostics distinguish configured, trusted and observed hooks;
  requested and observed model evidence; and managed root versus complete
  instruction-chain budgets. Twenty-five diagnostics tests pass, including
  preservation of the 40,026-byte fixture, private data and source directories.
- Coverage now measures executed Python lines and branches, including child
  processes. The authoritative suite runs once and its report is reused only for
  the same candidate and runtime. Loopback reporting tests use synthetic secrets.
- Independent review repaired stale runtime reuse, predictable temporary-file
  symlink overwrite, and multiple-subtest count inflation with regression tests.
  Shared runtime fingerprints record tool metadata without executing probes or
  dumping environment values. Installer preflight requires Python 3.11 or newer.
- Additional ownership tests reproduced malformed rollback progress accepting
  negative, oversized and boolean counters. Recovery now validates progress and
  status before locking or restoring; the initial 21 decision tests pass.
- Native policy integration and ownership/authorization branch coverage remain
  in progress. The first diagnostic run passed 191 of 192 tests; the unfinished
  Codex positive publication path failed. This is not accepted gate evidence.
- Codex hook `ask` is unsupported. Pinned native source confirms that applicable
  execpolicy prompt rules require approval or deny when prompting is disabled.
  Actual trusted hook invocation and accepted/declined approval remain Phase 6
  requirements; file registration and offline diagnostics cannot prove them.
- Phase 3 is accepted at `9fe3da7`; Phase 4 is uncommitted. No remote writes,
  extra inference cases, global profile changes or adopter fleet updates occurred.

## Phase 4 implementation handoff

- Canonical runtime now includes a portable verifier. Each adopter declares its
  own complete CI selection in `.rpi/policy.json`; this repo declares ten checks.
  Exact ordered check names/argv, candidate bytes and runtime must match. Custom
  partial selections cannot stand in for full CI. Native consent remains separate.
- The first complete local run passed ten checks and 273 tests. Subsequent
  independent cleanup corrected exact-one native registration checks, native
  bounded skill traversal, and Python runtime handling; focused tests passed.
  Final whole-gate acceptance runs against the regenerated candidate.
- Authorization decision tests cover every reachable branch. Measured policy
  lines/branches reached 99.19%/98.98%; configuration and package modules reached
  100%/100%. Recovery coverage and residual classification are preserved in
  `.rpi/local/lifecycle-decision-closure.json`.
- Self-application preserves unknown settings and explicit Agent Teams opt-in.
  Only exactly proven old blueprint git/gh blanket allows were removed; unknown
  legacy entries are reported for separate review. Native setup recovery remains
  local. No registration or receipt is labeled actual native enforcement.
- Native core versions remain Claude 2.1.261 and Codex 0.153.4. Python 3.11.2
  compilation also passed in the pinned local Linux container; complete 3.11/3.13
  cross-platform execution and actual harness acceptance remain Phase 6.

## Phase 5 implementation handoff

- Shared handoff and bounded dispatch contracts preserve phase scope, independent
  review, TDD, complete findings and resource limits. Audit coverage counts the
  eight core domains plus conditional AS, without requiring eight model instances.
- Triage records scan-start time, hashes and per-report dispositions. Partial
  scans and failed queries preserve the global marker; old retries and late
  arrivals remain eligible. Independent review found an unreadable-directory
  gap; a failing regression reproduced it and the traversal now records it.
- No additional rule/error IDs are retired. Historical harness claims were
  narrowed with evidence limitations and sibling-project follow-ups recorded.
- Managed root content is 6,573 bytes, below the 8 KiB product budget; that is
  separate from native complete instruction-chain limits.
- Reuse, quality and efficiency were reviewed independently. New helpers reuse
  the existing finding parser; full hashing and locked state revalidation remain
  necessary for backdated reports and concurrent checkpoints. No cost savings
  or actual native enforcement are inferred from these structural checks.
- Whole local gate and resulting commit are recorded at acceptance; native
  behavior and cross-platform final rehearsals remain Phase 6 work.
- The first Phase 5 full gate passed ten checks and 332 tests. Final independent
  review then reproduced loss of previously explicit nonstandard report names;
  scan inventory now includes existing registered paths, with a RED/GREEN
  regression. This invalidates that first gate; the final full rerun follows.


## Phase 6 acceptance and release preparation

The final acceptance scope includes nine actual extracted-package adopter/harness
cells, the complete ten-check local gate on macOS and pinned local Linux with
Python 3.11/3.13, version-bound native checks, independent review and two fresh
exploratory release charters. Full platform and charter acceptance remains pending
until its exact candidate-bound receipts exist. No main push/tag/release is
claimed by this preparation record.

Native primary workflow acceptance is observed for Claude 2.1.261 and Codex
0.153.4. Each client has actual menu/selector evidence, bundled resource reads,
TDD implementation, seeded mismatch detection, relevant/irrelevant trigger
observations and distinct native hook/permission outcomes. Codex's final policy
control also verifies clean pull execution and dirty pull denial using fake
transport. Claude's denied compound pull control includes a trailing execution
marker, whose absence is independently checked. No native fixture publishes code.

The eight Codex cases are independently reviewed. Claude primary implementation
passes five tests after three meaningful RED failures and one independent review;
the bounded Haiku implementation repeat passes four tests after three RED failures
with one reviewer. Source remains unchanged in research, plan and validation
cases. Native result messages are terminal success observations; the controller
then terminates its print process (exit 143), not a claimed CLI exit zero.

The original Haiku research case failed controlling-resource resolution and is
explicitly unsuccessful. Its first implementation invoked the native simplify
helper and exceeded the case's one-reviewer budget; a bounded repeat enforced
native permissions and completed the local lenses. Economy research is therefore
not accepted unattended workflow coverage. These optional comparison findings
do not invalidate observed primary Claude/Codex invocation or enforcement; no
performance or savings claim is made. See the evaluated compatibility limits.

All failed infrastructure attempts remain preserved: early Codex sandbox setup;
Phase 6 Codex command lookup and later fixture PATH mismatch; Claude reference
permission-controller omissions; one interrupted UI-controller stdin attempt;
and the original economy trials. Reruns and approval/sentinel-only continuations
are explicitly identified, not folded into the 16 named scenarios as successes.
The lookup defect received a failing regression and independent review before
repair. Native workflow bodies did not change during that policy-only correction.

Final documentation covers native routes, ownership/migration/rollback, inherited
models, optional scheduler scope, diagnostic limits and release topology. The
scheduler now requires ignored report paths before output, proven by regression
and independent review. All 57 audit IDs retain a disposition; no additional rule
or error IDs are retired. The release profile is docs/release-verification.md.

Raw native, matrix, review and release receipts remain ignored in .rpi/local.
The public plan and handoff preserve decisions and support boundaries. Final
publication must bind the exact integrated commit, pass Validate and Coverage
for its single main push, then read back the annotated tag and GitHub release.

### Exploratory findings and invalidated release evidence

Both fresh-context release charters ran against the same immutable extracted
candidate and reported failures. E1 found forced termination leaving a stale lock
and partial detach deleting shared runtime files. E2 found prior receipt reuse
during interrupted verification, missing locale binding, a configured Git alias
escape, misleading scheduler status and help requiring HOME. These are actionable
findings under repair with failing regressions and independent review; the
original reports are preserved. A defunct fixture child was an executor cleanup
limitation, separately resolved by removing its owned disposable container.

The earlier macOS Python 3.11 and 3.13 gates each passed ten checks and 352 tests,
but precede these discoveries and cannot establish release readiness. Linux gates
had not started. The repaired candidate needs new complete local platform gates
and affected fresh-context charter/native control verification. Unchanged native
workflow observations remain scoped to their exact resource hashes; no failed
charter is rewritten as a pass.
