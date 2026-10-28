# Phangan Events API

Production API for the **VibeRadar Koh Phangan** Telegram Mini App.

Built with FastAPI + asyncpg + PostgreSQL. Hexagonal architecture
(features = vertical slices, shared = cross-cutting domain, core =
composition root). See [ARCHITECTURE.md](ARCHITECTURE.md) for the
full layout.

---

## Quickstart

### Requirements

- Python 3.12+
- PostgreSQL 14+
- (Optional) Mapbox token for road-distance enrichment
- (Optional) Telegram Bot token for `/auth/login` & webhook flows

### Local setup

```bash
git clone <repo> phangan_api
cd phangan_api

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in DB_*, BOT_TOKEN, JWT_SECRET, MAPBOX_TOKEN, …

# apply migrations
psql "$DATABASE_URL" -f migrations/001_init.sql   # adjust to actual files

uvicorn main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health` → `{"status":"ok",…}`.

### Tests

```bash
python -m pytest tests/ -q
```

Note: some unit tests use `dataclass(slots=True)` and require Python 3.10+.
Local Python 3.9 will collect-error those — use the prod venv (3.12) or
upgrade locally.

### Linting / typing

The project relies on standard library tools only. Recommended:

```bash
python -m py_compile $(git ls-files '*.py')   # syntax sweep
python -m pytest tests/ -q                    # unit + integration
```

---

## Project layout

```
core/         composition root: config, DI, error handlers, logging, metrics, security
features/     vertical slices (auth, events, swipes, planner, users, media, bot, translations)
shared/       cross-cutting domain (i18n, telegram, ai, distance, facepile, media, cache)
scripts/      one-off CLIs (avatar backfill, recurrent events, seeders)
tests/        pytest tree mirroring features/ + shared/
migrations/   raw SQL DDL
main.py       app factory & lifespan
```

Each feature follows the same shape:

```
features/<slice>/
  routes.py        FastAPI router (HTTP layer only)
  service.py       use cases (orchestration, no DB)
  repository.py    asyncpg queries (one query per method when possible)
  schemas.py       pydantic request/response models
  builders.py      pure response shapers (when needed)
```

---

## Configuration

All settings live in `core/config.py` (`pydantic-settings`). Read from
`.env` by default. See `.env.example` for the full list. Highlights:

| Var | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Postgres connection |
| `DB_MIN_POOL`, `DB_MAX_POOL` | asyncpg pool sizes |
| `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Auth tokens |
| `BOT_TOKEN`, `WEBHOOK_URL` | Telegram bot wiring |
| `MAPBOX_TOKEN` | Optional — enables road-distance enrichment |
| `PUBLIC_MEDIA_BASE_URL` | Where avatars/media are served from |
| `LOG_LEVEL`, `LOG_FORMAT` | `INFO` / `json` recommended in prod |
| `CORS_ORIGINS` | Comma-separated list |
| `IP_STRIKE_LIMIT` | Throttle threshold for `SecurityMiddleware` |

---

## Operational endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe. Returns `{"status":"ok",…}` |
| `GET /metrics` | Prometheus text exposition (uptime, per-route counters & latency sums) |

`/metrics` is **in-process** — counters reset on restart. It's there for
introspection, not long-term aggregation. For real observability, scrape
it with Prometheus or replace `core/metrics.py` with `prometheus_client`.

---

## Deployment (production)

Prod is the `phangan-api` Docker container on fc-api, built by
`/srv/phangan/api/compose.yml` from `/srv/phangan/api/current`, a symlink
into `releases/<UTC timestamp>` (env in `/srv/phangan/api/env/prod.env`,
media mounted from `/srv/phangan/media`). A release is `git archive` of a
commit, with the hash in `REVISION` — commit first, then:

```bash
scripts/deploy_fc_api.sh          # HEAD; or a ref: scripts/deploy_fc_api.sh 1a2b3c4
```

The script uploads the release, switches `current`, rebuilds and waits for
the container healthcheck. It prints the previous release; to roll back,
point `current` at it and rebuild:

```bash
ssh fc-api "cd /srv/phangan/api && sudo ln -sfn releases/<previous> current \
  && docker compose build api && sudo docker compose up -d api"
```

---

## License

Proprietary. © Phangan team.
