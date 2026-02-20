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
2. Add a one-liner to `patterns/quick-reference.md`.

### Proposing a Methodology Improvement

If you've discovered a better workflow, a new best practice, or a refinement to an existing phase:

1. Open an issue using the **Methodology Improvement** template.
2. Describe what you learned, how you validated it, and where it fits in the methodology.

Or submit a PR:
1. Add or modify the appropriate file under `methodology/`.
2. If it's a new topic, create a new file and update `methodology/README.md`.

### Improving Templates

If the CLAUDE.md template, setup checklist, or slash commands could be better:

1. Submit a PR with your changes to files under `templates/`.
2. Explain what problem the change addresses.

## Pull Request Guidelines

- **Keep PRs focused.** One pattern, one improvement, one fix per PR.
- **Keep entries generic.** No project-specific references, company names, or proprietary details.
- **Use file:line references** instead of code snippets in documentation — snippets go stale.
- **Test your patterns.** If you're adding an error pattern, confirm the solution works across at least two sessions.
- **Follow existing format.** Match the structure and tone of existing entries.

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
