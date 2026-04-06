"""
Distance Service — Mapbox Matrix API with in-memory grid cache.

Enriches events with road-distance (km) and scooter/bike travel time (min)
from the user's GPS position to each venue.

Cache strategy:
  - Round user coords to ~500m grid cells
  - Cache per (grid_cell → venue_id) with 24h TTL
  - ~69 active venues × ~450 grid cells ≈ <1 MB RAM
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
_CACHE_TTL_S = 86400  # 24 hours
_GRID_PRECISION = 3   # ~110m at equator; groups users within ~100-200m
_MAPBOX_BATCH_SIZE = 24  # Max 24 destinations + 1 origin = 25 total
_MAPBOX_BASE = "https://api.mapbox.com/directions-matrix/v1/mapbox/driving"

# ── Koh Phangan bounding box (with ~1km coastal buffer) ──────────────────────
_PHANGAN_LAT_MIN = 9.65
_PHANGAN_LAT_MAX = 9.84
_PHANGAN_LNG_MIN = 99.91
_PHANGAN_LNG_MAX = 100.14


def _is_on_phangan(lat: float, lng: float) -> bool:
    """Check if coordinates fall within the Koh Phangan bounding box."""
    return (_PHANGAN_LAT_MIN <= lat <= _PHANGAN_LAT_MAX and
            _PHANGAN_LNG_MIN <= lng <= _PHANGAN_LNG_MAX)

# ── In-memory cache ─────────────────────────────────────────────────────────
# Structure: { (grid_lat, grid_lng): { venue_id: { "distance_m": float, "duration_s": float, "ts": float } } }
_cache: dict[tuple[float, float], dict[int, dict[str, float]]] = {}


def _grid_key(lat: float, lng: float) -> tuple[float, float]:
    """Round coords to grid cell."""
    return (round(lat, _GRID_PRECISION), round(lng, _GRID_PRECISION))


def _is_fresh(entry: dict[str, float]) -> bool:
    return (time.time() - entry.get("ts", 0)) < _CACHE_TTL_S


def _collect_venue_coords(events: list[dict]) -> dict[str, tuple[float, float]]:
    """Extract unique (event_id → lat/lng) for events that have venue coords."""
    venues: dict[str, tuple[float, float]] = {}
    for ev in events:
        lat, lng = ev.get("lat"), ev.get("lng")
        if lat is not None and lng is not None:
            venues[ev["id"]] = (lat, lng)
    return venues


async def _fetch_mapbox_matrix(
    user_lat: float,
    user_lng: float,
    destinations: list[tuple[int, float, float]],  # [(venue_key, lat, lng), ...]
    token: str,
) -> dict[int, dict[str, float]]:
    """Call Mapbox Matrix API and return { venue_key: { distance_m, duration_s } }."""
    results: dict[int, dict[str, float]] = {}

    for batch_start in range(0, len(destinations), _MAPBOX_BATCH_SIZE):
        batch = destinations[batch_start:batch_start + _MAPBOX_BATCH_SIZE]

        # Build coordinates string: origin;dest1;dest2;...
        coords_parts = [f"{user_lng},{user_lat}"]
        for _, lat, lng in batch:
            coords_parts.append(f"{lng},{lat}")
        coords_str = ";".join(coords_parts)

        url = f"{_MAPBOX_BASE}/{coords_str}"
        params = {
            "sources": "0",
            "annotations": "distance,duration",
            "access_token": token,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            distances = data.get("distances", [[]])[0]  # row 0 = from source
            durations = data.get("durations", [[]])[0]

            for i, (venue_key, _, _) in enumerate(batch):
                idx = i + 1  # offset by 1 because source is at index 0
                if idx < len(distances) and distances[idx] is not None:
                    results[venue_key] = {
                        "distance_m": distances[idx],
                        "duration_s": durations[idx] if idx < len(durations) else 0,
                        "ts": time.time(),
                    }
        except Exception as exc:
            logger.warning("Mapbox Matrix batch failed: %s", exc)
            # Partial results are fine — uncached venues just won't get distances

    return results


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine straight-line distance in km."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Koh Phangan road winding factor: roads are ~1.4x straight-line distance on average
_ROAD_FACTOR = 1.4


async def enrich_with_distances(
    events: list[dict],
    user_lat: float,
    user_lng: float,
) -> None:
    """Mutate events in-place, adding distance_km and bike_minutes fields.

    - distance_km: Haversine × road factor (reliable, no API quirks)
    - bike_minutes: Mapbox Matrix duration (API-based travel time estimate)
    """
    # Skip if user is not on Phangan — no point calculating distances
    if not _is_on_phangan(user_lat, user_lng):
        logger.debug("User at (%.4f, %.4f) is off-island, skipping distances", user_lat, user_lng)
        return

    settings = get_settings()
    token = settings.MAPBOX_TOKEN
    if not token:
        logger.debug("MAPBOX_TOKEN not set, skipping distance enrichment")
        return

    gk = _grid_key(user_lat, user_lng)
    cell_cache = _cache.setdefault(gk, {})

    # Collect unique venue coordinates from events
    # Use a dedup key based on rounded coords to avoid duplicate Mapbox calls
    venue_map: dict[tuple[float, float], list[dict]] = {}  # (lat,lng) → [events]
    for ev in events:
        lat, lng = ev.get("lat"), ev.get("lng")
        if lat is not None and lng is not None:
            coord_key = (round(lat, 5), round(lng, 5))
            venue_map.setdefault(coord_key, []).append(ev)

    # Find which coord_keys need Mapbox calls (not in cache or expired)
    uncached: list[tuple[int, float, float]] = []
    coord_key_to_id: dict[tuple[float, float], int] = {}

    for i, coord_key in enumerate(venue_map.keys()):
        venue_cache_key = hash(coord_key)
        coord_key_to_id[coord_key] = venue_cache_key

        cached = cell_cache.get(venue_cache_key)
        if cached and _is_fresh(cached):
            continue  # Cache hit
        uncached.append((venue_cache_key, coord_key[0], coord_key[1]))

    # Fetch missing from Mapbox (for duration only)
    if uncached:
        logger.info("Mapbox Matrix: %d venues to fetch for grid %s", len(uncached), gk)
        new_results = await _fetch_mapbox_matrix(user_lat, user_lng, uncached, token)
        cell_cache.update(new_results)

    # Apply distances to events
    for coord_key, evs in venue_map.items():
        venue_cache_key = coord_key_to_id[coord_key]
        entry = cell_cache.get(venue_cache_key)

        # Haversine distance × road factor (always available, no API dependency)
        haversine_dist = _haversine_km(user_lat, user_lng, coord_key[0], coord_key[1])
        dist_km = round(haversine_dist * _ROAD_FACTOR, 1)

        # Mapbox Matrix duration (if available)
        bike_min = None
        if entry and "duration_s" in entry:
            bike_min = math.ceil(entry["duration_s"] / 60)

        for ev in evs:
            ev["distance_km"] = dist_km
            ev["bike_minutes"] = bike_min

