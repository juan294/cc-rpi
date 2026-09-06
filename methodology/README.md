# RPI Methodology for Claude Code and Codex

> Adapted from HumanLayer's opencode-rpi implementation and their ACE-FCA (Advanced Context Engineering for Coding Agents) framework.

## Reading Order

1. **[philosophy.md](philosophy.md)** — Core tenets, error amplification, mental alignment. Read this first to understand WHY the methodology works.
2. **[context-engineering.md](context-engineering.md)** — The foundational discipline: compaction, context quality, progressive disclosure, settings & permissions. This is the technical backbone.
3. **[four-phases.md](four-phases.md)** — The Research-Plan-Implement-Validate workflow with detailed processes for each phase.
4. **[agent-design.md](agent-design.md)** — Bounded assignments, domain coverage, independent review, native skills, optional teams and harness-specific tools.
5. **[pseudocode-notation.md](pseudocode-notation.md)** — Compact notation for writing implementation plans.
6. **[testing.md](testing.md)** — Automated-first verification hierarchy, TDD protocol, and success criteria format.
7. **[push-accountability.md](push-accountability.md)** — Local verification and authorized publication: exact-commit monitoring, local failure repair.
8. **[ci-and-guardrails.md](ci-and-guardrails.md)** — Pre-commit hooks, CI workflows, development guardrails, enforcement stack.
9. **[scheduled-agents.md](scheduled-agents.md)** — Recurring quality agents on cron/launchd, shared context system.
10. **[cost-monitoring.md](cost-monitoring.md)** — Session inheritance, explicit economy choices, and measuring cost per outcome.
11. **[error-success-logging.md](error-success-logging.md)** — Framework for systematic skill improvement through logging.
12. **[webmcp-tool-design.md](webmcp-tool-design.md)** — Agent-facing tool design as an RPI application: the WebMCP/server-MCP boundary, the role-play-then-eval obligation. Conditional knowledge, not part of the spine -- read it when a project exposes tools to an agent.

## The One-Paragraph Summary

Every significant change goes through **Research** (describe the code as written),
**Plan** (create an implementation specification), **Implement** (TDD, independent
review, repair and simplify), and **Validate** (verify the approved scope against
the actual candidate). Use `rpi-assess` separately for requested evaluation.
Preserve phase artifacts and acceptance boundaries; an explicit continuation
request permits further phases without removing their checks. Narrow tasks may
stay with the parent, while independent assignments carry bounded scope and
required evidence. Model and effort inherit the owner's active pane.

The methodology is shared. Canonical `templates/skills/` sources render native
Claude and Codex packages; AGENTS.md holds shared facts and CLAUDE.md imports it.
Use namespaced `rpi-research`, `rpi-plan`, `rpi-implement` and `rpi-validate`
workflows, preserving the native client's own plan/status commands. Hook
registration is not proof of trust or execution. Read [the guide](../GUIDE.md),
[model profiles](../docs/model-profiles.md) and
[compatibility evidence](../docs/compatibility.md) for the implemented routes
and verified limitations.
