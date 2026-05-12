"""HTTP routes for user profile management."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from core.config import Settings
from core.dependencies import get_current_user_id, get_pool_dep, get_settings_dep
from features.users.schemas import UserUpdate
from features.users.service import UsersService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch(
    "/me",
    summary="Update user profile",
    description="Update mood or gender for the authenticated user.",
)
async def update_me(
    payload: UserUpdate,
    user_id: int = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_pool_dep),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    row = await UsersService(pool=pool, settings=settings).update_profile(user_id, payload)
    return {
        "user": {
            "id": str(row["id"]),
            "telegram_id": str(row["telegram_id"]),
            "first_name": row["first_name"],
            "gender": row["gender"],
            "current_mood": row["mood"],
            "avatar": row["avatar_path"],
        }
    }
