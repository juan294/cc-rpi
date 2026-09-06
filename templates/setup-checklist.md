# RPI Project Setup Checklist

Use this checklist for an explicitly requested new setup or adoption. Preserve
existing project knowledge and choose the native harnesses and installation
routes from actual requirements. The [lifecycle contract](skills/rpi-bootstrap/references/lifecycle-contract.md)
is the execution authority; this checklist does not authorize remote operations.

## Establish the project and scope

- [ ] Verify source and target paths, project purpose, stack, package manager,
  integration/production branches and deployment triggers.
- [ ] Use `rpi-bootstrap` for an empty project or `rpi-adopt` when existing
  instructions, settings, skills and custom ownership require reconciliation.
- [ ] Read current AGENTS.md, CLAUDE.md, native settings, custom extensions,
  ownership receipts and release runbooks before planning changes.
- [ ] Confirm Git and Python 3.11 or newer. Check the installed client versions
  against [compatibility evidence](../docs/compatibility.md).
- [ ] Record whether the product exposes an implemented or planned agent-facing
  surface. Select WebMCP/server-MCP guidance only when applicable.

## Select native routes and components

- [ ] Choose Claude Code, Codex or both, with one direct/plugin route per harness
  and scope. Diagnose existing registrations before adding duplicates.
- [ ] For direct installation, plan the four user-scope lifecycle skills
  separately from the project installation. Defaults are `~/.claude/skills/` and
  `~/.agents/skills/`, with user state under `~/.config/cc-rpi/installations/user`.
- [ ] For plugins, use the repository root as the Claude package and
  `generated/codex/` as the Codex package. Native managers own caches, updates,
  removal and trust. Do not copy or merge files inside those caches.
- [ ] Use direct installation when Claude needs conditional domain selection;
  the tested Claude plugin manager enables the whole package. Verify Codex's
  enabled modules through its actual native controls.
- [ ] Select the generally relevant shell, Git, multi-agent, deployment, CI,
  GitHub CLI, error-pattern and debugging domains. Include Python, macOS,
  Supabase and WebMCP modules only when applicable. The distribution manifest
  is the authoritative inventory; install complete directories and resources.
- [ ] Keep Claude native `/simplify` and the separate Codex `codex-simplify`
  helper. Avoid adding a project skill named `simplify` that shadows the native
  workflow.

## Plan, apply, check and recover

- [ ] Resolve the local source from the checkout or actual native metadata.
  Codex packages carry their source under `runtime/`; direct installations use
  their recorded local source receipt. Do not guess a personal checkout path.
- [ ] Generate an explicit engine `plan` with source, target, harness, route,
  action and task-owned `--output` path. Use `install` for setup, `update` for
  reconciliation and `detach` for proven-owned removal.
- [ ] Read the concrete plan: component selection, source identity, file/block/key
  changes, conflicts, instruction budgets and recovery paths. `conflict` blocks
  the selected operation set; `noop` requires no apply.
- [ ] Review native permission/hook changes separately. The exact
  `--allow-capabilities` component selections permit lifecycle setup changes;
  they do not grant native tool permission or user consent for publication.
- [ ] Apply the reviewed plan within existing authorization, then run engine
  `check` and `diagnose` with the explicit source/target and selected route.
  Preserve nonzero statuses and missing-evidence diagnostics.
- [ ] Retain `.rpi/manifest.json`, nonsecret baseline bytes and transaction
  journals. Resume or use `rollback --journal` for interrupted transactions;
  concurrent edits must cause reconciliation rather than forced restoration.
- [ ] For v1 migration, supply an immutable local `--legacy-base` only when its
  provenance and rendering inputs are known. Legacy names and sync metadata
  alone do not prove ownership. Follow the [migration guide](../docs/migrations/v2.md).
- [ ] Confirm detach preserves edited/unknown content, project facts, research,
  plans, decisions, local extensions and independent user/plugin installations.

## Shared project intelligence

- [ ] Keep verified project purpose, architecture, exact verification commands,
  branch topology, owner constraints and release routing in AGENTS.md.
- [ ] Make CLAUDE.md import AGENTS.md and contain only Claude-specific additions.
  Avoid reverse imports and duplicate universal instruction bodies.
- [ ] Preserve managed shared RPI blocks and the conditional rule map. Claude
  uses native path rules; Codex follows the root task/path map to full installed
  rule resources. Confirm rules are reachable from actual root and nested cwd.
- [ ] Keep domain details in selected skills/resources. Read controlling
  contracts completely; reuse valid implementation reads. Do not impose a
  universal instruction-slot quota or context-percentage law.
