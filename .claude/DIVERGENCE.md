# Divergence Manifest

`templates/` is the **product** -- the blueprint shipped downstream. `.claude/`
is cc-rpi's **self-application** of that product. They are not accidentally
redundant: only `.claude/commands/` and `.claude/skills/` auto-discover when
this repo is opened as a working directory, and `.claude-plugin/plugin.json` is
consulted only under `claude --plugin-dir .` or a marketplace install.

Most shared files are byte-identical, so they are **symlinks** into
`templates/`: edit the template and the self-application follows. A few must
differ, because a blueprint written for any repo cannot state a fact that is
true only of this one. Those stay real files, listed below with the reason.

`scripts/check-tree-drift.sh` validates this file against the filesystem. It
fails when a symlink has been materialized as a copy, when a file listed as
divergent has become identical (a stale divergence that should be collapsed),
and when a shared filename appears in neither list.

## Linked

Symlinks from `.claude/<path>` to `../../templates/<path>`. Edit the template.

| File |
|------|
| `commands/describe-pr.md` |
| `commands/plan.md` |
| `commands/pre-launch.md` |
| `commands/remediate.md` |
| `commands/research.md` |
| `commands/status.md` |
| `commands/triage.md` |
| `commands/update-docs.md` |
| `commands/validate.md` |
| `hooks/verify-edit.sh` |
| `scripts/contract-metrics.py` |
| `scripts/validate-findings.py` |
| `scripts/verify-counts.sh` |
| `scripts/verify-skills.sh` |
| `scripts/verify-version.sh` |

## Divergent

Real files in both trees. Each divergence is load-bearing; collapsing it would
either lie to downstream projects or misdescribe this one.

| File | Why it differs |
|------|----------------|
| `commands/fix-ci.md` | The template says "a protected production branch" because it cannot know the repo's topology. This repo's is `main`, so the local copy names it. |
| `commands/implement.md` | Same reason: the template says "the integration branch", the local copy says `main`, which is cc-rpi's long-lived canonical branch. |
| `commands/release.md` | The template describes version-scanning generically. cc-rpi has repeatedly shipped with the README badge and `.claude-plugin/*.json` left one to two releases stale, so the local copy carries a specific warning about that history, and points the retirement review at this repo's own ledger. |
| `hooks/guard-bash.sh` | The template blocks direct pushes to `main`/`master` (Error #48). cc-rpi's long-lived branch IS `main`, and validated changes may be pushed there after explicit approval, so the local copy comments that guard out and explains why. The policy here is "high-stakes and exceptional", not "never". |
| `rules/rpi-details.md` | Same topology reason as `commands/implement.md`: the template says "the integration branch" because it cannot know a project's topology, while cc-rpi's copy names `main` and adds that `main` is the canonical branch, not the default edit target. The heading and `description` also name cc-rpi specifically. Roughly 94 percent of the file is shared, so this pair is the one most likely to drift by someone editing only one side -- which is exactly why it is tracked here rather than left as two unrelated filenames. |

## Adding a shared file

When a file gains a counterpart in the other tree, add it to exactly one table
above. If it is identical, replace the copy with a symlink:

```bash
rm .claude/<path>
ln -s ../../templates/<path> .claude/<path>
```

If it must differ, record the reason in the Divergent table. "It just drifted"
is not a reason -- that is a bug, and the fix is to relink it.

## Windows

Symlinks require developer mode or an elevated shell on Windows. A checkout
without that support materializes them as regular files. `check-tree-drift.sh`
reports that as a failure with a fix rather than passing silently, so the fork
is visible instead of invisible.
