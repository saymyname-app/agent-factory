#!/usr/bin/env python3
"""Stop criteria of the stepped author-ceiling trial (af-2se8y2 §7). Read-only
except one timed run of a reference test. Run it every 30 min of the trial:

    trial_check.py SAMPLES START_EPOCH BASELINE_PROBE_S [--probe]

Prints one JSON verdict: `stop` true as soon as one criterion is met. It
never changes N: rolling back is the revert of the trial pull request.
"""
import calendar, json, subprocess, sys, time
from pathlib import Path

ROOT = Path.home() / "agent-factory"
PROBE = ["python3", "tests/project-launch-test.py"]  # ≈ 37 s at N=2 (16/10)
PSI_LIMIT, PSI_WINDOW = 75.0, 1800  # % of CPU "some", over the last 30 min
PROBE_LIMIT = 1.5  # × its duration at N=2
CONVOY = "af-pqfxmd"


def psi_last(samples: Path, window: int) -> float | None:
    rows = [json.loads(line) for line in samples.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r["ts"] >= time.time() - window]
    if len(rows) < 2:
        return None
    dt = rows[-1]["ts"] - rows[0]["ts"]
    key = "cpu_some_total_us"
    return 100 * (rows[-1]["psi"][key] - rows[0]["psi"][key]) / (dt * 1e6)


def stops_since(start: float) -> list[dict]:
    """Tickets stopped for a missing result (`*_no_result`) since the start."""
    proc = subprocess.run(["bin/convoy-state", "show", CONVOY], cwd=ROOT, capture_output=True, text=True)
    answer = json.loads(proc.stdout)
    found = []
    for ticket in answer.get("tickets", []):
        stop = ticket.get("stop") or {}
        reason, at = str(stop.get("reason", "")), stop.get("at")
        if reason.endswith("no_result") and at and calendar.timegm(time.strptime(at[:19], "%Y-%m-%dT%H:%M:%S")) >= start:
            found.append({"ticket": ticket.get("id"), "reason": reason, "at": at})
    return found


def conflicts_since(start: float) -> int:
    log = ROOT / ".gc/runtime/overlap-conflict-log.jsonl"
    if not log.exists():
        return 0
    return sum(1 for line in log.read_text().splitlines()
               if line.strip() and json.loads(line).get("kind") == "conflict" and json.loads(line).get("ts", 0) >= start)


def probe() -> float:
    t0 = time.monotonic()
    subprocess.run(PROBE, cwd=ROOT, capture_output=True)
    return time.monotonic() - t0


def main() -> int:
    samples, start, baseline = Path(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    psi = psi_last(samples, PSI_WINDOW)
    seconds = probe() if "--probe" in sys.argv else None
    stops, conflicts = stops_since(start), conflicts_since(start)
    criteria = {
        "psi_cpu_30min": {"value": psi, "limit": PSI_LIMIT, "met": psi is not None and psi > PSI_LIMIT},
        "probe_seconds": {"value": seconds, "limit": round(PROBE_LIMIT * baseline, 1),
                          "met": seconds is not None and seconds > PROBE_LIMIT * baseline},
        "no_result_stops": {"value": stops, "met": bool(stops)},
        "git_conflicts": {"value": conflicts, "met": conflicts > 0},
    }
    print(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "stop": any(c["met"] for c in criteria.values()),
                      "criteria": criteria}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
