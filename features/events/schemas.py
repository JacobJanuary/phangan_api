"""Event DTOs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class EventUpdate(BaseModel):
    title: Optional[dict[str, str]] = None
    summary: Optional[dict[str, str]] = None
    description: Optional[dict[str, str]] = None
    sharing_description: Optional[dict[str, str]] = None
    requirements: Optional[dict[str, str]] = None
    keywords: Optional[dict[str, list[str]]] = None
    demographic_filters: Optional[dict[str, bool]] = None
    ai_addons: Optional[list[str]] = None
    category: Optional[str] = None
    event_type: Optional[str] = None
    event_category: Optional[str] = None
    event_sub_category: Optional[str] = None
    event_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    ends_next_day: Optional[bool] = None
    location_name: Optional[str] = None
    price_thb: Optional[int] = None
    currency_code: Optional[str] = None
    capacity: Optional[int] = None
    public_status: Optional[str] = None
    metadata_status: Optional[str] = None
    timezone: Optional[str] = None
    faqs: Optional[list[dict[str, Any]]] = None
