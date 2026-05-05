# Database migrations

Schema versioning for the `ThaiApp` PostgreSQL database, managed by
[yoyo-migrations](https://ollycope.com/software/yoyo/latest/).

## Conventions

- File naming: `NNNN_short_description.sql` (zero-padded 4-digit prefix).
- Each migration is a plain SQL file. yoyo runs it inside a transaction
  unless the file starts with `-- yoyo: nontransactional`.
- Use `IF NOT EXISTS` / `IF EXISTS` where possible to keep migrations
  idempotent.
- Include both the `up` change and a corresponding rollback. By default
  yoyo treats the whole file as the `up` step; for rollbacks add a
  separate `NNNN_short_description.rollback.sql` next to it.
- Never edit a migration that has already been applied to production.
  Add a new one instead.

## Local usage

```bash
# Install (already in requirements.txt):
pip install yoyo-migrations psycopg2-binary

# Show pending migrations:
yoyo list --database "$DATABASE_URL" ./migrations

# Apply all pending:
yoyo apply --database "$DATABASE_URL" ./migrations

# Roll back the most recent:
yoyo rollback --database "$DATABASE_URL" ./migrations
```

`DATABASE_URL` format:
`postgresql://thai_app_user:PASSWORD@localhost:5432/ThaiApp`

## Initial baseline

`0001_baseline.sql` is a `pg_dump --schema-only` snapshot of production
taken on 2026-05-05. On the production server it has already been
applied (the schema exists), so it is registered as applied without
execution via `yoyo mark`. On a fresh database, running
`yoyo apply` will execute it normally and create the full schema.

See [`docs/adr/0000-database-migrations.md`](../docs/adr/0000-database-migrations.md)
for the rationale.
