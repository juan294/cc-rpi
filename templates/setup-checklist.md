# New Project Setup Checklist

Use this when setting up a new project to follow cc-rpi best practices.

## README Header

- [ ] Structure the project README with a standard header:
  1. `# Project Name — Tagline`
  2. GitHub badges (CI, Security Scan, Secret Scanning, stack versions, and optionally license if open source)
  3. One-line project description
  4. Horizontal divider (`---`)
  5. Rest of the README content below the divider
- [ ] Adjust badge URLs to match the project's GitHub owner/repo
- [ ] Add or remove stack badges as relevant (TypeScript, Node.js, Next.js, Python, etc.)

## Directory Setup

- [ ] Create `CLAUDE.md` at project root (adapt from `CLAUDE.md.template`)
  - Manually craft every line — don't auto-generate with `/init`
  - Keep it lean: only universally applicable instructions
- [ ] Create `AGENTS.md` at project root (adapt from `AGENTS.md.template`)
  - This is the Codex/OpenCode compatibility layer for cc-rpi projects
  - Point Codex and OpenCode at `CLAUDE.md`, `.claude/commands/`,
    `.claude/rules/`, and `.claude/skills/` as the source of truth
  - Keep Codex-only helpers that would collide with Claude-native
    commands out of `.claude/skills/`
  - Keep it focused on workflow translation, not duplicate project docs
- [ ] Create `.claude/commands/` and copy slash commands from `templates/commands/`
- [ ] Create `.opencode/commands/` and copy wrapper commands from
  `templates/opencode/commands/`
  - Keep these wrappers thin; they should delegate back to
    `.claude/commands/*.md`
  - Do not duplicate the workflow text into OpenCode-only command files
- [ ] Create `opencode.json` at project root
  - Adapt from `templates/opencode.json.template`
  - Load `CLAUDE.md` and `.claude/rules/*.md` through `instructions`
  - Keep command discovery in `.opencode/commands/`
- [ ] Create `.claude/skills/` for domain-specific knowledge (loaded on demand):
  - Each skill is a **folder** with a `SKILL.md` entry point, plus optional `references/`, `scripts/`, `examples/`, `assets/` subdirectories
  - Start with library reference and code quality skills (highest immediate value)
  - See `methodology/agent-design.md` "Skill Categories" for the full taxonomy
  - Skills keep CLAUDE.md lean while giving Claude access to specialized knowledge
- [ ] Create `.claude/agents/` for custom subagent definitions (optional):
  - e.g., `security-reviewer.md`, `performance-analyzer.md`
  - Define tool restrictions and model per agent
- [ ] Create `docs/` directory with subdirectories:
  - `docs/research/` — Research documents
  - `docs/plans/` — Implementation plans
  - `docs/decisions/` — Architecture decision records
- [ ] Configure `.claude/settings.json` (adapt from `templates/settings.json.template`):
  - Enable Agent Teams: `"env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }`
  - Configure hooks for file edits and pre-commit (deterministic enforcement)
  - Pre-approve common tool permissions to reduce prompts (especially for teammates)
  - Hooks are deterministic (guaranteed to run), unlike CLAUDE.md instructions (advisory)
- [ ] Add `.claude/settings.local.json` to `.gitignore`:
  - This is the personal/local counterpart to `settings.json` (which is committed and shared)
  - Use for: individual permission overrides, personal API keys, local tool paths
  - Claude Code merges both files, with `settings.local.json` taking precedence

### Shared vs Local Configuration

Two file pairs follow the same split pattern:

| Shared (committed) | Local (gitignored) | Purpose |
|--------------------|--------------------|---------|
| `CLAUDE.md` | `CLAUDE.local.md` | Project instructions vs personal preferences |
| `.claude/settings.json` | `.claude/settings.local.json` | Team permissions/hooks vs individual overrides |

**`CLAUDE.md`** — Team-wide rules: RPI workflow, operational rules, git conventions, key commands. Every developer and agent sees the same instructions. Checked into version control.

**`CLAUDE.local.md`** — Personal preferences and local context: your preferred verbosity level, local paths, personal workflow notes, task-specific context you don't want to pollute the shared file with. Gitignored. Optional.

**`settings.json`** — Shared tool permissions, hooks, Agent Teams env var. Committed.

