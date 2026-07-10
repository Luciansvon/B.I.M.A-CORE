#!/usr/bin/env python3
"""Continuously write Anisa's lightweight operational snapshot."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.operational_status import collect_snapshot, write_snapshot_atomic

SNAPSHOT_PATH = PROJECT_ROOT / "runtime" / "anisa_status.json"
logger = logging.getLogger("bima_core.status_collector")


def collect_once() -> None:
    """Collect and persist one snapshot."""
    snapshot = collect_snapshot(project_root=PROJECT_ROOT)
    write_snapshot_atomic(SNAPSHOT_PATH, snapshot)


def run(interval_seconds: int = 30) -> None:
    """Collect immediately, then refresh until PM2 stops the process."""
    while True:
        try:
            collect_once()
        except Exception:
            logger.exception("Operational snapshot refresh failed")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--once" in sys.argv[1:]:
        collect_once()
    else:
        run()
