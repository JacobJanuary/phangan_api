"""
User schemas for API requests and responses.
"""

from typing import Literal, Optional
from pydantic import BaseModel

class UserUpdate(BaseModel):
    gender: Optional[Literal["male", "female"]] = None
    current_mood: Optional[Literal["yoga", "business", "party", "all", "sunset", "games", "chill", "tomorrow"]] = None
