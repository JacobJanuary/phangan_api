# Architecture

Phangan API is structured as **hexagonal / ports-and-adapters**, organized
as **vertical slices** per feature. The intent is to keep HTTP, domain
logic, and persistence cleanly separated, while letting each feature own
its full stack from route to SQL.

---

## Three layers

```
┌──────────────────────────────────────────────────────────────────┐
│  features/  ─ vertical slices (HTTP → use case → SQL per slice)  │
│    auth · events · swipes · planner · users · media · bot · i18n │
├──────────────────────────────────────────────────────────────────┤
│  shared/    ─ cross-cutting domain (ports + adapters + services) │
│    i18n · telegram · ai · distance · facepile · media · cache    │
├──────────────────────────────────────────────────────────────────┤
│  core/      ─ composition root                                   │
│    config · dependencies · error_handlers · logging · metrics    │
│    middlewares · security                                        │
└──────────────────────────────────────────────────────────────────┘
                          ↑
                     main.py wires everything in lifespan
```

### `features/` — vertical slices

Each slice owns one logical capability end-to-end. A typical slice has:

| File | Responsibility |
|---|---|
| `routes.py` | FastAPI router. **HTTP only**: parse query/body, call service, return response. No SQL, no business logic. |
| `service.py` | Use cases. Orchestrates repositories + shared services. **Stateless** dataclass. |
| `repository.py` | Persistence. One asyncpg query per public method when possible. Returns rows / domain dataclasses, never HTTP types. |
| `schemas.py` | Pydantic models for request/response. |
| `builders.py` | Pure helpers that shape response dicts (when shaping is non-trivial). Easy to unit-test. |

Slices may import from `shared/` and `core/`, but **must not import from
sibling slices**. If two slices need the same logic, lift it into `shared/`.

### `shared/` — cross-cutting domain

Stable building blocks. Each subpackage typically has:

| File | Responsibility |
|---|---|
| `ports.py` | `Protocol` definitions — interfaces other code depends on. |
| `<adapter>.py` | Concrete implementations (e.g. `mapbox_adapter.py`, `postgres_adapter.py`). |
| `service.py` | Use cases composing ports + caching + business rules. |
| `repository.py` | DB access (when applicable). |
| Pure modules | e.g. `haversine.py`, `selector.py` — no IO, deterministic, trivially testable. |

`shared/` knows nothing about HTTP. It can be lifted into another service
or a worker without changes.

### `core/` — composition root

Glue: settings, DI helpers, logging, metrics, security middleware, error
mapping. **No domain logic**. Imported by both `features/` and `main.py`.

---

## Dependency injection

We avoid a DI framework. The pattern is:

1. `main.py` `lifespan()` builds long-lived resources (asyncpg pool,
   `MapboxMatrixProvider`, `DistanceService`, `FacepileService`) and
   stores them on `app.state`.
2. Routes pull them via `request.app.state.<name>` through a small
   `_service(request, pool, settings)` factory.
3. Per-request resources (current user id, settings) come from
   FastAPI `Depends(...)` declared in `core/dependencies.py`.

Why `app.state` for the heavy services? They're cache-bearing singletons
(e.g. distance cell cache, facepile TTL cache). Building one per request
would defeat the cache. Why not module-level globals? Tests can swap
them per app instance.

---

## Request lifecycle

```
client ── HTTP ──▶ MetricsMiddleware
                    └▶ RequestContextMiddleware (sets request_id ContextVar)
                       └▶ CORSMiddleware
                          └▶ SecurityMiddleware (IP throttling + access log)
                             └▶ FastAPI router → features.<slice>.routes
                                └▶ service (orchestration)
                                   └▶ repository (asyncpg) + shared services
                                ◀───── domain dataclasses / dicts
                             ◀───── pydantic-validated response
                          ◀───── status code, headers
                       ◀───── log line with request_id
                    ◀───── http_requests_total{method,path,status}++
```

Every log record carries the `request_id` (see `core/logging.py`). It's
also returned in the `X-Request-ID` response header so a client can
correlate failures with server logs.

---

## Error handling

Domain code raises plain Python exceptions defined in
`core/exceptions.py` (`AuthenticationError`, `ValidationError`,
`NotFoundError`, …). `core/error_handlers.py` translates each one to
the appropriate HTTP response. Routes don't manually emit 4xx/5xx —
they raise.

---

## Testing strategy

| Layer | Tested how |
|---|---|
| `shared/<pure>.py` | Plain unit tests with `pytest` (no fixtures). |
| `features/<slice>/builders.py` | Pure unit tests on dicts. |
| `features/<slice>/service.py` | Tests with fake repositories (Protocol-based). |
| `features/<slice>/routes.py` | `httpx.AsyncClient(app=app)` integration tests. |
| `features/<slice>/repository.py` | Optional — covered transitively via routes. |

Run all tests:

```bash
python -m pytest tests/ -q
```

---

## Phase history (refactor log)

| Phase | Outcome |
|---|---|
| **0** — migrations | Stable SQL baseline, idempotent migrations |
| **1** — core scaffolding | `core/config.py`, error handlers, logging, deps |
| **2** — shared kernel | `shared/{i18n, telegram, ai, distance, facepile, media, cache}` ports/adapters |
| **3** — feature migration | All 8 slices moved out of legacy `app/api/*.py` |
| **3.5** — distance & facepile | `app/services/{distance,facepile}_service.py` → `shared/{distance,facepile}/service.py`, wired via `app.state` |
| **4** — cleanup | Legacy `app/` deleted, scripts switched to `core.config` |
| **5** — docs & observability | This file, README, AGENTS.md, request id middleware wired, `/metrics` exposed |
