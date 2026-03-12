# Agent Operational Rules — Quick Reference

These rules must be internalized before starting any work. They prevent the most common recurring errors across all projects.

## Shell & Tool Rules

1. **Never run sibling tool calls that can fail in parallel** — chain Bash commands with `&&` or `;` instead. Applies to ALL tool types: Bash, TaskOutput, Read. If one sibling fails, all parallel calls are killed.

2. **Worktrees: always use absolute paths in every Bash command** — shell cwd resets to the main repo between calls. Prefix every command with `cd /absolute/path/to/worktree &&`.

3. **Never use `~` in file tool paths** — Write/Read/Edit don't expand tilde. Always use full absolute paths starting with `/`.

4. **Always pass `{ encoding: 'utf-8' }` to `execSync`/`spawnSync`** — they return Buffers by default. `.trim()` and other string methods fail on Buffer.

## Git Rules

5. **Always run typecheck/lint BEFORE committing** — pre-commit hooks run the same checks. Fix errors first, then commit. Don't discover failures at commit time.

6. **Always `git pull --rebase` before pushing** — remote may have advanced from other sessions, merged PRs, or parallel agents.

7. **Remove worktrees BEFORE merging PRs with `--delete-branch`** — Git can't delete a branch checked out in a worktree.

8. **Always `git worktree remove --force`** — worktrees have build artifacts/node_modules. Use `;` not `&&` for multiple removals. Apply fixes to ALL instances in a chain, not just the first.

## GitHub CLI Rules

9. **Don't guess `gh` CLI `--json` field names** — fields differ per subcommand. Run `gh <cmd> --json 2>&1 | head -5` first if unsure. `conclusion` exists on `gh run` but NOT `gh pr checks`.

10. **Check CI per-PR with `--json`, not chained human-readable output** — jumbled output is unreadable. `review: fail` means "needs approval", NOT a CI failure — always filter it out.

## Node.js / TypeScript Rules

11. **Don't run ESM CLI tools with `node <file>`** — shebang + ESM = SyntaxError. Use `chmod +x && ./<file>` or `npx .` instead.

## CI & Workflow Rules

12. **Never push and forget** — after every push to the development branch, spawn a background agent to monitor CI. If CI fails, investigate, fix, and re-push. The push isn't done until CI is green.

13. **Always write tests before implementation (TDD)** — Red-Green-Refactor, every time. Bug fixes need a regression test first. No "tests later." Tests written after implementation tend to be tautological.

14. **Exhaust all tools before suggesting manual steps** — before telling the user "go to the dashboard and...", check if you can use CLI tools, shell commands, MCP servers, or file tools to do it yourself. Only escalate when genuinely impossible.

15. **Always `git branch -D` (uppercase) for worktree branches** — worktree branches are almost never "fully merged" in git's view (squash merges, deleted remotes, abandoned work). Lowercase `-d` fails with "not fully merged." Full cleanup idiom: `git worktree remove --force <path>; git branch -D <branch>`

## Environment & Dependencies Rules

16. **Install dependencies before running commands in fresh environments** — worktrees, clones, and CI don't have node_modules. Always run `pnpm install` (or equivalent) first.

17. **Don't escape operators inside single-quoted jq filters** — `!=` is literal inside `'...'`. Writing `\!=` passes a backslash to jq, causing "INVALID_CHARACTER" syntax errors.

18. **Handle empty repos gracefully** — `git log` and `git diff HEAD` fail on repos with no commits. Check `git rev-parse HEAD` first or create an initial commit during bootstrap.

19. **Create boilerplate files sequentially, not in parallel** — API content filters can block certain files (CODE_OF_CONDUCT, SECURITY.md). Sequential creation with fallback prevents wasted turns.

20. **`gh release create` uses `--notes`, not `--body`** — different `gh` subcommands use different flags for similar concepts. `--body` is for `pr create` and `issue create`. When in doubt, check `--help`.

21. **Use `brew install` instead of `pip3 install` on macOS** — Homebrew Python 3.12+ blocks system-wide pip installs (PEP 668). Use `brew` for CLI tools, `pipx` for Python apps.

22. **Re-read directory contents before bulk file operations** — don't operate on memorized/stale file lists from previous sessions. Always `ls` first or use `rm -f` (ignores nonexistent). Files may already be deleted.

