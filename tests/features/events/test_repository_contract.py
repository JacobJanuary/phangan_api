"""Static guards for the current events DB contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_public_event_queries_do_not_reference_dropped_storage_columns() -> None:
    production_files = [
        ROOT / "features/events/repository.py",
        ROOT / "features/swipes/repository.py",
        ROOT / "features/planner/repository.py",
        ROOT / "scripts/recurrent_events_generator.py",
    ]
    combined = "\n".join(path.read_text() for path in production_files)

    forbidden = [
        "e.event_time",
        "events.event_time",
        "e.google_maps_url",
        "events.google_maps_url",
        "e.recurrence_type",
        "events.recurrence_type",
        "parent_id",
    ]
    for token in forbidden:
        assert token not in combined


def test_public_queries_use_public_status_and_typed_start_time() -> None:
    events_repo = (ROOT / "features/events/repository.py").read_text()
    swipes_repo = (ROOT / "features/swipes/repository.py").read_text()
    planner_repo = (ROOT / "features/planner/repository.py").read_text()

    for text in (events_repo, swipes_repo, planner_repo):
        assert "e.public_status = 'published'" in text
        assert "e.dedup_status = 'unique'" in text
        assert "e.start_time IS NOT NULL" in text
        assert "to_char(e.start_time, 'HH24:MI')" in text
