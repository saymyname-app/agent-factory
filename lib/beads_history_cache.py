#!/usr/bin/env python3
"""Print the whole Beads history of a store, read whole once a day and
otherwise only what changed since the last read.

    beads_history_cache.py --cache FILE [--full-every S] [--margin S] [--timeout S] -- CMD...

CMD is the whole-history read (`gc bd list --all --limit 0 --json`), run in
the current directory. Without a cache, a cache read whole more than
--full-every seconds ago (default one day), or one that cannot be read, CMD
runs as given. Otherwise CMD runs with `--updated-after <start of the last
read, less --margin>` and its beads replace those of the cache by id. The
merged list is printed as one JSON array, and the cache is rewritten
(atomically) only after a read that succeeded. A read that fails or prints
no JSON array prints nothing, leaves the cache as it was and exits non-zero,
with the read's own code when it has one (124 for a cut read): the caller
treats it as it did the whole read.

Why (af-tdpbg1): bin/pr-autopilot read the whole history of each rig on
every 3-minute pass -- the last 30 merged PRs are never none --, 14 610
beads and 60 MB of JSON in 20 s for the HQ store on 2026-11-20, 34 % of
what Dolt sent to its clients over 15 minutes of measure. The same read
limited to the last 15 minutes took 4 s and held one bead.

A deleted bead stays in the cache until the next whole read; a whole read
also follows any change of CMD, so a cache never mixes two stores.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from bounded_process import run as bounded_run


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: str, command: list[str]) -> dict | None:
    try:
        with open(path, encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, ValueError):
        return None
    if (not isinstance(cache, dict) or cache.get("command") != command
            or not isinstance(cache.get("beads"), list)
            or not all(isinstance(cache.get(k), (int, float)) for k in ("full_at", "read_at"))):
        return None
    return cache


def _read(command: list[str], timeout: float | None) -> tuple[list | None, int]:
    """The beads CMD prints, or None and the exit code to leave with: the
    read's own when it failed (124, a cut read, stays one for the caller)."""
    try:
        proc = bounded_run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, 124
    except OSError:
        return None, 1
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return None, proc.returncode
    try:
        beads = json.loads(proc.stdout or "null")
    except ValueError:
        return None, 1
    return (beads, 0) if isinstance(beads, list) else (None, 1)


def _write(path: str, cache: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".beads-history.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", required=True)
    parser.add_argument("--full-every", type=float, default=86400.0)
    parser.add_argument("--margin", type=float, default=600.0)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a read command is required after --")

    started = time.time()
    cache = _load(args.cache, command)
    if cache is not None and started - cache["full_at"] < args.full_every:
        changed, code = _read(command + ["--updated-after", _iso(cache["read_at"] - args.margin)], args.timeout)
        if changed is None:
            return code
        index = {bead.get("id"): i for i, bead in enumerate(cache["beads"]) if isinstance(bead, dict)}
        beads = list(cache["beads"])
        for bead in changed:
            if not isinstance(bead, dict) or not bead.get("id"):
                continue
            if bead["id"] in index:
                beads[index[bead["id"]]] = bead
            else:
                index[bead["id"]] = len(beads)
                beads.append(bead)
        full_at = cache["full_at"]
    else:
        beads, code = _read(command, args.timeout)
        if beads is None:
            return code
        full_at = started

    sys.stdout.write(json.dumps(beads, separators=(",", ":")))
    sys.stdout.flush()
    try:
        _write(args.cache, {"command": command, "full_at": full_at, "read_at": started, "beads": beads})
    except OSError as exc:
        # The answer is whole; the next pass only reads more.
        sys.stderr.write(f"beads_history_cache: cache not written: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
