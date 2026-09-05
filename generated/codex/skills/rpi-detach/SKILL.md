---
name: "rpi-detach"
description: "Remove proven-owned RPI installation components while preserving project instructions, custom settings, skills and user work products."
---

# Detach a Project from RPI

Remove only proven-owned unchanged RPI components within the explicit detach
request. Keep project intelligence, custom settings and user work products.

Read [the lifecycle contract](references/lifecycle-contract.md) completely.
Resolve the installed package/source and target project from actual metadata and
the request; do not assume the current directory is the intended target. Use the
ownership-aware engine's explicit source/target plan/apply interface. Skill
invocation or tool visibility does not grant extra authority.

## Inventory and review

1. Read the project's manifest/baselines, legacy evidence and current registrations.
   If no owned installation exists, report nothing to detach; preserve unknown
   candidates. Native plugin removal and shared user lifecycle removal are separate
   scopes; project detach cannot remove them.
2. Generate the engine's explicit `detach` plan for the target. Classify owned
   unchanged files, owned edited files, managed blocks/settings keys, unknown
   content and user work products. Record exactly what is removed and retained.
3. Present the concrete diff and recovery location. Use the detach authorization
   already supplied for safe owned removal; seek input only for a genuinely new
   destructive scope. A detach request does not authorize removal of research,
   plans, decisions, handoffs, custom skills, schedules or unrelated settings.

## Apply and preserve

1. Apply the reviewed engine plan transactionally after baseline/precondition
   verification. Retain edited or unknown files and explain the disposition.
2. Preserve AGENTS.md and CLAUDE.md; remove only their proven-owned unchanged
   blocks while keeping user additions and valid instruction relationships.
3. Remove only individually owned unchanged settings/hook registrations. Keep
   remaining JSON keys, permissions, environment and the user's settings files.
4. Preserve native plugin cache ownership and the independent user-scope lifecycle
   installation. Do not bulk-delete `.claude`, `.agents`, command or skill trees.
5. Keep curated docs and operational reports/logs. Remove only empty owned
   directories when safe. Existing launchd/cron schedules require their own
   explicit scope and concrete reviewed change; do not unload them implicitly.
6. Preserve recovery receipts and required baseline bytes outside the removed
   tree until verification and any recovery obligation finish.

## Completion

Verify remaining user files/settings and native registrations, removed managed
components, instruction integrity and recovery availability. Commit only the
reviewed local detach changes atomically where appropriate. Report removed and
retained files/blocks/keys, conflicts, recovery location and commit identity.
Do not claim complete detachment when conflicts remain. A repeated detach should
make no further changes. Re-adoption uses `rpi-adopt`; do not start it automatically.
