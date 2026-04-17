# Agent Operational Rules -- Quick Reference

Scope: `[universal]` `[frequent]` `[situational]` `[rare]`
Stack: `[node]` `[python]` `[macos]` `[github]` (omitted = all stacks)
Enforcement: `[hook-enforced]` = blocked by PreToolUse hook.
Skills: `[skill:name]` points to `.claude/skills/name/` for full examples.

## Shell & Tools

1. **Chain fallible tool calls with && or ;** `[universal]` -- parallel siblings are all killed if one fails.

3. **Use absolute paths in file tools** `[universal]` -- Write/Read/Edit don't expand `~`.

17. **Don't escape operators inside single-quoted jq filters** `[frequent]` -- `!=` is literal inside `'...'`. Writing `\!=` passes a backslash to jq, causing syntax errors.

19. **Create boilerplate files sequentially** `[situational]` -- API content filters can block certain files (CODE_OF_CONDUCT, SECURITY.md). Sequential creation with fallback prevents wasted turns.

22. **Re-read directory contents before bulk operations** `[universal]` -- don't operate on stale file lists. `ls` first or use `rm -f`.

24. **Use absolute paths for cross-project commands** `[universal]` -- cwd resets between Bash calls. `../` breaks.

26. **Don't build complex regex in shell -- use dedicated tools** `[frequent]` `[macos]` -- macOS zsh treats `!`, `{`, `}` as special. Use the built-in Grep tool, dedicated linters, or `bash -c '...'` for complex regex.

27. **Only pass correct file types to linters** `[frequent]` -- `markdownlint` on `.sh` = false errors. Before "fixing" warnings, check if the pattern is intentional. Add linter exceptions, don't change content.

28. **Use `--fix` for auto-fixable linter issues** `[frequent]` -- `[*]` in ruff output means auto-fixable. Run `ruff check --fix` or `eslint --fix` first, then address remaining manual issues.

31. **Run `--help` on unfamiliar CLIs before guessing flags** `[universal]` -- `--json` works on `gh` but not `vercel`. Each CLI has its own flag vocabulary.

34. **Don't retry WebFetch on a 403 -- switch strategies** `[frequent]` -- a 403 means the domain blocks automated requests. Alternate paths also 403. Use WebSearch or ask the user.

36. **Write temp scripts instead of mega one-liners** `[universal]` -- if your command needs loops/awk with complex logic, write to `/tmp/script.sh`. Prefer built-in tools (Grep, Read, Glob) over shell pipelines.

45. **Don't escape `!=` inside single-quoted strings** `[frequent]` `[python]` -- `\!=` breaks Python (`SyntaxError`) and jq (`INVALID_CHARACTER`). Inside `'...'`, all characters are literal.

47. **Inspect JSON structure before indexing** `[universal]` -- `data['key']` on a list gives `TypeError`. Check `type(data)` first.

51. **Save curl output before parsing** `[universal]` -- `curl | jq` crashes with unhelpful errors when the API returns HTML or auth failures. Save response first and check HTTP status, or use `curl -sf`.

## Git `[skill:git-workflow]`

2. **Use absolute paths in worktree commands** `[universal]` -- shell cwd resets to the main repo between calls. Prefix every command with `cd /absolute/path/to/worktree &&`.

6. **Pull before push** `[universal]` -- remote may have advanced from other sessions or parallel agents.

7. **Remove worktrees before merging PRs with `--delete-branch`** `[frequent]` -- Git can't delete a branch checked out in a worktree.

8. **Force-remove worktrees** `[frequent]` -- worktrees have build artifacts/node_modules. Use `git worktree remove --force` with `;` not `&&` for multiple removals.

15. **Use `git branch -D` (uppercase) for worktree branches** `[frequent]` -- squash merges and deleted remotes make `-d` fail with "not fully merged." Full cleanup: `git worktree remove --force <path>; git branch -D <branch>`.

18. **Handle empty repos gracefully** `[situational]` -- `git log` and `git diff HEAD` fail on repos with no commits. Check `git rev-parse HEAD` first.

25. **Use `git push -u` on first push** `[universal]` -- both `git push` and `git pull --rebase` need upstream tracking. Use `git push -u origin <branch>` first.

30. **Push before `gh pr create`** `[frequent]` `[github]` -- a PR requires the branch on the remote. `git push -u` first.

33. **Commit before `git pull --rebase`** `[universal]` `[hook-enforced]` -- fails with a dirty working tree.

48. **Push specific tags, not `--tags`** `[universal]` `[hook-enforced]` -- `--tags` pushes ALL local tags. If any old tag exists on remote, git exits non-zero. Use `git push origin <tag>` or `--follow-tags`.

52. **Verify current branch before committing** `[universal]` -- run `git branch --show-current` before `git commit`. Don't assume from conversation context.

