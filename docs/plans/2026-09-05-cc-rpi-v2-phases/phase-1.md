# Phase 1: correct policy, recipes, and artifact handling

[Main plan](../2026-09-05-cc-rpi-v2.md). Depends on the recorded main baseline. Not batch-eligible. Outcome: corrected v1-shaped content that can safely become v2 skills, plus a trustworthy local gate.

## Changes

1. Establish one canonical owner remote-budget rule and make every active recipe agree: local working branches, local integration, full local verification, trigger inspection, no Preview deployments, no feature-PR/debugging loop, separate production authorization. Update root/self-applied instructions as well as templates. Read-only inspection of existing runs/deployments remains allowed. Do not change remote repository settings, deploy integrations, or existing hosted schedules in this phase.
2. Correct git cleanup and lifecycle prose immediately: no default force-removal, unknown-file deletion, or whole AGENTS deletion. A worktree is disposable only after ownership, preserved changes and artifacts, and integration are established. The deterministic implementation follows in Phase 3.
3. Correct the verified factual recipes: gh checks fields and pending exit 8; status-aware GHAS checks; macOS grep -P; Node module interpretation; Python project-pin selection; early command failure hidden by later success; unknown versus missing paths; overgeneralized HTTP403; curl pipeline status; WebMCP return type; Supabase grants versus RLS, default privileges, and local-versus-remote application. A generic schema example must show intended allow/deny behavior, not postgres-only verification. Preserve project-specific public-data access and owner-only overrides.
4. Repair cc-rpi's local Drawio overlay quoting, editable-source retention, and XML contradiction. It is not one of the exported 12 skills. Record its ownership and keep its specialized exporter facts. Archy's function-security example is an adopter-specific case, not permission to edit Archy here.
5. Extract the actual local CI selection into `scripts/verify-local.sh`, invoked by CI and local completion. Preserve all existing checks; add new code checks as later phases introduce them. Replace the Linux-only inline link parser with a portable checker covering tracked product/docs files and explicit candidate artifacts. Test relative paths, anchors, fenced code, images, and targets absent from a clean candidate even when present in the author's workspace. Published Markdown links must resolve in the clean candidate/package; cite ignored local evidence by plain filename instead. Missing or zero enumerated inputs must not pass silently.
6. Preserve this plan, its phase directory, and `2026-09-05-cc-rpi-v2-notes.md` through explicit ignore exceptions. Keep current machine-specific research reports/inventories ignored; document the distinction between curated history and local evidence. New-project templates version plans/handoffs and curated research, with raw operational evidence governed by visibility. Do not bulk-stage ignored files.

Avoid a full rewrite of command bodies that Phase 2 immediately migrates. Complete factual corrections in canonical rules, domain skills and methodology here. Existing executable workflow instructions receive only the minimal urgent policy/safe-cleanup corrections needed to make this phase's active installation consistent; move their restructuring, names, adapters and remaining modernization into the single Phase 2 migration. The small safety overlap is deliberate because Phase 1 is independently accepted, even though no partial release is published.

## File targets

Primary: `templates/rules/{rpi-details,push-accountability,deployment-safety}.md`; `templates/commands/{implement,remediate,fix-ci,release,triage,update,detach}.md`; affected `templates/skills/{ci-workflow,deployment-safety,error-patterns,git-workflow,github-cli,macos-rules,python-rules,shell-tools,supabase,webmcp}/`; `templates/skills/error-patterns/references/error-catalog.md`; `templates/hooks/guard-bash.sh` if changed; `.claude/skills/drawio/`.

Consistency sweep: `patterns/`, relevant `methodology/`, root CLAUDE/AGENTS, `.claude/rules`, divergent commands/hooks, setup templates, README/GUIDE/CONTRIBUTING, CHANGELOG and `.claude/DIVERGENCE.md`. Keep stable rule numbers and existing retirement history.

Verification targets: `.github/workflows/{validate,coverage}.yml`, `scripts/verify-local.sh`, a portable link checker under `scripts/`, and focused tests under `tests/`. Do not invent an application build or typecheck command for this documentation/shell/Python repository.

## Executable contract

Write failing tests before changing executable behavior. Documentation corrections use real tool/help or disposable recipe checks; do not add tests that merely assert the replacement sentence exists.

```text
verify_local(required_checks):
    execute sequentially; capture each exit and tested identity
    missing prerequisite or empty expected inventory -> failure
    any failure or missing required result -> overall failure
    all required checks pass -> structured evidence plus success
```

Use a first command exiting 7 followed by a command exiting 0 as the regression oracle. Exercise git cleanup in disposable local repos containing dirty files, untracked files, unmerged commits, and a foreign worktree. All user sentinels must survive. Use stub remote executables for policy paths. No real remote command is required.

For Supabase examples, use a disposable local database with anon, owner, nonowner and service roles. Test intentional allowed and denied access and future-table exposure. Local success must not invoke a remote db command. Validate corrected shell/Node/Python examples against local runtimes; do not install a different grep merely to make the broken recipe pass.

## Acceptance and handoff

Automated: relevant regression/recipe checks, full existing CI-equivalent gate, safe link validation, syntax checks, count/version/drift invariants and contract self-tests pass. Coverage remains honestly labeled count-only until measured coverage is added for new Python modules. No remote reporting step runs locally.

Human review: confirm consistent owner policy, preserved TDD/fix-all/phase gates, accurate artifact handling, and no accidental weakening of project-specific release/data contracts. Save the correction inventory, test identity, and any unchanged harness-quirk candidates for Phase 5. Stop at phase acceptance; do not publish an intermediate release.

## Execution acceptance

- [x] Canonical policy, recipe and artifact corrections completed.
- [x] Independent compliance and three simplify lenses completed; findings repaired.
- [x] Full local gate: 10 checks and 31 unit tests passed.
- [x] Isolated PostgreSQL role recipe and cleanup sentinels passed.
- [x] Handoff preserved in `2026-09-05-cc-rpi-v2-notes.md`; continuation authorized.
