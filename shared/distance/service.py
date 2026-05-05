"""Distance enrichment service — orchestrates haversine + routing provider + cache.

Wraps the pure helpers (`haversine`, `bbox`) and a routing adapter
(`IRoutingProvider`) behind a single async method that mutates a list of
event dicts in place, adding `distance_km` and `bike_minutes`.

Cache strategy (preserved from legacy `app/services/distance_service.py`):
- Round user GPS to a coarse grid cell (~110m at equator)
- Per cell: cache `{venue_coord_key: RouteLeg}` with 24h TTL
- Skip enrichment entirely if user is outside the bounding box
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from shared.distance.bbox import BoundingBox
from shared.distance.haversine import road_km
from shared.distance.ports import IRoutingProvider, RouteLeg

logger = logging.getLogger(__name__)


# Koh Phangan bounding box (with ~1km coastal buffer).
PHANGAN_BBOX = BoundingBox(
    lat_min=9.65, lat_max=9.84, lng_min=99.91, lng_max=100.14
)

_DEFAULT_CACHE_TTL_S = 86400  # 24 hours
_DEFAULT_GRID_PRECISION = 3  # rounding decimals → ~110m grid at equator
_VENUE_COORD_PRECISION = 5  # rounding for venue dedup key


def _grid_key(lat: float, lng: float, *, precision: int) -> tuple[float, float]:
    return (round(lat, precision), round(lng, precision))


@dataclass(slots=True)
class _CacheEntry:
    leg: RouteLeg
    ts: float


@dataclass(slots=True)
class DistanceService:
    """Enrich event dicts with road distance + travel duration.

    The service is stateless from the caller's perspective: it owns its
    in-memory cache. Mount it once on `app.state.distance_service` (or
    instantiate per request — caching loses value but correctness is intact).
    """

    routing: IRoutingProvider | None
    bbox: BoundingBox = field(default_factory=lambda: PHANGAN_BBOX)
    road_factor: float = 1.4
    cache_ttl_s: int = _DEFAULT_CACHE_TTL_S
    grid_precision: int = _DEFAULT_GRID_PRECISION
    _cache: dict[tuple[float, float], dict[tuple[float, float], _CacheEntry]] = field(
        default_factory=dict, init=False
    )

    def _is_fresh(self, entry: _CacheEntry) -> bool:
        return (time.time() - entry.ts) < self.cache_ttl_s

    async def enrich_events(
        self,
        events: list[dict],
        *,
        user_lat: float,
        user_lng: float,
    ) -> None:
        """Mutate `events` in place: add `distance_km` and `bike_minutes` keys.

        - `distance_km`: haversine × road_factor (always set when user is on-island).
        - `bike_minutes`: from `IRoutingProvider`, rounded up; None when unavailable.
        """
        if not self.bbox.contains(user_lat, user_lng):
            logger.debug(
                "User off-island, skipping distance enrichment",
                extra={"user_lat": user_lat, "user_lng": user_lng},
            )
            return

        # Group events by venue coordinate (dedup repeat venues across events).
        venue_groups: dict[tuple[float, float], list[dict]] = {}
        for ev in events:
            lat, lng = ev.get("lat"), ev.get("lng")
            if lat is None or lng is None:
                continue
            coord_key = _grid_key(lat, lng, precision=_VENUE_COORD_PRECISION)
            venue_groups.setdefault(coord_key, []).append(ev)

        if not venue_groups:
            return

        cell_key = _grid_key(user_lat, user_lng, precision=self.grid_precision)
        cell_cache = self._cache.setdefault(cell_key, {})

        # Determine which venues need a fresh routing call.
        uncached: list[tuple[float, float]] = []
        for coord_key in venue_groups:
            entry = cell_cache.get(coord_key)
            if entry is None or not self._is_fresh(entry):
                uncached.append(coord_key)

        # Fetch missing legs from the routing provider (if configured).
        if uncached and self.routing is not None:
            try:
                legs = await self.routing.matrix(
                    origin=(user_lat, user_lng),
                    destinations=list(uncached),
                )
            except Exception as exc:
                logger.warning("Routing provider failed: %s", exc)
                legs = [None] * len(uncached)

            now = time.time()
            for coord_key, leg in zip(uncached, legs):
                if leg is not None:
                    cell_cache[coord_key] = _CacheEntry(leg=leg, ts=now)

        # Apply distance + duration to events.
        for coord_key, group in venue_groups.items():
            dist_km = road_km(
                user_lat,
                user_lng,
                coord_key[0],
                coord_key[1],
                factor=self.road_factor,
            )

            entry = cell_cache.get(coord_key)
            bike_minutes: int | None = None
            if entry is not None and self._is_fresh(entry):
                # Convert duration_s → minutes, rounded up, minimum 1.
                from math import ceil

                bike_minutes = max(1, ceil(entry.leg.duration_s / 60))

            for ev in group:
                ev["distance_km"] = dist_km
                ev["bike_minutes"] = bike_minutes
