"""Pure phantom-avatar selection logic.

No I/O, no DB, no randomness leakage — accepts an explicit `random.Random`
so tests stay deterministic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

Gender = Literal["male", "female"]


@dataclass(frozen=True, slots=True)
class Phantom:
    """A phantom avatar candidate."""

    avatar_path: str
    gender: Gender | None
    mood: str | None


# Map an event category to the phantom mood that visually fits best.
CATEGORY_TO_MOOD: dict[str, str] = {
    "party": "party",
    "chill": "spiritual",
    "business": "business",
    "education": "business",
    "sport": "party",
}


def _female_ratio(viewer_gender: str | None, rng: random.Random) -> float:
    """Bias selection towards the opposite gender of the viewer."""
    if viewer_gender == "male":
        return rng.uniform(0.6, 0.7)
    if viewer_gender == "female":
        return rng.uniform(0.3, 0.4)
    return 0.5


def pick_phantoms(
    *,
    needed: int,
    event_category: str | None,
    viewer_gender: str | None,
    pool_by_mood: dict[str, list[Phantom]],
    rng: random.Random | None = None,
) -> list[str]:
    """Select `needed` phantom avatar paths matching mood + viewer gender bias.

    Args:
        needed: How many avatar paths to return (clamped to >= 0).
        event_category: Used to resolve the target mood; defaults to "party".
        viewer_gender: "male", "female" or None — drives gender ratio.
        pool_by_mood: Mapping of mood -> available phantoms.
        rng: Random source. Pass a seeded `random.Random` for deterministic tests.

    Returns:
        Up to `needed` phantom avatar paths. Fewer if the pool is exhausted.
    """
    if needed <= 0:
        return []

    rng = rng or random.Random()
    cat = (event_category or "party").lower()
    mood = CATEGORY_TO_MOOD.get(cat, "party")

    ratio_f = _female_ratio(viewer_gender, rng)
    needed_f = int(needed * ratio_f)
    needed_m = needed - needed_f

    primary = list(pool_by_mood.get(mood, ()))
    fallback = [
        p for m, group in pool_by_mood.items() if m != mood for p in group
    ]

    def _take(target_gender: Gender, count: int) -> list[str]:
        if count <= 0:
            return []
        candidates = [p for p in primary if p.gender == target_gender]
        if len(candidates) < count:
            candidates = candidates + [p for p in fallback if p.gender == target_gender]
        rng.shuffle(candidates)
        return [p.avatar_path for p in candidates[:count]]

    return _take("female", needed_f) + _take("male", needed_m)
