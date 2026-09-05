# cc-rpi: RPI for Claude Code and Codex

## Project facts

cc-rpi is a documentation, shell and Python blueprint. `templates/` is the
canonical exported product; `generated/` contains deterministic native outputs.
`main` is the long-lived canonical integration branch. Implementation uses local
worktrees/temporary branches; direct main publication requires owner authorization.
There is no application build or registry publish step.

## Local verification

Run `bash scripts/verify-local.sh` sequentially for the complete portable CI
selection. Prerequisites are Git, Bash, Python 3.11+, PyYAML, ShellCheck, Node,
GitHub CLI and uv. The runner captures every exit and candidate identity in
`.rpi/local/verification.json`; a changed candidate invalidates that evidence.
Separate database and actual-harness acceptance receipts are required when the
plan names them. Coverage counts and measured source coverage are distinct.

There is no markdownlint configuration here; do not reflow prose to its default
80-column rules. Validate internal links and apply the no-emoji documentation
rule. Claude-only PostToolUse feedback is not prevention of an earlier edit.

## Source and task routing

| Task | Authoritative source |
| --- | --- |
| RPI workflows | `templates/skills/rpi-*/SKILL.md` and bundled resources |
| Distribution/install/update/detach | `templates/distribution.json`, `templates/scripts/rpi-distribution.py` |
| Native metadata | `templates/adapters/claude.json`, `templates/adapters/codex.json` |
| Domain rules | `templates/rules/`, `templates/skills/` |
| Workflow methodology | `methodology/README.md` and its reading order |
| Error/rule catalog | `patterns/agent-errors.md`, `patterns/quick-reference.md` |
| Contributions and retirements | `.claude/rules/contributing.md` |
| Git-heavy work | `.claude/rules/git-recipes.md` |
| Local diagram work | `.claude/skills/drawio/SKILL.md` (local extension, not exported) |
| Codex cleanup | `.codex/skills/codex-simplify/SKILL.md` |

Load controlling instructions and the selected workflow completely. Use Claude
`/rpi-plan` or plugin `/cc-rpi:rpi-plan`; use Codex `$rpi-plan` or its skill selector.
Native `/plan` and `/status` do not dispatch to old RPI artifact commands.
Existing legacy names carry migration notices; do not recreate colliding aliases.
`/simplify` means Claude's native command or Codex's `codex-simplify` helper.
Parallel independent assignments stay within the current authorized phase and
available resource limits; one integration owner manages local commits.

## Ownership and artifacts

Preserve project knowledge and local extensions when rendering self-application.
Never edit generated output manually or merge native plugin caches. The engine's
content-addressed baselines own selected files/blocks; unknown content is retained.
A read-only installation check diagnoses drift; ordinary work does not silently
rewrite the owner's user-level installation or update other projects.

The approved `2026-09-05-cc-rpi-v2.md` plan, its phase directory and notes are
explicitly tracked. Existing machine-specific research audits remain ignored.
Do not bulk-stage `docs/research/`. Curated plans/research in new adopters are
versioned knowledge; `docs/agents/` is ignored here under public-repo Rule #70.
Keep raw runtime observations, schemas, telemetry and recovery in `.rpi/local/`.

Run `.claude/scripts/validate-findings.py` on a pre-launch report before parsing
it for remediation; a nonzero result blocks dependent work. Preserve every
confirmed finding's disposition. The portable contract metrics aggregator accepts
`{ts, session_id, hook, decision, rule, file}` JSONL; an absent stream is unobserved.
When a guard blocks, report `BLOCKED / WHY / FIX` with a runnable fix.

<!-- rpi:rule-map:start -->
## Conditional rule access

Before acting on a matching task/path, read the installed rule body below.
The installation manifest records the selected components and exact mappings.
This root map applies even when a session starts at the repository root and
later edits a nested directory; it is an instruction contract, not a native
Codex glob loader. Sessions started inside a subproject also read their actual
root-to-current-directory instruction chain. Preserve project-specific overrides.

| Task or path | Required resource | Essential constraint |
| --- | --- | --- |
| Deployment, CI, release or infrastructure configuration | `.rpi/rules/deployment-safety.md` | Local gates first; no Vercel Preview; production needs authorization. |
| SQL, Supabase migrations, schema, data access or database tests | `.rpi/rules/supabase.md` | Reset/test locally; privileges and RLS are distinct; remote targets need authorization. |
| Behavioral changes, tests, fixtures and validation | `.rpi/rules/testing.md` | TDD for behavioral code; every required check must run and pass. |
| WebMCP, MCP tools, tool registration or agent-facing interfaces | `.rpi/rules/webmcp.md` | Validate on the server; isolate unstable browser APIs and test caller recovery. |

