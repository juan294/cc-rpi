# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.29.0] - 2026-09-01

### Added

- **WebMCP as a first-class blueprint surface.** A new `webmcp` skill
  (`templates/skills/webmcp/`) teaches the agent-facing tool contract in
  wrong/right pairs -- one function per tool, name by effect, take raw
  input, validate strictly in code, ship errors as recovery instructions,
  register/unregister tools with page state -- plus a
  `references/tool-design-framework.md` worked example. A new `webmcp.md`
  rule template confines the pre-standard `document.modelContext` global
  to a single adapter module. A new `methodology/webmcp-tool-design.md`
  maps the whole framework onto RPI (define goal + initial state is
  Research, role-play is Plan, evals + telemetry is Validate). Adds rules
  #85-92, bringing the rule count to 89, skill count to 12, and rule
  template count to 6. Installed conditionally -- alongside the existing
  supabase/python-rules/macos-rules pattern -- via `/bootstrap`, `/adopt`,
  and `/update`, so projects with no agent-facing surface pay nothing.
  Nothing retired this cycle: the 8 new rules are tool-contract facts, an
  environment fact about a pre-standard global, and a process obligation
  with no hook to enforce it -- none are retirement candidates under
  `.claude/rules/contributing.md`'s four grounds.

- **`/tool-design` command.** Turns a stated user goal into a tool
  contract plus seed evals by role-playing the conversation twice (clean,
  then deliberately vague) against the project's real codebase state.
  Sits between `/brainstorm` and `/plan` in the pipeline; derives tools
  from what the role-play actually required rather than the existing
  UI's button list. Model tier: opus.

- **Conditional 9th `/pre-launch` specialist: Agent Surface Engineer**
  (domain `AS`). Spawns only when a read-only gate detects an
  agent-facing surface (`modelContext`/`registerTool`/`toolname=`).
  Covers tool inventory, naming, schema validation, error-recovery text,
  registration lifecycle, and adapter isolation. Adds a conditional
  §11a report section and extends the Finding-ID domain grammar to
  include `AS` in both `validate-findings.py` and `remediate.md`.
  `verify-counts.sh` now machine-checks the "8 core specialists" claim,
  computed as the roster total minus every specialist marked
  `-- conditional`, so it stays correct as the roster grows.

- **Probabilistic-surface verification.** A new "Verifying Probabilistic
  Surfaces" section in the testing hierarchy covers evals for a caller
  that's a model rather than a program: fix the contract, then assert
  tool selection / parameter extraction / state management as
  probabilistic outcomes, preferring a code-based check over
  LLM-as-judge whenever one exists. Adds an agent-tool-call-failures
  error-logging category and conditional agent-surface obligations to
  the E2E Pro playbook's Wave A, scoped so a project with no agent
  surface inherits nothing new.

- **Coverage reporting to Portfolio** on every default-branch push
  (`.github/workflows/coverage.yml`, `scripts/report-coverage.sh`),
  replacing a stale local batch script.

### Fixed

- `verify-edit.sh` no longer blocks edits to files outside the project
  root -- a markdownlint `RangeError` on out-of-project files (e.g. agent
  memory writes) was being read as a lint violation.
- `verify-counts.sh` dropped an invalid backslash-escaped backtick in two
  `check_count` patterns; backtick isn't an ERE metacharacter, and GNU
  grep (CI) treats the escape literally where local grep implementations
  don't, so the pattern silently failed only in CI.
- Removed an unused variable in `morning-triage.sh` that tripped
  shellcheck and made CLAUDE.md's documented shellcheck command fail even
  though CI's own file list never covered that script.

### Changed

- `README.md` and `methodology/four-phases.md` synced to the above: the
  methodology file count, a WebMCP Tool Design bullet, `/tool-design` in
  the slash-command list, and a `/tool-design` branch in the Architecture
  Overview diagram.

## [1.28.2] - 2026-07-25

### Fixed

- **Removed private project names from shipped content.** `Archy-compatible`
  in `morning-triage.sh`, "the Chapa failures" in the multi-agent skill,
  `owner/XILLVER` in Error #23, and the `GenAI_Projects` folder name in
  Error #45 all identified the maintainer's own setup. Genericized, keeping
  each example's instructive shape -- Error #23 still demonstrates a fabricated
  repo name, Error #45 still contrasts a real parent directory against a
  plausible invented one. This shipped un-released in v1.28.1; tagging it so
  the plugin marketplace serves the cleaned content.

### Changed

- `CLAUDE.md` gained file-location rows for `scripts/install.sh` and the four
  repo-invariant scripts, and `AGENTS.md` now tells a Codex session to re-run
  the installer after pulling cc-rpi. Both shipped in v1.28.0 without being
  recorded in the places an agent actually looks.

## [1.28.1] - 2026-07-25

### Fixed

- Error #45 ("agent fabricates filesystem paths") illustrated itself with the
  maintainer's real home directory layout, which a public repository should not
  expose. Genericized to `/Users/you/...`. The lesson is preserved: the example
  still contrasts a real parent directory against a fabricated but plausible one
  (`Documents/GenAI_Projects` vs `code`), because inventing a believable parent
  is the specific failure the entry documents. A repo-wide sweep confirms no
  personal filesystem paths remain in shipped content.

## [1.28.0] - 2026-07-25

### Added

- **`scripts/install.sh`** -- installs the four user-level commands
  (`/bootstrap`, `/adopt`, `/update`, `/detach`) into `~/.claude/commands/`,
  substituting the path to your cc-rpi clone and verifying no placeholder
  survives. `--check` reports drift without changing anything.

  This closes a real adoption gap. Those commands ship with a
  `<path-to-your-cc-rpi-clone>` placeholder -- 12 occurrences across 4 files --
  and GUIDE previously told adopters to edit them by hand, with nothing
  verifying the result. Worse, the installed copies are snapshots: they go
  stale on every cc-rpi release and nothing detected it, so `/update` -- the
  command whose entire job is keeping projects current -- could silently sync
  projects using months-old instructions. Run the installer after every
  `git pull`, or `--check` to find out where you stand.

### Changed

- `README.md`, `GUIDE.md`, and `templates/setup-checklist.md` now point at
  `scripts/install.sh` instead of a manual copy-and-edit checklist, and say
  plainly that installed copies must be refreshed after each pull. The README
  Quick Start now names `/bootstrap` and `/adopt` rather than only offering a
  prose prompt.

## [1.27.1] - 2026-07-25

### Fixed

- **Deviation logs were destroyed before `/validate` could read them.** v1.27.0
  added a deviation log at `docs/plans/<plan>-notes.md`, written by
  `/implement` and read by `/validate` -- but that path was gitignored while
  `/implement` mandates a worktree, so the log was deleted at teardown before
  `/validate` ever saw it. `.gitignore` now excludes `docs/plans/*` and
  re-includes `!docs/plans/*-notes.md`. The `/*` matters: git cannot re-include
  a path whose parent **directory** is excluded, so the obvious
  `docs/plans/` + negation silently does nothing. `/implement` now says to
  commit the log with the phase, and to reference the plan by name rather than
  as a markdown link -- the plan stays untracked, so a link to it dangles in a
  clean checkout.
- **`verify-version.sh` blocked legitimate releases on historical references.**
  Its "previous version must appear nowhere" sweep flagged the Retirement
  Ledger's `Retired in` column and an illustrative comment, both of which name
  an old release correctly. The sweep now excludes `.claude/rules/contributing.md`
  (check 3 already validates ledger versions against real CHANGELOG releases)
  alongside `CHANGELOG.md` and `docs/`. Verified that a genuinely stale
  reference elsewhere still blocks.

## [1.27.0] - 2026-07-25

### Added

- **Retirement path for the rule corpus** (`.claude/rules/contributing.md`):
  four admissible grounds (superseded / hook-enforced / model-native / merged),
  a procedure that blocks while inbound references remain, and a Retirement
  Ledger. `/release` now asks what came OUT each cycle, not just what went in.
  The corpus had an intake path and no exit path across 38 releases.
