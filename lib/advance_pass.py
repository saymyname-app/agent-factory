"""The convoy-advance pass in flight: its lock, and when it started.

bin/convoy-advance holds one Factory-wide lock for a whole pass, and records
the start of the pass beside it while it holds it. bin/factory-watchdog
reads that start: a ticket a pass may still be moving (the pass started
within the stall window after the ticket's last record) is not yet paged,
and every other ticket is paged after the window of real silence
(af-xgd1rd). A pass killed by its order leaves its start behind; the reader
bounds it by the budget of one pass, and the next pass overwrites it.
"""
from __future__ import annotations

import calendar
import os
import time
from pathlib import Path

LOCK_NAME = "agent-factory-convoy-advance.lock"
PASS_NAME = "agent-factory-convoy-advance.pass"


def lock_dir() -> Path:
    return Path(os.environ.get("CONVOY_ADVANCE_LOCK_DIR") or os.environ.get("XDG_RUNTIME_DIR") or "/tmp")


def mark_started(now: float | None = None) -> None:
    """Called by the holder of the lock, once it holds it."""
    path = lock_dir() / PASS_NAME
    staged = path.with_name(f"{PASS_NAME}.{os.getpid()}")
    staged.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now)) + "\n",
                      encoding="utf-8")
    os.replace(staged, path)


def mark_ended() -> None:
    (lock_dir() / PASS_NAME).unlink(missing_ok=True)


def started() -> float | None:
    """The start of the pass in flight, or None when none is recorded."""
    try:
        text = (lock_dir() / PASS_NAME).read_text(encoding="utf-8").strip()
        return float(calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")))
    except (OSError, ValueError):
        return None
