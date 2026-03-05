# Known Agent Errors — Universal Catalog

Documented from real recurring issues across projects. Each entry includes the symptom, root cause, and the correct approach to use from the start.

**How to use this file:** Read this before starting any work. These are patterns Claude Code agents hit repeatedly — the solutions are known and should be applied from the first attempt, not rediscovered.

---

## Error #1: Sibling tool call errored (parallel verification commands)

**Symptom:** Running `typecheck` and `lint` (or any verification commands) as parallel Bash tool calls. When one exits non-zero, the others are killed with "Sibling tool call errored" — their output is lost completely.

**Root cause:** Claude Code kills all sibling tool calls when any one fails. This applies to ALL tool types — Bash, TaskOutput, Read, etc.

**Correct approach — always do this:**
```bash
# Chain sequentially — use ; to run all regardless of exit codes:
pnpm run typecheck 2>&1; pnpm run lint 2>&1

# Or use && to stop on first failure:
pnpm run typecheck 2>&1 && pnpm run lint 2>&1
```

**Never do this:**
```
# Parallel sibling Bash tool calls — one failure kills the rest:
Tool call 1: pnpm run typecheck 2>&1
Tool call 2: pnpm run lint 2>&1   ← killed if typecheck fails

# Parallel sibling TaskOutput calls — same problem:
Tool call 1: TaskOutput(task-id-1)  ← "No task found" → kills siblings
Tool call 2: TaskOutput(task-id-2)  ← "Sibling tool call errored"
Tool call 3: TaskOutput(task-id-3)  ← "Sibling tool call errored"
```

**Applies to:** ALL parallel sibling tool calls — Bash, TaskOutput, Read, sub-agents. Any tool that can error will kill its siblings. Check background tasks sequentially, not in parallel.

---

## Error #2: Shell cwd resets to main repo when working in a worktree

**Symptom:** Agent is working in a git worktree (e.g., `/project-e2e-fix/`). After a Bash command, the shell cwd silently resets to the main repo (e.g., `/project/`). All subsequent commands run in the wrong directory without any warning. The message `Shell cwd was reset to /path/to/main/repo` appears in output.

**Root cause:** Claude Code's shell state doesn't persist between calls. The working directory resets to the primary working directory, not the worktree.

**Correct approach — always do this when working in a worktree:**
```bash
# ALWAYS prefix every command with cd to the worktree using absolute path:
cd /absolute/path/to/worktree && pnpm run typecheck 2>&1

# ALWAYS use absolute paths for git operations in worktrees:
cd /absolute/path/to/worktree && git status

# For multi-command chains:
cd /absolute/path/to/worktree && pnpm run typecheck 2>&1; cd /absolute/path/to/worktree && pnpm run lint 2>&1
```

**Never do this:**
```bash
# Don't rely on cwd being in the worktree from a previous command:
git status  # ← this runs in main repo, not worktree!
pnpm run test  # ← also wrong directory
```

**Applies to:** Any work done outside the primary working directory — worktrees, monorepo subdirectories, temporary clones.

---

## Error #3: Commit rejected by pre-commit hook (typecheck/lint failure)

**Symptom:** Agent runs `git add <files> && git commit -m "..."` and it fails with exit code 1 because the pre-commit hook triggers a full typecheck/lint across the project and finds errors. Wasted time: the commit fails, the agent must fix errors, then re-stage and re-commit.

**Root cause:** The agent skipped running verification checks before committing. Pre-commit hooks enforce the same checks (typecheck, lint, tests) — discovering failures at commit time means unnecessary rework.

**Correct approach — always do this:**
```bash
# 1. Run the checks FIRST (same ones the pre-commit hook runs):
pnpm run typecheck 2>&1; pnpm run lint 2>&1

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
gh pr checks <PR> --json 2>&1 | head -5

# Known correct fields for common commands:
# gh pr checks: name, state, bucket, completedAt, description, event, link, startedAt, workflowName
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

**Symptom:** Running `node dist/index.js --version` fails with `SyntaxError: Invalid or unexpected token` pointing at the shebang line (`#!/usr/bin/env node`). The stack trace shows `compileSourceTextModule` (ESM loader).

**Root cause:** The built file has a shebang (`#!/usr/bin/env node`) and uses ESM (`"type": "module"` in package.json). Node's ESM loader doesn't strip shebangs the same way as CJS. Running `node <file>` directly causes the shebang to be parsed as JavaScript.

**Correct approach — always do this:**
```bash
# Option 1: Execute via the shebang (needs +x permission):
chmod +x dist/index.js && ./dist/index.js --version

# Option 2: Use the package bin entry:
npx . --version
# or after linking:
pnpm link --global && <cli-name> --version

# Option 3: Check package.json "bin" field and use that name:
grep -A2 '"bin"' package.json
```

**Never do this:**
```bash
# Don't run ESM CLI files with node directly:
node dist/index.js --version  # ← SyntaxError on shebang
```

**Applies to:** Any CLI tool with a shebang + ESM. Common in modern TypeScript CLIs built with tsup, esbuild, or rollup.

---

## Error #6: Cannot delete branch used by a worktree during PR merge

**Symptom:** Running `gh pr merge <PR> --merge --delete-branch` fails with "cannot delete branch 'fix/...' used by worktree at '/path/to/worktree'". The PR merges on GitHub but the local branch deletion fails.

**Root cause:** Git cannot delete a branch that is currently checked out in any worktree. The agent finished work in the worktree, pushed, created the PR, but forgot to remove the worktree before merging with `--delete-branch`.

