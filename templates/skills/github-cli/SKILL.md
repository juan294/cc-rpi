---
name: github-cli
description: "gh CLI patterns, JSON field discovery, PR check interpretation, label management, merge settings verification, CodeQL/GHAS gating."
---

# GitHub CLI

## JSON Field Discovery

Wrong -- guess field names:

```bash
gh pr checks 42 --json conclusion  # Unknown field
```

Right -- discover fields first:

```bash
gh pr checks 42 --json 2>&1 | head -5
```

## PR Check Interpretation

Wrong -- exit code 0 means passed, raw output is readable:

```bash
gh pr checks 42  # exit 0 but checks still pending; "review: fail" looks like CI
```

Right -- use structured JSON, filter review, or --watch:

```bash
gh pr checks 42 --json name,state,conclusion | jq '.[] | select(.name != "review")'
gh pr checks 42 --watch
```

## Release vs PR Flags

Wrong -- --body is for pr/issue create, not release:

```bash
gh release create v1.0.0 --body "notes"
```

Right -- releases use --notes:

```bash
gh release create v1.0.0 --notes "notes"
```

## Label and Merge Settings

Wrong -- assume labels exist and merge method is allowed:

```bash
gh issue create --label "chore" --title "Fix"  # label not found
gh pr merge 42 --merge                         # method not allowed
```

Right -- check or create first:

```bash
gh label list && gh label create "chore" --color "ededed"
gh api repos/{owner}/{repo} --jq '.allow_squash_merge, .allow_merge_commit'
```

When creating multiple issues, create them sequentially, not as parallel
tool calls -- a batch of parallel `gh issue create` calls that all hit the
same missing label fail together instead of surfacing once.

## Deprecated Projects (Classic) API

Wrong -- an older `gh` version queries a removed field and errors:

```bash
gh issue view 42 --json projectCards  # Projects (classic) is deprecated
```

Right -- upgrade `gh` first:

```bash
brew upgrade gh
```

## CodeQL Requires GHAS

Wrong -- add a code-scanning workflow without checking GHAS is enabled:

```yaml
# .github/workflows/codeql.yml added blindly -- fails CI on every push
```

Right -- confirm GHAS is enabled before adding the workflow:

```bash
gh api repos/{owner}/{repo}/code-scanning/alerts  # non-403 = GHAS enabled
```

GHAS is free on public repos but a paid add-on on private repos -- on
private repos, enabling it is a human cost decision, not an autonomous fix.
Querying existing alerts (what `/triage` does) is always safe; creating the
scanner workflow is not. For the full guardrail rationale, see
`methodology/ci-and-guardrails.md` in the cc-rpi blueprint repository.

## Duplicate PR Prevention

Wrong -- create PR when one already exists for this branch:

```bash
gh pr create --title "feat: thing"
```

Right -- check first, edit if exists:

```bash
gh pr list --head <branch> --base <base>
# Exists: gh pr edit <number>  |  New: gh pr create
```

## Identifier Discovery

Wrong -- fabricate repo names or issue numbers (case-sensitive):

```bash
gh issue view 42 --repo owner/MyProject
```

Right -- discover identifiers:

```bash
gh repo list owner --json name --limit 50
gh issue list --search "bug in login"
```
