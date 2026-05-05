"""Tests for `shared.distance` (haversine, bbox)."""

import pytest

from shared.distance.bbox import BoundingBox
from shared.distance.haversine import haversine_km, road_km, travel_minutes


# Reference: Thong Sala (9.7314, 100.0136) → Haad Rin (9.6754, 100.0686)
# expected ~8.5 km haversine
def test_haversine_known_distance() -> None:
    d = haversine_km(9.7314, 100.0136, 9.6754, 100.0686)
    assert 8.0 < d < 9.0


def test_haversine_zero_for_same_point() -> None:
    assert haversine_km(9.7, 100.0, 9.7, 100.0) == pytest.approx(0.0, abs=1e-9)


def test_road_km_applies_factor_and_rounds() -> None:
    base = haversine_km(9.7314, 100.0136, 9.6754, 100.0686)
    expected = round(base * 1.4, 1)
    assert road_km(9.7314, 100.0136, 9.6754, 100.0686) == expected


def test_road_km_rejects_non_positive_factor() -> None:
    with pytest.raises(ValueError):
        road_km(0, 0, 1, 1, factor=0)


def test_travel_minutes_rounds_up() -> None:
    # 5 km / 25 km/h = 12 min
    assert travel_minutes(5.0, kmh=25) == 12
    # 0.1 km / 25 km/h = 0.24 min → minimum 1
    assert travel_minutes(0.1, kmh=25) == 1


def test_travel_minutes_validation() -> None:
    with pytest.raises(ValueError):
        travel_minutes(-1, kmh=25)
    with pytest.raises(ValueError):
        travel_minutes(1, kmh=0)


def test_bbox_contains() -> None:
    phangan = BoundingBox(lat_min=9.65, lat_max=9.84, lng_min=99.91, lng_max=100.14)
    assert phangan.contains(9.74, 100.02) is True
    assert phangan.contains(13.7, 100.5) is False  # Bangkok


def test_bbox_validation() -> None:
    with pytest.raises(ValueError):
        BoundingBox(lat_min=10, lat_max=9, lng_min=0, lng_max=1)
    with pytest.raises(ValueError):
        BoundingBox(lat_min=0, lat_max=1, lng_min=10, lng_max=9)
