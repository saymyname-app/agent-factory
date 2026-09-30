"""Cockpit health-zone seam test (T16, Spec af-oohx2x — "Zone santé de
l'usine").

Same seam as tests/cockpit-core-test.py (T11): the cockpit process started
on faked sources (fake gc with API + SSE, fake bd whose bead list is
test-controlled, a real disposable git repo standing in for "faux clone
git"), driven only through plain HTTP GET/POST — never an internal
function.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
HEALTH_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "health"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIXTURES))

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
        raw = resp.read().decode("utf-8")
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.status, json.loads(raw)
        return resp.status, raw


def http_post(port, path, timeout=3):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path), data=b"", method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def wait_until(predicate, timeout=15, interval=0.05):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


def run_git(repo_dir, *args):
    subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


class GitFixture:
    """A disposable bare "origin" plus a local clone standing in for the
    live root — Testing Decisions' "faux clone git de projet" without a
    real network or the real project repo (AGENTS.md: never the live root)."""

    def __init__(self, tmp_path):
        self.origin_dir = tmp_path / "origin.git"
        self.clone_dir = tmp_path / "clone"
        run_git(tmp_path, "init", "--bare", str(self.origin_dir))
        run_git(self.origin_dir, "symbolic-ref", "HEAD", "refs/heads/main")
        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(self.clone_dir)],
            check=True, capture_output=True, text=True,
        )
        run_git(self.clone_dir, "checkout", "-B", "main")
        (self.clone_dir / "seed.txt").write_text("seed\n")
        run_git(self.clone_dir, "add", "seed.txt")
        run_git(self.clone_dir, "commit", "-m", "seed")
        run_git(self.clone_dir, "push", "origin", "HEAD:refs/heads/main")

    def advance_origin_by(self, n):
        """Push ``n`` new commits to origin/main that the clone does not
        have — the clone (standing in for the live root) is now behind."""
        work = self.clone_dir.parent / "origin-work"
        if not work.exists():
            subprocess.run(
                ["git", "clone", str(self.origin_dir), str(work)],
                check=True, capture_output=True, text=True,
            )
            run_git(work, "checkout", "-B", "main", "origin/main")
        for i in range(n):
            (work / ("f%d.txt" % i)).write_text("x\n")
            run_git(work, "add", ".")
            run_git(work, "commit", "-m", "advance %d" % i)
        run_git(work, "push", "origin", "HEAD:refs/heads/main")

    def catch_up(self):
        run_git(self.clone_dir, "fetch", "origin", "main")
        run_git(self.clone_dir, "reset", "--hard", "origin/main")


class CockpitHealthZoneTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.pid_file = str(self.tmp_path / "cockpit.pid")
        self.bd_state_file = self.tmp_path / "beads.json"
        self.port = free_port()
        self.proc = None
        self.git = GitFixture(self.tmp_path)

    def tearDown(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.proc is not None:
            self.proc.stdout.close()
            self.proc.stderr.close()
        self.fake_gc.stop()
        self.tmp.cleanup()

    def set_beads(self, beads):
        self.bd_state_file.write_text(json.dumps(beads))

    def start_cockpit(self, extra_env=None):
        env = dict(os.environ)
        env.update({
            "COCKPIT_HOST": "127.0.0.1",
            "COCKPIT_PORT": str(self.port),
            "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
            "COCKPIT_BD_BIN": str(HEALTH_FIXTURES / "fake-bd-health"),
            "COCKPIT_TEST_BD_STATE_FILE": str(self.bd_state_file),
            "COCKPIT_PID_FILE": self.pid_file,
            "COCKPIT_BEADS_POLL_SECONDS": "0.2",
            "COCKPIT_REPO_DIR": str(self.git.clone_dir),
            "COCKPIT_GIT_REMOTE": "origin",
            "COCKPIT_GIT_BRANCH": "main",
            "COCKPIT_GIT_POLL_SECONDS": "0.2",
            "COCKPIT_HEALTH_SUPERVISOR_UNREACHABLE_SECONDS": "3",
            "COCKPIT_HEALTH_FACTORY_STALLED_SECONDS": "3",
        })
        if extra_env:
            env.update(extra_env)
        proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.proc = proc
        wait_for_port("127.0.0.1", self.port)
        return proc

    def health(self):
        return http_get(self.port, "/api/health")[1]

    def home(self):
        return http_get(self.port, "/")[1]

    def wait_for_line_containing(self, needle, timeout=15):
        return wait_until(
            lambda: next((l for l in self.health()["lines"] if needle in l["text"]), None),
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    def test_no_problem_detected_when_everything_is_quiet(self):
        self.set_beads([])
        self.start_cockpit()
        self.fake_gc.push_event({"running": True, "partial": False})
        health = wait_until(lambda: self.health() if self.health()["lines"] == [] else None)
        self.assertTrue(health["ok"])
        self.assertIn("Aucun problème détecté", self.home())

    # ------------------------------------------------------------------
    def test_version_behind_appears_and_disappears_without_push(self):
        self.set_beads([])
        self.start_cockpit()
        self.fake_gc.push_event({"running": True, "partial": False})

        self.git.advance_origin_by(3)
        line = self.wait_for_line_containing("retard de 3 commit")
        self.assertEqual("warn", line["kind"])
        self.assertIn("retard de 3 commit", self.home())

        # Return to normal: no notification system exists yet (T16 scope is
        # display only) -- proving the line simply disappears is enough.
        self.git.catch_up()
        wait_until(lambda: True if not any(
            "retard de" in l["text"] for l in self.health()["lines"]
        ) else None)
        self.assertNotIn("retard de 3 commit", self.home())

    # ------------------------------------------------------------------
    def test_supervisor_unreachable_appears_and_disappears(self):
        self.set_beads([])
        self.start_cockpit()
        self.fake_gc.push_event({"running": True, "partial": False})
        # Wait for the first successful read to land before judging
        # anything "unreachable" -- with no read yet there is nothing to
        # measure the outage from.
        wait_until(
            lambda: http_get(self.port, "/api/status")[1]
            if http_get(self.port, "/api/status")[1]["gc"]["freshness"] == "fresh"
            else None
        )
        self.assertFalse(any("Superviseur injoignable" in l["text"] for l in self.health()["lines"]))

        self.fake_gc.go_down()
        line = self.wait_for_line_containing("Superviseur injoignable", timeout=15)
        self.assertEqual("bad", line["kind"])

        self.fake_gc.go_up()
        self.fake_gc.push_event({"running": True, "partial": False})
        wait_until(lambda: True if not any(
            "Superviseur injoignable" in l["text"] for l in self.health()["lines"]
        ) else None)

    # ------------------------------------------------------------------
    def test_factory_stalled_appears_when_delivery_work_is_ready(self):
        self.set_beads([])
        self.start_cockpit()
        stalled_since = time.time() - 10  # already old enough given the 3s test threshold
        self.fake_gc.push_event({
            "running": True, "partial": False,
            "last_progress_at": stalled_since, "delivery_ready": True,
        })
        line = self.wait_for_line_containing("Usine à l'arrêt ?")
        self.assertEqual("warn", line["kind"])

        # Progress resumes -- the line must clear.
        self.fake_gc.push_event({
            "running": True, "partial": False,
            "last_progress_at": time.time(), "delivery_ready": True,
        })
        wait_until(lambda: True if not any(
            "Usine à l'arrêt" in l["text"] for l in self.health()["lines"]
        ) else None)

    # ------------------------------------------------------------------
    def test_mayor_first_escalation_not_promoted(self):
        started = time.time() - 6000  # 1h40
        self.set_beads([{
            "id": "af-fakemf", "status": "open",
            "metadata": {"gc.mayor_first_since": started},
        }])
        self.start_cockpit()
        self.fake_gc.push_event({"running": True, "partial": False})
        line = self.wait_for_line_containing("corriger seule")
        self.assertEqual("warn", line["kind"])
        self.assertNotIn("af-fakemf", line["text"])  # never a bead id on screen
        self.assertNotIn("Maire", self.home())  # the Mayor is never named
        self.assertNotIn("Mayor", self.home())

        # Promoted to Benjamin (gc.needs_benjamin set) -- clears from health.
        self.set_beads([{
            "id": "af-fakemf", "status": "open",
            "metadata": {"gc.mayor_first_since": started, "gc.needs_benjamin": "quoi"},
        }])
        wait_until(lambda: True if not any(
            "corriger seule" in l["text"] for l in self.health()["lines"]
        ) else None)

    # ------------------------------------------------------------------
    def test_loop_order_failure_and_red_ci_lines(self):
        now = time.time()
        self.set_beads([
            {"id": "af-loop1", "status": "open", "metadata": {"gc.loop_detected": "true", "gc.loop_since": now}},
            {"id": "af-fail1", "status": "open", "metadata": {"gc.order_failed": "true", "gc.order_failed_at": now}},
            {"id": "af-ci1", "status": "open", "metadata": {"gc.ci_status": "red", "gc.ci_red_since": now}},
        ])
        self.start_cockpit()
        self.fake_gc.push_event({"running": True, "partial": False})
        wait_until(lambda: self.health() if len(self.health()["lines"]) >= 3 else None)
        health = self.health()
        texts = " ".join(l["text"] for l in health["lines"])
        self.assertIn("boucle", texts)
        self.assertIn("échoué", texts)
        self.assertIn("rouges", texts)
        for l in health["lines"]:
            self.assertNotIn("af-", l["text"])

        self.set_beads([])
        wait_until(lambda: self.health() if self.health()["lines"] == [] else None)

    # ------------------------------------------------------------------
    def test_recheck_forces_an_immediate_read(self):
        self.set_beads([])
        self.start_cockpit(extra_env={
            "COCKPIT_BEADS_POLL_SECONDS": "300",
            "COCKPIT_GIT_POLL_SECONDS": "300",
        })
        self.fake_gc.push_event({"running": True, "partial": False})
        wait_until(lambda: self.health() if self.health()["lines"] == [] else None)

        self.set_beads([{
            "id": "af-loop1", "status": "open",
            "metadata": {"gc.loop_detected": "true", "gc.loop_since": time.time()},
        }])
        # Poll interval is 300s -- without a recheck this would not show up
        # within the test's lifetime.
        status = http_post(self.port, "/api/health/recheck")
        self.assertIn(status, (200, 303))  # urllib follows the 303 -> final GET's 200
        health = self.health()
        self.assertTrue(any("boucle" in l["text"] for l in health["lines"]))


if __name__ == "__main__":
    unittest.main()
