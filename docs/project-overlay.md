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

`written-against` is the first 12 hex characters of `source.authored_sha256` for that skill's `SKILL.md` entry in `.rpi/manifest.json`. The value is the same for both harnesses and changes only when that stock skill changes, which is when the overlay needs a review. Leave out `## Declared overrides` when there are none.

## What an overlay can and cannot do

An overlay can add steps and checks and make the workflow stricter.

An overlay cannot grant push, tag, merge, deployment or publication authority. It cannot relax a gate. A gate is any rule that blocks or permits a release, publication, merge, deployment or phase acceptance, including which findings block, required checks and verification, and any safety or authorization rule, such as fixture, cleanup, real-user data and outward-action rules.

A declared override can change other procedure detail only. Each entry quotes the stock rule and names the reason, the source and the owner decision. The owner decision is a decision the owner made and recorded; the commit that first held the text is its source, not its approval.

A choice that the stock skill already leaves to the project, such as whether the release profile selects Wave B exploratory charters, belongs in `## Procedure`. It is not an override.

## Enforcement

This is an instruction contract. Nothing parses an overlay to stop forbidden text. Push and tag protection stays with the existing guard hook and `.rpi/policy.json`. Review overlays like any other change to the project's release procedure.
