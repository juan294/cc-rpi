# Known Agent Errors -- Universal Catalog

64 documented error patterns from real recurring issues across projects.
Each entry: symptom, root cause, correct approach, anti-pattern.

**Note:** This file is the source of truth for error patterns. The condensed
top-20 reference is distributed to projects via the error-patterns skill.

For the rule index -- one line per rule, naming the surface that holds it --
see [quick-reference.md](quick-reference.md).

---

## Error #1: Sibling tool call errored (parallel verification commands)

**Symptom:** A failed verification loses sibling output, or an early failure is hidden by a later successful command.

**Root cause:** Tool cancellation differs by harness. Shell semicolon chains return only the final command status.

**Correct approach — always do this:**

Run resource-intensive checks sequentially and retain every result:

```bash
result=0
pnpm run typecheck || result=$?
pnpm run lint || result=$?
exit "$result"
```

Use `&&` for fail-fast dependencies. Do not generalize one client version's
sibling cancellation to all tools and harnesses.

**Never do this:** Use a bare `typecheck; lint` as an overall pass/fail gate.

---

## Error #2: Shell cwd resets to main repo when working in a worktree

**Symptom:** A historical session reported a worktree command returning to
another directory. The original Claude client version was not recorded.

**Root cause:** The agent assumed a prior call established the next call's cwd.
Current Codex `exec_command` explicitly defaults to the turn cwd and accepts
per-call `workdir`; this is the verified tool contract, not a claim about every
shell or Claude client. Current Claude cwd behavior remains unverified.

