#!/usr/bin/env python3
"""Tests for bin/project-launch (spec af-wf4w5r .12, T01, af-m8m1kc).

Exercises the launcher that an author, the Evaluator and the Acceptance
Session all use to launch a project's product on an isolated port against a
named synthetic dataset, and to stop it again. All five T01 acceptance
criteria are covered end to end through the CLI's public interface --
nothing here reads project-launch's internals.
"""

from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "project-launch"
DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"
NO_LAUNCH_DESCRIPTOR = ROOT / "config" / "project-descriptors" / "agent-factory.json"
MUTATED_DATASET = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "datasets" / "content.json"


def _fetch(url: str, timeout: float = 5.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def _port_is_free(port: int) -> bool:
    # SO_REUSEADDR matches how HTTPServer itself binds (allow_reuse_address
    # = True); without it, a connection this test's own HTTP client made to
    # the stopped server can sit in TIME_WAIT and fail a plain bind() even
    # though the server process is gone and the port is genuinely free for
    # a real relaunch.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


class ProjectLaunchTest(unittest.TestCase):
    def setUp(self) -> None:
        self._state_files: list[Path] = []

    def tearDown(self) -> None:
        for state_file in self._state_files:
            if state_file.exists():
                self.stop(state_file=state_file)

    def new_state_file(self) -> Path:
        handle, path = tempfile.mkstemp(prefix="project-launch-state-")
        import os

        os.close(handle)
        state_file = Path(path)
        state_file.unlink()
        self._state_files.append(state_file)
        return state_file

    def start(self, *extra_args: str, descriptor: Path = DESCRIPTOR, check: bool = True):
        state_file = self.new_state_file()
        args = [
            str(TOOL),
            "start",
            str(descriptor),
            "--state-file",
            str(state_file),
            *extra_args,
        ]
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)
        return result, state_file

    def stop(self, *, state_file: Path, check: bool = True):
        return subprocess.run(
            (str(TOOL), "stop", "--state-file", str(state_file)),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    # AC1 -----------------------------------------------------------------

    def test_start_on_fixture_project_at_named_commit_answers_health_probe(self):
        result, state_file = self.start("--commit", "HEAD", "--dataset", "content")
        record = json.loads(result.stdout)
        self.assertTrue(record["started"])
        self.assertTrue(record["address"].startswith("http://127.0.0.1:"))

        status, body = _fetch(record["address"] + "/health")
        self.assertEqual(200, status)
        self.assertEqual({"status": "ok"}, json.loads(body))

    def test_start_launches_a_clean_copy_of_the_named_commit_not_the_cwd(self):
        original = MUTATED_DATASET.read_text()
        try:
            mutated = json.loads(original)
            mutated["state"] = "MUTATED-UNCOMMITTED"
            MUTATED_DATASET.write_text(json.dumps(mutated))

            result, state_file = self.start("--commit", "HEAD", "--dataset", "content")
            record = json.loads(result.stdout)
            self.assertTrue(record["started"])

            _, body = _fetch(record["address"] + "/")
            self.assertIn('data-anchor="fixture-state">content<', body)
            self.assertNotIn("MUTATED-UNCOMMITTED", body)
        finally:
            MUTATED_DATASET.write_text(original)

    # AC2 -------------------------------------------------------------------

    def test_named_dataset_renders_and_two_launches_render_identically(self):
        result_a, _ = self.start("--commit", "HEAD", "--dataset", "content")
        record_a = json.loads(result_a.stdout)
        _, body_a = _fetch(record_a["address"] + "/")

        result_b, _ = self.start("--commit", "HEAD", "--dataset", "content")
        record_b = json.loads(result_b.stdout)
        _, body_b = _fetch(record_b["address"] + "/")

        self.assertEqual(body_a, body_b)
        self.assertIn('data-anchor="fixture-generated-at">2026-01-01T00:00:00Z<', body_a)

    # AC3 ---------------------------------------------------------------------

    def test_two_concurrent_launches_use_distinct_ports_independently(self):
        result_a, state_a = self.start("--commit", "HEAD", "--dataset", "empty")
        record_a = json.loads(result_a.stdout)
        result_b, state_b = self.start("--commit", "HEAD", "--dataset", "content")
        record_b = json.loads(result_b.stdout)

        self.assertNotEqual(record_a["port"], record_b["port"])

        status_a, _ = _fetch(record_a["address"] + "/health")
        status_b, _ = _fetch(record_b["address"] + "/health")
        self.assertEqual(200, status_a)
        self.assertEqual(200, status_b)

        self.stop(state_file=state_a)
        self._state_files.remove(state_a)

        # Stopping the first launch must not disturb the second.
        status_b_after, _ = _fetch(record_b["address"] + "/health")
        self.assertEqual(200, status_b_after)

        for _ in range(20):
            if _port_is_free(record_a["port"]):
                break
            time.sleep(0.1)
        self.assertTrue(_port_is_free(record_a["port"]))

    # AC4 ------------------------------------------------------------------------

    def test_start_on_a_project_with_no_launch_recipe_is_refused(self):
        before_pids = subprocess.run(
            ("pgrep", "-fa", "project-launch"), capture_output=True, text=True
        ).stdout

        result, _ = self.start(
            "--commit", "HEAD", descriptor=NO_LAUNCH_DESCRIPTOR, check=False
        )

        self.assertNotEqual(0, result.returncode)
        error = json.loads(result.stdout)
        self.assertFalse(error["started"])
        self.assertIn("declares no launch recipe", error["error"])
        self.assertIn("agent-factory", error["error"])

        after_pids = subprocess.run(
            ("pgrep", "-fa", "project-launch"), capture_output=True, text=True
        ).stdout
        self.assertEqual(before_pids, after_pids)


if __name__ == "__main__":
    unittest.main()
