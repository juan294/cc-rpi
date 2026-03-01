# Workflow: Refactoring Existing Code

A step-by-step walkthrough of refactoring existing code using the full RPI cycle. This example extracts authentication logic from scattered Express middleware into a dedicated service — a structural change that touches many files.

---

## The scenario

Your API has grown. Authentication logic is spread across three places: an auth middleware, inline checks in route handlers, and a utility file with token helpers. You want to consolidate everything into a clean auth service. This is the kind of change where "just start refactoring" leads to broken imports, missed edge cases, and hours of debugging.

---

## Step 1: Research what exists

Refactoring is where research matters most. You need a complete map of what exists before moving anything. Open a fresh Claude Code session:

```
You: /research map all authentication and authorization logic in the codebase.
     I want to know every file that handles auth, what each one does, how they
     connect, and where the boundaries are unclear.
```

The agent explores thoroughly:

```
Claude: Researching authentication across your codebase...

[locator agent: finding all files with auth-related code]
[analyzer agent: tracing the auth flow from request to response]
[pattern agent: finding inconsistencies and duplication]

Research saved to docs/research/2026-02-22-auth-landscape.md

Key findings:

Auth logic lives in 3 places:
1. src/middleware/auth.ts (lines 12-58)
   - JWT verification, token extraction from headers
   - Attaches user object to req
   - Used by 14 routes

2. src/routes/admin.ts (lines 23-31, 45-52, 78-85)
   - Inline role checks: if (req.user.role !== 'admin')
   - Duplicated in 3 route handlers
   - Inconsistent error responses (sometimes 401, sometimes 403)

3. src/utils/token.ts
   - generateToken(), verifyToken(), refreshToken()
   - verifyToken() duplicates logic already in auth middleware
   - refreshToken() has a subtle bug: doesn't check token expiry
     before refreshing (line 34)

Dependencies:
- auth middleware imported by: src/routes/admin.ts, src/routes/users.ts,
  src/routes/todos.ts, src/routes/settings.ts
- token utils imported by: auth middleware, src/routes/auth.ts (login/register)
- JWT secret loaded from env in 2 different places (middleware and utils)

Full file:line references in the research document.
```

**Read the research carefully.** This is where you discover things you didn't know — like the inconsistent 401/403 responses and the refresh token bug. These need to be addressed in the refactor plan.

```
You: This is really useful. I didn't know about the refresh token bug.
     The research is accurate — proceed to planning.
```

---

## Step 2: Plan the refactor

New conversation. Clean context:

```
You: /plan refactor all auth logic into a dedicated AuthService.
     Research at docs/research/2026-02-22-auth-landscape.md.
     Also fix the refresh token bug and the inconsistent 401/403 responses
     found during research.
```

The agent reads the research and designs the refactor:

```
Claude: I've read the research. Here's what I'm proposing:

Design decision: AuthService as a class or as pure functions?
- Class: holds config (JWT secret, expiry), easier to mock in tests
- Pure functions: simpler, but config has to be passed everywhere

Which do you prefer?
```

```
You: Class. We can instantiate it once and inject it where needed.
```

```
Claude: Plan saved to docs/plans/2026-02-22-auth-refactor.md

3 phases:
- Phase 1: Create AuthService class with all token and verification logic.
  Write tests FIRST (TDD). No changes to existing code yet.
- Phase 2: Migrate middleware and routes to use AuthService. Replace inline
  role checks with AuthService.requireRole(). Fix 401/403 inconsistency.
- Phase 3: Fix refresh token bug, remove old utils/token.ts, clean up
  dead imports. Final integration tests.

Key principle: Phase 1 adds the new code alongside the old code.
Phase 2 switches over. Phase 3 removes the old code.
Nothing breaks between phases.
```

