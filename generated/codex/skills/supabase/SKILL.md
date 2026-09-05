---
name: "supabase"
description: "Supabase migration safety, local testing workflow, grant requirements, fallback observability, and health endpoint patterns."
---

# Supabase

## Migration Testing

Use a disposable local stack. `db reset --local` destroys local data, so first
confirm it is task-owned or preserve that data. Never reset a shared stack.

```bash
supabase start
supabase db reset --local
supabase status
# Use the reported local connection string to run role-based SQL tests:
psql "$LOCAL_DB_URL" -v ON_ERROR_STOP=1 -f tests/access.sql
```

Test anonymous access, the authenticated owner, a different authenticated
user, and the service role. Include intentional denials and a future table.
A query as `postgres` bypasses RLS and cannot validate client authorization.
Local success is necessary but does not guarantee the remote schema, roles,
extensions, or data match. `supabase db push` is a separate remote application
requiring local evidence, target inspection, and production authorization
when applicable; it is never part of the local test command.

## Table Privileges and Row Level Security

SQL grants allow operations on objects; RLS policies constrain which rows an
allowed operation can access. Both must express the project's intended access.
For owner-only notes (not public content):

```sql
CREATE TABLE public.notes (id uuid PRIMARY KEY, owner_id uuid NOT NULL, body text);
ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.notes FROM anon, authenticated;
GRANT SELECT ON public.notes TO authenticated;
CREATE POLICY notes_read_own ON public.notes FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = owner_id);
```

Here anon has no SELECT grant; an authenticated owner can read their own rows,
and another authenticated user sees none of those rows. Add write grants and
policies only when required, including `WITH CHECK` for allowed inserts or
updates. Existing projects intentionally serving public data may grant anon
SELECT with an explicit public-read policy; preserve that contract and any
owner-only overrides. See [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Default Privileges

Do not grant anon access to every future table by default. Inspect inherited,
existing, global and per-schema grants for the actual migration owner. For an
owner with broad defaults, revoke both applicable scopes before creating
private tables:

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
```

These commands affect future objects created by the named role, not existing
tables or objects created by other roles. A per-schema revoke cannot undo a
global default grant. Use a dedicated schema/default grant only for deliberately
public data, and test that a future private table remains inaccessible.
See [PostgreSQL default privileges](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html).

## Fallback Observability

Wrong -- silent fallback hides production bug:

```typescript
if (error) return DEFAULT_POSTS;  // nobody knows
```

Right -- log at ERROR level when fallback activates:

```typescript
if (error) {
  console.error('[TABLE_FALLBACK] posts query failed:', error.message);
  return DEFAULT_POSTS;
}
```

## Health Endpoints

Wrong -- health check only tests connectivity:

```typescript
app.get('/health', async () => {
  await supabase.from('posts').select('count');
  return { status: 'healthy' };  // doesn't detect degraded state
});
```

Right -- check actual data access:

```typescript
app.get('/health', async () => {
  const { data, error } = await supabase.from('posts').select('id').limit(1);
  if (error) return { status: 'degraded', reason: error.message };
  return { status: 'healthy' };
});
```
