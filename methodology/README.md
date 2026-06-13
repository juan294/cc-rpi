# RPI Methodology for Claude Code

> Adapted from HumanLayer's opencode-rpi implementation and their ACE-FCA (Advanced Context Engineering for Coding Agents) framework.

## Reading Order

1. **[philosophy.md](philosophy.md)** — Core tenets, error amplification, mental alignment. Read this first to understand WHY the methodology works.
2. **[context-engineering.md](context-engineering.md)** — The foundational discipline: compaction, context quality, progressive disclosure, settings & permissions. This is the technical backbone.
3. **[four-phases.md](four-phases.md)** — The Research-Plan-Implement-Validate workflow with detailed processes for each phase.
4. **[agent-design.md](agent-design.md)** — Documentarian rule, tool restrictions, subagent catalog, Anthropic-native commands (`/simplify`, `/batch`), agent teams, autonomy principles, skills, custom agents, hooks.
5. **[pseudocode-notation.md](pseudocode-notation.md)** — Compact notation for writing implementation plans.
6. **[testing.md](testing.md)** — Automated-first verification hierarchy, TDD protocol, and success criteria format.
7. **[push-accountability.md](push-accountability.md)** — Post-push CI ownership: background polling, fix-and-repush cycle.
8. **[ci-and-guardrails.md](ci-and-guardrails.md)** — Pre-commit hooks, CI workflows, development guardrails, enforcement stack.
9. **[scheduled-agents.md](scheduled-agents.md)** — Recurring quality agents on cron/launchd, shared context system.
10. **[cost-monitoring.md](cost-monitoring.md)** — Model economics: cost pools, model-tier binding, access tiers, and measuring cost-per-outcome.
11. **[error-success-logging.md](error-success-logging.md)** — Framework for systematic skill improvement through logging.

## The One-Paragraph Summary

Every significant change goes through four phases: **Research** (understand the codebase as-is), **Plan** (create a phased implementation spec), **Implement** (execute one phase at a time with review gates), **Validate** (verify implementation against the plan). Each phase runs in its own conversation to manage context. Errors amplify downstream — a bad line of research becomes thousands of bad lines of code — so human review is focused on research and plans, not generated code.
