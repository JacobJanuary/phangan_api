"""Static contract tests for public event visibility queries."""

from __future__ import annotations


def test_events_public_filter_requires_start_time() -> None:
    from pathlib import Path

    from features.events import repository

    assert "e.start_time IS NOT NULL" in repository._PUBLIC_EVENT_FILTER
    assert "OR ({start_time}) IS NULL" not in Path("features/events/repository.py").read_text()


def test_swipes_public_filter_requires_start_time() -> None:
    from features.swipes import repository

    assert "AND e.start_time IS NOT NULL" in repository._BASE_WHERE
    assert "OR (" not in repository._UPCOMING_TIME_FILTER.split("OR CASE", 1)[0]


def test_planner_query_requires_start_time() -> None:
    from pathlib import Path

    source = Path("features/planner/repository.py").read_text()
    assert "AND e.start_time IS NOT NULL" in source
