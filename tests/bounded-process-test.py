#!/usr/bin/env python3
"""Category P: timed commands own and stop their whole process group."""
from __future__ import annotations

import ast
import datetime
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import bounded_process  # noqa: E402
from bounded_process import run as bounded_run  # noqa: E402

EXCEPTIONS = ROOT / "config" / "bounded-process-exceptions.tsv"
DETACHED = ROOT / "config" / "detached-process-exceptions.tsv"
OWNER = """
import pathlib, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import bounded_process
program = ("import pathlib,subprocess,sys,time; "
           "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
           "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)")
if sys.argv[3] == "run":
    bounded_process.run([sys.executable, "-c", program, sys.argv[2]], timeout=60)
else:
    bounded_process.popen([sys.executable, "-c", program, sys.argv[2]])
    time.sleep(60)
"""


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


def times_out(call: ast.Call) -> bool:
    return any(keyword.arg == "timeout" for keyword in call.keywords)


def opens_a_session(call: ast.Call) -> bool:
    """`start_new_session` given anything but a literal False."""
    return any(keyword.arg == "start_new_session"
               and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is False)
               for keyword in call.keywords)


def call_sites(tree: ast.AST, path: str, matches) -> set[str]:
    """Each subprocess.run/Popen of `tree` that `matches`, named by its file
    and the function that holds it (`path:Class.function`, `path:<module>` at
    top level), then `#2`, `#3`… after the first in the same function. A name,
    not a line number: a line added elsewhere in the file leaves it unchanged
    (af-vy9ajj)."""
    found = set()
    seen: dict[str, int] = {}

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            function = child.func if isinstance(child, ast.Call) else None
            if (isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
                    and function.value.id == "subprocess" and function.attr in {"run", "Popen"}
                    and matches(child)):
                site = f"{path}:{'.'.join(scope) or '<module>'}"
                seen[site] = seen.get(site, 0) + 1
                found.add(site if seen[site] == 1 else f"{site}#{seen[site]}")
            named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            visit(child, (*scope, child.name) if named else scope)

    visit(tree, ())
    return found


def scanned_calls(matches, skip: Path | None = None) -> set[str]:
    found = set()
    for directory in (ROOT / "bin", ROOT / "lib", ROOT / "tests" / "cockpit-criteria"):
        for path in directory.rglob("*"):
            if not path.is_file() or path == skip:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            found |= call_sites(tree, str(path.relative_to(ROOT)), matches)
    return found


def direct_timed_calls() -> set[str]:
    return scanned_calls(times_out)


def guards() -> set[int]:
    """The pids of the guards this test process started and that still run
    (other guards of the host are not this test's business)."""
    found = set()
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                argv = (entry / "cmdline").read_bytes().split(b"\0")
                parent = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            if bounded_process.GUARD_NAME.encode() in argv and parent == os.getpid() and alive(int(entry.name)):
                found.add(int(entry.name))
    return found


def detached_sessions() -> set[str]:
    """Every subprocess.run/Popen given `start_new_session` (anything but a
    literal False) outside the one launcher."""
    return scanned_calls(opens_a_session, skip=ROOT / "lib" / "bounded_process.py")


