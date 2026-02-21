# Pseudocode Notation — Additional Examples

These supplement the single `createOrder` example in `methodology/pseudocode-notation.md`.

---

## Simple CRUD — No Branching

```
@ getUser(userId) -> User
ctx: DB(read)
pre: userId is valid UUID
do:
  1. lookup user by ID
  2. parse row into User type
fail: not found -> throw NotFoundError
```

## Middleware with Early Returns

```
@ authMiddleware(req, res, next) -> void
ctx: JWT verifier, req.headers
pre: Authorization header present
do:
  1. extract token from Authorization header
  2. verify JWT signature and expiry
  3. decode claims (userId, role)
  4. attach claims to req.user
  5. call next()
br: if no header -> 401 Unauthorized; if expired -> 401 TOKEN_EXPIRED
fail: malformed token -> 401 INVALID_TOKEN
```

## Multi-Step with Dependencies Between Steps

```
@ processPayment(orderId, paymentMethod) -> PaymentResult
ctx: DB(tx), stripeSvc, eventBus
pre: order exists; order.status == 'pending'
do:
  1. lookup order with line items (DB)
  2. compute total from line items
  3. create Stripe PaymentIntent(total, paymentMethod)
  4. write payment record with Stripe ID (tx)
  5. update order.status to 'paid' (tx)
  6. emit PaymentCompleted(orderId, paymentId)
br: if Stripe declines -> return PaymentDeclined; if amount mismatch -> abort tx
fx: DB write(payment, order update); Stripe charge; bus emit
fail: Stripe timeout -> retry once; second timeout -> return PaymentFailed
risk: partial commit if event bus fails after DB commit; use outbox pattern
```

## Background Job / Scheduled Task

```
@ runSecurityAudit() -> AuditReport
ctx: npm audit, file system, git
pre: repo is clean (no uncommitted changes)
do:
  1. run dependency audit (npm audit --json)
  2. scan for hardcoded secrets (grep patterns)
  3. check for outdated critical dependencies
  4. compile findings into report sections
  5. write report to docs/agents/security-audit.md
fx: file write (report)
fail: audit command fails -> report partial results with error note
```

## Function with Nested Branching

```
@ resolvePermission(userId, resource, action) -> boolean
ctx: DB(read), permissionCache
pre: userId valid; resource and action are known enums
do:
  1. check cache for (userId, resource, action) tuple
  2. if miss: lookup user roles from DB
  3. lookup role-permission mappings for resource+action
  4. compute effective permission (most permissive role wins)
  5. cache result with 5-min TTL
br: if cached -> return cached value; if no roles -> deny; if admin role -> allow all
fx: cache write on miss
fail: DB down -> deny (fail-closed for permissions)
```

## Migration / Data Transform

```
@ migrateUserEmails() -> MigrationResult
ctx: DB(tx), batchSize=500
pre: migration not already applied (check migrations table)
do:
  1. read users in batches of 500
  2. normalize email to lowercase for each batch
  3. write updated batch (tx per batch)
  4. log progress (batch N of M)
  5. write migration record on completion
br: if email already lowercase -> skip (no-op write)
fx: DB update(users.email); DB write(migration record)
fail: batch fails -> rollback batch tx; report last successful batch
risk: unique constraint violation if two users differ only by case
```
