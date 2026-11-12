#!/usr/bin/env python3
"""Criterion test of R23 (af-ujme6p; Spec af-fgcw0d, Testing Decisions 1, 3
and 8): a launch whose owner is another launch stops when that launch is
stopped, so the regression of the cockpit leaves nothing alive.

The regression of integration/af-fgcw0d was red on 12/11/2026 for one
reason only: its reaper found a cockpit on home-content still running when
`tests/cockpit-criteria-test.py` ended. That cockpit was the product Essai
launches (the synthetic `acceptance-session open --trial`, A2): a launch of
`bin/project-launch` made by the cockpit under test, with that cockpit as
its owner (`--owner-pid`). The case stopped its cockpit; the product it had
launched lived on.

The case goes through `bin/project-launch` only, as a launcher and as what
a launched product calls, on a disposable product repository holding the
Delivery Fixture City (its app is the product of the second launch) and a
first product, `outer.py`, written here: once started, it launches the
Fixture City with itself as owner, as the cockpit does through Essai, and
serves the address it got at GET /. The case stops the first launch with
`bin/project-launch stop`, then reads the address of the second.

False if the second launch still answers once the first is stopped and the
launcher has had the time to see its owner gone.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "bin" / "project-launch"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
# How long the launcher may take to see that the owner of a launch has ended
# and stop it: its guard reads the owner every second, and a stop gives the
# product 5 s to end on SIGTERM.
OWNER_ENDED_SECONDS = 20

# The first product: it launches the second with itself as owner, as the
# cockpit launches the product of Essai, and serves the address it got.
OUTER = r'''
import argparse, json, os, subprocess, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int)
parser.add_argument("--dataset")
args = parser.parse_args()
said = json.load(open(args.dataset, encoding="utf-8"))
started = subprocess.run(
    [sys.executable, said["launcher"], "--repo-root", said["repo"], "start", "--owner-pid", str(os.getpid()),
     said["descriptor"], "--commit", "HEAD", "--dataset", "content", "--state-file", said["state"],
     "--timeout", "30"],
    capture_output=True, text=True, stdin=subprocess.DEVNULL)
answer = started.stdout.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        body = b'{"status": "ok"}' if self.path == "/health" else answer
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
'''


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], env=GIT_ENV, check=True, text=True,
                          capture_output=True).stdout.strip()


def answers(address: str) -> bool:
    try:
        with urllib.request.urlopen(address + "/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return False


class LaunchOwnedByALaunch(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="launch-owned-by-a-launch-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.env = {**os.environ, "FACTORY_LAUNCH_TRACE": str(self.work / "stops.jsonl")}
        self.product = self.work / "product"
        shutil.copytree(ROOT / FIXTURE, self.product / FIXTURE)
        inner = self.product / FIXTURE / "descriptor.json"
        self.inner_state = self.work / "inner-launch.json"
        self.outer_state = self.work / "outer-launch.json"
        descriptor = json.loads(inner.read_text(encoding="utf-8"))
        descriptor["launch"]["recipe"] = ["{python}", "outer.py", "--port", "{port}", "--dataset", "{dataset}"]
        descriptor["launch"]["datasets"] = {"outer": "outer.json"}
        descriptor["launch"]["screens"] = [{"name": "accueil", "path": "/", "states": ["outer"]}]
        (self.product / "outer-descriptor.json").write_text(json.dumps(descriptor), encoding="utf-8")
        (self.product / "outer.py").write_text(OUTER, encoding="utf-8")
        (self.product / "outer.json").write_text(json.dumps({
            "launcher": str(LAUNCHER), "repo": str(self.product), "descriptor": str(inner),
            "state": str(self.inner_state),
        }), encoding="utf-8")
        git(self.product, "init", "-q", "-b", "main")
        git(self.product, "add", "-A")
        git(self.product, "-c", "user.name=criterion", "-c", "user.email=criterion@example.invalid",
            "commit", "-q", "-m", "two products")
        # Whatever the case leaves, its launches end with it: the second
        # first, as its owner may already be gone.
        for state in (self.outer_state, self.inner_state):
            self.addCleanup(self.stop, state)

    def stop(self, state: Path) -> subprocess.CompletedProcess:
        if not state.exists():
            return subprocess.CompletedProcess([], 0, json.dumps({"stopped": True}), "")
        return subprocess.run([sys.executable, str(LAUNCHER), "stop", "--state-file", str(state)],
                              env=self.env, text=True, capture_output=True, stdin=subprocess.DEVNULL)

    def test_a_launch_owned_by_a_stopped_launch_stops_with_it(self):
        started = subprocess.run(
            [sys.executable, str(LAUNCHER), "--repo-root", str(self.product), "start", "--owner-pid",
             str(os.getpid()), str(self.product / "outer-descriptor.json"), "--commit", "HEAD",
             "--dataset", "outer", "--state-file", str(self.outer_state), "--timeout", "60"],
            env=self.env, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        outer = json.loads(started.stdout)
        self.assertTrue(outer.get("started"), started.stdout + started.stderr)
        with urllib.request.urlopen(outer["address"] + "/", timeout=10) as response:
            inner = json.loads(response.read().decode("utf-8"))
        self.assertTrue(inner.get("started"), f"the first product did not launch the second: {inner}")
        self.assertTrue(answers(inner["address"]), f"the second product does not answer at {inner['address']}")

        stopped = self.stop(self.outer_state)
        self.assertEqual(json.loads(stopped.stdout).get("stopped"), True, stopped.stdout + stopped.stderr)
        self.assertFalse(answers(outer["address"]), "the first product still answers once stopped")

        deadline = time.monotonic() + OWNER_ENDED_SECONDS
        while answers(inner["address"]) and time.monotonic() < deadline:
            time.sleep(0.5)
        self.assertFalse(
            answers(inner["address"]),
            f"the product launched by the first one still answers at {inner['address']} "
            f"{OWNER_ENDED_SECONDS} s after its owner was stopped")


if __name__ == "__main__":
    unittest.main()
