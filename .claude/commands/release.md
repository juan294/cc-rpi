# Release New Version

Model tier: **sonnet** — Sonnet 5 (1M context) session.

Prepare and publish a new version release, adapted to the project type.

## Step 1: Orientation

Gather release context before making any changes.

1. **Detect project type** from manifest files:

   | Check | Type | Version source | Publish action |
   |-------|------|---------------|----------------|
   | `package.json` exists | Node/npm | `version` field in package.json | Advisory: "Ready for `npm publish`" |
   | `Cargo.toml` exists | Rust | `version` field in Cargo.toml | Advisory: "Ready for `cargo publish`" |
   | `pyproject.toml` exists | Python | `version` field in pyproject.toml | Advisory: "Ready for `twine upload`" |
   | `go.mod` exists | Go | Git tags only | Advisory: "Tag pushed, consumers can `go get`" |
   | None of above | Docs/generic | CHANGELOG.md or git tags | No publish step |

2. **Find current version** from the manifest file or latest git tag (`git tag --sort=-v:refname | head -1`).

3. **Find last release tag** and compute changes since then:

   ```bash
   git log <last-tag>..HEAD --oneline
   ```

4. **Identify all version-bearing files** -- do NOT rely on memory or a static
   list. Grep the CURRENT version string across the whole repo so nothing is
   missed:

   ```bash
   git grep -n -F "1.2.3"; git grep -n -F "v1.2.3"   # both bare and v-prefixed
   ```

   Hand-maintained version strings drift silently when there is no canonical
   manifest. Explicitly confirm these commonly-missed locations, even if a scoped
   scan would skip them:
   - **README/docs shield.io badges** -- the version can appear 3x on ONE line
     (badge label text, the `img.shields.io` URL, and the `releases/tag/` link href).
   - **Plugin/marketplace manifests** (`.claude-plugin/plugin.json`,
     `.claude-plugin/marketplace.json`) -- each carries its own `"version"`.
   - manifests, install instructions, constants files, docker tags, CI configs,
     documentation site configs, compatibility tables.

   cc-rpi is docs/generic with NO manifest: git tag + CHANGELOG are the source of
   truth and every other version string is hand-maintained -- the grep is
   mandatory. This repo has repeatedly shipped with the README badge and
   `.claude-plugin/*.json` left 1-2 releases stale; do not let that recur.

5. **Detect branching strategy:**
   - Check if current branch is main/master
   - Check for a permanent integration branch:
     `git branch -a --list '*develop' '*dev' '*integration'`
   - Check git log for merge commits from feature/release branches
   - If a long-lived `develop` (or `dev`/`integration`) branch exists and releases
     go `develop` -> `main`: **develop-based**
   - Else if on main AND no merge-branch pattern: **main-only**
   - Otherwise: **feature-branch**

6. **Present findings** to the user:
   - Project type and version source
   - Current version
   - Number of commits since last release, categorized by type
   - All version-bearing files found
   - Detected branching strategy
   - Suggest major/minor/patch bump based on commit types (feat = minor, fix = patch, breaking = major)

7. **Retirement review.** Ask what rules or errors were retired this cycle,
   and confirm the ledger in `.claude/rules/contributing.md`
   (`### Retirement Ledger`) records them -- even if the answer is "none."

8. **Consider related commands:**
   - If there are unreleased changes, remind the user to consider running `/update-docs` first
     to refresh all documentation before tagging.
   - If this is the first release, recommend running `/pre-launch` for a full audit.
   - Run `/status` for a quick orientation if the project state is unclear.

**STOP.** Ask the user for the version number before proceeding.

## Step 2: Preparation

After the user provides a version number, prepare all files for release. Do not publish yet.

1. **Bump version in manifest files** (package.json, Cargo.toml, pyproject.toml, etc.).
   If a lock file tracks the version (package-lock.json), update it too.

