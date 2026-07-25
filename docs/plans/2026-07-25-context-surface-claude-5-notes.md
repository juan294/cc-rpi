# Implementation Notes: Context Surface for the Claude 5 Generation

Plan: `docs/plans/2026-07-25-context-surface-claude-5.md` (untracked -- plans
stay local, only these notes are committed, so this is a name not a link)
Shipped: v1.27.0, 2026-07-25, tag `v1.27.0`, main `5618bec`.

> Recreated after the original was lost -- it was written inside the worktree,
> and `docs/plans/` is gitignored, so removing the worktree deleted it. See
> "Shipped defect" at the bottom; that is not just a mishap, it is a real flaw
> in the deviation-log feature this plan added.

## Deviations

### Phase 3 -- index is 6,923 bytes, not under 6,000

- **Plan said:** drop from 20,360 bytes to under 6,000.
- **Found:** 81 pointer lines plus the section map and legend land at 6,923.
  The lines alone are ~5,400 bytes; the rest is the legend decision D3 requires.
- **Chose:** keep 6,923.
- **Why:** the only routes under 6,000 were deleting the legend D3 mandates, or
  shortening rule titles, which costs the scannability that is the index's whole
  job. The load-bearing criterion -- zero rule bodies, one resolvable pointer per
  rule -- is met, at a 66 percent cut.

### Phase 3 -- scope and stack tags dropped from index lines

- **Chose:** tags travel with the rule body into its destination.
- **Why:** ~900 bytes on a file already over target, and the stack tag is already
  implied by the destination (`skills/python-rules` *is* the Python tag). A tag
  that repeats what the destination says is the duplication this phase removes.

### Phase 4 -- no skill was split on size

- **Plan said:** split the skills Phase 3 grew; expected `shell-tools`,
  `git-workflow`, `github-cli`, `deployment-safety`.
- **Found:** largest body is `shell-tools` at 221 lines against a 500 ceiling.
- **Chose:** left every skill flat, per the plan's own branch ("if body already
  under ceiling and cohesive -> leave flat") and its stated over-splitting risk.
- **Why:** splitting to demonstrate the pattern would have made the skills worse.
  The ceiling is now enforced by `verify-skills.sh` instead, so the next skill
  that does grow past it fails CI.

### Phase 4 -- error-patterns split for a different reason than size

- **Found:** its "full catalog" pointer aimed at `patterns/agent-errors.md` "in
  the cc-rpi blueprint repository" -- a file no downstream project has. The
  skill's level-3 detail was unreachable exactly where it was needed. The domain
  map was also stale, stopping at #62 of 64.
- **Chose:** added `references/error-catalog.md` with all 64 errors; fixed the map.
- **Why:** the genuine multi-file case, driven by a reachability defect rather
  than a line count.

### Phase 4 -- unplanned fix: every skill name violated the contract

- **Found:** all 11 template skills declared display-cased names with spaces
  (`"Git Workflow"`, `"Shell & Tools"`). The one working installed skill,
  `.claude/skills/drawio`, uses lowercase-hyphen matching its directory.
- **Chose:** normalized all 11 to their directory slug.
- **Why:** the name is the identifier the harness dispatches on -- not cosmetic.
  A pre-existing defect the phase's own criterion surfaced, so it was fixed.

### Phase 5 -- 15 linked files, not 12

- **Found:** the plan's count predated `verify-counts.sh`, `verify-skills.sh`,
  and `verify-version.sh`, each of which added a pair.
- **Chose:** linked all 15; the divergences grew to 5 with `rules/rpi-details.md`.

### Release -- shipped as ONE release, not two

- **Plan said:** D9, ship phases 1-3 as v1.27.0 and 4-6 as v1.28.0, because
  "relocation is disruptive for downstream `/update`; additions should not ride
  the same diff."
- **Chose:** shipped all six phases as v1.27.0.
- **Why:** the split was never actually available. Phase 4 fixed a contract
  violation in the same files Phase 3 rewrote, and Phase 5 symlinked files that
  Phase 6 then edited -- releasing 1-3 alone would have shipped a tree with
  invalid skill names and no drift guard. The stated concern (downstream
  surprise) was addressed instead by an explicit downstream-impact callout in
  the CHANGELOG and release notes.

## Verification not carried out

- **`/doctor`** is interactive and cannot run headlessly, so the criterion
  "`/doctor` reports no oversized skill or CLAUDE.md" was not executed.
  `verify-skills.sh` covers the skill half mechanically; CLAUDE.md is 5,873
  bytes against a ~40,000 warn threshold, so the remaining risk is nil.
- **Downstream `/update` against v1.27.0** cannot be checked before release.
  Still open -- see below.
- **The three "a fresh session surfaces X" criteria** (worktree rule, zsh
  regex, a `references/` file) require live sessions with no prior context and
  were not run.

## Verified after release

- A fresh `git clone` on macOS resolves all 9 symlinked commands, and both
  `check-tree-drift.sh` and `verify-version.sh` pass on the clean clone.
- `/triage` still cites rules #70, #71, and #84, and all three resolve in the
  index to `commands/triage.md`.

## Shipped defect (found while recreating this file)

Phase 6 added a deviation log at `docs/plans/<plan>-notes.md`, written by
`/implement` and read by `/validate`. In cc-rpi that path is **gitignored**,
while `/implement` mandates a worktree -- so the log is destroyed when the
worktree is removed, before `/validate` can ever read it. It works in a
downstream project that tracks `docs/plans/`, but cc-rpi's own self-application
is broken. Fix is one of: untrack `docs/plans/` here, write the log somewhere
tracked, or have `/implement` copy it out before worktree teardown.
