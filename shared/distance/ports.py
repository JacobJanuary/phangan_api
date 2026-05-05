"""Routing provider port (hexagonal boundary)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RouteLeg:
    """Result of a single source→destination routing query."""

    distance_m: float
    duration_s: float


class IRoutingProvider(Protocol):
    """Adapter interface for any routing/matrix backend (Mapbox, OSRM, …)."""

    async def matrix(
        self,
        origin: tuple[float, float],
        destinations: list[tuple[float, float]],
    ) -> list[RouteLeg | None]:
        """Return one `RouteLeg` per destination, or None where unavailable.

        The provider must NOT raise on per-destination failures — it should
        return `None` for legs that could not be resolved so callers can
        gracefully fall back to haversine estimates.
        """
        ...
