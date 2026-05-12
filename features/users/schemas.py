"""User-profile DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class UserUpdate(BaseModel):
    """Mutable subset of the user profile that the frontend can change."""

    gender: Literal["male", "female"] | None = None
    current_mood: Literal[
        "yoga", "business", "party", "all", "sunset", "games", "chill", "tomorrow"
    ] | None = None
