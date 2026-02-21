# Research: Authentication Flow

**Date:** 2025-12-15
**Question:** How does the current authentication system work?

---

## Summary

The application uses JWT-based authentication with refresh tokens. Login is handled by `src/auth/login.ts`, tokens are validated by middleware at `src/middleware/auth.ts`, and refresh logic lives in `src/auth/refresh.ts`. Sessions are stored in Redis with a 7-day TTL.

## Findings

### Entry Points

The authentication API exposes three endpoints:

- `POST /api/auth/login` — `src/routes/auth.ts:12` → `src/auth/login.ts:8`
- `POST /api/auth/refresh` — `src/routes/auth.ts:24` → `src/auth/refresh.ts:5`
- `POST /api/auth/logout` — `src/routes/auth.ts:31` → `src/auth/logout.ts:3`

### Token Generation

Tokens are created in `src/auth/tokens.ts:15-42`:
- Access token: 15-minute expiry, contains `userId` and `role` claims
- Refresh token: 7-day expiry, stored in Redis at `src/auth/tokens.ts:38`
- Both use `RS256` signing with keys loaded from environment variables at `src/config/auth.ts:4-8`

### Middleware Chain

Request authentication follows this path (`src/middleware/auth.ts:10-45`):
1. Extract `Authorization` header (`src/middleware/auth.ts:12`)
2. Verify JWT signature (`src/middleware/auth.ts:18`)
3. Check token expiry (`src/middleware/auth.ts:22`)
4. Attach `req.user` with decoded claims (`src/middleware/auth.ts:30`)
5. If expired, return `401` with `TOKEN_EXPIRED` code (`src/middleware/auth.ts:35`)

### Session Storage

Redis is used for refresh token storage (`src/auth/session.ts:5-28`):
- Key pattern: `session:{userId}:{tokenId}` (`src/auth/session.ts:8`)
- TTL: 7 days, matching refresh token expiry (`src/auth/session.ts:12`)
- On logout, the session key is deleted (`src/auth/logout.ts:8`)
- No mechanism exists for invalidating all sessions for a user

### Password Handling

Passwords are hashed with bcrypt at cost factor 12 (`src/auth/password.ts:6`). Comparison uses `bcrypt.compare` at `src/auth/password.ts:14`. No rate limiting exists on the login endpoint.

### Test Coverage

- Unit tests: `tests/auth/login.test.ts` (12 tests), `tests/auth/refresh.test.ts` (8 tests)
- Integration tests: `tests/integration/auth.test.ts` (6 tests)
- No tests found for the logout flow
- No tests found for token expiry edge cases

## Related Files

| Category | Files |
|----------|-------|
| Implementation | `src/auth/login.ts`, `src/auth/refresh.ts`, `src/auth/logout.ts`, `src/auth/tokens.ts`, `src/auth/session.ts`, `src/auth/password.ts` |
| Middleware | `src/middleware/auth.ts` |
| Routes | `src/routes/auth.ts` |
| Config | `src/config/auth.ts` |
| Tests | `tests/auth/login.test.ts`, `tests/auth/refresh.test.ts`, `tests/integration/auth.test.ts` |
| Types | `src/types/auth.ts` |

## Open Questions

- What is the intended behavior when a refresh token is used after the session is deleted from Redis? (Currently returns a generic 401.)
- Is the absence of login rate limiting intentional?