- [ ] Preserve project-owned extensions and unrelated settings. Shared project
  configuration is committed; personal/native authentication and private values
  stay in their supported local stores. Do not add broad Git/shell allowances
  merely to avoid prompts.
- [ ] Leave model/effort overrides absent by default. Use [optional native
  profiles](../docs/model-profiles.md) only as explicit owner choices; do not
  write global defaults, silently change a parent pane or promise restoration.
- [ ] Keep Agent Teams and schedules opt-in. A narrow task may stay with the
  parent; use bounded independent assignments when useful, with at most three
  simultaneous implementers and lower resource limits when needed.

## Verify actual native behavior

- [ ] Confirm native skill discovery and bundled resource access. Direct Claude
  workflows use `/rpi-research`; plugin Claude workflows use
  `/cc-rpi:rpi-research`. Codex direct skills use `$rpi-research`; choose the
  `cc-rpi:rpi-research` selector for its plugin route.
- [ ] Use `rpi-plan` and `rpi-status`; native `/plan` and `/status` are distinct.
  Legacy aliases are explicit rename notices, not native forwarding.
- [ ] Inspect hook registration, current source hash, native trust and observed
  execution separately. Configured or copied hooks are not guaranteed to run.
  Supported native permission boundaries retain approval authority.
- [ ] Keep guarded operations blocked when their required enforcement boundary
  is unavailable. Do not disable guards or fabricate approval receipts.
- [ ] Confirm malformed events and missing prerequisites produce the documented
  `BLOCKED / WHY / FIX` behavior at the actual supported boundary. Source-level
  fixtures alone do not prove native execution.

## Local verification and publication

- [ ] Declare the project's complete CI selection in `.rpi/policy.json` with
  unique check names and literal argv arrays, plus its `verification_command`.
  Include all applicable tests, measured coverage, typechecks, lint and builds.
- [ ] Run the installed `.rpi/scripts/rpi-verify.py` or documented wrapper locally.
  Its receipt must match the current candidate, runtime and complete check list.
  Required skipped/failed checks block acceptance; do not invent coverage values.
- [ ] Configure and verify appropriate local pre-commit checks. Exercise failures
  with local fixtures rather than a deliberately failing remote push.
- [ ] Preserve project release obligations, including any stricter adopter
  maneuver validator. Adapt [the release playbook](e2e-pro-playbook-template.md):
  truthful Wave A always; structural waves by actual risk. Exercise an existing
  authorized immutable candidate for exploratory release checks.
- [ ] Keep implementation branches/worktrees local. Integrate completed work
  locally, inspect hosted triggers and publish completed integration once only
  within authorization. Never create Vercel Previews or hosted debugging loops.
- [ ] Treat production, remote settings and new hosted schedules as separate
  authorization scopes. Observe the exact authorized published SHA and checks.

## Project documentation and adaptation

- [ ] Give README a project-specific title, concise purpose, accurate badges,
  setup requirements, verification commands and deployment/release references.
- [ ] Version curated `docs/research/`, `docs/plans/`, phase files, decisions and
  durable handoffs. Keep raw inventory, credentials and transient recovery local.
  Operational report tracking follows repository visibility and Rule #70.
- [ ] For libraries, include package/export checks and consumer integration tests.
  For CLIs, exercise stdin/stdout/stderr and exit codes. For Python, use the
  project's pinned runtime and actual pytest/typecheck/lint commands.
- [ ] For monorepos, record package ownership and cross-package checks before
  dividing work. For web apps, cover UI/accessibility and deployment behavior.
  For documentation/static sites, include build and link checks.
- [ ] For agent-facing products, use `rpi-tool-design` before the first related
  plan and seed evals from its transcripts. Read the selected WebMCP resource for
  current browser/API requirements rather than copying a stale global recipe.

## Updates and optional schedules

- [ ] Update from an explicitly selected local source through `rpi-update` and
  its plan/apply/check lifecycle. Source acquisition and native plugin updates
  are separate operations; never infer healthy installed bytes from a matching
  version alone.
- [ ] Do not create a fleet rollout or schedule by default. An opted-in scheduled
  launcher must bind source/target, use supported native invocation and existing
  permissions, preserve conflict/recovery evidence, and report actual engine
  check results. It must not publish, deploy or silently update global installs.
- [ ] Verify the actual scheduler environment, authentication, executable paths
  and resource limits if a schedule is requested. Historical launchd workarounds
  are not universal requirements; diagnose the observed failure.
- [ ] End setup with a durable handoff: chosen routes/components, preserved
  customizations, checks, remaining conflicts and next authorized phase.
