# cc-rpi — Claude Code Reference & Project Intelligence

[![CI](https://github.com/juan294/cc-rpi/actions/workflows/validate.yml/badge.svg)](https://github.com/juan294/cc-rpi/actions/workflows/validate.yml)
[![Version: v2.0.0](https://img.shields.io/badge/Version-v2.0.0-orange.svg)](https://github.com/juan294/cc-rpi/releases/tag/v2.0.0)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Claude Code](https://img.shields.io/badge/Built%20for-Claude%20Code-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)

![Chapa Badge](https://chapa.thecreativetoken.com/u/juan294/badge.svg)

A shared RPI (Research-Plan-Implement) blueprint for Claude Code and Codex.
One authored workflow corpus produces native skills and bundled resources for
both clients. Shared project intelligence lives in `AGENTS.md`; `CLAUDE.md`
imports it and adds Claude-specific guidance.

## Requirements

- Git and Python 3.11 or newer for installation and lifecycle operations.
- Claude Code, Codex, or both, configured for the chosen native route.
- For contributing: the tools and pinned Python dependencies listed in
  [CONTRIBUTING.md](CONTRIBUTING.md).

See [compatibility evidence](docs/compatibility.md) for tested versions, route
limitations and checks that remain unavailable. A generated file alone does not
prove native discovery, trust or execution.

## Quick Start

Clone a local source checkout:

```bash
git clone https://github.com/juan294/cc-rpi.git
cd cc-rpi
bash scripts/install.sh --check
```

Choose direct installation when you need a selected set of domain skills. Generate
an explicit plan for the four user-scope lifecycle skills:

```bash
bash scripts/install.sh --scope user --harness both --route direct \
  --output "$PWD/.rpi/local/user-install.json"
```

Read the plan and resolve any conflicts. Apply that exact file within your setup
request, then check the selected installation:

```bash
bash scripts/install.sh --apply "$PWD/.rpi/local/user-install.json"
bash scripts/install.sh --check --scope user --harness both --route direct
```

Select `--harness claude` or `--harness codex` when using only one client. Direct
user installations default to `~/.claude/skills/` and `~/.agents/skills/`, with
separate state under `~/.config/cc-rpi/installations/user`. The installer no longer
copies four unnamespaced commands or updates user files merely because it ran.

In the target project, invoke `rpi-bootstrap` for a new project or `rpi-adopt` for
an existing project. Claude direct skills use `/rpi-bootstrap` and `/rpi-adopt`;
Codex uses `$rpi-bootstrap` and `$rpi-adopt`. These workflows resolve an explicit
source/target and review the project installation plan before applying it.
Project scope owns the remaining workflows and selected domain modules; it does
not own the separate user lifecycle installation.

Native plugin installation is another route. Claude's package is this repository
root; Codex's self-contained package is `generated/codex/`. Native managers own
plugin installation, updates, removal and trust. Plugin selectors are namespaced,
for example Claude `/cc-rpi:rpi-research` and Codex `cc-rpi:rpi-research` in its
native skill selector. Use one registration route per harness and scope, and
verify discovery before invocation. Claude whole-package plugins cannot exclude
individual domain skills on the tested client; use the direct route for that
selection. See [GUIDE.md](GUIDE.md) and [compatibility](docs/compatibility.md).

## Updates, recovery and migration

Use `rpi-update` to compare installed files with their recorded baselines and an
explicit local source. Generate a new plan after source or target changes;
`ready`, `noop` and `conflict` are different outcomes. Review file, block and
settings-key ownership before applying. Permission/hook changes require the
engine's explicit capability selection and native setup review; a successful
copy is not permission approval.

`rpi-detach` removes only proven-owned unchanged content in the selected scope.
Custom instructions, edited/unknown files, research, plans and decisions are
preserved. Interrupted transactions retain journals; `scripts/install.sh --rollback`
takes the recorded journal path and refuses to overwrite concurrent
edits. Native plugin recovery remains the native manager's operation.

Read the [v2 migration guide](docs/migrations/v2.md) before adopting an existing
v1 installation. Legacy filenames and sync metadata do not establish ownership.
Native `/plan` and `/status` are not the RPI workflows: use `rpi-plan` and
`rpi-status`. Compatibility aliases are rename notices, not automatic forwarding.

## Workflow and model selection

Use descriptive `rpi-research`, evaluative `rpi-assess` when requested, then
`rpi-plan`, `rpi-implement` and `rpi-validate`. Implementation preserves TDD,
independent review, repair, simplify and complete applicable local verification.
A narrow task may stay with the parent; delegate bounded independent work when
useful, with at most three simultaneous implementers and lower resource limits
when needed. Pre-launch audits require eight core domains plus applicable agent
surfaces, not eight model instances.

Model and effort inherit the owner's active pane. [Optional native profiles](docs/model-profiles.md)
are explicit choices; installation does not rewrite global model defaults or
silently switch the parent to an economy model. Claude keeps native `/simplify`;
Codex receives the separate `codex-simplify` helper through its selected route.

Keep working branches/worktrees local. Run `bash scripts/verify-local.sh`, integrate
completed work locally, inspect hosted triggers and publish completed integration
only within explicit authorization. Never create Vercel Previews or use hosted
CI as a debugging loop. Production remains a separately authorized release.

## What's Inside

| Location | Purpose |
| --- | --- |
| [templates/distribution.json](templates/distribution.json) | Component identity, selection, ownership and bundled resources |
| `templates/skills/` | Canonical workflows and domain knowledge |
| `templates/adapters/` | Native metadata and configuration adapters |
| `generated/claude/`, `generated/codex/` | Deterministic complete native packages; never hand-edit |
| `templates/scripts/` | Renderer, transactional lifecycle, diagnostics and verification helpers |
| [methodology/](methodology/README.md) | Research, planning, implementation, testing and operational practices |
| [patterns/quick-reference.md](patterns/quick-reference.md) | Rule index; detailed recurring errors live in `patterns/agent-errors.md` |
| `examples/` | Research, phased plans and logging examples |
| [templates/setup-checklist.md](templates/setup-checklist.md) | Project setup and adaptation checks |
| `.claude/skills/`, `.agents/skills/` | This repository's self-applied native registrations |

The manifest supplies inventory counts. Shared universal policies render into
managed `AGENTS.md` blocks; conditional rules remain reachable through native
Claude path rules and Codex's explicit root task/path map. Local extensions such
as this repository's Drawio skill retain their own ownership.

Read [GUIDE.md](GUIDE.md) for the full workflow guide. Optional scheduled work is
configured separately; neither installation nor a source update creates a fleet
rollout, hosted schedule or global automatic sync.

## Adding New Patterns

When you discover a new recurring error or best practice:

1. Add it to `patterns/agent-errors.md` (detailed entry with symptom/root cause/solution)
2. Put the rule body in the surface that needs it — a skill, a `.claude/rules/` file, or a command — then add a one-line pointer to `patterns/quick-reference.md`, which is an index rather than a catalog
3. Keep entries generic — no project-specific references
4. Ask what came *out* this cycle, not only what went in — see the retirement ledger in `.claude/rules/contributing.md`

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## Community

- [GitHub Discussions](https://github.com/juan294/cc-rpi/discussions) — Ask questions, share ideas, discuss the methodology
- [Contributing Guide](CONTRIBUTING.md) — How to report patterns, propose improvements, submit PRs
- [Code of Conduct](CODE_OF_CONDUCT.md) — Expected behavior for all participants

## Credits

- [HumanLayer](https://humanlayer.dev/) — ACE-FCA framework and opencode-rpi implementation
- Adapted to native Claude Code and Codex workflows through one shared authored corpus

## License

[MIT](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.
