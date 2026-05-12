"""Phangan API — main entry point (composition root).

Wires together:
- Settings + Constants (core.config)
- asyncpg pool (lifespan)
- Error handlers (core.error_handlers)
- Middlewares (CORS + legacy SecurityMiddleware)
- Feature routers (features.*)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.middlewares import SecurityMiddleware
from core.config import get_settings
from core.error_handlers import register_error_handlers
from core.logging import RequestContextMiddleware, configure_logging
from core.metrics import MetricsMiddleware, metrics_endpoint
from features.auth.routes import router as auth_router
from features.bot.routes import router as bot_router
from features.bot.service import register_webhook
from features.events.routes import router as events_router
from features.media.routes import router as media_router
from features.planner.routes import router as planner_router
from features.swipes.routes import router as swipes_router
from features.translations.routes import router as translations_router
from features.users.routes import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT)
    logger.info("Starting Phangan API")

    pool = await asyncpg.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        min_size=settings.DB_MIN_POOL,
        max_size=settings.DB_MAX_POOL,
    )
    logger.info(
        "DB pool ready",
        extra={
            "host": settings.DB_HOST,
            "db": settings.DB_NAME,
            "min": settings.DB_MIN_POOL,
            "max": settings.DB_MAX_POOL,
        },
    )

    app.state.settings = settings
    app.state.pool = pool

    # Hexagonal shared services (Phase 3.5).
    from shared.distance.mapbox_adapter import MapboxMatrixProvider
    from shared.distance.service import DistanceService
    from shared.facepile.service import FacepileService

    routing = (
        MapboxMatrixProvider(access_token=settings.MAPBOX_TOKEN)
        if settings.MAPBOX_TOKEN
        else None
    )
    app.state.distance_service = DistanceService(routing=routing)
    app.state.facepile_service = FacepileService(
        pool=pool,
        media_base_url=settings.PUBLIC_MEDIA_BASE_URL,
    )

    # Telegram webhook registration is best-effort.
    try:
        await register_webhook(settings)
    except Exception as exc:
        logger.warning("Webhook registration failed (non-fatal): %s", exc)

    try:
        yield
    finally:
        await pool.close()
        logger.info("Phangan API shut down")


_public_docs = os.getenv("ENABLE_PUBLIC_DOCS", "0") == "1"

app = FastAPI(
    title="Phangan Events API",
    description="Production-ready API for the VibeRadar Koh Phangan Telegram Mini App",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _public_docs else None,
    redoc_url="/redoc" if _public_docs else None,
    openapi_url="/openapi.json" if _public_docs else None,
)

# Error handlers (translate domain exceptions → HTTP responses).
register_error_handlers(app)

# Middlewares (order: first added = outermost).
app.add_middleware(SecurityMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(MetricsMiddleware)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Feature routers.
app.include_router(media_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(events_router)
app.include_router(swipes_router)
app.include_router(planner_router)
app.include_router(translations_router)
app.include_router(bot_router)


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "ok", "service": "phangan-api"}


if os.getenv("ENABLE_PUBLIC_METRICS", "0") == "1":
    app.add_api_route(
        "/metrics", metrics_endpoint, methods=["GET"], tags=["system"], include_in_schema=False
    )