60. **Use `--ours`/`--theirs` for unmerged files** `[situational]` -- `git checkout --` fails on unmerged files during merge/rebase conflicts. Use `git checkout --ours <file>` or `--theirs`, or abort entirely. Check `git status` first.

61. **Remove conflicting untracked files before merge** `[situational]` -- untracked files at the same paths as incoming files cause git to abort. Delete or move them first.

## GitHub CLI `[skill:github-cli]`

9. **Don't guess `gh --json` field names** `[universal]` `[github]` -- fields differ per subcommand. Run `gh <cmd> --json 2>&1 | head -5` first. `conclusion` exists on `gh run` but not `gh pr checks`.

10. **Check CI per-PR with `--json`** `[universal]` `[github]` -- jumbled human-readable output is unreadable. `review: fail` means "needs approval", not CI failure -- filter it out.

20. **`gh release create` uses `--notes`, not `--body`** `[frequent]` `[github]` -- `--body` is for `pr create` and `issue create`.

23. **Don't fabricate GitHub identifiers** `[universal]` `[github]` -- repo names, branch names, issue numbers are case-sensitive. Use `gh repo list`, `git branch -r`, or `gh issue list --search`.

32. **Check repo merge settings before `gh pr merge`** `[frequent]` `[github]` -- repos may only allow squash/rebase or have auto-merge disabled. Run `gh api repos/{owner}/{repo}` first.

35. **`gh pr checks` exit 0 doesn't mean passed** `[frequent]` `[github]` -- all-pending checks also return 0. Inspect output or use `--json` to distinguish. Use `--watch` to wait.

43. **Upgrade `gh` if you hit "Projects (classic) deprecated"** `[rare]` `[github]` -- older `gh` versions query removed `projectCards` fields. `brew upgrade gh` fixes it.

56. **Don't assume GitHub labels exist** `[frequent]` `[github]` -- `gh issue create --label "chore"` fails if the label doesn't exist. Run `gh label list` first, or `gh label create`. Create issues sequentially to avoid Error #1 cascade.

57. **Check for existing PRs before `gh pr create`** `[frequent]` `[github]` -- fails if a PR already exists for the branch pair. Check with `gh pr list --head <branch>` first; use `gh pr edit` to update.

## CI & Verification `[skill:ci-workflow]`

4. **Pass `{ encoding: 'utf-8' }` to `execSync`/`spawnSync`** `[frequent]` `[node]` -- they return Buffers by default. `.trim()` fails on Buffer.

5. **Run typecheck/lint before committing** `[universal]` -- pre-commit hooks run the same checks. Fix first, commit second.

11. **Don't run ESM CLI tools with `node <file>`** `[situational]` `[node]` -- shebang + ESM = SyntaxError. Use `chmod +x && ./<file>` or `npx .`.

12. **Verify CI after every push** `[universal]` -- spawn a background agent to monitor. If CI fails, investigate and re-push. The push isn't done until CI is green.

16. **Install dependencies before running commands** `[universal]` `[node]` -- worktrees, clones, and CI don't have node_modules. Run `pnpm install` first.

50. **Run scaffolding tools before adding config files** `[situational]` `[node]` -- `create-next-app`, `create-vite`, etc. require an empty directory. Creating CLAUDE.md first causes the scaffolder to abort.

54. **Run full test suite after config changes** `[universal]` -- config changes (tsconfig, eslint, package.json, .env, CI workflows) have broader blast radius than code changes. Run typecheck + lint + test immediately.

## Python `[skill:python-rules]`

29. **Specify Python version for `uv sync`** `[frequent]` `[python]` -- `uv` auto-selects the newest Python. If Homebrew has 3.14+, packages may lack wheels. Check `.python-version` or use `uv sync --python 3.13`.

44. **Use `uv run python`, not bare `python3`** `[universal]` `[python]` `[hook-enforced]` -- system Python lacks project dependencies. Use `uv run python`, `poetry run python`, or equivalent.

46. **Use `python -m` for scripts with relative imports** `[frequent]` `[python]` -- `python scripts/foo.py` fails with `ModuleNotFoundError` if using `from scripts.bar import ...`. Use `python -m scripts.foo`.

## macOS `[skill:macos-rules]`

21. **Use `brew install` instead of `pip3 install` on macOS** `[frequent]` `[macos]` -- Python 3.12+ blocks system-wide pip (PEP 668). Use brew for CLI tools, pipx for Python apps.

37. **macOS launchd agents need four fixes** `[rare]` `[macos]` -- plist `HardResourceLimits`/`SoftResourceLimits` (NumberOfFiles: 122880), `EnvironmentVariables` (HOME, TERM, PATH), `claude setup-token` for non-interactive auth, and ProgramArguments must use `/bin/bash -c "exec /bin/bash <script>"`. Test with `launchctl start`, not from a terminal.