**`settings.local.json`** — Personal permission overrides (e.g., broader `Bash(*)` for your machine), local env vars. Gitignored.

**`AGENTS.md`** — Codex/OpenCode compatibility bridge. Teaches those
agents how to interpret the existing cc-rpi layout (`CLAUDE.md`,
`.claude/commands/`, `.claude/rules/`, `.claude/skills/`) without
changing the methodology. Committed.

**`opencode.json`** — OpenCode instruction loader. Pulls `CLAUDE.md`
and `.claude/rules/*.md` into OpenCode without duplicating the content
in `AGENTS.md`. Committed.

## CLAUDE.md Configuration

### Authoring Principles

- Keep CLAUDE.md **LEAN** -- loaded every session,
  only universally applicable instructions.
- Budget: ~100 usable instruction slots.
  System prompt uses ~50. Don't waste them.
- Test: "Would removing this line cause mistakes?"
  If not, cut it.
- Domain rules go in `.claude/rules/` (conditional loading)
  and `.claude/skills/` (on-demand knowledge).
  Don't duplicate their content in CLAUDE.md.
- Use `.claude/rules/` with `paths` frontmatter for rules
  that only apply when working with specific file types.
- Manually craft every line --
  don't auto-generate with `/init`.

### Checklist

- [ ] Fill in project name, description, and stack
- [ ] Document build/test/lint commands
- [ ] Document deployment pipeline (which branch deploys where)
- [ ] Document git workflow (integration branch, production branch,
  implementation isolation)
- [ ] Add project-specific context (key routes, data types, code ownership)
- [ ] Keep `AGENTS.md` aligned with the project's workflow conventions:
  - Slash-style commands dispatch to `.claude/commands/*.md`
  - OpenCode slash-style commands dispatch via `.opencode/commands/*.md`
    wrappers back to `.claude/commands/*.md`
  - `.claude/rules/` remains the rule source of truth
  - `.claude/skills/` remains the skill source of truth
  - Claude-native commands (`/simplify`, `/batch`, `/worktree`) are
    translated to Codex/OpenCode-equivalent behavior
  - Codex-only helpers that would shadow native Claude commands stay in
    `~/.codex/skills/`, not `.claude/skills/`

## Slash Commands

Copy and adapt from `templates/commands/`:
- [ ] `/research` — Codebase research with parallel subagents
- [ ] `/plan` — Interactive plan creation with phases
- [ ] `/implement` — Phase-by-phase execution with review gates
- [ ] `/validate` — Post-implementation verification
- [ ] `/describe-pr` — PR description generation
- [ ] `/remediate` — Fix all pre-launch findings with parallel TDD agents
- [ ] `/triage` — Morning agent report processing and action

Adjust file paths in each command to match your project's docs directory.

- [ ] Read the local command-bundle manifests before large command sync or
  setup changes:
  - `templates/commands/INSTALL.md`
  - `templates/commands/VERIFY.md`

For Codex compatibility, `AGENTS.md` should instruct Codex to treat each
file in `.claude/commands/` as the workflow spec when the user invokes
the matching slash-style command.

For OpenCode compatibility, each file in `.opencode/commands/` should be
a thin wrapper that points back to the matching file in
`.claude/commands/`.

**Slash commands vs skills:** Commands (`.claude/commands/`) are user-invoked workflows. Skills (`.claude/skills/`) are knowledge + workflows that Claude can also auto-detect. Use commands for RPI phases; use skills for domain conventions and reusable task patterns.

## Skills Setup

- [ ] Create `.claude/skills/` directory
- [ ] Copy blueprint skills from `cc-rpi/templates/skills/` to `.claude/skills/`:
  - Always: `git-workflow/`, `multi-agent/`, `deployment-safety/`, `ci-workflow/`, `github-cli/`, `error-patterns/`
  - Python projects: also `python-rules/`
  - macOS development: also `macos-rules/`
  - Supabase projects: also `supabase/`
- [ ] Review installed skills -- remove any that don't apply to your stack
- [ ] Add project-specific skills as needed (see `methodology/agent-design.md` for the skill taxonomy)

### Codex-Only Skill Setup (Optional)

