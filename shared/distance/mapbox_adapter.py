"""Mapbox Directions Matrix routing provider."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from shared.distance.ports import IRoutingProvider, RouteLeg

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.mapbox.com/directions-matrix/v1/mapbox/driving"
_MAX_DESTINATIONS = 24  # Mapbox limit: 25 coords total = 1 source + 24 dests


@dataclass(slots=True)
class MapboxMatrixProvider(IRoutingProvider):
    """Concrete `IRoutingProvider` backed by Mapbox Directions Matrix v1."""

    access_token: str
    base_url: str = _DEFAULT_BASE
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if not self.access_token:
            raise ValueError("MapboxMatrixProvider.access_token must be set")
        if self.timeout_s <= 0:
            raise ValueError("MapboxMatrixProvider.timeout_s must be positive")

    async def matrix(
        self,
        origin: tuple[float, float],
        destinations: list[tuple[float, float]],
    ) -> list[RouteLeg | None]:
        if not destinations:
            return []

        results: list[RouteLeg | None] = [None] * len(destinations)

        for batch_start in range(0, len(destinations), _MAX_DESTINATIONS):
            batch = destinations[batch_start : batch_start + _MAX_DESTINATIONS]
            origin_lat, origin_lng = origin
            coords = [f"{origin_lng},{origin_lat}"]
            coords.extend(f"{lng},{lat}" for lat, lng in batch)
            url = f"{self.base_url}/{';'.join(coords)}"
            params = {
                "sources": "0",
                "annotations": "distance,duration",
                "access_token": self.access_token,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                # Whole batch failed — leave the slots as None (graceful degradation).
                logger.warning(
                    "Mapbox matrix batch failed",
                    extra={
                        "batch_start": batch_start,
                        "batch_size": len(batch),
                        "error": str(exc),
                    },
                )
                continue

            distances = data.get("distances", [[]])
            durations = data.get("durations", [[]])
            row_d = distances[0] if distances else []
            row_t = durations[0] if durations else []

            for i in range(len(batch)):
                idx = i + 1  # offset by 1 — index 0 is the origin
                if idx >= len(row_d) or row_d[idx] is None:
                    continue
                duration = row_t[idx] if idx < len(row_t) and row_t[idx] is not None else 0.0
                results[batch_start + i] = RouteLeg(
                    distance_m=float(row_d[idx]),
                    duration_s=float(duration),
                )

        return results