If a required component is missing, report the exact missing path and run the
read-only installation check before proceeding with dependent work. Never
invent a successful read or silently treat an incomplete install as healthy.
<!-- rpi:rule-map:end -->

<!-- rpi:push-accountability:start -->
# Push Accountability

Keep working branches and worktrees local. Finish applicable tests, coverage,
typechecks, lint, build and deployment preflight locally, resolve failures,
and integrate completed work locally into the documented integration branch.
Inspect workflow and deployment triggers before the single authorized push of
that completed branch. Never create Vercel Preview deployments or publish
working branches/PRs for experimentation. If an integration push would create a
Preview, stop before pushing and use only a documented, non-destructive bypass.
Production publication remains separately and explicitly authorized. Read-only
inspection of existing runs and deployments is allowed.

Commit or preserve intended changes before pulling; never pull through a dirty
tree. After an authorized push, inspect every expected workflow for the exact
pushed commit. Diagnose failures from existing logs and reproduce/fix locally.
Report the failed remote result; do not trigger reruns or a fix-and-repush loop.
A new remote action needs authorization after the complete local gates pass.
<!-- rpi:push-accountability:end -->

<!-- rpi:rpi-details:start -->
# RPI Details

## Context Management

- Each RPI phase should be its own conversation.
  Preserve their acceptance boundaries unless the user explicitly authorizes
  continuation; a continuation instruction does not remove verification.
- Use `/clear` between unrelated tasks.
  Use `/compact` when context is heavy but the task continues.
- Handoffs record objective, approved scope, base/current commit and worktree,
  findings, decisions, check evidence and tested identity, deviations, risks and
  next phase. On resume, verify actual files, refs and evidence validity before
  relying on the handoff; compaction never grants new authority.
- Subagents are context control mechanisms --
  they search/read in their window and return only distilled results.
- Research and planning happen against the integration branch.
  Implementation happens in worktrees or temporary branches.

## Rules for All Phases

- Read controlling instructions/contracts and directly mentioned files completely.
  Inspect implementation to the depth needed; reuse valid prior reads.
- In `rpi-research`, document what exists without improvement recommendations.
  Use the separate `rpi-assess` workflow for evaluative research and alternatives.
- Every code reference must include file:line.
- Delegate only useful bounded independent assignments within this phase.
  A narrow task may stay with the parent. State objective, permitted actions,
  owned files, evidence/output, resource budget and terminal condition for each
  assignment. Missing required results remain coverage gaps until resolved.
- Never write documents with placeholder values.
- Exhaust all tools before suggesting manual steps --
  check CLI tools, shell commands, MCP servers, and file tools
  before escalating to the user.

## Rules for Implementation

- Follow the atomic loop:
  implement -> independent review -> repair -> simplify -> verify.
  The native simplify command or Codex helper catches code reuse, quality, and efficiency issues
  that the plan-compliance reviewer does not check.
- Independent batch work stays local, one owner per file set/worktree and one
  integration owner. Never use a batch mode that automatically publishes PRs.
  Keep at most three simultaneous implementers; use fewer when the task or
  available resources do not justify three.
- Run ALL automated verification after each phase.
- Stop after each phase for acceptance unless the user explicitly authorizes
  continuation. Finish all authorized phase work before that gate.
- If a technical discovery invalidates the plan contract, record the adjustment
  and explain the impact before dependent work; ask only for a required new decision.

## Pre-Release Workflow

`rpi-pre-launch` -> `rpi-remediate` -> `rpi-update-docs` -> `rpi-release`

After `rpi-pre-launch`, include a simplify pass for reuse, quality and
efficiency. Track its findings with the other audit results; resolve security
and infrastructure findings through the same review, repair and verification
loop. Preserve all required audit domains regardless of staffing.

Resolve every confirmed actionable finding before acceptance. Reject false
positives with evidence. Strategic findings needing a new architectural decision
receive explicit local dispositions and owner review; external issue creation
requires authorization. Never silently discard a finding.

## Testing Philosophy

Prefer automated verification.
Manual only for: sudo, hardware, new installs, visual-only.
Use deterministic linting/formatting tools. Preserve TDD for behavioral code
changes. Run all required phase/final gates locally, sequentially with failure
aggregation; a later success cannot erase an earlier failure. Reuse evidence
only for unchanged tested inputs, never as a substitute for an invalidated gate.
<!-- rpi:rpi-details:end -->