- [ ] Do not create a project skill literally named `simplify` in a
  Claude-compatible repo
- [ ] If Codex users want a `/simplify` equivalent, copy
  `cc-rpi/.codex/skills/codex-simplify/` to
  `~/.codex/skills/codex-simplify/`
- [ ] In `AGENTS.md`, state explicitly that Claude keeps native
  `/simplify` while Codex users invoke `codex-simplify`

## Rules Setup

- [ ] Create `.claude/rules/` directory
- [ ] Copy rule templates from `cc-rpi/templates/rules/`:
  - Always: `rpi-details.md`, `push-accountability.md`
  - Deployment pipelines: `deployment-safety.md`
  - Supabase projects: `supabase.md`
  - Projects with tests: `testing.md`
- [ ] Review `paths` frontmatter in conditional rules --
  adjust globs to match your project's file structure
- [ ] Add project-specific rules as needed
  (e.g., API conventions, database patterns)

## Agent Tool Hooks

- [ ] Create `.claude/hooks/` directory
- [ ] Copy `guard-bash.sh` from `templates/hooks/guard-bash.sh` to `.claude/hooks/guard-bash.sh`
- [ ] Verify `jq` is installed (`brew install jq` on macOS)
- [ ] Hooks configuration is already in `settings.json.template` — verify it was copied to `.claude/settings.json`
- [ ] Test: make a trivial edit, then run `echo '{"tool_name":"Bash","tool_input":{"command":"git pull --rebase"}}' | bash .claude/hooks/guard-bash.sh` (should print BLOCKED)
- [ ] Add project-specific guards to the bottom of the script (e.g., bare `python3` for uv projects)

## Pre-Commit Hooks

- [ ] Install a hook framework (e.g., Husky for Node.js, pre-commit for Python)
- [ ] Configure pre-commit to run typecheck + lint:
  ```bash
  # Example: Husky
  npx husky init
  echo "pnpm run typecheck && pnpm run lint" > .husky/pre-commit
  ```
- [ ] Test that the hook rejects a commit with a deliberate type error
- [ ] Add a note to CLAUDE.md reminding agents to run checks before committing

## CI Setup

- [ ] Create a CI workflow (GitHub Actions, etc.) that runs on push and PR:
  - Typecheck
  - Lint
  - Unit tests
  - Build verification
  - (Optional) Security audit, E2E tests
- [ ] Mark critical CI jobs as required for PR merges
- [ ] Enable branch protection on the production branch (require CI + review)
- [ ] Verify CI runs successfully on the chosen integration branch

## Git Setup

- [ ] Choose a documented branch topology:
  - `main-only` — `main` is the long-lived integration branch, and may
    also be the production branch
  - `develop/main` — `develop` is integration, `main` is production
- [ ] Document the integration branch in `CLAUDE.md`
- [ ] Document the production branch in `CLAUDE.md` (or state that the
  repo has no separate production branch)
- [ ] Require implementation to happen in worktrees or temporary
  branches regardless of topology
- [ ] Set up branch protection rules on GitHub
- [ ] Configure pre-commit hooks (typecheck, lint, test) — see
  Pre-Commit Hooks above

## Push Accountability

- [ ] Add push accountability instructions to CLAUDE.md or CLAUDE.local.md:
  - After every push to the branch under active CI verification,
    spawn a background CI monitor
  - Background agent polls, investigates failures, fixes, and re-pushes
  - Main terminal stays unblocked
- [ ] Test the workflow: push a deliberate failure, verify the background agent catches it

## Blueprint Sync (Recommended)

Set up nightly syncing with the cc-rpi blueprint so this project automatically stays current with new rules, error patterns, and command improvements.

