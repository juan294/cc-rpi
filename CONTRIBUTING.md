# Contributing to cc-rpi

Thank you for your interest in improving cc-rpi! This repository is a living document — it gets better every time someone encounters a new pattern, discovers a better approach, or finds a gap in the methodology.

## How to Contribute

### Reporting a New Error Pattern

If you've encountered a recurring Claude Code agent error that isn't in the catalog:

1. Open an issue using the **Error Pattern** template.
2. Include: the symptom, root cause, correct approach, and what to avoid.
3. Keep it generic — no project-specific references.

Or submit a PR directly:
1. Add the detailed entry to `patterns/agent-errors.md` following the existing format.
2. Add a one-line pointer to `patterns/quick-reference.md`. That file is an
   **index**, not a catalog: the rule body itself goes in the skill, rule file,
   or command that needs it, and the index line names where it went.
3. Update any hard-coded counts or references in onboarding docs and
   skills. Run `templates/scripts/verify-counts.sh` rather than grepping by
   hand — it computes the counts from the catalogs and reports every location
   that disagrees.

### Proposing a Methodology Improvement

If you've discovered a better workflow, a new best practice, or a refinement to an existing phase:

1. Open an issue using the **Methodology Improvement** template.
2. Describe what you learned, how you validated it, and where it fits in the methodology.

Or submit a PR:
1. Add or modify the appropriate file under `methodology/`.
2. If it's a new topic, create a new file and update `methodology/README.md`.

### Retiring a Rule or Error

Rules and errors can also come out, not just go in. A rule or error is a
retirement candidate on exactly one of four grounds:

- **Superseded** -- another rule covers it completely.
- **Hook-enforced** -- a Tier 1 guard now blocks it mechanically.
- **Model-native** -- current frontier models handle it by judgment.
- **Merged** -- folded into a broader rule.

See the full procedure, non-candidate criteria, and the Retirement Ledger
in `.claude/rules/contributing.md`.

### Consistency Sweep for Workflow Changes

If your change affects workflow, topology guidance, commands, rules,
skills, hooks, or onboarding instructions, include a consistency sweep
before merging.

Check these layers together:

1. `methodology/`
2. `templates/`
3. Repo-local `.claude/` self-application — mostly symlinks into `templates/`,
   so it follows automatically; only the files listed as divergent in
   `.claude/DIVERGENCE.md` need a second edit
4. `CLAUDE.md` and `AGENTS.md`
5. `README.md` and `GUIDE.md`
6. `CHANGELOG.md`

Then run `templates/scripts/verify-counts.sh`, `verify-skills.sh`, and
`check-tree-drift.sh` — they catch the drift a manual sweep misses.

### Improving Templates

If the CLAUDE.md template, setup checklist, or slash commands could be better:

1. Submit a PR with your changes to files under `templates/`.
2. Explain what problem the change addresses.

### `templates/` vs `.claude/`, and symlinks

`templates/` is the product shipped downstream; `.claude/` is cc-rpi's own
application of it. Where the two are identical, `.claude/` holds a **symlink**
into `templates/` — so edit the template and the self-application follows. Four
files deliberately differ, because a blueprint written for any repo cannot state
a fact true only of this one. `.claude/DIVERGENCE.md` records which is which and
why, and `templates/scripts/check-tree-drift.sh` (run in CI) fails when reality
and that manifest disagree.

**On Windows:** symlinks need developer mode or an elevated shell. Without it, a
checkout materializes them as regular copies. The drift check reports that as a
failure with a fix rather than passing silently, so you get a clear error instead
of an invisible fork. Enable developer mode, or clone in WSL.

## Pull Request Guidelines

- **Keep PRs focused.** One pattern, one improvement, one fix per PR.
- **Keep entries generic.** No project-specific references, company names, or proprietary details.
- **Use file:line references** instead of code snippets in documentation — snippets go stale.
- **Test your patterns.** If you're adding an error pattern, confirm the solution works across at least two sessions.
- **Follow existing format.** Match the structure and tone of existing entries.
- **Sweep all documentation layers** when workflow guidance changes.
  Don't update a template without checking the repo-local copy and
  onboarding docs.

## Commit Messages

Use conventional commits:

```
feat(patterns): add new error pattern for X
fix(methodology): correct phase 2 process step
docs(templates): clarify CLAUDE.md authoring guidance
```

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards.

## Questions?

Open a [GitHub Discussion](../../discussions) or an issue if something is unclear.
