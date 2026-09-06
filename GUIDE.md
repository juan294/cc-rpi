# The cc-rpi Guide

cc-rpi provides one shared Research-Plan-Implement methodology through native
Claude Code and Codex skills. Canonical workflows and resources are authored once;
adapters generate complete packages for each client. Both clients can bootstrap,
adopt, update and detach projects through the same ownership-aware engine.

## The workflow

Research describes what exists. Planning defines the intended change and its
success criteria. Implementation follows TDD, independent review, repair,
simplify and local verification. Validation compares the result with the approved
scope and the actual tested candidate. Use `rpi-assess` separately when you want
an evaluation or recommendations.

Review research and plans carefully: mistaken assumptions propagate into later
work. Separate phase conversations and durable handoffs keep scope, decisions
and evidence retrievable. Within a long phase, use native compaction as needed;
there is no universal instruction-slot or context-utilization target.

Phase acceptance remains explicit. If your request authorizes all phases, the
agent continues after completing each phase's checks without asking the same
permission again. A new architectural decision, destructive scope or publication
requirement still needs its actual authorization. A supplied release version or
already-authorized documentation update should not trigger a duplicate question.

## Installation

Installation requires Git and Python 3.11 or newer, plus the native clients you
choose to use. See [compatibility evidence](docs/compatibility.md) for tested
versions and limitations. The engine itself uses the Python standard library;
contributor verification has additional pinned dependencies in
[CONTRIBUTING.md](CONTRIBUTING.md).

Keep a verified local source checkout or supported native package. From a source
checkout, inspect the source and available installation options:

```bash
bash scripts/install.sh --check
bash scripts/install.sh --help
```

For a chosen direct user-scope installation, generate a task-owned local plan:

```bash
bash scripts/install.sh --scope user --harness both --route direct \
  --output "$PWD/.rpi/local/user-install.json"
```

Read the exact plan and resolve conflicts before applying it within your setup
request. Then inspect the selected installation:

```bash
bash scripts/install.sh --apply "$PWD/.rpi/local/user-install.json"
bash scripts/install.sh --check --scope user --harness both --route direct
```

Use `--harness claude` or `--harness codex` for one client. Direct user scope
installs the four lifecycle skills in `~/.claude/skills/` and `~/.agents/skills/`,
with separate state under `~/.config/cc-rpi/installations/user`. Explicit root
options are available. Project operations never silently update these roots.
`--check` without an installation destination checks only the source package.

### Direct and plugin routes

Direct installation supports a selected set of domain modules. Project scope owns
its remaining workflows, domain skills and managed project configuration. Install
whole selected skill directories, including scripts and references; never copy
only SKILL.md or invent resource paths.

Native plugins provide another route. Claude's package root is the repository;
Codex's self-contained package is `generated/codex/`, including its `runtime/`
source closure. Native managers own plugin caches, installation, update, removal
and trust. The project lifecycle engine never merges or edits those caches.

Use one registration route per harness and scope. The tested Claude plugin manager
controls the whole package, so choose direct installation when conditional domain
selection is required. Codex supports native module selection on the tested
client. Inspect actual native discovery and enabled modules; file presence alone
is not proof that a skill or hook is active.

| Route | Claude research invocation | Codex research selection |
| --- | --- | --- |
| Direct | `/rpi-research` | `$rpi-research` |
| Plugin | `/cc-rpi:rpi-research` | `cc-rpi:rpi-research` in the native skill selector |

The corresponding names apply to the other `rpi-*` workflows. Claude retains
native `/simplify`; Codex receives `codex-simplify` through its selected route.
Native `/plan` and `/status` are different from `rpi-plan` and `rpi-status`.
Managed colliding aliases are discontinued. Retained legacy aliases are
explicit-only rename notices, not forwarding commands; custom aliases remain
owner-owned.

### Bootstrap or adopt a project

Invoke `rpi-bootstrap` for an empty project or `rpi-adopt` for existing code and
configuration, using the selected client's native syntax. Either client can run
these workflows. They resolve the source and target, inventory ownership, select
harnesses/domains and generate an explicit project installation plan.

Inspect planned file, instruction-block and settings-key changes, source/target
identity, conflicts, budgets and recovery paths. Apply safe reviewed work within
existing authorization. Native permissions and hooks require explicit capability
setup selection; copying configuration is not native trust or user consent.

Shared project intelligence belongs in AGENTS.md. CLAUDE.md imports it and adds
Claude-specific guidance without a reverse import. Universal policy is managed
once; conditional rules remain reachable through native Claude path rules and
Codex's explicit root task/path map. Preserve project-specific rules, generated
vendor blocks, local skills and stricter release charters.

