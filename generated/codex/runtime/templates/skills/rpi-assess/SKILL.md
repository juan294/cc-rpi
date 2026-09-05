---
name: rpi-assess
description: "Evaluate the requested architecture, alternatives or current practices against repository evidence and primary sources, ending with a cited assessment artifact."
---

# Assess Alternatives and Current Practices

Evaluate the question in the request against the actual codebase, explicit goals,
constraints and current primary-source evidence. This is evaluative research;
`rpi-research` remains descriptive and a code-review workflow reviews a concrete
change. Do not turn an assessment into implementation.

## Process

1. Read directly mentioned files completely. Establish the decision to support,
   scope, baseline commit, criteria and material unknowns from the request and
   repository. Ask only for missing information that changes the evaluation.
2. Map the current system with cited `file:line` evidence. Distinguish current
   behavior, historical intent, external facts and inference.
3. Use bounded independent investigations when useful. Cover relevant alternatives
   and counterevidence, not a fixed number of agents or a predetermined winner.
4. Verify changing facts and niche claims using current primary sources. Record
   source dates, versions and verification date. Local pinned code/help is strong
   evidence for installed behavior; official documentation establishes external
   contracts. Never imply browsing occurred when it did not.
5. Compare options against explicit criteria: compatibility, correctness, security,
   user experience, maintenance, cost, operational constraints and migration risk
   where relevant. State trade-offs and what evidence could reverse the conclusion.
6. Write `docs/research/YYYY-MM-DD-description-assessment.md` containing the question,
   baseline, criteria, current-state evidence, alternatives, comparison, recommended
   direction with rationale, counterevidence, uncertainties and any decision needed.
7. Preserve the assessment as curated project knowledge. Present the recommendation,
   evidence limits and artifact path, then **stop**. Planning or implementation is
   a separate workflow unless the request explicitly authorizes it.

No code/configuration edits, dependency installation, remote mutation or automatic
issue creation occurs during assessment. Avoid unsupported rankings and generic
recommendations that ignore the project's actual constraints.
