"""Swipe DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SwipeCreate(BaseModel):
    event_id: int
    direction: Literal["right", "left"]