See the [setup checklist](templates/setup-checklist.md) and
[lifecycle contract](templates/skills/rpi-bootstrap/references/lifecycle-contract.md)
for exact source resolution and engine commands.

## Workflow reference

| Workflow | Purpose |
| --- | --- |
| `rpi-bootstrap` | Plan and apply a new project setup with explicit ownership and selected native components. |
| `rpi-adopt` | Audit existing configuration and reconcile authorized gaps while preserving custom content. |
| `rpi-update` | Compare recorded baselines, local bytes and an explicitly selected local source; apply safe owned updates and report conflicts. |
| `rpi-detach` | Remove proven-owned unchanged components while retaining edited/unknown content and project work products. |
| `rpi-research` | Describe the code as written, with source references and evidence. |
| `rpi-assess` | Evaluate requested concerns and alternatives separately from descriptive research. |
| `rpi-plan` | Create a phased implementation specification with success criteria and tests. |
| `rpi-implement` | Complete authorized phases through TDD, independent review, repair, simplify and local verification. |
| `rpi-validate` | Compare the actual implementation and evidence with the approved plan. |
| `rpi-brainstorm` | Clarify a vague or greenfield goal into a design brief. |
| `rpi-tool-design` | Design an agent-facing tool contract and seed evals from concrete role-play. |
| `rpi-describe-pr` | Prepare a reviewable PR description without implicitly publishing it. |
| `rpi-pre-launch` | Covers 8 core audit domains plus applicable agent surfaces and produces a validated report with stable finding IDs. |
| `rpi-remediate` | Resolve confirmed actionable findings and document evidence-backed rejections or architectural decisions. |
| `rpi-triage` | Discover reports and failures with durable scan checkpoints, inspect applicable alerts, and complete authorized local fixes. |
| `rpi-status` | Diagnose project state, source/installation drift, native discovery, trust and evidence limitations. |
| `rpi-fix-ci` | Reproduce a failed CI selection locally, repair it and run the complete applicable gate. |
| `rpi-update-docs` | Complete authorized documentation, diagram, version and inline documentation updates. |
| `rpi-explore-release` | Exercise an existing authorized immutable candidate using the project's required exploratory charters; never tags. |
| `rpi-release` | Prepare the supplied or selected version, notes and release evidence, then perform only the authorized publication actions. |

An empty project can begin with brainstorming or planning because there is no code
to investigate yet. For existing code, research the relevant behavior before
planning changes. Preserve curated research, approved plans, phase files,
decisions and handoffs in version control. Raw machine inventories and transient
recovery evidence remain local; operational report tracking follows visibility.

## Implementation and audit discipline

A narrow task may stay with the parent. Delegate useful independent questions or
owned file sets with an objective, allowed actions/files, evidence contract,
resource constraints and completion condition. Group failing tests by likely
root cause rather than assigning one agent per test. At most three implementers
may work simultaneously, with fewer when slots or resources require it.

Await every required result. Missing, failed or stale results are gaps, including
an absent independent review. For coordinated work,
[structured dispatch validation](templates/references/dispatch.md) checks the
handoff's declared scope and completion; it does not authenticate evidence or
create permission. Revalidate actual repository state when resuming.

Standalone simplify reruns checks invalidated by its changes. A parent-owned pass
returns exact changed files and invalidated checks for the parent's final gate.
Use native Claude `/simplify` or Codex `codex-simplify` without silently changing
models. Native batch/team mechanics vary; use them only when they can preserve
local work, ownership and the current approved phase. Otherwise use bounded
ordinary assignments. Agent Teams is opt-in, not an installation default.

Before release, `rpi-pre-launch` covers 8 core audit domains: architecture (AR), frontend (FE), backend
(BE), performance (PE), operations (DO), security (SE), QA and UX. Agent surfaces
(AS) additionally apply when implemented tools are exposed to agents. One
investigator can cover several compatible domains; eight domains do not require
eight model instances. Absence of a frontend or service is an inspected fact,
not permission to silently omit a core domain.

Findings retain the required ID grammar, fields, regression-risk reasoning and
`file:line` evidence. Coverage gaps block audit acceptance. Remediation resolves
all confirmed actionable findings within authorized scope; severity/time horizon
order work rather than exempting low or strategic findings. False positives need
evidence. Architectural decisions or explicitly deferred scope receive local
owner-reviewed dispositions, not invented completion or automatic external issues.

## Verification, diagnostics and release

