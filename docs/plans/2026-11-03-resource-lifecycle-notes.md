# Resource lifecycle implementation handoff

The owner authorized implementing the assessed shared resource policy in cc-rpi and necessary supporting instruction surfaces on 2026-11-03. Fleet updates are a subsequent action. The approved design puts portable ownership/completion policy in cc-rpi, executable lifecycle commands and protected-resource facts in each project, and fleet maintenance with the existing host owner. This change implements instruction delivery and adaptation guidance, not a Docker sweeper or project runtime rewrite.

Base: `a284a6e` on cc-rpi `main`. Implementation worktree: `/Users/juan/code/cc-rpi-resource-lifecycle`, branch `feat/resource-lifecycle-policy`. The repository was clean at entry. No Docker resources are created by this change; verification uses temporary filesystem fixtures. No remote publication, fleet reconciliation or host scheduler activation is included.

Acceptance: one canonical conditional rule reaches both clients through native output and the root task/path map, including task-only database/local-stack requests; ordinary task completion, Supabase verification, worktree cleanup and handoffs preserve the resource disposition; real update/detach fixtures preserve project contracts and private receipts; deterministic rendering and the complete portable gate pass. Native agent compliance and actual Docker disposal remain separate project acceptance, not claims of these tests.

## Verification and review

The new resource tests were run before implementation: task/path reachability failed in all five intended cases and update delivery failed because the component did not exist. After the rule, manifest and map changes, both tests passed. Independent review found one P2: the global fallback initially omitted explicit unique task identities and fresh ownership/consumer checks before stop/reset/removal. Both global instruction files were corrected and independently approved with no remaining findings. Private before/after hashes and recovery copies are retained locally. The simplify passes reused the existing renderer and shared handoff (reuse), clarified that another live owner blocks disposal rather than the owning lifecycle itself (quality), and retained conditional rule loading without a new controller or scheduler (efficiency). The full local gate must pass before integration; its exact candidate and evidence are retained under `.rpi/local/` and reported at delivery.

## Deviations

No separate planner phase or new executable resource controller was introduced: the owner explicitly authorized implementing the already assessed direction, and the existing distribution engine handles the new rule without code changes. Per-project executable adoption and fleet-wide instruction updates remain distinct from this blueprint change.
