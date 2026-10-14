#!/usr/bin/env python3
"""Tests for bin/project-launch (spec af-wf4w5r .12, T01, af-m8m1kc).

Exercises the launcher that an author, the Evaluator and the Acceptance
Session all use to launch a project's product on an isolated port against a
named synthetic dataset, and to stop it again. All five T01 acceptance
criteria are covered end to end through the CLI's public interface --
nothing here reads project-launch's internals.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import shutil
import signal
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
# A real project whose profile declares no launch recipe (the Factory's own
# declares one since af-6a98ip).
NO_LAUNCH_DESCRIPTOR = ROOT / "config" / "project-descriptors" / "saymyname.json"
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


PR_SET_CHILD_SUBREAPER = 36  # <linux/prctl.h>


@contextlib.contextmanager
def _adopting_orphans():
    """While this holds, a process a command of this test starts and leaves
    behind becomes a child of this test process instead of the host's init
    (prctl PR_SET_CHILD_SUBREAPER), so `_children()` can name it."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) refused")
    try:
        yield
    finally:
        libc.prctl(PR_SET_CHILD_SUBREAPER, 0, 0, 0, 0)


def _children() -> list[int]:
    """The processes whose parent is this test process, and no other: what
    another battery, a CI job or a live launch runs on the same host at the
    same moment is not in this list (af-29xv7v). An adopted process that
    has already ended is reaped first: it is no longer running."""
    with contextlib.suppress(ChildProcessError):
        while os.waitpid(-1, os.WNOHANG)[0]:
            pass
    me = str(os.getpid())
    found = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue  # gone between the listing and the read
        if fields[1] == me:
            found.append(int(stat.parent.name))
    return sorted(found)


