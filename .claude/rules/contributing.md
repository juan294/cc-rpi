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
2. Add a one-liner to `patterns/quick-reference.md`
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

A rule or error is a retirement candidate only on one of four grounds:

1. **Superseded** -- another rule covers it completely; name the successor.
2. **Hook-enforced** -- a Tier 1 guard now blocks it mechanically; the rule
   becomes an annotation on the hook rather than prose.
3. **Model-native** -- current frontier models handle it by judgment, and
   the rule states no environment fact the model cannot observe.
4. **Merged** -- folded into a broader rule; name the absorbing rule.

Rules that state an environment fact or an exact command are NOT retirement
candidates on capability grounds. Model improvement does not make a CLI flag
knowable.

Retirement procedure:

1. Validate the ground -- confirm one of the four above applies, stated in
   one sentence.
2. Find every inbound reference -- `patterns/quick-reference.md`'s index,
   `templates/skills/` and `.claude/skills/`, `templates/commands/` and
   `.claude/commands/`, `patterns/agent-errors.md`, and `methodology/`.
   **Blocking condition:** if any inbound reference remains, stop and fix
   the references before continuing.
3. Write the ledger entry below: number, reason, release, replacement.
4. The number is permanently retired and never reused.

Every release runs a retirement review -- "what came out this cycle" is
asked every time, even when the answer is "nothing."

### Retirement Ledger

| Rule | Retired in | Ground     | Replacement                                    |
|------|------------|------------|------------------------------------------------|
| 67   | v1.27.0    | Merged     | Rule #64 -- count CI runs before triggering    |
| 69   | v1.13.0    | Superseded | Renumbered to #72 (CHANGELOG.md v1.13.0)       |
| 80   | v1.27.0    | Merged     | Rule #13 (TDD) plus the pre-commit verify gate |

## Consistency Sweep for Workflow Changes

If a change touches workflow rules, topology guidance, commands, rules,
skills, hooks, or onboarding docs, sweep all documentation layers:

1. `methodology/`
2. `templates/`
3. Repo-local `.claude/` self-application
4. `CLAUDE.md` and `AGENTS.md`
5. `README.md` and `GUIDE.md`
6. `CHANGELOG.md`
