"""Cockpit-core seam test (af-0b6ffa, T11 — Spec af-oohx2x Testing Decisions).

The main seam for the whole cockpit: the process started on faked sources
(fake gc with API + SSE, fake bd, a real clock advanced only by sleeping —
this is a black-box process test, no fake clock is injected across the
process boundary). It drives the process the way Benjamin's browser would:
plain HTTP GET, never an internal function.

A companion test class drives `bin/factory-boot`'s new cockpit-launch step
against fully stubbed `gc`/`provider-failover`/`factory-build-gates`/
`cockpit` binaries — it is the CLI surface under test there, per Testing
Decisions ("une porte est testée par sa ligne de commande").
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
COCKPIT_BIN = ROOT / "bin" / "cockpit"
FACTORY_BOOT = ROOT / "bin" / "factory-boot"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(FIXTURES))

from fake_gc import FakeGc  # noqa: E402


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(host, port, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("nothing listening on %s:%d after %ss" % (host, port, timeout))


def http_get(port, path, timeout=3):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json_or_text(resp)


def json_or_text(resp):
    raw = resp.read().decode("utf-8")
    if resp.headers.get("Content-Type", "").startswith("application/json"):
        return json.loads(raw)
    return raw


def wait_until(predicate, timeout=5, interval=0.05):
    """Poll ``predicate()`` (no args) until it returns truthy; return that
    value. Raises AssertionError with the last falsy result on timeout."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


class CockpitSeamTest(unittest.TestCase):
    """AC1-AC4: the cockpit process started on faked sources."""

    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmp.name, "cockpit.pid")
        self.port = free_port()
        self.proc = None

    def tearDown(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            self.proc.stdout.close()
            self.proc.stderr.close()
        self.fake_gc.stop()
        self.tmp.cleanup()

    def start_cockpit(self, extra_env=None, port=None):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(port if port is not None else self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_BD_BIN": str(FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": self.pid_file,
                "COCKPIT_BEADS_POLL_SECONDS": "0.2",
            }
        )
        if extra_env:
            env.update(extra_env)
        proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.proc = proc
        return proc

    def snapshot(self):
        return http_get(self.port, "/api/status")[1]

    def home_body(self):
        return http_get(self.port, "/")[1]

    # ------------------------------------------------------------------
    # AC1 — the test starts the process on fake sources and reads what
    # the page receives.
    # ------------------------------------------------------------------
    def test_process_starts_and_serves_what_the_page_receives(self):
        self.start_cockpit()
        wait_for_port("127.0.0.1", self.port)

        self.fake_gc.push_event({"running": True, "suspended": False, "partial": False})
        # "Tout est à jour" needs every source fresh: wait for beads too,
        # not only gc (the beads source makes two bd reads, af-1al0t1).
        snapshot = wait_until(
            lambda: self.snapshot()
            if all(self.snapshot()[s]["freshness"] == "fresh" for s in ("gc", "beads"))
            else None,
            timeout=5,
        )
        self.assertEqual("fresh", snapshot["gc"]["freshness"])
        self.assertIn("beads", snapshot)

        status, body = http_get(self.port, "/")
        self.assertEqual(200, status)
        self.assertIn("Tout est à jour à", body)

    # ------------------------------------------------------------------
    # AC2 — fresh -> stale -> unknown over the clock; never a "0" without
    # a fresh read; a partial:true gc response is not taken as complete.
    # ------------------------------------------------------------------
    def test_freshness_ages_from_fresh_through_stale_to_unknown(self):
        self.start_cockpit(extra_env={"COCKPIT_VALIDITY_GC_SECONDS": "0.3"})
        wait_for_port("127.0.0.1", self.port)

        # Before any read: never a bare "0" or default value — None, unknown.
        snapshot = self.snapshot()
        self.assertIsNone(snapshot["gc"]["value"])
        self.assertEqual("unknown", snapshot["gc"]["freshness"])

        self.fake_gc.push_event({"running": True, "partial": False})
        snapshot = wait_until(
            lambda: self.snapshot() if self.snapshot()["gc"]["freshness"] == "fresh" else None,
            timeout=5,
        )
        self.assertEqual("fresh", snapshot["gc"]["freshness"])

        # A partial:true response must not be taken as a complete, fresh
        # read: it must not reset the age clock.
        self.fake_gc.push_event({"running": True, "partial": True})
        time.sleep(0.4)  # > validity (0.3s), so a real refresh would show fresh
        snapshot = self.snapshot()
        self.assertEqual(
            "stale", snapshot["gc"]["freshness"],
            "a partial:true gc event must not count as a complete, fresh read",
        )

        # Long enough without a complete read: the source is failing, not
        # merely stale — unknown (CONTEXT.md Freshness: "or its source is
        # failing").
        time.sleep(0.6)
        snapshot = self.snapshot()
        self.assertEqual("unknown", snapshot["gc"]["freshness"])

    # ------------------------------------------------------------------
    # AC3 — headline "Tout est à jour à HH:MM (Paris)", or the list of
    # stale/unknown sections when a source stops responding.
    # ------------------------------------------------------------------
    def test_headline_switches_to_the_stale_section_list(self):
        self.start_cockpit(
            extra_env={
                "COCKPIT_VALIDITY_GC_SECONDS": "0.3",
                "COCKPIT_BEADS_POLL_SECONDS": "0.1",
            }
        )
        wait_for_port("127.0.0.1", self.port)
        self.fake_gc.push_event({"running": True, "partial": False})

        body = wait_until(
            lambda: self.home_body() if "Tout est à jour à" in self.home_body() else None,
            timeout=5,
        )
        self.assertIn("Tout est à jour à", body)

        # gc goes quiet — no more events — and ages past its Validity window.
        body = wait_until(
            lambda: self.home_body() if "Périmé ou inconnu" in self.home_body() else None,
            timeout=5,
        )
        self.assertIn("Périmé ou inconnu", body)
        self.assertIn("usine (gc)", body)

    # ------------------------------------------------------------------
    # AC4 — refuses to listen anywhere but 127.0.0.1; survives a
    # simulated suspend and city stop.
    # ------------------------------------------------------------------
    def test_refuses_to_bind_off_loopback(self):
        proc = self.start_cockpit(extra_env={"COCKPIT_HOST": "0.0.0.0"})
        returncode = proc.wait(timeout=5)
        self.assertNotEqual(0, returncode)
        stderr = proc.stderr.read()
        self.assertIn("127.0.0.1", stderr)

    def test_survives_a_simulated_city_stop(self):
        self.start_cockpit()
        wait_for_port("127.0.0.1", self.port)
        self.fake_gc.push_event({"running": True, "partial": False})
        wait_until(
            lambda: self.snapshot() if self.snapshot()["gc"]["freshness"] == "fresh" else None,
            timeout=5,
        )

        self.fake_gc.go_down()  # simulated suspend/stop of the city
        time.sleep(0.5)

        self.assertIsNone(self.proc.poll(), "cockpit must not crash when gc goes quiet")
        status, snapshot = http_get(self.port, "/api/status")
        self.assertEqual(200, status)
        self.assertIn("gc", snapshot)

        self.proc.terminate()
        self.assertEqual(0, self.proc.wait(timeout=5))


