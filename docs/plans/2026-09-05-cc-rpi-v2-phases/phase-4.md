# Phase 4: models, enforcement, and diagnostics

[Main plan](../2026-09-05-cc-rpi-v2.md). Depends on Phase 3. Not batch-eligible. Outcome: the blueprint respects the owner's pane choice and reports which native protections actually work.

## Model contract

Remove remaining provider-generation pins from workflow bodies, methodology, guides and helper assignments. Agent names describe responsibilities. Shared content cannot switch a parent model. Defaults inherit the active model and effort; in native fields where inheritance is represented by omission, omit the field rather than inventing `effort: inherit`.

Document the simple Claude launch pattern `claude --model best --effort high` and the owner's implementation pane choice using supported family selectors. Do not put `best` in a subagent definition unless the supported schema explicitly accepts it; inheritance avoids that dependency. Test override precedence against the actual tool schema and client, including explicit user selection. Skills must not silently raise effort or replace a deliberately selected model.

Add an optional, explicit `economy` adapter policy alongside the default `inherit` policy. It can lower cost for mechanical status summaries, formatting, or bounded locator helpers. It must not classify architectural research, validation judgments, or stateful diagnosis as mechanical merely because of a workflow name. Claude rendering may emit supported skill `model`/`effort` fields for that invocation, and supported subagent fields for the helper; subsequent parent turns retain the owner's session choice. A locator may use the `haiku` family when available and adequate; emit `low` effort only if that model/client supports it. Do not assume every small model exposes effort. Explicit per-request user selection takes precedence over the configured economy policy. Verify native precedence; if frontmatter cannot respect an override, provide an explicit alternative entry/profile instead of silently overriding the user. [Claude skills](https://code.claude.com/docs/en/skills) and [subagent configuration](https://code.claude.com/docs/en/sub-agents) define the separate native controls.

Document optional user-local Codex research/implementation profiles and their supported native launch syntax. Resolve model IDs/effort choices from the documented App Server catalog and installed configuration, with a dated central mapping when needed. Codex economy selection uses only supported session/profile or helper controls; Claude frontmatter is not a Codex model control. Where no equivalent exists, report the limitation and inherit. The installer never rewrites global profiles automatically. Catalog defaults are not a universal quality ranking or proof of entitlement; do not infer identity from model prose, terminal titles, or the newest rollout file.

Use four diagnostic fields: requested role, requested model/effort source, resolved model/effort where exposed, and evidence source/client version. Distinguish unavailable identity from an actual match. Offline catalog access leaves an explicit user selection intact; it does not invent a fallback model. No launcher, background resolver service, automatic profile updater, or optimization algorithm is built.

## Native policy and hook adapters

Render Claude's native `permissions.deny` and `permissions.ask` rules as the structural permission boundary in project settings. Ask rules cover publication/deployment entry points, including `Bash(git push:*)` and `Bash(vercel deploy:*)`; deny rules cover only unconditionally forbidden forms that can be matched accurately. A blanket deny on every deployment or push would also forbid an authorized production release or completed integration push: deny takes precedence over ask/allow, so it cannot carry those exceptions. State-dependent Preview defaults, target branches, local verification and tag rules belong in the supplemental hook. Remove blueprint-owned blanket git/gh allow entries that teach unrestricted remote execution; preserve unrelated user settings and report conflicts. Verify the actual shell/tool matching, including the bare Vercel deployment form and supported wrappers, rather than assuming these two example patterns are complete. [Claude permission rules](https://code.claude.com/docs/en/permissions) document precedence and matching.

Implement the smallest shared `templates/scripts/rpi-policy.py` checks needed by supported Claude/Codex pre-action adapters. Keep `guard-bash.sh` as a compatible wrapper where appropriate. Preserve current dirty-pull, tag and protected-branch protections, and add the owner working-branch/Preview boundaries for recognized executable forms. Explicitly document the supported command shapes and reject or classify ambiguous forms conservatively. A substring matcher is not a complete shell security boundary. Codex gets its own verified permission adapter; it never receives Claude permission syntax as if it were native.

Use each harness's actual event schema, tool names, working directory semantics, output contract and trust mechanism. Unit-test native JSON events independently. Missing prerequisites or malformed events on a policy-sensitive operation must produce an actionable blocked/unsupported result rather than silent permission. Keep ordinary non-policy tools fast and unaffected. Do not regard a repository flag, model-written receipt, `--follow-tags`, or explicit skill invocation as proof of user authorization.

Record fail-closed policy handling as an intentional change from the current `guard-bash.sh` fail-open header, in that header, `.claude/DIVERGENCE.md`, migration notes and CHANGELOG. Prefer the already-required Python runtime for event parsing so the guard does not acquire an unnecessary jq dependency. Installation preflight checks every remaining prerequisite. A runtime failure emits `BLOCKED / WHY / FIX` with the exact missing dependency or malformed input and a runnable repair for the supported platform. If a guarded shell event cannot be classified because it is malformed, block that event; do not silently permit it or claim unrelated tools are blocked. Optional telemetry failures remain non-blocking and distinguishable from policy evaluation failures.

Separate structurally forbidden actions from permitted actions requiring authorization. Feature-branch publication and Preview creation remain denied. A completed integration/named-tag action can pass the structural hook only for the documented target with its required local evidence; user authorization belongs to the native trusted permission boundary and active owner instruction, not to a shell-text detector. Test both the authorized allowed path and unapproved denied path. If a supported client cannot supply a trustworthy approval boundary for remote automation, keep that automation blocked and provide the exact owner-executed publication commands at release review; do not ask the agent to forge an approval receipt or disable the guard.

