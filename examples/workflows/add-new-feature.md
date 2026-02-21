# Workflow: Adding a New Feature

A step-by-step walkthrough of adding a feature to an existing project using the full RPI cycle. This example adds rate limiting to a REST API that's already in production.

---

## The scenario

You have a Node.js/Express API that's been running for a few weeks. Users are hitting the login endpoint too aggressively and you need rate limiting. The project was set up with cc-rpi, so CLAUDE.md and all slash commands are in place.

---

## Step 1: Research the codebase

Before planning anything, understand what exists today. Open a fresh Claude Code session:

```
You: /research how does our API handle requests currently? I want to understand
     the middleware chain, error handling, and any existing rate limiting or
     throttling before I add rate limiting to the login endpoint.
```

The agent spawns parallel subagents to explore:

```
Claude: Researching your codebase...

[locator agent: finding middleware, routes, auth files]
[analyzer agent: understanding the request lifecycle]
[pattern agent: checking for existing throttling or rate-limiting code]

Research saved to docs/research/2026-02-22-request-handling.md

Key findings:
- Request lifecycle: cors → bodyParser → authMiddleware → routes → errorHandler
- No existing rate limiting or throttling anywhere in the codebase
- Auth middleware at src/middleware/auth.ts validates JWT on protected routes
- Login endpoint at src/routes/auth.ts — no protection against brute force
- Error handling is centralized in src/middleware/errorHandler.ts
- Express app created in src/app.ts, middleware registered in order

Full details with file:line references in the research document.
```

**Your job: read the research document.** Open `docs/research/2026-02-22-request-handling.md` and verify it accurately describes your codebase. If something's wrong or missing, say so — the agent will re-research.

```
You: Looks accurate. One thing — we also have a Redis instance running for
     session storage. That's relevant since rate limiters can use Redis as
     a backing store.
```

```
Claude: Good catch. I'll note that for the planning phase — Redis at
redis://localhost:6379 configured in src/config/redis.ts.
```

---

## Step 2: Plan the feature

Start a **new conversation** (`/clear` or open a fresh terminal). Clean context for planning:

```
You: /plan add rate limiting to the login endpoint. Research is at
     docs/research/2026-02-22-request-handling.md — we have Redis available.
```

The agent reads the research, explores additional context, and asks focused questions:

```
Claude: I've read the research. The middleware chain and Redis setup are clear.
A few decisions:

1. Rate limit strategy — per-IP, per-user, or both?
2. Limits — how many login attempts before blocking? What cooldown period?
3. Response — return 429 with retry-after header, or something custom?
4. Scope — just the login endpoint now, or set up infrastructure for
   rate limiting other endpoints later?
```

```
You: Per-IP for now. 5 attempts per 15-minute window. Standard 429 with
     retry-after. Set up the infrastructure so we can easily add other
     endpoints later.
```

The agent writes the plan:

```
Claude: Plan saved to docs/plans/2026-02-22-rate-limiting.md

2 phases:
- Phase 1: Rate limiting infrastructure (Redis-backed limiter, middleware
  factory, configuration)
- Phase 2: Apply to login endpoint + integration tests

Success criteria per phase documented. Ready to review?
```

**Read the plan carefully.** This is where you check:
- Does the middleware factory design make sense for reuse?
- Is the Redis key structure reasonable?
- Are the tests covering the right scenarios (under limit, at limit, over limit, cooldown expiry)?

```
You: Phase 1 looks good. In Phase 2, also add a test for when Redis is
     unavailable — the endpoint should still work, just without rate limiting.
     Don't block users because Redis is down.
```

```
Claude: Updated. Added a fail-open test case to Phase 2 — when Redis is
unreachable, requests pass through without rate limiting.
```

---

## Step 3: Implement

New conversation again. Clean context:

```
You: /implement docs/plans/2026-02-22-rate-limiting.md
```

```
Claude: Reading the plan... Starting Phase 1: Rate limiting infrastructure

[creates src/middleware/rateLimiter.ts — factory function]
[creates src/config/rateLimits.ts — centralized config]
[adds ioredis to dependencies]
[writes unit tests for the middleware factory]
[runs typecheck, lint, tests]

Phase 1 complete:
- ✅ rateLimiter middleware factory created
- ✅ Redis-backed sliding window counter
- ✅ Fail-open behavior when Redis is unavailable
- ✅ Configurable limits per route
- ✅ 6 unit tests passing
- ✅ TypeScript compiles, lint clean

Ready for Phase 2?
```

```
You: Good. Continue.
```

```
Claude: Starting Phase 2: Apply to login endpoint + integration tests

[adds rate limiter to login route in src/routes/auth.ts]
[writes integration tests with supertest + redis mock]
[runs full test suite]

Phase 2 complete:
- ✅ Login endpoint rate limited: 5 attempts / 15 min per IP
- ✅ Returns 429 with Retry-After header when exceeded
- ✅ Fail-open test: works when Redis is down
- ✅ 4 new integration tests (under/at/over limit + Redis failure)
- ✅ Full suite: 47 tests, all passing

All phases complete.
```

---

## Step 4: Validate

```
You: /validate docs/plans/2026-02-22-rate-limiting.md
```

```
Claude: Running validation...

- ✅ Phase 1: All success criteria met
- ✅ Phase 2: All success criteria met
- ✅ TypeScript: No errors
- ✅ Lint: Clean
- ✅ Tests: 47/47 passing
- ✅ Rate limiter factory is reusable for other endpoints
- ✅ Fail-open behavior verified

One note: You may want to manually test the 429 response format
matches what your frontend expects. The integration tests verify
the status code and header but not the response body rendering.

Verdict: All plan objectives achieved.
```

---

## Step 5: PR and push

```
You: /describe-pr
```

```
Claude: PR description generated. Creating PR...

→ https://github.com/yourname/my-api/pull/12
```

The agent monitors CI after pushing. If CI fails, it investigates and fixes without you needing to intervene.

---

## What made this different from "just asking Claude to add rate limiting"

If you'd said "add rate limiting to my login endpoint" without the methodology:

- The agent would jump straight to code, possibly missing the existing Redis setup
- No persistent research document — if the approach fails, you start from scratch
- No phased implementation — everything gets built at once, harder to catch issues mid-stream
- No explicit fail-open decision — the agent might default to fail-closed, blocking users when Redis goes down
- No validation against a plan — you'd eyeball the code instead of checking against documented criteria

With the RPI cycle, you spent your time on decisions that matter (per-IP vs per-user, fail-open vs fail-closed, reusable infrastructure vs one-off) and the agent handled everything else within guardrails you approved.
