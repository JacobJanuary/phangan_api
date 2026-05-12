"""Bounding box checks for geographic regions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned latitude/longitude bounding box."""

    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float

    def __post_init__(self) -> None:
        if self.lat_min > self.lat_max:
            raise ValueError("lat_min must be <= lat_max")
        if self.lng_min > self.lng_max:
            raise ValueError("lng_min must be <= lng_max")

    def contains(self, lat: float, lng: float) -> bool:
        """Return True iff (lat, lng) lies within the box (inclusive)."""
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lng_min <= lng <= self.lng_max
        )
