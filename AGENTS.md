# Agent / Copilot instructions

These rules govern how AI coding agents (Copilot, Claude, Cursor, etc.)
should work in this repository. Read [ARCHITECTURE.md](ARCHITECTURE.md)
first for the layout.

---

## Top-level rules

1. **Preserve HTTP contracts.** Endpoint paths, query/body shapes, response
   keys, and status codes are public. If you must change one, mark it in
   the commit message and ensure the frontend is updated in the same PR.
2. **No legacy `app/` directory.** It was deleted in phase 4. Do not
   recreate it. Anything that needs a home goes into `features/`,
   `shared/`, or `core/`.
3. **Slices don't talk to siblings.** `features/events/` cannot import
   `features/swipes/`. If two slices need the same logic, lift it into
   `shared/`.
4. **HTTP only in routes.** No SQL, no `aiohttp`, no Telegram calls
   inside `routes.py`. Route bodies should be ≤10 lines: parse, delegate,
   return.
5. **Repositories return data, not HTTP.** Never `raise HTTPException`
   from a repository or a `shared/` module. Raise domain exceptions
   from `core/exceptions.py` and let the error handler translate.
6. **Pure helpers stay pure.** Anything in `shared/<x>/{haversine,
   selector, builders}.py` and `features/<x>/builders.py` must not do IO.
   These are the easiest things to unit-test — keep them that way.
7. **Use `request.app.state`** to reach singletons (distance, facepile,
   pool, settings). Don't reach into module-level globals.

## Style

- Python 3.12 features are fine (`X | Y` unions, `match/case`,
  `dataclass(slots=True)`).
- `from __future__ import annotations` at the top of every module.
- Type-annotate **every** public function and dataclass field.
- Docstrings on modules and public service/repository classes; trivial
  helpers can skip.
- Prefer `dataclass(slots=True, frozen=True)` for value objects.
- One asyncpg query per repository method when possible. Use prepared
  parameters (`$1, $2`), never f-string interpolate user input.
- Prefer composition over inheritance. Inherit only from `Protocol`.

## Logging

- Use `logger = logging.getLogger(__name__)` per module.
- Pass structured fields via `extra={"key": value}` — **don't** format
  values into the message string. The JSON formatter picks up `extra`.
- Log levels:
  - `DEBUG`: noisy traces, off in prod.
  - `INFO`: normal lifecycle events (login OK, webhook registered).
  - `WARNING`: degraded but recoverable (Mapbox 5xx → fall back to
    haversine).
  - `ERROR`: caller-visible failure or unexpected state. Include
    `exc_info=True` when reraising.

## Tests

- New `service.py` ⇒ tests in `tests/features/<slice>/test_service.py`.
- New `shared/<x>/<pure>.py` ⇒ tests in `tests/unit/test_<x>.py`.
- Mock at the `Protocol` boundary, not at the asyncpg boundary.
- Don't add tests for one-line passthrough wrappers.

## Git / commits

- One concern per commit. The phase-* refactor commits are exemplars.
- Subject line ≤72 chars, imperative mood: `fix(auth): …`,
  `feat(shared): …`, `refactor(events): …`.
- Body should explain **why**, not what — the diff already shows what.
- Never `--force` push. Never `git reset --hard` shared branches.
- Don't commit `.env`, `media/`, `venv/`, `__pycache__/`.

## Deployment

- Prod is **not** a git repo. Deploy by `rsync` (see
  [README.md](README.md#deployment-production)).
- **Always** take a tarball backup before deploying.
- After deploy: import-smoke (`from main import app`), pytest, restart,
  curl `/health`, check `journalctl` for errors. In that order.
- The rsync `--exclude='/media/'` must be **anchored with the leading
  slash**. `--exclude='media/'` would also exclude `features/media/`
  and `shared/media/`. Don't.

## When in doubt

- Match the shape of an existing slice rather than inventing a new one.
  `features/events/` and `features/swipes/` are good references.
- Read [ARCHITECTURE.md](ARCHITECTURE.md). If your change doesn't fit
  the model, ask before contorting the model to fit your change.
