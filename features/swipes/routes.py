"""HTTP routes for swipes."""

from __future__ import annotations

from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from core.config import Settings
from core.dependencies import get_current_user_id, get_pool_dep, get_settings_dep
from features.swipes.schemas import SwipeCreate
from features.swipes.service import SwipesService

router = APIRouter(prefix="/api/v1/swipes", tags=["swipes"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def save_swipe(
    body: SwipeCreate,
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> Response:
    await SwipesService(pool=pool, settings=settings).save_swipe(
        user_id=user_id, payload=body
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/my-vibe")
async def my_vibe(
    lang: Literal["en", "ru"] = Query(default="ru"),
    include_past: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    return await SwipesService(pool=pool, settings=settings).my_vibe(
        user_id=user_id,
        lang=lang,
        include_past=include_past,
        limit=limit,
        offset=offset,
    )


@router.delete("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_swipes(
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
    user_id: int = Depends(get_current_user_id),
) -> Response:
    await SwipesService(pool=pool, settings=settings).reset_swipes(user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
