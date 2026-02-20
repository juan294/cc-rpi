# Known Agent Errors — Universal Catalog

Documented from real recurring issues across projects. Each entry includes the symptom, root cause, and the correct approach to use from the start.

**How to use this file:** Read this before starting any work. These are patterns Claude Code agents hit repeatedly — the solutions are known and should be applied from the first attempt, not rediscovered.

---

## Error #1: Sibling tool call errored (parallel verification commands)

**Symptom:** Running `typecheck` and `lint` (or any verification commands) as parallel Bash tool calls. When one exits non-zero, the others are killed with "Sibling tool call errored" — their output is lost completely.

**Root cause:** Claude Code kills all sibling Bash calls when any one fails.

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
```

**Applies to:** typecheck, lint, test, build — any commands that can fail. Also applies to sub-agents.

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
