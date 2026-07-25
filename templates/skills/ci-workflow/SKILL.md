---
name: ci-workflow
description: "Push accountability, CI monitoring after push, background agent CI verification, verification command sequencing."
---

# CI Workflow

## Push Accountability

Use the branch that is currently under CI verification. In a
`develop/main` topology this is often `develop`. In a `main-only` repo
it is usually the temporary branch or PR branch being validated before
merge.

Wrong -- push and move on:

```bash
git push origin <branch-under-test>
# Start next task immediately, never check CI
```

Right -- spawn background agent to monitor CI:

```bash
git push origin <branch-under-test>
# Background agent:
gh run list --branch <branch-under-test> --limit 1
# If CI fails: investigate with gh run view <id> --log-failed
# Fix and re-push. The push isn't done until CI is green.
```

## Buffer Output from execSync/spawnSync

Wrong -- `.trim()` fails because these return a Buffer by default:

```js
const sha = execSync('git rev-parse HEAD').trim();  // TypeError
```

Right -- pass encoding explicitly:

```js
const sha = execSync('git rev-parse HEAD', { encoding: 'utf-8' }).trim();
```

## Running ESM CLI Tools

Wrong -- `node <file>` on a shebang + ESM script throws SyntaxError:

```bash
node ./bin/cli.js
```

Right -- run it as an executable, or use npx:

```bash
chmod +x ./bin/cli.js && ./bin/cli.js
npx .
```

## Missing Dependencies

Wrong -- run commands in a worktree, fresh clone, or CI with no node_modules:

```bash
pnpm run build  # Cannot find module ...
```

Right -- install first:

```bash
pnpm install && pnpm run build
```

## Scaffolding Requires an Empty Directory

Wrong -- add config files before scaffolding, so the tool aborts:

```bash
echo "# Project" > CLAUDE.md
npx create-next-app@latest .   # aborts: directory not empty
```

Right -- scaffold first, add config files after:

```bash
npx create-next-app@latest .
echo "# Project" > CLAUDE.md
```

## Verification Command Sequencing

Wrong -- run typecheck, lint, test as parallel tool calls:

```bash
# Parallel call 1: pnpm run typecheck
# Parallel call 2: pnpm run lint
# Parallel call 3: pnpm run test
# If one fails, all parallel calls are killed (Error #1)
```

Right -- chain sequentially with semicolons:

```bash
pnpm run typecheck 2>&1; pnpm run lint 2>&1; pnpm run test 2>&1
```

## Pre-Commit Verification

Wrong -- commit first, discover failures from pre-commit hook:

```bash
git commit -m "feat: add feature"
# Pre-commit hook fails: lint errors, type errors
```

Right -- run checks before committing:

```bash
pnpm run typecheck 2>&1; pnpm run lint 2>&1
git add <files> && git commit -m "feat: add feature"
```

## Config Change Blast Radius

Wrong -- change tsconfig and continue coding:

```bash
# Edit tsconfig.json
# Continue implementing next feature
# Discover 200 type errors at commit time
```

Right -- run full test suite immediately after config changes:

```bash
# Edit tsconfig.json
pnpm run typecheck 2>&1; pnpm run lint 2>&1; pnpm run test 2>&1
# Fix any breakage before proceeding
```
