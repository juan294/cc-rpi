# Project overlay: implementation notes

Plan: 2026-11-14-project-overlay (local plan files under docs/plans/, not tracked). Base a628fd6. Owner approvals recorded 2026-11-14: the chapa and coach declared overrides, the four Phase 2 stock rules, and coach's solo-developer calibration under Procedure.

## Deviations

### Phase 1: block position

- Plan said: insert the block immediately after the first paragraph of the authored body.
- Found: in 10 of the 16 skills the first paragraph is the H1 title, and in all of them more lead text follows before the first `##`. A `##` block placed after the first paragraph takes that lead text (in `rpi-plan` and `rpi-validate`, the whole Process list) into the "Project overlay" section.
- Chose: insert the block immediately before the skill's original first `##` heading, so it is the first section and contains only its own text.
- Why: the block says "read it completely before you start", so its position does not decide when the overlay is read; Markdown sectioning does decide which text the block appears to own. The original review concern (a "one lead paragraph" parser that aborts on `rpi-plan` and `rpi-validate`) does not apply to this placement.

### Phase 1: statuses in the contract document

- Plan said: `docs/project-overlay.md` describes the statuses.
- Chose: the Phase 1 document describes format, authority and the hash; the four statuses are added with the diagnostics in Phase 2.
- Why: the Phase 1 commit must not document `rpi-status` output that does not exist yet.

### Phase 1: older installations stay healthy

- Plan said: entries without `authored_sha256` skip the staleness check until the next update.
- Found (independent review, reproduced by a failing test): adding the field made `check` report an unchanged older installation as action-needed (exit 2), because the only pending write was the manifest and the bookkeeping filter compared the new field.
- Chose: `status_bookkeeping_only` ignores `source.authored_sha256` as it already ignores `status`. Test: `test_manifest_without_authored_hash_stays_healthy_on_unchanged_source`.
- Why: recording the hash describes source bytes that already match; it must not create work for any installation, including user-scope lifecycle installs that this change does not otherwise touch.

## Review dispositions (Phase 1)

Independent review verdict: APPROVE, no blocking findings.

- Should-fix, older installation reports action-needed: fixed (see above).
- Should-fix, GUIDE and contract overclaimed "edits make updates conflict": fixed to "can conflict".
- Nit, no test pinned that the hash never appears as a top-level entry field: fixed in `test_skill_entries_record_one_authored_hash_for_both_harnesses`.
- Nit, README did not say the authority rule is an instruction contract: fixed.
- Nit, stale phase-1 pseudo-code and the untracked status deferral: fixed in the local plan files (phase-1.md, phase-2.md).

## Simplify dispositions (Phase 1)

Four independent cleanup reviews (reuse, simplification, efficiency, altitude). Applied:

- Reserved destinations are one list, `RESERVED_PROJECT_DIRECTORIES`, checked as the directory or anything below it.
- The authored hash is computed once per component and travels as partial `source` provenance merged when the entry is recorded; no extra in-memory field to strip.
- `status_bookkeeping_only` ignores the whole `source` provenance (the unchanged `base_hash` already pins the bytes), so a future provenance field needs no new special case.
- Tests reuse the renderer's `load_manifest`, `parse_skill` and in-process `render_tree`; the duplicate 500-line test is dropped because `parse_skill` rejects a longer body.
- The reservation cases are one loop in the existing reserved-state test; the adopter tests share `change_skill` and `strip_authored_hashes`.

Skipped, not material: caching the manifest parse in tests (under 1 ms per call). Mutation checks: removing the `.rpi/project` reservation, the provenance bookkeeping rule or the provenance merge each fails its test.

## Phase 1 acceptance

Candidate `25b105f` on branch `overlay-phase-1`. `bash scripts/verify-local.sh`: PASS, 10 of 10 checks, 766 tests, 90.25% line and 86.66% branch coverage, identity unchanged during the run (`.rpi/local/verification.json` in the worktree). Base `a628fd6` was verified first: PASS, 757 tests.

### Phase 2: version sweep was already stock

- Plan said: add a version-sweep rule to `rpi-update-docs`.
- Found: its version-scanner step already searches for previous version strings that may be stale (`templates/skills/rpi-update-docs/SKILL.md`, Step 1 item 4), and Step 2 runs the invariant scripts.
- Chose: no change. Three of the four approved rules were added.
- Why: the plan's precondition is "rule not already stated"; a duplicate adds text without behavior.

### Phase 2: workflow skill detection

- Plan said: an overlay is for a workflow skill when the manifest lists it as a project-scope `skill:rpi-*` component, with a packaged list for untracked installs.
- Chose: an overlay is valid when its skill has an installed copy under `.claude/skills/` or `.agents/skills/`; the manifest supplies only the authored hashes.
- Why: one rule covers tracked and untracked installations, and project installs never contain the user-scope lifecycle skills, so `rpi-update.md` is still `invalid`.

## Review dispositions (Phase 2)

Independent review verdict: APPROVE, no blocking findings.

- Should-fix, triage date rule compared a report with its own run date (circular): fixed to "today, or the run date its schedule expects".
- Should-fix, no test for unreadable or non-file overlays: added `test_project_overlay_unusable_files_are_invalid_and_never_raise`.
- Should-fix, plugin-route installs show every overlay as `invalid`: documented as a limitation in `docs/project-overlay.md` and the changelog, not handled. All 10 migration projects use the direct route in both harnesses (verified from their manifests on 2026-11-14); a fifth status would add surface for no current user.
- Nit, header-before-block ordering and the privacy check on the invalid path: added `test_project_overlay_header_is_checked_before_the_block`.
- Nit, unreadable `.rpi/project` raised: now one `invalid` item.
- Nit, CRLF skill copies read as `inert` and a BOM made the header invalid: section match is a line regex, and overlays are read as `utf-8-sig`; test added.
- Nit, `.DS_Store` and editor files reported: dotfiles are ignored.
- Nit, changelog and contract overclaimed the fix and header line: qualified with "when known".

## Simplify dispositions (Phase 2)

Applied: the authored-hash map keys on each entry's `component_id` and `adapter.harness` with the existing `records()` guard instead of parsing paths; name and file checks run before any skill copy is read; one `invalid()` helper; overrides are counted only after the header is valid; the CRLF test reuses `overlay_install(newline=...)`; a shorter changelog line.

Skipped: moving the existing `skills()` function onto the shared copy-directory constant (outside this diff); `cc_rpi_skill_names` for validity (needs `--source`, which a plain `rpi-status` run may not pass); merging the privacy checks (each covers a different path); using the module's `overlay_header` in tests (the header assertions would become tautological). Mutation checks: disabling the inert, stale, header-skill, override-section or dotfile rule each fails a test.
