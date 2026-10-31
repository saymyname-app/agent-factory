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


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from bounded_process import run as bounded_run  # noqa: E402

EXCEPTIONS = ROOT / "config" / "bounded-process-exceptions.tsv"


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def direct_timed_calls() -> set[str]:
    found = set()
    for directory in (ROOT / "bin", ROOT / "lib", ROOT / "tests" / "cockpit-criteria"):
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                function = node.func if isinstance(node, ast.Call) else None
                if (isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
                        and function.value.id == "subprocess" and function.attr in {"run", "Popen"}
                        and any(keyword.arg == "timeout" for keyword in node.keywords)):
                    found.add(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def listed_exceptions() -> set[str]:
    found = set()
    for number, line in enumerate(EXCEPTIONS.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3 or not parts[2].strip():
            raise AssertionError(f"{EXCEPTIONS.relative_to(ROOT)}:{number}: expected date, location and reason")
        observed = datetime.date.fromisoformat(parts[0])
        if observed > datetime.date.today():
            raise AssertionError(f"{EXCEPTIONS.relative_to(ROOT)}:{number}: future observation date")
        if parts[1] in found:
            raise AssertionError(f"{EXCEPTIONS.relative_to(ROOT)}:{number}: duplicate {parts[1]}")
        found.add(parts[1])
    return found


class BoundedProcessTest(unittest.TestCase):
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

    def test_every_direct_subprocess_timeout_is_a_dated_exception(self) -> None:
        self.assertEqual(listed_exceptions(), direct_timed_calls())


if __name__ == "__main__":
    unittest.main()
