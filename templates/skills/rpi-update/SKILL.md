---
name: rpi-update
description: "Reconcile an installed RPI project with an explicit local source using recoverable ownership baselines, preserving local changes and reporting conflicts."
---

# Update an Installed RPI Project

Reconcile an explicit installed project with a verified local source/package.
Support interactive and unattended execution without guessing ownership.

Read [the lifecycle contract](references/lifecycle-contract.md) completely.
Resolve the installed package/source and target project from actual metadata and
the request; do not assume the current directory is the intended target. Use the
ownership-aware engine's explicit source/target plan/apply interface. Skill
invocation or tool visibility does not grant extra authority.

## Inspect and plan

1. Read `.rpi/manifest.json`, recoverable baselines and source receipt. For legacy
   adoption, inspect `.claude/cc-rpi-sync.json` and known v1 candidates without
   treating matching filenames as ownership. If no adoption evidence exists,
   report that fact and use `rpi-adopt` only if authorized.
2. Confirm the local source identity, installed revision and selected components.
   Fetching/pulling a source is separate from reconciliation and must preserve
   dirty work; never update native plugin caches with the file-sync engine.
3. Compare installed bytes with both baseline and selected upstream bytes even
   when the upstream revision is unchanged. Detect missing or damaged installed
   files and resources; do not declare an unchanged revision healthy by itself.
4. Read changed rules/workflow knowledge as needed. Generate the engine's explicit
   `update` plan and inspect per-file/block/key dispositions: unchanged, new,
   upstream-only, local-only, merged, conflict, missing/damaged and retained.

## Apply safely

Apply the safe reviewed plan within existing authorization. Unattended runs may
apply safe owned updates, but preserve conflicts and return a diagnostic rather
than prompting indefinitely or overwriting. Preserve:

- Project identity, stack, command choices and deployment/branch semantics.
- Custom AGENTS/CLAUDE content, rules and path mappings.
- Unknown/local skill directories, bundled resources, commands and hooks.
- User permissions, environment values, deny rules and hook customizations.
- Shared user lifecycle installations and native plugin ownership.

Update full resource directories, managed instruction blocks and individually
owned settings entries. Do not regenerate whole user settings files, bulk-delete
legacy commands, infer ownership from headings or three-way merge plugin caches.
Record recoverable nonsecret baseline bytes and the new source identity only
through successful transaction completion. Keep an interrupted transaction's
journal and recovery path for resume/rollback.

## Verify and report

Run engine diagnostics plus applicable local gates. Confirm selected resources,
unique registration routes/scopes, rule maps, instruction budgets and preserved
custom content. Report conflicts/damage explicitly; missing evidence is not success.

Commit only reviewed local changes and manifest/baselines atomically where
appropriate. Summarize source version/commit, changed/added/retained components,
instruction/settings changes, recovered damage, unresolved conflicts and verified
native invocations. Save a durable update handoff. Keep branches local and do not
push, create PRs, schedule hosted jobs or create Vercel Previews.
