"""Retired recurrence writer.

The parser pipeline owns recurring/copy logic now. This script is kept as a
safe no-op because old cron/service references may still exist on a host; it
must not write to the `events` table or depend on removed legacy recurrence
columns.
"""

from __future__ import annotations

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("recurrent_events_generator")


def main() -> None:
    logger.info(
        "Recurrent Events Generator is retired; parser owns recurrence copies. No-op."
    )


if __name__ == "__main__":
    main()
