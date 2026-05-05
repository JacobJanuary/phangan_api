"""Planner DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlannerRequest(BaseModel):
    date: str = Field(..., description="Target date YYYY-MM-DD")
    lat: float = Field(..., description="User latitude")
    lng: float = Field(..., description="User longitude")
    lang: Literal["en", "ru"] = Field(default="ru")
    current_time: str | None = Field(default=None, description="Current time HH:MM")
    force_refresh: bool = Field(default=False, description="Bypass cache and force regeneration")
