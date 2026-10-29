"""Host-wide admission for products launched by the two evaluation flows.

The launch record is the durable occupancy marker. project-launch writes it
before spawning and removes it only after its descendants, port and worktree
are confirmed gone. A short reservation covers the interval before that
record exists. The same lock serializes admission across both flows.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


LIMIT = 2


def launch_timeout(settings: dict, datasets: int) -> int:
    """How long one evaluation launch may take: the floor `timeout_seconds`,
    or `per_dataset_seconds` for each dataset the evaluation covers when that
    is longer (af-vtg5kl). The Ticket and the Outcome Evaluation share it."""
    return max(settings["timeout_seconds"], datasets * settings.get("per_dataset_seconds", 0))


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


def launch_fully_gone(path: Path) -> bool:
    """A valid launch record whose process group, descendants and copy are all gone."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        launch_id = record["launch_id"]
        pid = int(record["pid"])
        process_group = int(record["process_group"])
        worktree = Path(record["worktree"])
        if not isinstance(launch_id, str) or not launch_id or pid <= 0 or process_group <= 0:
            return False
    except (KeyError, TypeError, ValueError, OSError):
        return False
    if Path(f"/proc/{pid}").exists() or worktree.exists():
        return False
    try:
        os.killpg(process_group, 0)
        return False
    except PermissionError:
        return False
    except ProcessLookupError:
        pass
    except OSError:
        return False
    marker = f"FACTORY_LAUNCH_ID={launch_id}".encode()
    for environ in Path("/proc").glob("[0-9]*/environ"):
        try:
            if marker in environ.read_bytes().split(b"\0"):
                return False
        except OSError:
            continue
    return True


def occupied() -> list[Path]:
    """A failed stop keeps its slot unless every owned process and copy is proven gone."""
    found: set[Path] = set()
    for root in state_roots():
        if root.is_dir():
            found.update(root.rglob("*.json"))
            found.update(root.rglob("*.trial"))
    return sorted(path for path in found if not launch_fully_gone(path))


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


def listening_sockets(port: int) -> set[str]:
    listeners = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in Path(table).read_text().splitlines()[1:]:
            fields = line.split()
            if int(fields[1].split(":")[1], 16) == port and fields[3] == "0A":
                listeners.add(f"socket:[{fields[9]}]")
    return listeners


def product_socket(record: dict) -> str | None:
    """Identify a listener owned by this exact launch and commit."""
    try:
        launch_id = record["launch_id"]
        worktree = Path(record["worktree"])
        port = int(record["port"])
        commit = record["commit"]
        address = record["address"]
        if not (isinstance(launch_id, str) and launch_id and worktree.is_dir()
                and isinstance(commit, str) and address == f"http://127.0.0.1:{port}"):
            return None
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
            return None
        # Match the listening socket to one of those descendants. A stranger
        # that happened to acquire the old port cannot become our product.
        listeners = listening_sockets(port)
        if not listeners:
            return None
        owned_socket = None
        for proc in owned:
            try:
                for fd in proc.joinpath("fd").iterdir():
                    try:
                        candidate = os.readlink(fd)
                        if candidate in listeners:
                            owned_socket = candidate
                            break
                    except OSError:
                        continue
            except OSError:
                continue
            if owned_socket:
                break
        if not owned_socket:
            return None
        # The worktree is the isolated copy of the exact commit requested.
        checked = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"],
                                 text=True, capture_output=True, timeout=5)
        return owned_socket if checked.returncode == 0 and checked.stdout.strip() == commit else None
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
        return None


def product_running(record: dict) -> bool:
    return product_socket(record) is not None


def attestation_dir() -> Path:
    return capacity_dir() / "attestations"


def attestation_path(state_file: str) -> Path:
    digest = hashlib.sha256(str(Path(state_file).resolve()).encode()).hexdigest()
    return attestation_dir() / f"{digest}.json"


def ready_product(state_file: str, record: dict) -> bool:
    """Controller attests the checked socket; sandbox verifies it still listens.

    The sandbox mounts attestations read-only over its writable state tree.
    A session created before that mount exists fails closed.
    """
    fields = ("started", "launch_id", "worktree", "repo_root", "commit",
              "dataset", "port", "address", "pid", "process_group")
    try:
        identity = {name: record[name] for name in fields}
        if identity["started"] is not True:
            return False
        path = attestation_path(state_file)
        if os.environ.get("DELIVERY_ROLE_SANDBOXED") == "1":
            if not os.statvfs(attestation_dir()).f_flag & os.ST_RDONLY:
                return False
            attested = json.loads(path.read_text(encoding="utf-8"))
            return (attested.get("state_file") == str(Path(state_file).resolve())
                    and attested.get("identity") == identity
                    and attested.get("socket") in listening_sockets(int(identity["port"]))
                    and identity["address"] == f"http://127.0.0.1:{identity['port']}")
        socket = product_socket(record)
        if socket is None:
            return False
        attestation_dir().mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps({"state_file": str(Path(state_file).resolve()),
                                   "identity": identity, "socket": socket}), encoding="utf-8")
        tmp.replace(path)
        return True
    except (KeyError, TypeError, ValueError, OSError):
        return False


def remove_attestation(state_file: str) -> None:
    attestation_path(state_file).unlink(missing_ok=True)
