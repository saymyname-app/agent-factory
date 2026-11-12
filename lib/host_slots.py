#!/usr/bin/env python3
"""One host-wide limit for every heavy test run: a pool of N slots (af-lsbqj9).

    host_slots.py run --label TEXT [--wait SECONDS] -- COMMAND...
    host_slots.py show
    host_slots.py held      # exit 0 in a slot holder's turn

From 08 to 11/11/2026 nine pull requests turned healthy tools red under a
load of 30 to 100 on 8 CPUs, and budgets were raised three times. Each fix
bounded one tool: bin/ci-run-tests took a lock for one battery at a time
(af-7m7ymg), the products of the two evaluations were capped at two (PR 561,
af-5rx5mu), and nothing bounded the rest: on 11/11 at 20:32 Paris tdd-step
trees, three project-launch copies and a spec-integration regression ran
beside each other, none through the lock. The lock lived in /tmp, which
bin/delivery-role-sandbox replaces with a tmpfs: a sandboxed role never saw it.

Now every heavy run takes one slot of this pool, here and nowhere else:
bin/ci-run-tests, the Cockpit regression, bin/tdd-step, bin/spec-integration,
the tools that launch a product with an owner, and bin/project-launch for a
product that outlives its caller (its guard holds the slot). The products of
the two evaluations hold theirs by their launch record, which survives the
pass (lib/evaluation_capacity.py): a record still alive counts in the pool.

- The pool has as many cores as the host has processors (HOST_SLOTS sets
  it). A test run takes `cores_per_run` of them and a product
  `cores_per_product`, from config/host-slots.json, which says what was
  measured: on 8 processors, two test runs, or one and two products.
- A share is one lock file per core, held by flock: it goes when its
  holder ends, however it ends. A run started by a slot holder
  (HOST_SLOT_HELD, inherited) takes none: it runs in its parent's turn,
  and never waits on itself.
- Waiting is not a failure and is no part of a budget: a tool takes its slot
  first, then starts its clock. Past its wait it says NOT RUN (exit 75).
- On a GitHub runner (one run per machine) a run takes no slot.

The pool lives in ~/.local/state, writable inside the sandbox. A test that
isolates its evaluations (EVALUATION_CAPACITY_STATE_DIR) isolates its pool
with them; HOST_SLOTS_DIR names a bare pool, without the evaluations'
records, for a test of the runs alone.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from account_home import account_home  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "host-slots.json"
NOT_RUN = 75
DEFAULT_WAIT = 5400
HELD = "HOST_SLOT_HELD"
# A slot taken by a caller and handed to bin/project-launch, whose guard
# keeps it for the life of the product.
HANDED = "HOST_SLOT_FD"


class Busy(RuntimeError):
    """No slot is free now."""


class NotRun(RuntimeError):
    """No slot came free within the wait."""


def directory() -> Path:
    if os.environ.get("HOST_SLOTS_DIR"):
        return Path(os.environ["HOST_SLOTS_DIR"])
    capacity = os.environ.get("EVALUATION_CAPACITY_STATE_DIR")
    base = Path(capacity) if capacity else account_home() / ".local" / "state" / "agent-factory-product-capacity"
    return base / "host-slots"


RUN, PRODUCT = "run", "product"


def costs() -> dict[str, int]:
    """The cores a test run and a product take, from config/host-slots.json."""
    known = {RUN: 4, PRODUCT: 2}
    try:
        written = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return known
    for kind, key in ((RUN, "cores_per_run"), (PRODUCT, "cores_per_product")):
        value = written.get(key) if isinstance(written, dict) else None
        if isinstance(value, int) and value > 0:
            known[kind] = value
    return known


def capacity() -> int:
    """The cores of the pool: the host's processors, or HOST_SLOTS."""
    override = os.environ.get("HOST_SLOTS", "")
    if override:
        if not override.isdigit() or int(override) < 1:
            raise ValueError(f"HOST_SLOTS wants a number of slots (1 or more), got: {override}")
        return int(override)
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def weight(kind: str) -> int:
    """What one `kind` takes of the pool; never more than the whole pool."""
    return min(costs()[kind], capacity())


def inherited() -> bool:
    return os.environ.get(HELD) == str(directory())


def durable() -> list[Path]:
    """Launch records of the evaluations' products still alive: each holds a
    product's share between passes, with no process of the pass to hold a lock. A bare
    pool a test names (HOST_SLOTS_DIR) holds none of them."""
    if os.environ.get("HOST_SLOTS_DIR"):
        return []
    from evaluation_capacity import occupied
    return occupied()


def _held(pool: Path) -> tuple[list[int], list[int]]:
    """The slot files held by someone, and those free (probed, then let go)."""
    held, free = [], []
    for index in range(capacity()):
        with (pool / f"slot-{index}.lock").open("a") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(index)
                continue
            fcntl.flock(probe, fcntl.LOCK_UN)
            free.append(index)
    return held, free


def holders() -> list[str]:
    """Who holds the pool now: each holder once, then each product record."""
    pool = directory()
    if not pool.is_dir():
        return []
    with _pool_lock(pool):
        held, _ = _held(pool)
    lines: list[str] = []
    for index in held:
        try:
            line = (pool / f"slot-{index}.holder").read_text(encoding="utf-8").strip() or "another session"
        except OSError:
            line = "another session"
        if line not in lines:
            lines.append(line)
    lines += [f"an evaluation product ({path.name})" for path in durable()]
    return lines


