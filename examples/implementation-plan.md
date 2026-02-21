# Plan: Add Rate Limiting to Login Endpoint

**Date:** 2025-12-16
**Research:** `docs/research/2025-12-15-auth-flow.md`
**Estimated phases:** 3

---

## Context

The login endpoint (`POST /api/auth/login`) has no rate limiting. Research confirmed that `src/routes/auth.ts:12` routes directly to `src/auth/login.ts:8` with no middleware protection beyond the standard Express pipeline.

## Design Decision

Use Redis-based sliding window rate limiting (the app already has a Redis dependency for session storage). Apply per-IP and per-email limits to prevent both brute force and credential stuffing.

**Limits:**
- Per-IP: 20 attempts per 15-minute window
- Per-email: 5 attempts per 15-minute window
- On limit exceeded: return `429 Too Many Requests` with `Retry-After` header

## Phases

### Phase 1 — Rate Limiter Core + Tests
**File:** `docs/plans/2025-12-16-rate-limiting-phases/phase-1.md`

```
@ createRateLimiter(key, limit, windowSec) -> RateLimiter
ctx: Redis
pre: Redis connection healthy
do:
  1. compute sliding window key from prefix + timestamp bucket
  2. lookup current count for key (INCR + EXPIRE pattern)
  3. compare count against limit
  4. compute retryAfter from window boundary
br: if count > limit -> return { limited: true, retryAfter }
fx: Redis INCR on key; EXPIRE sets TTL
fail: Redis down -> allow request (fail-open)
risk: clock skew across replicas
```

**Success criteria:**
- Automated:
  - [ ] Unit tests pass: `pnpm test tests/auth/rate-limiter.test.ts`
  - [ ] TypeScript compiles: `pnpm run typecheck`
  - [ ] Linting passes: `pnpm run lint`
- Manual: None

### Phase 2 — Middleware Integration + Tests
**File:** `docs/plans/2025-12-16-rate-limiting-phases/phase-2.md`

```
@ rateLimitMiddleware(req, res, next) -> void
ctx: RateLimiter, req.ip, req.body.email
pre: rate limiter initialized
do:
  1. extract IP from req.ip (trust proxy)
  2. extract email from req.body.email (normalize lowercase)
  3. check IP limiter
  4. check email limiter (only if IP passes)
  5. if either limited -> respond 429 with Retry-After header
  6. call next()
br: if IP limited -> skip email check (save Redis call)
fx: HTTP 429 response; Retry-After header
fail: malformed body -> skip email limit (IP-only)
```

**Success criteria:**
- Automated:
  - [ ] Integration tests pass: `pnpm test tests/integration/rate-limit.test.ts`
  - [ ] All existing auth tests still pass: `pnpm test tests/auth/`
  - [ ] TypeScript compiles: `pnpm run typecheck`
- Manual: None

### Phase 3 — Route Wiring + E2E Verification
**File:** `docs/plans/2025-12-16-rate-limiting-phases/phase-3.md`

```
@ wireRateLimit() -> void
ctx: Express router, rateLimitMiddleware
pre: middleware tested in isolation
do:
  1. import rateLimitMiddleware in src/routes/auth.ts
  2. add as first middleware on POST /api/auth/login route
  3. add rate limit config to src/config/auth.ts (env vars with defaults)
  4. update .env.example with new variables
fx: route now has rate limiting; config externalizes limits
risk: middleware ordering (rate limit must run before body parsing if body-dependent)
```

**Success criteria:**
- Automated:
  - [ ] Full test suite passes: `pnpm test`
  - [ ] Build succeeds: `pnpm run build`
  - [ ] TypeScript compiles: `pnpm run typecheck`
  - [ ] Linting passes: `pnpm run lint`
- Manual: None

## Files to Create

| File | Purpose |
|------|---------|
| `src/auth/rate-limiter.ts` | Sliding window rate limiter using Redis |
| `src/middleware/rate-limit.ts` | Express middleware wrapping the rate limiter |
| `tests/auth/rate-limiter.test.ts` | Unit tests for the rate limiter |
| `tests/integration/rate-limit.test.ts` | Integration tests for the middleware |

## Files to Modify

| File | Change |
|------|--------|
| `src/routes/auth.ts:12` | Add rate limit middleware to login route |
| `src/config/auth.ts` | Add rate limit configuration (limits, window size) |
| `.env.example` | Add `RATE_LIMIT_*` variables |
