# Local resource lifecycle

The portable policy lives in [the resource-lifecycle rule](../templates/rules/resource-lifecycle.md). It applies to local stacks, database tests and task services, including projects without Dockerfiles. Keep policy in the blueprint, application commands in the project and machine-wide maintenance with the host owner.

| Layer | Responsibility |
| --- | --- |
| cc-rpi | Distribute the same ownership, completion and preservation requirements to Claude and Codex. |
| Project | Implement the commands that allocate and finish its resources; declare protected data and lifecycle exceptions. |
| Host | Inventory all projects, report unresolved resources and invoke approved ownership-aware cleanup. |
| Container runtime | Apply memory, logging and cache limits; it cannot infer whether retained data is disposable. |

## Project adaptation

Link an existing resource runbook from AGENTS.md, or document verified project facts in `docs/development/resource-lifecycle.md`. Record exact start, test, inspect and finish commands; daemon/project identity and port allocation; protected/shared/recovery resources; ownership receipt location; consumer coordination; and failure retention. State when host maintenance or executable cleanup is absent. This document is project-owned and must survive blueprint updates.

Prefer a one-shot entry point for temporary checks. It should create an isolated environment, run the task, preserve its result and dispose of approved task resources. A reusable development stack has an explicit finish operation instead. Failed tasks can retain diagnostics without leaving unused services running. Do not copy a working project's entire lifecycle implementation into the blueprint before multiple adopters establish a common executable need.

Use the existing task receipt, locking and maintenance mechanisms where they suffice. Small commands do not need a new registry, scheduler or controller merely to satisfy the rule. Multi-agent/shared environments do need enough ownership and consumer evidence to prevent another task from being stopped or erased.

## Rollout and acceptance

Use the existing ownership-aware `rpi-update` plan/apply/check workflow. Reconcile each selected installation even when a source version is unchanged, but preserve conflicts and project-owned content. A requested fleet refresh is not permission to overwrite local customizations, install schedules or delete Docker resources.

Distinguish instruction delivery from runtime adoption. A healthy installation proves the rules and mappings are present. Runtime acceptance requires an exercised project lifecycle: success leaves no owned disposable resources; failure/interruption has a visible recovery disposition; repeated finish is safe; and concurrent consumers, replaced identities, persistent data and recovery holds remain protected. Do not report a project as automatically cleaned merely because it received the rule.

For interrupted tasks, extend an existing authorized host maintenance service. Inventory containers, networks and volumes, retain unknown resources, and surface failures and review reminders through the existing reporting channel. Automatic disposal is limited to previously authorized disposable resources after fresh ownership and consumer checks. The blueprint does not install or activate such a service.
