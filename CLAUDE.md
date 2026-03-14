# cc-rpi -- Claude Code Reference & Project Intelligence

## One-liner

Blueprint repository for Claude Code projects. Contains the RPI methodology, 53 known agent error patterns, 57 operational rules, and templates for CLAUDE.md, slash commands, and project setup.

## Stack

Markdown documentation, shell scripts (bash). CI: GitHub Actions with markdownlint.

## How This Repo Is Used

When starting a new project, the agent is told: "Go check my cc-rpi repository and set up the environment to follow all the best practices."

The agent should:
1. Read `patterns/quick-reference.md` -- internalize all operational rules
2. Read `patterns/agent-errors.md` -- know every known error pattern
3. Read `methodology/README.md` -- understand the RPI approach (follow reading order for depth)
4. Use `templates/setup-checklist.md` to set up the new project
5. Adapt `templates/CLAUDE.md.template` for the new project's CLAUDE.md
6. Copy `templates/commands/` into the new project's `.claude/commands/`

## RPI Workflow

This project follows its own Research-Plan-Implement pattern.
All significant changes go through four phases:
1. /research -- Understand the codebase as-is
2. /plan -- Create a phased implementation spec
3. /implement -- Execute one phase at a time with review gates
4. /validate -- Verify implementation against the plan

### Context Management

- Each RPI phase should be its own conversation. Don't run research + plan + implement in one session.
- Use `/clear` between unrelated tasks. Use `/compact` when context is heavy but the task continues.
- Subagents are context control mechanisms -- they search/read in their window and return only distilled results.

### Rules for All Phases

- Read all mentioned files COMPLETELY before doing anything else.
- Never suggest improvements during research -- only document what exists.
- Every code reference must include file:line.
- Spawn parallel subagents for independent research tasks.
- Wait for ALL subagents before synthesizing.
- Never write documents with placeholder values.

### Rules for Implementation

- Follow the atomic loop: implement -> review (plan compliance) -> fix -> approve -> `/simplify` (code quality) -> verify.
- Run `/simplify` after reviewer approval -- it handles code reuse, quality, and efficiency in one native pass.
- Check for `[batch-eligible]` phases in the plan -- use `/batch` to execute independent phases in parallel.
- STOP after each phase and wait for human confirmation.
- If the plan doesn't match reality, STOP and explain the mismatch.

## Key Commands

```bash
# Verification (CI runs markdownlint)
npx markdownlint '**/*.md' --ignore node_modules --ignore .claude 2>&1
```

### CRITICAL: Run verification commands sequentially, NEVER in parallel

Never run verification commands as parallel sibling Bash tool calls.
Chain with `&&` or `;`.

## Git Workflow

**`main` is the only branch. This is a documentation project -- no develop/main split.**

1. All work happens directly on `main` (or short-lived feature branches for large changes)
2. Always run markdownlint before committing
3. Always commit before pulling -- `git pull --rebase` requires a clean tree (hook enforced)
4. Before any commit, verify the current branch -- run `git branch --show-current`

### Commit Messages

Use conventional commits:
```
feat: description       # New errors, rules, methodology content
fix: description        # Corrections to existing content
docs: description       # GUIDE.md, README, examples
chore: description      # CI, templates, scripts
release: vX.Y.Z         # Version bumps
```

## Agent Operational Rules

Read `patterns/quick-reference.md` for the full rule set (57 rules).
Read `patterns/agent-errors.md` for detailed error patterns (53 errors).

These files ARE the source of truth -- they live in this repo. Do not duplicate their content here.

### Shell & Tools
- Chain verification commands sequentially, never as parallel Bash calls
- Never use `~` in file tool paths -- use full absolute paths starting with `/`

### Git Recipes (hooks enforce critical steps)
```bash
# Push sequence -- ALWAYS commit before pulling (Error #33, hook enforced)
git add <files> && git commit -m "msg" && git pull --rebase && git push

# Push with tag -- NEVER use --tags (Error #44, hook enforced)
git push origin main && git push origin v1.0.0
# Or: git push origin main --follow-tags

# Worktree cleanup
git worktree remove --force <path>; git branch -D <branch>
```