Permission/config changes are a separate setup diff, applied only within existing authorization and native trust. Preserve user/project hooks, deny rules and ordering. Evaluate the native `PermissionRequest` event when an adapter needs to handle an approval request; never have it manufacture consent or auto-approve from model-writable state. Copying Claude settings into Codex is prohibited. PostToolUse may report/edit-quality feedback after a write; it is not prevention of that write. The Markdown check continues to respect project markdownlint configuration and the no-emoji policy without forcing unrelated prose reflow.

Remove unconditional `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` from the new-install settings template. Ordinary supported subagents are the default. Preserve a user's existing explicit Agent Teams opt-in through ownership-aware migration; document it as an optional capability rather than enabling an experimental mode to satisfy the workflow.

## Diagnostics and telemetry

Extend `rpi-status` with an environment/installation report backed by a read-only engine operation. Report harness/version; expected and discovered skill roots; duplicate/legacy entries; instruction import cycles; source/install drift; missing resources; actual project topology; model/effort provenance; hooks registered versus trusted versus observed; and verification prerequisites. Do not read/log credentials or full settings. A missing telemetry stream is “unobserved,” not zero violations.

Retain the portable findings validator and contract metrics. Native adapters emit the documented event shape where appropriate, with unavailable coverage explicit. Claude's statusline/effort events and instruction-loading events are optional diagnostic sources; do not rewrite the owner's global statusline or require a model-ID cache to run RPI. Local scheduling stays the default. `/goal`, advisor, dynamic workflows and cloud routines are documented optional capabilities, not implicit new services.

In Claude session Bash, record `CLAUDE_EFFORT` as an observed effort value when present. There is no corresponding generic model-ID environment assumption: report observed model identity as unavailable unless a supported session-bound native event/statusline source provides it. Keep launch/config requests separate from resolved observations. A statusline cache must identify its session and freshness; an unrelated pane's cache cannot identify this pane. Missing effort data also remains unavailable rather than defaulting to a guessed level. Test observations during an economy override as well as ordinary inherited execution. [Claude hook effort fields](https://code.claude.com/docs/en/hooks)

## Tests and acceptance

TDD: supported model metadata, optional economy on/off, unsupported effort, explicit override precedence, parent restoration, offline catalog, unknown/stale identity, duplicate skill registration, missing tool dependency, hook field mismatch, and absent telemetry. Policy fixtures use fake git/gh/deployment tools and execution sentinels: allowed local work executes; denied feature push/Preview/protected release does not. Cover `git -C`, refspecs, implicit upstreams, chains, wrappers, flags, literal non-command text and malformed events. Verify native ask/deny precedence separately from stateful hook denials, including the allowed authorized release path. Test Agent Teams defaults and preservation of user opt-ins. Hook tests must identify the enforcing boundary accurately.

Use direct event fixtures first; Phase 6 supplies actual registration/trust/invocation evidence. Track changed Python modules with measured line/branch coverage and require tests for every ownership/destructive/authorization decision branch. Coverage percentages must come from coverage tooling, not self-test message counts.

Automated acceptance: model/policy/telemetry fixtures, nonempty validator coverage and full local gate pass. Human review: inspect the capability table and compare one allowed and denied result per adapter. No unsupported guarantee is labeled enforced. Handoff exact client schema/version assumptions and the remaining live acceptance cases to Phase 6.

## Implementation handoff

- Inherited model selection and explicit economy/profile contracts have native
  schema/precedence evidence and 20 focused model tests. Global owner profiles
  remain untouched. Four-field observations distinguish requested and resolved
  values, current-process effort and session-bound evidence.
- Shared fail-closed policy, Claude settings, Codex hooks/native prompt rules and
  entry-level capability reconciliation are implemented. Runtime requires Python
  3.11 or newer; Codex remote automation is scoped to tested version 0.153.4.
  Native trust and actual accepted/declined enforcement remain Phase 6 gates.
- Publication binds one explicit integration ref or annotated version tag to
  current complete project verification. Bounded release creation additionally
  binds its repository, tag and local notes. Project check declarations and
  receipts do not grant consent. Unsupported remote forms remain blocked.
- Read-only diagnostics preserve project data, report ownership/source drift,
  distinguish registration/trust/observation, and match native instruction and
  skill discovery bounds. Legacy broad allows remain unowned review findings
  unless exact prior provenance supports removal.
- Measured policy coverage reached 99.19% lines and 98.98% branches; ownership
  configuration and package modules reached 100% for both. Remaining defensive
  and copied-runtime coverage paths are explicitly classified in local evidence.
  The new recovery tests found and repaired malformed journal progress; cleanup
  also repaired duplicate native-entry checking and bounded discovery work.
- Three independent simplify passes completed: shared helpers satisfy reuse;
  quality and efficiency findings received focused fixes and regression tests.
  Authoritative acceptance is `bash scripts/verify-local.sh`, with every exit,
  candidate/runtime identity and measured result in `.rpi/local/verification.json`.
  The final Phase 4 log is `.rpi/local/phase-4-gates.log`.
- Phase 5 starts from these finalized workflow/runtime contracts. Phase 6 must
  exercise actual interactive invocation, trusted allowed/denied hooks, native
  approval, economy observations and the local cross-platform adopter matrix.
