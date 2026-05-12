"""Auth DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InitDataPayload(BaseModel):
    """Telegram Mini App initData payload."""

    initData: str = Field(min_length=1, max_length=8192)
