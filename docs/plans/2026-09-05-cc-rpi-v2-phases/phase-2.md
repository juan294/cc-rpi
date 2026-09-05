# Phase 2: shared skills and native entry points

[Main plan](../2026-09-05-cc-rpi-v2.md). Depends on Phase 1. Not batch-eligible. Outcome: one canonical workflow corpus, rendered native interfaces, and compatibility paths ready for transactional installation.

## Changes

1. Migrate all 19 workflows to portable `templates/skills/rpi-<name>/SKILL.md`: adopt, brainstorm, bootstrap, describe-pr, detach, explore-release, fix-ci, implement, plan, pre-launch, release, remediate, research, status, tool-design, triage, update, update-docs, validate. Add `rpi-assess` for evaluative research. Keep domain skill names and conditional installation unchanged.
2. Make shared bodies describe inputs, scope, roles, evidence, artifact locations, completion, and phase boundaries, referring to “the request” generically. Remove provider-specific spawn names, model pins and shell substitutions. The Claude adapter supplies `argument-hint` and a small `$ARGUMENTS` input preamble where needed; the Codex adapter uses the actual invocation request without those substitutions. Preserve the common body byte-for-byte underneath the declared adapter preamble. `rpi-research` stays descriptive; `rpi-assess` evaluates alternatives/current practices, distinct from native code review. Both stop with research artifacts.
3. Add `templates/distribution.json` and `templates/adapters/{claude,codex}.json`. Component classes include skills, rule bodies, instruction blocks, hook/config entries and resources. Define stable IDs, scope, dependencies, selection, former paths, adapter output, aliases and plugin-owned versus project-managed installation. Direct installs put four lifecycle workflows at user scope and the other 16 at project scope; plugin skill scope follows its verified native mechanism. The Codex-only simplify helper is not exposed to Claude.
4. Add deterministic rendering in `templates/scripts/rpi-distribution.py`. Canonical frontmatter uses the portable skill contract. Keep adapter configuration in JSON to avoid inventing a general YAML implementation. The renderer accepts a documented strict subset for authored portable headers and fails on unsupported syntax; a real YAML validator separately checks emitted frontmatter/sidecars. Do not silently misparse user-authored YAML; custom files are preserved, not regenerated.
5. Emit Claude's invocation/model controls only into Claude outputs and Codex's supported sidecar policy only into Codex outputs. Default model/effort overrides are omitted or explicit native inheritance; no model switch is implied by prose. Side-effect lifecycle/release workflows require explicit invocation in both adapters. Invocation visibility and allowed-tools grants are not authorization or a read-only sandbox.
6. Generate a managed product tree under `generated/claude/skills/` for the existing Claude plugin and `generated/codex/skills/` for Codex distribution. These are checked-in generated artifacts, never manually edited. Direct root self-application uses individual declared links or copies; plugin self-application suppresses equivalent direct registrations. Preserve local extensions. The Claude package exports only managed Claude output, not the entire personal `.claude/skills` tree. An early Codex package probe must verify that its adapter semantics and Codex-only helper survive packaging; use a harness-specific generated package if the shared marketplace format cannot express those differences.
7. Render AGENTS as shared project facts plus marked managed policy/routing blocks. CLAUDE becomes `@AGENTS.md` plus Claude-only additions. The old reverse dependency is removed in the same rendered change. The actual ownership-safe migration executes in Phase 3.
8. Do not create legacy `plan` or `status` forwarders: they conflict with native commands. Migrate proven managed copies to the namespaced replacements with a clear rename notice and recovery copy; unknown/custom copies remain untouched and diagnosed. Other already-installed managed aliases may remain during 2.x with `disable-model-invocation: true`, so they remain explicitly callable without advertising extra descriptions to the model. Never add legacy aliases to a fresh install. Resolve the correct direct/plugin target and test that an explicit-only alias can actually forward to the target under its invocation policy; if native forwarding is blocked, use an explicit rename notice instead of bypassing the restriction. [Claude invocation controls](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill)

## Rule mapping and instruction budget

`templates/rules/` remains the authoring source. Inventory all six existing rules plus Phase 1's owner remote-budget component, and enumerate any deliberate consolidation rather than silently dropping a rule during migration.

| Canonical rule | Claude output | Codex output |
| --- | --- | --- |
| Universal RPI, remote budget and push accountability | Shared AGENTS invariant blocks imported by CLAUDE; do not duplicate them as always-loaded managed Claude rule bodies | Same AGENTS blocks |
| deployment-safety, supabase, testing, webmcp | Native `.claude/rules` with reviewed project `paths` mappings | Essential invariants and a short conditional path/task map in root AGENTS; complete bodies in `.rpi/rules/<name>.md` |

