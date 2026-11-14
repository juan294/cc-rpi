# Project overlays

A project overlay holds one project's additions to one rpi-* workflow skill. It lets a project keep its own procedure without editing the managed `SKILL.md`. An edited managed skill can conflict with a later upstream change; an overlay cannot.

## Location and ownership

- One file per workflow skill: `.rpi/project/<skill-name>.md`, for example `.rpi/project/rpi-release.md`.
- The project owns the file. Track it in Git. Install, update and detach never read, write or delete it, and no component can claim the `.rpi/project` path.
- Both harnesses read the same file. Each of the 16 workflow skills has a `## Project overlay` section that tells the agent to read the file when it exists. The four lifecycle skills (`rpi-adopt`, `rpi-bootstrap`, `rpi-detach`, `rpi-update`) have no overlay.

## File format

```
<!-- rpi-overlay: skill=rpi-release; written-against=<12 hex characters> -->
# Project overlay for rpi-release

## Procedure
Project steps, checks and profile choices.

## Declared overrides
- Stock rule: "<exact quoted sentence from the stock skill>"
  Override: <what the project does instead>
  Reason: <why>
  Source: <commit or document that held the text>
  Owner decision: <YYYY-MM-DD, where recorded>
```

`written-against` is the first 12 hex characters of `source.authored_sha256` for that skill's `SKILL.md` entry in `.rpi/manifest.json`; when that hash is known, `rpi-status` prints the full header line. The value is the same for both harnesses and changes only when that stock skill changes, which is when the overlay needs a review. Leave out `## Declared overrides` when there are none.

## Statuses

`rpi-status` and the engine's `diagnose` report each file in `.rpi/project/` without printing its text:

| Status | Meaning | Fix |
| --- | --- | --- |
| `present` | The header matches the installed skill. | None. |
| `stale` | The stock skill changed since the overlay was reviewed. | Review the overlay against the new skill, then replace the header with the printed `header_line`. |
| `inert` | An installed copy of the skill has no `## Project overlay` section, so that harness ignores the overlay. | Run `rpi-update`. |
| `invalid` | The file is unreadable, is not a regular file, is not for an installed workflow skill, or its first line is not that skill's header. | Rename, remove or fix the file, or use the printed `header_line`. |

Staleness is not checked for an installation that has not recorded authored hashes yet; the next update records them. Files whose names start with a dot are ignored. Diagnostics inspect the direct-route skill copies in `.claude/skills/` and `.agents/skills/`; on a plugin-route installation they cannot see the installed skill, so an overlay reads as `invalid` there.

## What an overlay can and cannot do

An overlay can add steps and checks and make the workflow stricter.

An overlay cannot grant push, tag, merge, deployment or publication authority. It cannot relax a gate. A gate is any rule that blocks or permits a release, publication, merge, deployment or phase acceptance, including which findings block, required checks and verification, and any safety or authorization rule, such as fixture, cleanup, real-user data and outward-action rules.

A declared override can change other procedure detail only. Each entry quotes the stock rule and names the reason, the source and the owner decision. The owner decision is a decision the owner made and recorded; the commit that first held the text is its source, not its approval.

A choice that the stock skill already leaves to the project, such as whether the release profile selects Wave B exploratory charters, belongs in `## Procedure`. It is not an override.

## Enforcement

This is an instruction contract. Nothing parses an overlay to stop forbidden text. Push and tag protection stays with the existing guard hook and `.rpi/policy.json`. Review overlays like any other change to the project's release procedure.