**Correct approach — always do this:** Use the observed absolute worktree path,
`git -C`, or explicit tool working directory. Verify actual branch and status
before mutations; preserve every verification exit status (Error #1).

```bash
git -C /absolute/path/to/worktree status --short
cd /absolute/path/to/worktree && pnpm run typecheck
```

**Never do this:** Infer a worktree or branch from an earlier `cd` or handoff
without checking current state. Path and branch safety remain active.

---

## Error #3: Commit rejected by pre-commit hook (typecheck/lint failure)

**Symptom:** Agent runs `git add <files> && git commit -m "..."` and it fails with exit code 1 because the pre-commit hook triggers a full typecheck/lint across the project and finds errors. Wasted time: the commit fails, the agent must fix errors, then re-stage and re-commit.

**Root cause:** The agent skipped running verification checks before committing. Pre-commit hooks enforce the same checks (typecheck, lint, tests) — discovering failures at commit time means unnecessary rework.

**Correct approach — always do this:**
```bash
# 1. Run the checks FIRST (same ones the pre-commit hook runs):
pnpm run typecheck 2>&1 && pnpm run lint 2>&1

# 2. Fix any errors found

# 3. THEN stage and commit (the hook will pass):
git add <files> && git commit -m "fix(scope): description"
```

**Never do this:**
```bash
# Don't go straight to commit without checking first:
git add . && git commit -m "fix: something"  # ← hook fails, wasted time
```

**Key detail:** In monorepos, pre-commit hooks often run typecheck across ALL workspace packages, not just the files you changed. Pre-existing errors in other packages will block your commit even if your changes are clean.

---

## Error #4: Wrong `--json` field names for `gh` CLI commands

**Symptom:** Running `gh pr checks <PR> --json name,state,conclusion` fails with "Unknown JSON field: conclusion". The agent guesses field names that don't exist for that specific subcommand.

**Root cause:** `gh` CLI `--json` field names differ between subcommands. The agent assumes fields from one command (e.g., `gh run view`) work on another (e.g., `gh pr checks`). They don't.

**Correct approach — always do this:**
```bash
# If unsure of available fields, query them first:
gh pr checks --help

# Known correct fields for common commands:
# gh pr checks: name, state, bucket, completedAt, description, event, link, startedAt, workflow
# gh pr view:   number, title, state, body, url, headRefName, baseRefName, mergeable, reviewDecision
# gh run view:  conclusion, status, name, event, headBranch, workflowName
# gh run list:  conclusion, status, name, event, headBranch, workflowName

# For CI status monitoring, use gh run list instead of gh pr checks:
gh run list --branch <branch> --limit 1 --json conclusion,status,name
```

**Never do this:**
```bash
# Don't guess field names across subcommands:
gh pr checks 377 --json name,state,conclusion  # ← "conclusion" doesn't exist here
```

**Key detail:** `conclusion` exists on `gh run view/list` but NOT on `gh pr checks`. For PR check status, use `state` and `bucket`.

---

## Error #5: SyntaxError running CLI tool with `node dist/index.js`

**Symptom:** A CLI build fails to parse when invoked with Node.

**Root cause:** Possible causes include malformed generated bytes, unsupported syntax, or a mismatch between module format and package metadata. Node accepts a leading hashbang in both CommonJS and ESM.

**Correct approach — always do this:**

Inspect the exact failing bytes, installed Node version, file extension and
nearest package.json. `.mjs` selects ESM; `.cjs` selects CommonJS; `.js`
interpretation depends on package metadata and runtime rules.

```bash
node --version
node --check dist/index.js
node dist/index.js --version
```

Use the package's documented entry point. Direct Node execution is valid;
a wrapper or global install does not repair malformed output.
See [Node package rules](https://nodejs.org/api/packages.html#determining-module-system).

**Never do this:** Attribute every ESM syntax error to a shebang or bypass the actual parse error with an unrelated wrapper.

---

## Error #6: Cannot delete branch used by a worktree during PR merge

**Symptom:** Git refuses cleanup because the worktree contains files or the branch still holds unmerged work.

**Root cause:** The safety check is protecting data; a temporary branch name does not establish disposability.

**Correct approach — always do this:**

Inspect `git worktree list --porcelain`, the target's tracked/untracked/ignored
files, and its commits. Preserve source changes, curated plans, handoffs and
needed evidence; establish task ownership and local integration first.

```bash
git -C /absolute/path/to/worktree status --short --untracked-files=all
git -C /absolute/path/to/worktree status --short --ignored
git merge-base --is-ancestor work-branch integration-branch
# Only after the preceding ownership/preservation checks:
git worktree remove /absolute/path/to/worktree
git branch -d work-branch
```

Keep a dirty, foreign or unmerged worktree intact. Cleanup refusal requires
inspection, not a force retry. Working branches remain local.

**Never do this:** Default to `--force`, `git branch -D`, or a batch removal loop that hides failures.

---

## Error #7: `execSync(...).trim is not a function` — Buffer vs string

**Symptom:** Tests fail with `TypeError: (0, execSync)(...).trim is not a function` at runtime. Code like `execSync('some command').trim()` throws because `.trim()` doesn't exist on Buffer.

**Root cause:** Node.js `execSync()` returns a **Buffer** by default, not a string. String methods such as `.trim()` and `.split()` do not exist on Buffer; Buffer has its own `.toString()` and `.includes()` methods. The agent writes code assuming it returns a string.

**Correct approach — always do this:**
```typescript
// ALWAYS pass encoding to get a string back:
const output = execSync('some command', { encoding: 'utf-8' }).trim();

// Or convert explicitly:
const output = execSync('some command').toString().trim();
```

**Never do this:**
```typescript
// Buffer has no .trim():
const output = execSync('some command').trim();  // ← TypeError
```

**Applies to:** `execSync`, `spawnSync` (stdout/stderr are Buffers by default). Always specify `{ encoding: 'utf-8' }` or call `.toString()` before string methods.

---

## Error #8: Write/Read/Edit fail with `~` (tilde) in file paths

**Symptom:** A file operation receives a literal `~` path and fails to find the file.

**Root cause:** Shell expansion is not a universal file-API feature. Whether an
API expands tilde depends on its documented contract; quoting can also suppress
shell expansion.

**Correct approach — always do this:** Resolve the user's home and the actual
path using the available environment, then pass an observed absolute path when
the tool does not explicitly support expansion. Preserve ownership and branch
checks before mutations.

**Never do this:** Assume every file API expands `~`, or that one tool's failure
proves every current native tool lacks expansion. This safeguard is retained.

---

## Error #9: `git push` rejected (non-fast-forward)

**Symptom:** The authorized integration push is rejected because the remote advanced.

**Root cause:** The candidate no longer includes the remote integration history.

**Correct approach — always do this:**

Fetch and inspect the integration branch, preserve local work, reconcile
locally, and rerun affected complete gates. Inspect triggers before a new
publication decision. Push only completed integration work, never feature
branches, and do not use a pull-and-push chain as a verification shortcut.

**Never do this:** Force-push shared history or publish unverified rebases.

---

## Error #10: Checking CI for multiple PRs in one jumbled command

**Symptom:** The agent confuses check states or discards a real check called review.

**Root cause:** Check names are arbitrary; they do not establish the meaning of a failure.

**Correct approach — always do this:**

Inspect each existing PR with `gh pr checks <PR> --json name,state,bucket,workflow`.
Associate results with the PR and expected check inventory. A `review`-named
check may be a real required workflow; inspect it before classifying it.
Review approval state can be read separately with `gh pr view <PR> --json reviewDecision`.
Do not infer a complete CI pass from one recent run or an empty list.

**Never do this:** Filter a required check solely by its name or ignore pending exit 8.

---

## Error #11: `git worktree remove` fails on modified/untracked files, cascading failures

**Symptom:** Git refuses cleanup because the worktree contains files or the branch still holds unmerged work.

**Root cause:** The safety check is protecting data; a temporary branch name does not establish disposability.

**Correct approach — always do this:**

Inspect `git worktree list --porcelain`, the target's tracked/untracked/ignored
files, and its commits. Preserve source changes, curated plans, handoffs and
needed evidence; establish task ownership and local integration first.

```bash
git -C /absolute/path/to/worktree status --short --untracked-files=all
git -C /absolute/path/to/worktree status --short --ignored
git merge-base --is-ancestor work-branch integration-branch
# Only after the preceding ownership/preservation checks:
git worktree remove /absolute/path/to/worktree
git branch -d work-branch
```

Keep a dirty, foreign or unmerged worktree intact. Cleanup refusal requires
inspection, not a force retry. Working branches remain local.

**Never do this:** Default to `--force`, `git branch -D`, or a batch removal loop that hides failures.

---

## Error #12: Push and forget — CI breaks silently

**Symptom:** An authorized completed integration push finishes without checking its resulting workflows.

**Root cause:** Publication is mistaken for verified remote completion.

**Correct approach — always do this:**

Complete full local gates first, inspect remote triggers, then perform the
single authorized integration push. Inspect runs bound to the pushed commit
and expected workflows. Read-only run/log queries are allowed. If remote
checks unexpectedly fail, investigate and fix locally; do not start a hosted
fix-and-repush debugging loop. Report the failure and any further publication
boundary explicitly.

**Never do this:** Publish partial branches or repeatedly push experiments to discover CI failures.

---

## Error #13: Skipping TDD — writing implementation before tests

**Symptom:** Agent writes implementation code first, then either (a) adds tests as an afterthought that merely assert the implementation is correct rather than specifying behavior, or (b) says "I'll add tests later" and never does. When bugs are later found, there's no regression test to prevent recurrence.

**Root cause:** The agent defaults to implementation-first development. Without an explicit TDD mandate, tests become an optional follow-up rather than the starting point.

**Correct approach — always do this:**
```
# For every code change:
1. Write a failing test that describes the expected behavior
2. Run the test — confirm it fails (Red)
3. Write the minimum implementation to make it pass (Green)
4. Refactor while keeping tests green

# For bug fixes specifically:
1. Write a test that reproduces the bug
2. Confirm the test fails
3. Fix the bug
4. Confirm the test passes — this is now a regression test
```

**Never do this:**
```
# Don't write code first and tests second:
1. Write implementation
2. Write tests that assert the implementation works  ← tests are tautological
3. "Ship it"
```

**Why this matters:** Tests written after implementation tend to test that the code does what it does (tautological), not that it does what it should (behavioral). TDD forces tests to be independent specifications.

**Reviewing a test that already exists:** ordering is invisible after the fact, so judge the assertion instead. Name the change to production code that would make it fail. If nothing would -- it asserts the implementation back to itself, passes on any branch of an `or`, or only checks that a handler is imported or registered -- it is tautological no matter when it was written. See [the testing rule](../templates/rules/testing.md) for the mocking boundary, the can-this-fail check and coverage honesty.

---

## Error #14: Suggesting manual steps instead of using available tools

**Symptom:** Agent responds with "Go to the dashboard and click..." or "Open the browser and navigate to..." or "Run this command in your terminal..." for operations the agent could perform itself using available CLI tools, shell commands, or MCP servers.

**Root cause:** The agent defaults to instructional mode rather than action mode. It doesn't check whether it has tools available to perform the operation directly.

**Correct approach — always do this:**
```
# Before suggesting any manual step, check if you can do it:
1. Can I use a CLI tool? (gh, git, curl, project CLIs)
2. Can I use a shell command? (pnpm scripts, build tools)
3. Can I use MCP servers? (check available tools in the session)
4. Can I use file tools? (Read/Edit/Write for config changes)
5. Can I use web tools? (WebSearch/WebFetch for documentation)

# Only suggest manual intervention when genuinely required:
- OAuth consent flows (requires human browser interaction)
- Billing dashboards (requires human authorization)
- Hardware interaction (physical access needed)
- Elevated privileges the agent doesn't have
```

**Never do this:**
```
# Don't suggest manual steps for things you can do:
"Please inspect the CI status in your terminal"  ← use the available read-only tools
"Go to GitHub and check the CI status"        ← use `gh run list`
"Open the file and change line 42"            ← use Edit tool
```

**Key detail:** This error compounds — once an agent starts suggesting manual steps, the user loses trust in the agent's autonomy. Exhaust every tool before escalating.

---

## Error #15: `git branch -d` fails on worktree branches (not fully merged)

**Symptom:** Git refuses cleanup because the worktree contains files or the branch still holds unmerged work.

**Root cause:** The safety check is protecting data; a temporary branch name does not establish disposability.

**Correct approach — always do this:**

Inspect `git worktree list --porcelain`, the target's tracked/untracked/ignored
files, and its commits. Preserve source changes, curated plans, handoffs and
needed evidence; establish task ownership and local integration first.

```bash
git -C /absolute/path/to/worktree status --short --untracked-files=all
git -C /absolute/path/to/worktree status --short --ignored
git merge-base --is-ancestor work-branch integration-branch
# Only after the preceding ownership/preservation checks:
git worktree remove /absolute/path/to/worktree
git branch -d work-branch
```

Keep a dirty, foreign or unmerged worktree intact. Cleanup refusal requires
inspection, not a force retry. Working branches remain local.

**Never do this:** Default to `--force`, `git branch -D`, or a batch removal loop that hides failures.

---

## Error #16: Commands fail because dependencies aren't installed

**Symptom:** `pnpm vitest run ...` fails with `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL` — "Command 'vitest' not found". Or `pnpm run test` fails with "sh: vitest: command not found" and "Local package.json exists, but node_modules missing, did you mean to install?"

**Root cause:** The agent runs test/build/lint commands in a fresh clone, new worktree, or environment where `pnpm install` hasn't been run. Dependencies aren't available.

**Correct approach — always do this:**
```bash
# Before running any project commands in a new environment, install dependencies:
pnpm install  # or npm install, yarn install

# Especially important in worktrees (they don't share node_modules):
cd /path/to/worktree && pnpm install && pnpm run test

# Check if node_modules exists before running commands:
ls node_modules/.package-lock.json 2>/dev/null || pnpm install
```

**Never do this:**
```bash
# Don't assume dependencies are installed in fresh environments:
cd /path/to/worktree && pnpm run test  # ← "command not found"
```

**Applies to:** Any fresh worktree, clone, or CI environment. Node.js worktrees do NOT share node_modules with the main repo unless using workspaces with hoisting.

---

## Error #17: jq syntax error — shell escaping corrupts filter expressions

**Symptom:** `gh pr checks <PR> --json name,state | jq '[.[] | select(.state \!= "SUCCESS")]'` fails with "jq: error: syntax error, unexpected INVALID_CHARACTER" pointing at `\!=`.

**Root cause:** The agent over-escapes the `!=` operator. Inside single-quoted shell strings, `!` is literal — no escaping needed. Adding `\` before `!` passes the literal backslash to jq, which doesn't understand `\!=` as an operator.

**Correct approach — always do this:**
```bash
# Use single quotes and don't escape operators:
gh pr checks 458 --json name,state | jq '[.[] | select(.state != "SUCCESS")]'

# jq operators need no shell escaping inside single quotes:
jq '.[] | select(.name != "review")'
jq '.[] | select(.state == "SUCCESS" or .state == "SKIPPED")'

# If you need shell variable interpolation, use --arg:
jq --arg val "$SHELL_VAR" '.[] | select(.name == $val)'
```

**Never do this:**
```bash
# Don't escape jq operators inside single quotes:
jq '.[] | select(.state \!= "SUCCESS")'   # ← INVALID_CHARACTER
jq ".[] | select(.state != \"SUCCESS\")"   # ← fragile double-quote escaping
```

**Key detail:** Inside single quotes (`'...'`), the shell passes everything literally — no expansion, no escaping needed. Always use single quotes for jq filters.

---

## Error #18: Git commands fail on repo with no commits yet

**Symptom:** `git log --oneline -20` fails with "fatal: your current branch 'main' does not have any commits yet" in a newly initialized repository.

**Root cause:** The agent runs git history/diff commands as part of its standard workflow (e.g., checking recent commits before committing) without checking if the repo has any commits. This happens during project bootstrap after `git init` but before the first commit.

**Correct approach — always do this:**
```bash
# Check if commits exist before running git log:
git rev-parse HEAD >/dev/null 2>&1 && git log --oneline -20 || echo "No commits yet"

# During bootstrap, create the initial commit first:
git add . && git commit -m "feat: initial commit"
# Now git log works
```

**Never do this:**
```bash
# Don't assume commits exist in a new repo:
git log --oneline -20  # ← fatal if no commits yet
git diff HEAD          # ← also fails
```

**Applies to:** Project bootstrap workflows, fresh `git init` repos. Always handle the empty-repo case.

---

## Error #19: API content filter blocks file creation in parallel

**Symptom:** Historical parallel boilerplate writes reported an API content
filter error. The original client/model version and a controlled reproduction
were not recorded.

**Root cause:** The cause was not established. A failed content generation does
not prove a universal filename restriction or that all sibling calls failed.

**Correct approach — always do this:** Inspect each write result, preserve
successful files, and isolate the affected write with a legitimate minimal
template or external reference when appropriate. Record client/version and
reproduction evidence before attributing the failure to the harness. Ordinary
independent writes do not require a blanket sequential rule.

**Never do this:** Repeat unchanged blocked attempts, silently abandon a
required file, or assert that CODE_OF_CONDUCT.md/SECURITY.md filenames cause
filtering. Report an unresolved block and its evidence if no valid route remains.

**Disposition:** Retained and narrowed, not retired as harness-fixed.

---

## Error #20: `gh release create --body` — wrong flag name

**Symptom:** `gh release create v1.0.0 --title "v1.0.0: Title" --body "Release notes..."` fails with "unknown flag: --body".

**Root cause:** The agent confuses flags between `gh` subcommands. `gh pr create` and `gh issue create` use `--body`, but `gh release create` uses `--notes` (or `-n`). Different subcommands use different flag names for similar concepts.

**Correct approach — always do this:**
```bash
# For releases, use --notes (not --body):
gh release create v1.0.0 --title "v1.0.0: Title" --notes "Release notes here"

# If unsure, check the help:
gh release create --help 2>&1 | head -20

# Known flag differences:
# gh pr create:      --body, --title
# gh issue create:   --body, --title
# gh release create: --notes, --title  (NOT --body)
```

**Never do this:**
```bash
# Don't assume --body works on all gh subcommands:
gh release create v1.0.0 --body "notes"  # ← "unknown flag: --body"
```

**Key detail:** This is the same class of error as Error #4 (guessing `--json` fields). Different `gh` subcommands have different flags even for semantically similar concepts. When in doubt, check `--help`.

---

## Error #21: `pip3 install` fails on macOS — externally-managed-environment

**Symptom:** `pip3 install <package>` fails with "error: externally-managed-environment — This environment is externally managed. To install Python packages system-wide, try brew install xyz."

**Root cause:** macOS with Homebrew Python (3.12+) enforces PEP 668, which prevents `pip3 install` from modifying the system Python environment. This protects against breaking system tools that depend on Python.

**Correct approach — always do this:**
```bash
# For CLI tools, use brew:
brew install git-filter-repo

# For Python applications, use pipx (isolated environments):
brew install pipx && pipx install <package>

# For Python libraries in a project, use a virtual environment:
python3 -m venv .venv && source .venv/bin/activate && pip install <package>
```

**Never do this:**
```bash
# Don't use pip3 install on macOS with Homebrew Python:
pip3 install git-filter-repo  # ← "externally-managed-environment"

# Don't use --break-system-packages (risks breaking Homebrew):
pip3 install --break-system-packages <package>  # ← dangerous
```

**Applies to:** Any macOS system with Homebrew Python 3.12+. Always prefer `brew install` for CLI tools and `pipx` for Python applications.

---

## Error #22: `rm` fails on stale file list — agent doesn't re-read directory

**Symptom:** A cached removal list no longer describes the filesystem.

**Root cause:** The agent treats stale names as current ownership evidence.

**Correct approach — always do this:** Re-read the directory, establish task
ownership and preservation needs, then delete only named disposable artifacts.
A missing file can be harmless; an unknown existing file must be preserved.
Use an exact task-owned temporary path rather than a broad directory glob.

**Never do this:** Use `rm -f` or a glob to bypass ownership inspection or delete
editable diagram sources just because an export exists.

---

## Error #23: `gh` command fails — agent fabricates repo/resource names

**Symptom:** `gh repo view owner/MyProject --json name,owner` fails with "GraphQL: Could not resolve to a Repository with the name 'owner/MyProject'." The agent used a repo name that doesn't exist — it was guessed, misspelled, or hallucinated.

**Root cause:** The agent infers or fabricates GitHub identifiers (repository names, branch names, issue numbers) instead of discovering them through queries. GitHub identifiers are case-sensitive and must match exactly. Guessing leads to API failures.

**Correct approach — always do this:**
```bash
# Discover repos instead of guessing names:
gh repo list <owner> --json name --limit 50

# Verify a repo exists before querying it:
gh repo view <owner>/<repo> --json name 2>&1 || echo "Repo not found"

# For branches, list before assuming:
git branch -r | grep <pattern>
# or:
gh api repos/<owner>/<repo>/branches --jq '.[].name'

# For issues/PRs, query by search rather than guessing numbers:
gh issue list --search "keyword" --json number,title
```

**Never do this:**
```bash
# Don't fabricate or guess identifiers:
gh repo view owner/GUESSED-NAME --json name  # ← might not exist
gh pr view 999 --json title                   # ← PR number might be wrong
git checkout origin/assumed-branch            # ← branch might not exist
```

**Key detail:** This is the same class of error as Error #4 (guessing `--json` fields) and Error #20 (guessing flag names) — the agent assumes identifiers instead of querying them. GitHub names are case-sensitive: `MyRepo` != `myrepo` != `MYREPO`.

---

## Error #24: Cross-project `../` relative paths fail in Bash commands

**Symptom:** A cross-project relative path resolves from an unexpected cwd.

**Root cause:** The agent did not bind the operation to an observed directory.
See Error #2 for the Codex per-call contract and the unverified Claude case.
`cd destination && command` does not execute command when `cd` fails; the
historical claim of a silent fall-through was incorrect.

**Correct approach — always do this:** Discover the sibling project's actual
path, use an explicit working directory or absolute paths, and verify ownership
and preservation before any deletion. Read-only inspection is a useful preflight:

```bash
git -C /absolute/path/to/other-project status --short
```

**Never do this:** Guess `../` from stale context, use broad removal lists, or
replace ownership inspection with `rm -f`. Separate cross-project authorization
from path discovery; seeing a sibling project does not authorize modifying it.

---

## Error #25: `git push` or `git pull --rebase` fails — no upstream tracking for branch

**Symptom:** Git cannot infer a remote tracking branch.

**Root cause:** A local branch has no upstream; this is normal for task branches.

**Correct approach — always do this:**

Keep working branches local. Name refs explicitly when fetching integration
history. Only the completed, locally verified integration branch may receive
an upstream during an authorized push, after trigger inspection. A missing
upstream is not an instruction to publish the working branch.

**Never do this:** Run `git push -u` on a feature or remediation branch to silence the error.

---

## Error #26: Complex shell regex fails in zsh — special characters parsed differently

**Symptom:** A regex command fails with a shell parse error or unsupported grep option.

**Root cause:** Shell quoting and grep dialect support are separate. macOS BSD grep lacks `-P`; bash wrapping cannot add it.

**Correct approach — always do this:**

Use single quotes for literal patterns. Prefer `rg`, supported `grep -E`,
Python `re`, or a format-aware parser:

```bash
python3 -c 'import json; print(json.load(open("package.json"))["version"])'
```

Check executable help. Reproduce quoting errors independently of regex errors.

**Never do this:** Install another grep or switch shells merely to mask a broken portable recipe.

---

## Error #27: Linter runs on wrong file types or fights intentional patterns

**Symptom:** `markdownlint-cli2 "file.md" "script.sh" "config.yml"` reports hundreds of errors — most from non-markdown files being parsed as markdown. Or: linter reports errors like `MD029/ol-prefix` on files where continuous numbering (steps 1-22 across sections) is intentional. The agent then wastes turns "fixing" intentional formatting.

**Root cause:** Two related problems: (1) The agent passes files to a linter without filtering for the correct file type. It globs too broadly or includes all changed files regardless of extension. (2) The agent treats all linter warnings as bugs to fix, not considering whether the flagged pattern is intentional (e.g., continuous step numbering for agent instructions).

**Correct approach — always do this:**
```bash
# Only pass correct file types to linters:
markdownlint-cli2 "**/*.md"                          # ← only markdown
eslint "**/*.{ts,tsx,js,jsx}"                          # ← only JS/TS
shellcheck scripts/*.sh                                # ← only shell scripts

# When linting specific files, filter by extension:
echo "$changed_files" | grep '\.md$' | xargs markdownlint-cli2

# When a linter flags known-intentional patterns:
# 1. Check if the pattern is documented (README, CLAUDE.md, comments)
# 2. Add a disable comment or config override for that specific rule
# 3. Do NOT "fix" intentional formatting to satisfy the linter

# Use .markdownlintignore or inline disable comments:
<!-- markdownlint-disable MD029 -->
```

**Never do this:**
```bash
# Don't pass all files to a markdown linter:
markdownlint-cli2 "templates/**/*"  # ← includes .sh, .json, .yml files

# Don't "fix" intentional formatting:
# If steps are numbered 1-22 across sections intentionally,
# don't reset numbering per-section just because MD029 complains.

# Don't blindly fix all linter errors without understanding context:
# Some "errors" are intentional style choices documented in the project.
```

**Key detail:** Before fixing any linter error, check whether the flagged pattern is intentional. Continuous numbered steps in agent instruction files, shell scripts linted as markdown, and style choices documented in project config are all false positives. The agent should add linter exceptions for intentional patterns, not change the content to satisfy the linter.

---

## Error #28: Agent manually fixes auto-fixable linter issues instead of using `--fix`

**Symptom:** `ruff check src/ tests/` reports `I001 [*] Import block is un-sorted or un-formatted` (or similar auto-fixable rules). The `[*]` marker indicates the issue is auto-fixable. The agent then opens each file and manually reorders imports, wasting multiple turns on something a single command handles.

**Root cause:** The agent runs linters in check-only mode and doesn't recognize auto-fixable markers (`[*]` in ruff, `--fix` available in eslint). It treats every linter error as something to manually edit, even when the linter itself can fix it automatically.

**Correct approach — always do this:**
```bash
# For ruff (Python): use --fix for auto-fixable issues:
ruff check --fix src/ tests/
ruff format src/ tests/          # for formatting issues

# For eslint (JS/TS): use --fix:
eslint --fix src/

# For prettier: it always auto-fixes:
prettier --write "src/**/*.{ts,tsx}"

# General pattern:
# 1. Run linter with --fix first to handle auto-fixable issues
# 2. Run linter in check-only mode to see remaining manual issues
# 3. Only manually edit files for issues that can't be auto-fixed
ruff check --fix src/ tests/ 2>&1; ruff check src/ tests/ 2>&1
```

**Never do this:**
```bash
# Don't manually fix auto-fixable issues:
ruff check src/ tests/      # ← sees I001 [*] import sorting
# Then manually reorders imports in 5 files...  ← wasted 5 turns

# Don't ignore the [*] marker — it means "I can fix this for you":
# I001 [*] = auto-fixable
# E501     = NOT auto-fixable (no [*])
```

**Key detail:** The `[*]` marker in ruff output means the issue is auto-fixable with `--fix`. Similarly, eslint's `--fix` handles a large subset of rules automatically. Always try `--fix` first — it handles import sorting, whitespace, trailing commas, and many formatting issues. Only manually edit for issues the linter can't auto-fix.

---

## Error #29: `uv sync` fails — auto-selected Python version too new for packages

**Symptom:** Dependency installation fails for the selected interpreter.

**Root cause:** The chosen interpreter and package support may disagree. uv respects explicit requests, project constraints, and environment discovery; it does not universally select the newest Python.

**Correct approach — always do this:**

Read `.python-version`, `requires-python`, the lockfile and supported CI matrix.
Use `uv python find` to inspect selection and `uv sync --locked` to honor the
project. If a pin must change, justify it against the actual dependency support
and test matrix; use `uv python pin <version>` only for that deliberate change.
See [uv version selection](https://docs.astral.sh/uv/concepts/python-versions/).

**Never do this:** Replace every pin with 3.13 or delete `.venv` without examining the mismatch.

---

## Error #30: `gh pr create` before pushing branch to remote

**Symptom:** PR creation fails because the source ref is absent remotely.

**Root cause:** A PR requires a remote ref, but working branches are intentionally local under the owner budget policy.

**Correct approach — always do this:**

Finish implementation, full local verification, and local integration.
Inspect triggers before the single authorized integration push. Do not create
feature PRs as an implementation loop. If a documented release process uses
a PR, apply it only to an already authorized completed integration/release
ref and check for an existing PR first.

**Never do this:** Publish a working branch merely to make PR creation succeed.

---

## Error #31: Agent guesses CLI flags that don't exist on unfamiliar tools

**Symptom:** `vercel inspect <url> --json` fails with "Error: unknown or unexpected option: --json". Or `vercel logs --output raw <url>` gets "The '--output' option was ignored because it is now deprecated." The agent assumes flags from one CLI (like `gh`) work on unrelated CLIs (like `vercel`, `aws`, `docker`).

**Root cause:** The agent transfers mental models between CLIs. Because `gh` supports `--json` for structured output, the agent assumes all CLIs do. Because one tool has `--output`, the agent assumes another does too. Each CLI has its own flag vocabulary — there's no universal standard.

**Correct approach — always do this:**
```bash
# Check available flags before using them on unfamiliar CLIs:
vercel inspect --help 2>&1 | head -30
vercel logs --help 2>&1 | head -30

# Use the correct flags for each CLI:
# Vercel: no --json flag; use vercel inspect <url> and parse text output
# gh: supports --json with field names
# aws: supports --output json|table|text
# docker: supports --format with Go templates

# For structured output from CLIs without --json, pipe to text processing:
vercel inspect <url> 2>&1 | grep -E "^  (id|name|status|target)"
```

**Never do this:**
```bash
# Don't assume flags transfer between CLIs:
vercel inspect <url> --json          # ← "unknown option: --json"
vercel logs --output raw <url>       # ← "--output" deprecated

# Don't guess flags based on other CLIs:
# gh uses --json     → doesn't mean vercel does
# curl uses --output → doesn't mean vercel does
```

**Key detail:** This is the same class of error as Error #4 (guessing `gh --json` fields), Error #20 (guessing `gh` flag names), and Error #23 (fabricating identifiers) — the common thread is guessing instead of querying. Before using any flag on an unfamiliar CLI, run `<cmd> --help` to verify it exists. This takes 5 seconds and prevents wasted turns from invalid commands.

---

## Error #32: `gh pr merge` fails — wrong merge method, branch not up-to-date, or auto-merge disabled

**Symptom:** A PR merge is rejected by method, freshness, or auto-merge policy.

**Root cause:** The agent guessed flags before reading repository settings and
publication side effects.

**Correct approach — always do this:** Inspect settings and existing PR status
read-only with `gh api repos/{owner}/{repo}` and `gh pr view <N>`. Keep working
branches local. Reconcile and verify integration locally; do not use a
fetch/rebase/push chain to satisfy hosted checks. Only execute a release PR
mutation when that concrete completed release workflow is authorized. Do not
enable auto-merge or relax protections to bypass a refusal.

**Never do this:** Retry merge flags blindly or publish unverified work to
make the remote merge button available.

---

## Error #33: `git pull --rebase` fails — unstaged changes in working tree

**Symptom:** Rebase refuses unstaged changes.

**Root cause:** Local tracked or untracked work needs preservation before
history reconciliation.

**Correct approach — always do this:** Inspect `git status` and preserve all
user work. Commit only identified task changes, or record a specific stash
including applicable untracked files when that is the appropriate preservation
method. Fetch and reconcile integration history locally, restore preserved
content, resolve any conflicts, and verify the resulting candidate. Keep the
publication decision separate from preservation and rebase.

**Never do this:** Chain stash, pull, push and stash-pop, or use `git add -A`
to commit unrelated changes as an automatic prerequisite for pulling.

---

## Error #34: WebFetch returns 403 — agent retries same blocked domain

**Symptom:** Repeated identical requests return forbidden responses.

**Root cause:** HTTP 403 refuses the particular request; causes include authorization, policy, rate limiting, or automation blocking. One URL does not establish a domain-wide block.

**Correct approach — always do this:**

Inspect status, response and permitted authentication context. Retry only
after a relevant correction, or use another authorized source/search result.
Avoid blind URL variation or access-control bypasses. See [HTTP 403 semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-403-forbidden).

**Never do this:** Claim all paths are blocked based solely on one 403.

---

## Error #35: `gh pr checks` exit code 0 with pending checks — misread as "all passed"

**Symptom:** The agent reports success while checks are pending or the expected inventory is incomplete.

**Root cause:** The historical claim that pending always exits 0 is incorrect for the current CLI. Pending checks return 8.

**Correct approach — always do this:**

Use `gh pr checks --help` to discover supported fields and status semantics.

```bash
gh pr checks 42 --json name,state,bucket,workflow
gh pr checks 42 --watch
```

`bucket` is `pass`, `fail`, `pending`, `skipping`, or `cancel`. Exit 1 may
represent failed checks or command errors; inspect output. Confirm expected
checks exist, and handle skip/cancel according to repository policy.
See the [CLI manual](https://cli.github.com/manual/gh_pr_checks).

**Never do this:** Request the unsupported `conclusion` field or treat pending exit 8 as success.

---

## Error #36: Agent builds mega inline shell one-liner that zsh can't parse

**Symptom:** Agent constructs a massive single-line Bash command with `while`, `do`, `awk`, pipes, and special characters all inline. Fails with zsh errors like `(eval):1: condition expected: \≠` or other parse errors. The command is so long it's unreadable and undebuggable.

**Root cause:** The agent tries to accomplish a multi-step operation (file scanning, text processing, conditional logic) in a single inline shell command instead of writing a script file. zsh parses inline commands differently than bash scripts — special characters, Unicode, backticks, and nested quotes all become problematic. The longer the one-liner, the higher the probability of a parse failure.

**Correct approach — always do this:**
```bash
# For any multi-step shell logic, write a temporary script:
cat > /tmp/process.sh << 'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

repo_root=$(realpath .)
while IFS= read -r file; do
    dir=$(dirname "$file")
    # Complex awk/processing logic here
    awk '/^```/{skip=!skip; next} !skip{print}' "$file"
done < <(find "$repo_root" -name "*.md")
SCRIPT
chmod +x /tmp/process.sh && /tmp/process.sh

# Or better: use dedicated tools instead of shell pipelines
# Grep tool for searching, Read tool for file content, etc.
```

**Never do this:**
```bash
# Don't build mega one-liners with complex logic:
errfile=$(mktemp) && echo 0 > "$errfile" && repo_root=$(realpath .) && while IFS= read -r file; do dir=$(dirname "$file"); awk '/^``/{skip=!skip; next} !skip{p...' ← BREAKS in zsh

# Don't embed Unicode or special characters in inline commands:
awk '... ≠ ...'    # ← zsh can't parse ≠ inline

# Don't chain more than 2-3 simple commands inline:
# If your command needs while/for/awk/sed, it's a script, not a one-liner
```

**Key detail:** This is related to Error #26 (complex regex in zsh) but broader — it's about the entire anti-pattern of mega one-liners. The threshold is simple: if your command needs control flow (`while`, `for`, `if`) or complex text processing (`awk` with multi-line logic), write it to a temp file and execute that. This also makes debugging possible when things fail. Prefer using Claude Code's built-in tools (Grep, Read, Glob) over shell pipelines whenever possible.

---

## Error #37: Scheduled agent silently fails under macOS launchd

**Symptom:** A scheduled agent works in a terminal but fails under launchd,
with missing executables, descriptor-limit errors or authentication failures.

**Root cause:** The scheduler environment can differ from the terminal. The
historical report did not record client/macOS versions or prove universal
limits of 256 descriptors or a Claude requirement for 100K+ descriptors.

**Correct approach — always do this:** For an explicitly opted-in scheduled
job, inspect actual executable paths, cwd, environment, soft/hard limits,
non-interactive authentication support and sanitized logs. Select resource
limits from measured requirements; a shell cannot raise its soft limit beyond
its hard limit. Configure only necessary environment values and never publish
credentials. See the example in the macOS skill and scheduled-agent methodology.

**Never do this:** Treat every job as requiring four identical fixes, require a
new token when existing authentication works, or use successful terminal
execution as proof of scheduler success. Scheduler tests can invoke paid model
work and require the appropriate authorization.

**Disposition:** Retain the diagnostic checklist. A current-version native
reproduction is required before declaring a harness fix.

---

## Error #38: Claude CLI crashes with "Unexpected" when plist runs script directly

**Symptom:** A historical launchd job returned `Unexpected` even for
`claude --version`, with zero exit status and location-dependent behavior.
The original client version was not recorded.

**Root cause:** Unknown. The report observed that a `/bin/bash -c` exec wrapper
avoided the failure; it did not establish the proposed internal project-context
cause or that all direct script execution is invalid.

**Correct approach — always do this:** Record current client/macOS version,
arguments, cwd and sanitized logs. Reproduce the direct and wrapper cases under
the same authorized scheduler environment before recommending the workaround:

```xml
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>
  <string>-c</string>
  <string>exec /bin/bash /absolute/path/to/project/scripts/agent.sh</string>
</array>
```

Quote an actual script path safely if it contains spaces. Check expected output
and logs as well as exit status. `exec` replaces the shell; it does not make the
job system PID 1.

**Never do this:** Claim current Claude crashes merely because `.claude/` exists,
or install a scheduler/wrapper as an implicit prerequisite for normal RPI work.

**Disposition:** Retained historical workaround with unverified applicability;
no harness-fixed retirement without version-bound reproduction evidence.

---

## Error #39: `gh` CLI fails with "Projects (classic) deprecated" GraphQL error

**Symptom:** `gh issue view`, `gh pr edit`, `gh pr view`, or other `gh` commands fail with: "GraphQL: Projects (classic) is being deprecated in favor of the new Projects experience, see: https://github.blog/changelog/2024-05-23-sunset-notice-projects-classic/. (repository.issue.projectCards)" or similar `(repository.pullRequest.projectCards)`.

**Root cause:** The installed `gh` CLI version uses GraphQL queries that reference the deprecated `projectCards` and `projectColumns` fields. GitHub removed classic Projects from the API, so older `gh` versions break on any command that touches project metadata.

**Correct approach — always do this:**
```bash
# Upgrade gh CLI to latest version:
brew upgrade gh
# or:
gh upgrade

# Verify the version is recent enough:
gh --version
```

**Never do this:**
```bash
# Don't retry the same command — it will keep failing:
gh issue view 17     # ← fails with GraphQL error
gh issue view 17     # ← same error, upgrading is the only fix

# Don't try to work around it with --json (same API, same error):
gh pr edit 2 --title "..." --body "..."  # ← still hits projectCards
```

**Key detail:** The error looks like a permissions or API issue but is actually a client version problem. The `gh` CLI embeds GraphQL queries at build time — no amount of authentication or flag changes will fix it. The only fix is upgrading.

---

## Error #40: Agent uses `python3` instead of `uv run python` — bypasses venv

**Symptom:** `ModuleNotFoundError: No module named 'openai'` (or any project dependency) when the agent runs `python3 -c "from openai import OpenAI..."` or `export $(grep -v '^#' .env | xargs) && python3 -c "..."`. The dependency is installed in the project's venv but not in the system Python.

**Root cause:** The agent uses bare `python3` instead of `uv run python`, bypassing the virtual environment entirely. The project manages dependencies with `uv` (or `pip` in a venv), but the system Python has no access to them.

**Correct approach — always do this:**
```bash
# Always use uv run to execute within the project's venv:
uv run python -c "from openai import OpenAI; print('ok')"
uv run python scripts/my_script.py

# For environment variables, source .env inside uv run:
uv run bash -c 'source .env && python -c "from openai import OpenAI; print(\"ok\")"'

# Or use dotenv support if available:
uv run --env-file .env python scripts/my_script.py
```

**Never do this:**
```bash
# Don't use bare python3 in projects with a venv:
python3 -c "from openai import OpenAI"              # ← ModuleNotFoundError
export $(grep -v '^#' .env | xargs) && python3 ...  # ← env vars loaded but wrong Python

# Don't assume system Python has project dependencies:
python3 scripts/my_script.py                         # ← works on your machine != works correctly
```

**Key detail:** This applies to any venv-based project, not just `uv`. If the project uses `poetry`, use `poetry run python`. If it uses `pipenv`, use `pipenv run python`. The pattern is: always invoke Python through the project's dependency manager.

---

## Error #41: Over-escaping `!=` as `\!=` in inline Python — SyntaxError

**Symptom:** Running inline Python in a shell command produces `SyntaxError: unexpected character after line continuation character` pointing at `\!=`:
```
if batch.status \!= 'completed':
                ^
SyntaxError: unexpected character after line continuation character
```

**Root cause:** Same root cause as [Error #17](#error-17-jq-syntax-error--shell-escaping-corrupts-filter-expressions) (jq over-escaping), but in Python. The agent escapes `!=` as `\!=` inside a shell command that runs Python. In Python, `\` is a line continuation character, so `\!` is invalid syntax. Inside single-quoted shell strings, `!` is literal and needs no escaping.

**Correct approach — always do this:**
```bash
# Use single quotes for inline Python — no escaping needed:
python3 -c '
if batch.status != "completed":
    print("still running")
'

# For complex scripts, write to a temp file instead of inline:
uv run python scripts/check_status.py
```

**Never do this:**
```bash
# Don't escape operators inside single-quoted strings:
python3 -c 'if batch.status \!= "completed": ...'  # ← SyntaxError

# Don't use double quotes for inline Python (fragile escaping):
python3 -c "if batch.status != 'completed': ..."    # ← works but breaks with $variables
```

**Key detail:** This is the Python variant of Error #17. The rule is universal: inside single-quoted shell strings (`'...'`), ALL characters are literal — no escaping is needed or wanted. This applies to jq, Python, awk, sed, and any other language embedded in shell commands.

---

## Error #42: Python script fails — package-relative imports without `-m` flag

**Symptom:** `ModuleNotFoundError: No module named 'scripts'` when running `uv run python scripts/ab_testing/scorer.py`, even though the file exists and the import `from scripts.ab_testing.config import MANIFEST_PATH` is valid.

**Root cause:** Running a script directly with `python scripts/foo.py` sets `scripts/` as the script's directory, not a package. Python doesn't add the parent directory to `sys.path`, so `from scripts.ab_testing.config import ...` fails because `scripts` isn't recognized as an importable package.

**Correct approach — always do this:**
```bash
# Use -m flag to run as a module (treats parent dir as the package root):
uv run python -m scripts.ab_testing.scorer

# Or ensure the project is installed in development mode:
uv pip install -e .
uv run python scripts/ab_testing/scorer.py  # ← now works because package is installed

# Or run from the project root with PYTHONPATH set:
PYTHONPATH=. uv run python scripts/ab_testing/scorer.py
```

**Never do this:**
```bash
# Don't run scripts directly when they use package-relative imports:
uv run python scripts/ab_testing/scorer.py                    # ← ModuleNotFoundError
python scripts/ab_testing/scorer.py                           # ← same error
cd scripts/ab_testing && uv run python scorer.py              # ← even worse
```

**Key detail:** If a Python file uses `from package.module import ...` (dotted package path), it expects to be run as part of a package. Check the imports at the top of the file before deciding how to invoke it. If you see dotted imports from the project root, use `-m`.

---

## Error #43: Agent indexes JSON list with string key — TypeError

**Symptom:** `TypeError: list indices must be integers or slices, not str` when parsing JSON inline with `python3 -c "..."`. The agent assumes the JSON structure is a dict (object) when it's actually a list (array).

**Root cause:** The agent guesses the shape of JSON data without inspecting it first. Common when parsing API responses, config files, or command output where the top-level type varies (some endpoints return arrays, others return objects).

**Correct approach — always do this:**
```bash
# Inspect the structure first:
uv run python -c "import json; data = json.load(open('file.json')); print(type(data)); print(data[:2] if isinstance(data, list) else list(data.keys())[:5])"

# Handle both shapes defensively:
uv run python -c "
import json
data = json.load(open('file.json'))
if isinstance(data, list):
    for item in data:
        print(item.get('name', 'unknown'))
else:
    print(data['name'])
"
```

**Never do this:**
```bash
# Don't assume dict when structure is unknown:
python3 -c "import json; data = json.load(open('f.json')); print(data['papers'])"
# ← TypeError if data is a list, not a dict

# Don't chain access without checking:
python3 -c "import json; d = json.load(open('f.json')); print(d['results'][0]['name'])"
# ← could fail at any level if the structure differs from expectations
```

**Key detail:** When working with unfamiliar JSON (API responses, generated files, command output), always inspect `type(data)` and a sample of the contents before writing access code. A 5-second check prevents cryptic TypeErrors.

---

## Error #44: `git push --tags` pushes ALL local tags — old tags cause push failure

**Symptom:** An intended release publishes unrelated tags or reports rejection
of an old tag even though other refs were updated.

**Root cause:** `--tags` selects every local tag; `--follow-tags` can also select
more than the named release because it includes reachable annotated tags.

**Correct approach — always do this:** After full local release verification and
explicit publication authorization, push only the named tag:

```bash
git push origin v1.0.0
```

Inspect the resulting remote ref even if another ref in a multi-ref push failed.

**Never do this:** Use `--tags`, `--follow-tags`, or force a tag to fix an
unrelated rejection. Do not move already published release tags.

---

## Error #45: Agent fabricates filesystem paths — "No such file or directory"

**Symptom:** `git -C /Users/you/Documents/Projects/some-repo pull --rebase` fails with `fatal: cannot change to '/Users/you/Documents/Projects/some-repo': No such file or directory`. The actual path was `/Users/you/code/some-repo`.

**Root cause:** The agent guesses or hallucinates a plausible filesystem path instead of using the known working directory or discovering the path. Common fabrications include inventing parent directory names (`Projects`, `Development`, `repos`, `workspace`), getting the nesting level wrong, or mixing up similar project names. This is the filesystem equivalent of Error #23 (fabricating GitHub identifiers).

**Correct approach — always do this:**
```bash
# Use the project's working directory (provided by the environment):
git -C /Users/you/code/some-repo pull --rebase

# If you need to find another project, discover it:
ls /Users/you/code/
# Then use the actual name from the listing

# Or ask the user for the path if it's not discoverable
```

**Never do this:**
```bash
# Don't guess directory names:
git -C /Users/you/Documents/Projects/some-repo pull --rebase
# ← "Documents/Projects" is fabricated — the real parent is "code"

# Don't assume paths from previous sessions are still valid:
cd /Users/you/projects/old-name/src
# ← directories may have been renamed, moved, or deleted
```

**Key detail:** The working directory is always available from the environment. For cross-project operations, use `ls` or Glob to discover paths — never guess directory names. Even plausible-sounding names like `Projects` or `repos` are often wrong.

---

## Error #46: Scaffolding tool fails on non-empty directory

**Symptom:** `pnpm create next-app@latest .` fails with "The directory contains files that could conflict: .claude/, CLAUDE.md, README.md". The scaffolder lists the conflicting files and aborts without creating the project.

**Root cause:** Project scaffolding tools (`create-next-app`, `create-react-app`, `create-vite`, `create-astro`, etc.) require an empty or nearly-empty directory. The agent creates project configuration files (CLAUDE.md, `.claude/`, README.md, `.gitignore`) BEFORE running the scaffolder, then the scaffolder detects existing files and refuses to proceed. This commonly happens during `/bootstrap` when the agent sets up the RPI config files as a first step instead of last.

**Correct approach — always do this:**
```bash
# 1. Run the scaffolding tool FIRST in a clean directory:
pnpm create next-app@latest . --typescript --tailwind --eslint --app --src-dir

# 2. THEN add project config files after scaffolding completes:
# (CLAUDE.md, .claude/, etc.)
```

**Never do this:**
```bash
# Don't create config files before scaffolding:
mkdir -p .claude/commands
echo "# Project" > CLAUDE.md           # ← directory is no longer empty
pnpm create next-app@latest . ...       # ← fails: "files that could conflict"

# Don't try to force-scaffold over existing files:
# Most scaffolders don't have a --force flag, and the ones that do may overwrite your config
```

**Key detail:** This applies to ALL project scaffolding tools — they all expect a clean target directory. The rule is simple: scaffold first, configure second. If the directory already has a git repo with initial commits, use a temporary directory to scaffold, then copy the result back (excluding `.git`).

---

## Error #47: Piping API response to JSON parser without error checking

**Symptom:** A parser hides an HTTP or transport error.

**Root cause:** Pipelines return the last program status by default; curl does not fail on HTTP errors without the relevant flag.

**Correct approach — always do this:**

Save the body to a task-owned temporary file, capture curl's transport exit
and HTTP status, and parse only expected success responses. For terse scripts:

```bash
set -o pipefail
curl -fsS "$URL" | jq '.'
```

Even if jq accepts empty input and exits 0, pipefail retains curl's failure.
Do not dump private response bodies into logs. See [curl documentation](https://curl.se/docs/manpage.html).

**Never do this:** Assume `curl -f | jq` fails as a pipeline without pipefail.

---

## Error #48: Agent commits or pushes to the wrong branch

**Symptom:** A commit or push targets an unintended branch.

**Root cause:** The agent relied on stale branch context rather than checking
the actual worktree and ref.

**Correct approach — always do this:** Run `git branch --show-current` and
`git status` before a commit; stage only identified task files. Keep temporary
branches local. After complete local verification and integration, inspect
remote triggers and confirm the exact authorized integration ref before its
single push. A production branch requires explicit production authorization.
Hook enforcement is defense in depth; verify the actual supported harness
and rule before claiming that a guard guarantees safety.

**Never do this:** Append an automatic pull/push chain to every commit or
assume a branch name establishes deployment authority.

---

## Error #49: Sub-agents create git conflicts from parallel work

**Symptom:** Multiple sub-agents or teammates make changes in parallel. When the main agent tries to commit their combined work, there are merge conflicts, overlapping file edits, or orphaned references. In one observed case, 10 parallel agents all succeeded individually but left behind overlapping test files and broken cross-references that required a full cleanup session.

**Root cause:** Sub-agents operate in isolated contexts and don't see each other's changes. When two agents edit the same file (or files that reference each other), the results conflict. The orchestrating agent doesn't enforce file ownership boundaries or centralize git operations.

**Correct approach — always do this:**
```
When orchestrating parallel agents:
1. Break work so each agent owns DISTINCT files — no overlap
2. Only the main agent handles git commit/push
3. Sub-agents write changes to working directories or /tmp/agent-<name>/
4. Main agent reviews all changes for conflicts before committing
5. Run the full test suite AFTER combining all agent output
```

**Never do this:**
```
# Don't let sub-agents commit independently:
Sub-agent 1: git add . && git commit -m "fix: agent-1 changes" && git push
Sub-agent 2: git add . && git commit -m "fix: agent-2 changes" && git push
# ← Race condition, merge conflicts, overlapping edits

# Don't assume parallel agents produce compatible output:
# Even if each agent's changes pass tests individually,
# the COMBINED changes may conflict
```

**Key detail:** Agent Teams are particularly susceptible because teammates are fully independent Claude Code sessions. They can each commit and push without coordination. The CLAUDE.md rule "only the main agent handles git commit/push" prevents this. For Agent Teams, use the shared task list to track file ownership and prevent teammates from claiming overlapping work.

---

## Error #50: Agent skips test suite after config or infrastructure changes

**Symptom:** Agent modifies configuration files (tsconfig, eslint config, package.json, environment variables, database config, CI workflows) and immediately proceeds to the next task without running tests. Later in the session — or in a subsequent session — tests fail due to the config change. The agent then burns multiple rounds debugging failures that could have been caught immediately.

**Root cause:** The agent treats config changes as "not code" and doesn't apply the same verify-after-change discipline it uses for source code. But config changes often have broader blast radius than code changes — a single tsconfig modification can break hundreds of files, and a dependency update can introduce incompatibilities across the entire test suite.

**Correct approach — always do this:**
```bash
# After ANY config or infrastructure change, immediately run the full suite:
pnpm run typecheck 2>&1 && pnpm run lint 2>&1 && pnpm run test 2>&1

# This applies to ALL of these:
# - tsconfig.json, eslint.config.*, prettier.config.*
# - package.json (dependencies, scripts, engines)
# - .env files, environment variable changes
# - Database migrations, schema changes
# - CI/CD workflow files
# - Docker/container configuration
# - Build configuration (vite.config, next.config, webpack.config)
```

**Never do this:**
```bash
# Don't modify config and move on without testing:
# Edit tsconfig.json to add strict mode
# Edit next.config.js to change build output
# → Immediately start writing new feature code
# ← Tests are now broken but you won't find out until much later
```

**Key detail:** Config changes have a multiplicative failure pattern — they can break files the agent never touched. Running the test suite immediately after a config change costs minutes but saves the multi-round debug cycles that happen when failures are discovered later with more changes stacked on top.

---

## Error #51: CI explosion from parallel agent pushes

**Symptom:** Parallel agents publish branches and trigger redundant hosted builds.

**Root cause:** Working branches were treated as remote milestones instead of local work.

**Correct approach — always do this:**

Keep every agent branch/worktree local. Coordinate file ownership and scoped
tests. Integrate the complete result locally, run full applicable gates, inspect
workflow/deployment triggers, and push the completed integration branch once
when authorized. Never trigger Vercel Previews.

**Never do this:** Push feature branches, create PRs, or dispatch remote CI for experiments.

---

## Error #52: Agent assumes GitHub labels exist when creating issues

**Symptom:** `gh issue create --label "chore"` (or `"security"`, `"bug"`, `"enhancement"`, etc.) fails with `could not add label: 'chore' not found`. When multiple issues are created as parallel sibling tool calls, the first failure cascades via Error #1 and kills all remaining issue creations.

**Root cause:** The agent assumes standard label names exist on the repository. GitHub repos start with no labels by default (or a small default set). Custom repos, forks, and newly created repos often have none of the labels the agent expects. The agent never checks what labels are available before using them.

**Correct approach — always do this:**
```bash
# Check what labels exist before using them:
gh label list

# If the label doesn't exist, create it first:
gh label create "chore" --description "Maintenance tasks" --color "ededed"

# Or omit labels on creation and add them after:
gh issue create --title "..." --body "..."
# Then add labels if they exist:
gh issue edit <number> --add-label "chore" 2>/dev/null || true

# When creating multiple issues, do it sequentially (Error #1):
gh issue create --title "Issue 1" --body "..." && \
gh issue create --title "Issue 2" --body "..."
```

**Never do this:**
```bash
# Don't assume labels exist:
gh issue create --title "fix: auth bug" --label "bug" --label "security"
# ← fails if either label is missing

# Don't create multiple issues as parallel sibling tool calls:
# Tool call 1: gh issue create --label "chore" ...  ← fails, kills siblings
# Tool call 2: gh issue create --label "security" ... ← cancelled
# Tool call 3: gh issue create --label "bug" ... ← cancelled
```

**Key detail:** This error is especially common after `/pre-launch` audits, where the agent tries to create multiple issues for findings and assigns category labels. The fix is to either create all needed labels upfront (`gh label create`), or omit labels entirely and let the user categorize. When creating multiple issues, always do it sequentially to avoid the parallel cancellation cascade.

---

## Error #53: Agent runs `gh pr create` without checking for existing PR

**Symptom:** `gh pr create --base main --head develop --title "Release v0.3.0"` fails with `a pull request for branch "develop" into branch "main" already exists: https://github.com/.../pull/36`. The agent then tries to recover by editing or recreating the PR, wasting turns.

**Root cause:** The agent doesn't check whether a PR already exists for the head-to-base branch pair before attempting to create one. This commonly happens during release workflows where a develop-to-main PR may already be open from a previous push, or when a previous agent session created the PR but didn't finish its workflow.

**Correct approach — always do this:**
```bash
# Only within an explicitly authorized completed release PR workflow:
# Check if a PR already exists for the branch pair:
EXISTING_PR=$(gh pr list --head develop --base main --json number --jq '.[0].number')

if [ -n "$EXISTING_PR" ]; then
  # Update the existing PR:
  gh pr edit "$EXISTING_PR" --title "Release v0.3.0" --body "..."
else
  # Create a new PR:
  gh pr create --base main --head develop --title "Release v0.3.0" --body "..."
fi
```

**Never do this:**
```bash
# Don't blindly create without checking:
gh pr create --base main --head develop --title "Release v0.3.0" --body "..."
# ← fails if PR already exists for develop → main
```

**Key detail:** This is especially common in gitflow-style workflows where a develop-to-main PR persists across multiple release cycles, and in CI/CD pipelines where automated agents create PRs. The same pattern applies to any repeated workflow — release PRs, dependency update PRs, sync PRs. Always check first and update if one exists.

---

## Error #54: `git checkout --` fails on unmerged (conflicted) files

**Symptom:** `git checkout -- src/components/chat/chat-interface.tsx src/components/onboarding/onboarding-flow.tsx ...` fails with `error: path 'src/components/chat/chat-interface.tsx' is unmerged` for every file listed. The agent was trying to discard changes during a merge or rebase conflict, but `git checkout --` doesn't work on files in a conflicted state.

**Root cause:** During a merge, rebase, or cherry-pick that hits conflicts, affected files enter an "unmerged" state. `git checkout -- <file>` is designed to restore a file to its last committed version, but it can't do that for unmerged files because git doesn't know which version to restore to — there are multiple candidates (ours, theirs, base). The agent treats `git checkout --` as a universal "discard changes" command without considering the conflict state.

**Correct approach — always do this:**
```bash
# If you want to keep YOUR version of conflicted files:
git checkout --ours src/components/chat/chat-interface.tsx
git add src/components/chat/chat-interface.tsx

# If you want to keep THEIR version of conflicted files:
git checkout --theirs src/components/chat/chat-interface.tsx
git add src/components/chat/chat-interface.tsx

# If you want to abort the entire merge/rebase/cherry-pick:
git merge --abort       # during a merge
git rebase --abort      # during a rebase
git cherry-pick --abort # during a cherry-pick

# To check what state you're in:
git status  # Shows "Unmerged paths" section with conflicted files

# Resolve each conflict after comparing both versions; preserve unrelated work.
# During rebase, ours/theirs refer to rebased-history roles, not simple authorship.
```

**Never do this:**
```bash
# Don't use plain checkout -- on conflicted files:
git checkout -- src/components/chat/chat-interface.tsx
# ← "error: path '...' is unmerged"

# Don't retry the same command on more files:
git checkout -- file1.tsx file2.tsx file3.tsx
# ← same error for every file, all are unmerged
```

**Key detail:** The error message "is unmerged" means you're in the middle of a conflicted merge/rebase/cherry-pick. Before trying to discard changes, check `git status` to see the conflict state. The three options are: resolve the conflicts (edit + `git add`), pick a side (`--ours`/`--theirs`), or abort the operation entirely. Plain `git checkout --` is only for non-conflicted files.

---

## Error #55: `git merge` blocked by untracked working tree files

**Symptom:** Git refuses to overwrite an untracked local file.

**Root cause:** The file may contain user work or a curated artifact absent from the incoming branch.

**Correct approach — always do this:**

Inspect and compare the conflicting content. Preserve it outside the collision
with an exact recovery path, or commit it when appropriate. Resolve duplicates
only after verifying ownership and equivalence. Retry the merge locally and
restore/reconcile preserved content. Coordinate agent output paths beforehand.

**Never do this:** Delete untracked plans because the branch has a similarly named file, or use blind `git clean`.

---

## Error #56: Agent merges to `main` without understanding deployment topology

**Symptom:** A remote merge or push triggers an unapproved production deployment.

**Root cause:** The branch name alone does not reveal publication side effects.

**Correct approach — always do this:**

Inspect actual workflow and hosting triggers. Complete work in local branches
and integrate locally into the documented non-production integration branch,
or the canonical branch when the repository has only one. Local integration
does not publish. Production-triggering remote actions require explicit release
authorization after local gates. Treat existing dependency PRs as read-only
inputs until their mutations are authorized.

**Never do this:** Assume every main branch deploys, or assume an ordinary cleanup request authorizes production.

---

## Error #57: Sequential merge cascade wastes CI resources (O(n^2) rebase storm)

**Symptom:** Merging dependency PRs repeatedly invalidates remaining checks and triggers extra builds.

**Root cause:** Hosted merges are being used as the integration loop.

**Correct approach — always do this:**

Combine compatible dependency changes in local branches, give risky upgrades
focused local review, integrate the complete result locally, and run full gates
once on that candidate. Inspect triggers and publish only the completed
authorized integration branch. Existing remote PR cleanup is a separately
reviewable action, not an excuse to create a new batch PR.

**Never do this:** Rebase, push, wait and merge repeatedly to experiment on hosted CI.

---

## Error #58: Agent deploys untested code to production (no preview verification)

**Symptom:** A build passes but a deployment runtime fails on startup.

**Root cause:** Build success does not prove runtime parity; bundling, cold starts, and platform-specific resolution need verification.

**Correct approach — always do this:**

Run local build, tests, lint, typechecks, runtime smoke tests, and available
platform packaging preflights before publication. Inspect bundled artifacts
and existing deployment logs read-only. Never create Vercel Previews. Record
any remaining platform-only uncertainty; production remains a separately
authorized release after local gates. Prepare rollback and verify the actual
authorized deployment when released.

**Never do this:** Push a non-production branch to create a Preview or use production as a diagnostic loop.

---

## Error #59: Agent improvises production recovery with repeated failed deployments

**Symptom:** Attempts to diagnose by redeploying prolong an outage.

**Root cause:** Recovery and investigation were mixed into a billed experiment loop.

**Correct approach — always do this:**

Use the project's authorized incident rollback procedure to restore a known
good deployment, then verify service. Read existing logs and reproduce locally.
Keep repair branches local, complete full gates and platform preflights, and
obtain any required production authorization for the fixed release. Never
create Previews or redeploy broken code just to capture logs.

**Never do this:** Promote a broken deployment, dispatch hosted experiments, or exceed incident authority.

---

## Error #60: Agent treats all dependency updates as equal risk

**Symptom:** An upgrade affects far more runtime behavior than its review covered.

**Root cause:** Version bump size alone does not establish risk.

**Correct approach — always do this:**

Classify dependency changes by runtime use, compatibility, affected surfaces
and platform behavior. Every candidate still needs complete applicable local
gates; increase targeted runtime and packaging checks for risky changes.
Review framework upgrades individually before combining verified changes into
local integration. Publish once under the owner remote-budget policy.

**Never do this:** Treat dev dependencies as risk-free or replace local verification with a Preview deployment.

---

## Error #61: Silent fallback masks production data failure

**Symptom:** The app appears to work fine — pages load, no errors in the console, health checks pass. But users see stock/placeholder content instead of real data. The root cause is a backend failure (database permission error, API auth expiry, missing migration grant) that triggers a fallback code path. The fallback serves default data silently, with no logging, no alerting, and no health check degradation. Nobody knows production is broken until a user reports seeing wrong content.

**Root cause:** The agent writes "resilient" code with graceful degradation — if the primary data fetch fails, return fallback data. This is good practice in theory, but the agent implements it without any observability: no error-level logging when the fallback activates, no health endpoint that detects degraded state, no metrics or alerts. The fallback becomes a silent failure mode that hides real production bugs.

Real example: A Supabase migration created tables but didn't include `GRANT SELECT TO anon`. The `getStoriesServer()` function got a 403, silently fell back to `FALLBACK_STORIES` with stock images. The site looked "fine" — it just wasn't showing real content.

**Correct approach — always do this:**

```typescript
// When implementing fallback behavior, ALWAYS add three layers:

// 1. ERROR-LEVEL LOGGING when fallback activates
async function getStoriesServer() {
  const { data, error } = await supabase.from('stories').select('*');
  if (error || !data?.length) {
    // NOT console.log — this must be ERROR level, searchable, alertable
    console.error('[STORIES_FALLBACK] Primary fetch failed, serving fallback data', {
      error: error?.message,
      code: error?.code,
      timestamp: new Date().toISOString(),
    });
    return FALLBACK_STORIES;
  }
  return data;
}

// 2. HEALTH ENDPOINT that detects degraded state
// GET /api/health should check actual data sources, not just "server is up"
async function healthCheck() {
  const stories = await supabase.from('stories').select('id').limit(1);
  return {
    status: stories.error ? 'degraded' : 'healthy',
    stories: { status: stories.error ? 'fallback' : 'ok' },
  };
}

// 3. ALERTING on the health endpoint or error logs
// Configure your monitoring (Vercel, Datadog, etc.) to alert on:
// - Health endpoint returning "degraded"
// - [STORIES_FALLBACK] appearing in function logs
```

**Never do this:**

```typescript
// Don't create silent fallbacks:
async function getStoriesServer() {
  const { data, error } = await supabase.from('stories').select('*');
  if (error || !data?.length) {
    return FALLBACK_STORIES;  // ← silent! no logging, no alerting
  }
  return data;
}

// Don't write health checks that only test connectivity:
async function healthCheck() {
  return { status: 'ok' };  // ← always "ok", even when serving fallback data
}

// Don't log fallbacks at INFO/DEBUG level:
console.log('Using fallback stories');  // ← invisible in production log noise
```

**Key detail:** The pattern applies to any code with fallback behavior — not just database queries. API clients with default responses, feature flags with hardcoded defaults, CDN fallbacks to origin, cache miss handlers that return stale data. Whenever you write a fallback path, ask: "If this fallback activates in production, will anyone know?" If the answer is no, add error logging and health check coverage before shipping.

---

## Error #62: Agent pushes Supabase migration to remote without local testing

**Symptom:** An untested migration fails against a remote database.

**Root cause:** Syntax success and postgres-only queries do not validate migration ordering, client grants or RLS.

**Correct approach — always do this:**

Use a task-owned disposable local stack, preserve shared local data, and run
`supabase db reset --local`. Discover the local connection with `supabase status`.
Test anon, authenticated owner, authenticated nonowner and service access;
include expected denials and future-table exposure. Grants permit operations;
RLS policies restrict rows. Preserve intentional public-data and owner-only
contracts. Local success does not guarantee remote schema/data parity.
Remote `supabase db push` is a separate authorized application after local
verification and target inspection, never part of a local test command.

**Never do this:** Push migrations to debug them, grant every future table to anon, or assume local success proves remote success.

---

## Error #63: Parallel agents each run full test suite, exhausting local resources

**Symptom:** The machine becomes unresponsive — CPU pegged, memory exhausted, swap thrashing. Activity Monitor or `htop` shows hundreds of Node/Python/test-runner processes. The agent launched N parallel worktree agents (e.g., 10), and each independently runs the project's full test suite. With a 7,000-test suite, that's ~70,000 tests executing simultaneously, each test runner spawning its own worker processes. The result is N x workers-per-suite processes competing for CPU and memory. The machine may need a hard reboot.

**Root cause:** The agent treats "verify your changes" as "run the full test suite" and does this for every parallel agent. No coordination limits how many agents run tests concurrently. Each worktree agent has its own copy of the codebase and independently spawns a full test runner (vitest, jest, pytest, etc.) with its default worker count. The multiplication is catastrophic: 10 agents x 4 workers each = 40 concurrent test processes, each loading the full application into memory.

Real example: An agent implementing 10 independent features launched 10 worktree agents. Each ran `pnpm test` (vitest with the full 6,900-test suite). This created 478 Node processes simultaneously. The machine with 16GB RAM was completely overwhelmed. The agent acknowledged the mistake but couldn't cancel the already-running processes.

**Correct approach — always do this:**

```bash
# 1. Agents run ONLY tests related to their changed files
pnpm vitest run src/features/my-feature/  # scoped to changed directory
pytest tests/test_my_module.py            # specific test file only

# 2. Keep at most three implementers in the current phase; fewer if resources require
# Launch wave 1 (3 agents), wait for completion, then wave 2

# 3. Defer full test suite to the integration step
# After all agents complete and changes are merged:
pnpm test  # one full run, once, at the end

# 4. If agents must run broader tests, limit workers
pnpm vitest run --pool=threads --poolOptions.threads.maxThreads=2
pytest -x --numprocesses=2
```

**Never do this:**

```bash
# Don't let each of N parallel agents run the full suite:
# Agent 1: pnpm test     ← full 7,000-test suite
# Agent 2: pnpm test     ← another full suite
# ...
# Agent 10: pnpm test    ← 70,000 tests total, machine melts

# Don't assume "more parallel = faster":
# 10 agents x full suite = resource starvation, not speed
```

**Key detail:** Cancellation and process lifetime depend on the harness and
tool contract (Error #1). Inspect every returned result and track owned process
handles; do not infer that a sibling failure killed or completed all work.
Scope tests and concurrency, and preserve ownership before stopping processes.

---

## Error #64: Agent implements a finding's recommendation literally, breaking an invariant the fix never checked

**Symptom:** A code-review or pre-launch finding correctly diagnoses a real problem and proposes a fix. A remediation agent implements that fix exactly as written, the targeted symptom disappears, tests for the symptom pass — and a different, often higher-value behavior silently regresses. The diagnosis was right; the recommendation was incomplete; nobody verified the assumption the recommendation rested on before shipping it.

**Root cause:** The agent treats a finding's `Recommendation` field as a work order rather than a hypothesis. A finding is written by a specialist with a partial mental model of one domain; its proposed fix usually carries an unstated assumption ("mechanism Y can replace mechanism X") that holds for the case the specialist looked at but not for every case in production. The remediation agent's TDD test guards the *symptom the finding named*, not the *invariant the fix could break*, so the regression sails through green tests. The deeper trap is a value swap: trading a correctness, security, or UX invariant for a non-functional metric (perf, ISR, bundle size) without anyone deciding that trade was worth it.

Real example: A Performance Engineer finding (`FE-M1`) correctly identified that the highest-traffic route had lost ISR (Incremental Static Regeneration) because it called a server-side `getServerLocale()` on every request. The recommendation: move locale handling to a client component (`LocaleSync`) so the route could be statically generated again. The remediation agent implemented exactly that. But `LocaleSync` only read the `?lang=` URL param — it never read the locale **cookie**. `getServerLocale()` resolved locale from the cookie for returning users. So after the "fix," every returning English user (the cookie path) got a page body in the wrong language. The symptom test ("ISR is restored") passed; no test asserted "an English cookie user sees an English body." You cannot have both ISR and server-rendered per-user locale unless the whole page body moves to client components — a real architectural trade the finding never surfaced and nobody chose. The ISR win was not worth breaking i18n for all English users.

**Correct approach — always do this:**

- **Treat the recommendation as a hypothesis.** Before implementing, independently confirm its assumptions in the real code. If the fix swaps mechanism X for mechanism Y, verify Y covers *every* input X handled — every locale source, every auth path, every caller — not just the one the finding named.
- **Author findings with a `Regression risk` field.** State the invariants that must still hold, the assumptions the fix depends on, and any property the fix trades away. A blanket "none" on a behavior-changing finding is a contract failure.
- **Guard the invariant, not the symptom.** The TDD failing-test must assert the behavior the fix could break ("English cookie user still sees an English body"), not merely that the diagnosed symptom is gone ("ISR is restored").
- **Halt on an unsafe trade.** If verification shows the recommendation is incomplete, wrong, or trades a correctness/security/UX invariant for a metric, STOP and escalate to a human with the unresolved trade. Halting one finding beats shipping a regression.

**Never do this:**

- Don't implement a finding's `Recommendation` verbatim because it came from an audit — audits diagnose well and prescribe narrowly.
- Don't let "the symptom test is green" stand in for "nothing else broke." Symptom coverage is not invariant coverage.
- Don't silently trade correctness for performance. If a fix forces that choice, it is a human decision, not an autonomous one.

**Key detail:** The chain of failure has three independent links, and breaking any one stops it: (1) the finding states a `Regression risk` so the assumption is visible; (2) the implementer verifies that assumption against real code before writing the fix; (3) a test asserts the invariant, not the symptom. The contract enforces link 1 (`validate-findings.py` requires the field); the remediation gate enforces links 2 and 3. Maps to Rule #83.
