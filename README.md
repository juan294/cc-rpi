# cc-rpi — Claude Code Reference & Project Intelligence

A blueprint repository for setting up and running projects with [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Contains the RPI (Research-Plan-Implement) methodology, a catalog of known agent errors, and operational rules learned from hundreds of real sessions.

## What's Inside

### Methodology (`methodology/`)

The full Research-Plan-Implement pattern adapted for Claude Code, based on HumanLayer's opencode-rpi and ACE-FCA framework. Organized by topic:

- **Philosophy** — Core tenets, error amplification principle, mental alignment
- **Context Engineering** — The foundational discipline: compaction, context quality, utilization targets
- **Four Phases** — Research, Plan, Implement, Validate with detailed processes
- **Agent Design** — Documentarian rule, tool restrictions, subagent catalog
- **Pseudocode Notation** — Compact notation for writing implementation plans
- **Testing** — Automated-first verification hierarchy
- **Error & Success Logging** — Framework for systematic improvement

### Known Error Patterns (`patterns/`)

A catalog of recurring Claude Code agent errors documented from real sessions. Each entry includes the symptom, root cause, correct approach, and what to avoid:

- Shell behavior (parallel calls, cwd resets, tilde paths)
- Git operations (worktrees, pre-commit hooks, push rejections)
- GitHub CLI (`gh` field names, CI status checking)
- Node.js/TypeScript (ESM shebangs, Buffer vs string)

### Templates (`templates/`)

Ready-to-use starting points for new projects:

- **CLAUDE.md template** — Comprehensive project configuration with all operational rules baked in
- **Setup checklist** — Step-by-step guide for new project setup
- **Slash commands** — `/research`, `/plan`, `/implement`, `/validate`, `/describe-pr`

## How to Use This

### Setting Up a New Project

Tell Claude Code:

> Go read the cc-rpi repository at `~/Documents/GenAI_Projects/cc-rpi` and set up this project following all the best practices. Read the quick reference, error catalog, and methodology, then configure CLAUDE.md and slash commands for this project.

### Adding New Patterns

When you discover a new recurring error or best practice:

1. Add it to `patterns/agent-errors.md` (detailed entry with symptom/root cause/solution)
2. Add a one-liner to `patterns/quick-reference.md`
3. Keep entries generic — no project-specific references

## Credits

- [HumanLayer](https://humanlayer.dev/) — ACE-FCA framework and opencode-rpi implementation
- Adapted for Claude Code's native capabilities (CLAUDE.md, Task tool, slash commands)

## License

MIT
