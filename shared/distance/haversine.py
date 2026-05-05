"""Pure haversine distance helpers."""

from __future__ import annotations

import math


_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres.

    Inputs are decimal degrees. Returns the straight-line distance assuming
    a spherical Earth (good enough for venue-scale routing).
    """
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def road_km(
    lat1: float, lng1: float, lat2: float, lng2: float, *, factor: float = 1.4
) -> float:
    """Approximate road distance — haversine multiplied by a winding factor.

    The default 1.4 reflects empirical Koh Phangan road network winding.
    """
    if factor <= 0:
        raise ValueError("road factor must be positive")
    return round(haversine_km(lat1, lng1, lat2, lng2) * factor, 1)


def travel_minutes(distance_km: float, *, kmh: float) -> int:
    """Estimated travel time in whole minutes (rounded up, minimum 1)."""
    if distance_km < 0:
        raise ValueError("distance_km must be non-negative")
    if kmh <= 0:
        raise ValueError("kmh must be positive")
    return max(1, math.ceil(distance_km / kmh * 60))