### GitHub CLI
- Don't guess `gh --json` field names -- query available fields first
- Check CI per-PR with `--json`, not chained human-readable output

## Push Accountability

After every push, verify CI:
1. `gh run list --branch main --limit 1` to check status
2. If CI fails -- investigate with `gh run view <id> --log-failed`, fix, and re-push
3. The push isn't done until CI is green

## Contributing to This Repo

When new error patterns are discovered during work on ANY project:
1. Add them to `patterns/agent-errors.md` following the existing format
2. Add a one-liner to `patterns/quick-reference.md`
3. Update counts in `GUIDE.md` (two locations: prose paragraph + "Where to Go Deeper" table)
4. Update `CHANGELOG.md`
5. Keep entries generic -- no project-specific references

When new best practices or methodology refinements are confirmed:
1. Add them to the appropriate file under `methodology/`
2. Or create a new file under `patterns/` if it's a distinct topic

## Repo Structure

```
cc-rpi/
├── CLAUDE.md                         # This file
├── GUIDE.md                          # Human-readable quick-start guide
├── README.md                         # Public documentation
├── .claude/
│   ├── settings.json                 # Agent Teams, hooks, permissions
│   ├── hooks/guard-bash.sh           # PreToolUse enforcement (Errors #33, #44, #48)
│   └── commands/                     # Slash commands (copied from templates/)
├── docs/
│   ├── research/                     # RPI research documents about this repo
│   └── plans/                        # RPI implementation plans for this repo
├── methodology/                      # The RPI approach (11 files)
├── examples/                         # Sample documents and workflow walkthroughs
├── patterns/                         # Operational knowledge
│   ├── quick-reference.md            # 57 rules to internalize before any work
│   └── agent-errors.md               # 53 errors with symptoms and solutions
└── templates/                        # Files to adapt for new projects
    ├── CLAUDE.md.template            # Starting point for project CLAUDE.md
    ├── settings.json.template        # .claude/settings.json template
    ├── setup-checklist.md            # Step-by-step new project setup
    ├── hooks/guard-bash.sh           # Hook template (source for .claude/hooks/)
    ├── commands/                     # Command templates (source for .claude/commands/)
    └── scripts/                      # Scheduled agent shell script templates
```

## Project File Locations

Go directly to these paths -- never search the codebase for them.

| Topic | Path | Notes |
|-------|------|-------|
| Error catalog | `patterns/agent-errors.md` | Full entries with symptoms, root cause, solution |
| Operational rules | `patterns/quick-reference.md` | One-liner rules (source of truth) |
| Methodology | `methodology/` | 11 files, reading order in `methodology/README.md` |
| Templates | `templates/` | Source files adapted for new projects |
| Command source | `templates/commands/` | Canonical command definitions |
| Active commands | `.claude/commands/` | Copies of templates/ for this repo's own use |
| Hook source | `templates/hooks/guard-bash.sh` | Canonical hook definition |
| Active hook | `.claude/hooks/guard-bash.sh` | Copy for this repo's own use |
| Research docs | `docs/research/YYYY-MM-DD-description.md` | RPI research about cc-rpi itself |
| Plans | `docs/plans/YYYY-MM-DD-description.md` | RPI plans for cc-rpi improvements |
| Examples | `examples/` | Sample research docs, plans, logs, workflows |
| Changelog | `CHANGELOG.md` | Version history with error/rule counts |
| Guide | `GUIDE.md` | Human-readable walkthrough (counts in 2 places) |

## Memory Management

When you discover an operational lesson during any session -- CI failure pattern, workaround, tooling quirk -- save it to auto memory immediately. Don't wait to be asked.

After completing any significant change, save the key decisions and context to auto memory so future sessions start with full awareness.
