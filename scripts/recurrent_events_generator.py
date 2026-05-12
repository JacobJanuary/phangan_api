"""Disabled legacy recurrent writer.

Recurring event copies are owned by the parser pipeline. This script remains as
a compatibility entrypoint for stale cron references, but it intentionally does
not read or write deprecated recurrence columns on `events`.
"""

from __future__ import annotations

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("recurrent_events_generator")


def main() -> None:
    logger.info(
        "Legacy recurrent_events_generator is disabled; parser owns recurring copies."
    )


if __name__ == "__main__":
    main()
