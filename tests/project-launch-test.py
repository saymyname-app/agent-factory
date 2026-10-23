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
import functools
import json
import os
import shutil
import signal
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
TOOL = ROOT / "bin" / "project-launch"
DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"
# A real project whose profile declares no launch recipe (the Factory's own
# declares one since af-6a98ip).
NO_LAUNCH_DESCRIPTOR = ROOT / "config" / "project-descriptors" / "saymyname.json"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def _commit_product(product: Path) -> None:
    """Make `product` a Git repository whose one commit holds what it holds."""
    for args in (("init", "-q", "-b", "main"), ("add", "-A"),
                 ("-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "commit", "-q", "-m", "produit")):
        subprocess.run(("git", "-C", str(product), *args), env=GIT_ENV, check=True, capture_output=True)


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
        self._launch_env: dict | None = None  # the environment of _private_tmp's launches
        # The stops the guard and the sweep trace go here, not to the host's.
        trace_dir = Path(tempfile.mkdtemp(prefix="launch-trace-"))
        self.addCleanup(shutil.rmtree, trace_dir, True)
        self.trace = trace_dir / "stops.jsonl"
        previous = os.environ.get("FACTORY_LAUNCH_TRACE")
        os.environ["FACTORY_LAUNCH_TRACE"] = str(self.trace)
        self.addCleanup(lambda: os.environ.pop("FACTORY_LAUNCH_TRACE") if previous is None
                        else os.environ.__setitem__("FACTORY_LAUNCH_TRACE", previous))

    @functools.cached_property
    def product(self) -> Path:
        """A throwaway product repository holding the fixture, whose commit
        the launches of this test name: the tree these tests run in is not
        one -- the regression command runs them on a tree extracted by
        `git archive` (af-qsloqo). Its name stays out of the launcher's
        `project-launch-*` copies, which a test counts."""
        product = Path(tempfile.mkdtemp(prefix="launched-product-")).resolve()
        self.addCleanup(shutil.rmtree, product, ignore_errors=True)
        shutil.copytree(ROOT / FIXTURE, product / FIXTURE)
        _commit_product(product)
        return product

    @functools.cached_property
    def product_commit(self) -> str:
        return subprocess.run(["git", "-C", str(self.product), "rev-parse", "HEAD"],
                              text=True, capture_output=True, check=True).stdout.strip()

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

    def start(self, *extra_args: str, descriptor: Path = DESCRIPTOR, check: bool = True,
              env: dict | None = None):
        state_file = self.new_state_file()
        args = [
            str(TOOL),
            "--repo-root",
            str(self.product),
            "start",
            str(descriptor),
            "--state-file",
            str(state_file),
            *extra_args,
        ]
        result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=check)
        return result, state_file

    def stop(self, *, state_file: Path, check: bool = True):
        return subprocess.run(
            (str(TOOL), "stop", "--state-file", str(state_file)),
            cwd=ROOT,
            env=self._launch_env,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_reuse_requires_launch_identity_and_its_listening_port(self):
        """The launch is made from this test's own product repository
        (`start` names it), so the case holds outside any Git tree too."""
        sys.path.insert(0, str(ROOT / "lib"))
        from evaluation_capacity import product_running

        _, state_file = self.start("--dataset", "content")
        record = json.loads(state_file.read_text())
        self.assertEqual(str(self.product), record["repo_root"])
        self.assertTrue(product_running(record))
        self.assertFalse(product_running({**record, "launch_id": "unrelated"}))
        self.assertFalse(product_running({**record, "port": record["port"] + 1,
                                          "address": f"http://127.0.0.1:{record['port'] + 1}"}))
        self.assertFalse(product_running({**record, "commit": "0" * 40}))
        self.stop(state_file=state_file)
        self.assertFalse(product_running(record))

    def test_stop_recovers_an_interrupted_unregistered_checkout(self):
        worktree = Path(tempfile.mkdtemp(prefix="project-launch-"))
        (worktree / "partial").write_text("checkout interrupted")
        launch_id = "interrupted-checkout"
        commit = self.product_commit
        owner = Path(f"{worktree}.owner")
        owner.write_text(json.dumps({"launch_id": launch_id, "repo_root": str(self.product), "commit": commit}))
        state_file = self.new_state_file()
        state_file.write_text(json.dumps({"started": False, "launch_id": launch_id,
                                          "worktree": str(worktree), "repo_root": str(self.product),
                                          "commit": commit, "dataset": "content"}))
        stopped = self.stop(state_file=state_file)
        self.assertTrue(json.loads(stopped.stdout)["stopped"])
        self.assertFalse(worktree.exists())
        self.assertFalse(owner.exists())
        self.assertFalse(state_file.exists())

    def test_legacy_record_never_signals_an_unrelated_reused_pid(self):
        _, state_file = self.start("--dataset", "content")
        record = json.loads(state_file.read_text())
        stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            record.pop("launch_id")
            record["pid"] = stranger.pid
            state_file.write_text(json.dumps(record))
            stopped = self.stop(state_file=state_file)
            self.assertTrue(json.loads(stopped.stdout)["stopped"])
            self.assertIsNone(stranger.poll())
        finally:
            stranger.kill()
            stranger.wait()

    def test_corrupt_worktree_path_is_refused_without_deleting_it(self):
        _, state_file = self.start("--dataset", "content")
        record = json.loads(state_file.read_text())
        with tempfile.TemporaryDirectory(prefix="unrelated-") as unrelated:
            altered = {**record, "worktree": unrelated}
            state_file.write_text(json.dumps(altered))
            refused = self.stop(state_file=state_file, check=False)
            self.assertEqual(1, refused.returncode)
            self.assertTrue(Path(unrelated).exists())
            self.assertTrue(state_file.exists())
            state_file.write_text(json.dumps(record))
            self.stop(state_file=state_file)

    def test_stop_recognizes_exit_without_waiting_for_the_parent_to_reap(self):
        # The stop command is not the product's parent, just as for an
        # evaluation launched by an earlier controller pass. Keep the child
        # unreaped deliberately: kill(pid, 0) still succeeds after it exits.
        for already_dead in (True, False):
            with self.subTest(already_dead=already_dead):
                proc = subprocess.Popen(
                    [sys.executable, "-c", "pass" if already_dead else
                     "import time; print('ready', flush=True); time.sleep(60)"],
                    stdout=subprocess.PIPE, text=True)
                try:
                    if already_dead:
                        os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT)
                    else:
                        self.assertEqual("ready", proc.stdout.readline().strip())
                    result = subprocess.run(
                        [str(TOOL), "stop", "--pid", str(proc.pid)],
                        text=True, capture_output=True, timeout=3)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue(json.loads(result.stdout)["stopped"])
                    self.assertIsNotNone(proc.wait(timeout=1))
                finally:
                    proc.kill()
                    proc.wait()
                    proc.stdout.close()

    def test_stop_keeps_the_grace_and_kills_a_product_ignoring_sigterm(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import signal,time; "
             "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "print('ready', flush=True); time.sleep(60)"],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual("ready", proc.stdout.readline().strip())
            started = time.monotonic()
            result = subprocess.run([str(TOOL), "stop", "--pid", str(proc.pid)],
                                    text=True, capture_output=True, timeout=8)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(json.loads(result.stdout)["stopped"])
            self.assertGreaterEqual(time.monotonic() - started, 5)
            self.assertEqual(-signal.SIGKILL, proc.wait(timeout=1))
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()

    def test_stop_ends_a_descendant_in_another_session(self):
        with _adopting_orphans():
            launch_id = "test-escaped-descendant"
            env = {**os.environ, "FACTORY_LAUNCH_ID": launch_id}
            proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import subprocess,sys,time; child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
                 "start_new_session=True); print(child.pid, flush=True); time.sleep(60)"],
                stdout=subprocess.PIPE, text=True, start_new_session=True, env=env)
            child = int(proc.stdout.readline().strip())
            state_file = self.new_state_file()
            state_file.write_text(json.dumps({
                "pid": proc.pid, "process_group": proc.pid, "launch_id": launch_id,
            }))
            try:
                result = self.stop(state_file=state_file)
                self.assertTrue(json.loads(result.stdout)["stopped"])
                self.assertFalse(state_file.exists())
                self.assertIsNotNone(proc.wait(timeout=1))
                stat = Path(f"/proc/{child}/stat")
                self.assertTrue(not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] in {"Z", "X"})
            finally:
                for pid in (proc.pid, child):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.wait()
                proc.stdout.close()
                try:
                    os.waitpid(child, os.WNOHANG)
                except ChildProcessError:
                    pass

    def test_stop_ends_an_unmarked_descendant_still_holding_the_verified_copy(self):
        with _adopting_orphans():
            worktree = Path(tempfile.mkdtemp(prefix="project-launch-detached-test-"))
            launch_id = "test-unmarked-descendant"
            proc = subprocess.Popen(
                [sys.executable, "-c",
                 "import os,subprocess,sys,time; child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
                 "start_new_session=True, env={k:v for k,v in os.environ.items() if k != 'FACTORY_LAUNCH_ID'}); "
                 "print(child.pid, flush=True); time.sleep(60)"],
                cwd=worktree, stdout=subprocess.PIPE, text=True, start_new_session=True,
                env={**os.environ, "FACTORY_LAUNCH_ID": launch_id})
            child = int(proc.stdout.readline().strip())
            state_file = self.new_state_file()
            commit = self.product_commit
            Path(f"{worktree}.owner").write_text(json.dumps({
                "launch_id": launch_id, "repo_root": str(self.product), "commit": commit}))
            state_file.write_text(json.dumps({
                "pid": proc.pid, "process_group": proc.pid, "launch_id": launch_id,
                "worktree": str(worktree), "repo_root": str(self.product), "commit": commit,
            }))
            try:
                result = self.stop(state_file=state_file, check=False)
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertTrue(json.loads(result.stdout)["stopped"])
                self.assertIsNotNone(proc.wait(timeout=1))
                self.assertFalse(state_file.exists())
                self.assertFalse(worktree.exists())
                self.assertFalse(Path(f"/proc/{child}/stat").exists() and
                                 Path(f"/proc/{child}/stat").read_text().rsplit(")", 1)[1].split()[0] not in {"Z", "X"})
            finally:
                for pid in (proc.pid, child):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.wait()
                proc.stdout.close()
                shutil.rmtree(worktree, ignore_errors=True)
                try:
                    os.waitpid(child, os.WNOHANG)
                except ChildProcessError:
                    pass

    def test_start_requires_a_recoverable_launch_record(self):
        result = subprocess.run(
            [str(TOOL), "start", str(DESCRIPTOR), "--dataset", "content"],
            cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("--state-file", result.stderr)

    def test_interrupted_record_update_keeps_the_previous_valid_record(self):
        """The record is written before the copy is checked out, then updated
        with the port: an update that cannot complete leaves the previous
        record whole, where one written in place would be clobbered. The
        product's own post-checkout hook makes the record's folder read-only
        between the two."""
        if os.geteuid() == 0:
            self.skipTest("root writes into a read-only folder")
        folder = Path(tempfile.mkdtemp(prefix="launch-record-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.addCleanup(folder.chmod, 0o700)  # before the removal, whatever fails
        target = folder / "launch.json"
        hooks = folder.with_name(folder.name + "-hooks")
        hooks.mkdir()
        self.addCleanup(shutil.rmtree, hooks, ignore_errors=True)
        hook = hooks / "post-checkout"
        hook.write_text(f"#!/bin/sh\nchmod 0500 '{folder}'\n")
        hook.chmod(0o700)
        subprocess.run(("git", "-C", str(self.product), "config", "core.hooksPath", str(hooks)),
                       env=GIT_ENV, check=True, capture_output=True)

        result = subprocess.run(
            (str(TOOL), "--repo-root", str(self.product), "start", str(DESCRIPTOR),
             "--dataset", "content", "--state-file", str(target)),
            cwd=ROOT, text=True, capture_output=True)
        folder.chmod(0o700)
        self._state_files.append(target)

        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        record = json.loads(target.read_text())
        self.assertEqual((False, self.product_commit, "content"),
                         (record["started"], record["commit"], record["dataset"]))
        self.assertNotIn("port", record)
        self.assertEqual([target], list(folder.iterdir()))

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
        dataset = self.product / FIXTURE / "datasets" / "content.json"
        mutated = json.loads(dataset.read_text())
        mutated["state"] = "MUTATED-UNCOMMITTED"
        dataset.write_text(json.dumps(mutated))

        result, state_file = self.start("--commit", "HEAD", "--dataset", "content")
        record = json.loads(result.stdout)
        self.assertTrue(record["started"])

        _, body = _fetch(record["address"] + "/")
        self.assertIn('data-anchor="fixture-state">content<', body)
        self.assertNotIn("MUTATED-UNCOMMITTED", body)

    def test_start_launches_a_product_that_lives_in_another_repository(self):
        """`--repo-root` names the repository of the product; the profile
        tool stays the Factory's (T10, af-j8jo02)."""
        product = self.product
        state_file = self.new_state_file()

        result = subprocess.run(
            (str(TOOL), "--repo-root", str(product), "start", str(DESCRIPTOR), "--dataset", "content",
             "--state-file", str(state_file)),
            cwd=product, env=GIT_ENV, text=True, capture_output=True)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(str(product.resolve()), record["repo_root"])
        self.assertEqual(200, _fetch(record["address"] + "/health")[0])

    def test_stop_ends_a_launch_whose_product_repository_was_removed(self):
        """A ticket's runtime worktree can be deleted while its product still
        runs: the owner sidecar alone vouches for the copy (2026-10-15)."""
        product = self.product
        state_file = self.new_state_file()
        started = subprocess.run(
            (str(TOOL), "--repo-root", str(product), "start", str(DESCRIPTOR), "--dataset", "content",
             "--state-file", str(state_file)),
            cwd=product, env=GIT_ENV, text=True, capture_output=True)
        self.assertEqual(0, started.returncode, started.stdout + started.stderr)
        record = json.loads(started.stdout)
        shutil.rmtree(product)

        result = self.stop(state_file=state_file, check=False)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(Path(record["worktree"]).exists())
        self.assertFalse(Path(record["worktree"] + ".owner").exists())
        self.assertFalse(Path(f"/proc/{record['pid']}").exists())
        self.assertTrue(_port_is_free(record["port"]))

    def test_a_copy_of_a_removed_repository_without_its_owner_is_kept(self):
        worktree = Path(tempfile.mkdtemp(prefix="project-launch-"))
        self.addCleanup(shutil.rmtree, worktree, ignore_errors=True)
        state_file = self.new_state_file()
        state_file.write_text(json.dumps({"launch_id": "no-owner", "worktree": str(worktree),
                                          "repo_root": str(worktree) + "-gone", "commit": "0" * 40}))
        result = self.stop(state_file=state_file, check=False)
        self.assertEqual(1, result.returncode)
        self.assertIn("unverified product worktree kept", result.stdout)
        self.assertTrue(worktree.exists())
        state_file.unlink()

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
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        product = Path(tempfile.mkdtemp(prefix="project-launch-contested-"))
        self.addCleanup(shutil.rmtree, product, ignore_errors=True)
        shutil.copytree(ROOT / FIXTURE, product / FIXTURE)
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
        _commit_product(product)

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
                cwd=product, env={**GIT_ENV, "CONTEST_DIR": str(contest)}, text=True, capture_output=True)
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

    def test_a_recipe_that_cannot_be_started_is_refused_and_leaves_nothing(self):
        """A recipe whose program does not exist starts nothing: the copy of
        the commit and the launch record are released (af-wv3qu2). The copy
        is made in a temporary folder of this test alone: another launch on
        the same host makes its own in the shared one at the same moment."""
        descriptor = json.loads(DESCRIPTOR.read_text())
        descriptor["launch"]["recipe"] = ["no-such-program-af-wv3qu2", *descriptor["launch"]["recipe"][1:]]
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = Path(folder) / "descriptor.json"
        path.write_text(json.dumps(descriptor))
        copies = Path(tempfile.mkdtemp(prefix="launch-copies-")).resolve()
        self.addCleanup(shutil.rmtree, copies, ignore_errors=True)

        result, state_file = self.start("--commit", "HEAD", "--dataset", "content", descriptor=path, check=False,
                                        env={**os.environ, "TMPDIR": str(copies)})

        self.assertNotEqual(0, result.returncode)
        error = json.loads(result.stdout)
        self.assertFalse(error["started"])
        self.assertIn("recipe could not be started", error["error"])
        self.assertTrue(error["cleanup_confirmed"])
        self.assertFalse(state_file.exists(), "the refused start kept its launch record")
        self.assertEqual([], list(copies.iterdir()), "the refused start left its copy")

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


    def _owned_launch(self, state_file: Path) -> subprocess.Popen:
        """A launcher that starts the product as its own (`--owner-pid`),
        then waits, as tdd-step does while its tests run."""
        owner = subprocess.Popen(
            [sys.executable, "-c",
             "import os, subprocess, sys, time; "
             "r = subprocess.run([sys.argv[1], '--repo-root', sys.argv[4], 'start', sys.argv[2], '--dataset', 'content', "
             "'--state-file', sys.argv[3], '--owner-pid', str(os.getpid())], capture_output=True, text=True); "
             "print(r.stdout.strip(), flush=True); time.sleep(120)",
             str(TOOL), str(DESCRIPTOR), str(state_file), str(self.product)],
            cwd=ROOT, stdout=subprocess.PIPE, text=True)
        self.addCleanup(owner.stdout.close)
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        self.assertTrue(json.loads(owner.stdout.readline())["started"])
        return owner

    def _until_no_children(self, seconds: float = 20.0) -> list[int]:
        deadline = time.monotonic() + seconds
        while (left := _children()) and time.monotonic() < deadline:
            time.sleep(0.2)
        return left

    def test_a_launch_ends_when_its_owner_is_killed(self):
        # af-f7x7w7: tdd-step stopped its product in a `finally`, which a
        # SIGTERM or SIGKILL (evidence-capture's timeout) never runs; the
        # product, in its own session, outlived it for days.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=sig.name), _adopting_orphans():
                state_file = self.new_state_file()
                owner = self._owned_launch(state_file)
                record = json.loads(state_file.read_text())
                owner.send_signal(sig)
                owner.wait(timeout=5)
                left = self._until_no_children()
                _end(left)
                self.assertEqual([], left, "a process of the launch outlived its owner")
                self.assertFalse(state_file.exists(), "the launch record outlived its owner")
                self.assertFalse(Path(record["worktree"]).exists(), "the launch copy outlived its owner")
                self.assertTrue(_port_is_free(record["port"]))

    def test_a_launch_ends_when_its_owner_is_killed_before_it_is_healthy(self):
        # af-f7x7w7, second measure: an agent's tool timeout killed
        # prototype-fidelity, and project-launch start with it, while the
        # product was still answering its probe; the record said
        # started=false and the product lived on.
        descriptor = json.loads(DESCRIPTOR.read_text())
        descriptor["launch"]["recipe"] = ["{python}", "-c", "import time; time.sleep(120)"]
        slow = Path(tempfile.mkdtemp(prefix="project-launch-slow-")) / "descriptor.json"
        self.addCleanup(shutil.rmtree, slow.parent, True)
        slow.write_text(json.dumps(descriptor))
        with _adopting_orphans():
            state_file = self.new_state_file()
            owner = subprocess.Popen(
                [sys.executable, "-c",
                 "import os, subprocess, sys, time; "
                 "subprocess.Popen([sys.argv[1], '--repo-root', sys.argv[4], 'start', sys.argv[2], '--dataset', 'content', '--timeout', '60', "
                 "'--state-file', sys.argv[3], '--owner-pid', str(os.getpid())]); time.sleep(120)",
                 str(TOOL), str(slow), str(state_file), str(self.product)],
                cwd=ROOT, start_new_session=True)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with contextlib.suppress(OSError, ValueError):
                    if "pid" in json.loads(state_file.read_text()):
                        break
                time.sleep(0.2)
            record = json.loads(state_file.read_text())
            self.assertFalse(record["started"])
            os.killpg(owner.pid, signal.SIGKILL)  # as evidence-capture's timeout does
            owner.wait(timeout=5)
            left = self._until_no_children()
            _end(left)
        self.assertEqual([], left, "a process of the launch outlived its killed owner")
        self.assertFalse(state_file.exists(), "the launch record outlived its owner")
        self.assertFalse(Path(record["worktree"]).exists(), "the launch copy outlived its owner")

    def test_an_owned_launch_stopped_normally_leaves_no_guard(self):
        with _adopting_orphans():
            state_file = self.new_state_file()
            owner = self._owned_launch(state_file)
            self.stop(state_file=state_file)
            owner.kill()
            owner.wait(timeout=5)
            left = self._until_no_children()
            _end(left)
        self.assertEqual([], left, "the guard outlived a normal stop")

    def test_start_refuses_an_owner_that_is_not_running(self):
        dead = subprocess.Popen(["true"])
        dead.wait()
        result, state_file = self.start("--dataset", "content", "--owner-pid", str(dead.pid), check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("owner", json.loads(result.stdout)["error"])
        self.assertFalse(state_file.exists())

    def test_every_factory_launcher_owns_what_it_starts(self):
        # The class, not tdd-step alone: each tool that starts a product
        # names itself its owner, so the product ends with it.
        callers = [path for path in sorted((ROOT / "bin").iterdir())
                   if path.name != "project-launch" and path.is_file()
                   and "LAUNCH_TOOL" in path.read_text(errors="replace")
                   and '"start"' in path.read_text(errors="replace")]
        # Their products outlive the command on purpose: an open Acceptance
        # Session, or products prepared for reuse, ended by their own records.
        detached = {"acceptance-session", "ticket-evaluation", "outcome-evaluation"}
        self.assertTrue(detached <= {path.name for path in callers})
        owners = [path for path in callers if path.name not in detached]
        self.assertGreaterEqual(len(owners), 4)
        for path in owners:
            with self.subTest(caller=path.name):
                self.assertTrue('"--owner-pid", str(os.getpid())' in path.read_text(),
                                f"{path.name} starts a product it does not own")
        # They say so: no launch is left without an owner by omission.
        for path in callers:
            if path.name in detached:
                with self.subTest(caller=path.name):
                    self.assertIn('"start", "--detached"', path.read_text())

    # --- every launch ends, whoever calls (22/10/2026, af-npz9v1) -----------

    def _traced(self) -> list[dict]:
        if not self.trace.exists():
            return []
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def _until_gone(self, record: dict, seconds: float = 30.0) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and Path(record["worktree"]).exists():
            time.sleep(0.2)
        self.assertFalse(Path(record["worktree"]).exists(), "the launch copy outlived the rule")
        self.assertTrue(_port_is_free(record["port"]), "the launch still holds its port")

    def test_a_launch_without_owner_pid_is_owned_by_its_caller(self):
        # ticket-evaluation, outcome-evaluation and the criteria tests passed
        # no --owner-pid: their products lived on after them.
        with _adopting_orphans():
            state_file = self.new_state_file()
            caller = subprocess.Popen(
                [sys.executable, "-c",
                 "import subprocess, sys, time; "
                 "r = subprocess.run([sys.argv[1], '--repo-root', sys.argv[4], 'start', sys.argv[2], '--dataset', 'content', "
                 "'--state-file', sys.argv[3]], capture_output=True, text=True); "
                 "print(r.stdout.strip(), flush=True); time.sleep(120)",
                 str(TOOL), str(DESCRIPTOR), str(state_file), str(self.product)],
                cwd=ROOT, stdout=subprocess.PIPE, text=True)
            self.addCleanup(caller.stdout.close)
            record = json.loads(caller.stdout.readline())
            self.assertTrue(record["started"])
            caller.kill()
            caller.wait(timeout=5)
            left = self._until_no_children()
            _end(left)
        self.assertEqual([], left, "a process of the launch outlived its caller")
        self.assertFalse(state_file.exists())
        self._until_gone(record)
        self.assertEqual(["owner_ended"], [event["reason"] for event in self._traced()])

    def test_a_detached_launch_outlives_its_caller_until_stop(self):
        result, state_file = self.start("--dataset", "content", "--detached")
        record = json.loads(result.stdout)
        # `start` itself, its caller here, has ended: the product still answers.
        self.assertEqual(200, _fetch(record["address"] + "/health")[0])
        self.stop(state_file=state_file)
        self._until_gone(record)
        self.assertEqual([], self._traced(), "a stop asked for is not a stop of the guard")

    def test_detached_and_an_owner_are_refused_together(self):
        result, state_file = self.start("--dataset", "content", "--detached", "--owner-pid", str(os.getpid()),
                                        check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--detached", json.loads(result.stdout)["error"])
        self.assertFalse(state_file.exists())

    def test_a_launch_ends_at_its_lifetime(self):
        result, state_file = self.start("--dataset", "content", "--detached", "--max-lifetime", "8")
        record = json.loads(result.stdout)
        self._until_gone(record)
        self.assertFalse(state_file.exists())
        [event] = self._traced()
        self.assertEqual(("guard", "lifetime_over", record["launch_id"], True),
                         (event["by"], event["reason"], event["launch_id"], event["stopped"]))

    def test_a_launch_whose_record_is_removed_without_stop_ends(self):
        # 22/10/2026: the criteria tests deleted their folder, launch records
        # included, after a stop that did not end the product; the guard
        # took the missing record for a stop and left. 24 cockpits ran on
        # for up to 283 minutes.
        result, state_file = self.start("--dataset", "content")
        record = json.loads(result.stdout)
        state_file.unlink()
        self._until_gone(record)
        [event] = self._traced()
        self.assertEqual(("guard", "record_removed", True), (event["by"], event["reason"], event["stopped"]))

    def test_a_record_reused_by_another_launch_does_not_stop_it(self):
        first, state_file = self.start("--dataset", "content")
        record = json.loads(first.stdout)
        self.stop(state_file=state_file)
        result = subprocess.run([str(TOOL), "--repo-root", str(self.product), "start", str(DESCRIPTOR),
                                 "--dataset", "content", "--state-file", str(state_file)],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        second = json.loads(result.stdout)
        time.sleep(3)  # longer than a round of the first launch's guard
        self.assertEqual(200, _fetch(second["address"] + "/health")[0])
        self.assertTrue(Path(record["worktree"]) != Path(second["worktree"]))
        self.assertEqual([], self._traced())

    def _private_tmp(self) -> dict:
        """An environment whose launch copies live in a folder of this test:
        the sweep it runs releases them, and nothing of the host's."""
        folder = Path(tempfile.mkdtemp(prefix="launch-sweep-")).resolve()
        self.addCleanup(shutil.rmtree, folder, True)
        self._launch_env = {**os.environ, "TMPDIR": str(folder)}
        return self._launch_env

    def _guard_of(self, launch_id: str) -> int:
        for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
            with contextlib.suppress(OSError):
                argv = cmdline.read_bytes().split(b"\0")
                if b"guard" in argv and launch_id.encode() in argv:
                    return int(cmdline.parent.name)
        self.fail(f"no guard for launch {launch_id}")

    def test_the_sweep_stops_a_launch_whose_owner_and_guard_have_ended(self):
        env = self._private_tmp()
        owner = subprocess.Popen(["sleep", "120"])
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        result, state_file = self.start("--dataset", "content", "--owner-pid", str(owner.pid), env=env)
        record = json.loads(result.stdout)
        os.kill(self._guard_of(record["launch_id"]), signal.SIGKILL)  # a guard killed, a host restarted
        owner.kill()
        owner.wait(timeout=5)
        sweep = [str(TOOL), "sweep", "--launch-id", record["launch_id"]]
        dry = json.loads(subprocess.run([*sweep, "--dry-run"], env=env, text=True, capture_output=True,
                                        check=True).stdout)
        self.assertEqual(["owner_ended"], [event["reason"] for event in dry["stopped"]])
        self.assertEqual(200, _fetch(record["address"] + "/health")[0], "a dry run stopped the launch")
        swept = json.loads(subprocess.run(sweep, env=env, text=True, capture_output=True, check=True).stdout)
        self.assertEqual([record["worktree"]], [event["worktree"] for event in swept["stopped"]])
        self._until_gone(record, seconds=5)
        [event] = self._traced()
        self.assertEqual(("sweep", "owner_ended", True), (event["by"], event["reason"], event["stopped"]))

    def test_the_sweep_keeps_a_launch_whose_owner_lives(self):
        env = self._private_tmp()
        result, state_file = self.start("--dataset", "content", env=env)
        record = json.loads(result.stdout)
        swept = json.loads(subprocess.run([str(TOOL), "sweep", "--launch-id", record["launch_id"]], env=env,
                                          text=True, capture_output=True, check=True).stdout)
        self.assertEqual(([], 1), (swept["stopped"], swept["running_kept"]))
        self.assertEqual(200, _fetch(record["address"] + "/health")[0])
        self.stop(state_file=state_file)

    def test_a_launch_ends_with_its_owner_after_its_temporary_folder_is_removed(self):
        # 22/10/2026: 25 fixture products of acceptance tests outlived them
        # for up to 39 hours; each test had removed its TMPDIR, and the
        # guard, which could no longer read it, ended on that error.
        env = self._private_tmp()
        with _adopting_orphans():
            state_file = self.new_state_file()
            caller = subprocess.Popen(
                [sys.executable, "-c",
                 "import subprocess, sys, time; "
                 "r = subprocess.run([sys.argv[1], '--repo-root', sys.argv[4], 'start', sys.argv[2], '--dataset', 'content', "
                 "'--state-file', sys.argv[3]], capture_output=True, text=True); "
                 "print(r.stdout.strip(), flush=True); time.sleep(120)",
                 str(TOOL), str(DESCRIPTOR), str(state_file), str(self.product)],
                cwd=ROOT, env=env, stdout=subprocess.PIPE, text=True)
            self.addCleanup(caller.stdout.close)
            record = json.loads(caller.stdout.readline())
            self.assertTrue(record["started"])
            shutil.rmtree(env["TMPDIR"])
            caller.kill()
            caller.wait(timeout=5)
            left = self._until_no_children()
            _end(left)
        self.assertEqual([], left, "a process of the launch outlived its caller")
        self.assertFalse(state_file.exists())
        self.assertTrue(_port_is_free(record["port"]))
        self.assertEqual([("owner_ended", True)], [(event["reason"], event["stopped"]) for event in self._traced()])

    def test_the_sweep_releases_a_copy_left_without_process(self):
        env = self._private_tmp()
        result, state_file = self.start("--dataset", "content", "--detached", env=env)
        record = json.loads(result.stdout)
        os.kill(self._guard_of(record["launch_id"]), signal.SIGKILL)
        os.killpg(record["process_group"], signal.SIGKILL)  # the product died; its copy stayed
        time.sleep(0.5)
        old = time.time() - 7 * 3600
        os.utime(f"{record['worktree']}.owner", (old, old))
        swept = json.loads(subprocess.run([str(TOOL), "sweep", "--launch-id", record["launch_id"]], env=env,
                                          text=True, capture_output=True, check=True).stdout)
        self.assertEqual(["copy_left"], [event["reason"] for event in swept["released"]])
        self.assertFalse(Path(record["worktree"]).exists())
        self.assertFalse(Path(f"{record['worktree']}.owner").exists())


if __name__ == "__main__":
    unittest.main()
