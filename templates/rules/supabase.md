---
description: Supabase migration safety -- local testing, GRANTs, fallback logging, health checks
paths:
  - supabase/**
  - "**/*.sql"
  - "**/migrations/**"
---

# Supabase Rules

## Migration Rules

- Every migration creating a public-facing table must
  include explicit grants:
  `GRANT SELECT ON table_name TO anon, authenticated;`
- Add `ALTER DEFAULT PRIVILEGES` in initial setup migration
  so future tables get anon SELECT automatically.

## Fallback Observability

- If a query fails and code falls back to defaults,
  log `[TABLE_FALLBACK]` at ERROR -- not INFO.
- Health endpoints must check actual data access,
  not just connectivity.
  Return `"degraded"` if primary tables are inaccessible.

## Migration Safety

Test migrations locally before pushing to remote:

1. `supabase start` (requires Docker Desktop)
2. `supabase db reset` (apply all migrations locally)
3. `docker exec supabase_db_<project> psql -U postgres`
   `-c "<verification query>"`
4. Only after local verification: `supabase db push`

Container name: `supabase_db_<project>` from
`supabase/config.toml`. Never push without local testing.

For full migration procedures, see the supabase skill.