- **`shell-tools` skill** -- 16 cross-cutting shell and tool-call environment
  facts (quoting inside single-quoted zsh/jq/Python strings, absolute paths and
  cwd resets, linter invocation, curl/JSON handling). Skills 10 -> 11.
- **Four repo-invariant scripts, all CI-enforced**, each emitting BLOCKED/WHY/FIX
  with a runnable fix: `verify-counts.sh` (stated counts match the catalogs),
  `verify-skills.sh` (skill frontmatter contract, 500-line body ceiling,
  sibling-file wiring), `verify-version.sh` (version strings match CHANGELOG,
  including the README badge that carries it 3x on one line), and
  `check-tree-drift.sh` (`templates/` vs `.claude/`).
- **`templates/skills/error-patterns/references/error-catalog.md`** -- the repo's
  first multi-file skill. All 64 errors as one-liners, so the skill's level-3
  detail is reachable downstream, where `patterns/agent-errors.md` does not exist.
- **`.claude/DIVERGENCE.md`** -- manifest recording which shared files are
  symlinked and which deliberately differ, with the reason for each.
- Interface design over worked examples (`methodology/agent-design.md`), rich
  references (`methodology/context-engineering.md` + `/plan`), `/doctor`
  awareness, a deviation log written by `/implement` and read by `/validate`,
  and an optional comprehension gate in `/validate`.

### Changed

- **`patterns/quick-reference.md` is now an INDEX, not a catalog** (20,360 ->
  6,923 bytes). Every rule body moved into the skill, rule file, command, or
  methodology doc that needs it, so each rule loads at its point of use. Each
  line is `N. title -> destination`, and CI asserts the destination resolves.
  **Downstream impact:** if you run `/update`, expect this file to shrink to
  pointers. Confirm your update also pulls the skills and rules the index now
  names, or rule text you previously had inline will be missing.
- **All 11 skill `name:` fields normalized** from display case to
  lowercase-hyphen matching the directory (`"Git Workflow"` -> `git-workflow`).
  The previous values did not satisfy the Agent Skills identifier contract.
- **`.claude/` de-duplicated into symlinks** -- 15 byte-identical files now link
  into `templates/`; 5 that diverge on purpose stay real and are documented.
- `.claude/rules/rpi-workflow.md` renamed to `rpi-details.md` so it pairs with
  its template and the drift check can see it.
- Rule #72 (Triage processes Dependabot PRs) renumbered to **#84**; the Supabase
  rule keeps #72 by seniority.
- Pinned model tiers refreshed to Claude Opus 5 / Sonnet 5 / Haiku 4.5.
- **Hardened `/release`'s version scan** (`templates/commands/release.md` +
  active `.claude/commands/release.md`): Step 1 now mandates a `git grep` of the
  current version string instead of relying on memory, and explicitly names the
  commonly-missed locations (shield.io badges where the version repeats 3x on one
  line, and `.claude-plugin/*.json` manifests). Step 2 adds a post-bump re-grep
  of the OLD version to confirm nothing was missed. Motivated by the README badge
  and plugin manifests repeatedly shipping 1-2 releases stale.

### Removed

- **Rule #67** ("Justify every external action") -- retired, merged into #64.
- **Rule #80** ("Verify an API supports a call before chaining") -- retired,
  merged into #13 plus the verification gate.
  Rules 83 -> 81. These are the first retirements in the project's history;
  both are recorded in the ledger with their ground.

### Fixed

- `shell-tools` was missing from the always-install lists in `bootstrap.md`,
  `setup-checklist.md`, and `update.md`, so downstream projects would never have
  received it. `update.md` was also missing `systematic-debugging` since v1.21.0.
- Four onboarding surfaces told the agent to "internalize every operational
  rule" from a file that is now an index of pointers.
- `CLAUDE.md` claimed CI runs markdownlint. It never has, and the repo ships no
  markdownlint config, so its 80-column defaults fight the repo's own style.
- Missing `---` separators before errors #63 and #64; duplicate rule number 72;
  a stale "63-error catalog" count; committed `__pycache__` bytecode.

## [1.26.0] - 2026-07-24

### Added

- **E2E Pro release-verification playbook template**
  (`templates/e2e-pro-playbook-template.md`) — a cross-project template that turns
  release verification into auditable evidence: it proves that every *required*
  check actually ran and passed against the exact artifact being tagged. Ships as a
  copy-and-adapt blueprint with a 20-decision ledger, an 8-wave implementation plan,
  a capability-registry schema, a constrained-combination engine, a per-release plan
  compiler, a multi-layer evidence model, and a project epic. Its mandatory floor is
  **Wave A** (a release gate that cannot lie: zero-pass fails, required skip/fail
  blocks even when quarantined, candidate identity is fixed and verified, tag is
  last); Waves C–H are adopted by project risk. Framed to sit alongside `/release`
  (tagging authority), `/pre-launch` + `/remediate` (static audit), and
  `methodology/testing.md` — not replace them.
- **`/explore-release` command** (`templates/commands/explore-release.md`) — Wave B
  of E2E Pro: diff-driven, fresh-context exploratory release charters with the
  mandatory eight-maneuver table, a synthetic-fixture safety contract, and a
  block-on-failure gate. Feeds evidence to `/release`; never tags.

### Changed

- Wired E2E Pro into the propagation path: `templates/setup-checklist.md` (new
  "Release Verification (E2E Pro)" section + `/explore-release` in the command
  list), `templates/commands/bootstrap.md` and `adopt.md` (install steps +
  migration-order entry), and `GUIDE.md` (new subsection + "Where to Go Deeper"
  row).
- Swept command/template inventories for the new command: `/explore-release`
  added to GUIDE.md's "Supporting Commands" and opus model-tier tables, the
  README command bullet, and `templates/commands/detach.md` (Tier-1 removal, so
  detach no longer orphans it) and `update.md` (Phase 3 sample). Added a
  "Release verification" row to `CLAUDE.md`'s Project File Locations and an E2E
  Pro playbook bullet to the README Templates section.
- Corrected stale count in the plugin manifests
  (`.claude-plugin/plugin.json`, `marketplace.json`): "63-pattern" ->
  "64-pattern" agent-error knowledge base.
- Updated the per-command Model tier doc line from Sonnet 4.6 to Sonnet 5 across
  the command set.

## [1.25.0] - 2026-06-26

### Added

- **Error #64 + Rule #83 — "a finding's recommendation is a hypothesis":**
  new error pattern (`patterns/agent-errors.md`) and paired rule
  (`patterns/quick-reference.md`) for the failure where a remediation agent
  implements an audit finding's proposed fix literally and breaks a
  correctness/UX invariant the fix never verified. Real case: a Performance
  finding traded server-side locale resolution for ISR on the highest-traffic
  route, breaking i18n for every cookie-based (returning) user — the symptom
  test ("ISR restored") passed; no test guarded "English user sees an English
  body". Error count: 63 → 64. Rule count: 82 → 83.
- **Required `Regression risk` field on every pre-launch finding** — the
  Output Contract (`pre-launch.md`) now mandates an
  invariants/assumptions/trade-offs field, enforced before parsing by
  `validate-findings.py` (added to required fields; bundled fixtures +
  self-test updated).

### Changed

- **Pre-launch "Second-order rule"** (`pre-launch.md`) — a finding is a
  hypothesis, not a work order. Specialists reason one step past each fix
  and, when a non-functional goal (perf/ISR/bundle) conflicts with a
  correctness/security/UX invariant, default to the invariant and flag the
  trade rather than presupposing the win.
- **Remediation verify-the-recommendation gate** (`remediate.md`) — worktree
  agents independently confirm a finding's assumptions in real code and write
  the guard test against the invariant (not the symptom) before implementing.
  A recommendation that fails verification or trades away an invariant
  **halts** and escalates to a human instead of being implemented literally.
  Adds a "Halted" report line and a `/remediate` rule.