def _end(pids: list[int]) -> None:
    for pid in pids:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)


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

    def test_start_launches_a_product_that_lives_in_another_repository(self):
        """`--repo-root` names the repository of the product; the profile
        tool stays the Factory's (T10, af-j8jo02)."""
        import os
        import shutil

        fixture = Path("tests") / "fixtures" / "delivery-fixture-city"
        product = Path(tempfile.mkdtemp(prefix="project-launch-product-"))
        self.addCleanup(shutil.rmtree, product, ignore_errors=True)
        shutil.copytree(ROOT / fixture, product / fixture)
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        for args in (("init", "-q", "-b", "main"), ("add", "-A"),
                     ("-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "commit", "-q", "-m", "produit")):
            subprocess.run(("git", "-C", str(product), *args), env=env, check=True, capture_output=True)
        state_file = self.new_state_file()

        result = subprocess.run(
            (str(TOOL), "--repo-root", str(product), "start", str(DESCRIPTOR), "--dataset", "content",
             "--state-file", str(state_file)),
            cwd=product, env=env, text=True, capture_output=True)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(str(product.resolve()), record["repo_root"])
        self.assertEqual(200, _fetch(record["address"] + "/health")[0])

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

    # The port is the product's -------------------------------------------------

    def contested_launch(self, taken: int):
        """Launch the fixture product through a recipe that, before the
        product binds the port it is given, lets this test answer on that
        port in its place -- as another launch on the same host can, between
        the moment the launcher chooses a port and the moment the product
        binds it. The first `taken` ports given are answered here, 200 to
        everything, and the product then fails to bind them. Returns the
        launcher's answer, the ports given, and the impostors' addresses."""
        import shutil
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        product = Path(tempfile.mkdtemp(prefix="project-launch-contested-"))
        self.addCleanup(shutil.rmtree, product, ignore_errors=True)
        fixture = Path("tests") / "fixtures" / "delivery-fixture-city"
        shutil.copytree(ROOT / fixture, product / fixture)
        (product / "contested.py").write_text(
            "import os, sys, time\n"
            "port, contest = sys.argv[1], os.environ['CONTEST_DIR']\n"
            "with open(os.path.join(contest, 'ports'), 'a') as given:\n"
            "    given.write(port + '\\n')\n"
            "deadline = time.monotonic() + 20\n"
            "while not os.path.exists(os.path.join(contest, 'release-' + port)) and time.monotonic() < deadline:\n"
            "    time.sleep(0.05)\n"
            "os.execv(sys.argv[2], sys.argv[2:])\n"
        )
        descriptor = json.loads(DESCRIPTOR.read_text())
        descriptor["launch"]["recipe"] = ["{python}", "contested.py", "{port}", *descriptor["launch"]["recipe"]]
        (product / "descriptor.json").write_text(json.dumps(descriptor))
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        for args in (("init", "-q", "-b", "main"), ("add", "-A"),
                     ("-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "commit", "-q", "-m", "produit")):
            subprocess.run(("git", "-C", str(product), *args), env=env, check=True, capture_output=True)

        class Impostor(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "8")
                self.end_headers()
                self.wfile.write(b"impostor")

        contest = product / "contest"
        contest.mkdir()
        impostors: dict[int, str] = {}
        done = threading.Event()

        def answer_in_place_of_the_product():
            seen: list[int] = []
            while not done.is_set():
                given = (contest / "ports").read_text().split() if (contest / "ports").exists() else []
                for port in map(int, given[len(seen):]):
                    seen.append(port)
                    if len(seen) <= taken:
                        server = ThreadingHTTPServer(("127.0.0.1", port), Impostor)
                        threading.Thread(target=server.serve_forever, daemon=True).start()
                        self.addCleanup(server.server_close)
                        self.addCleanup(server.shutdown)
                        impostors[port] = f"http://127.0.0.1:{port}/"
                        time.sleep(1)  # long enough for the health probe to reach the impostor
                    (contest / f"release-{port}").touch()
                time.sleep(0.02)

        watcher = threading.Thread(target=answer_in_place_of_the_product, daemon=True)
        watcher.start()
        state_file = self.new_state_file()
        with _adopting_orphans():
            result = subprocess.run(
                (str(TOOL), "--repo-root", str(product), "start", str(product / "descriptor.json"),
                 "--dataset", "content", "--state-file", str(state_file), "--timeout", "15"),
                cwd=product, env={**env, "CONTEST_DIR": str(contest)}, text=True, capture_output=True)
            record = json.loads(result.stdout)
            left = [] if record.get("started") else _children()
            _end(left)
        done.set()
        watcher.join()
        given = [int(port) for port in (contest / "ports").read_text().split()]
        return record, state_file, given, impostors, left

    def test_a_port_another_process_answers_on_is_not_the_product_and_another_is_taken(self):
        record, _, given, impostors, _ = self.contested_launch(taken=1)

        self.assertIs(True, record["started"], record)
        self.assertEqual(2, len(given), "the launcher did not choose another port")
        self.assertEqual(given[1], record["port"])
        self.assertNotIn(record["port"], impostors)
        # What answers at the announced address is the launched product.
        _, page = _fetch(record["address"] + "/")
        self.assertIn('data-anchor="fixture-state">content<', page)
        # The process that took the first port is not the launcher's to stop.
        self.assertEqual("impostor", _fetch(impostors[given[0]])[1])

    def test_a_product_whose_every_port_is_taken_is_not_started_and_leaves_nothing(self):
        record, state_file, given, impostors, left = self.contested_launch(taken=3)

        self.assertIs(False, record["started"], record)
        self.assertEqual(3, len(given))
        self.assertIn("another process", record["error"])
        self.assertEqual([], left, "the refused start left a process behind")
        self.assertFalse(state_file.exists(), "the refused start wrote a launch record")
        for address in impostors.values():
            self.assertEqual("impostor", _fetch(address)[1])

    # AC4 ------------------------------------------------------------------------

    def test_start_without_a_named_dataset_is_refused_and_launches_nothing(self):
        """T38 (af-8o4jcp): a recipe that needs no dataset path still launches
        on a named dataset only."""
        descriptor = json.loads(DESCRIPTOR.read_text())
        content = descriptor["launch"]["datasets"]["content"]
        descriptor["launch"]["recipe"] = [
            content if token == "{dataset}" else token for token in descriptor["launch"]["recipe"]]
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = Path(folder) / "descriptor.json"
        path.write_text(json.dumps(descriptor))

        with _adopting_orphans():
            result, state_file = self.start("--commit", "HEAD", descriptor=path, check=False)
            started = _children()
            _end(started)

        self.assertNotEqual(0, result.returncode)
        error = json.loads(result.stdout)
        self.assertFalse(error["started"])
        self.assertIn("no dataset named", error["error"])
        self.assertEqual([], started, "the refused start left a process behind")
        self.assertFalse(state_file.exists(), "the refused start wrote a launch record")

    def test_start_on_a_project_with_no_launch_recipe_is_refused(self):
        # "Nothing was started" is read from what this test owns -- the
        # processes its own command left behind and its own launch record --
        # never from the host's process list: a CI job or another battery on
        # the same host runs these same tests at the same moment (af-29xv7v).
        with _adopting_orphans():
            self.assertEqual([], _children())

            # The probe sees a process a command leaves behind, as a real
            # launch does: without this, an empty list would prove nothing.
            subprocess.run(("sh", "-c", "sleep 60 &"), stdout=subprocess.DEVNULL, check=True)
            left_behind = _children()
            _end(left_behind)
            self.assertEqual(1, len(left_behind), "the probe does not see a process left behind")

            result, state_file = self.start(
                "--commit", "HEAD", descriptor=NO_LAUNCH_DESCRIPTOR, check=False
            )
            started = _children()
            _end(started)

        self.assertNotEqual(0, result.returncode)
        error = json.loads(result.stdout)
        self.assertFalse(error["started"])
        self.assertIn("declares no launch recipe", error["error"])
        self.assertIn("saymyname", error["error"])

        self.assertEqual([], started, "the refused start left a process behind")
        self.assertFalse(state_file.exists(), "the refused start wrote a launch record")


if __name__ == "__main__":
    unittest.main()
