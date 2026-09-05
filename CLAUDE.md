@AGENTS.md

# Claude Code integration

Shared project intelligence and owner constraints live in AGENTS.md.
cc-rpi's direct installation exposes managed skills in `.claude/skills/`;
its plugin exports only `generated/claude/skills/`. Do not register both routes.
Use `/rpi-research`, `/rpi-plan`, `/rpi-implement` and `/rpi-validate`, or the
`/cc-rpi:rpi-plan` form when using the plugin. Native `/plan` remains a mode.

Claude keeps native `/simplify`; `codex-simplify` is exported only to Codex.
The local Drawio skill is a project-owned extension, never a product domain skill.
Native `.claude/rules/` path rules complement the shared root policy.
Hook registration in `.claude/settings.json` is distinct from native trust and
observed enforcement. PostToolUse feedback cannot prevent an edit already made.

The selected session model/effort is inherited by default. Optional native model
profiles must be deliberately selected; prose does not switch a running model.
