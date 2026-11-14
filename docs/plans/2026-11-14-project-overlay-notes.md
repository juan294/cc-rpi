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