**Correct approach — always do this:**
```bash
# 1. Remove the worktree FIRST (after pushing all changes):
git worktree remove --force /path/to/worktree

# 2. THEN merge the PR with branch cleanup:
gh pr merge <PR> --merge --delete-branch
```

**Alternative if PR is already merged:**
```bash
# Clean up worktree and branch after the fact:
git worktree remove --force /path/to/worktree && git branch -d <branch-name>
```

**General worktree lifecycle:**
1. Create worktree -> do work -> push -> create PR
2. Remove worktree: `git worktree remove --force <path>`
3. Merge PR: `gh pr merge <PR> --merge --delete-branch`
4. Pull changes to main/develop

---

## Error #7: `execSync(...).trim is not a function` — Buffer vs string

**Symptom:** Tests fail with `TypeError: (0, execSync)(...).trim is not a function` at runtime. Code like `execSync('some command').trim()` throws because `.trim()` doesn't exist on Buffer.

**Root cause:** Node.js `execSync()` returns a **Buffer** by default, not a string. String methods (`.trim()`, `.split()`, `.toString()`, `.includes()`) don't exist on Buffer. The agent writes code assuming it returns a string.

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

**Symptom:** Multiple Write tool calls fail with "Error writing file" when paths use `~/Documents/...`. Agent may misdiagnose and retry (e.g., "these are new files so they don't need to be read first") — but the retry also fails because the path is still wrong.

**Root cause:** The Write, Read, and Edit tools require **truly absolute paths** starting with `/`. The `~` tilde is a shell shorthand that only Bash expands — file tools don't perform tilde expansion.

**Correct approach — always do this:**
```
# Use full absolute paths for ALL file tool operations:
Write(/Users/<user>/path/to/project/src/file.ts)
Read(/Users/<user>/path/to/project/src/file.ts)
Edit(/Users/<user>/path/to/project/src/file.ts)
```

**Never do this:**
```
# Tilde paths fail silently or with "Error writing file":
Write(~/path/to/project/src/file.ts)  # ← FAILS
Read(~/path/to/project/src/file.ts)   # ← FAILS
```

**Extra danger with parallel writes:** If you attempt multiple Write calls in parallel and they all use `~` paths, ALL of them fail — wasting an entire turn. Always double-check paths before batching file operations.

**Applies to:** All file tools (Write, Read, Edit, Glob). Always use full absolute paths starting with `/`.

---

## Error #9: `git push` rejected (non-fast-forward)

**Symptom:** `git push origin develop` fails with "non-fast-forward" — "Updates were rejected because the tip of your current branch is behind its remote counterpart."

**Root cause:** The remote branch has commits the local branch doesn't (from another session, a merged PR, or a parallel agent). The agent pushed without pulling first.

**Correct approach — always do this:**
```bash
# ALWAYS pull before pushing:
git pull --rebase origin <branch> && git push origin <branch>

# At the START of any session, sync the working branch:
git pull --rebase origin develop

# If working on a feature branch, also keep it rebased:
git pull --rebase origin develop
```

**Never do this:**
```bash
# Don't push without pulling first:
git push origin develop  # ← fails if remote is ahead
```

**Key context:** This is especially common when running multiple parallel sessions (multi-clauding) or after merging PRs on GitHub. Always assume the remote may have advanced since you last pulled.

---

## Error #10: Checking CI for multiple PRs in one jumbled command

**Symptom:** Agent chains `gh pr checks 1 && echo "---PR1 DONE---"; gh pr checks 2 && echo "---PR2 DONE---"; ...` in a single Bash call. Output is an unreadable mix of all PRs' results — can't tell which check belongs to which PR. The `echo` separators don't appear because `&&` skips them when `gh pr checks` exits non-zero (which it does when any check fails, including `review`).

**Root cause:** Two problems: (1) cramming multiple PR checks into one command produces jumbled output, and (2) `gh pr checks` exits non-zero if ANY check fails — including `review`, which just means "needs approval", not a CI failure.

**Correct approach — always do this:**
```bash
# Check one PR at a time with structured output:
gh pr checks <PR> --json name,state,bucket

# To check only build/CI status (ignore review requirements):
gh pr checks <PR> --json name,state,bucket --jq '.[] | select(.name != "review")'

# For multiple PRs, loop with clear labels:
for pr in 1 2 3; do echo "=== PR #$pr ==="; gh pr checks $pr --json name,state,bucket --jq '.[] | select(.bucket != "")' 2>&1; done

# Or just check the CI run directly:
gh run list --branch <branch> --limit 1 --json conclusion,status,name
```

**Never do this:**
```bash
# Don't chain multiple gh pr checks in one mega-command:
gh pr checks 1 && echo "done"; gh pr checks 2 && echo "done"  # ← jumbled, unreadable
```

**Key detail:** `review: fail` in `gh pr checks` means the PR needs a review approval — it's NOT a CI/build failure. Filter it out or ignore it when checking if CI passed.

---

## Error #11: `git worktree remove` fails on modified/untracked files, cascading failures

**Symptom:** `git worktree remove .worktrees/foo && git worktree remove .worktrees/bar && git branch -d ...` fails with "contains modified or untracked files, use --force to delete it". Because of `&&` chaining, the second removal and branch deletion never run. Agent then adds `--force` to the first but forgets the second — fails again.

