# cc-rpi release verification profile

This adapts the [release playbook](../templates/skills/rpi-release/references/e2e-pro-playbook.md)
to a public blueprint and portable CLI distribution. It does not invent a web
deployment, application datastore, registry publication or production smoke test.

## Project and environment

| Area | Project value |
|---|---|
| Product and artifact | Public `juan294/cc-rpi`; Markdown workflows, Python/Bash tools and generated native packages at an exact Git commit and annotated version tag |
| Build | `python3 templates/scripts/rpi-distribution.py render --source . --output generated`; checked generated files are the distributable artifact |
| Integration and publication | Main-only topology; implementation in an isolated local branch/worktree, reviewed local fast-forward to `main`, one authorized main push, then exact named tag and GitHub release |
| Owner and authority | Repository owner authorizes release version, remote compute and any rollback; an implementation request alone does not authorize production |
| Complete gate | `bash scripts/verify-local.sh`: ten ordered checks declared in `.rpi/policy.json`, including measured subprocess coverage and nonempty test inventory |
| Unit/integration selection | `python3 scripts/verification-checks.py unit-tests`; same authoritative results feed coverage on identical candidate/runtime |
| Lint and types | ShellCheck, Markdown links/frontmatter and count/version/skill/drift checks; Python compilation, JSON/YAML/native schemas. No separate application typechecker exists. |
| Native E2E | Version-bound Claude and Codex package discovery, selector, workflow and permission cases in disposable projects; recorded outside the published source |
| Datastore/storage/events | No product service; synthetic files, Git receipts and local lifecycle journals. PostgreSQL recipe acceptance uses a disposable local database. |
| Authentication/vendors | Existing owner native-client authentication for authorized inference. GitHub publication and existing Portfolio reporting are separate remote effects. No payment, mail or hardware integration. |
| Observability | Candidate-bound `.rpi/local` verification, coverage and native transcripts; public handoff contains sanitized conclusions. |
| Rollback | Select the previous native plugin version; preview and apply receipt-backed project reconciliation or use the specific preserved lifecycle journal. Never reset custom content indiscriminately. |

| Environment | Artifact and fidelity | Authorized writes and limits |
|---|---|---|
| Local macOS | Exact candidate; real filesystem and CLI consumers | Synthetic fixture writes and owner-authorized repository changes; loopback reporting only |
| Local Linux | Exact snapshot in a pinned Ubuntu 24.04 amd64 container, Python 3.11/3.13, network disabled for gates | Disposable fixture writes; proves Linux portable behavior, not a hosted service deployment |
| Native harness fixtures | Digest-bound extracted packages; real clients and inference authentication | Synthetic local files and fake Git transport only; ambient capabilities and client versions recorded |
| GitHub Actions | Exact published main SHA; Validate plus Coverage and its Portfolio report | One authorized completed-main push after local gates; no hosted debugging retries |
| Preview/staging/production app | No applicable application target | No Vercel Preview or production deployment is part of this release |

## Required obligations

Wave A is enforced by the nonempty machine-readable check inventory, aggregated
exits, candidate/runtime identity, measured executed tests and coverage receipts.
Missing, failed, stale or substituted required evidence blocks acceptance.
Loopback report tests verify signing, rejection and retry behavior with synthetic
credentials; they never contact Portfolio during preflight.

Wave B uses two independent fresh-context charters on an immutable candidate:
ownership/recovery and policy/verification/reporting. Each attempts all eight
maneuvers, adapting locale/device to shell, encoding or execution context. Reports
include concrete observations, all findings, high-risk gaps and cleanup evidence.
Any failure must be repaired and its invalidated evidence rerun before release.

The selected C-H work is proportional to this product: the distribution manifest
and finding ledger map capabilities; nine adopter/harness combinations exercise
important interactions; lifecycle transaction and policy tests cover state changes;
extracted native packages and local Linux supply environment fidelity. A separate
capability service, combination compiler, production vendor cadence and hardware
arcs are inapplicable. The full platform program is not claimed implemented.

For v2.0.0, native evidence covers 16 named scenarios, with failed infrastructure
attempts and necessary bounded reruns recorded separately. Evidence can be reused
only when its actual input hashes remain unchanged. Documentation-only updates
do not imply rerunning unaffected native inference, but final local gates bind the
complete integrated candidate.

## Publication evidence

Before pushing, inspect GitHub workflows/webhooks and connected deployment
projects read-only. A discovered Vercel Preview trigger blocks publication.
Record the exact integrated SHA and accepted local/native/charter evidence, push
completed `main` once, and require both expected push workflows to succeed for
that SHA. Then create and push only annotated `v2.0.0` at that commit and publish
the reviewed notes with `gh release create --verify-tag --notes-file`.

Read back the tag target and release identity before calling the version released.
Remote-only failures stay failures and are diagnosed locally; no automatic rerun
or repair-and-repush loop is authorized by this profile. Preserve operational
evidence in its ignored local location when it is still needed for recovery.

## Disposable scheduler lifecycle acceptance

The tracked fixture exercises the shipped installer with a fake `launchctl`,
including repeated install/removal, failed reload/removal, unavailable status,
bootstrap failure and interrupted-install recovery. It checks real generated
plist files and durable fake scheduler state. This proves the installer contract;
it does not claim actual macOS launchd compatibility or execute agent workloads.

Run locally using the already-prepared Ubuntu image; no image build, pull, owner
HOME mount, authentication mount or Docker socket is part of this check. The
fixture refuses ordinary host execution, existing HOME scheduler directories,
and nonempty fixture directories. The container keeps its default HOME unchanged.

```bash
mkdir -p .rpi/local
RPI_SCHEDULER_EVIDENCE=$(mktemp -d "$PWD/.rpi/local/scheduler-acceptance.XXXXXX")
printf 'Local scheduler evidence: %s\n' "$RPI_SCHEDULER_EVIDENCE"
docker run --rm --init --pull never --platform linux/amd64 --network none \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$PWD/tests/fixtures/scheduler-lifecycle.py,dst=/input/scheduler-lifecycle.py,readonly" \
  --mount "type=bind,src=$PWD/templates/scripts/agents/install-agents.sh,dst=/input/install-agents.sh,readonly" \
  --mount "type=bind,src=$RPI_SCHEDULER_EVIDENCE,dst=/work" \
  sha256:f13ee02e989c0cfd91c04426a3c235770521df3c1ea0f2d1e9339266e915aca4 \
  python /input/scheduler-lifecycle.py --disposable-container
```

Require exit zero and preserve `evidence/results.json` and `evidence/cleanup.json`
from the printed local fixture directory. Results bind the installer and fixture
hashes. This is a separate required local release check; ordinary CI runs the
portable status tests without mutating any host scheduler state.