- [ ] Install the `/update` command as a user-level command (`~/.claude/commands/update.md`)
- [ ] Run `/update` once manually to verify it works and create the initial `.claude/cc-rpi-sync.json`
- [ ] Copy the scheduled agent script from `cc-rpi/templates/scripts/cc-rpi-update-agent.sh` to `scripts/agents/cc-rpi-update.sh`
- [ ] Set `CC_RPI_PATH` in the script to your cc-rpi clone location
- [ ] Make it executable: `chmod +x scripts/agents/cc-rpi-update.sh`
- [ ] Create required directories: `mkdir -p docs/agents logs`
- [ ] Run `claude setup-token` from an interactive terminal (required for non-interactive auth under launchd/cron)
- [ ] Ensure your launchd plist has `HardResourceLimits`/`SoftResourceLimits` (NumberOfFiles: 122880), `EnvironmentVariables` (HOME, TERM, PATH), and ProgramArguments uses `/bin/bash -c "exec /bin/bash <script>"` wrapper — see script comments for the full plist template
- [ ] Schedule with launchd (macOS) or cron (Linux) — see script comments for templates
- [ ] Test with `launchctl start <label>` (not by running the script from a terminal — terminal execution masks launchd issues)
- [ ] Check `docs/agents/cc-rpi-update-report.md` and `logs/cc-rpi-update.error.log` for results

### How It Works

The sync uses `.claude/cc-rpi-sync.json` to track the last synced commit. On each run, it:
1. Pulls the latest cc-rpi
2. Uses `git diff` to identify what changed since last sync (efficient — no full re-read)
3. Updates slash commands (direct replacement from templates)
4. Updates the Codex compatibility layer in `AGENTS.md`
5. Updates blueprint-managed CLAUDE.md sections (smart merge — preserves project-specific content)
6. Adds new settings.json permissions (additive — never removes project-specific entries)
7. Commits changes with `chore: sync with cc-rpi blueprint <version>`

The shell script reads update instructions from cc-rpi at runtime, so when cc-rpi improves the `/update` command, all projects automatically get the new logic.

## Scheduled Agents (Optional)

- [ ] Create `scripts/agents/` and `scripts/agents/lib/` directories
- [ ] Read the local scheduled-agent manifests before installing:
  - `templates/scripts/agents/INSTALL.md`
  - `templates/scripts/agents/VERIFY.md`
