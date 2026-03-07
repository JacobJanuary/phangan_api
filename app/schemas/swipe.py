"""
Swipe schemas for the My Vibe feature.
"""

from typing import Literal

from pydantic import BaseModel


class SwipeCreate(BaseModel):
    event_id: int
    direction: Literal["right", "left"]
