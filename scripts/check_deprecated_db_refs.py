"""Fail if production SQL references removed/legacy DB columns."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_DIRS = ["core", "features", "shared", "scripts"]
SKIP_FILES = {Path("scripts/check_deprecated_db_refs.py")}
PATTERNS = {
    "events.event_time": re.compile(r"\be\.event_time\b|\bevents\.event_time\b"),
    "events.google_maps_url": re.compile(r"\be\.google_maps_url\b|\bevents\.google_maps_url\b"),
    "events.recurrence_type": re.compile(r"\be\.recurrence_type\b|recurrence_type\s+IN\b"),
    "events.parent_id": re.compile(r"\be\.parent_id\b|\bparent_id\b"),
    "ai_duplicate_candidates.candidate_ids": re.compile(r"\bcandidate_ids\b"),
    "discovery_venues.instagram_url": re.compile(r"\binstagram_url\b"),
    "discovery_venues.monitoring_approved": re.compile(r"\bmonitoring_approved\b"),
    "discovery_venues.summary_dead_fields": re.compile(
        r"\bgenerative_summary\b|\breview_summary\b|\bneighborhood_summary\b"
    ),
}


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        files.extend(base.rglob("*.py"))
    return sorted(files)


def main() -> int:
    failures: list[str] = []
    for path in iter_python_files():
        rel = path.relative_to(ROOT)
        if rel in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                failures.append(f"{rel}:{line_no}: deprecated DB ref {label}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