38. **launchd plist must not run project scripts directly** `[rare]` `[macos]` -- `<string>/project/scripts/agent.sh</string>` causes Claude CLI to crash with "Unexpected" when the script is inside a directory with `.claude/`. Use `/bin/bash -c "exec /bin/bash <script>"` wrapper. Exit code is 0 despite the error.

## Multi-Agent `[skill:multi-agent]`

53. **Only the main agent handles git commit/push** `[universal]` -- sub-agents write changes; the main agent reviews, tests, and commits centrally. Prevents wrong-branch pushes and merge conflicts.

55. **Only the main agent pushes -- worktree agents commit locally** `[universal]` -- N independent pushes trigger N x M CI runs. Agents commit locally, main agent batch-pushes all branches, creates PRs, and monitors CI centrally.

73. **Parallel agents run scoped tests only -- full suite runs once at integration** `[universal]` -- N agents each running the full test suite creates N x workers processes that exhaust CPU/memory. Agents test only their changed files; limit concurrent agents to 3-4; run the full suite once after merging.

## Deployment & Resources `[skill:deployment-safety]`

62. **Merging to main IS deploying to production** `[universal]` -- in projects with CI/CD, a merge is a deployment. Dependabot PRs target main by default.

63. **Batch dependency updates into a single PR** `[frequent]` -- merging N PRs one-by-one with "require up-to-date" creates O(n^2) CI waste. Create one branch, apply all updates, run CI once.

64. **Every CI run costs money -- count before triggering** `[universal]` -- estimate runs before starting. If >2-3, find a more efficient approach. Work locally until confident, push once.

65. **Framework upgrades need preview verification** `[frequent]` -- CI passing is necessary but not sufficient. Build != Runtime. Deploy to a preview URL and verify the site loads before merging.

66. **When production is down: roll back first** `[universal]` -- restore service immediately. Investigate on a non-production environment. Fix forward on develop, verify on preview, release to main.

67. **Justify every external action before triggering** `[universal]` -- before any CI run, deployment, or API call: Is this needed? Is this justified? Is this verifiable? If any answer is "no", stop.

## Supabase `[skill:supabase]`

72. **Test migrations locally before pushing to remote** `[frequent]` -- run `supabase start` + `supabase db reset` locally, verify with `docker exec ... psql`, then `supabase db push`. The local instance has full Postgres with RLS and extensions -- treat it as UAT.

## Quality & Process

13. **Write tests before implementation (TDD)** `[universal]` -- Red-Green-Refactor. Bug fixes need a regression test first.

14. **Exhaust all tools before suggesting manual steps** `[universal]` -- check CLI tools, shell commands, MCP servers, file tools before escalating to the user.

39. **Run `/simplify` after reviewer approval** `[frequent]` -- catches code reuse, quality, and efficiency issues the plan-compliance reviewer doesn't check.

40. **Mark independent plan phases as `[batch-eligible]`** `[frequent]` -- during `/plan`, identify phases with no file overlap. `/batch` executes them in parallel (one worktree per phase, each opens a PR).

41. **Use `/batch` for bulk changes outside RPI** `[situational]` -- migrations, multi-issue sprints, repetitive refactors. Don't manually iterate through 20 files when `/batch` can parallelize.

42. **After `/pre-launch`, run `/simplify` first** `[situational]` -- fixes dead code, duplicates, inefficiencies in one pass. Then address security and infrastructure findings manually.

49. **Don't fabricate filesystem paths** `[universal]` -- the agent invents plausible names (`Projects`, `repos`). Use the working directory or discover with `ls`/Glob.

58. **Fix everything, always** `[universal]` -- categorize by severity, but fix 100%. With AI agents, fix cost is near-zero. Exception: `/remediate` Wave 3 (Later/strategic) items get issues filed but no fix agents -- requires human architectural judgment.

59. **Use `.claude/rules/` with `paths` frontmatter for conditional rules** `[frequent]` -- domain rules load only when Claude works with matching files (e.g., deployment rules on `.github/**`, test rules on `**/*.test.*`). Replaces `<important if>` blocks with infrastructure-level conditional loading.

68. **Every fallback path must be observable** `[universal]` -- add ERROR-level logging when fallbacks activate, health endpoint coverage for degraded state, and alerting hooks. A silent fallback is a silent production bug.

## Agent Reports

70. **Do not commit agent reports to the repository** `[universal]` -- `docs/agents/`, `logs/`, `scripts/agents/` are gitignored. Reports are local operational tools. The only triage commits are code fixes.

71. **Use timestamp-based discovery for triage** `[frequent]` -- touch `docs/agents/.last-triage` after each run. Next triage uses `find ... -newer .last-triage`. On first run, process all reports.

74. **Promote repeated failures beyond prose** `[frequent]` -- after 3
recurrences, choose the smallest durable asset: rule, hook, scripted
verifier, or golden-case fixture.

---

For detailed symptoms, root causes, and examples, see [agent-errors.md](agent-errors.md).

For the full deployment safety guide, see [deployment-safety.md](deployment-safety.md).