class CockpitCliLifecycleTest(unittest.TestCase):
    """`bin/cockpit start/status/stop` itself — the background lifecycle
    factory-boot's decision (FactoryBootCockpitLaunchTest) relies on."""

    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmp.name, "cockpit.pid")
        self.port = free_port()
        self.env = dict(os.environ)
        self.env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_BD_BIN": str(FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": self.pid_file,
                "COCKPIT_BEADS_POLL_SECONDS": "5",
            }
        )

    def tearDown(self):
        subprocess.run([str(COCKPIT_BIN), "stop"], env=self.env, capture_output=True)
        self.fake_gc.stop()
        self.tmp.cleanup()

    def cockpit(self, *args):
        return subprocess.run(
            [str(COCKPIT_BIN), *args], env=self.env, capture_output=True, text=True, timeout=15
        )

    def test_start_is_idempotent_then_stop_clears_it(self):
        self.assertEqual(1, self.cockpit("status").returncode)

        first = self.cockpit("start")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        wait_for_port("127.0.0.1", self.port)
        self.assertEqual(0, self.cockpit("status").returncode)
        first_pid = Path(self.pid_file).read_text().strip()

        second = self.cockpit("start")
        self.assertEqual(0, second.returncode)
        self.assertEqual(
            first_pid, Path(self.pid_file).read_text().strip(),
            "a second `start` while already running must not launch another process",
        )

        stop = self.cockpit("stop")
        self.assertEqual(0, stop.returncode, stop.stdout + stop.stderr)
        self.assertEqual(1, self.cockpit("status").returncode)


class FactoryBootCockpitLaunchTest(unittest.TestCase):
    """AC5 — factory-boot launches the cockpit if it is not running, and
    does not launch a second process if it already is."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        _write_stub(self.root / "bin" / "provider-failover")
        _write_stub(self.root / "bin" / "factory-build-gates")
        import shutil

        shutil.copy(FIXTURES / "fake-cockpit-bin", self.root / "bin" / "cockpit")
        os.chmod(self.root / "bin" / "cockpit", 0o755)
        self.cockpit_log = self.root / "cockpit-calls.log"
        self.cockpit_log.write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def run_factory_boot(self, cockpit_running):
        env = dict(os.environ)
        env.update(
            {
                "FACTORY_ROOT": str(self.root),
                "GC_BIN": str(FIXTURES / "fake-gc-supervisor-cli"),
                "FACTORY_BOOT_LOG": str(self.root / "factory-boot.log"),
                "FACTORY_BOOT_LOCK": str(self.root / "factory-boot.lock"),
                "FACTORY_BOOT_WAIT_SECONDS": "1",
                "FAKE_COCKPIT_LOG": str(self.cockpit_log),
                "FAKE_COCKPIT_RUNNING": "1" if cockpit_running else "0",
            }
        )
        return subprocess.run(
            [str(FACTORY_BOOT)], env=env, capture_output=True, text=True, timeout=30
        )

    def test_launches_cockpit_when_not_running(self):
        result = self.run_factory_boot(cockpit_running=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        calls = self.cockpit_log.read_text().splitlines()
        self.assertEqual(["status", "start"], calls)

    def test_does_not_launch_a_second_process_when_already_running(self):
        result = self.run_factory_boot(cockpit_running=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        calls = self.cockpit_log.read_text().splitlines()
        self.assertEqual(["status"], calls)
        self.assertIn("cockpit already running", result.stdout)


def _write_stub(path):
    path.write_text("#!/usr/bin/env bash\nexit 0\n")
    os.chmod(path, 0o755)


if __name__ == "__main__":
    unittest.main()
