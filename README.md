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

The prod box (Ubuntu) runs `phangan-api.service` (systemd) on port 62537.
The directory `/home/ubuntu/Phangan/phangan_api` is **not** a git repo —
deploys are by `rsync`. Standard flow:

```bash
# 1. Backup
ssh -p 42537 ubuntu@<host> \
  "cd /home/ubuntu/Phangan && tar --exclude='phangan_api/venv' \
     --exclude='phangan_api/media' \
     -czf phangan_api_backup_$(date +%Y%m%d_%H%M%S).tar.gz phangan_api/"

# 2. Sync (NB: anchor /media/ to top level — do NOT exclude '*/media/')
rsync -avz --delete \
  --exclude='__pycache__/' --exclude='.git/' --exclude='.pytest_cache/' \
  --exclude='/venv/' --exclude='/media/' --exclude='.env' \
  -e 'ssh -p 42537' \
  features/ shared/ core/ main.py scripts/ \
  ubuntu@<host>:/home/ubuntu/Phangan/phangan_api/

# 3. Smoke-test on prod
ssh -p 42537 ubuntu@<host> \
  "cd /home/ubuntu/Phangan/phangan_api && \
   venv/bin/python -c 'from main import app; print(len(app.routes))' && \
   venv/bin/python -m pytest tests/ -q"

# 4. Restart
ssh -p 42537 ubuntu@<host> "sudo systemctl restart phangan-api && \
  systemctl is-active phangan-api"

# 5. Verify
curl https://api.fastpump.fun/health
```

---

## License

Proprietary. © Phangan team.
