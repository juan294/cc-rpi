---
name: "Supabase"
description: "Supabase migration safety, local testing workflow, grant requirements, fallback observability, and health endpoint patterns."
---

# Supabase

## Migration Testing

Wrong -- push migration directly to remote:

```bash
supabase db push  # bug in migration -> production database corrupted
```

Right -- test locally first:

```bash
supabase start                    # requires Docker Desktop
supabase db reset                 # apply all migrations locally
docker exec supabase_db_<project> psql -U postgres -c "SELECT * FROM new_table LIMIT 1;"
supabase db push                  # only after local verification
```

## Table Grants

Wrong -- create table without grants (RLS blocks access):

```sql
CREATE TABLE public.posts (id uuid PRIMARY KEY, title text NOT NULL);
-- Clients get 403: permission denied
```

Right -- include explicit grants:

```sql
CREATE TABLE public.posts (id uuid PRIMARY KEY, title text NOT NULL);
GRANT SELECT ON public.posts TO anon, authenticated;
```

## Default Privileges

Wrong -- grant per-table, forget on future tables:

```sql
GRANT SELECT ON posts TO anon;  -- next table has same bug
```

Right -- set default privileges in initial setup migration:

```sql
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO anon, authenticated;
```

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
