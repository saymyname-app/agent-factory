"""Host-wide admission for products launched by the two evaluation flows.

The launch record is the durable occupancy marker. project-launch writes it
before spawning and removes it only after its descendants, port and worktree
are confirmed gone. A short reservation covers the interval before that
record exists. The same lock serializes admission across both flows.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


LIMIT = 2


class Busy(RuntimeError):
    pass


def state_roots() -> tuple[Path, Path]:
    home = Path.home() / ".local" / "state"
    return (
        Path(os.environ.get("TICKET_EVALUATION_STATE_DIR") or home / "agent-factory-evaluation"),
        Path(os.environ.get("OUTCOME_EVALUATION_STATE_DIR") or home / "agent-factory-outcome-evaluation"),
    )


def capacity_dir() -> Path:
    return Path(os.environ.get("EVALUATION_CAPACITY_STATE_DIR") or
                Path.home() / ".local" / "state" / "agent-factory-product-capacity")


def occupied() -> list[Path]:
    """A failed stop deliberately keeps its record and therefore its slot."""
    found: set[Path] = set()
    for root in state_roots():
        if root.is_dir():
            found.update(root.rglob("*.json"))
            found.update(root.rglob("*.trial"))
    return sorted(found)


@contextmanager
def admission(state_file: Path) -> Iterator[int]:
    """Reserve one of two host slots before project-launch can spawn.

    Hold the lock through startup. A crash after project-launch writes its
    provisional record leaves that record counted; a crash before it writes
    one leaves no process to recover. Stale reservations are retired under
    the lock on the next admission.
    """
    directory = capacity_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for stale in directory.glob("*.reservation"):
            # No live holder can leave a reservation while we own the lock.
            # The provisional record either owns that slot or no product
            # was spawned. project-launch guarantees this ordering.
            stale.unlink(missing_ok=True)
        if len(occupied()) >= LIMIT:
            raise Busy(f"capacité des produits d'évaluation atteinte ({LIMIT} sur l'hôte)")
        reservation = directory / f"{uuid.uuid4().hex}.reservation"
        reservation.write_text(json.dumps({"state_file": str(state_file)}), encoding="utf-8")
        try:
            # The detached launcher inherits this lock. If the caller dies
            # before its provisional record exists, the launcher still holds
            # admission until it exits and its record owns the slot.
            yield lock.fileno()
        finally:
            reservation.unlink(missing_ok=True)
            fcntl.flock(lock, fcntl.LOCK_UN)


def product_running(record: dict) -> bool:
    """Only reuse a live product that owns its recorded listening port."""
    try:
        launch_id = record["launch_id"]
        worktree = Path(record["worktree"])
        port = int(record["port"])
        commit = record["commit"]
        address = record["address"]
        if not (isinstance(launch_id, str) and launch_id and worktree.is_dir()
                and isinstance(commit, str) and address == f"http://127.0.0.1:{port}"):
            return False
        # A reused PID alone proves nothing. Every descendant inherits this
        # unique environment marker, even if it moved into another group.
        owned = []
        marker = f"FACTORY_LAUNCH_ID={launch_id}".encode()
        for environ in Path("/proc").glob("[0-9]*/environ"):
            try:
                if marker in environ.read_bytes().split(b"\0"):
                    owned.append(environ.parent)
            except OSError:
                continue
        if not owned:
            return False
        # Match the listening socket to one of those descendants. A stranger
        # that happened to acquire the old port cannot become our product.
        listeners = set()
        for table in ("/proc/net/tcp", "/proc/net/tcp6"):
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                if int(fields[1].split(":")[1], 16) == port and fields[3] == "0A":
                    listeners.add(f"socket:[{fields[9]}]")
        if not listeners:
            return False
        owns_port = False
        for proc in owned:
            try:
                for fd in proc.joinpath("fd").iterdir():
                    try:
                        if os.readlink(fd) in listeners:
                            owns_port = True
                            break
                    except OSError:
                        continue
            except OSError:
                continue
            if owns_port:
                break
        if not owns_port:
            return False
        # The worktree is the isolated copy of the exact commit requested.
        checked = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"],
                                 text=True, capture_output=True, timeout=5)
        return checked.returncode == 0 and checked.stdout.strip() == commit
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
        return False
