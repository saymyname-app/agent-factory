#!/usr/bin/env python3
"""S.load-cut: a pass of an order cut by its budget is deferred (exit 0);
only DEFER_LIMIT passes cut in a row fail; a pass that ends clears the count
(bin/bounded-pass, af-56yoam.7)."""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "bounded-pass"
_loader = importlib.machinery.SourceFileLoader("bounded_pass", str(TOOL))
_spec = importlib.util.spec_from_loader("bounded_pass", _loader)
bounded_pass = importlib.util.module_from_spec(_spec)
_loader.exec_module(bounded_pass)

ENDS = ["sh", "-c", "exit 4"]
HANGS = ["sleep", "30"]
GIVES_UP = ["sh", "-c", "exit 75"]


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


class BoundedPassTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="bounded-pass-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.root)])
        self.count = self.root / ".gc" / "runtime" / "some-order-deferred-passes"

    def run_pass(self, command: list[str], *extra: str, budget: str = "0.2") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"FACTORY_ROOT": str(self.root)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = bounded_pass.main(["some-order", "--budget", budget, "--kill-after", "0.2", *extra,
                                      "--", *command])
        return code, out.getvalue(), err.getvalue()

    def counted(self) -> int:
        return int(self.count.read_text()) if self.count.exists() else 0

    def test_the_table_of_passes(self) -> None:
        self.assertEqual(bounded_pass.DEFER_LIMIT, 3)
        # (case, cut in a row before, command, extra options, exit, cut in a row after, said)
        table = [
            ("a pass that ends keeps its own exit", 0, ENDS, [], 4, 0, ""),
            ("cut once: deferred, count 1", 0, HANGS, [], 0, 1,
             "some-order: budget exceeded after 0.2s — pass deferred (1 of 3 in a row, loadavg "),
            ("cut a second time in a row: still deferred", 1, HANGS, [], 0, 2, "(2 of 3 in a row"),
            ("cut the third time in a row: the order fails", 2, HANGS, [], 2, 3,
             "some-order: budget exceeded after 0.2s — 3 passes in a row cut short"),
            ("a pass that ends clears the count", 2, ENDS, [], 4, 0, ""),
            ("a pass that gives up by itself counts as cut", 0, GIVES_UP, ["--deferred-exit", "75"], 0, 1,
             "pass gave up within its 0.2s budget (exit 75) — pass deferred (1 of 3"),
            ("without --deferred-exit, 75 is the pass's own exit", 2, GIVES_UP, [], 75, 0, ""),
        ]
        for case, before, command, extra, code, after, said in table:
            with self.subTest(case):
                self.count.unlink(missing_ok=True)
                if before:
                    self.count.parent.mkdir(parents=True, exist_ok=True)
                    self.count.write_text(f"{before}\n")
                got, out, err = self.run_pass(command, *extra)
                self.assertEqual(got, code, out + err)
                self.assertEqual(self.counted(), after)
                self.assertIn(said, out + err)

    def test_a_cut_pass_leaves_nothing_alive_even_in_another_group(self) -> None:
        pid_file = self.root / "pid"
        # The pass starts a process in a session of its own, as timeout(1) does.
        command = [sys.executable, "-c",
                   "import pathlib,subprocess,sys,time; "
                   "c=subprocess.Popen(['sleep','60'], start_new_session=True); "
                   f"pathlib.Path({str(pid_file)!r}).write_text(str(c.pid)); time.sleep(60)"]
        # Long enough for the interpreter to start and write the pid under load.
        code, out, _ = self.run_pass(command, budget="3")
        self.assertEqual(code, 0, out)
        left = int(pid_file.read_text())
        deadline = time.monotonic() + 5
        while alive(left) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(alive(left), "a process the cut pass left in another group is still alive")

    def test_the_command_line_runs_a_pass_and_refuses_a_bad_budget(self) -> None:
        env = dict(os.environ, FACTORY_ROOT=str(self.root))
        done = subprocess.run([str(TOOL), "some-order", "--budget", "5", "--", "sh", "-c", "echo ran; exit 3"],
                              capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual((done.returncode, done.stdout), (3, "ran\n"), done.stderr)
        refused = subprocess.run([str(TOOL), "some-order", "--budget", "0", "--", "true"],
                                 capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("must be above 0", refused.stderr)


if __name__ == "__main__":
    unittest.main()
