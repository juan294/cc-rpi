# Phase 1 — Rate Limiter Core + Tests

**Plan:** `docs/plans/2025-12-16-rate-limiting.md`

## TDD Steps

### Red — Write Failing Tests First

Create `tests/auth/rate-limiter.test.ts`:

1. Test: allows requests under the limit
2. Test: blocks requests at the limit
3. Test: resets after window expires
4. Test: returns correct `retryAfter` value
5. Test: fail-open when Redis is unavailable
6. Test: handles concurrent increments correctly

Use a real Redis test instance (not mocks) for accuracy.

### Green — Implement `src/auth/rate-limiter.ts`

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

Implementation notes:
- Use `MULTI/EXEC` for atomic INCR + EXPIRE (`src/auth/rate-limiter.ts`)
- Key format: `ratelimit:{prefix}:{Math.floor(Date.now() / (windowSec * 1000))}`
- Export a factory function, not a class — matches existing patterns in `src/auth/session.ts:5`

### Refactor

- Extract Redis key generation if shared with session storage
- Ensure consistent error handling with existing patterns in `src/auth/tokens.ts:40-42`

## Verification

```bash
pnpm test tests/auth/rate-limiter.test.ts
pnpm run typecheck
pnpm run lint
```

## Checklist

- [ ] All 6 tests written and failing (Red)
- [ ] `src/auth/rate-limiter.ts` implemented (Green)
- [ ] All 6 tests passing
- [ ] TypeScript compiles
- [ ] Linting passes
- [ ] Refactoring done with green tests
