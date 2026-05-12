"""HTTP routes for auth feature."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, Request

from core.config import Settings
from core.dependencies import get_pool_dep, get_settings_dep
from features.auth.schemas import InitDataPayload
from features.auth.service import AuthService
from shared.ai.cascade import CascadeOrchestrator

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_cascade(request: Request) -> CascadeOrchestrator | None:
    return getattr(request.app.state, "ai_cascade", None)


@router.post(
    "/init",
    summary="Zero-Click Registration via Telegram Mini App",
    description=(
        "Validates Telegram initData, registers or updates the user, and "
        "returns a JWT plus localized UI texts."
    ),
)
async def init_auth(
    payload: InitDataPayload,
    background_tasks: BackgroundTasks,
    request: Request,
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    service = AuthService(
        pool=pool,
        settings=settings,
        cascade=_get_cascade(request),
    )
    return await service.init_session(payload, background_tasks)
