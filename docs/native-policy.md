# Native policy boundary

The shared pre-action parser is supplemental. It returns exit 2 with nonempty
`BLOCKED / WHY / FIX` stderr on a forbidden or unsupported guarded event. A
structural pass returns exit 0 without a native allow decision. Repository
settings, verification reports and explicit skill invocation never prove consent.

Claude registers `PreToolUse` for `Bash`, and uses native `permissions.ask` and
`permissions.deny` entries. Remote structural passage accepts the known `default`,
`acceptEdits` and `plan` modes; missing, unknown, `dontAsk` and bypass modes remain
blocked. Native deny precedence and the user's approval remain authoritative.
Codex uses its own `hooks.json` and execpolicy rules. The pinned 0.153.4 contract
maps several native policies to `permission_mode: default`; an explicit prompt
rule becomes a native approval request or a denial when prompting is disabled.
It never becomes consent. Codex's hook `ask` response is unsupported and must not
be used as an approval mechanism. Other Codex versions remain unsupported for
remote automation until their native contract is verified.

Both adapters consume `hook_event_name`, `tool_name`, `tool_input.command`, and
an existing `cwd`. Native hook execution must start within the trusted installed
project; the registration finds the installed wrapper in the working directory
or its ancestors without requiring Git first. The wrapper requires Python, and
Git is required only when the policy evaluates repository state. Unrelated tools
and ordinary local shell commands do not require a verification report.

## Supported shell and publication forms

Literal shell argv, command chains and substitutions are inspected without
executing them. Literal `echo`, `printf`, search arguments and quoted cat/tee
here-document bodies are text. Recognized local Git commands, `git -C PATH`,
ordinary environment wrappers and local package commands remain available.
Policy-sensitive `eval`, dynamic target expansion, unknown executable wrappers,
Git configuration injection and Git environment overrides are rejected. This
parser is not a complete shell security boundary.

A push requires one explicit configured remote and one literal integration ref
or annotated version tag. Implicit upstream/refspec configuration, working
branches, force, deletion, mirrors, bulk/follow-tags publication and configuration
that expands publication are blocked. A named tag must point at the exact verified
candidate. Vercel's bare/default deployment and non-production targets are denied.
Explicit production commands need exact local evidence and a native approval
boundary. Claude supports the declared `vercel`/`vc` and npx/pnpm Vercel forms;
Codex remote passage requires separately issued canonical commands covered by its
project prompt rules. Unsupported remote wrappers remain blocked.

GitHub run viewing/listing/watching and PR/release/workflow inspection are local
policy read paths. PR creation/merging, workflow dispatches and run reruns are
blocked. Canonical `gh release create TAG --verify-tag --title TITLE --notes-file FILE`
accepts an annotated version tag at the verified integration HEAD and an existing
notes file inside that repository, subject to the same native approval boundary.
The release checkout must have one documented remote with identical single
fetch/push URLs and no divergent GitHub default repository. Repository/target
overrides and additional options remain unsupported. This conservative local
binding follows the [GitHub CLI 2.100.0 remote selection contract](https://github.com/cli/cli/blob/v2.100.0/pkg/cmd/factory/default.go). Arbitrary
API, release editing and asset mutations require an exact owner-reviewed command
outside agent automation. The release review supplies those commands without forging a
receipt or disabling the guard.

## Project setup and evidence

Review native changes separately with `--allow-capabilities config:claude-policy`,
`--allow-capabilities config:codex-hooks` and, for Codex permission files,
`--allow-capabilities resource:codex-permissions`. The installation engine keeps
unknown hooks, settings and explicit Agent Teams opt-ins. New installs do not
activate Agent Teams. A capability file change or retirement also needs setup
scope; explicitly selected detach may remove unchanged owned content.

Declare the project's full local gate selection in `.rpi/policy.json` using
`verification_checks` (unique `name` and literal `argv` pairs) and
`verification_command` (the runnable local runner argv). An adopter can use
`["python3", ".rpi/scripts/rpi-verify.py"]`. The runner executes that complete
inventory sequentially; custom fixture selections cannot attest the full suite.
Publication compares every expected name/argv and successful exit, candidate
identity and runtime identity before and after verification. This validates
local evidence, not user authorization. See [migration setup](migrations/v2.md).

Direct native event fixtures and pinned source inspection establish the adapter
contract. They do not establish actual client trust, invocation or approval.
Phase 6 separately records a trusted allowed and denied invocation and real
native accepted/declined approval for each supported adapter. Until then report
registration, trust and observed enforcement separately; absent telemetry is
unobserved. Optional telemetry failure does not change the policy decision.
