# Examples

Sample documents and workflow walkthroughs illustrating the RPI methodology in practice. These are reference patterns — adapt structure and depth to your project's needs.

## Artifact Samples

What the outputs of each phase look like:

| File | Illustrates |
|------|------------|
| `research-document.md` | Research phase output: descriptive, no opinions, file:line references |
| `implementation-plan.md` | Plan phase output: phases, pseudocode notation, success criteria |
| `implementation-plan-phases/` | Per-phase detail files referenced by the plan |
| `error-log.md` | Error log entry: root cause analysis focused on user skill |
| `success-log.md` | Success log entry: what worked and why it's repeatable |
| `pseudocode-examples.md` | Additional pseudocode notation examples beyond the single one in the methodology |

## Workflow Walkthroughs

End-to-end examples showing how a developer interacts with the methodology. Each walkthrough shows the exact commands, the agent's responses, and where the developer makes decisions:

| File | Scenario |
|------|----------|
| `workflows/bootstrap-new-project.md` | Setting up a new project from scratch with `/bootstrap`, then building the first feature with `/plan` and `/implement` |
| `workflows/add-new-feature.md` | Adding rate limiting to an existing API using the full `/research` → `/plan` → `/implement` → `/validate` cycle |
| `workflows/refactor-existing-code.md` | Refactoring scattered auth logic into a dedicated service — where the phased approach prevents cascading breakage |