2. **Generate CHANGELOG entry** from commits since last tag. Categorize by conventional
   commit prefix into Keep a Changelog format:

   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - feat: commits summarized here

   ### Fixed
   - fix: commits summarized here

   ### Changed
   - refactor/chore commits summarized here
   ```

   Present the draft entry to the user for review. Apply their edits before writing.

3. **Update version references** in all files identified in Step 1:
   README badges (all occurrences on the line), plugin/marketplace manifests,
   install instructions, constants, docker tags, etc. Then re-run the grep from
   Step 1 for the OLD version and confirm nothing remains outside CHANGELOG
   history -- a non-empty result (other than dated CHANGELOG entries) means a
   file was missed.

4. **Run verification commands** sequentially (chain with `&&` or aggregate failures explicitly, never parallel Bash calls):

   ```bash
   bash templates/scripts/verify-counts.sh
   bash templates/scripts/verify-skills.sh
   bash templates/scripts/verify-version.sh
   bash templates/scripts/check-tree-drift.sh
   ```

   `verify-version.sh` is the mechanical backstop for the Step 1 grep: it
   fails if the README badge (which carries the version 3x on one line) or
   either `.claude-plugin/*.json` disagrees with CHANGELOG, and if the
   previous version survives anywhere outside CHANGELOG. Run it AFTER the
   bump -- before the bump it will correctly report the pre-release state.

   These are cc-rpi's real gates -- there is no typecheck/test/build here.
   They catch a stated count that no longer matches its catalog, a skill that
   outgrew its ceiling, and a `.claude/` file that forked from its template.
   Each prints a runnable FIX on failure.

   Do NOT run `npx markdownlint`: this repo ships no markdownlint config, so it
   applies 80-column defaults that every file here violates by design.

   If any fail, fix before proceeding.

5. **Present the full diff** to the user.

**STOP.** Wait for the user to review and approve the changes before publishing.

## Step 3: Publish

Apply the remote budget from the push-accountability rule. Working and release
branches remain local. Do not create feature/release PRs or Preview deployments.

1. Commit the complete release preparation on the local working branch after
   verifying the intended branch and all applicable local gates.
2. Inspect the documented integration/production topology and current remote
   workflow/deployment triggers. Check that the integration branch has not moved,
   integrate the completed candidate locally, and bind final gate evidence to
   that integrated state. Reconcile and reverify locally if it has moved.
3. Confirm the version, integrated commit, release notes, expected remote runs,
   and publication authorization. Use authorization already given for this
   release; otherwise present the complete candidate before asking. Production
   remains separately authorized from ordinary integration publication.
4. If a push would create a Vercel Preview, stop before pushing. Use a documented,
   non-destructive bypass; never change remote settings as an improvised bypass.
5. Publish only the completed authorized target branch once. In a main-only
   release whose explicitly authorized target is `main`:

   ```bash
   git push origin main
   # Capture the exact published commit for the verification below:
   git rev-parse main
   ```

   In develop-based repositories, ordinary completion publishes only the fully
   verified integration branch. A production release integrates locally into
   the documented production branch and publishes that final branch only with
   explicit production authorization. If branch protection requires a release
   PR, prepare the candidate locally and report that publication constraint;
   do not create a working-branch PR or bypass protection.
6. Inspect every expected workflow for the exact pushed commit:

   ```bash
   gh run list --branch <published-branch> --commit <published-sha> \
     --json databaseId,headSha,name,status,conclusion
   ```

   Report missing, pending, failed and successful runs accurately. A remote
   failure is diagnosed from existing logs and repaired locally; never use
   reruns or fix-and-repush as an experimentation loop.
7. Only after every expected main/integration publication workflow passes for
   that exact commit, create and publish the named release tag and GitHub release:

   ```bash
   git tag -a vX.Y.Z <published-sha> -m "vX.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --notes-file /absolute/path/to/release-notes.md
   ```

   Inspect any expected tag-triggered runs as well. A missing, pending or failed
   branch check blocks tag/release publication; preserve the local candidate.
8. Report the tag, commit, GitHub release link and verification outcome.
   Registry publication remains advisory unless separately authorized.

## Rules

- NEVER use `git push --tags` -- push tags by name: `git push origin vX.Y.Z` (Error #44).
- NEVER use `--body` with `gh release create` -- use `--notes` (Error #20).
- Keep working branches and release preparation local; no feature/release PR loop.
- Preserve permanent integration branches and task artifacts during cleanup.
- ALWAYS verify CI after push (push accountability).
- ALWAYS present the diff before committing (Step 2 gate).
- ALWAYS ask for the version number -- never guess or auto-increment.
- Registry publish (npm/cargo/twine) is ADVISORY ONLY -- tell the user it is ready, do not run it.
  Reason: most registries require 2FA and publishing cannot be undone.
- Run verification commands sequentially, never as parallel Bash calls.