**This is the critical review.** Check:
- Does the phasing make sense? (New code first, migration second, cleanup third)
- Will anything break between phases? (It shouldn't — old code stays until Phase 3)
- Are the role check replacements covering all 3 duplicated locations?
- Does the refresh token fix match what you'd expect?

```
You: Solid plan. One addition to Phase 2: when you migrate the role checks,
     add a requireRole middleware factory instead of checking inside each
     handler. router.get('/users', auth, requireRole('admin'), handler)
     — that pattern.
```

```
Claude: Updated. Phase 2 now includes a requireRole() middleware factory
that wraps AuthService.checkRole(). Cleaner route definitions.
```

---

## Step 3: Implement phase by phase

New conversation:

```
You: /implement docs/plans/2026-02-22-auth-refactor.md
```

```
Claude: Reading the plan... Starting Phase 1: Create AuthService (TDD)

Writing tests first...
[creates src/services/__tests__/authService.test.ts]
[tests: token generation, verification, refresh, role checking, expiry handling]

Tests written. Running them — they should all FAIL (red phase):
- [x] 11 tests, 11 failing (AuthService doesn't exist yet)

Now implementing to make them pass...
[creates src/services/authService.ts]
[implements AuthService class]
[reviewer: plan compliance PASS]
[/simplify: clean]
[runs tests]

Phase 1 complete:
- [x] AuthService class with: generateToken, verifyToken, refreshToken,
  extractFromHeader, checkRole, requireRole middleware factory
- [x] JWT secret loaded from config in one place
- [x] 11 tests, all passing (green phase)
- [x] Existing code untouched — old auth still works
- [x] TypeScript compiles, lint clean

Ready for Phase 2?
```

At this point you can verify: the new AuthService exists alongside the old code. Nothing is broken. You can even import it manually and test it.

```
You: Tests look thorough. Continue.
```

```
Claude: Starting Phase 2: Migrate middleware and routes to AuthService

[rewrites src/middleware/auth.ts to use AuthService.verifyToken()]
[replaces inline role checks in admin.ts with requireRole('admin')]
[fixes 401/403: unauthorized = 401, forbidden (wrong role) = 403]
[updates imports in all 4 route files]
[reviewer: plan compliance PASS]
[/simplify: found duplicated error response construction in 2 route files. Fixed.]
[runs full test suite]

Phase 2 complete:
- [x] auth middleware now delegates to AuthService
- [x] 3 inline role checks replaced with requireRole() middleware
- [x] Consistent responses: 401 for missing/invalid token, 403 for wrong role
- [x] Route definitions cleaner: router.get('/users', auth, requireRole('admin'), handler)
- [x] /simplify: 1 fix applied (error response reuse)
- [x] All existing tests still pass (38 tests)
- [x] 4 new tests for role middleware and error responses

Ready for Phase 3?
```

```
You: The 401/403 split is exactly right. Continue.
```

```
Claude: Starting Phase 3: Fix refresh token bug + cleanup

[fixes refreshToken: now checks expiry before refreshing]
[deletes src/utils/token.ts — all logic now in AuthService]
[removes dead imports from auth.ts and auth routes]
[adds regression test for the refresh token expiry bug]
[reviewer: plan compliance PASS]
[/simplify: flagged unused error type export from old token.ts re-export. Removed.]
[runs full test suite]

Phase 3 complete:
- [x] Refresh token bug fixed (rejects expired tokens before refreshing)
- [x] Regression test: expired token refresh returns 401
- [x] src/utils/token.ts deleted
- [x] No dead imports remaining
- [x] /simplify: 1 fix applied (stale re-export cleanup)
- [x] Full suite: 45 tests, all passing
- [x] TypeScript compiles, lint clean

All phases complete.
```

---

## Step 4: Validate

```
You: /validate docs/plans/2026-02-22-auth-refactor.md
```

```
Claude: Running validation...

- [x] Phase 1: AuthService exists with full test coverage
- [x] Phase 2: All routes migrated, no inline role checks remaining
- [x] Phase 3: Old token utils removed, refresh bug fixed
- [x] TypeScript: No errors
- [x] Lint: Clean
- [x] Tests: 45/45 passing
- [x] No references to old utils/token.ts anywhere in codebase
- [x] grep for inline role checks: 0 results

Suggestion: manually test the refresh token flow with an expired token
to confirm the fix works end-to-end through the HTTP layer.

Verdict: All plan objectives achieved.
```

---

## Step 5: PR

```
You: /describe-pr
```

```
Claude: PR created → https://github.com/yourname/my-api/pull/15
```

---

## Why the RPI cycle matters more for refactoring

Refactoring is the riskiest type of change for AI agents. Without structure:

- The agent tries to do everything at once — rewrite, migrate, and clean up in a single pass. One mistake cascades everywhere.
- No research phase means the agent misses things. It might not find the 3 duplicated role checks or the refresh token bug. You'd discover those later, after the refactor is "done."
- No phased approach means there's no safe rollback point. With RPI, after Phase 1, the old code still works. After Phase 2, you can verify the migration before removing anything. Phase 3 is just cleanup — the risky work is already done.

The research document is especially valuable here. It becomes a map of the territory you're refactoring. If the map is wrong, throw it out and research again — that's 5 minutes. If the refactor is wrong, you're reverting commits and starting over — that's hours.
