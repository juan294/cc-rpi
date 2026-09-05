---
description: Contributing rules for cc-rpi -- adding error patterns, workflow docs, and consistency sweeps
paths:
  - patterns/**
  - methodology/**
  - templates/**
  - .claude/**
  - CLAUDE.md
  - AGENTS.md
  - README.md
  - GUIDE.md
  - CONTRIBUTING.md
  - CHANGELOG.md
---

# Contributing to cc-rpi

## Adding Error Patterns

When new error patterns are discovered during work on ANY project:

1. Add to `patterns/agent-errors.md` following the existing format
2. Put the rule body in the surface that needs it (a skill, a `.claude/rules/`
   file, or a command), then add a one-line pointer to
   `patterns/quick-reference.md` in the form `N. title -> destination`.
   That file is an index; no rule bodies live there. CI checks the
   destination resolves.
3. Update any hard-coded counts or references in onboarding docs and
   skills (`README.md`, `GUIDE.md`, bootstrap docs, `error-patterns/`)
4. Update `CHANGELOG.md`
5. Keep entries generic -- no project-specific references

## Adding Best Practices

When new best practices or methodology refinements are confirmed:

1. Add to the appropriate file under `methodology/`
2. Or create a new file under `patterns/` if it's a distinct topic

## Retiring a Rule or Error

The corpus has an intake path -- "Adding Error Patterns" and "Adding Best
Practices" above -- but it has never had an exit path. Across 38 releases it
has only grown. This section is the exit path.

A rule or error is a retirement candidate only on one of five grounds:

1. **Superseded** -- another rule covers it completely; name the successor.
2. **Hook-enforced** -- the exact native boundary is registered, trusted and
   observed blocking the failure on the stated client version. Installation
   alone is not enforcement; keep the behavior as a hook annotation.
3. **Model-native** -- reproducible evaluations across supported model profiles
   establish the capability, and no unobservable environment fact is lost.
   One successful session is insufficient; retain unproven safeguards.
4. **Merged** -- folded into a broader rule; name the absorbing rule.
5. **Harness-fixed** -- a named client version and reproducible tool/native
   evidence show that the failure no longer applies within a precise scope.
   Record the tool contract, reproduction and result; preserve guidance for
   other clients, configurations and unverified behavior.

Rules that state an environment fact or an exact command are NOT retirement
candidates on capability grounds. Model improvement does not make a CLI flag
knowable.

Retirement procedure:

1. Validate the ground -- confirm one of the five above applies, stated in
   one sentence.
2. Find every inbound reference -- `patterns/quick-reference.md`'s index,
   `templates/skills/` and `.claude/skills/`, `templates/commands/` and
   `.claude/commands/`, `patterns/agent-errors.md`, and `methodology/`.
   **Blocking condition:** if any inbound reference remains, stop and fix
   the references before continuing.
3. Write the ledger entry below: number, reason, release, replacement.
4. The number is permanently retired and never reused.

Every release runs a retirement review -- "what came out this cycle" is
asked every time, even when the answer is "nothing." There is no retirement
quota. Rule IDs and error IDs are separate permanent numbering systems.

### Retirement Ledger

| Rule | Retired in | Ground     | Replacement                                    |
|------|------------|------------|------------------------------------------------|
| 67   | v1.27.0    | Merged     | Rule #64 -- count CI runs before triggering    |
| 69   | v1.13.0    | Superseded | Renumbered to #72 (CHANGELOG.md v1.13.0)       |
| 80   | v1.27.0    | Merged     | Rule #13 (TDD) plus the pre-commit verify gate |

### v2 Review: Retained and Narrowed (2026-09-05)

No additional IDs are retired. Error #1 now scopes sibling cancellation to the
observed harness; aggregate verification remains required. Errors #2/#24 retain
explicit worktree/cross-project paths: the current Codex `exec_command` schema
states that omitted `workdir` uses the turn cwd and supplied `workdir` applies
to that call. This refutes a universal persistent-shell assumption, not path or
branch safety. Current Claude cwd behavior remains unverified. Error #8 retains
explicit path resolution where the file API does not promise tilde expansion.
Error #19 retains recovery from observed blocked writes without a universal
filename/content-filter claim. Errors #37/#38 retain launchd diagnostics and
the historical wrapper workaround; the original client version and a current
reproduction are missing, so neither universal failure nor a harness fix is
claimed. Rule #74 and other model-capability safeguards remain active.

A harness-fixed retirement must add version-bound reproduction evidence to
this ledger before removing guidance. See [compatibility follow-ups](../../docs/compatibility-followups.md)
for outstanding native and sibling-project checks.

## Consistency Sweep for Workflow Changes

If a change touches workflow rules, topology guidance, commands, rules,
skills, hooks, or onboarding docs, sweep all documentation layers:

1. `methodology/`
2. `templates/`
3. Repo-local `.claude/` self-application -- most of it now **symlinks** into
   `templates/` and follows automatically. Only the files listed as divergent
   in `.claude/DIVERGENCE.md` need a second edit; `check-tree-drift.sh` fails
   the build if you miss one or add an untracked pair.
4. `CLAUDE.md` and `AGENTS.md`
5. `README.md` and `GUIDE.md`
6. `CHANGELOG.md`

Then run the invariant scripts rather than re-reading by eye:
`templates/scripts/verify-counts.sh`, `verify-version.sh`, `verify-skills.sh`,
`check-tree-drift.sh`.
