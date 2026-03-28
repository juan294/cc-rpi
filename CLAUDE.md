# cc-rpi -- Claude Code Reference & Project Intelligence

## One-liner

Blueprint repository for Claude Code projects. Contains the RPI methodology, 62 known agent error patterns, 72 operational rules, and templates for CLAUDE.md, slash commands, skills, rules, and project setup.

## Stack

Markdown documentation, shell scripts (bash). CI: GitHub Actions with markdownlint.

## How This Repo Is Used

When starting a new project, the agent is told: "Go check my cc-rpi repository and set up the environment to follow all the best practices."

The agent should:

1. Read `patterns/quick-reference.md` -- internalize all operational rules
2. Read `methodology/README.md` -- understand the RPI approach (follow reading order for depth)
3. Use `templates/setup-checklist.md` to set up the new project
4. Adapt `templates/CLAUDE.md.template` for the new project's CLAUDE.md
5. Copy `templates/commands/` into the new project's `.claude/commands/`
6. Copy relevant `templates/skills/` into `.claude/skills/`
7. Copy relevant `templates/rules/` into `.claude/rules/`

The error-patterns skill provides condensed error reference on demand. The full catalog (`patterns/agent-errors.md`) is available but not required for onboarding.

## RPI Workflow

This project follows its own Research-Plan-Implement pattern.

1. /research -- Understand the codebase as-is
2. /plan -- Create a phased implementation spec
3. /implement -- Execute one phase at a time with review gates
4. /validate -- Verify implementation against the plan

Each phase is its own conversation. STOP after each phase.
Use /clear between tasks, /compact when context is heavy.

## Key Commands

```bash
# Verification (CI runs markdownlint)
npx markdownlint '**/*.md' --ignore node_modules --ignore .claude 2>&1
```

Run verification sequentially with `&&` or `;`, NEVER as parallel Bash calls.

## Git Workflow

**`main` is the only branch. Documentation project -- no develop/main split.**

1. All work happens directly on `main`
2. Always run markdownlint before committing
3. Always commit before pulling (hook enforced)
4. Verify current branch before any commit

### Commit Messages

```
feat: description       # New errors, rules, methodology content
fix: description        # Corrections to existing content
docs: description       # GUIDE.md, README, examples
chore: description      # CI, templates, scripts
release: vX.Y.Z         # Version bumps
```

## Push Accountability

After every push, verify CI:

1. `gh run list --branch main --limit 1` to check status
2. If CI fails -- investigate with `gh run view <id> --log-failed`, fix, re-push
3. The push isn't done until CI is green

## Project File Locations

Go directly to these paths -- never search the codebase for them.

| Topic | Path | Notes |
|-------|------|-------|
| Error catalog | `patterns/agent-errors.md` | 62 errors, source of truth |
| Operational rules | `patterns/quick-reference.md` | 72 rules with scope/stack tags |
| Deployment safety | `patterns/deployment-safety.md` | Resource efficiency rules |
| Skill templates | `templates/skills/` | 9 domain skills |
| Rule templates | `templates/rules/` | 5 conditional/universal rules |
| Active rules | `.claude/rules/` | cc-rpi's own rules |
| Methodology | `methodology/` | 11 files, order in README.md |
| Commands | `templates/commands/` | Canonical command definitions |
| Active commands | `.claude/commands/` | This repo's own commands |
| Hooks | `templates/hooks/guard-bash.sh` | Template; `.claude/hooks/` active |
| Research | `docs/research/YYYY-MM-DD-*.md` | RPI research about cc-rpi |
| Plans | `docs/plans/YYYY-MM-DD-*.md` | RPI plans for cc-rpi |

## Memory

Save operational lessons to auto memory immediately. Don't wait to be asked.
