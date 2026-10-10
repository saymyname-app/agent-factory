#!/usr/bin/env python3
"""bin/ci-test-ceiling (Spec CI01, af-q9urgr §3, user stories 16 and 17;
Testing Decisions 3, 4 and 6): no test file above 120 seconds in the seconds
Factory CI records, outside the known list and the written exceptions.

Each case calls the command's entry function in this process, with the
arguments of the command line, on a tree fabricated for it: the recorded
seconds, the known list and the test files it names. One pass and one
refusal are launched as real processes. The pass is the control on the
repository itself, which is what makes a pull request red in CI when it
records a file above the ceiling.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "ci-test-ceiling"
SECONDS = Path("config") / "ci-test-seconds.tsv"
KNOWN = Path("config") / "ci-test-ceiling-known.txt"

# Two of the files that were above the ceiling when the control was introduced.
LISTED = "tests/convoy-advance-test.py"
OTHER_LISTED = "tests/tdd-step-test.py"

_loader = importlib.machinery.SourceFileLoader("ci_test_ceiling", str(CLI))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
tool = importlib.util.module_from_spec(_spec)
_loader.exec_module(tool)


def call(*args):
    """The command line, in this process: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tool.main(["ci-test-ceiling", *args])
    return code, out.getvalue(), err.getvalue()


class CeilingTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ci-test-ceiling-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def tree(self, seconds, known=(), files=None):
        """A tree whose recorded seconds are `seconds` ({path: seconds}), whose
        known list names `known`, and whose test files hold `files` ({path:
        text}; a measured file not given holds one comment line)."""
        (self.root / "config").mkdir(exist_ok=True)
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / SECONDS).write_text(
            "# Seconds each test file took.\n"
            + "".join("%s\t%d\n" % item for item in sorted(seconds.items())),
            encoding="utf-8",
        )
        (self.root / KNOWN).write_text(
            "# The known list.\n" + "".join(path + "\n" for path in known), encoding="utf-8"
        )
        for path in seconds:
            (self.root / path).write_text((files or {}).get(path, "# a test\n"), encoding="utf-8")
        return str(self.root)

    def passed(self, result, *words):
        code, out, err = result
        self.assertEqual((code, err), (0, ""), result)
        self.assertEqual(len(out.splitlines()), 1, out)
        for word in words:
            self.assertIn(word, out)

    def refused(self, result, *words):
        code, out, err = result
        self.assertEqual((code, out), (1, ""), result)
        for word in words:
            self.assertIn(word, err)
        return err

    # --- under and above ---------------------------------------------------

    def test_files_at_or_under_the_ceiling_pass(self):
        root = self.tree({"tests/a-test.py": 3, "tests/b-test.sh": 120})
        self.passed(call("check", "--root", root), "2 test files measured", "0 on the list")

    def test_a_file_above_the_ceiling_is_refused_by_name_with_its_seconds(self):
        root = self.tree({"tests/a-test.py": 3, "tests/slow-test.py": 121})
        err = self.refused(call("check", "--root", root), "tests/slow-test.py", "121 s", "120 s")
        self.assertNotIn("tests/a-test.py", err)
        self.assertEqual(len(err.splitlines()), 1, err)

    def test_a_recorded_line_whose_file_is_gone_is_not_a_refusal(self):
        root = self.tree({"tests/a-test.py": 3, "tests/gone-test.py": 500})
        (self.root / "tests" / "gone-test.py").unlink()
        self.passed(call("check", "--root", root))

    def test_seconds_that_cannot_be_read_are_a_refusal(self):
        root = self.tree({"tests/a-test.py": 3})
        (self.root / SECONDS).unlink()
        self.refused(call("check", "--root", root), "config/ci-test-seconds.tsv", "nothing is checked")

    def test_recorded_seconds_without_one_duration_are_a_refusal(self):
        for text in ("", "# Seconds each test file took.\n", "\n\n"):
            with self.subTest(text=text):
                root = self.tree({})
                (self.root / SECONDS).write_text(text, encoding="utf-8")
                self.refused(call("check", "--root", root), "config/ci-test-seconds.tsv", "holds no duration")

    def test_a_malformed_line_of_the_recorded_seconds_is_refused_with_its_number(self):
        for line in ("tests/slow-test.py 300", "tests/slow-test.py\t", "tests/slow-test.py\t300s",
                     "tests/slow-test.py\t300\textra", "\t300"):
            with self.subTest(line=line):
                root = self.tree({"tests/a-test.py": 3})
                (self.root / SECONDS).write_text(
                    "# Seconds each test file took.\ntests/a-test.py\t3\n%s\n" % line, encoding="utf-8"
                )
                err = self.refused(call("check", "--root", root), "config/ci-test-seconds.tsv, line 3", line)
                self.assertEqual(len(err.splitlines()), 1, err)

    def test_comment_and_blank_lines_of_the_recorded_seconds_are_not_durations(self):
        root = self.tree({})
        (self.root / SECONDS).write_text(
            "# Seconds each test file took in Factory CI run 1 of o/r.\n# Written by bin/ci-test-seconds.\n"
            "tests/a-test.py\t3\n\n",
            encoding="utf-8",
        )
        self.passed(call("check", "--root", root), "1 test files measured")

    def test_prune_leaves_the_list_as_it_is_when_the_recorded_seconds_hold_no_duration(self):
        root = self.tree({}, known=[LISTED])
        before = (self.root / KNOWN).read_text(encoding="utf-8")
        self.refused(call("prune", "--root", root), "holds no duration", "left as it is")
        self.assertEqual((self.root / KNOWN).read_text(encoding="utf-8"), before)

    # --- the written exception --------------------------------------------

    def test_a_written_exception_with_its_reason_passes(self):
        root = self.tree(
            {"tests/slow-test.py": 300},
            files={"tests/slow-test.py": "#!/bin/sh\n# ci: over-ceiling — one journey that cannot be cut\n"},
        )
        self.passed(call("check", "--root", root), "1 with a written exception")

    def test_a_written_exception_without_reason_is_refused(self):
        for line in ("# ci: over-ceiling", "# ci: over-ceiling — ", "# ci: over-ceiling -",
                     "# ci: over-ceiling — <reason>", "# ci: over-ceiling — <Raison>",
                     "# ci: over-ceiling — too slow", "# ci: over-ceiling — 123456789"):
            with self.subTest(line=line):
                root = self.tree({"tests/slow-test.py": 300}, files={"tests/slow-test.py": line + "\n"})
                self.refused(call("check", "--root", root), "tests/slow-test.py", "gives no reason")

    # --- the known list -----------------------------------------------------

    def test_a_file_of_the_known_list_passes_while_it_is_above(self):
        root = self.tree({LISTED: 923, "tests/a-test.py": 3}, known=[LISTED])
        self.passed(call("check", "--root", root), "1 on the list")

    def test_a_list_that_grows_is_refused(self):
        root = self.tree({LISTED: 923, "tests/new-test.py": 400}, known=[LISTED, "tests/new-test.py"])
        err = self.refused(call("check", "--root", root), "tests/new-test.py", "only shrinks")
        self.assertNotIn(LISTED, err)

    def test_a_listed_file_no_longer_above_must_leave_the_list(self):
        root = self.tree({LISTED: 80, OTHER_LISTED: 185}, known=[LISTED, OTHER_LISTED])
        err = self.refused(call("check", "--root", root), LISTED, "80 s", "leaves the list", "prune")
        self.assertNotIn(OTHER_LISTED, err)

    def test_a_listed_file_without_recorded_seconds_must_leave_the_list(self):
        root = self.tree({OTHER_LISTED: 185}, known=[LISTED, OTHER_LISTED])
        self.refused(call("check", "--root", root), LISTED, "no line", "leaves the list")

    def test_a_file_that_left_the_list_and_is_above_again_is_refused(self):
        root = self.tree({LISTED: 400}, known=[])
        self.refused(call("check", "--root", root), LISTED, "400 s")

    # --- prune ----------------------------------------------------------------

    def test_prune_removes_only_the_lines_no_longer_above_and_check_passes_after(self):
        root = self.tree({LISTED: 80, OTHER_LISTED: 185}, known=[LISTED, OTHER_LISTED])
        self.passed(call("prune", "--root", root), "1 line(s) removed", LISTED, "1 left")
        self.assertEqual(
            (self.root / KNOWN).read_text(encoding="utf-8"), "# The known list.\n%s\n" % OTHER_LISTED
        )
        self.passed(call("check", "--root", root), "1 on the list")

    def test_prune_never_adds_a_line_and_leaves_a_list_that_grew_refused(self):
        root = self.tree({"tests/new-test.py": 400}, known=["tests/new-test.py"])
        before = (self.root / KNOWN).read_text(encoding="utf-8")
        self.passed(call("prune", "--root", root), "0 line(s) removed")
        self.assertEqual((self.root / KNOWN).read_text(encoding="utf-8"), before)
        self.refused(call("check", "--root", root), "tests/new-test.py", "only shrinks")

    # --- usage ----------------------------------------------------------------

    def test_an_unknown_command_is_a_usage_error(self):
        for args in ((), ("verify",), ("check", "--root"), ("check", "extra")):
            with self.subTest(args=args):
                code, out, err = call(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("Usage:", err)

    # --- real processes: one pass, one refusal ---------------------------

    def test_the_repository_itself_passes_as_a_real_process(self):
        result = subprocess.run([str(CLI), "check"], capture_output=True, text=True, timeout=30)
        self.assertEqual((result.returncode, result.stderr), (0, ""), result)
        self.assertIn("none above 120 s outside the known list", result.stdout)

    def test_a_file_above_the_ceiling_is_refused_as_a_real_process(self):
        root = self.tree({"tests/slow-test.py": 121})
        result = subprocess.run(
            [str(CLI), "check", "--root", root], capture_output=True, text=True, timeout=30
        )
        self.assertEqual((result.returncode, result.stdout), (1, ""), result)
        self.assertIn("ci-test-ceiling check: tests/slow-test.py: 121 s", result.stderr)


if __name__ == "__main__":
    unittest.main()