- [ ] Copy `lib/agent-utils.sh` from `cc-rpi/templates/scripts/agents/lib/agent-utils.sh` to `scripts/agents/lib/`
- [ ] Copy `install-agents.sh` from `cc-rpi/templates/scripts/agents/install-agents.sh` to `scripts/agents/`
- [ ] Create `docs/agents/` directory for agent reports and shared context
- [ ] Create `logs/` directory for agent output capture
- [ ] **Gitignore all agent operational directories** (Rule #70 — reports are never committed):
  ```gitignore
  # Agent operational output (never committed)
  docs/agents/
  logs/
  scripts/agents/
  ```
  This applies to ALL projects — open-source and closed-source alike. Reports stay on disk for historical access but never enter version control.
- [ ] Write at least one agent script (e.g., test-health, security-audit) — source `lib/agent-utils.sh` and add a `# SCHEDULE:` comment
- [ ] Run `claude setup-token` for non-interactive auth (required for launchd/cron)
- [ ] Install agents: `bash scripts/agents/install-agents.sh` (auto-generates plists from `# SCHEDULE:` comments)
- [ ] Test with `launchctl start` (macOS) — don't test from a terminal, it masks launchd issues
- [ ] Check status: `bash scripts/agents/install-agents.sh --status`
- [ ] Verify the agent produces a report in `docs/agents/`
- [ ] Add `/pre-launch` slash command for multi-agent production audit
- [ ] Add `/triage` slash command for morning agent report processing
- [ ] (Optional) Set up `morning-triage.sh` for multi-project orchestration

## Workflow Habits

- [ ] Always `/research` before `/plan` (except greenfield —
  no code means nothing to research; start with `/plan`)
- [ ] Always `/plan` before `/implement`
- [ ] Always review plans before approving
- [ ] Mark independent plan phases as `[batch-eligible]` during `/plan`
- [ ] Never skip the human confirmation gate between implementation phases
- [ ] Always run `/simplify` after reviewer approval during `/implement`
- [ ] Use `/batch` for independent phases and bulk migrations
- [ ] Use `/validate` after implementation
- [ ] Run `/remediate` after `/pre-launch` to fix all findings with parallel agents
- [ ] Run `/triage` every morning to process overnight agent reports
- [ ] Use `/clear` between unrelated tasks to reset context
- [ ] Run each RPI phase in its own conversation
- [ ] Research and plan against the integration branch; implement in
  worktrees
- [ ] Read research output critically — throw out and redo if wrong
- [ ] Invest most review time on research and plans, not generated code
- [ ] For large features, have Claude interview you before planning (AskUserQuestion)
- [ ] Follow TDD: write failing tests before implementation code
- [ ] Monitor CI after every push — never push and forget
- [ ] Keep the methodology stable across agents:
  - Claude Code uses `.claude/commands/`, `.claude/rules/`,
    `.claude/skills/`
  - OpenCode uses `AGENTS.md`, `opencode.json`, `.opencode/commands/`,
    and also understands `.claude/skills/`
  - Codex uses `AGENTS.md` to interpret those same artifacts
  - The workflow stays the same; only the harness translation changes

## Project-Type Adaptation

The defaults above assume a web application. Adapt these sections based on your project type:

### Web Application (default)

The standard setup applies as-is. Choose either a `main-only` or a
`develop/main` topology, then document which branch is integration and
which branch deploys to production. Typical stack badges: framework
(Next.js, Remix), runtime (Node.js), language (TypeScript). Add a
license badge only if the project is open source.

### Library / npm Package

- **Git workflow:** `main-only` is often simplest if releases are tagged
  from `main`, but implementation still happens in worktrees or
  temporary branches
- **CI additions:** Add `npm pack` or `pnpm pack` verification, publish dry-run
- **Testing:** Prioritize unit tests and type-level tests. Add consumer integration tests (test the package from a downstream project's perspective)
- **CLAUDE.md:** Document the public API surface. Add "do not change exports without a major version bump" rule
- **Pre-commit:** Add `publint` or `arethetypeswrong` checks if publishing types
- **Badges:** Add npm version badge, bundle size badge

### CLI Tool

- **CI additions:** Test the CLI binary end-to-end (invoke the compiled CLI with test args, assert output)
- **Testing:** Focus on integration tests (stdin/stdout/stderr/exit codes) over unit tests
- **CLAUDE.md:** Document all commands and flags. Add "ESM CLI files use shebang — never run with `node`, use `chmod +x && ./cli` or `npx .`"
- **Pre-commit:** Add smoke test (run `./cli --help` and assert exit 0)

### Monorepo

- **Git workflow:** Use the same explicit topology choice as the base
  project (`main-only` or `develop/main`), but CI runs per-package with
  change detection
- **CI additions:** Use `turbo`/`nx` affected detection. Only run checks for changed packages
- **CLAUDE.md:** Document the workspace structure, how packages depend on each other, which package owns which feature
- **Pre-commit:** Run typecheck across ALL workspace packages (not just changed ones — cross-package type errors are common)
- **Worktrees:** Extra caution — worktrees with monorepos can have `node_modules` issues. Document `pnpm install` in worktree setup
- **Agent Teams:** Monorepos are ideal for teams — each teammate owns a different package

### Python Project

- **Pre-commit hooks:** Use the `pre-commit` framework (not Husky). Configure with `.pre-commit-config.yaml`
- **Key commands:** Replace `pnpm run *` with equivalents: `pytest`, `mypy .`, `ruff check .`, `ruff format --check .`
- **CI additions:** Add `pip audit` for dependency security, `mypy` for type checking
- **CLAUDE.md:** Document virtual environment setup. Add `{ encoding: 'utf-8' }` note for subprocess calls
- **Permissions:** Update settings.json to allow `Bash(python *)", "Bash(pytest *)", "Bash(pip *)`

### Static Site / Documentation

- **Git workflow:** `main-only` is often enough for simple sites, but
  implementation should still happen in worktrees or temporary branches
- **CI:** Build verification + link checking + image optimization check
- **Testing:** Minimal — focus on build success and broken link detection
- **CLAUDE.md:** Keep lean. Document build command, content directory structure, frontmatter conventions

## Thoughts Directory Structure

```
docs/
├── research/                  # Research documents
│   └── YYYY-MM-DD-topic.md
├── plans/                     # Implementation plans
│   ├── YYYY-MM-DD-feature.md  # Main plan
│   └── YYYY-MM-DD-feature-phases/
│       ├── phase-1.md
│       └── phase-2.md
├── decisions/                 # ADRs / decision records
└── prs/                       # PR descriptions
    └── {number}_description.md
```