@contextmanager
def _pool_lock(pool: Path) -> Iterator[None]:
    """Counting and taking a slot is one step (held for milliseconds)."""
    with (pool / "pool.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Slot:
    """The lock files one holder holds: one per core of its weight."""

    def __init__(self, handles, pool: Path):
        self.handles, self.pool = handles, pool

    @property
    def fds(self) -> tuple[int, ...]:
        return tuple(handle.fileno() for handle in self.handles)

    def release(self) -> None:
        for handle in self.handles:
            if not handle.closed:
                handle.close()


def try_take(label: str, kind: str = RUN) -> Slot:
    """The share of a `kind` now, or Busy. `label` names the holder to those
    who wait. A product record counts as one product's share."""
    pool = directory()
    pool.mkdir(parents=True, exist_ok=True)
    need = weight(kind)
    with _pool_lock(pool):
        held, free = _held(pool)
        taken = len(held) + len(durable()) * weight(PRODUCT)
        if taken + need > capacity() or len(free) < need:
            raise Busy(f"{min(taken, capacity())} of the {capacity()} cores of the host pool taken, "
                       f"{need} wanted for a {kind}")
        handles = []
        for index in free[:need]:
            handle = (pool / f"slot-{index}.lock").open("a")
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            handles.append(handle)
            try:
                (pool / f"slot-{index}.holder").write_text(
                    f"{label} (pid {os.getpid()}, since {time.strftime('%H:%M')})\n", encoding="utf-8")
            except OSError:
                pass
    return Slot(handles, pool)


def take(label: str, wait: float = DEFAULT_WAIT, say=None, mark: bool = True, kind: str = RUN) -> Slot | None:
    """A slot for this run, waiting its turn at most `wait` seconds (NotRun
    past it). None where none is taken: a GitHub runner, or a run inside a
    slot holder's turn. `say` gets a line every 30 s of the wait. The slot
    marks the environment, so what this run starts runs in its turn; a slot
    taken to be handed over (`handed`) does not (`mark=False`)."""
    if os.environ.get("GITHUB_ACTIONS") == "true" or inherited():
        return None
    started, said = time.monotonic(), None
    while True:
        try:
            slot = try_take(label, kind)
            break
        except Busy as busy:
            waited = time.monotonic() - started
            who = "; ".join(holders()) or "another session"
            if waited >= wait:
                raise NotRun(f"{busy} after {waited:.0f}s of waiting (at most {wait:g}s), held by: {who}") from None
            if say and (said is None or waited - said >= 30):
                say(f"waiting for a host slot ({busy}, held by: {who}); waited {waited:.0f}s of at most {wait:g}s")
                said = waited
            time.sleep(1)
    if mark:
        os.environ[HELD] = str(slot.pool)
    return slot


_PROCESS_SLOT: list[Slot] = []


def hold(label: str, wait: float = DEFAULT_WAIT, say=None) -> None:
    """Take a slot for the rest of this process (once); it goes when the
    process ends. For a tool whose products and tests all run in one turn."""
    if _PROCESS_SLOT:
        return
    slot = take(label, wait, say)
    if slot:
        _PROCESS_SLOT.append(slot)


def adopt_handed() -> Slot | None:
    """The share a caller handed this process (HOST_SLOT_FD), already held."""
    raw = os.environ.pop(HANDED, "")
    try:
        handles = [os.fdopen(int(fd), "a") for fd in raw.split(",") if fd]
    except (ValueError, OSError):
        return None
    if not handles:
        return None
    os.environ[HELD] = str(directory())
    return Slot(handles, directory())


@contextmanager
def handed(slot: Slot | None) -> Iterator[tuple[int, ...]]:
    """While inside, a child started with the yielded pass_fds receives
    `slot` (bin/project-launch hands it to its guard). Without a slot,
    nothing is handed."""
    if slot is None:
        yield ()
        return
    previous = os.environ.get(HANDED)
    os.environ[HANDED] = ",".join(str(fd) for fd in slot.fds)
    try:
        yield slot.fds
    finally:
        if previous is None:
            os.environ.pop(HANDED, None)
        else:
            os.environ[HANDED] = previous


def cmd_run(args: argparse.Namespace) -> int:
    """Run COMMAND in a slot, then let the slot go. The command runs in a
    session of its own that dies with this process; a signal to this
    process ends it too."""
    import bounded_process

    def say(line: str) -> None:
        print(f"{args.name}: {line}", file=sys.stderr, flush=True)

    try:
        slot = take(args.label, args.wait, say)
    except NotRun as exc:
        print(f"{args.name}: NOT RUN -- {exc}. Nothing ran: this is not a test failure. Start it again later.",
              file=sys.stderr, flush=True)
        return NOT_RUN
    child = bounded_process.popen(args.command)

    def stop(signum, _frame):
        bounded_process.kill_group(child)
        sys.exit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, stop)
    status = child.wait()
    bounded_process.release(child)
    if slot:
        slot.release()
    return status


def cmd_held(_args: argparse.Namespace) -> int:
    """Exit 0 when this run is in a slot holder's turn: it takes none."""
    return 0 if inherited() else 1


def cmd_show(_args: argparse.Namespace) -> int:
    print(json.dumps({"directory": str(directory()), "cores": capacity(),
                      "weights": {kind: weight(kind) for kind in (RUN, PRODUCT)},
                      "holders": holders()}, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="host_slots.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--label", required=True)
    p.add_argument("--name", default="host-slots", help="prefix of the lines it says")
    p.add_argument("--wait", type=float, default=DEFAULT_WAIT)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(handler=cmd_run)
    sub.add_parser("show").set_defaults(handler=cmd_show)
    sub.add_parser("held").set_defaults(handler=cmd_held)
    args = parser.parse_args(argv)
    if args.cmd == "run":
        if args.command[:1] == ["--"]:
            args.command = args.command[1:]
        if not args.command:
            parser.error("run wants a COMMAND after --")
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