## [1.24.0] - 2026-06-25

### Added

- **5 new operational rules (#78–#82):** multi-agent scope discipline (#78 terminal
  conditions + watchdog budget), dedup gate (#79 check repo state before continuing),
  API-existence verification before chaining (#80), programmatic markdown table
  formatting (#81), and CodeQL/GHAS prerequisite gate (#82). Rule count: 77 → 82.
- **Methodology: "Scope Discipline and the Watchdog"** (`methodology/agent-design.md`) —
  orchestrator obligations table (scoped spawn, watchdog budget, dedup gate) drawn
  from a real 2h+ runaway fork-agent incident.
- **Methodology: "Code Scanning Requires GHAS"** (`methodology/ci-and-guardrails.md`) —
  `gh api` probe command, public-free vs private-paid distinction, and the rule that
  querying alerts is always safe but creating the scanner requires GHAS confirmation.
- **Methodology: "Checkpoint and Resume"** (`methodology/scheduled-agents.md`) — bash
  step-marker pattern (`done_step`/`mark_step`) so headless nightly agents survive
  mid-flight auth failures, API 500s, and 529 overloads without restarting from scratch.
- **Skill: "Cleanup After Merge"** (`templates/skills/git-workflow/SKILL.md`) — complete
  post-merge recipe: worktree remove → local branch delete → `git fetch --prune` →
  verify nothing dangling.
- **Skill: "Scope & Watchdog" and "Dedup Before Continuing"**
  (`templates/skills/multi-agent/SKILL.md`) — wrong/right examples for both patterns.

## [1.23.0] - 2026-06-23

### Added

- **Contract-layer metrics (impact measurement).** The `guard-bash.sh` and
  `verify-edit.sh` hooks now append one fail-open JSONL row per evaluated
  command/edit to `.claude/metrics/contract-events.jsonl` (decision, rule, file,
  session — never command text or file contents). `templates/scripts/contract-metrics.py`
  aggregates the log into block rates per hook/rule, a verify-edit **self-correction
  rate** (block followed by a clean re-edit of the same file in the same session),
  and a week-over-week trend. A deterministic `contract-metrics-agent.sh`
  (weekly, no Claude CLI / no cost) snapshots the report to
  `docs/agents/contract-metrics-report.md`. Lets you evaluate months from now
  whether the contract layer actually changed agent behavior, instead of trusting
  blindly. Raw log gitignored (`.claude/metrics/`); report follows Rule #70.

## [1.22.0] - 2026-06-23

### Added

- **Contract layer (post-action verification).** A targeted set of deterministic
  guardrails that move the mechanically-detectable subset of rules from advisory
  prose to hard enforcement:
  - `templates/hooks/verify-edit.sh` — a `PostToolUse` hook on `Write`/`Edit`
    that checks edited `.md` files for emoji (always on; per-file opt-out via
    `<!-- contract:allow-emoji -->`) and runs markdownlint when the project ships
    a markdownlint config. cc-rpi's first post-action verification layer; realizes
    "Level 1: Editor-time" from `methodology/ci-and-guardrails.md`.
  - Standardized `BLOCKED / WHY / FIX` corrective-hint format across hooks (shared
    `emit_block` helper in `guard-bash.sh` and `verify-edit.sh`) so every block is
    a guided correction.
  - `templates/scripts/validate-findings.py` — enforces the pre-launch/remediate
    Finding-ID contract (grammar, required fields, `file:line` rule); `/remediate`
    runs it as a Step-1 gate before parsing, rejecting malformed reports.
  - New Rule #77 ("No emojis in documentation", `[hook-enforced]`). Rule count
    76 -> 77.
  - Inspired by `cristhianrivera/contract-driven-llm-agent` (idea source only —
    no SQL/ontology/reconciler machinery ported).
- **`/triage` covers GitHub Security & Quality Alerts.** Every triage run now
  queries three GitHub-native alert surfaces in addition to local agent reports
  and the Dependabot PR queue: code scanning / CodeQL (including quality
  warnings), Dependabot security alerts, and secret scanning. All open alerts are
  treated as findings (no severity filtering), classified GREEN/YELLOW/RED, and
  surfaced in discovery, the action plan, and the report — so GitHub-native
  warnings cannot be hidden by a GREEN local report. A failed/disabled alert
  query is itself a triage finding.
- **`/triage` handles `leanness-report.md` as an actionable source.** Each
  `shrink`/`delete`/`yagni`/dead-code/efficiency item is extracted and listed
  individually (never bulk-applied), with safety guardrails: keep edits scoped to
  the named files, preserve public APIs unless a dead export is identified, verify
  importers before deleting, and rely on or add tests per risk. Leanness items are
  100% actionable under Rule #58 after approval.

## [1.21.0] - 2026-06-19

### Added

- **`/brainstorm` command (optional RPI pre-step).** Socratic, one-question-at-a-time
  intake for vague or greenfield work where the request is a goal, not a spec and
  there is no existing code to `/research`. Produces a design brief in
  `docs/research/YYYY-MM-DD-*-brief.md` that `/plan` consumes. Documented as an
  optional front end, not a fifth phase. `templates/commands/brainstorm.md`.
- **`systematic-debugging` skill.** Auto-consulted (`user-invocable: false`)
  procedure for novel bugs: reproduce -> isolate -> hypothesize -> test ->
  fix-root-cause -> verify, plus stop-conditions. Routes known tool/git/CI
  failures to the error-patterns skill. Brings `templates/skills/` to 10.
- **Installable as a Claude Code plugin.** Added `.claude-plugin/plugin.json`
  (manifest pointing `skills`/`commands` at the existing `templates/` dirs --
  no file moves) and `.claude-plugin/marketplace.json` so the repo is its own
  self-hosted marketplace. Install with
  `/plugin marketplace add juan294/cc-rpi` then `/plugin install cc-rpi@cc-rpi`.
  Commands/skills namespace as `/cc-rpi:research`, `/cc-rpi:brainstorm`, etc.
  Passes `claude plugin validate`. The blueprint/copy model is unchanged and
  continues to work alongside the plugin.

### Changed

- **Documentation consistency sweep for the additions above.** `/bootstrap` and
  `setup-checklist.md` now install `systematic-debugging/` and list `/brainstorm`,
  so new projects pick up both; GUIDE skill count corrected 9 -> 10 (two places)
  with `systematic-debugging` enumerated; `four-phases.md` topology diagram shows
  `/brainstorm` as an optional pre-step; bootstrap example command count fixed.

### Fixed

- **Nightly `cc-rpi-update` agent could not edit `.claude/` files.** The scheduled
  `templates/scripts/cc-rpi-update-agent.sh` ran `claude -p` without a permission
  mode, so Claude Code's sensitive-file guard on `.claude/` edits blocked every
  blueprint sync in non-interactive mode (the agent detected updates but applied
  nothing). Added `--permission-mode bypassPermissions` to the invocation —
  `acceptEdits` does **not** bypass the `.claude/` guard; only `bypassPermissions`
  does. Required for unattended agents that must edit `.claude/` and commit.

## [1.20.0] - 2026-06-14

### Added

- **Develop-based release flow (`/release`).** `release.md` now detects a third
  branching strategy: a permanent `develop` integration branch that releases via a
  direct `develop` -> `main` PR (no intermediate `release/vX.Y.Z` branch). Merges
  squash + auto-merge and never passes `--delete-branch` on the permanent branch.
- **Rule #76: standardize GitHub repo settings.** Documents the canonical
  per-project configuration -- squash-only merges, auto-merge, delete-branch-on-merge,
  Dependabot alerts + security update PRs, and the Production environment restricted
  to protected branches. Ties to Rule #15 (`git branch -D`) and the develop-based
  release flow. Now 76 rules.

## [1.19.0] - 2026-06-13

### Added

- **Model tier economics layer (ported from copilot-rpi v1.16.0).** Added a
  `haiku` floor tier alongside the existing `opus`/`sonnet` tiers and gave
  every command an explicit `Model tier` line. `/status` and `/describe-pr`
  now run on the floor; `/research`, `/plan`, `/pre-launch` stay frontier;
  the rest run mid-tier.
- **`methodology/cost-monitoring.md`.** New doc on model economics: the four
  cost pools, model tiers as the primary lever, access tiers (frontier access
  for authoring loops, the floor for consumption), measuring cost-per-outcome,
  and cost-tied approval gates. Added to the methodology reading order (now 12
  files).
- **Cost-report scheduled agent.** Weekly agent (runs on the floor tier) that
  turns Claude Code / Anthropic API usage exports into cost-per-outcome numbers
  and flags workflows drifting above their declared tier.
- **Rule #74 (Pin a model tier to every workflow)** and **Rule #75 (Measure
  cost per outcome before betting beyond the floor)** in the quick-reference,
  under a new "Cost & Models" section. Now 75 rules.
- **GUIDE "Model Tiers at a Glance" table** mapping every command to its tier.

### Changed

- **`context-engineering.md` "Model Selection" section rewritten.** Replaced
  the generic "complex/routine/bulk → different models" guidance — which
  contradicted the per-command tier lines — with the 3-tier system, a
  tier→concrete-Claude-model binding table, subagent tier-inheritance, and an
  override-upward-never-silently-downward rule.

## [1.18.0] - 2026-05-02

### Added

- **Rule #72: Triage processes Dependabot PRs.** `/triage` now scans
  open Dependabot PRs (`gh pr list --author "app/dependabot"`) as part
  of Step 1 Discovery and processes them in a new Step 5 (after the
  triage commit is pushed). Patch and minor updates with green CI
  auto-merge via `gh pr merge --squash --auto --delete-branch`. Major
  bumps defer for human review. CI red with an obvious fix (snapshot
  drift, lockfile, generated files) gets one fix attempt before
  deferring. Conflicts are rebased via `gh pr update-branch` and
  re-evaluated. Dependabot processing happens last so a flaky dependency
  PR can't block triage code fixes. Updated:
  `patterns/quick-reference.md`, `methodology/scheduled-agents.md`
  Morning Triage section, `.claude/commands/triage.md` and template
  counterpart, and `GUIDE.md`.

### Changed

- **Rule #70 is now conditional on repo visibility.** Previously, agent
  operational directories (`docs/agents/`, `logs/`, `scripts/agents/`)
  were gitignored across all projects. They are now gitignored only on
  public repos so operational details (security findings, internal
  metrics, agent status) don't leak. On private repos these directories
  are tracked, and `/triage` commits reports alongside code fixes as a
  historical audit trail. Visibility is detected via
  `gh repo view --json visibility`; missing remote or `gh` unavailable
  fail-safes to PUBLIC behavior. Updated:
  `patterns/quick-reference.md` (Rule #70),
  `methodology/scheduled-agents.md` (Report Lifecycle, gitignore
  section, Prerequisites), `templates/setup-checklist.md`,
  `templates/commands/bootstrap.md`,
  `.claude/commands/triage.md` and template counterpart,
  `.claude/commands/pre-launch.md` and template counterpart, and
  `GUIDE.md`.

## [1.17.2] - 2026-04-18

### Changed

- **Harness scope policy documented in `README.md`** -- new "Harness
  Scope" section states the one-harness-per-blueprint principle,
  explains why Codex is the one exception (single `AGENTS.md` bridge,
  not a parallel command tree), and points OpenCode, GitHub Copilot,
  and other harnesses at sibling repos, community overlays, or forks.
  Links `copilot-rpi` as the canonical precedent for a sibling-repo
  harness layer.

## [1.17.1] - 2026-04-17

### Fixed

- **Blueprint consistency alignment** -- workflow and onboarding docs now
  use one coherent model across `methodology/`, `templates/`,
  repo-local `.claude/`, `CLAUDE.md`, `AGENTS.md`, `README.md`, and
  `GUIDE.md`. Worktree-based implementation is documented as universal,
  branch-topology guidance is labeled consistently, outdated
  error-catalog count references are updated to `63`, and contributor
  guidance now requires a cross-layer consistency sweep when workflow
  docs change.

## [1.17.0] - 2026-04-17

### Added

- **Codex-only `codex-simplify` skill** -- new
  `.codex/skills/codex-simplify/SKILL.md` provides a portable
  Codex-side equivalent of Claude Code's native `/simplify` without
  introducing a conflicting project skill named `simplify`.

### Changed

- **Codex compatibility docs** -- `AGENTS.md`,
  `templates/AGENTS.md.template`, `templates/setup-checklist.md`,
  `README.md`, `GUIDE.md`, and `CLAUDE.md` now document the
  non-conflicting `codex-simplify` pattern and the install path under
  `~/.codex/skills/`.

## [1.16.0] - 2026-04-15

### Added

- **Codex compatibility layer** -- new `templates/AGENTS.md.template`
  teaches Codex / GPT-5.x how to interpret the existing cc-rpi project
  structure: `CLAUDE.md`, `.claude/commands/`, `.claude/rules/`, and
  `.claude/skills/`. This keeps the methodology stable across Claude
  Code and Codex without changing the workflow itself.
- **Repo-local `AGENTS.md`** -- cc-rpi itself now includes a Codex
  compatibility file so the blueprint can be operated directly in Codex.

### Changed

- **`/bootstrap` and `/adopt`** -- now create `AGENTS.md` by default so
  newly bootstrapped or adopted projects are Codex compatible unless the
  user explicitly opts out.
- **`/update`** -- now syncs the Codex compatibility layer via
  `templates/AGENTS.md.template` and tracks it in `.claude/cc-rpi-sync.json`.
- **`/detach`** -- now inventories `AGENTS.md` as a blueprint-managed
  artifact and warns before deleting customized Codex compatibility
  files.
- **Setup and onboarding docs** -- README, GUIDE, CLAUDE.md, and
  `templates/setup-checklist.md` now document the cross-harness pattern:
  Claude Code owns `.claude/*`; Codex uses `AGENTS.md` to interpret the
  same methodology.

## [1.15.0] - 2026-04-11

### Changed

- **`/pre-launch` command** — deep-audit restructure. Now spawns 8
  parallel specialist agents (Principal Architect, Staff FE, Staff BE,
  Performance Engineer, DevOps/SRE Lead, Security Reviewer,
  QA/Reliability Lead, Product Designer/UX Lead) instead of 6. Produces
  a 16-section launch-readiness report with Executive Summary, System
  Architecture Overview, End-to-End Flow Analysis, 8 per-domain findings
  sections, Prioritized Action Plan, Top-10 ROI ranking,
  Before/After/Later processing waves, Open Questions, and Final Verdict.
  Findings carry a 5-tier severity (launch-blocker / high / medium / low
  / strategic), a 3-tier time horizon (Before launch / After launch /
  Later), stable finding IDs (e.g., `SE-B1`), and mandatory
  evidence/inference labeling. Each specialist opens with a
  system-map-first domain model. Critic-mode mindset: systemic findings
  preferred over isolated nitpicks.
- **`/remediate` command** — updated to parse the new 16-section report
  format and process findings in 3 sequential waves. Wave 1 (Before
  launch — launch-blockers + high severity) runs first with full TDD +
  merge + CI verification. Wave 2 (After launch — medium severity) runs
  next with STOP gate for user deferral. Wave 3 (Later / strategic —
  low + strategic severity) files GitHub issues but does NOT spawn
  worktree fix agents — these require human architectural judgment and
  remain in the backlog. Rule #58's 100% coverage is preserved: every
  finding gets an issue; Wave 3 is the one documented exception to
  auto-fix. Issue labels now include `wave-1-before-launch` /
  `wave-2-after-launch` / `wave-3-later` in addition to domain and
  severity labels.

### Fixed

- **`SECURITY.md`** — supported versions table updated from `0.1.x` to
  `1.x` (placeholder was never updated from initial scaffold).

### Migration note for blueprint consumers

Run `/update` in any project using cc-rpi to pull the new `/pre-launch`
and `/remediate` command files. Existing pre-launch reports from the old
format are NOT backward-compatible with the new `/remediate` parser —
regenerate with the new `/pre-launch` before running `/remediate`.

## [1.14.5] - 2026-04-07

### Added

- **Draw.io diagram skill:** New `.claude/skills/drawio/` skill for generating
  native draw.io diagrams (`.drawio` mxGraphModel XML) with optional export to
  PNG, SVG, or PDF. Cross-platform CLI support (macOS, Linux, Windows/WSL2).

### Changed

- **Greenfield clarity:** Clarified across GUIDE.md, methodology/four-phases.md,
  templates/setup-checklist.md, and templates/commands/bootstrap.md that
  `/research` only applies to projects with existing code. For greenfield
  projects, start directly with `/plan`.

## [1.14.4] - 2026-04-04

### Added

- **Error #63:** Parallel agents each run full test suite, exhausting local
  resources. N agents x full suite = N x workers processes competing for CPU
  and memory. Agents must run scoped tests only; full suite runs once at
  integration.
- **Rule #73:** Parallel agents run scoped tests only -- full suite runs once
  at integration.

## [1.14.3] - 2026-04-03

### Changed

- **Sonnet tier commands** -- model tier headers now specify Sonnet 4.6 (1M context)
  instead of generic "Sonnet session". Affects `/implement`, `/validate`,
  `/remediate`, `/triage`, and `/fix-ci` in both `.claude/commands/` and
  `templates/commands/`.

## [1.14.2] - 2026-04-03

### Changed

- **Model tier annotations** -- all RPI commands now declare their model tier.
  `/research` and `/plan` are pinned to Opus; `/implement`, `/remediate`,
  `/validate`, `/fix-ci`, and `/triage` are pinned to Sonnet. Subagents
  spawned by each command carry explicit `model:` parameters. Reduces Max
  plan token consumption by ~64% for projects previously running all
  commands on Opus.

## [1.14.1] - 2026-03-28

### Changed

- **`/implement`** -- added EnterWorktree step: implementation now always
  runs in an isolated worktree, preventing conflicts with uncommitted work
  on main.

## [1.14.0] - 2026-03-28

### Added

- **`templates/rules/`** -- 5 rule template files for `.claude/rules/` conditional loading: `rpi-details.md` (always loaded), `push-accountability.md` (always loaded), `deployment-safety.md` (path-conditional), `supabase.md` (path-conditional), `testing.md` (path-conditional). Rules with `paths` frontmatter only load when Claude works with matching files -- true infrastructure-level conditional loading.
- **`templates/skills/error-patterns/`** -- New skill providing condensed top-20 error reference on demand. Agents no longer need to read the full 117K-char error catalog during onboarding. Full catalog remains available for deep debugging.

### Changed

- **CLAUDE.md template** -- context overhaul v2: reduced from 241 to 70 lines (71% reduction). All `<important if>` blocks migrated to `.claude/rules/` with `paths` frontmatter. Working Patterns section removed (already in skills). Always-loaded context reduced from ~10K to ~4.9K chars.
- **`/bootstrap`** -- no longer requires reading `agent-errors.md` during onboarding. Now installs `.claude/rules/` (stack-aware) and `error-patterns/` skill. Step numbering updated.
- **`/adopt`** -- adds `.claude/rules/` audit, `<important if>` migration guidance, rules installation step. CLAUDE.md lean guidance updated (~70 lines target).
- **`/update`** -- new Phase 4b syncs `.claude/rules/` (preserves custom paths, never deletes project rules). CLAUDE.md section list updated for v2 template. Sync metadata includes `rulesSynced`/`rulesCustom` fields.
- **Setup checklist** -- new "Authoring Principles" section (migrated from CLAUDE.md template comment block), new "Rules Setup" section, `error-patterns/` added to skills list.
- **cc-rpi CLAUDE.md** -- self-applied v2: reduced from 221 to 96 lines. RPI details, git recipes, and contributing guidelines moved to `.claude/rules/`. Repo structure updated with rules/ directories.
- **`patterns/agent-errors.md`** -- preamble updated to reference error-patterns skill; file is no longer mandatory onboarding reading.

## [1.13.0] - 2026-03-26

### Added

- **Rule #70: Never commit agent reports to the repository** -- `docs/agents/`, `logs/`, and `scripts/agents/` are gitignored in all projects (open-source and closed-source). Reports stay on disk as local operational history but never enter version control.
- **Rule #71: Use timestamp-based discovery for triage, not git status** -- triage now uses a `.last-triage` marker file and `find -newer` instead of `git status` for report discovery. Decouples the entire triage workflow from git tracking.
- **Rule #72** (renumbered from #69): Supabase migration local testing rule unchanged, renumbered to accommodate new rules.
- **Report Lifecycle** section in `methodology/scheduled-agents.md` -- codifies the separation between operational reports (local-only) and code fixes (committed). Includes required `.gitignore` entries.
- **`templates/scripts/agents/lib/agent-utils.sh`** -- shared utility library for all agent scripts. Handles environment setup, fd limits, auth preflight, logging, and shared context read/write/prune. Eliminates boilerplate duplication across agents.
- **`templates/scripts/agents/install-agents.sh`** -- automated launchd installer. Auto-discovers agent scripts via `# SCHEDULE:` comments, generates plists with all four launchd gotcha fixes, and installs/unloads/shows status.

- **8 domain skill templates** in `templates/skills/` -- progressive disclosure for operational rules. Skills: git-workflow, ci-workflow, deployment-safety, multi-agent, github-cli, python-rules, macos-rules, supabase. Each uses example-based format (wrong/right pairs) per Anthropic guidance that examples beat rule lists.

### Changed

- **CLAUDE.md template** -- context pressure optimization: always-loaded lines reduced from ~199 to ~152 (-24%). "Agent Operational Rules" section (43 lines of rule lists) replaced with "Working Patterns" section (4 canonical examples in `<examples>` tags). "Push Accountability" wrapped in `<important if>`. "Agent Autonomy" and "Memory Management" slimmed. "Conditional Blocks" guide moved to HTML comment. Skills reference added.
- **`patterns/quick-reference.md`** -- restructured with scope/stack/skill tags on every rule. Sections reorganized by domain (matching skills). Word count reduced 33% (2,950 to 1,975 words). LIKELY_KNOWN rules trimmed to one-liners per Anthropic Claude 4.6 guidance.
- **`/bootstrap`** -- now installs blueprint skills from `templates/skills/` (stack-aware).
- **`/adopt`** -- skills gap elevated to HIGH priority in audit report.
- **`/update`** -- new Phase 4 syncs skills (direct replacement). Blueprint-managed sections list updated for new template structure.
- **Setup checklist** -- new "Skills Setup" section. Scheduled agents section updated with `agent-utils.sh`, `install-agents.sh`, and gitignore steps.
- **`/triage` command** -- Step 1 rewritten: three-layer git-based scan replaced with timestamp-based discovery. Step 4 rewritten: two-commit strategy (reports + fixes) replaced with single commit (fixes only) plus `.last-triage` marker touch.
- **`morning-triage.sh`** -- both main and fallback prompts updated to reflect local-only reports and timestamp-based discovery.
- **Agent shell script template** in `methodology/scheduled-agents.md` -- now sources `lib/agent-utils.sh` instead of duplicating boilerplate. Uses `SHARED_CONTEXT_START/END` blocks and `# SCHEDULE:` comments.
- **Scheduling section** in `methodology/scheduled-agents.md` -- automated installation via `install-agents.sh` is now the recommended path for macOS launchd.

## [1.12.0] - 2026-03-25

### Added

- **Error #62: Agent pushes Supabase migration to remote without local testing** -- agent writes migration SQL and runs `supabase db push` directly without testing against the local Postgres instance. Migrations fail on remote, leaving the database in a partially migrated state. Solution: always run `supabase start` + `supabase db reset` locally, verify with `docker exec`, then push.
- **Rule #69: Always test Supabase migrations locally before pushing to remote** -- use the full local Supabase stack as UAT before pushing any migration. New "Supabase Rules" section in quick-reference.md.
- **Supabase migration safety** conditional block in CLAUDE.md template -- step-by-step local testing workflow with `supabase start`, `supabase db reset`, `docker exec` verification, and `supabase db push`.

## [1.11.1] - 2026-03-25

### Added

- **Error #61: Silent fallback masks production data failure** -- agent writes "resilient" code with graceful degradation (fallback data, default responses) but no observability. Fallback activates silently in production, serving placeholder content while hiding the real bug (e.g., missing database grants, expired API auth). Solution: every fallback path needs ERROR-level logging, health endpoint degraded state, and alerting.
- **Rule #68: Every fallback path must be observable** -- when writing fallback behavior, always add error logging, health check coverage, and monitoring hooks. Silent fallbacks are silent production bugs.
- **Supabase migration rules** in CLAUDE.md template conditional block -- every migration creating a public table must include `GRANT SELECT TO anon, authenticated`; `ALTER DEFAULT PRIVILEGES` belongs in the initial setup migration; fallback paths must log at ERROR level; health endpoints must check actual data access.

## [1.11.0] - 2026-03-25

### Added

- **Deployment Safety & Resource Efficiency** -- new patterns file (`patterns/deployment-safety.md`) codifying lessons from a real production incident where an agent merged 7 Dependabot PRs to `main`, triggered 80+ CI runs and 21 Vercel deployments, and took down a live site for 2+ hours. Includes deployment topology awareness, dependency risk assessment, production recovery protocol, and resource efficiency patterns.
- **Error #54: `git checkout --` fails on unmerged (conflicted) files** -- agent tries to discard changes with `git checkout --` during a merge/rebase/cherry-pick conflict; files are "unmerged" so plain checkout fails. Solution: use `--ours`/`--theirs` to pick a side, or abort the operation.
- **Error #55: `git merge` blocked by untracked working tree files** -- untracked files at the same paths as files in the branch being merged cause git to abort. Common in multi-agent workflows where main repo and worktree agents create files at the same paths. Solution: delete or move untracked copies before merging.
- **Error #56: Agent merges to `main` without understanding deployment topology** -- agent treats "clean up PRs" as "merge them" without checking that merging to `main` triggers production deployments. Dependabot PRs target `main` by default. Solution: cherry-pick to `develop`, close the Dependabot PR.
- **Error #57: Sequential merge cascade wastes CI resources** -- merging N PRs one-by-one with "require up-to-date" branch protection creates O(n^2) rebase cascades. 7 PRs x 9 workflows = ~189 unnecessary CI runs. Solution: batch all updates into a single PR.
- **Error #58: Agent deploys untested code to production** -- CI passing is not sufficient for framework upgrades. Build != Runtime. Local != Production. A Next.js minor bump crashed all Vercel serverless functions despite passing all CI checks. Solution: deploy to preview URL and verify before merging to `main`.
- **Error #59: Agent improvises production recovery with repeated failed deployments** -- agent panic-deploys during an outage, each failed attempt extending the downtime and costing money. Solution: roll back immediately, investigate on non-production, fix forward on `develop`.
- **Error #60: Agent treats all dependency updates as equal risk** -- applying uniform verification to framework upgrades and dev patches alike. A Next.js upgrade needs preview verification; a minimatch patch needs CI only. Solution: classify dependencies by risk level before merging.
- **Rules #60-#61** -- git conflict resolution quick-reference rules.
- **Rules #62-#67** -- deployment and resource efficiency rules covering: main=production, batch dependencies, cost awareness, preview verification, recovery protocol, and action justification. New "Deployment & Resource Efficiency Rules" section in quick-reference.md.
- **Updated CLAUDE.md template** -- added deployment safety conditional block for projects with CI/CD deployment pipelines.

## [1.10.0] - 2026-03-19

### Added

- **Rule #59: Wrap context-specific CLAUDE.md sections in `<important if="condition">` tags** -- as CLAUDE.md grows, conditional blocks give the agent explicit activation signals so domain-specific rules (testing, deployment, CI) only fire when relevant. Keeps universal content unwrapped. Added to `patterns/quick-reference.md` (Rule #59) and `templates/CLAUDE.md.template` (new "Conditional Blocks" section with examples and authoring guidance).
- **Session stability and prompt caching guidance** in `methodology/context-engineering.md` -- don't switch models mid-session (cache is per-model, switching to Haiku mid-Opus-session is more expensive, not less -- use subagents instead) and don't add/remove MCP tools mid-session (tools are part of the cached prefix, loading/unloading invalidates the cache). Both are counterintuitive behaviors that silently increase cost and latency.
- **Expanded skills authoring guide** in `methodology/agent-design.md` -- skills are folders (not just markdown files) with scripts, references, assets, and examples. Covers folder structure with progressive disclosure, SKILL.md format with gotchas section, 5 authoring principles (description for triggering, lead with gotchas, don't state the obvious, avoid railroading, include scripts), 9-category skill taxonomy (library reference, product verification, data fetching, business process, code scaffolding, code quality, CI/CD, runbooks, infrastructure ops), and on-demand hooks for situational guardrails. Updated `templates/setup-checklist.md` to reference the taxonomy and folder pattern.

## [1.9.0] - 2026-03-16

### Added

- **`/remediate` command** -- post-pre-launch remediation automation. Parses the pre-launch audit report, creates GitHub issues for every finding (100% coverage regardless of priority), spawns parallel worktree agents that follow TDD (write failing test, implement fix, verify, `/simplify`), merges PRs sequentially with test verification after each merge, runs a final `/simplify` on the integrated result, monitors CI, cleans up all worktrees and branches, and generates a remediation report. Completes the release cycle: `/pre-launch` -> `/remediate` -> `/update-docs` -> `/release`.
- **`/triage` command** -- morning agent report processing. Three-layer exhaustive discovery (git status + Glob + cross-reference) to find every report -- never misses one. Checks `logs/` for agent failures before analyzing reports. Reads all reports completely, synthesizes findings, drafts action plan for ALL items (fix everything, Rule #58), implements fixes, commits reports as historical artifacts separately from code fixes, updates shared-context.md, pushes, and monitors CI.
- **`morning-triage.sh` script template** -- multi-project orchestration. Configurable list of project directories, runs `/triage` in each sequentially, produces a cross-project summary. Archy-compatible for higher-level orchestration.
- **Rule #58: Fix everything, always** -- new core tenet and operational rule. Categorize findings by severity, but fix 100% of them. With AI agents, the cost of fixing is near-zero -- the old prioritization model of deferring low-priority items no longer applies. Added to `methodology/philosophy.md` (core tenet #9, key lesson #17) and `patterns/quick-reference.md` (Rule #58).

## [1.8.0] - 2026-03-14

### Added

- **`/release` command** -- project-type-flexible release automation. Detects project type (npm, Rust, Python, Go, docs-only) and branching strategy (main-only vs feature-branch). Bumps versions in all manifest files and references, generates CHANGELOG entry from categorized commits, creates release commit and annotated tag, publishes GitHub release, and advises on registry publish (npm/cargo/twine -- advisory only, never runs publish automatically). Bakes in error pattern guards (#20, #44, #53) and 3 human confirmation gates.
- **`/update-docs` command** -- comprehensive documentation refresh. Spawns 4 parallel read-only discovery agents (change analyst, documentation inventory, diagram analyzer, version reference scanner) to build an update plan from changes since the last release. After user approval, sequentially updates all markdown files, Mermaid diagrams, version badges/references, counts, and inline code docs (JSDoc, Python docstrings, Rust doc comments). Flags uncertain diagrams as `[NEEDS REVIEW]`. Saves report to `docs/agents/update-docs-report.md`.

## [1.7.0] - 2026-03-14

### Added

- **`/detach` command** -- clean removal of cc-rpi from a project. Inventories all blueprint artifacts in 4 tiers (scaffolding files, CLAUDE.md sections, configuration entries, user work products), previews exactly what will be removed, asks for confirmation, then executes in a single atomic commit. Preserves project-specific config and research/plan documents by default. Flags customized files for review before deletion. User-level command installed in `~/.claude/commands/detach.md`.

## [1.6.2] - 2026-03-14

### Fixed

- **Hooks schema in settings.json.template** -- PreToolUse entries used a flat `"command"` field instead of the required nested `"hooks"` array with `{"type": "command", "command": "..."}`. Every project bootstrapped since v1.4.0 had an invalid hook config that was silently ignored. Fixed in `templates/settings.json.template` and `methodology/ci-and-guardrails.md`.

### Added

- **Self-adoption** -- cc-rpi now follows its own RPI methodology. Added `.claude/commands/` (8 workflow commands), `.claude/hooks/guard-bash.sh` (Tier 1 enforcement), `.claude/settings.json`, and `docs/research/` + `docs/plans/` directories. CLAUDE.md rewritten to serve as both repo description and operational rules. Error #48 guard disabled in the local hook copy (main-only workflow).

## [1.6.1] - 2026-03-14

### Added

- **Error #53: Agent runs `gh pr create` without checking for existing PR** — `gh pr create` fails when a PR already exists for the head-to-base branch pair. Check with `gh pr list --head <branch>` first; if one exists, use `gh pr edit` to update it.

## [1.6.0] - 2026-03-13

### Added

- **Error #51: CI explosion from parallel agent pushes** — when N agents push independently, every push triggers M CI workflows (N x M x retries runs). New rule: worktree agents commit locally, main agent batch-pushes all branches in one command, creates all PRs, and monitors CI centrally. Added to `agent-errors.md` (Error #51), `quick-reference.md` (Rule #55), and `agent-design.md` (Parallel Agent Push Strategy section + worktree agent row in Central Commit Rule table).
- **Error #52: Agent assumes GitHub labels exist when creating issues** — `gh issue create --label "chore"` fails if label doesn't exist. Check with `gh label list` or create first. Especially common after `/pre-launch` audits creating multiple issues with category labels.
- **Project File Locations table** in `CLAUDE.md.template` — consolidated all fixed-path references (agent reports, logs, scripts, ADRs, PR descriptions, research docs, plans) into a single scannable table with a one-time "do not search" directive. Eliminates per-session token waste from agents searching for known locations.

## [1.5.0] - 2026-03-08

### Added

- **Errors #46–#50** — five new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #50–#54):
  - **#46:** Scaffolding tool fails on non-empty directory — `create-next-app` and similar tools abort when CLAUDE.md or `.claude/` already exists. Scaffold first, configure second.
  - **#47:** Piping API response to JSON parser without error checking — `curl | jq` crashes with unhelpful parse errors when API returns non-JSON. Save response and check HTTP status first.
  - **#48:** Agent commits or pushes to the wrong branch — doesn't verify current branch before committing. Guard hook now blocks direct push to main/master.
  - **#49:** Sub-agents create git conflicts from parallel work — overlapping file edits and orphaned references. Central commit rule: only the main agent handles git commit/push.
  - **#50:** Agent skips test suite after config changes — config changes have broader blast radius than code. Always run full suite immediately after config/infrastructure changes.
- **`/status` command** — quick 5-line project orientation (branch, last commit, working tree, CI status, open items). Addresses the ~40% empty session problem by giving users a fast check without starting a full task.
- **`/fix-ci` command** — self-healing CI that parses failure logs, spawns parallel fix agents per failure category, and iterates until green (max 3 cycles). Automates the manual diagnose-fix-verify loop.
- **Protected branch guard** in `guard-bash.sh` — blocks `git push origin main/master` unless it's a release flow with `--follow-tags`. Enforces Error #48 at Tier 1.
- **Git Protocol for Multi-Agent Work** section in `agent-design.md` — central commit rule, branch verification, file ownership for parallel agents, and branch strategy for agent orchestration.
- **Self-Healing CI** section in `push-accountability.md` — parallel fix agent pattern for multi-failure CI with retry budget and rules.
- **Branch verification and post-config test rules** in `CLAUDE.md.template` — two new Git Workflow rules and a sub-agent git centralization rule.

## [1.4.0] - 2026-03-05

### Added

- **Three-tier error prevention model** — documented in `methodology/ci-and-guardrails.md`. Rules graduate from Document (advisory) to Prompt (command recipes) to Enforce (hooks). Addresses the core architectural flaw: passive rules in CLAUDE.md don't prevent errors the agent has already been told about.
- **Agent tool hooks (Level 0 enforcement)** — `templates/hooks/guard-bash.sh` PreToolUse hook that blocks known-bad Bash patterns before execution. Currently enforces Error #33 (git pull --rebase with uncommitted changes) and Error #44 (git push --tags). Configured in `settings.json.template`.
- **Git command recipes** in `CLAUDE.md.template` — compound command sequences the agent copies as a unit instead of composing individual commands. Covers push sequence, first push, tag push, and worktree cleanup.
- **Errors #44–#45** — two new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #48–#49):
  - **#44:** `git push --tags` pushes ALL local tags — old tags cause push failure. Use specific tag names or `--follow-tags`.
  - **#45:** Agent fabricates filesystem paths — guesses directory names like `GenAI_Projects` instead of using working directory or discovering with `ls`.

## [1.3.0] - 2026-03-01

### Added

- **`/simplify` integration** — Anthropic's native code quality command (reuse, quality, efficiency) integrated into the RPI workflow. Runs after reviewer approval in `/implement`, recommended after `/pre-launch` audit, and suggested by `/validate` for quality findings. Added to the atomic loop, agent-design catalog, and quick-reference rules (39, 42).
- **`/batch` integration** — Anthropic's native parallel execution command integrated into the planning and implementation workflow. Plans now mark independent phases as `[batch-eligible]`, and `/implement` offers `/batch` for parallel phase execution. Added to agent-design catalog and quick-reference rules (40, 41).
- **Two-layer review model** — Implementation phases now separate plan-compliance review (reviewer subagent) from code-quality review (`/simplify`). Documented in `four-phases.md`, `agent-design.md`, and `CLAUDE.md.template`.
- **Batch eligibility assessment** — Plans must evaluate phase independence and mark `[batch-eligible]` where applicable. Added to plan completion criteria in `four-phases.md` and example in `implementation-plan.md`.
- **Rules #39–#42** in `quick-reference.md` — Native Command Rules covering `/simplify` and `/batch` usage patterns.
- **Post-adoption baseline audit** — `/adopt` now recommends running `/pre-launch` after setup for a full codebase quality baseline, followed by `/simplify` for auto-fixes.
- **Errors #39–#43** — five new agent error patterns added to `agent-errors.md` and `quick-reference.md` (rules #43–#47):
  - **#39:** `gh` CLI fails with "Projects (classic) deprecated" GraphQL error — upgrade `gh` to latest version
  - **#40:** Agent uses bare `python3` instead of `uv run python` — bypasses venv, causes ModuleNotFoundError
  - **#41:** Over-escaping `!=` as `\!=` in inline Python — SyntaxError from line continuation character
  - **#42:** Python script fails with ModuleNotFoundError — package-relative imports need `-m` flag
  - **#43:** Agent indexes JSON list with string key — TypeError from assuming dict structure

### Changed

- **Emoji removal** — all emoji characters removed from documentation, replaced with text equivalents.

## [1.2.0] - 2026-02-23

### Added

- **`/update` command** — user-level slash command for syncing projects with the latest cc-rpi blueprint. Uses incremental git-diff detection via `.claude/cc-rpi-sync.json`, updates commands (direct replacement), CLAUDE.md (smart merge of blueprint-managed sections), and settings.json (additive merge). Works both interactively and headlessly for scheduled agents.
- **Blueprint sync scheduled agent** (`templates/scripts/cc-rpi-update-agent.sh`) — shell script template for nightly automated syncing. Reads update instructions from cc-rpi at runtime (self-updating). Includes retry logic, launchd scheduling templates, and preflight checks.
- **Blueprint Sync section** in `setup-checklist.md` — step-by-step setup for nightly syncing with explanation of the three-tier update strategy.
- **Memory Management section** in `CLAUDE.md.template` — new blueprint-managed section that instructs agents to proactively save operational lessons (CI patterns, workarounds, environment quirks) to auto memory without being asked.
- **Memory-save phase** in `/bootstrap` and `/adopt` commands — Phase 4 (bootstrap) and Phase 5 (adopt) now require agents to save all key decisions, project context, and internalized rules to auto memory after setup, so future sessions start with full awareness.
- **Errors #22–#25** — four new agent error patterns added to `agent-errors.md` and `quick-reference.md`:
  - **#22:** `rm` fails on stale file list — agent operates on memorized filenames without re-reading directory
  - **#23:** `gh` commands fail when agent fabricates/guesses repo names, branch names, or identifiers
  - **#24:** Cross-project `../` relative paths fail because Bash cwd resets between calls
  - **#25:** `git pull --rebase` fails on branches with no upstream tracking — use `git push -u` first

## [1.1.0] - 2026-02-23

### Added

- **Errors #16–#21** — six new agent error patterns added to `agent-errors.md` and `quick-reference.md`:
  - **#16:** Commands fail because dependencies aren't installed (fresh worktrees/clones missing node_modules)
  - **#17:** jq syntax error from over-escaping `!=` as `\!=` inside single-quoted filters
  - **#18:** Git commands fail on repos with no commits yet (bootstrap scenario)
  - **#19:** API content filter blocks parallel boilerplate file creation
  - **#20:** `gh release create` uses `--notes`, not `--body` (wrong flag name across subcommands)
  - **#21:** `pip3 install` fails on macOS with Homebrew Python 3.12+ (externally-managed-environment)

### Fixed

- Removed hardcoded local paths from template commands (`/bootstrap`, `/adopt`)
- Replaced hardcoded GitHub username in template Chapa badge URLs with `[OWNER]` placeholder
- Genericized personal references in `CLAUDE.md` for public consumption
- Removed unused GitHub Sponsors configuration

## [1.0.0] - 2026-02-21

### Added

- **Human-readable guide** (`GUIDE.md`) — standalone walkthrough of philosophy, workflow, command cheat sheet, and practical tips. Designed for humans, articles, and NotebookLM podcasts.
- **`/bootstrap` command** — user-level slash command for setting up new projects from scratch. Reads the blueprint, asks about project type and stack, creates all configuration.
- **`/adopt` command** — user-level slash command for migrating existing projects. Audits configuration, infrastructure, and workflow with parallel agents, presents prioritized gap report, migrates incrementally with user approval.
- **Worked examples directory** (`examples/`) — sample research document, implementation plan with phase files, error/success log entries, and pseudocode notation examples.
- **Phase completion criteria** — "done when" / "NOT done if" checklists for all four RPI phases in `four-phases.md`.
- **Failure recovery decision trees** — 6 recovery flows (wrong research, plan-reality mismatch, CI failures, subagent conflicts, scheduled agent crashes, validation issues) in `four-phases.md`.
- **Phase handoff templates** — structured handoff documents with YAML frontmatter, what carries over vs starts fresh, and 4 resume scenarios (clean continuation, diverged codebase, incomplete work, stale handoff) in `four-phases.md`.
- **Function stakes framework** — 5-level classification (read-only through critical) with approval requirements and fallback behavior in `agent-design.md`.
- **Precise autonomy boundaries** — 14-action decision table for agent autonomy in `agent-design.md`.
- **Subagent quick reference table** — all 10 roles mapped to Claude Code `subagent_type` parameters in `agent-design.md`.
- **Documentarian rule examples** — 3 pairs of good/bad examples in `agent-design.md`.
- **Agent Teams as default** — enabled via `settings.json.template`, documented in `agent-design.md` and `context-engineering.md` with architecture, comparison to subagents, and limitations.
- **Compaction examples** — good/bad compaction, discard-vs-preserve table, and `run_silent` micro-compaction pattern in `context-engineering.md`.
- **Hooks documentation** — configuration examples and common patterns in `context-engineering.md`.
- **Error/success log storage** — directory structure, index file pattern, when to query logs, graduation-to-rules workflow, and compression philosophy in `error-success-logging.md`.
- **Concrete scheduled agent prompts** — test-health, security-audit, code-quality, dependency-health with full prompt templates in `scheduled-agents.md`.
- **Scheduled agent resilience** — retry logic, WIP limits, and stagger schedule table in `scheduled-agents.md`.
- **`settings.json.template`** — shared settings with Agent Teams, hooks, and permission whitelist.
- **`README-header.md`** — standard README header template with badges and Chapa embed.
- **Project-type adaptation** — setup guidance for 6 archetypes (web app, library, CLI, monorepo, Python, static site) in `setup-checklist.md`.
- **Shared vs local configuration** — documented CLAUDE.md/CLAUDE.local.md and settings.json/settings.local.json split pattern in `setup-checklist.md`.
- **Workflow walkthroughs** (`examples/workflows/`) — three end-to-end developer interaction examples showing exact commands, agent responses, and decision points: bootstrapping a new project, adding a new feature (rate limiting), and refactoring existing code (auth service extraction).
- **Error #15: `git branch -d` on worktree branches** — new pattern added to `agent-errors.md` and `quick-reference.md`. Always use uppercase `-D` for worktree branch cleanup.

## [0.1.0] - 2026-02-20

### Added

- RPI (Research-Plan-Implement) methodology adapted for Claude Code
  - Philosophy, context engineering, four phases, agent design
  - Pseudocode notation format for implementation plans
  - Testing and error/success logging frameworks
  - Push accountability — post-push CI ownership protocol with background polling and fix-and-repush cycle (`methodology/push-accountability.md`)
  - CI & guardrails — pre-commit hooks, CI workflows, development guardrails, enforcement stack (`methodology/ci-and-guardrails.md`)
  - Scheduled agents — recurring quality agents on cron/launchd with shared context system (`methodology/scheduled-agents.md`)
  - TDD protocol — Red-Green-Refactor cycle integrated into testing.md
  - Agent team patterns — 6 team scenarios (debug, pre-launch audit, self-healing, health check, feature implementation, code review) in agent-design.md
  - Agent autonomy principles — tool exhaustion rule, autonomy boundaries, self-correction over escalation in agent-design.md
  - Claude settings & permissions — permission whitelisting, environment variables, model selection in context-engineering.md
- Known agent error patterns catalog (`patterns/agent-errors.md`)
  - Errors 12-14: push-and-forget, skipping TDD, suggesting manual steps
- Quick reference operational rules (`patterns/quick-reference.md`)
  - Rules 12-14: CI monitoring, TDD, tool exhaustion
- Project templates
  - CLAUDE.md template with push accountability, TDD, and autonomy sections
  - Setup checklist with pre-commit hooks, CI setup, push accountability, and scheduled agents
  - Slash commands: `/research`, `/plan`, `/implement`, `/validate`, `/describe-pr`, `/pre-launch`
- Open source project scaffolding (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY)
