# Agent Operational Rules — Quick Reference

These rules must be internalized before starting any work. They prevent the most common recurring errors across all projects.

## Shell & Tool Rules

1. **Never run verification commands as parallel sibling Bash calls** — chain with `&&` or `;` instead. If one sibling fails, all parallel calls are killed.

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

---

For detailed symptoms, root causes, and examples, see [agent-errors.md](agent-errors.md).
