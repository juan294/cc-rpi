---
name: "rpi-bootstrap"
description: "Set up a new project with shared RPI instructions, native workflows and relevant domain rules through an ownership-aware local installation plan."
---

# Bootstrap a New Project

Set up the project requested by the user with shared RPI intelligence and native
workflow entry points. Reuse information already supplied; ask only for material
missing decisions such as project identity, stack, target path and intended users.

Read [the lifecycle contract](references/lifecycle-contract.md) completely.
Resolve the installed package/source and target project from actual metadata and
the request; do not assume the current directory is the intended target. Use the
ownership-aware engine's explicit source/target plan/apply interface. Skill
invocation or tool visibility does not grant extra authority.

## Discover and adapt

1. Establish project name, description, type (web, library, CLI, monorepo, Python,
   static or other), stack, package manager, tests, git topology and deployment
   constraints. If files already exist, inventory them and use `rpi-adopt` when
   existing ownership/configuration needs reconciliation.
2. Establish whether the product exposes tools to agents, including WebMCP or
   server MCP, independent of project type. Preserve an explicit decision that
   the surface is absent or planned.
3. Inspect the resolved source manifest, shared instruction template and relevant
   rules. Shared project facts belong in AGENTS.md; CLAUDE.md imports AGENTS.md
   and adds only Claude-specific guidance. Never introduce a reverse import.
4. Choose supported harnesses and one distribution route per harness. Direct
   installs place the four lifecycle workflows at user scope and the remaining
   workflows at project scope; project installation does not own the shared
   user installation. Plugins own immutable package skills. Do not duplicate
   registrations across user/project or plugin/direct routes.
5. Select the eight generally relevant domains: shell-tools, git-workflow,
   multi-agent, deployment-safety, ci-workflow, github-cli, error-patterns and
   systematic-debugging. Include python-rules, macos-rules, supabase and webmcp
   only when their project/environment conditions apply. Record selection.
6. Preserve universal RPI and remote-budget constraints in managed shared
   instructions. Map conditional deployment, database, testing and WebMCP rules
   to actual paths/tasks. Claude uses native path rules; Codex receives the short
   root map plus installed full rule resources. Do not invent directory globs.

## Install and verify

1. Generate the engine's local `install` plan for the chosen source, target,
   harnesses, route and domain selection. Inspect changes, ownership conflicts,
   instruction-byte budgets, settings keys and recovery locations before apply.
2. Apply the reviewed safe plan within the setup authorization already provided.
   Preserve user files/settings and unknown ownership. Resolve conflicts before
   dependent changes; never overwrite custom content to complete setup.
3. Create curated `docs/research/`, `docs/plans/`, `docs/decisions/` and handoff
   locations as appropriate. Version research, plans and decisions. Raw machine
   inventories and transient evidence stay local; public repositories ignore
   operational reports/logs, while private/internal tracking follows Rule #70.
4. Adapt [the release playbook](references/e2e-pro-playbook.md) into the project's
   release documentation with verified Project Adaptation Profile values. Adopt
   Wave A's truthful release gate; select structural Waves C-H by risk, recording
   inapplicable sections and reasons. `rpi-explore-release` supplies Wave B when
   an existing authorized immutable candidate can be exercised; do not create a
   Preview to satisfy it.
5. Prepare the README and applicable local checks/hooks from actual project
   facts. Remote repository settings, production, new hosted schedules and
   publication remain separately authorized operations. Do not enable optional
   agent teams or schedules merely because the blueprint supports them.
6. Run engine diagnostics and actual applicable local verification. Verify native
   registrations and bundled resources, unique scope/route registration, preserved
   local extensions, settings and the shared instruction import direction.

## Completion

Save a durable setup handoff with project facts, chosen route/harnesses, component
selection, skipped features, git/deployment constraints, verification and remaining
conflicts. Update available project/session memory without storing secrets. Keep
working branches local. Report the concrete setup and next step: an empty project
can begin with `rpi-plan`; existing code may need `rpi-research`. Stop after setup
unless another workflow was explicitly authorized.
