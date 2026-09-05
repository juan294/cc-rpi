# Deployment Safety & Resource Efficiency

Every CI run costs money. Every deployment costs money. Every GitHub Actions minute is billed. Every Vercel build minute is billed. Agents must treat these resources with the same care they would treat production data — deliberately, efficiently, and with justification for every action.

This document codifies the lessons from a real production incident where an agent merged 7 Dependabot PRs directly to `main`, triggered 80+ CI runs and 21 Vercel deployments, and took down a live production site for 2+ hours. The total waste: ~60 unnecessary CI runs, ~15 unnecessary deployments, and hours of owner time on manual recovery.

**Every rule in this document exists because an agent violated it and caused real damage.**

---

## Remote Budget

Keep working branches and worktrees local. Finish applicable tests, coverage,
typechecks, lint, build and deployment preflight locally, resolve failures,
and integrate completed work locally into the documented integration branch.
Inspect workflow and deployment triggers before the single authorized push of
that completed branch. Never create Vercel Preview deployments or publish
working branches/PRs for experimentation. If an integration push would create a
Preview, stop before pushing and use only a documented, non-destructive bypass.
Production publication remains separately and explicitly authorized. Read-only
inspection of existing runs and deployments is allowed.

## Core Principle: Understand the Deployment Topology

Before touching any branch, the agent must understand what happens when code lands on that branch:

- **Which branches trigger deployments?** (`main` almost always deploys to production)
- **Which branches trigger CI?** (most branches trigger CI on push)
- **What platform hosts the deployments?** (Vercel, AWS, Netlify, etc.)
- **Would a push create a Vercel Preview?** If so, stop before the push; use only a documented, non-destructive bypass.
- **What does the CI matrix look like?** (how many workflows run per push?)

If the agent doesn't know the answers, it must check before merging, pushing, or triggering any pipeline.

---

## Rule: Production Branch Actions Require Release Authorization

When the documented topology deploys production from `main`, a merge/push to it is a production action. Some main-only repositories use it only as canonical source; inspect the actual triggers rather than assuming topology.

This means:

- **Dependabot PRs target `main` by default.** Merging them deploys to production immediately.
- **"Clean up the PRs" means close or retarget them** — not merge them to production.
- **The correct workflow for Dependabot:** apply reviewed updates to a local working branch, verify and integrate the combined result locally, then use the authorized release path. Closing/commenting on PRs requires authorization.
- **"Merge the PRs" is never authorization to deploy to production** unless the user explicitly says "deploy to production" or "merge to main."

---

## Rule: Every Action Has a Cost — Justify It First

Before triggering any CI run, deployment, or external API call, answer three questions:

1. **Is this needed?** Can I achieve the same result locally or with fewer runs?
2. **Is this justified?** Does this directly advance the task, or am I guessing?
3. **Is this verifiable?** Will I know if it succeeded or failed, and what to do next?

If the answer to any of these is "no," do not proceed.

### Cost Awareness Checklist

Before starting any task that involves CI or deployments:

- [ ] How many CI runs will this trigger? If more than 2-3, find a more efficient approach.
- [ ] How many deployments will this trigger? If more than 1-2, find a more efficient approach.
- [ ] Can I batch these changes into a single locally integrated change?
- [ ] Can I test this locally before pushing?
- [ ] Am I about to push partial or experimental work to a branch that triggers CI?

---

## Dependency Updates: Batch, Assess Risk, Verify

### Never Merge Dependencies One-by-One

Merging N dependency PRs sequentially on a branch with "require branches to be up-to-date" protection creates an O(n^2) rebase cascade:

- Merge 1 -> rebase remaining N-1 PRs -> each reruns CI
- Merge 2 -> rebase remaining N-2 PRs -> each reruns CI
- Total wasted CI runs: N x (N-1) / 2 x workflows_per_push

For 7 PRs with 9 workflows each, that's ~189 unnecessary workflow runs.

**The correct approach:**

1. Create a single branch (e.g., `chore/dependency-updates`)
2. Cherry-pick or apply all dependency updates to that branch
3. Run the complete applicable local CI-equivalent selection on the combined result
4. Integrate locally; inspect triggers before the single authorized integration push

### Assess Risk Before Merging

Not all dependency updates are equal:

| Risk Level | Examples | Verification Required |
|------------|----------|----------------------|
| **Low** | Dev dependency patches (eslint, prettier) | Complete applicable local gates |
| **Medium** | Runtime library patches/minors (lodash, axios) | Local gates + runtime smoke tests |
| **High** | Framework upgrades (Next.js, React, Vue) | Local gates + runtime/packaging tests + deployment preflight |
| **Critical** | Major version bumps of core frameworks | Full local QA, compatibility review, explicitly authorized release |

**Framework upgrades need runtime evidence as well as build evidence.** Run
local packaging, server startup and request smoke tests plus available deployment
preflight. Existing platform logs/configuration can inform the review. A local
pass cannot prove an unexercised hosted runtime is compatible.

### Vercel: No Preview Deployments

