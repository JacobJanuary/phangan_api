"""Tests for `shared.facepile.selector.pick_phantoms`."""

import random

from shared.facepile.selector import Phantom, pick_phantoms


def _make_pool() -> dict[str, list[Phantom]]:
    return {
        "party": [
            Phantom(f"party_f{i}.jpg", "female", "party") for i in range(5)
        ] + [
            Phantom(f"party_m{i}.jpg", "male", "party") for i in range(5)
        ],
        "spiritual": [
            Phantom(f"spi_f{i}.jpg", "female", "spiritual") for i in range(3)
        ] + [
            Phantom(f"spi_m{i}.jpg", "male", "spiritual") for i in range(3)
        ],
        "business": [
            Phantom(f"biz_f{i}.jpg", "female", "business") for i in range(2)
        ] + [
            Phantom(f"biz_m{i}.jpg", "male", "business") for i in range(2)
        ],
    }


def test_returns_empty_when_needed_zero() -> None:
    assert pick_phantoms(
        needed=0,
        event_category="party",
        viewer_gender="male",
        pool_by_mood=_make_pool(),
    ) == []


def test_chill_category_maps_to_spiritual_mood() -> None:
    rng = random.Random(42)
    out = pick_phantoms(
        needed=4,
        event_category="chill",
        viewer_gender=None,
        pool_by_mood=_make_pool(),
        rng=rng,
    )
    # All picks should come from the spiritual pool first (it has 6 entries)
    assert len(out) == 4
    assert all(p.startswith("spi_") for p in out)


def test_male_viewer_biased_towards_female() -> None:
    rng = random.Random(7)
    out = pick_phantoms(
        needed=10,
        event_category="party",
        viewer_gender="male",
        pool_by_mood=_make_pool(),
        rng=rng,
    )
    female_count = sum(1 for p in out if "_f" in p)
    # Ratio is uniform(0.6, 0.7) -> at least 60% female (== 6 of 10)
    assert female_count >= 6


def test_falls_back_to_other_moods_when_primary_short() -> None:
    rng = random.Random(1)
    pool = {
        "party": [Phantom("only_one_f.jpg", "female", "party")],
        "spiritual": [Phantom(f"spi_f{i}.jpg", "female", "spiritual") for i in range(5)],
    }
    out = pick_phantoms(
        needed=4,
        event_category="party",
        viewer_gender="male",
        pool_by_mood=pool,
        rng=rng,
    )
    # Only 1 female in primary 'party' pool — fallback should fill from 'spiritual'.
    female_count = sum(1 for p in out if "_f" in p)
    assert female_count >= 2


def test_deterministic_with_seeded_rng() -> None:
    pool = _make_pool()
    out1 = pick_phantoms(
        needed=5,
        event_category="party",
        viewer_gender="male",
        pool_by_mood=pool,
        rng=random.Random(123),
    )
    out2 = pick_phantoms(
        needed=5,
        event_category="party",
        viewer_gender="male",
        pool_by_mood=pool,
        rng=random.Random(123),
    )
    assert out1 == out2
