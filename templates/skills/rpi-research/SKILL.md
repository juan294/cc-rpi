---
name: rpi-research
description: "Document how an existing codebase works to answer the requested research question, producing a cited research artifact without implementation or evaluative recommendations."
---

# Research the Existing Codebase

Use the question and file paths in the request. This workflow is descriptive:
record what exists and how it works. For alternatives, current-practice judgments
or recommendations, use `rpi-assess` as a separate evaluative workflow.

## Process

1. Read [the research contract](references/research-contract.md) and every
   directly mentioned file completely before decomposing the question.
2. Identify the research areas needed: locate relevant files, trace behavior and
   data flow, find comparable patterns, and inspect relevant historical documents.
3. Choose bounded independent read-only assignments when they reduce uncertainty.
   Assign explicit scope, output evidence and a completion condition. Work locally
   when delegation adds no value; wait for all delegated results before synthesis.
4. Verify claims against the actual code. Distinguish repository evidence from
   historical descriptions and external facts. Record gaps rather than inventing
   behavior or creating unnecessary open questions.
5. Write `docs/research/YYYY-MM-DD-description.md` with the actual date, topic,
   repository, branch and commit; summarize the answer, detailed findings,
   `file:line` evidence, relevant context and unresolved questions.
6. Preserve the research artifact as curated project knowledge under the project's
   tracking policy. Keep raw machine inventories and transient evidence local.
7. Present a concise summary, artifact path and outstanding uncertainty. **Stop at
   the research boundary.** Do not begin planning or implementation unless the
   user explicitly authorized that next workflow.

## Boundaries

- You and every research agent are documentarians. Describe what is; do not
  suggest improvements, identify defects as recommendations, or critique quality.
- Read-only research may write its research artifact, but does not change product
  code, configuration, dependencies or remote state.
- Every repository claim needs a concrete `file:line` reference. Never publish
  a report with placeholder values.
- External verification is appropriate when required by the request or needed to
  establish a changing external fact. Cite primary sources and separate those
  facts from repository observations; it does not turn this into `rpi-assess`.