23. **Don't fabricate GitHub identifiers — discover them** — repo names, branch names, and issue numbers are case-sensitive and must be exact. Use `gh repo list`, `git branch -r`, or `gh issue list --search` instead of guessing.

24. **Never use `../` relative paths for cross-project Bash commands** — cwd resets between Bash calls (Error #2). Use full absolute paths starting with `/` for any file operation outside the current project.

25. **Use `git push -u` on first push — both `git push` and `git pull --rebase` need upstream tracking** — branches that have never been pushed have no tracking info. Always `git push -u origin <branch>` first, or specify remote explicitly: `git pull --rebase origin <branch>`.

26. **Don't build complex regex pipelines in shell — use dedicated tools** — macOS defaults to zsh where `!`, `{`, `}` trigger special parsing. `grep -oP` with complex Perl regex breaks with zsh parse errors. Use the built-in Grep tool, dedicated linters, or `bash -c '...'` for complex regex.

27. **Only pass correct file types to linters — don't fight intentional patterns** — `markdownlint` on `.sh` files = hundreds of false errors. Before "fixing" linter warnings, check if the pattern is intentional (e.g., continuous step numbering). Add linter exceptions for intentional style, don't change the content.

28. **Use `--fix` for auto-fixable linter issues — don't manually edit** — `[*]` in ruff output means auto-fixable. Run `ruff check --fix` or `eslint --fix` first, then check for remaining manual issues. Don't waste turns manually reordering imports that `--fix` handles in one command.

29. **Specify Python version for `uv sync` — system default may be too new** — `uv` auto-selects the newest Python on the system. If Homebrew has Python 3.14+, packages may lack wheels. Check `.python-version` or use `uv sync --python 3.13`.

30. **Always `git push -u` before `gh pr create`** — a PR requires the branch to exist on the remote. Push with `-u` first, then create the PR. Combines with Rule #25 — `-u` handles both upstream tracking and remote existence.

31. **Don't guess CLI flags on unfamiliar tools — run `--help` first** — `--json` works on `gh` but not `vercel`. `--output` works on `curl` but is deprecated on `vercel`. Each CLI has its own flag vocabulary. Run `<cmd> --help` before using flags you haven't verified.

32. **Check repo merge settings before `gh pr merge`** — don't default to `--merge`. Repos may only allow squash/rebase, require branches to be up-to-date, or have auto-merge disabled. Run `gh api repos/{owner}/{repo}` to check allowed methods first.

33. **Commit or stash before `git pull --rebase`** — `git pull --rebase` fails if there are unstaged changes. Always commit your work before the pull+push sequence. Don't chain `git pull --rebase && git push` right after editing files.

34. **Don't retry WebFetch on a 403 domain — switch strategies** — a 403 means the domain blocks automated requests. Alternate URL paths on the same domain will also 403. Use WebSearch instead, or ask the user for the content.

35. **`gh pr checks` exit code 0 doesn't mean "passed" — it means "no failures yet"** — all-pending checks also return exit code 0. Always inspect the actual output or use `--json` to distinguish passed from pending. Use `--watch` to wait for completion.

36. **Don't build mega inline shell one-liners — write a temp script** — if your command needs `while`/`for`/`awk` with complex logic, write it to `/tmp/script.sh` and execute that. zsh can't parse long inline commands with special characters, Unicode, or nested quotes. Prefer built-in tools (Grep, Read, Glob) over shell pipelines.

37. **macOS launchd agents need four fixes** — plist `HardResourceLimits`/`SoftResourceLimits` (NumberOfFiles: 122880), plist `EnvironmentVariables` (HOME, TERM, PATH), `claude setup-token` for non-interactive auth, and ProgramArguments must use `/bin/bash -c "exec /bin/bash <script>"` (not direct script path). Test with `launchctl start`, not from a terminal — terminal execution masks all four problems.

38. **launchd plist must NOT run project scripts directly** — `<string>/project/scripts/agent.sh</string>` in ProgramArguments causes Claude CLI to crash with "Unexpected" when the script is inside a directory with `.claude/`. Use `/bin/bash -c "exec /bin/bash <script>"` wrapper instead. Exit code is 0 despite the error, so preflight checks silently pass.

## Native Command Rules

39. **Always run `/simplify` after reviewer approval during `/implement`** — it catches code reuse, quality, and efficiency issues that the plan-compliance reviewer doesn't check.

40. **Mark independent plan phases as `[batch-eligible]`** — during `/plan`, identify phases with no file overlap and no dependency on another phase's output. `/batch` can execute these in parallel (one worktree per phase, each opens a PR).

41. **Use `/batch` for bulk changes outside the RPI cycle** — migrations, multi-issue sprints, and repetitive refactors across many files are `/batch` territory. Don't manually iterate through 20 files when `/batch` can parallelize them.

42. **After `/pre-launch` audit, run `/simplify` first** — it fixes the bulk of architect and performance-eng findings (dead code, duplicates, inefficiencies) in one automated pass. Then address security, infrastructure, and accessibility findings manually.

## Environment & Language Rules

43. **`gh` fails with "Projects (classic) deprecated" GraphQL error** — upgrade `gh` CLI (`brew upgrade gh`). Older versions query removed `projectCards` fields. No flag or auth change fixes it.

44. **Always use `uv run python` (or project's venv runner) — never bare `python3`** — system Python doesn't have project dependencies. Use `uv run python`, `poetry run python`, or `pipenv run python`.

45. **Don't escape `!=` inside single-quoted shell strings** — `\!=` breaks Python (`SyntaxError: unexpected character after line continuation`) and jq (`INVALID_CHARACTER`). Inside `'...'`, all characters are literal.

46. **Use `python -m` for scripts with package-relative imports** — `python scripts/foo.py` fails with `ModuleNotFoundError` if the script uses `from scripts.bar import ...`. Use `python -m scripts.foo` instead.

47. **Inspect JSON structure before indexing** — `data['key']` on a list gives `TypeError: list indices must be integers`. Check `type(data)` first when working with unfamiliar JSON.

48. **Use `git push origin <tag>` instead of `--tags`** — `--tags` pushes ALL local tags. If any old tag already exists on the remote, git exits non-zero even though commits and new tags pushed fine. Push specific tags by name, or use `--follow-tags` for annotated tags reachable from pushed commits.

49. **Don't fabricate filesystem paths — use the working directory or discover with `ls`** — the agent invents plausible directory names (`Projects`, `GenAI_Projects`, `repos`) that don't exist. Use the environment's working directory for the current project, and `ls`/Glob to discover paths for other projects.

50. **Run project scaffolding tools BEFORE adding config files** — `create-next-app`, `create-vite`, etc. require an empty directory. Creating CLAUDE.md or `.claude/` first causes the scaffolder to abort with "files that could conflict." Scaffold first, configure second.

51. **Never pipe `curl` directly to a JSON parser** — `curl | jq` or `curl | python3 json.load()` crashes with unhelpful parse errors when the API returns non-JSON (HTML error pages, auth failures, rate limits). Save the response first and check HTTP status, or use `curl -sf` to fail on errors.

## Branch & Multi-Agent Rules

52. **Always verify the current branch before committing** — run `git branch --show-current` before any `git commit`. Don't assume the branch from conversation context — git state may have changed. If the user hasn't specified a branch, ask. Hook blocks push to main/master.

53. **Only the main agent handles git commit/push** — sub-agents and teammates write changes to their working directories. The main agent reviews all changes, runs tests, and commits centrally. This prevents wrong-branch pushes and merge conflicts from parallel agents.

54. **Run the full test suite after config or infrastructure changes** — config changes (tsconfig, eslint, package.json, .env, migrations, CI workflows) have broader blast radius than code changes. A single tsconfig modification can break hundreds of files. Always run `typecheck; lint; test` immediately after config changes, before proceeding.

55. **Only the main agent pushes — worktree agents commit locally** — when N agents work in parallel worktrees, each independent push triggers N x M CI runs (branches x workflows). Agents commit locally, main agent batch-pushes all branches in one command (`git push origin branch-1 branch-2 ...`), creates all PRs, and monitors CI centrally. Saves runner minutes (especially 10x macOS) and eliminates wrong-branch pushes.

56. **Don't assume GitHub labels exist — check or create first** — `gh issue create --label "chore"` fails if the label doesn't exist on the repo. Run `gh label list` first, or create needed labels with `gh label create`. When creating multiple issues, do it sequentially (not as parallel tool calls) to avoid Error #1 cancellation cascade.

---

For detailed symptoms, root causes, and examples, see [agent-errors.md](agent-errors.md).
