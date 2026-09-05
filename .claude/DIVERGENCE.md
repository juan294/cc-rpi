# Divergence Manifest

`templates/` is the canonical product. `generated/` contains deterministic native
Claude/Codex output from `templates/distribution.json` and the two adapters.
Never hand-edit generated files. The renderer checks exact source coverage,
resources, metadata, instruction blocks and self-application.

## Generated self-application

The manifest selects direct self-application for both harnesses, project-scope
workflows, the Codex-only helper and this repository's domain modules. Individual
`.claude/skills/` and `.agents/skills/` links point into the matching generated
skill directories. The four user lifecycle skills are not duplicated at project
scope. Native plugin registration must not duplicate these direct registrations.

Shared universal RPI and push policies render once into marked root AGENTS blocks;
CLAUDE imports AGENTS. The old local `rules/rpi-details.md` divergence is removed:
project facts in AGENTS specify main, so a second always-loaded workflow body is
unnecessary. The remote-budget rule is consolidated into push accountability.
Six rule bodies remain available under `.rpi/rules/`; only four conditional rules
are native Claude registrations. Codex uses the explicit root task/path map.

`rpi-distribution.py check-generated` compares a fresh render, and `check-self`
checks the selected full native directories, root blocks and rule mappings.
Copies are valid where native symlink support is unavailable, provided bytes
match; native Windows execution is not claimed without testing.

## Linked

The following compatibility/infrastructure files remain linked directly to
`templates/`. The other generated registrations are enumerated by the distribution
manifest, avoiding a second hand-maintained inventory here.

| File |
| --- |
| `commands/describe-pr.md` |
| `commands/fix-ci.md` |
| `commands/implement.md` |
| `commands/pre-launch.md` |
| `commands/release.md` |
| `commands/remediate.md` |
| `commands/research.md` |
| `commands/triage.md` |
| `commands/update-docs.md` |
| `commands/validate.md` |
| `hooks/verify-edit.sh` |
| `scripts/contract-metrics.py` |
| `scripts/validate-findings.py` |
| `scripts/verify-counts.sh` |
| `scripts/verify-skills.sh` |
| `scripts/verify-version.sh` |

## Divergent

| File | Why it differs |
| --- | --- |
| `hooks/guard-bash.sh` | The v1 wrapper's generic protected-main guard differs from this repository's explicitly authorized main-only release topology. Phase 4 replaces this fail-open implementation with a shared fail-closed parser and explicit native boundaries. |

## Compatibility and local ownership

Known legacy commands now contain explicit-only rename notices. Managed `plan`
and `status` registrations are discontinued because native commands own those
names. Recovery copies are local under `.rpi/local/legacy-command-recovery/`, and
immutable source history remains in commit `e9dad45`. Custom commands are not
removed or inferred to be managed by filename.

`.claude/skills/drawio/` is a project-owned local extension. It has no exported
`templates/skills/` counterpart and is not one of the 12 domain skills. Preserve
its editable sources and specialized desktop exporter instructions during
self-application, update and detach. Local contributing/git recipes and project
facts likewise remain repository-owned extensions.
