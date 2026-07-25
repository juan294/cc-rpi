# cc-rpi -- Claude Code Reference & Project Intelligence

## One-liner

Blueprint repository for Claude Code projects, with Codex compatibility
via `AGENTS.md` plus Codex-only helper skills in `.codex/skills/`.
Contains the RPI methodology, 64 known agent error patterns, 81
operational rules, and templates for CLAUDE.md, AGENTS.md, slash
commands, skills, rules, and project setup.

## Stack

Markdown documentation, shell scripts (bash). CI: GitHub Actions -- internal
link validation, shellcheck, count/skill/drift checks, JSON and YAML syntax.

## How This Repo Is Used

When starting a new project, the agent is told: "Go check my cc-rpi repository and set up the environment to follow all the best practices."

The agent should:

1. Read `patterns/quick-reference.md` -- internalize all operational rules
2. Read `methodology/README.md` -- understand the RPI approach (follow reading order for depth)
3. Use `templates/setup-checklist.md` to set up the new project
4. Adapt `templates/CLAUDE.md.template` for the new project's CLAUDE.md
5. Adapt `templates/AGENTS.md.template` for the new project's AGENTS.md
6. Copy `templates/commands/` into the new project's `.claude/commands/`
7. Copy relevant `templates/skills/` into `.claude/skills/`
8. Copy relevant `templates/rules/` into `.claude/rules/`
9. If Codex-only helpers are needed, sync them from `.codex/skills/`
   into `~/.codex/skills/`

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
# What CI actually runs (.github/workflows/validate.yml)
bash templates/scripts/verify-counts.sh      # error/rule/skill counts agree
bash templates/scripts/verify-skills.sh      # skill frontmatter + 500-line ceiling
bash templates/scripts/check-tree-drift.sh   # templates/ vs .claude/ symlinks
shellcheck --severity=warning templates/hooks/*.sh templates/scripts/*.sh
python3 templates/scripts/validate-findings.py --self-test
python3 templates/scripts/contract-metrics.py --self-test
```

Run verification sequentially with `&&` or `;`, NEVER as parallel Bash calls.

This repo ships **no markdownlint config**, so `npx markdownlint` applies its
80-column defaults, which every file here violates by design. The
`verify-edit.sh` hook gates its markdownlint check on a config existing, and CI
does not run it at all. Don't reflow prose to satisfy it. The real markdown
gates are the no-emoji hook and CI's internal-link validation.

## Git Workflow

**`main` is the long-lived canonical branch for this repo.**

1. Research and planning happen against `main`
2. Implementation happens in temporary branches or isolated worktrees
3. Direct pushes to `main` are exceptional/high-stakes, not the default path
4. Always run the verification commands above before committing
5. Always commit before pulling (hook enforced)
6. Verify current branch before any commit

### Commit Messages

```
feat: description       # New errors, rules, methodology content
fix: description        # Corrections to existing content
docs: description       # GUIDE.md, README, examples
chore: description      # CI, templates, scripts
release: vX.Y.Z         # Version bumps
```

## Push Accountability

After every push, verify CI on the branch you just pushed:

1. `gh run list --branch $(git branch --show-current) --limit 1` to check status
2. If CI fails -- investigate with `gh run view <id> --log-failed`, fix, re-push
3. The push isn't done until CI is green

## Project File Locations

Go directly to these paths -- never search the codebase for them.

| Topic | Path | Notes |
|-------|------|-------|
| Error catalog | `patterns/agent-errors.md` | 64 errors, source of truth |
| Operational rules | `patterns/quick-reference.md` | Index of 81 rules -> their surfaces |
| Deployment safety | `patterns/deployment-safety.md` | Resource efficiency rules |
| Skill templates | `templates/skills/` | 11 domain skills |
| Codex-only skills | `.codex/skills/` | Personal Codex helpers such as `codex-simplify` |
| Rule templates | `templates/rules/` | 5 conditional/universal rules |
| Active rules | `.claude/rules/` | cc-rpi's own rules |
| Methodology | `methodology/` | 12 files, order in README.md |
| Commands | `templates/commands/` | Canonical command definitions |
| Release verification | `templates/e2e-pro-playbook-template.md` | E2E Pro playbook; Wave A gate + structural waves, `/explore-release` runs Wave B |
| Active commands | `.claude/commands/` | This repo's own commands |
| Hooks | `templates/hooks/guard-bash.sh` (PreToolUse), `templates/hooks/verify-edit.sh` (PostToolUse) | Templates; `.claude/hooks/` active |
| Contract validator | `templates/scripts/validate-findings.py` | Enforces pre-launch/remediate Finding-ID contract; `.claude/scripts/` active |
| Contract metrics | `templates/scripts/contract-metrics.py` | Aggregates hook telemetry (`.claude/metrics/contract-events.jsonl`) into block/self-correction rates; weekly snapshot via `scripts/agents/contract-metrics-agent.sh` |
| Research | `docs/research/YYYY-MM-DD-*.md` | RPI research about cc-rpi |
| Plans | `docs/plans/YYYY-MM-DD-*.md` | RPI plans for cc-rpi |

## Memory

Save operational lessons to auto memory immediately. Don't wait to be asked.
