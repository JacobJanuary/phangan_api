"""User profile use cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import asyncpg

from core.config import Settings
from core.exceptions import NotFoundError, ValidationError
from features.users.repository import UsersRepository
from features.users.schemas import UserUpdate

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UsersService:
    pool: asyncpg.Pool
    settings: Settings

    async def update_profile(self, user_id: int, payload: UserUpdate) -> dict[str, Any]:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            raise ValidationError("Empty payload — nothing to update")

        repo = UsersRepository(pool=self.pool)
        row = await repo.update_profile(user_id, fields)
        if row is None:
            raise NotFoundError(f"User {user_id} not found")

        return dict(row)
