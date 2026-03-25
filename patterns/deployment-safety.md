# Deployment Safety & Resource Efficiency

Every CI run costs money. Every deployment costs money. Every GitHub Actions minute is billed. Every Vercel build minute is billed. Agents must treat these resources with the same care they would treat production data — deliberately, efficiently, and with justification for every action.

This document codifies the lessons from a real production incident where an agent merged 7 Dependabot PRs directly to `main`, triggered 80+ CI runs and 21 Vercel deployments, and took down a live production site for 2+ hours. The total waste: ~60 unnecessary CI runs, ~15 unnecessary deployments, and hours of owner time on manual recovery.

**Every rule in this document exists because an agent violated it and caused real damage.**

---

## Core Principle: Understand the Deployment Topology

Before touching any branch, the agent must understand what happens when code lands on that branch:

- **Which branches trigger deployments?** (`main` almost always deploys to production)
- **Which branches trigger CI?** (most branches trigger CI on push)
- **What platform hosts the deployments?** (Vercel, AWS, Netlify, etc.)
- **Is there a staging/preview environment?** (Vercel preview URLs, staging servers)
- **What does the CI matrix look like?** (how many workflows run per push?)

If the agent doesn't know the answers, it must check before merging, pushing, or triggering any pipeline.

---

## Rule: Merging to `main` IS Deploying to Production

In any project with CI/CD connected to `main`, a merge to `main` is a production deployment. There is no distinction between "merging a PR" and "deploying to production." They are the same action.

This means:

- **Dependabot PRs target `main` by default.** Merging them deploys to production immediately.
- **"Clean up the PRs" means close or retarget them** — not merge them to production.
- **The correct workflow for Dependabot:** cherry-pick updates to `develop`, close the Dependabot PR, release via the normal `develop` -> `main` process.
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
- [ ] Can I batch these changes into a single PR instead of multiple?
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
3. Run CI once on the combined result
4. Merge the single PR

### Assess Risk Before Merging

Not all dependency updates are equal:

| Risk Level | Examples | Verification Required |
|------------|----------|----------------------|
| **Low** | Dev dependency patches (eslint, prettier) | CI passing is sufficient |
| **Medium** | Runtime library patches/minors (lodash, axios) | CI + local smoke test |
| **High** | Framework upgrades (Next.js, React, Vue) | CI + platform preview deployment + manual verification |
| **Critical** | Major version bumps of core frameworks | Full QA cycle, staged rollout |

**Framework upgrades (Next.js, React, etc.) must never be merged without testing on the actual deployment platform.** CI passing is necessary but NOT sufficient. Build success does not equal runtime success. Local success does not equal production success.

### Vercel-Specific: Preview Before Production

For Vercel-hosted projects:

1. Deploy the dependency update to a preview URL (push to a non-main branch)
2. Verify the preview deployment: site loads, API routes respond, health checks pass
3. Only after preview verification succeeds, merge to `main`

A production-only bug (like a missing module that only manifests on Vercel's serverless runtime) will not be caught by local testing or CI. The preview deployment is the only safety net.

---

## Production Incident Recovery Protocol

When production is down, follow this exact sequence. Do not improvise.

### Step 1: Roll Back Immediately

Roll back to the last known good deployment. Do not investigate first. Do not "try one more thing." The priority is restoring service.

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

**Never promote a broken deployment "briefly" to capture logs.** That causes another outage. Use the platform's log retention, or deploy to a preview URL to reproduce the error.

### Step 3: Fix Forward on `develop`

1. Create the fix on `develop` (or a feature branch)
2. Test locally
3. Deploy to a preview URL and verify
4. Only after preview verification, create a PR to `main`
5. Merge and verify the production deployment

### Step 4: Count the Cost

Every recovery attempt that fails is another billed deployment and another outage window. Before each recovery action, ask: "Am I confident this will work, or am I guessing?" If guessing, stop and think more.

---

## Resource Efficiency Patterns

### Local First

Always prefer local operations over remote ones:

- Run tests locally before pushing
- Build locally before deploying
- Verify changes locally before creating PRs
- Use `next build` / `npm run build` locally before trusting CI

### Minimize Push Events

Each push event can trigger N workflows. Minimize pushes:

- Squash fixes locally before pushing (avoid push-fix-push-fix cycles)
- Use `--amend` and `--force-push` on feature branches (not main) to avoid extra CI runs
- Batch multiple changes into single commits when they're related

### Minimize Deployment Events

- Never push to `main` or production branches for testing
- Use preview/staging environments for verification
- Don't deploy to diagnose — use logs, local reproduction, or isolated environments
- Count deployments before starting: "This task should take 1 deployment. If I'm at 3, something is wrong."

### Worktree Agents: Commit Locally, Push Centrally

When using parallel worktree agents:

- Agents commit locally only — never push or create PRs
- Main agent reviews all worktrees after completion
- Main agent batch-pushes all branches in one command
- One background agent monitors all CI runs
- See Error #51 for the full pattern

---

## Anti-Patterns (Real Incidents)

### The Rebase Cascade

Agent merges 7 Dependabot PRs one-by-one. Each merge invalidates checks on remaining PRs. Each remaining PR needs a rebase + full CI re-run. Result: 80+ CI runs, 30 of which were pure waste from rebases.

**Fix:** Batch all updates into a single branch and PR.

### The Accidental Production Deploy

Agent told to "clean up Dependabot PRs." Interprets this as "merge them." Dependabot PRs target `main`. Each merge triggers a production deployment. One dependency has a production-only bug. Site goes down.

**Fix:** Understand that merging to `main` = deploying to production. Cherry-pick updates to `develop` instead.

### The Panic Recovery

Production is down. Agent promotes the broken deployment "briefly" to capture logs — site goes down again. Deploys maintenance mode with TypeScript errors — fails. Deploys again with env var issues — fails. Each failed attempt is another billed deployment and another outage window.

**Fix:** Roll back immediately. Investigate on non-production. Fix forward on `develop`. Never improvise recovery.

### The Untested Framework Upgrade

Agent merges Next.js minor version bump after CI passes. Build succeeds, tests pass, local `next start` works. But on Vercel's serverless runtime, a dev-only module is referenced in production build paths. Every serverless function crashes at startup. The bug only manifests on the deployment platform.

**Fix:** Framework upgrades require preview deployment verification. CI passing != production working.

---

## Summary of Deployment Rules

| Rule | One-liner |
|------|-----------|
| Topology first | Understand what each branch deploys before merging |
| Main = production | Merging to `main` is always a production deployment |
| Justify actions | Every CI run and deployment must be needed, justified, and verifiable |
| Batch dependencies | Never merge dependency PRs one-by-one — batch into a single PR |
| Assess risk | Framework upgrades need preview verification; dev patches need CI only |
| Preview before prod | Deploy to preview URL and verify before merging to `main` |
| Roll back first | When production is down, restore service before investigating |
| Fix forward | Create fixes on `develop`, verify on preview, then release to `main` |
| Count the cost | Track CI runs and deployments — stop if exceeding estimates |
| Local first | Test locally before pushing; build locally before deploying |
