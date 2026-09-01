# Agent Operational Rules -- Index

An **index, not a catalog**. Every rule body lives in the surface that needs
it, so it loads at its point of use and costs nothing otherwise. Scope and
stack tags travel with the body.

Destinations -- `skills/<n>` = `templates/skills/<n>/SKILL.md` (loads on
description match); `rules/<f>` = `templates/rules/<f>` (loads via `paths:`
frontmatter); `commands/<f>` = a step in that slash command;
`methodology/<f>` = authoring-time reading; `hook: <s>` = not relocated, a
Tier 1 hook already enforces it.

Numbers are permanent and never reused. A gap means **retired**, not missing.
Retired so far: 67, 69, and 80 -- the ground for each is recorded in the
ledger in `.claude/rules/contributing.md`.

## Shell & Tools [skill:shell-tools]

1. Chain fallible tool calls with `&&` or `;` -> skills/shell-tools
3. Use absolute paths in file tools -- no `~` expansion -> skills/shell-tools
17. Don't escape operators inside single-quoted jq filters -> skills/shell-tools
19. Create boilerplate files sequentially -> skills/shell-tools
22. Re-read directory contents before bulk operations -> skills/shell-tools
24. Use absolute paths for cross-project commands -> skills/shell-tools
26. Build complex regex in a tool, not in zsh -> skills/shell-tools
27. Only pass matching file types to linters -> skills/shell-tools
28. Use `--fix` for auto-fixable linter issues -> skills/shell-tools
31. Run `--help` on unfamiliar CLIs before guessing flags -> skills/shell-tools
34. A WebFetch 403 means switch strategies, not retry -> skills/shell-tools
36. Write temp scripts instead of mega one-liners -> skills/shell-tools
45. Don't escape `!=` inside single-quoted strings -> skills/shell-tools
47. Inspect JSON structure before indexing -> skills/shell-tools
49. Don't fabricate filesystem paths -> skills/shell-tools
51. Save curl output before parsing -> skills/shell-tools

## Git [skill:git-workflow]

2. Use absolute paths in worktree commands -> skills/git-workflow
6. Pull before push -> skills/git-workflow
7. Remove worktrees before merging with `--delete-branch` -> skills/git-workflow
8. Force-remove worktrees -> skills/git-workflow
15. Use `git branch -D` for worktree branches -> skills/git-workflow
18. Handle empty repos gracefully -> skills/git-workflow
25. Use `git push -u` on first push -> skills/git-workflow
30. Push before `gh pr create` -> skills/git-workflow
33. Commit before `git pull --rebase` -> hook: guard-bash.sh
48. Push specific tags, not `--tags` -> hook: guard-bash.sh
52. Verify current branch before committing -> skills/git-workflow
60. Use `--ours`/`--theirs` for unmerged files -> skills/git-workflow
61. Remove conflicting untracked files before merge -> skills/git-workflow

## GitHub CLI [skill:github-cli]

9. Don't guess `gh --json` field names -> skills/github-cli
10. Check CI per-PR with `--json` -> skills/github-cli
20. `gh release create` uses `--notes`, not `--body` -> skills/github-cli
23. Don't fabricate GitHub identifiers -> skills/github-cli
32. Check repo merge settings before `gh pr merge` -> skills/github-cli
35. `gh pr checks` exit 0 doesn't mean passed -> skills/github-cli
43. Upgrade `gh` on "Projects (classic) deprecated" -> skills/github-cli
56. Don't assume GitHub labels exist -> skills/github-cli
57. Check for existing PRs before `gh pr create` -> skills/github-cli
82. No CodeQL workflow without GHAS -> skills/github-cli

## CI & Verification [skill:ci-workflow]