def listed_exceptions(listing: Path = EXCEPTIONS) -> set[str]:
    found = set()
    for number, line in enumerate(listing.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3 or not parts[2].strip():
            raise AssertionError(f"{listing.relative_to(ROOT)}:{number}: expected date, location and reason")
        observed = datetime.date.fromisoformat(parts[0])
        if observed > datetime.date.today():
            raise AssertionError(f"{listing.relative_to(ROOT)}:{number}: future observation date")
        if parts[1] in found:
            raise AssertionError(f"{listing.relative_to(ROOT)}:{number}: duplicate {parts[1]}")
        found.add(parts[1])
    return found


class BoundedProcessTest(unittest.TestCase):
    def test_a_process_disappearing_during_liveness_read_is_not_alive(self) -> None:
        with mock.patch.object(Path, "read_text", side_effect=ProcessLookupError):
            self.assertFalse(alive(123))

    def test_timeout_kills_the_commands_descendants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bounded-process-") as folder:
            child_pid = Path(folder) / "child.pid"
            program = (
                "import pathlib,subprocess,sys,time; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    bounded_run([sys.executable, "-c", program, str(child_pid)], timeout=1)
                pid = int(child_pid.read_text())
                deadline = time.monotonic() + 2
                while alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertFalse(alive(pid), "a descendant outlived the bounded command")
            finally:
                if child_pid.exists() and alive(pid := int(child_pid.read_text())):
                    os.kill(pid, signal.SIGKILL)

    def test_an_exception_keeps_its_name_when_lines_move_around_it(self) -> None:
        # 12/11/2026: #866 and #867, unrelated, went red because lines added
        # above it moved bin/convoy-advance's listed fidelity check off 3768.
        source = (
            "import subprocess\n"
            "class Trial:\n"
            "    def start(self):\n"
            "        subprocess.Popen(['a'], start_new_session=True)\n"
            "        subprocess.run(['b'], start_new_session=False)\n"
            "        subprocess.run(['c'], start_new_session=True)\n"
            "subprocess.Popen(['d'], start_new_session=True)\n"
        )
        named = {"bin/x:Trial.start", "bin/x:Trial.start#2", "bin/x:<module>"}
        self.assertEqual(named, call_sites(ast.parse(source), "bin/x", opens_a_session))
        moved = source.replace("class Trial:\n", "import os\n\n\nclass Trial:\n    'Moved.'\n")
        self.assertEqual(named, call_sites(ast.parse(moved), "bin/x", opens_a_session))

    def test_every_direct_subprocess_timeout_is_a_dated_exception(self) -> None:
        self.assertEqual(listed_exceptions(), direct_timed_calls())

    def test_every_session_outside_the_launcher_is_a_dated_exception(self) -> None:
        # A session of its own outlives its caller unless lib/bounded_process.py
        # guards it: each other one is detached on purpose and says why.
        self.assertEqual(listed_exceptions(DETACHED), detached_sessions())

    def owner_killed(self, mode: str) -> int:
        """Start an owner that runs a command through the launcher (`mode`:
        run or popen), kill the owner with SIGKILL once the command has a
        descendant, and return that descendant's pid."""
        with tempfile.TemporaryDirectory(prefix="bounded-process-") as folder:
            child_pid = Path(folder) / "child.pid"
            owner = subprocess.Popen([sys.executable, "-c", OWNER, str(ROOT / "lib"), str(child_pid), mode])
            try:
                deadline = time.monotonic() + 20
                while not (child_pid.exists() and child_pid.read_text()) and time.monotonic() < deadline:
                    time.sleep(0.05)
                pid = int(child_pid.read_text())
                self.assertTrue(alive(pid))
            finally:
                owner.kill()
                owner.wait()
            return pid

    def assert_dies(self, pid: int) -> None:
        try:
            deadline = time.monotonic() + 5
            while alive(pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(alive(pid), "a descendant outlived its killed caller")
        finally:
            if alive(pid):
                os.kill(pid, signal.SIGKILL)

    def test_a_caller_killed_during_run_takes_the_whole_group_with_it(self) -> None:
        # 10/11/2026: the order killed the pass at 90 min, its regression ran
        # on alone and wrote a green piece no merge followed (af-8cfygl).
        self.assert_dies(self.owner_killed("run"))

    def test_a_caller_killed_while_it_holds_a_popen_takes_the_group_with_it(self) -> None:
        self.assert_dies(self.owner_killed("popen"))

    def test_a_released_group_is_left_alone_and_its_guard_leaves(self) -> None:
        process = bounded_process.popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            watcher, _ = process.bounded_guard
            bounded_process.release(process)
            self.assertIsNotNone(watcher.poll(), "the guard outlived its release")
            time.sleep(0.2)
            self.assertIsNone(process.poll(), "a released group was killed")
        finally:
            bounded_process.kill_group(process)
            process.wait()

    def test_a_run_that_ends_leaves_no_guard_behind(self) -> None:
        before = guards()
        bounded_run([sys.executable, "-c", "pass"], timeout=30)
        self.assertEqual(before, guards())


if __name__ == "__main__":
    unittest.main()
