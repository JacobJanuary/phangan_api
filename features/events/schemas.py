"""Event DTOs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EventUpdate(BaseModel):
    title: Optional[dict[str, str]] = None
    summary: Optional[dict[str, str]] = None
    description: Optional[dict[str, str]] = None
    category: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    location_name: Optional[str] = None
    google_maps_url: Optional[str] = None
    price_thb: Optional[int] = None
    recurrence_type: Optional[str] = None