**Root cause:** Worktrees almost always end up with modified/untracked files (build artifacts, node_modules, .next, dist, etc.). The default `git worktree remove` refuses to delete them. And `&&` chaining means one failure stops the whole chain.

**Correct approach — always do this:**
```bash
# ALWAYS use --force when removing worktrees:
git worktree remove --force .worktrees/foo

# For multiple worktrees, use ; (not &&) so each runs regardless:
git worktree remove --force .worktrees/foo; git worktree remove --force .worktrees/bar; git branch -d branch1 branch2

# Or loop:
for wt in .worktrees/foo .worktrees/bar; do git worktree remove --force "$wt" 2>/dev/null; done
```

**Never do this:**
```bash
# Don't use && (stops at first failure):
git worktree remove .worktrees/foo && git worktree remove .worktrees/bar  # ← second never runs

# Don't forget --force (worktrees always have untracked files):
git worktree remove .worktrees/foo  # ← fails on build artifacts

# Don't partially apply the fix:
git worktree remove --force .worktrees/foo && git worktree remove .worktrees/bar  # ← bar still fails
```

**Rule of thumb:** When applying a fix to a chained command, apply it to ALL instances, not just the first one that failed.

---

## Error #12: Push and forget — CI breaks silently

**Symptom:** Agent pushes code to the development branch, immediately moves on to the next task, and never checks CI status. Hours later, someone discovers CI has been red for multiple commits. Downstream work is built on a broken foundation.

**Root cause:** The agent treats `git push` as the end of the workflow. There's no accountability loop — no one checks whether the pushed code actually passes CI.

**Correct approach — always do this:**
```bash
# After every push, spawn a background monitor:
# 1. Poll CI until it completes
gh run list --branch develop --limit 1 --json conclusion,status,databaseId

# 2. If it fails, investigate:
gh run view <run-id> --log-failed 2>&1 | tail -100

# 3. Fix and re-push in the same branch
# 4. Poll again until green
```

In Claude Code, use `Task` with `run_in_background: true` to monitor CI without blocking the main terminal.

**Never do this:**
```bash
# Don't push and move on without checking:
git push origin develop
# ← agent starts next task, never checks CI
```

**Key detail:** Even single-line changes can break CI if they affect types, imports, or test fixtures. EVERY push gets a monitor.

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
"Please run `gh pr create` in your terminal"  ← you have Bash, run it yourself
"Go to GitHub and check the CI status"        ← use `gh run list`
"Open the file and change line 42"            ← use Edit tool
```

**Key detail:** This error compounds — once an agent starts suggesting manual steps, the user loses trust in the agent's autonomy. Exhaust every tool before escalating.

---

## Error #15: `git branch -d` fails on worktree branches (not fully merged)

**Symptom:** After removing a worktree, `git branch -d <branch>` fails with "error: the branch 'worktree-agent-xxx' is not fully merged" and "If you are sure you want to delete it, run 'git branch -D'." The agent retries with `-D` (uppercase), wasting a turn.

**Root cause:** `git branch -d` (lowercase) checks whether the branch is merged into its upstream tracking branch. Worktree branches are almost never "fully merged" in git's view — they may have been squash-merged via PR (different commit hashes), the remote branch may already be deleted, or the work was abandoned. The lowercase `-d` safety check is designed for long-lived branches, not ephemeral worktree branches.

**Correct approach — always do this:**
```bash
# ALWAYS use -D (uppercase, force) for worktree branch cleanup:
git worktree remove --force /path/to/worktree; git branch -D <branch-name>

# Full worktree cleanup sequence:
git worktree remove --force /path/to/worktree; git branch -D worktree-branch-name
```

**Never do this:**
```bash
# Don't use lowercase -d for worktree branches:
git worktree remove --force /path/to/worktree && git branch -d worktree-branch  # ← fails: "not fully merged"
```

**Key detail:** This combines with Error #11 — use `--force` on `git worktree remove`, `-D` (uppercase) on `git branch`, and `;` (not `&&`) to chain them. The complete worktree cleanup idiom is: `git worktree remove --force <path>; git branch -D <branch>`

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

**Symptom:** When creating multiple boilerplate files in parallel (LICENSE, CODE_OF_CONDUCT.md, SECURITY.md, CONTRIBUTING.md), one or more Write tool calls fail with "API Error: 400 — Output blocked by content filtering policy". The blocked calls waste the entire turn.

**Root cause:** The Anthropic API content filter sometimes blocks generation of certain standard open-source files (especially CODE_OF_CONDUCT.md and SECURITY.md) due to their policy/legal language triggering safety filters. When these are created in parallel, the entire batch is affected.

**Correct approach — always do this:**
```
# Create boilerplate files one at a time, not in parallel:
1. Create LICENSE
2. Create CONTRIBUTING.md
3. Create CODE_OF_CONDUCT.md
4. Create SECURITY.md

# If a content filter blocks a file:
# - Simplify the content (use minimal templates)
# - Reference an external URL instead of inline content
# - Ask the user to create that specific file manually
```

**Never do this:**
```
# Don't create all boilerplate files in one parallel batch:
Parallel Write: LICENSE, CODE_OF_CONDUCT.md, SECURITY.md, CONTRIBUTING.md
# ← one blocked file wastes the whole turn
```

**Key detail:** This is a platform limitation, not a code error. The workaround is sequential creation with graceful fallback. If a file gets blocked, move on and note it for the user rather than retrying the same content.

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

**Symptom:** `rm /path/to/file1.png /path/to/file2.png ...` fails with "No such file or directory" for every file in the list. The agent is trying to delete files that were already removed in a previous session or that no longer exist at those paths.

**Root cause:** The agent operates on a memorized or cached list of files instead of checking what actually exists in the directory right now. Between sessions, files may have been moved, renamed, or already deleted. The agent "remembers" filenames from a prior context and acts on stale information.

**Correct approach — always do this:**
```bash
# Always list the directory contents fresh before bulk operations:
ls /path/to/directory/

