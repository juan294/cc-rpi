# Error Log Entry

## What Happened

Asked Claude to "add validation to the API" without specifying which endpoints or what validation rules. Claude added input validation to all 14 endpoints, including internal-only ones that already had upstream validation, resulting in duplicate checks and 3 broken integration tests.

## Primary Cause

**Prompt Error: Ambiguous instruction**

## The Exact Triggering Prompt

> Add input validation to the API. Make sure all endpoints validate their inputs properly.

## What Was Wrong With the Prompt

- "The API" is 14 endpoints — no scoping to specific ones
- "Properly" is undefined — no validation rules specified
- No mention of which endpoints are public vs internal
- No success criteria for what "validated" means

## What the User Should Have Said Instead

> Add Zod validation schemas to the 3 public-facing endpoints: POST /api/users, POST /api/orders, and PATCH /api/orders/:id. Validate request body shape and types only — don't add business logic validation. Write tests first. Don't modify internal endpoints (src/routes/internal/) — they're validated upstream by the API gateway.

## The Gap

| Expected | Got | Why |
|----------|-----|-----|
| Validation on 3 public endpoints | Validation on all 14 endpoints | Prompt said "all endpoints" |
| Leave internal endpoints alone | Duplicate validation on internal routes | No exclusion specified |
| Zod schemas matching existing patterns | Mix of Zod and manual checks | No pattern reference given |

## Prevention Action Items

1. Always scope API changes to specific endpoints by path
2. Reference existing validation patterns when they exist
3. Explicitly exclude areas that should not be touched
4. Define "done" with concrete criteria, not adjectives like "properly"

## One-Line Lesson

Scope API changes to specific endpoint paths and exclude what shouldn't be touched.
