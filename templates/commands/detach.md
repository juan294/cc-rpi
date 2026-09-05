# Detach Project from cc-rpi Blueprint

Model tier: **sonnet** — Sonnet 5 (1M context) session.

You are cleanly removing cc-rpi artifacts from this project. The blueprint lives at `<path-to-your-cc-rpi-clone>/`.

This command removes all blueprint-managed files and configuration while preserving project-specific content and user work products.

## Phase 1: Verify Adoption

1. Check for `.claude/cc-rpi-sync.json` or RPI commands in `.claude/commands/` (research.md, plan.md, implement.md, validate.md).
2. If neither exists: report "This project doesn't appear to use cc-rpi. Nothing to detach." and **stop**.
3. If sync metadata exists, read it and report the current blueprint version and last sync date.

## Phase 2: Inventory Artifacts

Scan this project for all cc-rpi artifacts. Categorize each into one of four tiers.

### Tier 1: Candidate blueprint scaffolding (prove ownership before removal)

Check for these files and note which exist:

- Managed blocks within `AGENTS.md` (never the whole file)
- `.claude/commands/research.md`
- `.claude/commands/plan.md`
- `.claude/commands/implement.md`
- `.claude/commands/validate.md`
- `.claude/commands/describe-pr.md`
- `.claude/commands/pre-launch.md`
- `.claude/commands/status.md`
- `.claude/commands/fix-ci.md`
- `.claude/commands/explore-release.md`
- `.claude/hooks/guard-bash.sh`
- `.claude/cc-rpi-sync.json`
- `scripts/agents/cc-rpi-update.sh` (nightly sync agent, if exists)

For each candidate, compare against its recorded installed baseline to establish ownership and customization. A filename or match to today's template is insufficient proof. Missing baseline means retain and report.

For `AGENTS.md`, identify owned blocks from recorded baseline bytes or explicit managed markers. Preserve the file and all user content; unknown ownership is retained and reported.

For `guard-bash.sh`, check if content exists below the `# Project-specific guards below this line` marker. If so, mark as "customized."

### Tier 2: Blueprint-managed CLAUDE.md sections

Read the project's CLAUDE.md and AGENTS.md. The following headers are inventory hints only, never proof of ownership. Remove only content established as owned by baseline bytes or explicit managed markers:

- `## RPI Workflow` (including all `###` subsections under it)
- `## Working Patterns` (including `<examples>` blocks under it)
- `## TDD Protocol`
- `## Agent Autonomy`
- `## Memory Management`
- `## Project File Locations`
- `<important if>` blocks: Push Accountability, Deployment Safety, Supabase sections

Note which sections exist. Do NOT touch any other sections -- they are project-specific.

### Tier 3: Configuration entries

Read `.claude/settings.json` and identify:

- `hooks.PreToolUse` entries referencing `guard-bash.sh` -- remove only proven-owned unchanged registrations
- `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` -- will flag for user decision
- All other entries (permissions, project-specific hooks, other env vars) -- will keep

Check for a launchd plist for the cc-rpi update agent:

- `~/Library/LaunchAgents/*cc-rpi*` or `~/Library/LaunchAgents/*blueprint*`

### Tier 4: User work products

Check for and count files in:

- `docs/research/` -- research documents
- `docs/plans/` -- implementation plans
- `docs/decisions/` -- architecture decision records
- `docs/agents/` -- agent reports
- `logs/` -- agent logs

These are the user's intellectual work. Default is to **keep** them.

## Phase 3: Preview Report

Present the full inventory to the user:

```text
== Detach Preview ==

Blueprint version: <version> (synced <date>)

WILL REMOVE (blueprint scaffolding):
  [list each Tier 1 file that exists, with "unmodified" or "customized" tag]

WILL EDIT (CLAUDE.md):
  Remove sections: [list each Tier 2 section found]
  Keep sections: [list remaining sections]

WILL CLEAN (settings.json):
  Remove: [list Tier 3 entries to remove]
  Keep: [list what stays]

WILL KEEP (your work):
  [list Tier 4 directories with file counts, or "none found"]

CUSTOMIZED FILES (review recommended):
  [list retained custom/unknown files and blocks with preservation reasons]
```

If no customized files exist, omit the CUSTOMIZED FILES section.

## Phase 4: Confirm and Execute

Ask the user three questions:

1. **"Proceed with detach?"** -- required. If no, stop.
2. **"Remove research docs and plans too?"** -- default: no. Only remove Tier 4 if user explicitly says yes.
3. **"Keep Agent Teams enabled?"** -- if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` exists. Default: keep.

Keep customized and unknown files by default. A detach request does not authorize deletion of user-owned content.

Then execute in order:

1. Preserve recovery copies outside disposable state. Delete only proven-owned,
   unchanged Tier 1 files. Keep AGENTS.md and remove only its proven-owned blocks.
2. Remove only proven-owned unchanged Tier 2 blocks. Keep custom additions even
   under familiar headers; retain unresolved blocks instead of deleting by heading.
3. Clean Tier 3 configuration:
   - Remove only proven-owned unchanged hook registrations for guard-bash.sh from `.claude/settings.json`. If no other hooks remain, remove the entire `hooks` key.
   - Remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` from `env` if user chose to remove it. If no other env vars remain, remove the entire `env` key.
4. Handle Tier 4 per user decision (keep by default).
5. Clean up empty directories: remove `.claude/commands/` if empty, `.claude/hooks/` if empty. Do NOT remove `.claude/` itself or `.claude/settings.json`.
6. If a launchd plist was found: `launchctl unload <plist>` then delete the plist file. Ask before this step.

## Phase 5: Commit

Stage only the reviewed detach changes and create a single atomic local commit:

```text
chore: detach from cc-rpi blueprint

Removed RPI methodology commands, hooks, CLAUDE.md blueprint sections,
and sync metadata. Project-specific configuration preserved.
```

## Phase 6: Report

Present the final summary:

```text
== Detach Complete ==

Removed: [N] files, [N] CLAUDE.md sections, [N] settings.json entries
Kept: [list preserved Tier 4 directories with counts, or "no work products found"]
Commit: [hash]

This project no longer syncs with cc-rpi. The slash commands, hooks,
and methodology sections have been removed. Your project configuration,
permissions, and work products are untouched.

To re-adopt later: run /adopt
```

## Rules for This Process

- **Preview before delete.** Never remove anything without showing the user what will happen first (Phase 3).
- **Preserve project identity.** Only remove blueprint-managed content. Everything project-specific stays.
- **Keep user work products by default.** Research docs, plans, and decisions are the user's work. Only remove if explicitly asked.
- **Flag customizations.** If a command or hook has been modified from the template, preserve it and report the customization.
- **Flag Codex compatibility customizations.** Always preserve `AGENTS.md`; remove only proven-owned blocks.
- **One atomic commit.** All removals go in a single commit. Don't scatter across multiple commits.
- **Idempotent.** Running on a project without cc-rpi artifacts reports "nothing to detach" and stops. Running twice produces no changes the second time.
- **Don't touch Claude Code itself.** `.claude/` directory, `settings.json` (with remaining entries), and `settings.local.json` are Claude Code's own -- they exist independently of cc-rpi.