4. Pass `{ encoding: 'utf-8' }` to `execSync`/`spawnSync` -> skills/ci-workflow
5. Run typecheck/lint before committing -> skills/ci-workflow
11. Don't run ESM CLI tools with `node <file>` -> skills/ci-workflow
12. Verify CI after every push -> skills/ci-workflow
16. Install dependencies before running commands -> skills/ci-workflow
50. Run scaffolding tools before adding config files -> skills/ci-workflow
54. Run the full test suite after config changes -> skills/ci-workflow

## Python [skill:python-rules]

29. Specify a Python version for `uv sync` -> skills/python-rules
44. Use `uv run python`, not bare `python3` -> hook: guard-bash.sh
46. Use `python -m` for scripts with relative imports -> skills/python-rules

## macOS [skill:macos-rules]

21. Use `brew install` instead of `pip3 install` -> skills/macos-rules
37. macOS launchd agents need four fixes -> skills/macos-rules
38. launchd plists must not run project scripts directly -> skills/macos-rules

## Multi-Agent [skill:multi-agent]

53. Only the main agent handles git commit/push -> skills/multi-agent
55. Only the main agent pushes; worktree agents commit -> skills/multi-agent
73. Parallel agents run scoped tests only -> skills/multi-agent
78. Spawn agents with a terminal condition -> skills/multi-agent
79. Dedup against repo state before continuing work -> skills/multi-agent

## Deployment & Resources [skill:deployment-safety]

62. Merging to the production branch IS deploying -> skills/deployment-safety
63. Batch dependency updates into a single PR -> skills/deployment-safety
64. Every CI run costs money -- count first -> skills/deployment-safety
65. Framework upgrades need preview verification -> skills/deployment-safety
66. When production is down, roll back first -> skills/deployment-safety
68. Every fallback path must be observable -> skills/deployment-safety
76. Standardize GitHub repo settings per project -> skills/deployment-safety

## Supabase [skill:supabase]

72. Test migrations locally before pushing to remote -> skills/supabase

## Agent-Facing Tools [skill:webmcp]

85. Scope each WebMCP tool to one function -> skills/webmcp
86. Name agent tools by effect -- execute vs initiate -> skills/webmcp
87. Take raw user input; don't make the agent compute -> skills/webmcp
88. Validate strictly in code, loosely in schema -> skills/webmcp
89. A tool error is a recovery instruction, not a stack trace -> skills/webmcp
90. Register and unregister tools with page state -> skills/webmcp
91. Confine the pre-standard modelContext global to one adapter -> rules/webmcp.md
92. Role-play and ship an eval before shipping a tool -> methodology/webmcp-tool-design.md

## RPI Process

14. Exhaust all tools before suggesting manual steps -> rules/rpi-details.md
39. Run `/simplify` after reviewer approval -> rules/rpi-details.md
40. Mark independent plan phases `[batch-eligible]` -> rules/rpi-details.md
41. Use `/batch` for bulk changes outside RPI -> rules/rpi-details.md
42. After `/pre-launch`, run `/simplify` first -> rules/rpi-details.md
58. Fix everything, always -> rules/rpi-details.md

## Testing

13. Write tests before implementation (TDD) -> rules/testing.md

## Findings

83. A finding's recommendation is a hypothesis -> commands/pre-launch.md + commands/remediate.md

## Agent Reports

70. Report commit policy depends on repo visibility -> commands/triage.md
71. Use timestamp-based discovery for triage -> commands/triage.md
84. Triage processes Dependabot PRs -> commands/triage.md

## Cost & Models

74. Pin a model tier to every workflow -> methodology/cost-monitoring.md
75. Measure cost per outcome, not per token -> methodology/cost-monitoring.md

## Authoring & Doc Discipline

59. Use `.claude/rules/` with `paths` frontmatter -> methodology/context-engineering.md
77. No emojis in documentation -> hook: verify-edit.sh
81. Format markdown tables programmatically -> hook: verify-edit.sh

---

For detailed symptoms, root causes, and examples, see
[agent-errors.md](agent-errors.md).

For the full deployment safety guide, see
[deployment-safety.md](deployment-safety.md).
