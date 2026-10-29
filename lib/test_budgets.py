#!/usr/bin/env python3
"""The time budgets of the tests of a ticket, in one file measured from real
runs (study C, T3, af-npz9v1.32; docs/research/2026-10-22-strategie-tests-
budgets.md § 4).

    test_budgets.py show    [--root DIR] [--store DIR]
    test_budgets.py refresh [--root DIR] [--store DIR]
    test_budgets.py check-order [--root DIR]

Until 27/10/2026 three deadlines were written by hand in three places
(600 s in bin/tdd-step, 600 s in bin/spec-integration, 30 min for the order
convoy-advance), tied to nothing measured; the series grew with each ticket
and green tickets were refused at 600 s. Now `config/test-budgets.json` holds
them all, and every reader takes them from here:

- `host_wait_seconds`: how long the cockpit's regression waits for the host
  lock (tests/cockpit-criteria/regression.py);
- `green_seconds` / `full_seconds`: its budget once the lock is held, at a
  ticket's green (the ticket's families, study C T4) and for the whole series
  (a merge, a take-up, prefactoring);
- `criterion_test_seconds`: one criterion test run by bin/tdd-step;
- `margin_seconds`, `alert_ratio`.

`refresh` sets `green_seconds` and `full_seconds` to 1.5 times the slowest of
the last ten successful runs of each kind found in the evidence store (the line
« regression: took Ns » the regression prints, or for older merged runs its
per-file seconds), rounded up to the minute; a kind with fewer than three
runs keeps its figure. `show` prints the budgets, the deadlines derived from
them, the last runs and how many more criterion classes the full series holds
before its alert. `check-order` exits 1 when the order convoy-advance gives
a pass less than one wait and two full runs (a take-up control, then the
tests of the merged result).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = Path("config") / "test-budgets.json"
ORDER = Path("orders") / "convoy-advance.toml"
DEFAULTS = {"host_wait_seconds": 600, "green_seconds": 600, "full_seconds": 600, "criterion_test_seconds": 600,
            "margin_seconds": 60, "alert_ratio": 0.8}
# Anywhere in the output: a green piece holds it inside the JSON answer of
# bin/tdd-step, a merged piece on a line of its own.
TOOK = re.compile(r"regression: took (\d+)s [^\n\"]*\((green|full)\b")
FILE_LINE = re.compile(r"^(?:PASS|FAIL|LATE) (\S+) \((\d+)s\)", re.MULTILINE)
JOBS = 4  # the files run 4 at a time before the criterion tests (regression.py)
CRITERIA = "tests/cockpit-criteria-test.py"


def load(root: Path = ROOT) -> dict:
    """The budgets of `root`, the defaults for a field it lacks."""
    try:
        data = json.loads((root / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **{key: data[key] for key in DEFAULTS if isinstance(data.get(key), (int, float))}}


def deadline(budgets: dict, kind: str) -> int:
    """What a caller gives one run of the regression: the wait, the budget of
    its kind and the margin."""
    return int(budgets["host_wait_seconds"] + budgets[f"{kind}_seconds"] + budgets["margin_seconds"])


def pass_seconds(budgets: dict) -> int:
    """One pass of convoy-advance: one wait, two full runs, two margins."""
    return int(budgets["host_wait_seconds"] + 2 * budgets["full_seconds"] + 2 * budgets["margin_seconds"])


def runs(store: Path) -> list[dict]:
    """Every regression run the evidence store records, oldest first:
    {kind, seconds, at, commit}."""
    found = []
    for path in store.glob("*/*/*.json"):
        if path.name not in ("merged_tests.json", "tdd_green.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if path.name == "merged_tests.json" and str(record.get("exit_code")) != "0":
            continue
        output = record.get("output") or ""
        took = TOOK.findall(output)
        if took:
            for seconds, kind in took:
                found.append({"kind": kind, "seconds": int(seconds), "at": record.get("at", ""),
                              "commit": record.get("commit")})
        elif path.name == "merged_tests.json" and str(record.get("exit_code")) == "0":
            lines = FILE_LINE.findall(output)
            if any(name == CRITERIA for name, _ in lines):
                others = sum(int(s) for name, s in lines if name != CRITERIA)
                criteria = sum(int(s) for name, s in lines if name == CRITERIA)
                found.append({"kind": "full", "seconds": math.ceil(others / JOBS) + criteria,
                              "at": record.get("at", ""), "commit": record.get("commit"), "estimated": True,
                              "criteria": criteria})
    return sorted(found, key=lambda run: run["at"])


def budget_of(seconds: list[int]) -> int:
    return 60 * math.ceil(1.5 * max(seconds) / 60)


def refreshed(budgets: dict, found: list[dict]) -> dict:
    new = dict(budgets)
    for kind in ("green", "full"):
        last = [run["seconds"] for run in found if run["kind"] == kind][-10:]
        if len(last) >= 3:
            new[f"{kind}_seconds"] = budget_of(last)
    return new


def classes_at(repo: Path, commit: str | None) -> int | None:
    if not commit:
        return None
    listed = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", commit,
                             "tests/cockpit-criteria/commands/"], capture_output=True, text=True)
    if listed.returncode != 0:
        return None
    count = 0
    for name in (n for n in listed.stdout.split() if n.endswith("-test.py")):
        shown = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{name}"], capture_output=True, text=True)
        count += len(re.findall(r"^class \w+\([^)]*\):", shown.stdout, re.MULTILINE))
    return count


def headroom(budgets: dict, found: list[dict], repo: Path) -> dict | None:
    """Seconds a criterion class adds to the full series (fitted on the
    merged runs), and how many more classes it holds before its alert."""
    points = [(classes_at(repo, run["commit"]), run["criteria"]) for run in found if "criteria" in run][-10:]
    points = [(x, y) for x, y in points if x]
    if len({x for x, _ in points}) < 2:
        return None
    slope, _ = statistics.linear_regression([x for x, _ in points], [y for _, y in points])
    last = [run["seconds"] for run in found if run["kind"] == "full"][-1]
    room = budgets["alert_ratio"] * budgets["full_seconds"] - last
    return {"seconds_per_class": round(slope, 1), "last_full_seconds": last,
            "classes_before_alert": math.floor(room / slope) if slope > 0 else None}


def order_seconds(root: Path) -> int | None:
    match = re.search(r'^timeout\s*=\s*"(\d+)m"', (root / ORDER).read_text(encoding="utf-8"), re.MULTILINE)
    return int(match.group(1)) * 60 if match else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="test-budgets")
    parser.add_argument("command", choices=("show", "refresh", "check-order"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--store", type=Path)
    args = parser.parse_args(argv)
    budgets = load(args.root)
    if args.command == "check-order":
        order, needed = order_seconds(args.root), pass_seconds(budgets)
        ok = order is not None and order >= needed
        print(json.dumps({"ok": ok, "order_seconds": order, "pass_seconds": needed}))
        return 0 if ok else 1
    sys.path.insert(0, str(ROOT / "lib"))
    from account_home import account_home  # noqa: E402
    store = args.store or account_home() / ".local" / "state" / "agent-factory-evidence"
    found = runs(store)
    if args.command == "refresh":
        new = refreshed(budgets, found)
        (args.root / FILE).write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "before": budgets, "after": new}, indent=2))
        return 0
    print(json.dumps({
        "budgets": budgets,
        "deadlines": {"green": deadline(budgets, "green"), "full": deadline(budgets, "full"),
                      "pass": pass_seconds(budgets), "order": order_seconds(args.root)},
        "last_runs": found[-6:],
        "headroom": headroom(budgets, found, args.root),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
