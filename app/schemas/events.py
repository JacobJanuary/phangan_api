from typing import Optional, Dict
from pydantic import BaseModel

class EventUpdate(BaseModel):
    title: Optional[Dict[str, str]] = None
    summary: Optional[Dict[str, str]] = None
    description: Optional[Dict[str, str]] = None
    category: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    location_name: Optional[str] = None
    google_maps_url: Optional[str] = None
    price_thb: Optional[int] = None
    recurrence_type: Optional[str] = None
