#!/usr/bin/env python3
"""Criterion tests of the isolated cockpit launch (T01, af-oigubn; Spec
af-2zseit, user story 126).

They go through `bin/project-launch`, the launcher an author, the Evaluator
and the Acceptance Session all use, with the Factory's own profile
(`config/project-descriptors/agent-factory.json`), then through the address
the launcher announces. Nothing here reads the code of the cockpit.

The decor is a disposable Git repository holding the tree these tests run
in, with two commits: the tree as it is, then a HEAD where the dataset
`home-content` is no longer a synthetic one. A launch asked at the first
commit must serve the first commit.

What these cases prove that `tests/project-launch-test.py` does not: that
test proves the launcher on the recipe of the Delivery Fixture City, one
process and no dependency. These prove the recipe of the real cockpit: its
process, the synthetic sources it reads instead of the city in service, and
that none of them outlives `stop`.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = "bin/project-launch"
PROFILE = "config/project-descriptors/agent-factory.json"
# The ports of the city in service: its cockpit and its supervisor.
CITY_COCKPIT_PORT = 8173
CITY_SUPERVISOR_PORT = 8372
PR_SET_CHILD_SUBREAPER = 36  # <linux/prctl.h>


def git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
        "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, env=env
    ).stdout.strip()


def declared_dataset(repo: Path, name: str) -> str | None:
    """Where the profile of `repo` says the dataset `name` is, if it says so."""
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    return ((profile.get("launch") or {}).get("datasets") or {}).get(name)


def fetch(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def answers(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2).close()
    except (urllib.error.URLError, ConnectionError, OSError):
        return False
    return True


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


@contextlib.contextmanager
def adopting_orphans():
    """While this holds, a process a launch leaves behind becomes a child of
    this test process instead of the host's init, so `children()` names it."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) refused")
    try:
        yield
    finally:
        libc.prctl(PR_SET_CHILD_SUBREAPER, 0, 0, 0, 0)


def children() -> list[int]:
    """The live processes whose parent is this test process, and no other."""
    with contextlib.suppress(ChildProcessError):
        while os.waitpid(-1, os.WNOHANG)[0]:
            pass
    me, found = str(os.getpid()), []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if fields[1] == me and fields[0] != "Z":
            found.append(int(stat.parent.name))
    return sorted(found)


class IsolatedCockpitLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="cockpit-launch-criteria-"))
        cls.repo = cls.work / "repo"
        shutil.copytree(
            ROOT, cls.repo, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        git(cls.repo, "init", "--quiet", "--initial-branch", "main")
        git(cls.repo, "add", "--all", "--force")
        git(cls.repo, "commit", "--quiet", "--message", "the tree under test")
        cls.requested = git(cls.repo, "rev-parse", "HEAD")
        dataset = declared_dataset(cls.repo, "home-content")
        if dataset:
            (cls.repo / dataset).write_text(
                json.dumps({"generated_at": "2026-10-12T12:00:00+02:00", "synthetic": False}), encoding="utf-8"
            )
            git(cls.repo, "add", "--all")
        git(cls.repo, "commit", "--quiet", "--allow-empty", "--message", "home-content is no longer synthetic")
        cls.head = git(cls.repo, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def setUp(self) -> None:
        self.states: list[Path] = []

    def tearDown(self) -> None:
        for state in self.states:
            if state.exists():
                self.stop(state)

    def start(self, commit: str, dataset: str) -> tuple[dict, Path]:
        state = self.work / f"launch-{self._testMethodName}-{len(self.states)}.json"
        self.states.append(state)
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "start", str(self.repo / PROFILE),
             "--commit", commit, "--dataset", dataset, "--state-file", str(state), "--timeout", "30"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        try:
            return json.loads(proc.stdout), state
        except json.JSONDecodeError:
            self.fail(f"bin/project-launch start answered no JSON (exit {proc.returncode}): {proc.stdout}{proc.stderr}")

    def stop(self, state: Path) -> dict:
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "stop", "--state-file", str(state)],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        return json.loads(proc.stdout)

    def status(self, address: str) -> dict:
        """GET /api/status, once the cockpit has read its supervisor."""
        deadline = time.monotonic() + 15
        while True:
            code, content_type, body = fetch(address + "/api/status")
            self.assertEqual(200, code)
            self.assertTrue(content_type.startswith("application/json"), content_type)
            snapshot = json.loads(body)
            if (snapshot.get("gc") or {}).get("value") or time.monotonic() > deadline:
                return snapshot
            time.sleep(0.2)

    # Criterion 1 ---------------------------------------------------------

    def test_start_serves_the_real_cockpit_at_the_requested_commit_on_the_named_dataset(self):
        record, _ = self.start(self.requested, "home-content")
        self.assertIs(True, record.get("started"), record)
        # The requested commit, not the HEAD of the repository: at HEAD the
        # dataset home-content is not synthetic, and is never served.
        self.assertEqual(self.requested, record["commit"])
        self.assertNotEqual(self.head, record["commit"])
        self.assertNotIn(record["port"], (CITY_COCKPIT_PORT, CITY_SUPERVISOR_PORT))
        address = record["address"]
        self.assertEqual(f"http://127.0.0.1:{record['port']}", address)

        code, content_type, page = fetch(address + "/")
        self.assertEqual(200, code)
        self.assertTrue(content_type.startswith("text/html"), content_type)
        self.assertIn("<title>Cockpit</title>", page)

        snapshot = self.status(address)
        # The read model of the cockpit, each source read and fresh.
        for source in ("gc", "beads", "projets", "journal"):
            self.assertEqual("fresh", snapshot[source]["freshness"], source)
        # Its state is the named dataset's, not the city in service's.
        self.assertEqual("home-content", snapshot["gc"]["value"]["city"])

        # Another named dataset, another state, on another isolated port.
        other, _ = self.start(self.requested, "factory-suspended")
        self.assertIs(True, other.get("started"), other)
        self.assertNotEqual(record["port"], other["port"])
        self.assertEqual("factory-suspended", self.status(other["address"])["gc"]["value"]["city"])
        self.assertEqual("home-content", self.status(address)["gc"]["value"]["city"])

    def test_a_dataset_that_is_not_synthetic_is_never_served(self):
        # At the requested commit the dataset is synthetic and the cockpit answers.
        record, _ = self.start(self.requested, "home-content")
        self.assertIs(True, record.get("started"), record)
        # At HEAD the same dataset is a source that is not synthetic: no cockpit.
        with adopting_orphans():
            refused, state = self.start(self.head, "home-content")
            self.assertIs(False, refused.get("started"), refused)
            self.assertFalse(state.exists(), "a refused launch leaves no launch record")
            deadline = time.monotonic() + 10
            while children() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual([], children(), "a refused launch leaves no process")

    # Criterion 2 ---------------------------------------------------------

    def test_stop_closes_the_isolated_process_and_port_and_leaves_other_services(self):
        class Neighbour(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

        # A service that is not the launched product, as the city in service is.
        neighbour = ThreadingHTTPServer(("127.0.0.1", 0), Neighbour)
        threading.Thread(target=neighbour.serve_forever, daemon=True).start()
        self.addCleanup(neighbour.server_close)
        self.addCleanup(neighbour.shutdown)
        neighbour_url = f"http://127.0.0.1:{neighbour.server_address[1]}/"

        with adopting_orphans():
            record, state = self.start(self.requested, "home-content")
            self.assertIs(True, record.get("started"), record)
            address, port, worktree = record["address"], record["port"], Path(record["worktree"])
            self.assertEqual("home-content", self.status(address)["gc"]["value"]["city"])
            self.assertTrue(children(), "the launched cockpit is a process of this launch")

            self.assertEqual({"stopped": True}, self.stop(state))

            self.assertFalse(answers(address + "/"), "the previous address still answers")
            self.assertFalse(answers(address + "/api/status"), "the previous address still answers")
            self.assertTrue(port_is_free(port), "the isolated port is still open")
            deadline = time.monotonic() + 10
            while children() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual([], children(), "an orphan process outlives the stop")
        with self.assertRaises(ProcessLookupError):
            os.kill(record["pid"], 0)
        self.assertFalse(worktree.exists(), "the clean copy of the commit is still there")
        self.assertFalse(state.exists())
        self.assertTrue(answers(neighbour_url), "a service that is not the launched product was stopped")


if __name__ == "__main__":
    unittest.main()