Never create Vercel Previews, including automatic previews from branch pushes.
Inspect triggers before publication. If a push would create one, stop before
pushing and use only the project's documented, non-destructive bypass. Resolve
known failures locally. Record remaining platform-only uncertainty for release
review instead of creating a paid experiment.

---

## Production Incident Recovery Protocol

When production is down, follow this exact sequence. Do not improvise.

### Step 1: Roll Back Immediately

Within the project's explicitly authorized incident procedure, roll back to the last known good deployment before investigating. Rollback is a production action; ordinary implementation authorization does not include it.

```bash
# Vercel: use the dashboard or CLI to promote the last working deployment
vercel rollback  # or promote a specific deployment ID

# Or via the Vercel dashboard: Deployments -> find last working -> Promote to Production
```

### Step 2: Investigate on Non-Production

Once production is stable on the rollback:

- Read Vercel function logs for the error
- Reproduce locally if possible (but remember: local != production)
- Check the deployment platform's runtime behavior specifically

**Never promote a broken deployment "briefly" to capture logs.** That causes another outage. Use the platform's existing log retention and local reproduction. Never create a Preview.

### Step 3: Fix Forward on `develop`

1. Create the fix in a local task-owned branch/worktree
2. Run all applicable local gates and deployment preflight
3. Integrate the complete fix locally and inspect remote triggers
4. Publish only with explicit production authorization
5. Inspect the resulting production deployment without a repeated deployment loop

### Step 4: Count the Cost

Every recovery attempt that fails is another billed deployment and another outage window. Before each recovery action, ask: "Am I confident this will work, or am I guessing?" If guessing, stop and think more.

---

## Resource Efficiency Patterns

### Local First

Always prefer local operations over remote ones:

- Run tests locally before pushing
- Build locally before deploying
- Verify and integrate changes locally; keep working branches and PRs unpublished
- Use `next build` / `npm run build` locally before trusting CI

### Minimize Push Events

Each push event can trigger N workflows. Minimize pushes:

- Squash fixes locally before pushing (avoid push-fix-push-fix cycles)
- Keep feature branches local; publish the completed integration branch once
- Batch multiple changes into single commits when they're related

### Minimize Deployment Events

- Never push to `main` or production branches for testing
- Use local runtime/packaging tests and deployment preflight; never create Vercel Previews
- Don't deploy to diagnose — use logs, local reproduction, or isolated environments
- Count deployments before starting: "This task should take 1 deployment. If I'm at 3, something is wrong."

### Worktree Agents: Commit Locally, Push Centrally

When using parallel worktree agents:

- Agents commit locally only — never push or create PRs
- Main agent reviews all worktrees after completion
- Main agent integrates completed branches locally, verifies, and inspects triggers
- Only the final authorized integration branch is pushed once
- One background agent monitors all CI runs
- See Error #51 for the full pattern

---

## Anti-Patterns (Real Incidents)

### The Rebase Cascade

Agent merges 7 Dependabot PRs one-by-one. Each merge invalidates checks on remaining PRs. Each remaining PR needs a rebase + full CI re-run. Result: 80+ CI runs, 30 of which were pure waste from rebases.

**Fix:** Batch all updates in a local branch, fully verify, and integrate locally.

### The Accidental Production Deploy

Agent told to "clean up Dependabot PRs." Interprets this as "merge them." Dependabot PRs target `main`. Each merge triggers a production deployment. One dependency has a production-only bug. Site goes down.

**Fix:** Understand that merging to `main` = deploying to production. Cherry-pick updates to `develop` instead.

### The Panic Recovery

Production is down. Agent promotes the broken deployment "briefly" to capture logs — site goes down again. Deploys maintenance mode with TypeScript errors — fails. Deploys again with env var issues — fails. Each failed attempt is another billed deployment and another outage window.

**Fix:** Roll back immediately. Investigate on non-production. Fix forward on `develop`. Never improvise recovery.

### The Untested Framework Upgrade

Agent merges Next.js minor version bump after CI passes. Build succeeds, tests pass, local `next start` works. But on Vercel's serverless runtime, a dev-only module is referenced in production build paths. Every serverless function crashes at startup. The bug only manifests on the deployment platform.

**Fix:** Require local runtime and packaging tests plus deployment preflight. Inspect existing platform evidence and disclose remaining platform-only uncertainty; never create a Preview.

---

## Summary of Deployment Rules

| Rule | One-liner |
|------|-----------|
| Topology first | Understand what each branch deploys before merging |
| Production authorization | Follow the documented topology and explicit release authorization |
| Justify actions | Every CI run and deployment must be needed, justified, and verifiable |
| Batch dependencies | Verify a combined local batch before integration |
| Assess risk | Framework upgrades need runtime/packaging tests and preflight |
| No Previews | Block Preview-triggering pushes; use a documented non-destructive bypass |
| Roll back first | When production is down, restore service before investigating |
| Fix forward | Fix and verify locally, then publish the explicitly authorized release |
| Count the cost | Track CI runs and deployments — stop if exceeding estimates |
| Local first | Test locally before pushing; build locally before deploying |
