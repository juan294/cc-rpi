# cc-rpi — Claude Code Reference & Project Intelligence

## What This Is

This is the blueprint repository for all of Juan's projects. It contains:
- The RPI (Research-Plan-Implement) methodology adapted for Claude Code
- A catalog of known agent errors with proven solutions
- Operational rules that prevent recurring mistakes
- Templates for CLAUDE.md, slash commands, and project setup

## How This Repo Is Used

When starting a new project, the agent is told: "Go check my cc-rpi repository and set up the environment to follow all the best practices."

The agent should:
1. Read `patterns/quick-reference.md` — internalize all operational rules
2. Read `patterns/agent-errors.md` — know every known error pattern
3. Read `methodology/README.md` — understand the RPI approach (follow reading order for depth)
4. Use `templates/setup-checklist.md` to set up the new project
5. Adapt `templates/CLAUDE.md.template` for the new project's CLAUDE.md
6. Copy `templates/commands/` into the new project's `.claude/commands/`

## Repo Structure

```
cc-rpi/
├── CLAUDE.md                         # This file (repo self-description)
├── GUIDE.md                          # Human-readable quick-start guide
├── README.md                         # Public documentation
├── methodology/                      # The RPI approach
│   ├── README.md                     # Overview and reading order
│   ├── philosophy.md                 # Core tenets, error amplification
│   ├── context-engineering.md        # Context management, compaction, settings
│   ├── four-phases.md                # Research → Plan → Implement → Validate
│   ├── agent-design.md               # Documentarian rule, subagent catalog, teams, autonomy
│   ├── pseudocode-notation.md        # Plan notation format
│   ├── testing.md                    # Automated-first verification, TDD protocol
│   ├── push-accountability.md        # Post-push CI ownership, background verification
│   ├── ci-and-guardrails.md          # Pre-commit hooks, CI workflows, enforcement
│   ├── scheduled-agents.md           # Recurring quality agents, cron/launchd
│   └── error-success-logging.md      # Systematic improvement framework
├── examples/                         # Sample documents
│   ├── README.md                     # Index of all examples
│   ├── research-document.md          # Sample research phase output
│   ├── implementation-plan.md        # Sample plan with phases and pseudocode
│   ├── implementation-plan-phases/   # Per-phase detail files
│   │   └── phase-1.md
│   ├── error-log.md                  # Sample error log entry
│   ├── success-log.md                # Sample success log entry
│   └── pseudocode-examples.md        # Additional pseudocode notation examples
├── patterns/                         # Operational knowledge
│   ├── quick-reference.md            # Rules to internalize before any work
│   └── agent-errors.md               # Detailed error catalog with solutions
└── templates/                        # Files to adapt for new projects
    ├── CLAUDE.md.template            # Starting point for project CLAUDE.md
    ├── README-header.md              # Standard README header (badges, Chapa, divider)
    ├── settings.json.template        # .claude/settings.json (Agent Teams, hooks, permissions)
    ├── setup-checklist.md            # Step-by-step new project setup
    └── commands/                     # Slash command templates
        ├── research.md               # /research — codebase research
        ├── plan.md                   # /plan — implementation planning
        ├── implement.md              # /implement — phased execution
        ├── validate.md               # /validate — verification
        ├── describe-pr.md            # /describe-pr — PR description
        └── pre-launch.md             # /pre-launch — multi-agent production audit
```

## Contributing to This Repo

When new error patterns are discovered during work on ANY project:
1. Add them to `patterns/agent-errors.md` following the existing format
2. Add a one-liner to `patterns/quick-reference.md`
3. Keep entries generic — no project-specific references

When new best practices or methodology refinements are confirmed:
1. Add them to the appropriate file under `methodology/`
2. Or create a new file under `patterns/` if it's a distinct topic