# Use -f to ignore nonexistent files (when some may already be deleted):
rm -f /path/to/directory/file1.png /path/to/directory/file2.png

# Or use a glob to delete what actually exists:
rm -f /path/to/directory/*.png

# For selective deletion, verify each file first:
for f in /path/to/directory/*.png; do [ -f "$f" ] && rm "$f"; done
```

**Never do this:**
```bash
# Don't operate on files from memory without re-reading the directory:
rm /path/to/file1.png /path/to/file2.png  # ← files may not exist anymore

# Don't batch many rm paths from a stale list:
rm file-from-tuesday.png file-from-wednesday.png  # ← already deleted last session
```

**Key detail:** This is especially common in multi-session workflows where the agent processes and deletes files, then in a later session tries to delete the same files again. Always re-read directory contents at the start of any bulk file operation.

---

## Error #23: `gh` command fails — agent fabricates repo/resource names

**Symptom:** `gh repo view owner/XILLVER --json name,owner` fails with "GraphQL: Could not resolve to a Repository with the name 'owner/XILLVER'." The agent used a repo name that doesn't exist — it was guessed, misspelled, or hallucinated.

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

**Symptom:** `rm ../other-project/scripts/agent.sh ../other-project/docs/agents/report.md` fails with "No such file or directory". The agent uses `../` relative paths to reference files in sibling projects, but the shell's working directory is not what the agent expects.

**Root cause:** The Bash tool's working directory resets to the primary working directory between calls (see Error #2). Even within a single call, `../` relative paths are fragile — they depend on the exact cwd, which may differ from what the agent assumes. This is an extension of the worktree cwd problem applied to cross-project file operations.

**Correct approach — always do this:**
```bash
# Always use absolute paths for cross-project operations:
rm -f /Users/username/projects/other-project/scripts/agent.sh
rm -f /Users/username/projects/other-project/docs/agents/report.md

# For multiple files across projects, use absolute paths with ; (not &&):
rm -f /absolute/path/project-a/file1; rm -f /absolute/path/project-b/file2
```

**Never do this:**
```bash
# Don't use relative paths for cross-project operations:
rm ../other-project/scripts/agent.sh    # ← cwd may not be where you think
rm ../../shared/config.json             # ← breaks when cwd resets

# Don't assume cwd is in a specific project:
cd ../other-project && rm scripts/agent.sh  # ← cd may fail silently, rm runs in wrong dir
```

**Applies to:** Any Bash command that references files outside the current project. Always use full absolute paths starting with `/`. This is Error #2's principle (absolute paths in worktrees) generalized to all cross-directory operations.

---

## Error #25: `git push` or `git pull --rebase` fails — no upstream tracking for branch

**Symptom (push variant):** `git push` fails with "fatal: The current branch main has no upstream branch. To push the current branch and set the remote as upstream, use `git push --set-upstream origin main`."

**Symptom (pull variant):** `git pull --rebase && git push` fails with "There is no tracking information for the current branch. Please specify which branch you want to rebase against."

**Root cause:** The agent runs `git push` or `git pull --rebase` on a branch that has never been pushed to a remote, or where upstream tracking was never configured. Without tracking info, git doesn't know which remote branch to push to or pull from. This commonly happens on freshly created branches, new repos after `git init`, or after cloning when switching to a new local branch.

**Correct approach — always do this:**
```bash
# On first push of any branch, always set upstream tracking:
git push -u origin <branch>

# After -u is set, plain git push / git pull --rebase works.

# If unsure whether tracking is set, specify remote and branch explicitly:
git pull --rebase origin <branch> && git push origin <branch>

# Or check tracking status first:
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "No upstream — use git push -u origin <branch>"
```

**Never do this:**
```bash
# Don't assume all branches have upstream tracking:
git push                       # ← fails on branches without tracking
git pull --rebase && git push  # ← also fails

# Don't retry the same command after this error:
git push  # ← same error, still no tracking info
```

**Key detail:** Rule #6 says "always `git pull --rebase` before pushing." This error is what happens when you follow that rule on a branch with no upstream. The fix is to always use `-u` on the first push, which sets tracking so subsequent pull/push cycles work. If you're unsure, specify `origin <branch>` explicitly — it always works regardless of tracking state.

---

## Error #26: Complex shell regex fails in zsh — special characters parsed differently

**Symptom:** A complex `grep -oP` or `grep -P` pipeline fails with `(eval):1: parse error: condition expected: \!` or similar zsh parse errors. The regex contains characters like `!`, `{`, `}`, or `(` that zsh interprets before they reach grep.

**Root cause:** macOS defaults to zsh, where `!` triggers history expansion and other special characters have different quoting rules than bash. When the agent builds complex regex pipelines with `grep -oP`, characters like `\!` inside the pattern are intercepted by zsh's parser before grep ever sees them. This is compounded by the agent building overly complex shell one-liners instead of using available tools.

**Correct approach — always do this:**
```bash
# Option 1 (preferred): Use the Grep tool instead of shell grep:
# The built-in Grep tool handles regex safely without shell interpretation.

# Option 2: If shell grep is required, use bash explicitly:
bash -c 'grep -oP "\[(?![!])([^\]]*\]\(\K[^\)]+" "$1"' _ "$file"

# Option 3: Simplify the regex — break complex patterns into steps:
grep -o '\[.*\](.*)'  # simpler grep, then process in a second step

# Option 4: Use dedicated tools instead of regex pipelines:
# For markdown links: use markdown-link-check, markdownlint, or remark
# For JSON: use jq
# For structured data: use awk with simpler patterns
```

**Never do this:**
```bash
# Don't build complex Perl regex pipelines in zsh:
grep -oP '\[(?![!])([^\]]*\]\(\K[^\)]+' "$file"  # ← zsh parse error on \!

# Don't build Rube Goldberg shell one-liners:
while IFS= read -r file; do dir=$(dirname "$file"); grep -oP '...' "$file" | while IFS= read -r link; do ...
# ← fragile, unreadable, breaks on zsh special chars
```

**Key detail:** The agent's impulse to build complex shell pipelines is the deeper problem. Before writing any multi-pipe shell command with regex, ask: (1) Can I use the built-in Grep/Glob tools? (2) Is there a dedicated CLI tool for this? (3) Can I break this into simpler steps? Complex one-liners that work in bash often fail in zsh — and macOS is zsh by default.

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

**Symptom:** `uv sync --all-extras` exits code 1 during package installation. Output shows `Using CPython 3.14.3 interpreter at: /opt/homebrew/opt/python@3.14/bin/python3.14` — uv picked the newest system Python, which is too new for some packages (missing wheels, C extension build failures). Common failures: `cryptography`, `pymupdf`, `pandas`, `numpy`, or any package with compiled extensions.

**Root cause:** `uv` auto-selects the newest Python interpreter available on the system. When the user has installed Python 3.14 via Homebrew (or any bleeding-edge version), `uv` picks it by default. Many packages don't ship pre-built wheels for the newest Python minor version, causing build failures or incompatibilities.

**Correct approach — always do this:**
```bash
# Check if the project pins a Python version:
cat .python-version 2>/dev/null
grep -A2 'requires-python' pyproject.toml 2>/dev/null

# Specify the Python version explicitly if needed:
uv sync --python 3.13 --all-extras

# Or pin the Python version in the project:
echo "3.13" > .python-version
uv sync --all-extras  # ← now uses 3.13

# If a venv already exists with the wrong Python, recreate:
rm -rf .venv && uv sync --python 3.13 --all-extras
```

**Never do this:**
```bash
# Don't assume the system default Python is compatible:
uv sync --all-extras  # ← picks Python 3.14, packages may not have wheels

# Don't ignore the "Using CPython X.Y.Z" line in uv output:
# If it shows a version newer than 3.13, many packages will fail to install
```

**Key detail:** This is especially common on macOS with Homebrew, where `brew install python` installs the latest stable release and `brew upgrade` can bump it to a new minor version. Always check `.python-version` or `pyproject.toml` `requires-python` before running `uv sync`. If the project doesn't pin a version, default to the latest widely-supported release (currently 3.13), not whatever the system provides.

---

## Error #30: `gh pr create` before pushing branch to remote

**Symptom:** `gh pr create --base master --title "feat: ..." --body "## Summary..."` fails with "aborted: you must first push the current branch to a remote, or use the --head flag".

**Root cause:** The agent ran `gh pr create` without first pushing the branch to the remote. A PR requires the branch to exist on the remote — GitHub can't create a PR from a branch that only exists locally. The agent skipped the push step, going directly from local commits to PR creation.

**Correct approach — always do this:**
```bash
# ALWAYS push with -u before creating a PR:
git push -u origin <branch>

# THEN create the PR:
gh pr create --base main --title "feat: ..." --body "..."

# Full PR workflow:
# 1. Commit changes locally
# 2. Push to remote: git push -u origin <branch>
# 3. Create PR: gh pr create --base main --title "..." --body "..."
```

**Never do this:**
```bash
# Don't create a PR before pushing:
git commit -m "feat: something"
gh pr create --base main --title "feat: something" --body "..."  # ← branch not on remote!
```

**Key detail:** This combines with Error #25 — `git push -u` both sets upstream tracking AND pushes the branch to the remote. Using `-u` on the first push handles both problems at once. The PR creation workflow should always be: commit → push with `-u` → create PR.

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

**Symptom:** `gh pr merge <N> --merge` fails with any of: (1) "the head branch is not up to date with the base branch", (2) "the base branch policy prohibits the merge", or (3) `--auto` fails with "Pull request Auto merge is not allowed for this repository (enablePullRequestAutoMerge)." The agent blindly retries with different flags instead of diagnosing the actual issue.

**Root cause:** The agent defaults to `gh pr merge --merge` without checking the repository's branch protection settings. Repos often require squash or rebase merges only, require branches to be up-to-date before merge, or don't have auto-merge enabled. The agent tries one flag, it fails, then guesses another flag — wasting multiple turns.

**Correct approach — always do this:**
```bash
# Before merging, check allowed merge methods:
gh api repos/{owner}/{repo} --jq '{
  allow_merge: .allow_merge_commit,
  allow_squash: .allow_squash_merge,
  allow_rebase: .allow_rebase_merge,
  auto_merge: .allow_auto_merge
}'

# Use the correct merge method based on repo settings:
gh pr merge <N> --squash    # if only squash is allowed
gh pr merge <N> --rebase    # if only rebase is allowed

# If "head branch not up to date" — update the branch first:
gh pr update-branch <N>     # ← uses GitHub API to update
# Or locally:
git fetch origin && git rebase origin/main && git push

# If you need auto-merge, verify it's enabled first:
gh api repos/{owner}/{repo} --jq '.allow_auto_merge'
```

**Never do this:**
```bash
# Don't default to --merge without checking:
gh pr merge <N> --merge            # ← may violate branch policy

# Don't blindly escalate through flags:
gh pr merge <N> --merge            # ← fails: policy prohibits
gh pr merge <N> --merge --auto     # ← fails: auto-merge not enabled
# Wasted 2 turns — should have checked settings first

# Don't retry merge without fixing the underlying issue:
gh pr merge <N> --merge            # ← fails: branch not up-to-date
gh pr merge <N> --merge            # ← same failure, nothing changed
```

**Key detail:** These three failure modes all stem from the same mistake — attempting merge without understanding the repo's configuration. One `gh api` call reveals allowed methods, auto-merge status, and branch protection rules. Always check before merging.

---

## Error #33: `git pull --rebase` fails — unstaged changes in working tree

**Symptom:** `git pull --rebase && git push origin <branch>` fails with "cannot pull with rebase: You have unstaged changes. Please commit or stash them." The agent chains pull+push without checking for a clean working tree first.

**Root cause:** The agent has uncommitted changes from recent edits (e.g., code fixes, file modifications) and immediately tries to pull --rebase. Git refuses to rebase over a dirty working tree because the rebase could conflict with local changes. The agent follows rule #6 ("always pull --rebase before pushing") but skips the prerequisite of having a clean tree.

**Correct approach — always do this:**
```bash
# Always check for dirty state before pull --rebase:
git status --short

# If there are uncommitted changes, commit them first:
git add -A && git commit -m "fix: description" && git pull --rebase && git push

# Or stash if the changes aren't ready to commit:
git stash && git pull --rebase && git push && git stash pop

# Best pattern: commit all work BEFORE the pull+push sequence
```

**Never do this:**
```bash
# Don't chain pull+push without checking working tree state:
git pull --rebase && git push origin develop   # ← fails if dirty

# Don't assume the working tree is clean after editing files:
# (you just ran Edit tool 3 times — of course there are changes)
```

**Key detail:** This error often follows a pattern: the agent edits files, runs checks, then tries to push without committing first. The fix is simple — always commit before the pull+push sequence. This complements Rule #6 (always pull --rebase before push) with the prerequisite that the tree must be clean first.

---

## Error #34: WebFetch returns 403 — agent retries same blocked domain

**Symptom:** WebFetch to a URL returns "Request failed with status code 403." The agent then tries alternate URL paths on the same domain — all return 403. Meanwhile, parallel fetch attempts trigger "Sibling tool call errored" (Error #1), compounding the failure.

**Root cause:** Many sites (help centers, documentation portals, APIs) block automated/bot requests at the domain level. A 403 from one URL on a domain means ALL URLs on that domain will likely return 403. Retrying with different paths wastes turns and, if done in parallel, triggers sibling tool call failures.

**Correct approach — always do this:**
```bash
# On first 403, switch strategies immediately:
# Option 1: Use WebSearch to find the information from other sources
# Option 2: Ask the user to copy-paste the relevant content
# Option 3: Try a cached/archive version if appropriate

# If you must try multiple URLs, do it sequentially (not parallel):
# And stop after the first 403 — the domain is blocking you
```

**Never do this:**
```
# Don't retry multiple URLs on the same 403 domain:
Fetch(https://help.example.com/articles/123-topic-a)     # ← 403
Fetch(https://help.example.com/articles/456-topic-b)     # ← also 403
Fetch(https://help.example.com/articles/789-topic-c)     # ← also 403

# Especially don't do it in parallel (triggers Error #1):
Parallel Fetch 1: help.example.com/path-a  # ← 403 → kills siblings
Parallel Fetch 2: help.example.com/path-b  # ← "Sibling tool call errored"
Parallel Fetch 3: help.example.com/path-c  # ← "Sibling tool call errored"
```

**Key detail:** A 403 is a domain-level signal, not a page-level one. The server is rejecting automated access entirely. No amount of URL variation will fix it. Switch to WebSearch or ask the user for the content.

---

## Error #35: `gh pr checks` exit code 0 with pending checks — misread as "all passed"

**Symptom:** Agent runs `gh pr checks <N> 2>&1`, sees exit code 0, and concludes all CI checks passed. But the output shows every check with status "pending" — none have actually run yet. The agent then proceeds to merge or reports "CI is green" when CI hasn't started.

**Root cause:** `gh pr checks` returns exit code 0 when there are no failures — including when all checks are still pending. Exit code 0 means "no failures detected," NOT "all checks passed." The agent checks only the exit code and ignores the actual status values in the output.

**Correct approach — always do this:**
```bash
# Use --watch to wait for checks to complete:
gh pr checks <N> --watch

# Or use --json to inspect actual check states:
gh pr checks <N> --json name,state,conclusion --jq '
  if all(.state == "COMPLETED" and .conclusion == "SUCCESS") then "all_passed"
  elif any(.state != "COMPLETED") then "still_pending"
  else "has_failures" end
'

# Or parse text output to detect pending status:
gh pr checks <N> 2>&1 | grep -c "pending"
# If count > 0, checks are not done yet

# Best: Use --watch in a background agent to monitor until completion
```

**Never do this:**
```bash
# Don't rely on exit code alone:
gh pr checks <N> 2>&1
# Exit code 0 + "pending" everywhere = NOT passed

# Don't immediately try to merge after seeing exit code 0:
gh pr checks <N> 2>&1          # ← exit 0, all pending
gh pr merge <N> --merge        # ← premature, checks haven't run

# Don't report "CI is green" based on exit code:
# "Exit code 0" ≠ "all checks passed" when checks are pending
```

**Key detail:** The three states of `gh pr checks` exit codes: 0 = no failures (could be all-passed OR all-pending), 1 = at least one failure. You MUST inspect the actual output or use `--json` to distinguish between "passed" and "pending." This is especially important in repos where checks take several minutes to start after a push.

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

**Symptom:** A scheduled agent script works perfectly when run from a terminal (`./scripts/agents/my-agent.sh`) but silently fails, crashes, or exits immediately when launched by `launchctl start`. The log file is empty or contains cryptic errors like "Too many open files", "claude: command not found", or an OAuth login URL that nobody sees.

**Root cause:** Three independent issues compound under launchd's minimal execution environment (plus a fourth — see [Error #38](#error-38-claude-cli-crashes-with-unexpected-when-plist-runs-script-directly) for the ProgramArguments wrapper requirement):

1. **File descriptor limit (hard cap 256):** launchd enforces a hard limit of 256 open files per process. Claude CLI needs 100K+ file descriptors for its Node.js runtime and network connections. `ulimit -n` inside the script has no effect because the hard limit is 256 — you can't raise soft above hard.

2. **Missing environment variables:** launchd doesn't source `~/.zshrc`, `~/.bash_profile`, or any shell profile. PATH is minimal (`/usr/bin:/bin:/usr/sbin:/sbin`), HOME may be unset, and TERM is absent. Claude CLI and its dependencies aren't on PATH.

3. **No interactive authentication:** Claude CLI's default OAuth flow opens a browser for login. Under launchd, there's no TTY, no browser, and no user to click "Authorize." The CLI either hangs waiting for auth or exits with an error. `claude setup-token` creates a persistent API token that works in non-interactive environments.

**Correct approach — always do this:**

```xml
<!-- In the .plist file — resource limits MUST be in the plist, not the script -->
<key>HardResourceLimits</key>
<dict>
  <key>NumberOfFiles</key>
  <integer>122880</integer>
</dict>
<key>SoftResourceLimits</key>
<dict>
  <key>NumberOfFiles</key>
  <integer>122880</integer>
</dict>
<!-- Environment variables — plist is the only reliable place -->
<key>EnvironmentVariables</key>
<dict>
  <key>HOME</key>
  <string>/Users/YOUR_USERNAME</string>
  <key>TERM</key>
  <string>xterm-256color</string>
  <key>PATH</key>
  <string>/usr/local/bin:/opt/homebrew/bin:/Users/YOUR_USERNAME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
</dict>
```

```bash
# In the agent script — defense-in-depth (supplements the plist)

# 1. Ensure critical env vars exist (fallback if plist vars missing)
export HOME="${HOME:-$(eval echo ~"$(whoami)")}"
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"

# 2. Verify file descriptor limit (plist should have set this)
ulimit -n 122880 2>/dev/null
FD_LIMIT=$(ulimit -n)
if [ "$FD_LIMIT" -lt 10000 ]; then
  echo "[$(date)] FATAL: File descriptor limit too low ($FD_LIMIT)."
  echo "  Fix: Add HardResourceLimits/SoftResourceLimits to your .plist"
  exit 1
fi

# 3. Verify non-interactive auth works
if ! "$CLAUDE_BIN" -p "echo ok" --output-format text >/dev/null 2>&1; then
  echo "[$(date)] FATAL: Claude CLI auth failed in non-interactive mode."
  echo "  Fix: Run 'claude setup-token' from an interactive terminal."
  exit 1
fi
```

```bash
# One-time setup — run interactively before scheduling:
claude setup-token
# Then test the plist:
launchctl start com.project.agent.my-agent
# Check logs — don't trust terminal execution as proof it works
```

**Never do this:**
```bash
# Don't rely on ulimit alone — launchd hard limit is 256, can't raise above it:
ulimit -n 122880  # ← fails silently, stays at 256

# Don't source shell profiles — fragile and may have interactive-only code:
source ~/.zshrc   # ← may fail or produce side effects under launchd

# Don't rely on interactive OAuth — no browser, no TTY under launchd:
# Claude will try to open a browser URL that nobody will see

# Don't test by running the script from a terminal:
./scripts/agents/my-agent.sh  # ← works! (terminal has high fd limit + full env)
# This proves nothing about launchd execution
```

**Key detail:** All three fixes must be applied together — any single missing fix causes silent failure. The plist resource limits are the only way to raise file descriptors under launchd (`ulimit` can't exceed the hard limit). The plist environment variables are the only reliable way to set PATH (scripts can supplement but not replace). And `claude setup-token` is the only way to authenticate without a browser. Always test with `launchctl start`, never from a terminal — terminal execution masks all three problems.

---

## Error #38: Claude CLI crashes with "Unexpected" when plist runs script directly

**Symptom:** Agent plist with correct resource limits, env vars, and auth still fails. Claude CLI returns `error: An unknown error occurred (Unexpected)` even for `claude --version`. The error is instant (< 1 second). Exit code is 0 despite the error.

**Root cause:** When launchd directly executes a script located inside a project directory that has a `.claude/` folder, the Claude CLI misidentifies the project context from the initial process arguments. This causes an internal crash before any real work begins. The same script works fine when located outside the project tree (e.g., `/tmp`), or when the plist uses `/bin/bash -c "exec /bin/bash <script>"` instead of running the script directly.

**Diagnostic clue:** The failure is **location-dependent**, not content-dependent. The same script at `/tmp/my-agent.sh` works, but at `/project/scripts/agents/my-agent.sh` fails. Removing `.claude/settings.json` doesn't fix it. The error is a CLI bug in how it resolves project context under launchd's process model.

**Correct approach from the start:**

Use `/bin/bash -c "exec /bin/bash <script>"` in ProgramArguments instead of the script path directly:

```xml
<!-- WRONG — direct script execution, causes crash: -->
<key>ProgramArguments</key>
<array>
  <string>/path/to/project/scripts/agents/my-agent.sh</string>
</array>

<!-- ALSO WRONG — /bin/bash without -c exec, same crash: -->
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>
  <string>/path/to/project/scripts/agents/my-agent.sh</string>
</array>

<!-- CORRECT — bash -c with exec wrapper: -->
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>
  <string>-c</string>
  <string>exec /bin/bash /path/to/project/scripts/agents/my-agent.sh</string>
</array>
```

The `exec` replaces the initial shell process, so the agent script still runs as PID 1 of the launchd job (clean process tree, correct signal handling). The `-c` wrapper changes the initial process context so Claude CLI doesn't misidentify the project root from the launchd process arguments.

**Never do this:**
```xml
<!-- Don't run scripts directly — even with /bin/bash prefix: -->
<array>
  <string>/bin/bash</string>
  <string>/project/scripts/agents/my-agent.sh</string>
</array>
<!-- Claude CLI will crash with "Unexpected" if the script is inside a .claude/ project -->
```

**Key detail:** This error has zero debug output — `--debug-file` is never written because the CLI crashes before reaching the debug initialization. The exit code is 0 despite the error, which means auth preflight checks (`if ! claude -p "echo ok" >/dev/null 2>&1`) silently pass, masking the problem. Combined with [Error #37](#error-37-scheduled-agent-silently-fails-under-macos-launchd), a working launchd agent plist requires four fixes: resource limits, env vars, setup-token auth, and the `-c exec` ProgramArguments wrapper.

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

**Symptom:** `git push origin main --tags` exits non-zero with `! [rejected] v1.0 -> v1.0 (already exists)`. The new commits and new tags pushed fine, but the agent sees exit code 1 and treats the entire push as failed.

**Root cause:** `--tags` pushes every local tag to the remote, not just tags created in this session. If any tag was previously pushed, recreated locally, or already exists on the remote, git rejects it — and the non-zero exit code makes the agent think nothing was pushed. The agent then retries or panics, wasting turns.

**Correct approach — always do this:**
```bash
# Push commits and a specific tag by name:
git push origin main && git push origin v1.3.0

# Or use --follow-tags (only pushes annotated tags reachable from pushed commits):
git push origin main --follow-tags
```

**Never do this:**
```bash
# Don't push all tags blindly:
git push origin main --tags
# ← pushes EVERY local tag, fails if any already exists on remote

# Don't use --force to fix it:
git push origin main --tags --force
# ← force-pushes all tags, potentially overwriting remote tag history
```

**Key detail:** `--tags` and `--follow-tags` are very different. `--tags` pushes all refs under `refs/tags/`. `--follow-tags` only pushes annotated tags that point to commits being pushed. Use `--follow-tags` for release workflows, or push specific tags by name.

---

## Error #45: Agent fabricates filesystem paths — "No such file or directory"

**Symptom:** `git -C /Users/juan/Documents/GenAI_Projects/cc-rpi pull --rebase` fails with `fatal: cannot change to '/Users/juan/Documents/GenAI_Projects/cc-rpi': No such file or directory`. The actual path was `/Users/juan/Documents/code/cc-rpi`.

**Root cause:** The agent guesses or hallucinates a plausible filesystem path instead of using the known working directory or discovering the path. Common fabrications include inventing parent directory names (`Projects`, `GenAI_Projects`, `repos`, `workspace`), getting the nesting level wrong, or mixing up similar project names. This is the filesystem equivalent of Error #23 (fabricating GitHub identifiers).

**Correct approach — always do this:**
```bash
# Use the project's working directory (provided by the environment):
git -C /Users/juan/Documents/code/cc-rpi pull --rebase

# If you need to find another project, discover it:
ls /Users/juan/Documents/code/
# Then use the actual name from the listing

# Or ask the user for the path if it's not discoverable
```

**Never do this:**
```bash
# Don't guess directory names:
git -C /Users/juan/Documents/GenAI_Projects/cc-rpi pull --rebase
# ← "GenAI_Projects" is fabricated — the real dir is "code"

# Don't assume paths from previous sessions are still valid:
cd /Users/juan/projects/old-name/src
# ← directories may have been renamed, moved, or deleted
```

**Key detail:** The working directory is always available from the environment. For cross-project operations, use `ls` or Glob to discover paths — never guess directory names. Even plausible-sounding names like `Projects` or `repos` are often wrong.