Declare the project's actual complete CI selection in `.rpi/policy.json` and run
its installed `.rpi/scripts/rpi-verify.py` or documented wrapper. This repository
uses `bash scripts/verify-local.sh`. Checks run sequentially, retain every exit,
and bind results to candidate bytes and runtime identity. Required failures or
skips block acceptance; changed inputs cannot reuse an old passing receipt.

Read-only engine `diagnose` and `rpi-status` distinguish configured, discovered,
trusted and observed states. Missing native observations stay unavailable. A hook
can exist yet be skipped or untrusted. Supported native permissions retain
approval authority; guarded remote automation stays blocked when the necessary
boundary is unavailable. See [compatibility](docs/compatibility.md) and
[migration](docs/migrations/v2.md), including the deliberate fail-closed change.

The pre-release sequence is `rpi-pre-launch`, `rpi-remediate`, `rpi-update-docs`,
then `rpi-release`. Adapt the [E2E Pro playbook](templates/e2e-pro-playbook-template.md)
to the project's actual release runbook. Wave A requires truthful exact-candidate
evidence; structural waves depend on risk. Preserve existing stricter adopter
requirements, including eight-maneuver validators. An existing authorized
immutable candidate can supply exploratory evidence; do not create a Vercel
Preview to satisfy a gate.

Keep working branches/worktrees local, finish all applicable local checks and
integrate completed work locally. Inspect hosted triggers before one authorized
completed integration push. Never use hosted CI as a debugging loop. Production,
publication and new hosted schedules retain their separate authorization scopes.
Observe the exact published SHA and required workflow/event/check set.

## Model selection

Workflows inherit the owner's active pane model and effort. Optional
[native profiles](docs/model-profiles.md) are explicit session choices. The
installer does not rewrite global defaults, start a model resolver or silently
switch a parent to an economy model. Record requested role, requested model/effort
and source, resolved values where exposed, and evidence source/client version.
An alias or configuration value is a request, not an observed model identity.

For an explicitly selected Claude research/planning launch, the documented
`claude --model best --effort high` uses native controls. Keep the owner's chosen
implementation pane selection. Mechanical economy tasks use a separate selected
session/profile; native overrides can persist or outrank other settings, so no
automatic parent restoration is promised.

## Updates, detach and optional schedules

An update compares current installed bytes even when the source revision has not
changed, so missing resources are still detected. `ready`, `noop` and `conflict`
plans are distinct. Preserve `.rpi/manifest.json`, nonsecret baselines and durable
journals; use the recorded rollback path for interrupted transactions and retain
concurrent user edits. Detach removes only unchanged proven ownership and leaves
research, plans, decisions, custom files and separate user/plugin installations.

Schedules require explicit setup and resource authorization. The optional
`templates/scripts/cc-rpi-update-agent.sh` launcher requires `RPI_UPDATE_ENABLED=1`,
absolute `CC_RPI_PATH` and `RPI_PROJECT_ROOT`, and selected `RPI_HARNESS` and
`RPI_ROUTE`. Direct mode also requires `RPI_UPDATE_SKILL_DIR` from actual user
skill discovery. It validates source/resources, uses the matching native workflow
without adding a duplicate plugin in direct mode, and keeps native permissions.
Required unavailable permissions are denied rather than bypassed.

The launcher checks installation state after the native attempt and preserves
both exit statuses in unique ignored `.rpi/local/update-runs/` reports. It refuses
unignored output paths, performs no separate inference auth probe and does not
blindly retry a partial update. It neither pulls source nor updates global user
skills, native caches, models or schedules. Plugin manager updates remain separate.
Verify the actual scheduler environment/authentication and keep local recovery
records; do not assume a universal launchd file-descriptor requirement.

## Further reading

The index contains 92 operational rules with permanent IDs. The distribution
manifest owns native component counts.

| Topic | Reference |
| --- | --- |
| Methodology and reading order | [methodology/README.md](methodology/README.md) |
| Context and durable handoffs | [context engineering](methodology/context-engineering.md) |
| Assignment design | [agent design](methodology/agent-design.md) |
| Testing and release evidence | [testing](methodology/testing.md) |
| Publication policy | [push accountability](methodology/push-accountability.md) |
| Model choices and costs | [cost monitoring](methodology/cost-monitoring.md) |
| 64 documented errors | [error catalog](patterns/agent-errors.md) |
| Index of 92 rules | [quick reference](patterns/quick-reference.md) |
| Current component inventory | [distribution manifest](templates/distribution.json) |
| Project adaptation | [setup checklist](templates/setup-checklist.md) |
| Worked examples | [examples](examples/README.md) |

The methodology draws on HumanLayer's opencode-rpi and ACE-FCA framework, adapted
to native Claude Code and Codex workflows through shared authored sources.
