# ADR-0000: Database schema migrations with yoyo-migrations

**Status**: Accepted
**Date**: 2026-05-05
**Context**: Phase 0 of the architectural refactor.

## Context

The `phangan_api` PostgreSQL database (15 tables, ~3 GB of data) was
historically modified by hand on the production server: ad-hoc
`ALTER TABLE` statements via `psql`, no version control of the schema,
no rollback path, and no way to bring up an empty staging database
from code alone. This is a maintenance and onboarding risk.

We need a migration tool that:

1. Versions the schema in the same git repository as the application.
2. Does not require an ORM (we use raw asyncpg in the application).
3. Lets us write plain SQL migrations.
4. Has minimal runtime dependencies and a small operational surface.
5. Plays well with existing tables (so we can adopt it without
   recreating the database).

## Decision

We adopt [yoyo-migrations](https://ollycope.com/software/yoyo/latest/).

- Migration files live in `./migrations/` as `NNNN_<name>.sql`.
- `0001_baseline.sql` is a `pg_dump --schema-only` of the current
  production schema, kept in the repo as the canonical starting point.
- On production, the baseline is registered as already applied with
  `yoyo mark`; yoyo creates the `_yoyo_migration` log table without
  executing the baseline SQL.
- On any fresh database, `yoyo apply ./migrations` reproduces the full
  schema from scratch.
- Deployment runs `yoyo apply` before starting the FastAPI service
  (added to `setup_service.sh` / systemd `ExecStartPre`).

## Alternatives considered

- **Alembic**: standard for SQLAlchemy projects but pulls in an ORM
  dependency we explicitly do not want. Rejected.
- **Sqitch / dbmate / Atlas**: powerful, but external binaries that
  must be installed on every machine. Overkill for this codebase.
- **No migration tool, continue manual `ALTER TABLE`**: keeps the
  existing operational risk; rejected as the entire point of this
  ADR is to remove it.

## Consequences

**Positive**

- Schema changes are reviewable in pull requests.
- Staging and local databases reproduce production schema with one
  command.
- Rollback is a first-class operation (`yoyo rollback`).
- New developers onboard without copying production dumps.

**Negative**

- One additional Python dependency (`yoyo-migrations`,
  `psycopg2-binary`).
- Developers must remember to write a migration instead of running
  `psql` directly. This is enforced by code review and by adding the
  migration step to deployment.
- The baseline file is large (~1200 lines). Future migrations should
  be small and focused.
