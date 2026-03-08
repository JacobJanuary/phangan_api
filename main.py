"""
Phangan API — main entry point.

Enterprise-grade FastAPI application with:
  - asyncpg connection pool (lifespan managed)
  - Security middleware (IP blacklisting)
  - CORS for Telegram Mini App
  - Modular API routers
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.media import router as media_router
from app.api.users import router as users_router
from app.api.v1_events import router as v1_events_router
from app.api.v1_planner import router as v1_planner_router
from app.api.v1_swipes import router as v1_swipes_router
from app.core.config import get_settings
from app.core.middlewares import SecurityMiddleware
from app.db.database import close_pool, create_pool

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown resources."""
    settings = get_settings()
    logger.info("🚀 Starting Phangan API...")
    await create_pool(settings)
    yield
    await close_pool()
    logger.info("👋 Phangan API shut down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Phangan Events API",
    description="Production-ready API for the VibeRadar Koh Phangan Telegram Mini App",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Middleware stack (order matters: first added = outermost) ─────────────
settings = get_settings()

app.add_middleware(SecurityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(media_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(v1_events_router)
app.include_router(v1_swipes_router)
app.include_router(v1_planner_router)


# ── Health check (no API key required) ────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Simple health probe for monitoring."""
    return {"status": "ok", "service": "phangan-api"}
