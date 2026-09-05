# Cost Monitoring & Model Economics

Measure the cost of a verified outcome, including rework. RPI research and plans
provide reusable evidence, but implementation, validation and diagnosis still
require judgment. A reviewed plan does not establish that a cheaper model can
execute it adequately.

## Default: Inherit the Owner Pane

Workflows and helpers inherit the owner's active model and effort. Shared
instructions omit model overrides, generation pins and workflow cost tiers.
Respect an explicit per-request choice. Unknown or unavailable catalog data does
not justify replacing that choice.

The [model selection guide](context-engineering.md#model-selection--inherit-the-owner-pane)
documents native launch/profile controls and their precedence. Keep provider
selectors in the dated adapter descriptor, rather than copying concrete model
IDs into every workflow.

## Optional Economy Choices

An owner can explicitly select an economy launch or profile for a bounded
mechanical task: formatting, a factual status summary, or locating files within a
known scope. Define the expected output and verification first. Architectural
research, validation judgments and stateful diagnosis are not mechanical merely
because their workflow has a familiar name.

Use a separate session when native controls would otherwise override or persist
beyond the requested task. Claude skill frontmatter can override the owner's
session choice; Codex turn overrides persist into subsequent turns. RPI therefore
does not inject automatic economy frontmatter or switch the parent and promise
to restore it. Unsupported effort controls are omitted, not guessed. The default
inherit policy remains available without profiles or a model resolver.

## Measure Cost Per Outcome

Use the provider's actual usage export or billing evidence. Separate measured
values from estimates and record missing data explicitly. Useful comparisons:

| Measure | What it reveals |
|---------|-----------------|
| Cost per completed change | Inference and rework attributable to verified changes shipped |
| Cost per workflow run | Trends for comparable scope and acceptance requirements |
| Verification and rework | Whether a cheaper run produced more failures or follow-up work |
| Selection provenance | Requested model/effort and source versus session-bound observations |
| Tool and hosted compute | CI, deployment and other metered actions attributable to the outcome |

Do not infer a healthy model mix, universal price ratio, entitlement or quality
ranking from family names or catalog defaults. Local inference also uses hardware,
electricity and operator time. Compare like-for-like outcomes before changing a
profile. The [cost report agent](scheduled-agents.md#cost-report-agent) can
summarize available measurements; deterministic calculations should happen in
code, with uncertainty visible in the report.

## Budget and Authorization

The [remote budget](../patterns/deployment-safety.md) remains independent of model
choice: no Vercel Previews, no working-branch publication, and no hosted CI as an
experimentation loop. Complete applicable gates locally before the authorized
integration push. Production publication requires explicit authorization.

The `/pre-launch` (8 specialists, plus a conditional ninth for agent-facing
surfaces) coverage contract remains intact. Choose bounded independent work only
when its expected result justifies the extra inference and coordination. Existing task authorization remains valid;
this document creates no new approval gate for ordinary research or local work.
Report material budget constraints and measured regressions to the owner, and
change an explicit model selection only within their instructions.