The Codex root map requires reading the relevant installed body before acting on a matching path/task. It is an instruction contract, not a native glob-triggered loader. Matching scope comes from the installed manifest; do not turn scattered SQL/test globs into invented directories. Optional nested AGENTS can repeat a scoped pointer for explicitly mapped subprojects, but must never be the only way a root-started session receives a safety constraint. Claude lazily loads nested CLAUDE files during relevant reads; Codex discovers a root-to-current-directory chain at startup. Test root-started edits into a nested directory and sessions started inside it separately. [Claude loading](https://code.claude.com/docs/en/memory), [Codex discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

Limit generated managed root AGENTS content to **8 KiB**, including marker bytes. This is a chosen product budget, not a claim about model capacity. Report complete installed instruction-chain bytes separately, including selected global/override files and project-owned additions, against the effective Codex limit (32 KiB by default). Never truncate user content or automatically raise the limit. Confirm consumer accounting with boundary fixtures; do not assume Claude's stripped comments are free in Codex. [Codex instruction limit](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

## Early plugin compatibility gate

Before building Phase 3's file-sync paths, test cc-rpi's actual local marketplace/package in isolated native profiles for both clients. Existing ingestion of another Claude marketplace establishes a lead, not compatibility of this package. Inspect actual installed files, names, resources, metadata treatment, hook availability/trust, plugin update/revert behavior and lifecycle source resolution. Confirm Claude's `/cc-rpi:rpi-plan`; record the actual Codex selector name rather than inventing one. Test generated supported packages, not just the current unrendered template export.

Decision rule: prefer plugin-owned immutable shared skills on a harness when install/load/invoke/resource/update tests pass, including adapter semantics and the declared domain-module selection behavior; keep customization in owned project files and never edit plugin cache. If a capability fails, retain that harness's native directory adapter and document why. Do not claim per-skill exclusion if the native manager only enables whole packages. Direct installation remains an offline/customization fallback; no project registers both routes for the same managed workflow. Preserve the renderer and project-migration tests, but do not build three-way cache merges, a package downloader, a duplicate plugin updater or a plugin rollback manager.

Record the route decision and tested package identity before Phase 3. Installation probes use isolated local configuration and do not alter the owner's marketplace setup. Any actual inference must be covered by the Phase 2/6 execution scope: move two relevant cases forward from Phase 6's 16, rather than adding an open-ended test campaign. This early gate tests native package management and skill access; full project migration and lifecycle execution are verified after Phase 3 supplies the engine.

## Tests and artifacts

TDD targets: renderer, manifest validation, resource resolution, alias collision classification and expanded skill/drift checkers. Modify `templates/scripts/{verify-skills,verify-counts,check-tree-drift}.sh` and plugin metadata so they enumerate the new product rather than the old tree. Generated counts separate 20 workflows, 12 domain skills, and one Codex-only helper; local extensions do not change exported counts.

```text
render(component, harness):
    validate portable source + declared adapter fields
    emit shared body unchanged and harness-specific metadata
    copy every declared resource with its relative layout
    validate dependencies and output containment
    return file inventory + hashes
```

Required cases: deterministic rerender; intentionally malformed metadata; duplicate ID; missing source/resource/rule mapping; empty manifest; unsupported Claude field in Codex output; escaped path; domain inclusion/exclusion; plugin/direct or user/project duplicate registration; local extension preservation; import-cycle rejection; root/nested rule reachability; instruction byte-budget boundaries; retired plan/status aliases; explicit-only forwarding; literal request arguments; source paths containing spaces/quotes/ampersand. Verify expected behavior independently, not only renderer snapshots generated by the same code.

`claude plugin validate templates/skills` returned success with no inspected contents during research. Native validation is supplementary only after a negative control proves it inspected the intended files. The project validator must report exact nonzero expected coverage.

## Acceptance and handoff

Automated: rendering, metadata/resource/rule/alias fixtures, self-application drift, full local gate, and clean generated-package extraction pass. All migrated commands retain their artifact/phase contract. No clone-path placeholder survives in published output. Complete the bounded plugin-route evidence now; remaining native menu/runtime coverage finishes in Phase 6. Do not claim discovery from file existence.

Human review: inspect one research, planning, implementation and lifecycle skill in both outputs. Confirm shared content has one source, adapter differences are justified, and no existing project/global installation has been rewritten. Handoff the stable schema, output inventory, alias map and fixtures to Phase 3.

## Execution status

- [x] Canonical workflow/adapter migration and deterministic rendering.
- [x] Resource, metadata, ownership-boundary and self-application verification.
- [x] Actual package research invocation, update/revert and domain-route evidence.
- [x] Full local gate: 10 checks and 53 unit tests passed.

Native lifecycle execution follows the Phase 3 runtime implementation; remaining
menu, instruction-chain and invocation cases remain in Phase 6 acceptance.
