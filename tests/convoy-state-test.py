#!/usr/bin/env python3
"""bin/convoy-state on a fake tracker state (T33, af-p4d6ec; Spec af-wf4w5r
§0 rule 2, Testing Decisions seam 2): one test per refusal and per pass, each
refusal re-reading the tracker to prove nothing was written. Only the command
line is exercised; ticket branches live in a throwaway Git repository.

One stage down (Spec CI01 §3.1, af-q9urgr): a case gives the command line to
the entry function of the command, `main` of lib/convoy_state.py, in the
process of the tests, and reads what a caller of the command reads: exit
status, standard output, standard error, the fake tracker, the write log. No
other function of the module is called. The commands the tool starts itself
(the fake `gc`, git) stay real processes. A few cases start bin/convoy-state
for real, named by `real_process=True`: one pass, one refusal, the bead given
on standard input, and the eight commands that write at the same time.

    CONVOY_STATE_TEST_REAL_PROCESS=1 python3 tests/convoy-state-test.py

starts every command of every case as a real process, as before: the way to
check a red seen in-process against the real command line."""

import contextlib
import importlib.machinery
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "convoy-state"
MODULE = ROOT / "lib" / "convoy_state.py"  # what bin/convoy-state imports `main` from
REAL_PROCESS = os.environ.get("CONVOY_STATE_TEST_REAL_PROCESS") == "1"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"

CONVOY = "fx-convoy"
T1 = "fx-t1"
T2 = "fx-t2"
ABSENT_COMMIT = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "sha256:" + "ab" * 32

EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4


@contextlib.contextmanager
def standard_streams(stdin_text):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "stdin", io.StringIO(stdin_text or "")), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def call_entry(argv, env, stdin_text=None):
    """One command line given to the entry function, in this process; what a
    process would have returned (status, standard output, standard error).

    The program is read and compiled once. Its module is run anew for each
    call, under the environment of that call: it reads GC_BIN and FACTORY_ROOT
    when it is loaded and keeps the bounds of the flow once read, so a module
    kept from one call to the next would answer with the environment and the
    settings of the first. Nothing of a call is left for the next.

    A `SystemExit` is the exit status (argparse leaves that way). Any other
    exception is a crash of the command: it is not caught, and fails the case
    with its traceback."""
    global _program
    if _program is None:
        _program = importlib.machinery.SourceFileLoader("convoy_state", str(MODULE)).get_code("convoy_state")
    module = types.ModuleType("convoy_state")
    module.__file__ = str(MODULE)
    with mock.patch.dict(os.environ, env, clear=True), \
            mock.patch.object(sys, "argv", [str(TOOL), *argv]), \
            standard_streams(stdin_text) as (out, err):
        try:
            exec(_program, module.__dict__)
            status = module.main(list(argv))
        except SystemExit as exc:
            status = exc.code
    # The interpreter's reading of `raise SystemExit(status)`.
    if status is None:
        status = 0
    elif not isinstance(status, int):
        err.write(f"{status}\n")
        status = 1
    return subprocess.CompletedProcess((str(TOOL), *argv), status, out.getvalue(), err.getvalue())


_program = None


class ConvoyStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="convoy-state-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.repo = self.tmp / "repo"
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.seed()

    # --- harness ------------------------------------------------------------

    def seed(self, tickets=(T1, T2), kinds=None):
        """A published, unmarked convoy. A ticket is a `prefactoring` unless
        `kinds` says otherwise: the one kind that is marked without a
        demonstration line (T05)."""
        beads = {CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                          "metadata": {"gc.spec_id": "fx-spec"}, "tracks": list(tickets)}}
        for ticket in tickets:
            kind = (kinds or {}).get(ticket, "prefactoring")
            beads[ticket] = {"title": f"ticket {ticket}", "status": "open", "issue_type": "task",
                             "metadata": {"gc.ticket_kind": kind} if kind else {}}
        self.tracker.write_text(json.dumps({"beads": beads}))

    def tracker_state(self):
        return json.loads(self.tracker.read_text())

    def edit_tracker(self, bead_id, status=None, **metadata):
        state = self.tracker_state()
        bead = state["beads"][bead_id]
        if status is not None:
            bead["status"] = status
        bead.setdefault("metadata", {}).update(metadata)
        self.tracker.write_text(json.dumps(state))

    def run_tool(self, *args, env=None, input=None, real_process=False):
        """One command line of the tool, under `env` (the case's own by
        default), `input` on its standard input. Given to the entry function
        in this process, unless the case asks for a real process or
        CONVOY_STATE_TEST_REAL_PROCESS=1 asks it for all."""
        argv = [str(a) for a in args]
        env = self.env if env is None else env
        if real_process or REAL_PROCESS:
            return subprocess.run((str(TOOL), *argv), env=env, text=True, capture_output=True, input=input)
        return call_entry(argv, env, input)

    def ok(self, *args):
        proc = self.run_tool(*args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def show(self, expect=0):
        proc = self.run_tool("show", CONVOY, "--repo", self.repo)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def ticket(self, shown, ticket_id):
        return next(t for t in shown["tickets"] if t["id"] == ticket_id)

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid",
             *args), env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def init_repo(self):
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "base")

    def commit_on(self, branch):
        """Add one commit to `branch` (created from main if new); return its SHA."""
        exists = subprocess.run(
            ("git", "-C", str(self.repo), "rev-parse", "-q", "--verify", f"refs/heads/{branch}"),
            capture_output=True,
        ).returncode == 0
        self.git("checkout", "-q", branch) if exists else self.git("checkout", "-q", "-b", branch, "main")
        self.git("commit", "-q", "--allow-empty", "-m", f"work on {branch}")
        return self.git("rev-parse", "HEAD")

    def started_ticket(self, ticket_id=T1, branch="ticket/t1"):
        """A marked convoy whose ticket was started through the dispatch door
        and has one commit on its branch; returns that commit."""
        self.init_repo()
        self.ok("mark", CONVOY)
        tip = self.commit_on(branch)
        self.ok("set-branch", CONVOY, ticket_id, "--branch", branch)
        self.ok("record-gate", CONVOY, ticket_id, "--gate", "dispatch")
        self.edit_tracker(ticket_id, status="in_progress")
        return tip

    def assert_refused_and_nothing_written(self, *args, mention=None, real_process=False):
        before_bytes = self.tracker.read_bytes()
        before_show = self.run_tool("show", CONVOY, "--repo", self.repo).stdout
        writes_before = self.write_log.read_text() if self.write_log.exists() else ""
        proc = self.run_tool(*args, real_process=real_process)
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        refusal = json.loads(proc.stdout)
        self.assertFalse(refusal["ok"])
        if mention:
            self.assertIn(mention, refusal["error"])
        self.assertEqual(before_bytes, self.tracker.read_bytes())
        self.assertEqual(before_show, self.run_tool("show", CONVOY, "--repo", self.repo).stdout)
        self.assertEqual(writes_before, self.write_log.read_text() if self.write_log.exists() else "")
        return proc

    # --- AC1: one read renders the whole durable state ------------------------

    def test_show_names_the_spec_the_convoy_delivers(self):
        """T09: the evidence store is filed by Spec, and the Spec of a convoy
        is read here like the rest of its state."""
        self.ok("mark", CONVOY)
        self.assertEqual("fx-spec", self.show()["convoy"]["spec"])

    def test_show_renders_no_spec_when_the_convoy_names_none(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        del state["beads"][CONVOY]["metadata"]["gc.spec_id"]
        self.tracker.write_text(json.dumps(state))
        self.assertIsNone(self.show()["convoy"]["spec"])

    def test_show_renders_mark_exit_verdicts_counters_evidence_and_gate_records(self):
        tip = self.started_ticket()
        self.ok("set-exit", CONVOY, T1, "--exit", "finished")
        for kind in ("code_review", "evaluation", "fidelity"):
            self.ok("set-verdict", CONVOY, T1, "--kind", kind, "--state", "favorable", "--commit", tip)
        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "unfavorable", "--commit", tip)
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.ok("bump-counter", CONVOY, "--counter", "end_rounds")
        self.ok("add-evidence", CONVOY, T1, "--piece", "red_proof", "--digest", DIGEST, "--commit", tip)
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)

        shown = self.show()
        self.assertTrue(shown["ok"])
        self.assertFalse(shown["unruled"])
        self.assertEqual("new-flow/v1", shown["convoy"]["mark"])
        self.assertEqual({"end_rounds": 1}, shown["convoy"]["counters"])

        t1 = self.ticket(shown, T1)
        self.assertEqual("new-flow/v1", t1["mark"])
        self.assertEqual("closed", t1["status"])
        self.assertEqual("ticket/t1", t1["branch"])
        self.assertEqual(tip, t1["tip"])
        self.assertEqual("finished", t1["exit"]["exit"])
        self.assertEqual({"code_review", "evaluation", "fidelity"}, set(t1["verdicts"]))
        for kind, state in (("code_review", "favorable"),
                            ("evaluation", "unfavorable"), ("fidelity", "favorable")):
            self.assertEqual(state, t1["verdicts"][kind]["state"])
            self.assertEqual(tip, t1["verdicts"][kind]["commit"])
            self.assertIs(True, t1["verdicts"][kind]["valid"])
        self.assertEqual({"resumes": 2, "correction_rounds": 1}, t1["counters"])
        self.assertEqual(DIGEST, t1["evidence"]["red_proof"]["digest"])
        self.assertEqual(tip, t1["evidence"]["red_proof"]["commit"])
        self.assertEqual({"dispatch", "ticket_end"}, set(t1["gates"]))
        self.assertEqual(tip, t1["gates"]["ticket_end"]["commit"])
        self.assertEqual([], t1["unruled"])

        t2 = self.ticket(shown, T2)
        self.assertEqual("new-flow/v1", t2["mark"])
        self.assertIsNone(t2["exit"])
        self.assertEqual({}, t2["verdicts"])
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, t2["counters"])
        self.assertEqual({}, t2["evidence"])
        self.assertEqual({}, t2["gates"])
        self.assertEqual([], t2["unruled"])

    # --- T22: a marked convoy does not close by itself ---------------------------

    def test_mark_puts_the_convoy_and_not_its_tickets_under_manual_lifecycle(self):
        """`owned` is what Gas City's convoy sweep (`gc convoy check`) reads
        to leave a convoy open once all its tickets are closed."""
        self.ok("mark", CONVOY)

        beads = self.tracker_state()["beads"]
        self.assertEqual(["owned"], beads[CONVOY].get("labels"))
        self.assertNotIn("labels", beads[T1])
        self.assertNotIn("labels", beads[T2])

    def test_marking_again_restores_the_manual_lifecycle_of_a_convoy_that_lost_it(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        state["beads"][CONVOY]["labels"] = ["autre"]
        self.tracker.write_text(json.dumps(state))

        self.ok("mark", CONVOY)

        self.assertEqual(["autre", "owned"], self.tracker_state()["beads"][CONVOY]["labels"])

    def test_marking_again_writes_nothing_on_a_convoy_already_under_manual_lifecycle(self):
        self.ok("mark", CONVOY)
        self.write_log.write_text("")

        self.assertEqual([], self.ok("mark", CONVOY)["marked"])
        self.assertEqual("", self.write_log.read_text())

    def test_a_marked_convoy_closed_outside_acceptance_or_abandon_is_unruled(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        state["beads"][CONVOY].update(status="closed", close_reason="convoy autoclose: all children closed")
        self.tracker.write_text(json.dumps(state))

        shown = self.show(expect=EXIT_UNRULED)

        self.assertEqual("closed", shown["convoy"]["status"])
        reasons = [entry["reason"] for entry in shown["convoy"]["unruled"]]
        self.assertEqual(1, len(reasons), reasons)
        self.assertIn("fermé hors commande", reasons[0])
        self.assertIn("convoy autoclose: all children closed", reasons[0])

    def test_an_open_marked_convoy_whose_tickets_are_all_closed_is_not_unruled_for_that(self):
        tip = self.started_ticket()
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)
        self.ok("close-ticket", CONVOY, T2, "--commit", tip, "--file", GATE_REPORT)

        shown = self.show()

        self.assertEqual("open", shown["convoy"]["status"])
        self.assertEqual([], shown["convoy"]["unruled"])

    def test_list_names_apart_the_marked_convoys_closed_outside_acceptance_or_abandon(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        state["beads"]["fx-closed"] = {"title": "fermé à la main", "status": "closed", "issue_type": "convoy",
                                       "metadata": {"gc.flow.mark": "new-flow/v1"}, "tracks": []}
        state["beads"]["fx-plain"] = {"title": "sans marque, fermé", "status": "closed", "issue_type": "convoy",
                                      "metadata": {}, "tracks": []}
        self.tracker.write_text(json.dumps(state))
        before = self.tracker.read_bytes()

        listed = self.ok("list")

        self.assertEqual([CONVOY], listed["convoys"])
        self.assertEqual(["fx-closed"], listed["closed_outside"])
        self.assertEqual(before, self.tracker.read_bytes())

    def test_marking_again_keeps_counters_and_marks_a_ticket_added_since(self):
        self.ok("mark", CONVOY)
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        state = self.tracker_state()
        state["beads"]["fx-t3"] = {"title": "ajouté par patch", "status": "open", "issue_type": "task",
                                   "metadata": {"gc.ticket_kind": "prefactoring"}}
        state["beads"][CONVOY]["tracks"].append("fx-t3")
        self.tracker.write_text(json.dumps(state))

        self.ok("mark", CONVOY)
        shown = self.show()
        self.assertEqual(1, self.ticket(shown, T1)["counters"]["resumes"])
        self.assertEqual("new-flow/v1", self.ticket(shown, "fx-t3")["mark"])
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, self.ticket(shown, "fx-t3")["counters"])

    def test_concurrent_counter_bumps_are_all_counted(self):
        self.ok("mark", CONVOY)
        # Real processes: the lock is held between processes, and one process
        # has one environment and one standard output.
        with ThreadPoolExecutor(max_workers=8) as pool:
            procs = list(pool.map(
                lambda _: self.run_tool("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes",
                                        real_process=True),
                range(8),
            ))
        self.assertEqual([0] * 8, [p.returncode for p in procs], [p.stdout + p.stderr for p in procs])
        self.assertEqual(8, self.ticket(self.show(), T1)["counters"]["resumes"])

    # --- T05: the entry contract fields a marked ticket carries ---------------

    LINE = "Sur le produit lancé, la page d'accueil (GET /) affiche les trois éléments = « Alpha », « Bêta », « Gamma »."

    def test_mark_writes_the_demonstration_lines_and_show_renders_kind_and_line(self):
        self.seed(kinds={T1: "vertical_slice", T2: "prefactoring"})
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}", "--user-stories", f"{T1}=2")

        shown = self.show()
        self.assertFalse(shown["unruled"])
        t1, t2 = self.ticket(shown, T1), self.ticket(shown, T2)
        self.assertEqual("vertical_slice", t1["kind"])
        self.assertEqual(self.LINE, t1["demonstration_line"])
        self.assertEqual("prefactoring", t2["kind"])
        self.assertIsNone(t2["demonstration_line"])

    def test_marking_again_with_the_same_lines_writes_nothing(self):
        self.seed(kinds={T1: "repair"})
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}")
        before = self.tracker.read_bytes()
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}")
        self.assertEqual(before, self.tracker.read_bytes())

    def test_mark_refuses_a_slice_or_a_repair_without_demonstration_line(self):
        for kind in ("vertical_slice", "repair"):
            with self.subTest(kind=kind):
                self.seed(kinds={T1: kind})
                self.assert_refused_and_nothing_written("mark", CONVOY, mention=T1)
                self.assert_refused_and_nothing_written(
                    "mark", CONVOY, "--demonstration-line", f"{T1}=   ", mention="ligne de démonstration")

    def test_mark_refuses_a_ticket_whose_kind_is_absent_or_outside_the_closed_list(self):
        for kind in (None, "prefactor", "prototype"):
            with self.subTest(kind=kind):
                self.seed(kinds={T1: kind})
                self.assert_refused_and_nothing_written(
                    "mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}", mention="genre")

    def test_mark_refuses_a_demonstration_line_on_a_prefactoring(self):
        self.assert_refused_and_nothing_written(
            "mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}", mention="prefactoring")

    def test_mark_refuses_a_demonstration_line_for_a_ticket_outside_the_convoy(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.assert_refused_and_nothing_written(
            "mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}",
            "--demonstration-line", f"fx-elsewhere={self.LINE}", mention="fx-elsewhere")

    def test_mark_refuses_to_change_a_demonstration_line_already_written(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}", "--user-stories", f"{T1}=2")
        self.assert_refused_and_nothing_written(
            "mark", CONVOY, "--demonstration-line", f"{T1}=Une autre observation.", "--user-stories", f"{T1}=2",
            mention="déjà")

    def test_ticket_whose_kind_is_unknown_is_unruled_and_not_defaulted(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.ticket_kind": "prefactor"})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertNotIsInstance(t1["kind"], str)
        self.assertIn("prefactor", json.dumps(t1["unruled"], ensure_ascii=False))

    def test_slice_without_demonstration_line_is_unruled(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.ticket_kind": "vertical_slice"})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertIsNone(t1["demonstration_line"])
        self.assertIn("ligne de démonstration", json.dumps(t1["unruled"], ensure_ascii=False))

    # --- T06: the user stories a marked vertical_slice covers -----------------

    def mark_slice(self, *stories):
        return ("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}",
                *(arg for entry in stories for arg in ("--user-stories", entry)))

    def test_mark_writes_the_user_stories_and_show_renders_them(self):
        self.seed(kinds={T1: "vertical_slice", T2: "repair"})
        self.ok(*self.mark_slice(f"{T1}=4,12"), "--demonstration-line", f"{T2}={self.LINE}")

        shown = self.show()
        self.assertFalse(shown["unruled"])
        self.assertEqual(["4", "12"], self.ticket(shown, T1)["user_stories"])
        self.assertIsNone(self.ticket(shown, T2)["user_stories"])

    def test_marking_again_with_the_same_user_stories_writes_nothing(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=4,12"))
        before = self.tracker.read_bytes()
        self.ok(*self.mark_slice(f"{T1}=4,12"))
        self.ok(*self.mark_slice())
        self.assertEqual(before, self.tracker.read_bytes())

    def test_mark_refuses_a_slice_without_user_stories(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.assert_refused_and_nothing_written(*self.mark_slice(), mention="user stor")
        self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}="), mention="user stor")

    def test_mark_refuses_user_stories_on_a_prefactoring_or_a_repair(self):
        for kind in ("prefactoring", "repair"):
            with self.subTest(kind=kind):
                self.seed(kinds={T1: kind})
                lines = ("--demonstration-line", f"{T1}={self.LINE}") if kind == "repair" else ()
                self.assert_refused_and_nothing_written(
                    "mark", CONVOY, *lines, "--user-stories", f"{T1}=4", mention="vertical_slice")

    def test_mark_refuses_user_stories_that_are_not_story_numbers(self):
        self.seed(kinds={T1: "vertical_slice"})
        for stories in ("quatre", "4,,5", "4,4", "0", "-1", "4;5"):
            with self.subTest(stories=stories):
                self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}={stories}"), mention="user stor")

    def test_mark_refuses_user_stories_for_a_ticket_outside_the_convoy_or_given_twice(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}=4", "fx-elsewhere=5"), mention="fx-elsewhere")
        self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}=4", f"{T1}=5"), mention=T1)
        self.assert_refused_and_nothing_written(*self.mark_slice("4"), mention="TICKET=")

    def test_mark_refuses_to_change_user_stories_already_written(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=4,12"))
        self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}=4"), mention="déjà")

    def test_slice_without_user_stories_is_unruled(self):
        self.seed(kinds={T1: "repair"})
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}={self.LINE}")
        self.edit_tracker(T1, **{"gc.ticket_kind": "vertical_slice"})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertIsNone(t1["user_stories"])
        self.assertIn("user stor", json.dumps(t1["unruled"], ensure_ascii=False))

    def test_user_stories_written_outside_the_command_are_unruled_and_not_rendered_as_stories(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=4"))
        for raw in ("4", 4, json.dumps({"stories": []}), json.dumps({"stories": ["quatre"]})):
            with self.subTest(raw=raw):
                self.edit_tracker(T1, **{"gc.flow.user_stories": raw})
                t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
                self.assertNotIsInstance(t1["user_stories"], list)
                self.assertEqual(raw, t1["user_stories"]["raw"])

    # --- T06: the slice that establishes the launch recipe --------------------

    def test_mark_writes_the_slice_that_establishes_the_launch_recipe(self):
        self.seed(kinds={T1: "vertical_slice", T2: "prefactoring"})
        self.ok(*self.mark_slice(f"{T1}=3"), "--establishes-launch-recipe", T1)

        shown = self.show()
        self.assertFalse(shown["unruled"])
        self.assertIs(True, self.ticket(shown, T1)["establishes_launch_recipe"])
        self.assertIs(False, self.ticket(shown, T2)["establishes_launch_recipe"])
        before = self.tracker.read_bytes()
        self.ok(*self.mark_slice(f"{T1}=3"), "--establishes-launch-recipe", T1)
        self.assertEqual(before, self.tracker.read_bytes())

    def test_mark_replaces_only_a_withdrawn_launch_recipe_slice(self):
        self.seed(tickets=(T1,), kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=3"), "--establishes-launch-recipe", T1)
        state = self.tracker_state()
        state["beads"][CONVOY]["tracks"].append(T2)
        state["beads"][T2] = {"title": "replacement", "status": "open", "issue_type": "task",
                               "metadata": {"gc.ticket_kind": "vertical_slice"}}
        state["beads"][T1]["status"] = "closed"
        self.tracker.write_text(json.dumps(state))
        args = ("mark", CONVOY, "--demonstration-line", f"{T2}={self.LINE}",
                "--user-stories", f"{T2}=3", "--establishes-launch-recipe", T2)
        self.assert_refused_and_nothing_written(*args, mention="une seule")
        self.ok("record-gate", CONVOY, T1, "--gate", "withdrawn")
        old = self.tracker_state()["beads"][T1]
        self.ok(*args)
        self.assertEqual(old, self.tracker_state()["beads"][T1])
        self.assertIs(True, self.tracker_state()["beads"][T2]["metadata"]["gc.flow.establishes_launch_recipe"])

    def test_mark_refuses_a_launch_recipe_established_by_anything_but_a_vertical_slice(self):
        self.assert_refused_and_nothing_written(
            "mark", CONVOY, "--establishes-launch-recipe", T1, mention="vertical_slice")
        self.assert_refused_and_nothing_written(
            "mark", CONVOY, "--establishes-launch-recipe", "fx-elsewhere", mention="fx-elsewhere")

    def test_mark_refuses_two_slices_that_establish_the_launch_recipe(self):
        self.seed(kinds={T1: "vertical_slice", T2: "vertical_slice"})
        self.assert_refused_and_nothing_written(
            *self.mark_slice(f"{T1}=3", f"{T2}=4"), "--demonstration-line", f"{T2}={self.LINE}",
            "--establishes-launch-recipe", T1, "--establishes-launch-recipe", T2, mention="une seule")

    def test_mark_refuses_to_change_which_slice_establishes_the_launch_recipe(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=3"))
        self.assert_refused_and_nothing_written(
            *self.mark_slice(f"{T1}=3"), "--establishes-launch-recipe", T1, mention="déjà")

    def test_launch_recipe_flag_written_outside_the_command_is_unruled(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.flow.establishes_launch_recipe": True})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertIn("vertical_slice", json.dumps(t1["unruled"], ensure_ascii=False))

        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=3"))
        self.edit_tracker(T1, **{"gc.flow.establishes_launch_recipe": "oui"})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("oui", t1["establishes_launch_recipe"]["raw"])

    # --- T36: the slice that is the Prototype Fold -----------------------------

    def test_mark_writes_the_slice_that_is_the_prototype_fold(self):
        self.seed(kinds={T1: "vertical_slice", T2: "prefactoring"})
        self.ok(*self.mark_slice(f"{T1}=3"), "--prototype-fold", T1)

        shown = self.show()
        self.assertFalse(shown["unruled"])
        self.assertIs(True, self.ticket(shown, T1)["prototype_fold"])
        self.assertIs(False, self.ticket(shown, T2)["prototype_fold"])
        before = self.tracker.read_bytes()
        self.ok(*self.mark_slice(f"{T1}=3"), "--prototype-fold", T1)
        self.assertEqual(before, self.tracker.read_bytes())

    def test_mark_refuses_a_prototype_fold_that_is_not_a_vertical_slice_of_the_convoy(self):
        self.assert_refused_and_nothing_written("mark", CONVOY, "--prototype-fold", T1, mention="vertical_slice")
        self.assert_refused_and_nothing_written("mark", CONVOY, "--prototype-fold", "fx-elsewhere", mention="fx-elsewhere")

    def test_mark_refuses_to_change_which_slice_is_the_prototype_fold(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=3"))
        self.assert_refused_and_nothing_written(*self.mark_slice(f"{T1}=3"), "--prototype-fold", T1, mention="déjà")

    def test_prototype_fold_flag_written_outside_the_command_is_unruled(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.flow.prototype_fold": True})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertIn("vertical_slice", json.dumps(t1["unruled"], ensure_ascii=False))

        self.seed(kinds={T1: "vertical_slice"})
        self.ok(*self.mark_slice(f"{T1}=3"))
        self.edit_tracker(T1, **{"gc.flow.prototype_fold": "oui"})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("oui", t1["prototype_fold"]["raw"])

    # --- AC2: a malformed write is refused and nothing is written -------------

    def test_verdict_without_commit_is_refused(self):
        self.started_ticket()
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", mention="commit")
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", "",
            mention="commit")
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", "HEAD",
            mention="commit")

    def test_verdict_state_or_kind_outside_the_closed_list_is_refused(self):
        tip = self.started_ticket()
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "approved", "--commit", tip,
            mention="approved")
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, T1, "--kind", "vibes", "--state", "favorable", "--commit", tip,
            mention="vibes")

    def test_ticket_exit_outside_the_closed_list_is_refused(self):
        self.started_ticket()
        self.assert_refused_and_nothing_written("set-exit", CONVOY, T1, "--exit", "done", mention="done")

    def test_gate_outside_the_closed_list_or_ticket_end_without_its_verdicts_is_refused(self):
        tip = self.started_ticket()
        self.assert_refused_and_nothing_written("record-gate", CONVOY, T1, "--gate", "by-hand", mention="by-hand")
        # T19: the record of the ticket-end gate is its nine verdicts, written with the closing.
        self.assert_refused_and_nothing_written(
            "record-gate", CONVOY, T1, "--gate", "ticket_end", "--commit", tip, mention="close-ticket")
        self.assert_refused_and_nothing_written("close-ticket", CONVOY, T1, "--file", GATE_REPORT, mention="commit")

    def test_negative_or_non_integer_counter_is_refused(self):
        self.started_ticket()
        self.assert_refused_and_nothing_written(
            "set-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--value", "-1", mention="-1")
        self.assert_refused_and_nothing_written(
            "set-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--value", "deux", mention="deux")
        self.assert_refused_and_nothing_written(
            "set-counter", CONVOY, "--counter", "end_rounds", "--value", "-2", mention="-2")

    def test_counter_unknown_or_on_the_wrong_bead_is_refused(self):
        self.started_ticket()
        self.assert_refused_and_nothing_written(
            "bump-counter", CONVOY, "--ticket", T1, "--counter", "retries", mention="retries")
        self.assert_refused_and_nothing_written(
            "bump-counter", CONVOY, "--ticket", T1, "--counter", "end_rounds", mention="end_rounds")
        self.assert_refused_and_nothing_written("bump-counter", CONVOY, "--counter", "resumes", mention="resumes")

    def test_counter_write_that_would_be_incoherent_is_refused(self):
        self.started_ticket()
        # a correction round counts among the resumes: it can never exceed them
        self.assert_refused_and_nothing_written(
            "bump-counter", CONVOY, "--ticket", T1, "--counter", "correction_rounds", mention="correction_rounds")

    def test_evidence_without_digest_or_commit_is_refused(self):
        tip = self.started_ticket()
        self.assert_refused_and_nothing_written(
            "add-evidence", CONVOY, T1, "--piece", "red_proof", "--commit", tip, mention="digest")
        self.assert_refused_and_nothing_written(
            "add-evidence", CONVOY, T1, "--piece", "red_proof", "--digest", "md5:abc", "--commit", tip,
            mention="digest")
        self.assert_refused_and_nothing_written(
            "add-evidence", CONVOY, T1, "--piece", "red_proof", "--digest", DIGEST, mention="commit")
        # the tracker has no metadata key with a hyphen: refused before it is tried
        self.assert_refused_and_nothing_written(
            "add-evidence", CONVOY, T1, "--piece", "red-proof", "--digest", DIGEST, "--commit", tip,
            mention="red-proof")

    def test_write_on_a_ticket_outside_the_convoy_is_refused(self):
        tip = self.started_ticket()
        state = self.tracker_state()
        state["beads"]["fx-other"] = {"title": "ailleurs", "status": "open", "issue_type": "task"}
        self.tracker.write_text(json.dumps(state))
        self.assert_refused_and_nothing_written(
            "set-verdict", CONVOY, "fx-other", "--kind", "code_review", "--state", "favorable", "--commit", tip,
            mention="fx-other")

    # --- AC3: an incoherent ticket is signalled, never defaulted --------------

    def test_ticket_closed_without_gate_record_is_unruled(self):
        self.started_ticket()
        self.edit_tracker(T1, status="closed")
        shown = self.show(expect=EXIT_UNRULED)
        self.assertTrue(shown["unruled"])
        t1 = self.ticket(shown, T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertTrue(any("fermé" in entry["reason"] and "relevé de porte" in entry["reason"]
                            for entry in t1["unruled"]), t1["unruled"])
        self.assertNotIn("ticket_end", t1["gates"])
        self.assertEqual([], self.ticket(shown, T2)["unruled"])

    def test_ticket_started_without_dispatch_gate_record_is_unruled(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T2, status="in_progress")
        shown = self.show(expect=EXIT_UNRULED)
        t2 = self.ticket(shown, T2)
        self.assertEqual("état sans règle", t2["signal"])
        self.assertTrue(any("porte de dispatch" in entry["reason"] for entry in t2["unruled"]), t2["unruled"])

    def test_verdict_tied_to_a_commit_absent_from_the_branch_is_unruled(self):
        self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable",
                "--commit", ABSENT_COMMIT)
        shown = self.show(expect=EXIT_UNRULED)
        t1 = self.ticket(shown, T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertTrue(any(ABSENT_COMMIT in entry["reason"] and "ticket/t1" in entry["reason"]
                            for entry in t1["unruled"]), t1["unruled"])
        # no default: the verdict is rendered neither valid nor invalid
        self.assertNotIn("valid", t1["verdicts"]["code_review"])

    def test_verdict_on_a_commit_of_another_branch_is_unruled(self):
        self.started_ticket()
        elsewhere = self.commit_on("ticket/t2")
        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "favorable", "--commit", elsewhere)
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertNotIn("valid", t1["verdicts"]["evaluation"])

    def test_verdict_whose_ticket_branch_cannot_be_found_is_unruled(self):
        tip = self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", tip)
        self.ok("set-branch", CONVOY, T1, "--branch", "ticket/gone")
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertTrue(any("ticket/gone" in entry["reason"] for entry in t1["unruled"]), t1["unruled"])
        self.assertNotIn("valid", t1["verdicts"]["code_review"])

    def test_incoherent_counter_is_unruled_and_not_defaulted(self):
        self.started_ticket()
        self.edit_tracker(T1, **{"gc.flow.counter.resumes": 1, "gc.flow.counter.correction_rounds": 2})
        self.edit_tracker(T2, **{"gc.flow.counter.resumes": "beaucoup"})
        shown = self.show(expect=EXIT_UNRULED)

        t1 = self.ticket(shown, T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertTrue(any("correction_rounds" in entry["reason"] for entry in t1["unruled"]), t1["unruled"])

        t2 = self.ticket(shown, T2)
        self.assertEqual("état sans règle", t2["signal"])
        self.assertTrue(any("resumes" in entry["reason"] for entry in t2["unruled"]), t2["unruled"])
        self.assertNotIsInstance(t2["counters"]["resumes"], int)
        self.assertEqual("beaucoup", t2["counters"]["resumes"]["raw"])

    def test_missing_counter_is_unruled_not_read_as_zero(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        del state["beads"][T1]["metadata"]["gc.flow.counter.resumes"]
        self.tracker.write_text(json.dumps(state))
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("état sans règle", t1["signal"])
        self.assertNotIsInstance(t1["counters"]["resumes"], int)

    def test_unmarked_ticket_in_a_marked_convoy_is_unruled(self):
        self.ok("mark", CONVOY)
        state = self.tracker_state()
        state["beads"]["fx-t3"] = {"title": "ajouté hors porte", "status": "open", "issue_type": "task"}
        state["beads"][CONVOY]["tracks"].append("fx-t3")
        self.tracker.write_text(json.dumps(state))
        t3 = self.ticket(self.show(expect=EXIT_UNRULED), "fx-t3")
        self.assertEqual("état sans règle", t3["signal"])
        self.assertIsNone(t3["mark"])

    def test_field_written_outside_the_command_is_unruled(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.flow.my_own_field": "x",
                                 "gc.flow.verdict.code_review": '{"state": "favorable"}'})
        t1 = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        reasons = " | ".join(entry["reason"] for entry in t1["unruled"])
        self.assertIn("gc.flow.my_own_field", reasons)
        self.assertIn("code_review", reasons)
        self.assertNotIn("valid", t1["verdicts"]["code_review"])

    # --- AC4: a convoy without the mark is left exactly as it is --------------

    def test_unmarked_convoy_is_reported_not_new_flow_and_nothing_is_written(self):
        self.init_repo()
        tip = self.git("rev-parse", "HEAD")
        before = self.tracker.read_bytes()

        proc = self.run_tool("show", CONVOY, "--repo", self.repo)
        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["new_flow"])
        self.assertIn("pas un convoi du nouveau flux", answer["message"])

        for args in (
            ("set-branch", CONVOY, T1, "--branch", "ticket/t1"),
            ("set-exit", CONVOY, T1, "--exit", "finished"),
            ("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", tip),
            ("set-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--value", "1"),
            ("bump-counter", CONVOY, "--counter", "end_rounds"),
            ("add-evidence", CONVOY, T1, "--piece", "p", "--digest", DIGEST, "--commit", tip),
            ("record-gate", CONVOY, T1, "--gate", "dispatch"),
        ):
            proc = self.run_tool(*args)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, f"{args}: {proc.stdout}{proc.stderr}")
            self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])

        # what every existing command reads of this convoy is byte-identical
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertFalse(self.write_log.exists())

    def test_mark_refuses_a_bead_that_is_not_a_convoy(self):
        # The refusal kept on the real command line (Spec CI01 §3.1).
        self.assert_refused_and_nothing_written("mark", T1, mention=T1, real_process=True)

    # --- AC5: a verdict stops being valid when the branch tip moves -----------

    def test_verdict_is_no_longer_valid_once_the_ticket_branch_tip_has_changed(self):
        tip = self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", tip)
        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "favorable", "--commit", tip)
        self.assertIs(True, self.ticket(self.show(), T1)["verdicts"]["code_review"]["valid"])

        new_tip = self.commit_on("ticket/t1")
        t1 = self.ticket(self.show(), T1)
        self.assertEqual(new_tip, t1["tip"])
        for kind in ("code_review", "evaluation"):
            self.assertIs(False, t1["verdicts"][kind]["valid"])
            self.assertEqual(tip, t1["verdicts"][kind]["commit"])
        self.assertEqual([], t1["unruled"])

        # replayed on the new tip, the verdict is valid again
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", new_tip)
        t1 = self.ticket(self.show(), T1)
        self.assertIs(True, t1["verdicts"]["code_review"]["valid"])
        self.assertIs(False, t1["verdicts"]["evaluation"]["valid"])


    # --- the mark of one ticket, the convoy's factory incident (T34) -------------

    def test_ticket_says_a_marked_ticket_is_of_the_new_flow(self):
        self.ok("mark", CONVOY)

        answer = self.ok("ticket", T1)

        self.assertTrue(answer["new_flow"])
        self.assertEqual(T1, answer["ticket"])

    def test_ticket_says_an_unmarked_ticket_is_not_of_the_new_flow_and_writes_nothing(self):
        before = self.tracker.read_text()

        proc = self.run_tool("ticket", T1)

        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertFalse(json.loads(proc.stdout)["new_flow"])
        self.assertEqual(before, self.tracker.read_text())

    def test_ticket_reads_a_bead_already_read_from_the_tracker(self):
        self.ok("mark", CONVOY)
        bead = [{"id": T1, "status": "open", "metadata": self.tracker_state()["beads"][T1]["metadata"]}]
        env = {**self.env, "GC_BIN": "/nonexistent/gc"}  # the tracker is not read again

        # A real process: the bead comes through a real standard input.
        proc = self.run_tool("ticket", T1, "--bead-json", "-", env=env, input=json.dumps(bead),
                             real_process=True)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["new_flow"])

    def test_every_tracker_call_names_the_city(self):
        # Left to find the city by itself, gc starts one more command before
        # each read (af-2o6oyl).
        calls = self.tmp / "gc-calls.log"
        recorder = self.tmp / "recording-gc"
        recorder.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\nexec "{FAKE_GC}" "$@"\n')
        recorder.chmod(0o755)
        city = self.tmp / "city"
        city.mkdir()
        env = {**self.env, "GC_BIN": str(recorder), "FACTORY_ROOT": str(city)}

        # The pass kept on the real command line (Spec CI01 §3.1): a write
        # and two reads, through bin/convoy-state and its own start.
        for command in (("mark", CONVOY), ("show", CONVOY), ("list",)):
            proc = self.run_tool(*command, env=env, real_process=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        lines = calls.read_text().splitlines()
        self.assertIn(f"--city {city} bd show {CONVOY} --json", lines)
        self.assertEqual([], [line for line in lines if not line.startswith(f"--city {city} bd ")])

    def test_ticket_with_an_unknown_mark_is_a_state_without_rule(self):
        self.edit_tracker(T1, **{"gc.flow.mark": "new-flow/v0"})

        proc = self.run_tool("ticket", T1)

        self.assertEqual(EXIT_UNRULED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("état sans règle", proc.stdout)

    def test_record_incident_is_read_back_by_show(self):
        self.ok("mark", CONVOY)

        self.ok("record-incident", CONVOY, "--bead", "fx-incident")
        self.assertEqual("fx-incident", self.show()["convoy"]["incident"]["bead"])
        self.assertNotIn("signature", self.show()["convoy"]["incident"])

        self.ok("record-incident", CONVOY, "--bead", "fx-incident", "--signature", DIGEST)
        incident = self.show()["convoy"]["incident"]
        self.assertEqual(DIGEST, incident["signature"])
        self.assertIn("at", incident)

    def test_a_convoy_without_incident_shows_none(self):
        self.ok("mark", CONVOY)

        self.assertIsNone(self.show()["convoy"]["incident"])

    def test_clear_incident_removes_it(self):
        self.ok("mark", CONVOY)
        self.ok("record-incident", CONVOY, "--bead", "fx-incident", "--signature", DIGEST)

        self.ok("clear-incident", CONVOY)

        self.assertIsNone(self.show()["convoy"]["incident"])
        self.assertNotIn("gc.flow.incident", self.tracker_state()["beads"][CONVOY]["metadata"])

    def test_record_incident_refuses_a_malformed_signature_or_bead_and_writes_nothing(self):
        self.ok("mark", CONVOY)
        before = self.tracker.read_text()

        for args in (("--bead", "fx-incident", "--signature", "abc"), ("--bead", "not a bead id"), ()):
            with self.subTest(args=args):
                proc = self.run_tool("record-incident", CONVOY, *args)
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual(before, self.tracker.read_text())

    def test_record_incident_refuses_an_unmarked_convoy_and_writes_nothing(self):
        before = self.tracker.read_text()

        for command in (("record-incident", CONVOY, "--bead", "fx-incident"), ("clear-incident", CONVOY)):
            with self.subTest(command=command):
                proc = self.run_tool(*command)
                self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual(before, self.tracker.read_text())

    def test_an_incident_record_written_outside_the_command_is_a_state_without_rule(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(CONVOY, **{"gc.flow.incident": "à la main"})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("unruled", shown["convoy"]["incident"])
        self.assertEqual("gc.flow.incident", shown["convoy"]["unruled"][0]["field"])


    # --- T10: acceptance criteria, steps of the TDD, stop of a ticket ---------

    BASE = "1" * 40
    RED = "2" * 40
    AMENDED = "3" * 40

    def marked_slice(self):
        self.seed(kinds={T1: "vertical_slice"})
        self.edit_bead(T1, description=(
            "## What to build\n\n- [ ] pas un critère\n\n## Acceptance criteria\n\n"
            "- [ ] Le nombre s'affiche\n- [x] La sonde nomme le jeu\n\n## Target rigs\n\n- [ ] ni celui-ci\n"))
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}=La page affiche 3", "--user-stories", f"{T1}=1")

    def edit_bead(self, bead_id, **fields):
        state = self.tracker_state()
        state["beads"][bead_id].update(fields)
        self.tracker.write_text(json.dumps(state))

    def set_tdd(self, step, commit, *options, ticket=T1):
        return self.ok("set-tdd", CONVOY, ticket, "--step", step, "--commit", commit, *options)

    def frozen_slice(self):
        self.marked_slice()
        self.set_tdd("red", self.RED, "--base", self.BASE)
        self.set_tdd("freeze", self.RED)

    def test_show_renders_the_acceptance_criteria_of_a_ticket_in_order(self):
        self.marked_slice()

        shown = self.show()

        self.assertEqual(["Le nombre s'affiche", "La sonde nomme le jeu"], self.ticket(shown, T1)["criteria"])
        self.assertEqual([], self.ticket(shown, T2)["criteria"])

    def test_tdd_steps_are_read_back_by_show_each_with_its_commit(self):
        self.frozen_slice()
        self.set_tdd("green", self.AMENDED)

        tdd = self.ticket(self.show(), T1)["tdd"]

        self.assertEqual((self.RED, self.BASE), (tdd["red"]["commit"], tdd["red"]["base"]))
        self.assertEqual(self.RED, tdd["freeze"]["commit"])
        self.assertEqual(self.AMENDED, tdd["green"]["commit"])
        self.assertEqual({}, self.ticket(self.show(), T2)["tdd"])
        self.assertIsNone(self.ticket(self.show(), T1)["stop"])

    def test_red_is_refused_without_its_start_commit_or_with_a_malformed_commit(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "red", "--commit", self.RED, mention="commit de départ")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "red", "--commit", "abc", "--base", self.BASE, mention="commit")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "bleu", "--commit", self.RED, mention="étape du TDD")

    def test_freeze_is_refused_without_a_red_at_the_same_commit(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "freeze", "--commit", self.RED, mention="rouge")
        self.set_tdd("red", self.RED, "--base", self.BASE)
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "freeze", "--commit", self.AMENDED, mention="rouge")

    def test_green_and_amendment_are_refused_without_a_freeze(self):
        self.marked_slice()
        self.set_tdd("red", self.RED, "--base", self.BASE)
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "green", "--commit", self.RED, mention="gel")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "amendment", "--commit", self.RED, "--reason", "r", mention="gel")

    def test_a_frozen_ticket_takes_a_new_red_or_freeze_only_at_the_commit_of_its_amendment(self):
        self.frozen_slice()
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "red", "--commit", self.AMENDED, "--base", self.BASE, mention="gelés")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "freeze", "--commit", self.RED, mention="gelés")

        self.set_tdd("amendment", self.AMENDED, "--reason", "le champ change de nom")
        self.set_tdd("red", self.AMENDED, "--base", self.BASE)
        self.set_tdd("freeze", self.AMENDED)

        tdd = self.ticket(self.show(), T1)["tdd"]
        self.assertEqual("le champ change de nom", tdd["amendment"]["reason"])
        self.assertEqual((self.AMENDED, self.AMENDED), (tdd["red"]["commit"], tdd["freeze"]["commit"]))

    def test_a_second_amendment_or_an_amendment_without_reason_is_refused(self):
        self.frozen_slice()
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "amendment", "--commit", self.AMENDED, mention="raison")
        self.set_tdd("amendment", self.AMENDED, "--reason", "le champ change de nom")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "amendment", "--commit", self.AMENDED, "--reason", "encore",
            mention="un seul amendement par ticket")

    def test_the_prefactoring_step_and_the_red_step_each_have_their_kind_of_ticket(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "prefactoring", "--commit", self.RED, "--base", self.BASE,
            mention="vertical_slice")
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T2, "--step", "red", "--commit", self.RED, "--base", self.BASE, mention="prefactoring")

        self.set_tdd("prefactoring", self.RED, "--base", self.BASE, ticket=T2)

        self.assertEqual(self.BASE, self.ticket(self.show(), T2)["tdd"]["prefactoring"]["base"])

    def test_stop_ticket_is_read_back_by_show_and_refuses_every_later_step(self):
        self.marked_slice()

        self.ok("stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 2 déjà vert")

        stop = self.ticket(self.show(), T1)["stop"]
        self.assertEqual(("criterion_already_green", "critère 2 déjà vert"), (stop["reason"], stop["detail"]))
        self.assert_refused_and_nothing_written(
            "set-tdd", CONVOY, T1, "--step", "red", "--commit", self.RED, "--base", self.BASE, mention="ticket arrêté")
        self.assert_refused_and_nothing_written(
            "stop-ticket", CONVOY, T1, "--reason", "amendment_exhausted", "--detail", "encore", mention="déjà arrêté")

    def test_stop_ticket_refuses_a_reason_outside_the_closed_list_or_no_detail(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "stop-ticket", CONVOY, T1, "--reason", "fatigue", "--detail", "x", mention="raison d'arrêt")
        self.assert_refused_and_nothing_written(
            "stop-ticket", CONVOY, T1, "--reason", "amendment_exhausted", mention="précision")

    def test_tdd_step_or_stop_written_outside_the_command_is_a_state_without_rule(self):
        self.marked_slice()
        self.edit_tracker(T1, **{"gc.flow.tdd.red": json.dumps({"commit": self.RED, "at": "x"}),
                                 "gc.flow.tdd.bleu": "x", "gc.flow.stop": "à la main"})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["tdd"]["red"])
        self.assertIn("unruled", ticket["tdd"]["bleu"])
        self.assertIn("unruled", ticket["stop"])
        self.assertEqual({"gc.flow.stop", "gc.flow.tdd.bleu", "gc.flow.tdd.red"},
                         {entry["field"] for entry in ticket["unruled"]})

    def test_tdd_step_and_stop_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (("set-tdd", CONVOY, T1, "--step", "red", "--commit", self.RED, "--base", self.BASE),
                        ("stop-ticket", CONVOY, T1, "--reason", "amendment_exhausted", "--detail", "x")):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- T11: the Ticket Handoff, the parking, the Declared Scope --------------

    HEAD = "4" * 40
    SECTIONS = {"done": ["Critère 1 : le nombre s'affiche."], "deviations": "aucun",
                "not_done": [{"what": "La sonde n'est pas branchée.", "paths": ["app.py"]}, "Le libellé manque."],
                "out_of_ticket": "aucun"}

    def handoff_file(self, **changes):
        handoff = {"sections": self.SECTIONS, "partial": False, "commit": self.HEAD,
                   "records": {"commits": [], "deferral_markers": []}, **changes}
        path = self.tmp / "handoff.json"
        path.write_text(json.dumps({key: value for key, value in handoff.items() if value is not None}))
        return path

    def sealed_records(self, commit=None):
        self.ok("add-evidence", CONVOY, T1, "--piece", "handoff_records", "--digest", DIGEST,
                "--commit", commit or self.HEAD)

    def test_set_handoff_records_the_sections_and_the_records(self):
        self.marked_slice()
        self.sealed_records()

        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file())

        handoff = self.ticket(self.show(), T1)["handoff"]
        self.assertEqual(self.SECTIONS, handoff["sections"])
        self.assertEqual((False, self.HEAD), (handoff["partial"], handoff["commit"]))
        self.assertEqual({"commits": [], "deferral_markers": []}, handoff["records"])
        self.assertIsNone(self.ticket(self.show(), T2)["handoff"])

    def test_set_handoff_refuses_a_section_absent_empty_or_unknown(self):
        self.marked_slice()
        self.sealed_records()
        for sections, mention in (
            ({key: value for key, value in self.SECTIONS.items() if key != "deviations"}, "deviations absente"),
            ({**self.SECTIONS, "done": []}, "done mal formée"),
            ({**self.SECTIONS, "out_of_ticket": ""}, "out_of_ticket mal formée"),
            ({**self.SECTIONS, "done": ["deux\nlignes"]}, "done"),
            ({**self.SECTIONS, "not_done": [{"what": "x", "ligne": 3}]}, "not_done"),
            ({**self.SECTIONS, "suite": "aucun"}, "rubriques inconnues"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(
                    "set-handoff", CONVOY, T1, "--file", self.handoff_file(sections=sections), mention=mention)

    def test_set_handoff_refuses_records_the_exit_tool_did_not_seal(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.handoff_file(), mention="handoff_records")
        # Sealed at another commit: not the records of this Handoff.
        self.sealed_records(commit=self.RED)
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.handoff_file(), mention="handoff_records")

    def test_set_handoff_refuses_a_complete_handoff_without_records_and_a_bad_file(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.handoff_file(records=None), mention="sans relevés")
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.handoff_file(commit="abc"), mention="commit du Handoff")
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.handoff_file(partial="non"), mention="partial")
        self.assert_refused_and_nothing_written(
            "set-handoff", CONVOY, T1, "--file", self.tmp / "absent.json", mention="illisible")
        self.assert_refused_and_nothing_written("set-handoff", CONVOY, T1, mention="illisible")

    def test_a_partial_handoff_may_leave_sections_and_records_out(self):
        self.marked_slice()
        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file(
            sections={"done": ["Le chargeur est écrit."]}, partial=True, records=None))
        handoff = self.ticket(self.show(), T1)["handoff"]
        self.assertEqual(({"done": ["Le chargeur est écrit."]}, True), (handoff["sections"], handoff["partial"]))
        self.assertNotIn("records", handoff)

    def seed_chain(self):
        """T2 waits for T1, T3 for T2; T4 waits for nothing."""
        self.seed(tickets=(T1, T2, "fx-t3", "fx-t4"))
        state = self.tracker_state()
        state["beads"][T2]["blocks"] = [T1]
        state["beads"]["fx-t3"]["blocks"] = [T2]
        self.tracker.write_text(json.dumps(state))
        self.ok("mark", CONVOY)

    def test_park_parks_the_ticket_and_every_ticket_that_waits_for_it(self):
        self.seed_chain()

        answer = self.ok("park", CONVOY, T1, "--cause", "planning_exception", "--detail", "Question sur l'ordre")

        self.assertEqual([T1, T2, "fx-t3"], answer["parked"])
        shown = self.show()
        for ticket_id in (T1, T2, "fx-t3"):
            park = self.ticket(shown, ticket_id)["park"]
            self.assertEqual(("planning_exception", T1, "Question sur l'ordre"),
                             (park["cause"], park["origin"], park["detail"]), ticket_id)
        self.assertIsNone(self.ticket(shown, "fx-t4")["park"])

    def test_park_leaves_a_descendant_already_parked_and_a_closed_one(self):
        self.seed_chain()
        self.ok("park", CONVOY, "fx-t3", "--cause", "operator_request", "--detail", "Accès à l'horloge")
        self.ok("record-gate", CONVOY, T2, "--gate", "withdrawn")
        self.edit_tracker(T2, status="closed")

        answer = self.ok("park", CONVOY, T1, "--cause", "planning_exception", "--detail", "Question sur l'ordre")

        self.assertEqual([T1], answer["parked"])
        shown = self.show()
        self.assertEqual("operator_request", self.ticket(shown, "fx-t3")["park"]["cause"])
        self.assertIsNone(self.ticket(shown, T2)["park"])

    def test_park_refuses_a_cause_outside_the_list_no_detail_a_closed_or_parked_ticket(self):
        self.seed_chain()
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "fatigue", "--detail", "x", mention="cause de parcage")
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "operator_request", mention="précision du parcage")
        self.assert_refused_and_nothing_written(
            "park", CONVOY, "fx-absent", "--cause", "operator_request", "--detail", "x", mention="n'appartient pas")
        self.ok("park", CONVOY, "fx-t4", "--cause", "operator_request", "--detail", "x")
        self.assert_refused_and_nothing_written(
            "park", CONVOY, "fx-t4", "--cause", "operator_request", "--detail", "x", mention="déjà parqué")
        self.ok("record-gate", CONVOY, T1, "--gate", "withdrawn")
        self.edit_tracker(T1, status="closed")
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "operator_request", "--detail", "x", mention="fermé")

    def test_handoff_or_park_written_outside_the_command_is_a_state_without_rule(self):
        self.marked_slice()
        self.edit_tracker(T1, **{"gc.flow.handoff": json.dumps({"sections": {}, "at": "x"}),
                                 "gc.flow.park": json.dumps({"cause": "fatigue", "origin": T1, "detail": "x", "at": "x"})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["handoff"])
        self.assertIn("unruled", ticket["park"])
        self.assertEqual({"gc.flow.handoff", "gc.flow.park"}, {entry["field"] for entry in ticket["unruled"]})

    def test_show_renders_the_declared_scope_the_publication_door_wrote(self):
        self.marked_slice()
        self.assertIsNone(self.ticket(self.show(), T1)["declared_scope"])
        self.edit_tracker(T1, **{"gc.scope_paths": "app/home.py,app/static/*"})
        self.assertEqual(["app/home.py", "app/static/*"], self.ticket(self.show(), T1)["declared_scope"])

    def test_handoff_and_park_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (("set-handoff", CONVOY, T1, "--file", self.handoff_file()),
                        ("park", CONVOY, T1, "--cause", "operator_request", "--detail", "x")):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- the integration branch, the merge of a ticket, a verdict made invalid (T18) ---

    def integrated(self):
        """A started ticket in a convoy whose integration branch is recorded."""
        tip = self.started_ticket()
        base = self.git("rev-parse", "main")
        self.ok("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main", "--base", base)
        return tip, base

    # --- the author session of a ticket (T12) ---------------------------------

    def test_set_session_puts_the_started_ticket_in_progress_under_its_session(self):
        self.marked_slice()
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")

        self.ok("set-session", CONVOY, T1, "--session", "delivery-author-fx-1")

        ticket = self.ticket(self.show(), T1)
        self.assertEqual("delivery-author-fx-1", ticket["session"]["name"])
        self.assertEqual("in_progress", ticket["status"])
        self.assertEqual("delivery-author-fx-1", self.tracker_state()["beads"][T1]["metadata"]["gc.session_name"])

    def test_set_session_refuses_a_session_that_already_took_another_ticket(self):
        self.marked_slice()
        for ticket in (T1, T2):
            self.ok("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.ok("set-session", CONVOY, T1, "--session", "delivery-author-fx-1")

        self.assert_refused_and_nothing_written(
            "set-session", CONVOY, T2, "--session", "delivery-author-fx-1", mention="une session neuve par ticket")

    def test_set_session_refuses_a_ticket_not_started_by_the_door_a_closed_one_and_no_name(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-session", CONVOY, T1, "--session", "delivery-author-fx-1", mention="porte de dispatch")
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.assert_refused_and_nothing_written("set-session", CONVOY, T1, mention="session absente")
        self.edit_tracker(T1, status="closed")
        self.assert_refused_and_nothing_written(
            "set-session", CONVOY, T1, "--session", "delivery-author-fx-1", mention="fermé")

    def test_set_session_again_by_the_same_session_writes_nothing(self):
        self.marked_slice()
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.ok("set-session", CONVOY, T1, "--session", "delivery-author-fx-1")
        before = self.tracker.read_text()

        self.assertEqual({}, self.ok("set-session", CONVOY, T1, "--session", "delivery-author-fx-1")["written"])

        self.assertEqual(before, self.tracker.read_text())

    def test_session_written_outside_the_command_is_a_state_without_rule(self):
        self.marked_slice()
        self.edit_tracker(T1, **{"gc.flow.session": "à la main"})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["session"])

    def test_set_integration_records_the_branch_of_the_spec_on_the_convoy(self):
        self.ok("mark", CONVOY)
        self.assertIsNone(self.show()["convoy"]["integration"])

        self.ok("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main",
                "--base", ABSENT_COMMIT)
        integration = self.show()["convoy"]["integration"]
        self.assertEqual(("integration/fx-spec", "main", ABSENT_COMMIT),
                         (integration["branch"], integration["protected"], integration["base"]))

    def test_set_integration_again_writes_nothing_and_another_branch_is_refused(self):
        self.ok("mark", CONVOY)
        record = ("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main",
                  "--base", ABSENT_COMMIT)
        self.ok(*record)
        before = self.tracker.read_bytes()

        self.assertEqual({}, self.ok(*record)["written"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assert_refused_and_nothing_written(
            "set-integration", CONVOY, "--branch", "integration/autre", "--protected", "main",
            "--base", ABSENT_COMMIT, mention="ne se réécrit pas")

    def test_set_integration_refuses_a_malformed_record(self):
        self.ok("mark", CONVOY)
        for args, mention in (
            (("--protected", "main", "--base", ABSENT_COMMIT), "branche d'intégration"),
            (("--branch", "integration/fx spec", "--protected", "main", "--base", ABSENT_COMMIT), "branche d'intégration"),
            (("--branch", "integration/fx-spec", "--base", ABSENT_COMMIT), "branche protégée"),
            (("--branch", "integration/fx-spec", "--protected", "main", "--base", "HEAD"), "commit de départ"),
        ):
            with self.subTest(args=args):
                self.assert_refused_and_nothing_written("set-integration", CONVOY, *args, mention=mention)

    def test_set_merge_records_what_was_done_of_the_ticket(self):
        tip, base = self.integrated()
        self.assertIsNone(self.ticket(self.show(), T1)["merge"])

        self.ok("set-merge", CONVOY, T1, "--outcome", "merged", "--ticket-commit", tip, "--integration", base,
                "--commit", ABSENT_COMMIT)
        merge = self.ticket(self.show(), T1)["merge"]
        self.assertEqual(("merged", tip, base, ABSENT_COMMIT),
                         (merge["outcome"], merge["ticket_commit"], merge["integration"], merge["commit"]))

        self.ok("set-merge", CONVOY, T1, "--outcome", "conflict", "--ticket-commit", tip, "--integration", base)
        merge = self.ticket(self.show(), T1)["merge"]
        self.assertEqual("conflict", merge["outcome"])
        self.assertNotIn("commit", merge)

    def test_set_merge_refuses_a_malformed_record(self):
        tip, base = self.integrated()
        for args, mention in (
            (("--outcome", "rebased", "--ticket-commit", tip, "--integration", base), "issue de fusion"),
            (("--ticket-commit", tip, "--integration", base), "issue de fusion"),
            (("--outcome", "merged", "--ticket-commit", tip, "--integration", base), "commit du résultat fusionné absent"),
            (("--outcome", "red", "--ticket-commit", tip, "--integration", base), "commit du résultat fusionné absent"),
            (("--outcome", "conflict", "--ticket-commit", tip, "--integration", base, "--commit", ABSENT_COMMIT),
             "inattendu"),
            (("--outcome", "conflict", "--ticket-commit", "abc", "--integration", base), "pointe du ticket"),
            (("--outcome", "conflict", "--ticket-commit", tip), "pointe de la branche d'intégration"),
        ):
            with self.subTest(args=args):
                self.assert_refused_and_nothing_written("set-merge", CONVOY, T1, *args, mention=mention)

    def test_set_merge_refuses_a_convoy_without_integration_branch_and_a_closed_ticket(self):
        tip = self.started_ticket()
        record = ("set-merge", CONVOY, T1, "--outcome", "conflict", "--ticket-commit", tip, "--integration", tip)
        self.assert_refused_and_nothing_written(*record, mention="branche d'intégration")

        self.ok("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main", "--base", tip)
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)
        self.assert_refused_and_nothing_written(*record, mention="fermé")

    def test_invalidate_verdicts_marks_them_invalid_and_counts_one_resume(self):
        judged = self.started_ticket()
        for kind in ("code_review", "evaluation"):
            self.ok("set-verdict", CONVOY, T1, "--kind", kind, "--state", "favorable", "--commit", judged)
        tip = self.commit_on("ticket/t1")

        answer = self.ok("invalidate-verdicts", CONVOY, T1, "--tip", tip, "--kind", "code_review", "--kind", "evaluation")
        self.assertEqual(["code_review", "evaluation"], answer["invalidated"])
        t1 = self.ticket(self.show(), T1)
        for kind in ("code_review", "evaluation"):
            self.assertEqual((judged, "favorable", False),
                             (t1["verdicts"][kind]["commit"], t1["verdicts"][kind]["state"], t1["verdicts"][kind]["valid"]))
            self.assertEqual(tip, t1["verdicts"][kind]["invalidated"]["tip"])
        self.assertEqual({"resumes": 1, "correction_rounds": 0}, t1["counters"])
        self.assertEqual([], t1["unruled"])

    def test_invalidate_verdicts_again_counts_nothing_more(self):
        judged = self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", judged)
        tip = self.commit_on("ticket/t1")
        self.ok("invalidate-verdicts", CONVOY, T1, "--tip", tip, "--kind", "code_review")
        before = self.tracker.read_bytes()

        answer = self.ok("invalidate-verdicts", CONVOY, T1, "--tip", self.commit_on("ticket/t1"), "--kind", "code_review")
        self.assertEqual(([], {}), (answer["invalidated"], answer["written"]))
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(1, self.ticket(self.show(), T1)["counters"]["resumes"])

    def test_an_invalidated_verdict_stays_invalid_until_it_is_replayed(self):
        judged = self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "favorable", "--commit", judged)
        tip = self.commit_on("ticket/t1")
        self.ok("invalidate-verdicts", CONVOY, T1, "--tip", tip, "--kind", "evaluation")

        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "favorable", "--commit", tip)
        verdict = self.ticket(self.show(), T1)["verdicts"]["evaluation"]
        self.assertIs(True, verdict["valid"])
        self.assertNotIn("invalidated", verdict)
        self.assertEqual(1, self.ticket(self.show(), T1)["counters"]["resumes"])

    def test_invalidate_verdicts_refuses_what_is_not_an_outdated_verdict(self):
        tip = self.started_ticket()
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", tip)
        for args, mention in (
            (("--tip", tip), "genre de verdict absent"),
            (("--tip", tip, "--kind", "vibes"), "genre de verdict"),
            (("--tip", tip, "--kind", "evaluation"), "ne porte pas de verdict evaluation"),
            (("--tip", "HEAD", "--kind", "code_review"), "pointe de la branche du ticket"),
            (("--kind", "code_review"), "pointe de la branche du ticket"),
            # the verdict judged that very tip: no commit was added after it
            (("--tip", tip, "--kind", "code_review"), "aucun commit ne lui a été ajouté"),
        ):
            with self.subTest(args=args):
                self.assert_refused_and_nothing_written("invalidate-verdicts", CONVOY, T1, *args, mention=mention)

    def test_integration_or_merge_written_outside_the_command_is_a_state_without_rule(self):
        self.started_ticket()
        self.edit_tracker(CONVOY, **{"gc.flow.integration": json.dumps({"branch": "integration/fx-spec"})})
        self.edit_tracker(T1, **{"gc.flow.merge": json.dumps({"outcome": "squashed", "at": "x"}),
                                 "gc.flow.verdict.fidelity": json.dumps(
                                     {"state": "favorable", "commit": ABSENT_COMMIT, "at": "x", "invalidated": "oui"})})

        shown = self.show(expect=EXIT_UNRULED)
        self.assertIn("unruled", shown["convoy"]["integration"])
        self.assertEqual(["gc.flow.integration"], [entry["field"] for entry in shown["convoy"]["unruled"]])
        ticket = self.ticket(shown, T1)
        self.assertIn("unruled", ticket["merge"])
        self.assertEqual({"gc.flow.merge", "gc.flow.verdict.fidelity"}, {entry["field"] for entry in ticket["unruled"]})

    def test_integration_merge_and_invalidation_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (
            ("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main", "--base", ABSENT_COMMIT),
            ("set-merge", CONVOY, T1, "--outcome", "conflict", "--ticket-commit", ABSENT_COMMIT,
             "--integration", ABSENT_COMMIT),
            ("invalidate-verdicts", CONVOY, T1, "--tip", ABSENT_COMMIT, "--kind", "code_review"),
        ):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- a review of the criterion tests recorded before ADR-0030 L3 ------------
    # bin/test-review and the commands that wrote gc.flow.test_review left in
    # L7; a ticket in flight may still carry its record or its stop.

    COUNT_TEST = "tests/test_count.py::CountTest.test_count_is_shown"

    def json_file(self, name, content):
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def red_slice(self):
        self.marked_slice()
        self.set_tdd("red", self.RED, "--base", self.BASE)

    def test_freeze_needs_no_review_of_the_criterion_tests(self):
        """ADR-0030 L3: the code review reads the criterion tests after the green."""
        self.red_slice()

        self.set_tdd("freeze", self.RED)

        self.assertEqual(self.RED, self.ticket(self.show(), T1)["tdd"]["freeze"]["commit"])
        self.assertIsNone(self.ticket(self.show(), T1).get("test_review"))

    def test_a_review_recorded_before_l3_is_still_read_and_holds_nothing(self):
        self.red_slice()
        record = {"rounds": [{"commit": self.RED, "files": {"tests/test_count.py": DIGEST}, "verdict": "unfavorable",
                              "tests": {self.COUNT_TEST: {"state": "unfavorable", "reason": "statut 200 seul"}},
                              "recorded_by": "delivery-reviewer-tests", "at": "2026-10-15T00:00:00Z"}],
                  "request": {"commit": self.RED, "files": {"tests/test_count.py": DIGEST},
                              "criteria": {"1": [self.COUNT_TEST]},
                              "launches": [{"bead": "fx-r1", "at": "2026-10-15T00:00:00Z"}],
                              "at": "2026-10-15T00:00:00Z"}}
        self.edit_tracker(T1, **{"gc.flow.test_review": json.dumps(record)})

        self.set_tdd("freeze", self.RED)

        shown = self.show()
        self.assertEqual(record, self.ticket(shown, T1)["test_review"])
        self.assertEqual(self.RED, self.ticket(shown, T1)["tdd"]["freeze"]["commit"])

    def test_a_review_without_result_is_a_reason_to_stop_a_ticket(self):
        """A stop the test review wrote before L3 is still read (a ticket in flight carries one)."""
        self.red_slice()

        self.ok("stop-ticket", CONVOY, T1, "--reason", "test_review_no_result",
                "--detail", "la relecture des tests n'a rendu aucun verdict, relance comprise")

        self.assertEqual("test_review_no_result", self.ticket(self.show(), T1)["stop"]["reason"])

    def test_a_stop_raised_to_the_operator_is_recorded_once(self):
        self.red_slice()
        self.assert_refused_and_nothing_written("stop-raised", CONVOY, T1, mention="n'est pas arrêté")
        self.ok("stop-ticket", CONVOY, T1, "--reason", "test_review_no_result", "--detail", "aucun verdict")
        self.assertNotIn("raised", self.ticket(self.show(), T1)["stop"])

        self.ok("stop-raised", CONVOY, T1)

        stop = self.ticket(self.show(), T1)["stop"]
        self.assertEqual(("test_review_no_result", "aucun verdict"), (stop["reason"], stop["detail"]))
        self.assertIn("raised", stop)
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok("stop-raised", CONVOY, T1)["written"])
        self.assertEqual(before, self.tracker.read_bytes())

    def test_test_review_written_outside_the_command_is_a_state_without_rule(self):
        self.red_slice()
        self.edit_tracker(T1, **{"gc.flow.test_review": json.dumps({"rounds": [{"verdict": "favorable"}]})})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("unruled", self.ticket(shown, T1)["test_review"])
        self.assertEqual(["gc.flow.test_review"], [entry["field"] for entry in self.ticket(shown, T1)["unruled"]])

    # --- code review of a ticket, models per role (T14) -------------------------

    def review_commits(self):
        """The start commit of the ticket branch, the commit under review and
        the commit of a correction, in a real repository: a verdict is tied
        to the branch of its ticket."""
        if not hasattr(self, "_review_commits"):
            self.init_repo()
            base = self.git("rev-parse", "HEAD")
            self._review_commits = (base, self.commit_on("ticket/t1"), self.commit_on("ticket/t1"))
        return self._review_commits

    REVIEW_BASE = property(lambda self: self.review_commits()[0])
    REVIEWED = property(lambda self: self.review_commits()[1])
    CORRECTED = property(lambda self: self.review_commits()[2])
    SPEC_LINE = "La page d'accueil affiche le nombre d'éléments."
    CITED = {"axis": "spec", "blocking": True, "summary": "Le nombre d'éléments n'est jamais rendu.",
             "citation": {"source": "spec", "quote": SPEC_LINE}}
    TASTE = {"axis": "standards", "blocking": True, "summary": "Possible Feature Envy dans render()."}
    SEAM_QUESTION = {"id": "Q1", "kind": "internal_test", "subject": "tests/test_internal.py",
                     "text": "Le fichier de test tests/test_internal.py passe-t-il par un seam listé ?"}

    def finished_slice(self, commit=None):
        """A marked slice whose author has finished at `commit`: sealed
        records, complete Handoff, Ticket Exit « terminé »."""
        commit = commit or self.REVIEWED
        if not self.tracker_state()["beads"][T1]["metadata"].get("gc.flow.mark"):
            self.marked_slice()
            self.ok("set-branch", CONVOY, T1, "--branch", "ticket/t1")
        self.sealed_records(commit)
        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file(commit=commit))
        self.ok("set-exit", CONVOY, T1, "--exit", "finished")

    def open_code_review(self, kind="review", commit=None, base=None, questions=None):
        args = ["open-code-review", CONVOY, T1, "--kind", kind, "--commit", commit or self.REVIEWED,
                "--base", base or self.REVIEW_BASE]
        if questions is not None:
            args += ["--file", self.json_file("questions.json", {"questions": questions})]
        return self.ok(*args)

    def review_file(self, findings=(), answers=None, commit=None, **extra):
        self.reviews = getattr(self, "reviews", 0) + 1
        content = {"commit": commit or self.REVIEWED, "recorded_by": f"delivery-reviewer-fx-{self.reviews}",
                   "findings": list(findings), **extra}
        if answers is not None:
            content["answers"] = answers
        return self.json_file(f"review-{self.reviews}.json", content)

    def record_code_review(self, findings=(), **given):
        return self.ok("record-code-review", CONVOY, T1, "--file", self.review_file(findings, **given))

    def judgement_file(self, judgements, commit=None):
        self.reviews = getattr(self, "reviews", 0) + 1
        return self.json_file(f"judgement-{self.reviews}.json", {
            "commit": commit or self.CORRECTED, "recorded_by": "delivery-reviewer-fx2", "judgements": judgements})

    def respond(self, responses):
        return self.ok("respond-code-review", CONVOY, T1, "--file",
                       self.json_file("responses.json", {"responses": responses}))

    def code_review(self, expect=0):
        return self.ticket(self.show(expect=expect), T1)["code_review"]

    def refused_review(self):
        """A review that left one Blocking Finding (F1.1) at REVIEWED."""
        self.finished_slice()
        self.open_code_review()
        return self.record_code_review([self.CITED])

    def corrected_review(self):
        """The Blocking Finding answered « corrigé » at CORRECTED, where the
        author finished again."""
        self.refused_review()
        self.respond({"F1.1": {"response": "fixed", "commit": self.CORRECTED}})
        self.finished_slice(self.CORRECTED)

    def test_set_model_records_the_model_of_a_role_on_the_ticket(self):
        self.marked_slice()
        self.assertIsNone(self.ticket(self.show(), T1)["models"])

        self.ok("set-model", CONVOY, T1, "--role", "author", "--agent", "delivery-author",
                "--provider", "claude-standard", "--model", "claude-opus-5-5")
        self.ok("set-model", CONVOY, T1, "--role", "reviewer", "--agent", "delivery-reviewer",
                "--provider", "codex", "--model", "gpt-5.6-sol")

        models = self.ticket(self.show(), T1)["models"]
        self.assertEqual(("delivery-author", "claude-standard", "claude-opus-5-5"),
                         tuple(models["author"][name] for name in ("agent", "provider", "model")))
        self.assertEqual("gpt-5.6-sol", models["reviewer"]["model"])

    def test_set_model_refuses_a_role_outside_the_list_and_a_missing_model(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "set-model", CONVOY, T1, "--role", "mayor", "--agent", "mayor", "--provider", "codex", "--model", "m",
            mention="liste fermée")
        self.assert_refused_and_nothing_written(
            "set-model", CONVOY, T1, "--role", "author", "--agent", "delivery-author", "--provider", "codex",
            mention="modèle")

    def test_open_code_review_records_the_request_at_the_commit_the_author_finished_at(self):
        self.finished_slice()
        self.assertIsNone(self.code_review())

        self.open_code_review(questions=[self.SEAM_QUESTION])

        review = self.code_review()
        self.assertEqual([], review["rounds"])
        request = review["request"]
        self.assertEqual(("review", self.REVIEWED, self.REVIEW_BASE, [self.SEAM_QUESTION], []),
                         tuple(request[name] for name in ("kind", "commit", "base", "questions", "launches")))
        self.assertEqual({"verdict": None, "commit": None, "unsettled": []}, review["state"])

    def test_the_request_says_whether_the_reviewer_has_another_model_than_the_author(self):
        self.finished_slice()
        self.open_code_review()
        self.assertEqual({"author": None, "reviewer": None, "same_model": None}, self.code_review()["request"]["models"])

        for reviewer, same in (("gpt-5.6-sol", False), ("Claude-Opus-5-5", True)):
            self.ok("set-model", CONVOY, T1, "--role", "author", "--agent", "delivery-author",
                    "--provider", "claude-standard", "--model", "claude-opus-5-5")
            self.ok("set-model", CONVOY, T1, "--role", "reviewer", "--agent", "delivery-reviewer",
                    "--provider", "p", "--model", reviewer)
            self.open_code_review(questions=[{**self.SEAM_QUESTION, "id": f"Q-{same}"}])
            self.assertEqual({"author": "claude-opus-5-5", "reviewer": reviewer, "same_model": same},
                             self.code_review()["request"]["models"])

    def test_the_mention_of_identical_models_is_kept_on_the_recorded_round(self):
        self.finished_slice()
        for role in ("author", "reviewer"):
            self.ok("set-model", CONVOY, T1, "--role", role, "--agent", f"delivery-{role}",
                    "--provider", "claude", "--model", "claude-opus-5-5")
        self.open_code_review()

        self.record_code_review()

        self.assertIs(True, self.code_review()["rounds"][0]["models"]["same_model"])

    def test_open_code_review_is_refused_on_a_ticket_that_is_not_finished_at_that_commit(self):
        self.marked_slice()
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE,
            mention="terminé")
        self.finished_slice()
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.CORRECTED, "--base", self.REVIEW_BASE,
            mention="Handoff")
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "avis", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE,
            mention="liste fermée")
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", "abc", "--base", self.REVIEW_BASE,
            mention="SHA")

    def test_open_code_review_is_refused_on_a_stopped_ticket(self):
        self.finished_slice()
        self.ok("stop-ticket", CONVOY, T1, "--reason", "code_review_no_result", "--detail", "aucun verdict")

        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE,
            mention="arrêté")

    def test_the_same_code_review_opened_twice_writes_nothing_and_a_third_launch_is_refused(self):
        self.finished_slice()
        self.open_code_review()
        self.ok("launch-code-review", CONVOY, T1, "--bead", "fx-r1")
        before = self.tracker.read_bytes()

        self.assertEqual({}, self.open_code_review()["written"])

        self.assertEqual(before, self.tracker.read_bytes())
        self.ok("launch-code-review", CONVOY, T1, "--bead", "fx-r2")
        self.assertEqual(["fx-r1", "fx-r2"], [launch["bead"] for launch in self.code_review()["request"]["launches"]])
        self.assert_refused_and_nothing_written("launch-code-review", CONVOY, T1, "--bead", "fx-r3", mention="relance")

    def test_a_review_without_finding_is_favorable_at_the_reviewed_commit(self):
        self.finished_slice()
        self.open_code_review()

        answer = self.record_code_review()

        self.assertEqual(("favorable", [], []), (answer["verdict"], answer["blocking"], answer["demoted"]))
        ticket = self.ticket(self.show(), T1)
        self.assertNotIn("request", ticket["code_review"])
        (round_,) = ticket["code_review"]["rounds"]
        self.assertEqual(("review", "favorable", self.REVIEWED, self.REVIEW_BASE, "delivery-reviewer-fx-1"),
                         tuple(round_[name] for name in ("kind", "verdict", "commit", "base", "recorded_by")))
        self.assertEqual({"verdict": "favorable", "commit": self.REVIEWED, "unsettled": []}, ticket["code_review"]["state"])
        self.assertEqual(("favorable", self.REVIEWED),
                         tuple(ticket["verdicts"]["code_review"][name] for name in ("state", "commit")))

    def test_a_finding_that_cites_a_line_of_the_spec_is_a_blocking_finding(self):
        self.finished_slice()
        self.open_code_review()

        answer = self.record_code_review([self.CITED])

        self.assertEqual(("unfavorable", ["F1.1"]), (answer["verdict"], answer["blocking"]))
        ticket = self.ticket(self.show(), T1)
        (finding,) = ticket["code_review"]["rounds"][0]["findings"]
        self.assertEqual(("F1.1", True, self.CITED["citation"]),
                         (finding["id"], finding["blocking"], finding["citation"]))
        self.assertEqual({"verdict": "unfavorable", "commit": self.REVIEWED, "unsettled": ["F1.1"]},
                         ticket["code_review"]["state"])
        self.assertEqual("unfavorable", ticket["verdicts"]["code_review"]["state"])

    def test_a_blocking_finding_without_citation_is_recorded_as_non_blocking(self):
        # AC2, and the demonstration line: a finding of taste is recorded
        # without blocking.
        self.finished_slice()
        self.open_code_review()

        answer = self.record_code_review([self.TASTE])

        self.assertEqual(("favorable", []), (answer["verdict"], answer["blocking"]))
        self.assertEqual(["F1.1"], [entry["id"] for entry in answer["demoted"]])
        self.assertIn("citation", answer["demoted"][0]["reason"])
        (finding,) = self.code_review()["rounds"][0]["findings"]
        self.assertIs(False, finding["blocking"])
        self.assertEqual(self.TASTE["summary"], finding["summary"])
        self.assertIn("citation", finding["demoted"])

    def test_a_citation_the_caller_could_not_find_in_its_source_does_not_block(self):
        self.finished_slice()
        self.open_code_review()
        unfound = {**self.CITED, "citation_refused": "la citation est absente de la Spec fx-spec"}
        outside = {**self.CITED, "citation": {"source": "goût", "quote": "x"}}
        no_path = {**self.CITED, "citation": {"source": "repo_rule", "quote": "Toute fonction est typée."}}

        answer = self.record_code_review([unfound, outside, no_path])

        self.assertEqual(("favorable", []), (answer["verdict"], answer["blocking"]))
        findings = self.code_review()["rounds"][0]["findings"]
        self.assertEqual([False, False, False], [finding["blocking"] for finding in findings])
        self.assertIn("absente de la Spec", findings[0]["demoted"])

    def test_a_closed_question_answered_no_is_a_blocking_finding(self):
        # AC6: a test file internal to a seam that is not listed, an amended
        # test that no longer observes its criterion.
        amended = {"id": "Q2", "kind": "amended_test", "subject": self.COUNT_TEST,
                   "text": "Le test amendé observe-t-il encore son critère ?"}
        self.finished_slice()
        self.open_code_review(questions=[self.SEAM_QUESTION, amended])

        answer = self.record_code_review(answers={
            "Q1": {"answer": "non", "reason": "il importe render() sans passer par GET /"},
            "Q2": {"answer": "oui"}})

        self.assertEqual(("unfavorable", ["F1.1"]), (answer["verdict"], answer["blocking"]))
        (finding,) = self.code_review()["rounds"][0]["findings"]
        self.assertEqual(("tests", True, "Q1"), (finding["axis"], finding["blocking"], finding["question"]))
        self.assertIn("il importe render()", finding["summary"])
        self.assertEqual({"Q1": {"answer": "non", "reason": "il importe render() sans passer par GET /"},
                          "Q2": {"answer": "oui"}}, self.code_review()["rounds"][0]["answers"])

    def test_record_code_review_refuses_answers_outside_the_closed_questions(self):
        self.finished_slice()
        self.open_code_review(questions=[self.SEAM_QUESTION])
        for answers, mention in (({}, "Q1"), ({"Q1": {"answer": "non"}}, "sans raison"),
                                 ({"Q1": {"answer": "peut-être"}}, "liste fermée"),
                                 ({"Q1": {"answer": "oui"}, "Q9": {"answer": "oui"}}, "Q9")):
            self.assert_refused_and_nothing_written(
                "record-code-review", CONVOY, T1, "--file", self.review_file(answers=answers), mention=mention)

    def test_record_code_review_refuses_a_verdict_given_by_the_reviewer_and_a_review_outside_its_request(self):
        self.finished_slice()
        self.assert_refused_and_nothing_written(
            "record-code-review", CONVOY, T1, "--file", self.review_file(), mention="aucune revue")
        self.open_code_review()
        for content, mention in (
            (self.review_file(verdict="favorable"), "verdict"),
            (self.review_file(commit=self.CORRECTED), "commit"),
            (self.review_file([{**self.CITED, "axis": "goût"}]), "liste fermée"),
            (self.review_file([{**self.CITED, "summary": ""}]), "résumé"),
            (self.review_file([{**self.CITED, "blocking": "oui"}]), "blocking"),
            (self.review_file(recorded_by=""), "session"),
        ):
            self.assert_refused_and_nothing_written("record-code-review", CONVOY, T1, "--file", content, mention=mention)

    def test_each_blocking_finding_is_answered_fixed_or_contested(self):
        self.finished_slice()
        self.open_code_review()
        self.record_code_review([self.CITED, {**self.CITED, "summary": "Le libellé manque."}, self.TASTE])

        self.respond({"F1.1": {"response": "fixed", "commit": self.CORRECTED},
                      "F1.2": {"response": "contested", "reason": "La Spec dit « nombre », pas « libellé »."}})

        responses = self.code_review()["rounds"][0]["responses"]
        self.assertEqual(("fixed", self.CORRECTED), (responses["F1.1"]["response"], responses["F1.1"]["commit"]))
        self.assertEqual("contested", responses["F1.2"]["response"])

    def test_respond_refuses_a_list_that_is_not_the_closed_list_of_blocking_findings(self):
        self.finished_slice()
        self.assert_refused_and_nothing_written(
            "respond-code-review", CONVOY, T1, "--file",
            self.json_file("responses.json", {"responses": {}}), mention="aucun Blocking Finding")
        self.open_code_review()
        self.record_code_review([self.CITED, self.TASTE])
        fixed = {"response": "fixed", "commit": self.CORRECTED}
        for responses, mention in (
            ({}, "F1.1"),
            ({"F1.1": fixed, "F1.2": fixed}, "F1.2"),
            ({"F1.1": {"response": "fixed"}}, "commit"),
            ({"F1.1": {"response": "contested"}}, "raison"),
            ({"F1.1": {"response": "ignoré"}}, "liste fermée"),
        ):
            self.assert_refused_and_nothing_written(
                "respond-code-review", CONVOY, T1, "--file",
                self.json_file("responses.json", {"responses": responses}), mention=mention)

    def test_a_second_review_is_not_opened_while_blocking_findings_wait_for_their_judgement(self):
        self.refused_review()

        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE,
            mention="Blocking Finding")
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "judgement", "--commit", self.REVIEWED, "--base", self.REVIEWED,
            mention="réponse")

    def test_a_review_outdated_before_any_correction_round_is_replayed_at_the_new_tip(self):
        # af-s31cvi: the author finished again at a new tip outside the round.
        self.refused_review()
        self.finished_slice(self.CORRECTED)

        self.open_code_review("review", self.CORRECTED)

        request = self.code_review()["request"]
        self.assertEqual(("review", self.CORRECTED), (request["kind"], request["commit"]))

    def test_a_review_whose_findings_were_answered_is_judged_not_replayed(self):
        self.corrected_review()

        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.CORRECTED, "--base", self.REVIEW_BASE,
            mention="Blocking Finding")

    def test_a_review_is_not_replayed_while_the_correction_round_answers_its_findings(self):
        self.refused_review()
        self.evaluated(**self.NOT_OBSERVED)
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)
        self.finished_slice(self.CORRECTED)

        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.CORRECTED, "--base", self.REVIEW_BASE,
            mention="Blocking Finding")

    def test_the_judgement_is_opened_on_the_answered_list_against_the_correction(self):
        self.corrected_review()

        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)

        request = self.code_review()["request"]
        self.assertEqual(("judgement", self.CORRECTED, self.REVIEWED, []),
                         tuple(request[name] for name in ("kind", "commit", "base", "questions")))
        self.assert_refused_and_nothing_written(
            "respond-code-review", CONVOY, T1, "--file",
            self.json_file("responses.json", {"responses": {"F1.1": {"response": "contested", "reason": "non"}}}),
            mention="jugement")

    def test_a_judgement_is_refused_on_another_base_than_the_reviewed_commit_or_without_a_refused_review(self):
        self.corrected_review()
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "judgement", "--commit", self.CORRECTED, "--base", self.REVIEW_BASE,
            mention="commit revu")

    def test_every_blocking_finding_judged_favorably_by_the_second_session_gives_a_favorable_verdict(self):
        # AC3, second half.
        self.corrected_review()
        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)

        answer = self.ok("record-code-review", CONVOY, T1, "--file", self.judgement_file({"F1.1": {"state": "favorable"}}))

        self.assertEqual("favorable", answer["verdict"])
        ticket = self.ticket(self.show(), T1)
        self.assertEqual(["review", "judgement"], [round_["kind"] for round_ in ticket["code_review"]["rounds"]])
        self.assertEqual("delivery-reviewer-fx2", ticket["code_review"]["rounds"][1]["recorded_by"])
        self.assertEqual({"verdict": "favorable", "commit": self.CORRECTED, "unsettled": []}, ticket["code_review"]["state"])
        self.assertEqual(("favorable", self.CORRECTED),
                         tuple(ticket["verdicts"]["code_review"][name] for name in ("state", "commit")))

    def test_a_blocking_finding_judged_unfavorably_stays_unsettled_and_nothing_more_opens(self):
        self.corrected_review()
        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)

        answer = self.ok("record-code-review", CONVOY, T1, "--file", self.judgement_file(
            {"F1.1": {"state": "unfavorable", "reason": "le correctif n'affiche toujours pas le nombre"}}))

        self.assertEqual(("unfavorable", ["F1.1"]), (answer["verdict"], answer["blocking"]))
        self.assertEqual({"verdict": "unfavorable", "commit": self.CORRECTED, "unsettled": ["F1.1"]},
                         self.code_review()["state"])
        for kind, base in (("review", self.REVIEW_BASE), ("judgement", self.REVIEWED)):
            self.assert_refused_and_nothing_written(
                "open-code-review", CONVOY, T1, "--kind", kind, "--commit", self.CORRECTED, "--base", base,
                mention="tour de correction")

    def test_a_judgement_given_by_the_session_that_reviewed_is_refused(self):
        self.corrected_review()
        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)
        reviewed_by = self.ticket(self.show(), T1)["code_review"]["rounds"][0]["recorded_by"]
        same_session = self.json_file("judgement-same.json", {
            "commit": self.CORRECTED, "recorded_by": reviewed_by, "judgements": {"F1.1": {"state": "favorable"}}})

        self.assert_refused_and_nothing_written(
            "record-code-review", CONVOY, T1, "--file", same_session, mention="session neuve")

    def judge_after_a_review_by(self, reviewed_conversation, judged_conversation):
        """gc 1.5.0 wakes a drained session again under the same name: the
        review is rendered by `delivery-reviewer-fx` in conversation
        `reviewed_conversation` (None: a record from before conversations were
        recorded), the judgement by the same name in `judged_conversation`."""
        self.finished_slice()
        self.open_code_review()
        extra = {} if reviewed_conversation is None else {"conversation": reviewed_conversation}
        self.ok("record-code-review", CONVOY, T1, "--file", self.json_file("review-woken.json", {
            "commit": self.REVIEWED, "recorded_by": "delivery-reviewer-fx", "findings": [self.CITED], **extra}))
        self.respond({"F1.1": {"response": "fixed", "commit": self.CORRECTED}})
        self.finished_slice(self.CORRECTED)
        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)
        return ("record-code-review", CONVOY, T1, "--file", self.json_file("judgement-woken.json", {
            "commit": self.CORRECTED, "recorded_by": "delivery-reviewer-fx", "conversation": judged_conversation,
            "judgements": {"F1.1": {"state": "favorable"}}}))

    def test_a_judgement_by_the_same_conversation_of_a_woken_session_is_refused(self):
        self.assert_refused_and_nothing_written(*self.judge_after_a_review_by("3", "3"), mention="session neuve")

    def test_a_judgement_by_a_fresh_conversation_of_a_woken_session_is_accepted(self):
        answer = self.ok(*self.judge_after_a_review_by("3", "4"))

        self.assertEqual("favorable", answer["verdict"])
        self.assertEqual([("delivery-reviewer-fx", "3"), ("delivery-reviewer-fx", "4")],
                         [(round_["recorded_by"], round_["conversation"]) for round_ in self.code_review()["rounds"]])

    def test_a_review_recorded_without_its_conversation_still_refuses_its_session_name(self):
        self.assert_refused_and_nothing_written(*self.judge_after_a_review_by(None, "4"), mention="session neuve")

    def test_a_judgement_refuses_a_list_that_is_not_the_blocking_findings(self):
        self.corrected_review()
        self.open_code_review("judgement", self.CORRECTED, self.REVIEWED)
        for judgements, mention in (({}, "F1.1"), ({"F1.1": {"state": "unfavorable"}}, "sans raison"),
                                    ({"F1.1": {"state": "favorable"}, "F1.9": {"state": "favorable"}}, "F1.9")):
            self.assert_refused_and_nothing_written(
                "record-code-review", CONVOY, T1, "--file", self.judgement_file(judgements), mention=mention)

    def test_a_commit_added_after_a_favorable_review_has_it_replayed_in_full(self):
        self.finished_slice()
        self.open_code_review()
        self.record_code_review()
        self.assert_refused_and_nothing_written(
            "open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE,
            mention="déjà")
        self.finished_slice(self.CORRECTED)

        self.open_code_review(commit=self.CORRECTED)

        self.assertEqual(("review", self.CORRECTED), tuple(self.code_review()["request"][n] for n in ("kind", "commit")))

    def test_a_code_review_without_result_is_a_reason_to_stop_a_ticket(self):
        self.finished_slice()

        self.ok("stop-ticket", CONVOY, T1, "--reason", "code_review_no_result",
                "--detail", "la revue de code n'a rendu aucun verdict, relance comprise")

        self.assertEqual("code_review_no_result", self.ticket(self.show(), T1)["stop"]["reason"])

    def test_code_review_or_models_written_outside_the_command_are_a_state_without_rule(self):
        self.finished_slice()
        self.edit_tracker(T1, **{"gc.flow.code_review": json.dumps({"rounds": [{"verdict": "favorable"}]}),
                                 "gc.flow.models": json.dumps({"mayor": {"model": "m"}})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["code_review"])
        self.assertIn("unruled", ticket["models"])
        self.assertEqual(["gc.flow.code_review", "gc.flow.models"], sorted(entry["field"] for entry in ticket["unruled"]))

    def test_code_review_on_an_unmarked_convoy_writes_nothing(self):
        before = self.tracker.read_text()
        for command in (
            ("open-code-review", CONVOY, T1, "--kind", "review", "--commit", self.REVIEWED, "--base", self.REVIEW_BASE),
            ("launch-code-review", CONVOY, T1, "--bead", "fx-r1"),
            ("record-code-review", CONVOY, T1, "--file", self.review_file()),
            ("respond-code-review", CONVOY, T1, "--file", self.json_file("responses.json", {"responses": {}})),
            ("set-model", CONVOY, T1, "--role", "author", "--agent", "a", "--provider", "p", "--model", "m"),
        ):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- Ticket Evaluation on the launched product (T15) ---------------------------

    CRITERIA = ("Le nombre s'affiche", "La sonde nomme le jeu")
    LINE = "La page affiche 3"
    ROLES = {"author": {"provider": "claude-standard", "supplier": "anthropic"},
             "evaluator": {"provider": "codex", "supplier": "openai"}, "same_provider": False,
             "other_declared": ["openai"]}
    PRODUCT = {"dataset": "content", "address": "http://127.0.0.1:41001", "state_file": "/state/content.json"}

    def open_evaluation(self, commit=None, environment=None, roles=None):
        return self.ok("open-evaluation", CONVOY, T1, "--commit", commit or self.REVIEWED, "--file",
                       self.json_file("evaluation-request.json",
                                      {"roles": roles or self.ROLES, "environment": environment or [self.PRODUCT]}))

    def captured(self, piece="evaluation.seen", commit=None, ticket=T1):
        """The fingerprint bin/evidence-capture writes for a piece captured at `commit`."""
        self.ok("add-evidence", CONVOY, ticket, "--piece", piece, "--digest", DIGEST, "--commit", commit or self.REVIEWED)
        return piece

    def states(self, commit=None, **changes):
        """Every state « observed », each on a captured piece."""
        piece = self.captured(commit=commit)
        self.evaluations = getattr(self, "evaluations", 0) + 1
        content = {
            "commit": commit or self.REVIEWED, "recorded_by": f"delivery-evaluator-fx-{self.evaluations}",
            "criteria": [{"number": number, "text": text, "state": "observed", "evidence": piece}
                         for number, text in enumerate(self.CRITERIA, start=1)],
            "demonstration_line": {"text": self.LINE, "state": "observed", "evidence": piece},
        }
        content.update(changes)
        return content

    def states_file(self, content):
        return self.json_file("evaluation.json", content)

    def record_evaluation(self, content=None):
        return self.ok("record-evaluation", CONVOY, T1, "--file", self.states_file(content or self.states()))

    def evaluation(self, expect=0):
        return self.ticket(self.show(expect=expect), T1)["evaluation"]

    def opened_evaluation(self):
        self.finished_slice()
        self.open_evaluation()

    def finished_prefactoring(self):
        """A marked prefactoring whose author has finished at REVIEWED."""
        commit = self.REVIEWED
        self.ok("mark", CONVOY)
        self.ok("set-branch", CONVOY, T1, "--branch", "ticket/t1")
        self.sealed_records(commit)
        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file(commit=commit))
        self.ok("set-exit", CONVOY, T1, "--exit", "finished")
        return commit

    def test_open_evaluation_freezes_the_criteria_and_the_demonstration_line_of_the_approved_ticket(self):
        self.finished_slice()

        self.open_evaluation()

        evaluation = self.evaluation()
        request = evaluation["request"]
        self.assertEqual((self.REVIEWED, list(self.CRITERIA), self.LINE),
                         (request["commit"], request["criteria"], request["demonstration_line"]))
        self.assertEqual((self.ROLES, [self.PRODUCT], []), (request["roles"], request["environment"], request["launches"]))
        self.assertEqual([self.PRODUCT["state_file"]], evaluation["live"])
        self.assertEqual({"verdict": None, "outcome": None, "commit": None, "not_observed": [], "unobservable": []},
                         evaluation["state"])

    def test_open_evaluation_twice_writes_nothing_more_and_new_products_keep_the_launches(self):
        self.opened_evaluation()
        self.ok("launch-evaluation", CONVOY, T1, "--bead", "fx-e1")
        self.assertEqual({}, self.open_evaluation()["written"])

        other = {**self.PRODUCT, "address": "http://127.0.0.1:41002", "state_file": "/state/content-2.json"}
        self.open_evaluation(environment=[other])

        evaluation = self.evaluation()
        self.assertEqual(([other], ["fx-e1"]), (evaluation["request"]["environment"],
                                                [launch["bead"] for launch in evaluation["request"]["launches"]]))
        self.assertEqual([other["state_file"], self.PRODUCT["state_file"]], evaluation["live"])

    def test_open_evaluation_refusals_write_nothing(self):
        self.finished_slice()
        request = self.json_file("evaluation-request.json", {"roles": self.ROLES, "environment": [self.PRODUCT]})
        for content, mention in (
            ({"roles": self.ROLES}, "environnement d'évaluation absent"),
            ({"roles": self.ROLES, "environment": [{**self.PRODUCT, "address": "http://example.org"}]}, "adresse du produit lancé"),
            ({"roles": self.ROLES, "environment": [{"dataset": "content", "address": self.PRODUCT["address"]}]},
             "environnement d'évaluation mal formé"),
            ({"environment": [self.PRODUCT]}, "relevé des rôles"),
            ({"roles": {**self.ROLES, "same_provider": None}, "environment": [self.PRODUCT]}, "incohérent"),
            ({"roles": self.ROLES, "environment": [self.PRODUCT], "criteria": ["autre"]}, "champs inconnus"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(
                    "open-evaluation", CONVOY, T1, "--commit", self.REVIEWED, "--file",
                    self.json_file("refused-request.json", content), mention=mention)
        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", self.CORRECTED, "--file", request, mention="Ticket Handoff")
        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", "HEAD", "--file", request, mention="commit de l'évaluation")

    def test_open_evaluation_refuses_a_ticket_that_is_not_finished_or_has_no_criterion(self):
        self.marked_slice()
        self.review_commits()
        request = self.json_file("evaluation-request.json", {"roles": self.ROLES, "environment": [self.PRODUCT]})
        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", self.REVIEWED, "--file", request, mention="n'est pas terminé")

        self.finished_slice()
        self.edit_bead(T1, description="## What to build\n\nrien d'observable\n")
        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", self.REVIEWED, "--file", request,
            mention="aucun critère d'acceptation")

    def test_open_evaluation_refuses_a_prefactoring(self):
        commit = self.finished_prefactoring()

        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", commit, "--file",
            self.json_file("evaluation-request.json", {"roles": self.ROLES, "environment": [self.PRODUCT]}),
            mention="aucune session d'Evaluator")

    def test_launch_evaluation_records_two_launches_and_refuses_a_third(self):
        self.finished_slice()
        self.assert_refused_and_nothing_written("launch-evaluation", CONVOY, T1, "--bead", "fx-e1", mention="rien à lancer")
        self.open_evaluation()
        self.assert_refused_and_nothing_written("launch-evaluation", CONVOY, T1, "--bead", "pas un bead", mention="mal formé")

        self.ok("launch-evaluation", CONVOY, T1, "--bead", "fx-e1")
        self.ok("launch-evaluation", CONVOY, T1, "--bead", "fx-e2")

        self.assertEqual(["fx-e1", "fx-e2"], [launch["bead"] for launch in self.evaluation()["request"]["launches"]])
        self.assert_refused_and_nothing_written("launch-evaluation", CONVOY, T1, "--bead", "fx-e3", mention="une seule relance")

    def test_record_evaluation_computes_a_favorable_verdict_when_everything_is_observed(self):
        self.opened_evaluation()

        answer = self.record_evaluation()

        self.assertEqual(("favorable", "favorable"), (answer["outcome"], answer["verdict"]))
        evaluation = self.evaluation()
        self.assertNotIn("request", evaluation)
        (round_,) = evaluation["rounds"]
        self.assertEqual(("evaluation", self.REVIEWED, "delivery-evaluator-fx-1", self.ROLES),
                         tuple(round_[name] for name in ("kind", "commit", "recorded_by", "roles")))
        self.assertEqual([{"dataset": "content", "address": self.PRODUCT["address"]}], round_["environment"])
        self.assertEqual([(1, self.CRITERIA[0], "observed"), (2, self.CRITERIA[1], "observed")],
                         [(item["number"], item["text"], item["state"]) for item in round_["criteria"]])
        verdict = self.ticket(self.show(), T1)["verdicts"]["evaluation"]
        self.assertEqual(("favorable", self.REVIEWED), (verdict["state"], verdict["commit"]))

    def test_record_evaluation_records_the_demonstration_line_alone_without_criteria_states(self):
        # ADR-0030 L4: the frozen criterion tests prove the criteria; the
        # Evaluator of an interface ticket judges the demonstration line.
        self.opened_evaluation()
        content = self.states()
        del content["criteria"]

        answer = self.record_evaluation(content)

        self.assertEqual(("favorable", "favorable"), (answer["outcome"], answer["verdict"]))
        (round_,) = self.evaluation()["rounds"]
        self.assertEqual(([], "observed"), (round_["criteria"], round_["demonstration_line"]["state"]))

    def test_record_evaluation_computes_the_outcome_of_each_refusal(self):
        not_observed = {"state": "not_observed", "reason": "le nombre n'est pas sur la page"}
        by_criterion = {"state": "unobservable", "cause": "criterion", "reason": "aucun point d'entrée ne le sert"}
        by_environment = {"state": "unobservable", "cause": "environment", "reason": "le produit ne répond plus"}
        for first, second, outcome, verdict in (
            (not_observed, {}, "return_to_author", "unfavorable"),
            (by_criterion, {}, "planning_exception", "unfavorable"),
            (by_criterion, not_observed, "planning_exception", "unfavorable"),
            (by_environment, not_observed, "return_to_author", "unfavorable"),
            (by_environment, {}, "environment_outage", None),
        ):
            with self.subTest(outcome=outcome, first=first["state"], second=second.get("state")):
                # Each case on a convoy and a repository of its own.
                self.seed()
                self.__dict__.pop("_review_commits", None)
                shutil.rmtree(self.repo, ignore_errors=True)
                self.opened_evaluation()
                content = self.states()
                content["criteria"][0].update(first)
                content["criteria"][1].update(second)

                answer = self.record_evaluation(content)

                self.assertEqual((outcome, verdict), (answer["outcome"], answer["verdict"]))
                shown = self.ticket(self.show(), T1)
                self.assertEqual(outcome, shown["evaluation"]["state"]["outcome"])
                if verdict is None:
                    # An outage is not a refusal: no verdict is written.
                    self.assertNotIn("evaluation", shown["verdicts"])
                    self.assertEqual([{"what": "critère 1", "cause": "environment"}],
                                     shown["evaluation"]["state"]["unobservable"])
                else:
                    self.assertEqual(verdict, shown["verdicts"]["evaluation"]["state"])

    def test_record_evaluation_refuses_what_is_outside_its_contract_and_writes_nothing(self):
        self.opened_evaluation()
        valid = self.states()

        def changed(**criterion):
            content = json.loads(json.dumps(valid))
            content["criteria"][0].update(criterion)
            return content

        without_evidence = changed()
        del without_evidence["criteria"][0]["evidence"]
        twice = json.loads(json.dumps(valid))
        twice["criteria"].append(dict(twice["criteria"][0]))
        other_commit = self.captured("evaluation.other", commit=self.CORRECTED)
        for content, mention in (
            ({**valid, "verdict": "favorable"}, "le verdict est calculé par du code, jamais donné par l'Evaluator"),
            ({**valid, "outcome": "favorable"}, "le verdict est calculé par du code"),
            ({**valid, "note": "tout va bien"}, "champ inconnu : note"),
            ({**valid, "commit": self.CORRECTED}, "porte sur le commit"),
            ({**valid, "recorded_by": ""}, "session de l'Evaluator"),
            (changed(state="partially_observed"), "état hors de la liste fermée"),
            (without_evidence, "état sans Evidence Record valide"),
            (changed(evidence="evaluation.absent"), "n'a pas d'empreinte sur le ticket"),
            (changed(evidence=other_commit), "non au commit évalué"),
            (changed(text="Le nombre est visible"), "critère 1 reformulé"),
            (twice, "deux états rendus"),
            ({**valid, "criteria": valid["criteria"] + [{"number": 3, "text": "x", "state": "observed",
                                                         "evidence": "evaluation.seen"}]},
             "un critère que le ticket approuvé n'a pas"),
            ({**valid, "demonstration_line": {**valid["demonstration_line"], "text": "La page répond"}},
             "ligne de démonstration reformulé"),
            ({key: value for key, value in valid.items() if key != "demonstration_line"},
             "ligne de démonstration : aucun état rendu"),
            (changed(state="not_observed"), "sans raison"),
            (changed(reason="tout est là"), "une raison ne se donne pas"),
            (changed(state="unobservable", reason="rien"), "sans cause dans la liste fermée"),
            (changed(state="unobservable", reason="rien", cause="author"), "sans cause dans la liste fermée"),
            (changed(cause="criterion"), "une cause ne se donne qu'avec"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(
                    "record-evaluation", CONVOY, T1, "--file", self.states_file(content), mention=mention)

    def test_record_evaluation_refuses_criteria_changed_on_the_ticket_since_the_request(self):
        self.opened_evaluation()
        content = self.states()
        self.edit_bead(T1, description="## Acceptance criteria\n\n- [ ] Le nombre s'affiche\n")

        self.assert_refused_and_nothing_written(
            "record-evaluation", CONVOY, T1, "--file", self.states_file(content),
            mention="ne sont plus ceux de la demande d'évaluation")

    def test_record_evaluation_without_an_open_request_is_refused(self):
        self.finished_slice()

        self.assert_refused_and_nothing_written(
            "record-evaluation", CONVOY, T1, "--file", self.states_file(self.states()),
            mention="aucune évaluation n'est demandée")

    def test_an_evaluation_already_made_at_a_commit_is_not_opened_again_unless_it_was_an_outage(self):
        self.opened_evaluation()
        content = self.states()
        content["criteria"][0].update(state="unobservable", cause="environment", reason="le produit ne répond plus")
        self.record_evaluation(content)

        self.open_evaluation()
        self.record_evaluation()

        self.assertEqual(["environment_outage", "favorable"], [r["outcome"] for r in self.evaluation()["rounds"]])
        self.assert_refused_and_nothing_written(
            "open-evaluation", CONVOY, T1, "--commit", self.REVIEWED, "--file",
            self.json_file("evaluation-request.json", {"roles": self.ROLES, "environment": [self.PRODUCT]}),
            mention="déjà évalué")

    def test_record_startup_records_that_the_product_of_a_prefactoring_starts(self):
        commit = self.finished_prefactoring()
        piece = self.captured("evaluation.startup", commit=commit)
        environment = [{"dataset": "content", "address": self.PRODUCT["address"]}]

        answer = self.ok("record-startup", CONVOY, T1, "--commit", commit, "--piece", piece, "--file",
                         self.json_file("startup.json", {"environment": environment}))

        self.assertEqual(("startup", "favorable", "favorable"), (answer["kind"], answer["outcome"], answer["verdict"]))
        (round_,) = self.evaluation()["rounds"]
        self.assertEqual((True, piece, environment), (round_["started"], round_["evidence"], round_["environment"]))
        self.assertEqual("favorable", self.ticket(self.show(), T1)["verdicts"]["evaluation"]["state"])

    def test_record_startup_records_a_product_that_does_not_start_as_unfavorable(self):
        commit = self.finished_prefactoring()

        answer = self.ok("record-startup", CONVOY, T1, "--commit", commit, "--detail", "la sonde ne répond pas")

        self.assertEqual(("return_to_author", "unfavorable"), (answer["outcome"], answer["verdict"]))
        evaluation = self.evaluation()
        self.assertEqual((False, "la sonde ne répond pas"), (evaluation["rounds"][0]["started"], evaluation["rounds"][0]["detail"]))
        self.assertEqual(["démarrage du produit"], evaluation["state"]["not_observed"])

    def test_record_startup_refusals_write_nothing(self):
        commit = self.finished_prefactoring()
        environment = self.json_file("startup.json", {"environment": [{"dataset": None, "address": self.PRODUCT["address"]}]})
        for args, mention in (
            (("--commit", commit), "précision du démarrage manqué"),
            (("--commit", commit, "--piece", "evaluation.absent", "--file", environment), "sans Evidence Record valide"),
            (("--commit", commit, "--piece", self.captured("evaluation.startup", commit=commit), "--detail", "x"), "s'excluent"),
            (("--commit", commit, "--piece", "evaluation.startup"), "illisible"),
            (("--commit", self.CORRECTED, "--detail", "x"), "Ticket Handoff"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written("record-startup", CONVOY, T1, *args, mention=mention)

    def test_a_product_that_starts_is_not_the_evaluation_of_an_interface_slice_but_one_that_does_not_start_refuses_it(self):
        self.opened_evaluation()
        description = self.tracker_state()["beads"][T1]["description"]
        self.edit_bead(T1, description=description + "\n\n" + self.prototype_section())
        piece = self.captured("evaluation.startup")
        self.assert_refused_and_nothing_written(
            "record-startup", CONVOY, T1, "--commit", self.REVIEWED, "--piece", piece, "--file",
            self.json_file("startup.json", {"environment": [{"dataset": None, "address": self.PRODUCT["address"]}]}),
            mention="ne vaut évaluation que pour un ticket sans interface")

        self.ok("record-startup", CONVOY, T1, "--commit", self.REVIEWED, "--detail", "la copie propre ne démarre pas")

        evaluation = self.evaluation()
        self.assertNotIn("request", evaluation)
        self.assertEqual("unfavorable", evaluation["state"]["verdict"])

    def test_a_product_that_starts_is_the_evaluation_of_a_slice_without_interface_its_model_one_not_required(self):
        """ADR-0030 L4: only an interface ticket is evaluated by a model."""
        self.opened_evaluation()
        piece = self.captured("evaluation.startup")

        self.ok("record-startup", CONVOY, T1, "--commit", self.REVIEWED, "--piece", piece, "--file",
                self.json_file("startup.json", {"environment": [{"dataset": None, "address": self.PRODUCT["address"]}]}))

        evaluation = self.evaluation()
        self.assertNotIn("request", evaluation)
        self.assertEqual(("startup", "favorable", "not_required"),
                         tuple(evaluation["rounds"][-1].get(name) for name in ("kind", "verdict", "model")))

    def test_release_evaluation_forgets_the_stopped_products_and_keeps_those_an_open_evaluation_runs_on(self):
        self.opened_evaluation()
        self.assert_refused_and_nothing_written(
            "release-evaluation", CONVOY, T1, "--state-file", self.PRODUCT["state_file"], mention="une évaluation est ouverte")
        self.assert_refused_and_nothing_written("release-evaluation", CONVOY, T1, mention="relevé de lancement absent")
        self.assert_refused_and_nothing_written(
            "release-evaluation", CONVOY, T1, "--state-file", "/state/unknown.json", mention="produit lancé inconnu")
        self.record_evaluation()

        self.ok("release-evaluation", CONVOY, T1, "--state-file", self.PRODUCT["state_file"])

        self.assertNotIn("live", self.evaluation())

    def test_release_evaluation_withdraws_the_open_evaluation_with_its_products_when_asked(self):
        self.opened_evaluation()
        self.ok("launch-evaluation", CONVOY, T1, "--bead", "fx-e1")
        content = self.states()

        self.ok("release-evaluation", CONVOY, T1, "--state-file", self.PRODUCT["state_file"], "--withdraw")

        evaluation = self.evaluation()
        self.assertEqual(([], False, False), (evaluation["rounds"], "request" in evaluation, "live" in evaluation))
        # What the session of the withdrawn evaluation hands in later is refused.
        self.assert_refused_and_nothing_written(
            "record-evaluation", CONVOY, T1, "--file", self.states_file(content), mention="aucune évaluation n'est demandée")

    def test_the_products_of_a_stopped_ticket_are_released_and_nothing_else_is_recorded_on_it(self):
        self.opened_evaluation()
        self.ok("stop-ticket", CONVOY, T1, "--reason", "evaluation_no_result", "--detail", "aucun état en 2 lancements")

        self.ok("release-evaluation", CONVOY, T1, "--state-file", self.PRODUCT["state_file"])

        self.assertNotIn("live", self.evaluation())
        self.assert_refused_and_nothing_written(
            "record-evaluation", CONVOY, T1, "--file", self.states_file(self.states()), mention="ticket arrêté")
        self.assertEqual("evaluation_no_result", self.ticket(self.show(), T1)["stop"]["reason"])

    def test_an_evaluation_written_outside_the_command_is_a_state_without_rule(self):
        self.finished_slice()
        self.edit_tracker(T1, **{"gc.flow.evaluation": json.dumps({"rounds": [{"verdict": "favorable"}]})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["evaluation"])
        self.assertEqual(["gc.flow.evaluation"], [entry["field"] for entry in ticket["unruled"]])

    def test_an_evaluation_on_an_unmarked_convoy_writes_nothing(self):
        before = self.tracker.read_text()
        request = self.json_file("evaluation-request.json", {"roles": self.ROLES, "environment": [self.PRODUCT]})
        for command in (
            ("open-evaluation", CONVOY, T1, "--commit", self.REVIEWED, "--file", request),
            ("launch-evaluation", CONVOY, T1, "--bead", "fx-e1"),
            ("record-evaluation", CONVOY, T1, "--file", request),
            ("record-startup", CONVOY, T1, "--commit", self.REVIEWED, "--detail", "x"),
            ("release-evaluation", CONVOY, T1, "--state-file", "/state/content.json"),
        ):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- T16: the fidelity result and the Planning Exceptions that name an anchor --

    FIDELITY = {
        "screens": ["accueil"],
        "states": {"empty": {"viewports": ["desktop"], "anchors": ["titre", "liste"]}},
        "deviations": [],
    }
    DEVIATION = {"state": "empty", "viewport": "desktop", "anchor": "liste", "kind": "absent", "property": "présence"}

    def fidelity_file(self, **changes):
        path = self.tmp / "fidelity.json"
        path.write_text(json.dumps({**self.FIDELITY, **changes}, ensure_ascii=False))
        return path

    def measured_slice(self):
        self.marked_slice()
        self.ok("add-evidence", CONVOY, T1, "--piece", "fidelity", "--digest", DIGEST, "--commit", self.HEAD)

    def set_fidelity(self, **changes):
        return self.ok("set-fidelity", CONVOY, T1, "--commit", self.HEAD, "--piece", "fidelity",
                       "--file", self.fidelity_file(**changes))

    def test_set_fidelity_records_a_green_result_and_its_verdict_at_the_commit(self):
        self.measured_slice()

        self.set_fidelity()

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        fidelity = ticket["fidelity"]
        self.assertEqual((self.HEAD, "favorable", "vert", "fidelity"),
                         (fidelity["commit"], fidelity["verdict"], fidelity["state"], fidelity["piece"]))
        self.assertEqual(self.FIDELITY["states"], fidelity["states"])
        self.assertEqual(("favorable", self.HEAD), (ticket["verdicts"]["fidelity"]["state"], ticket["verdicts"]["fidelity"]["commit"]))
        self.assertIsNone(self.ticket(self.show(expect=EXIT_UNRULED), T2)["fidelity"])

    def test_set_fidelity_with_a_deviation_is_red_and_names_it(self):
        self.measured_slice()

        self.set_fidelity(deviations=[self.DEVIATION])

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual(("unfavorable", "rouge"), (ticket["fidelity"]["verdict"], ticket["fidelity"]["state"]))
        self.assertEqual([{**self.DEVIATION, "status": "ouvert"}], ticket["fidelity"]["deviations"])
        self.assertEqual("unfavorable", ticket["verdicts"]["fidelity"]["state"])

    def test_set_fidelity_keeps_the_first_deviations_of_a_result_longer_than_one_command_line_argument(self):
        # af-m0hvif: 22,313 deviations on one ticket, a result no single
        # argument of a tracker write can carry (128 KiB on Linux).
        anchors = [f"ancre_{n:02}" for n in range(30)]
        deviations = [{"state": "empty", "viewport": "desktop", "anchor": anchors[n % 30], "kind": "style",
                       "property": f"propriété-{n}"} for n in range(3000)]
        deviations.append({"state": "empty", "viewport": None, "anchor": None, "kind": "token", "property": "--bg"})
        self.measured_slice()

        self.set_fidelity(states={"empty": {"viewports": ["desktop"], "anchors": anchors}}, deviations=deviations)

        fidelity = self.ticket(self.show(expect=EXIT_UNRULED), T1)["fidelity"]
        self.assertGreater(len(json.dumps(deviations)), 128 * 1024)
        self.assertEqual(("unfavorable", "rouge", 3001, [*anchors, None]),
                         (fidelity["verdict"], fidelity["state"], fidelity["deviation_count"],
                          fidelity["deviation_anchors"]))
        self.assertEqual([{**d, "status": "ouvert"} for d in deviations[:100]], fidelity["deviations"])

    def test_a_cut_fidelity_result_is_accepted_only_when_every_anchor_of_it_is(self):
        anchors = [f"ancre_{n:02}" for n in range(30)]
        # ancre_29 is named only past the first 100 deviations, the ones the ticket keeps.
        deviations = [{"state": "empty", "viewport": "desktop", "anchor": anchors[n % (29 if n < 100 else 30)],
                       "kind": "absent", "property": "présence"} for n in range(300)]
        self.measured_slice()
        self.set_fidelity(states={"empty": {"viewports": ["desktop"], "anchors": anchors}}, deviations=deviations)

        self.raise_exception(*anchors[:-1])
        self.answer("c")
        fidelity = self.ticket(self.show(expect=EXIT_UNRULED), T1)["fidelity"]
        self.assertEqual({"accepté par Benjamin"}, {d["status"] for d in fidelity["deviations"]})
        self.assertEqual("rouge", fidelity["state"])

        self.raise_exception(*anchors)
        self.answer("c", at="2099-01-02T00:00:00Z")
        self.assertEqual("accepté par Benjamin", self.ticket(self.show(expect=EXIT_UNRULED), T1)["fidelity"]["state"])

    def test_set_fidelity_refuses_a_result_that_code_did_not_measure(self):
        self.marked_slice()
        # No piece of the evidence store at that commit.
        self.assert_refused_and_nothing_written(
            "set-fidelity", CONVOY, T1, "--commit", self.HEAD, "--piece", "fidelity", "--file", self.fidelity_file(),
            mention="pièce")
        self.ok("add-evidence", CONVOY, T1, "--piece", "fidelity", "--digest", DIGEST, "--commit", self.HEAD)
        for changes, mention in (
            ({"verdict": "favorable"}, "verdict"),
            ({"states": {}}, "état"),
            ({"screens": []}, "écrans"),
            ({"states": {"empty": {"viewports": ["desktop"], "anchors": []}}}, "ancres"),
            ({"deviations": [{**self.DEVIATION, "kind": "goût"}]}, "genre d'écart"),
            ({"deviations": [{**self.DEVIATION, "state": "content"}]}, "état non comparé"),
            ({"deviations": [{**self.DEVIATION, "anchor": None}]}, "sans ancre"),
            ({"deviations": [{"state": "empty", "anchor": "liste"}]}, "écart mal formé"),
        ):
            with self.subTest(changes=changes):
                self.assert_refused_and_nothing_written(
                    "set-fidelity", CONVOY, T1, "--commit", self.HEAD, "--piece", "fidelity",
                    "--file", self.fidelity_file(**changes), mention=mention)
        self.assert_refused_and_nothing_written(
            "set-fidelity", CONVOY, T1, "--commit", ABSENT_COMMIT, "--piece", "fidelity", "--file", self.fidelity_file(),
            mention="commit")

    def raise_exception(self, *anchors, option="c", summary="La liste est livrée sans sa région"):
        args = [arg for anchor in anchors for arg in ("--anchor", anchor)]
        return self.ok("raise-planning-exception", CONVOY, T1, "--kind", "semantic", "--summary", summary,
                       *args, *(("--accept-option", option) if anchors else ()))

    def answer(self, option, at="2099-01-01T00:00:00Z"):
        """What bin/escalation-door repondre writes on the ticket."""
        self.edit_tracker(T1, **{"gc.needs_benjamin": "none", "gc.escalation_response_option": option,
                                 "gc.escalation_response_at": at})

    def test_planning_exception_naming_an_anchor_is_open_until_the_operator_answers(self):
        self.measured_slice()
        self.set_fidelity(deviations=[self.DEVIATION])

        self.raise_exception("liste")
        self.edit_tracker(T1, **{"gc.needs_benjamin": "Planning Exception (semantic) sur fx-t1 : …"})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        raised = ticket["planning_exceptions"]
        self.assertEqual([("semantic", ["liste"], "c", "open", False)],
                         [(e["kind"], e["anchors"], e["accept_option"], e["state"], e["accepted"]) for e in raised])
        self.assertEqual([], ticket["accepted_anchors"])
        self.assertEqual("rouge", ticket["fidelity"]["state"])

    def test_resolved_planning_exception_naming_the_anchor_turns_the_deviation_accepted(self):
        self.measured_slice()
        self.set_fidelity(deviations=[self.DEVIATION])
        self.raise_exception("liste")

        self.answer("c")

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual(["liste"], ticket["accepted_anchors"])
        self.assertEqual(("resolved", True), (ticket["planning_exceptions"][0]["state"], ticket["planning_exceptions"][0]["accepted"]))
        fidelity = ticket["fidelity"]
        self.assertEqual("accepté par Benjamin", fidelity["state"])
        self.assertEqual(["accepté par Benjamin"], [d["status"] for d in fidelity["deviations"]])
        # Nothing rewrote the verdict: the deviation is still one.
        self.assertEqual("unfavorable", fidelity["verdict"])
        self.assertEqual("unfavorable", ticket["verdicts"]["fidelity"]["state"])

    def test_only_the_accepting_answer_on_the_named_anchor_accepts_a_deviation(self):
        self.measured_slice()
        other = {**self.DEVIATION, "anchor": "titre", "kind": "style", "property": "color"}
        self.set_fidelity(deviations=[self.DEVIATION, other])
        self.raise_exception("liste")

        # Answered by another option than the one that accepts.
        self.answer("a")
        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual(("resolved", False), (ticket["planning_exceptions"][0]["state"], ticket["planning_exceptions"][0]["accepted"]))
        self.assertEqual("rouge", ticket["fidelity"]["state"])

        # Accepted, on one of the two anchors that deviate: still red.
        self.answer("c", at="2099-01-02T00:00:00Z")
        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("rouge", ticket["fidelity"]["state"])
        self.assertEqual({"liste": "accepté par Benjamin", "titre": "ouvert"},
                         {d["anchor"]: d["status"] for d in ticket["fidelity"]["deviations"]})

    def test_planning_exception_naming_no_anchor_is_accepted_by_its_accepting_answer(self):
        # ADR-0030 L5: every Planning Exception has an accept path.
        self.measured_slice()
        self.ok("raise-planning-exception", CONVOY, T1, "--kind", "semantic", "--summary", "Question sur l'ordre",
                "--accept-option", "c")

        self.answer("c")

        ticket = self.ticket(self.show(), T1)
        self.assertEqual([([], "c", "resolved", True)],
                         [(e["anchors"], e["accept_option"], e["state"], e["accepted"])
                          for e in ticket["planning_exceptions"]])
        self.assertEqual([], ticket["accepted_anchors"])

    def test_an_answer_given_before_the_exception_was_raised_resolves_nothing(self):
        self.measured_slice()
        self.set_fidelity(deviations=[self.DEVIATION])
        self.answer("c")

        self.raise_exception("liste")

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual("open", ticket["planning_exceptions"][0]["state"])
        self.assertEqual("rouge", ticket["fidelity"]["state"])

    def test_a_later_planning_exception_keeps_the_answer_given_to_the_previous_one(self):
        self.measured_slice()
        self.set_fidelity(deviations=[self.DEVIATION])
        self.raise_exception("liste")
        self.answer("c")

        self.raise_exception(summary="Le ticket recouvre un autre ticket")
        self.edit_tracker(T1, **{"gc.needs_benjamin": "Planning Exception (semantic) sur fx-t1 : …"})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)
        self.assertEqual([("resolved", True), ("open", False)],
                         [(e["state"], e["accepted"]) for e in ticket["planning_exceptions"]])
        self.assertEqual(["liste"], ticket["accepted_anchors"])
        self.assertEqual("accepté par Benjamin", ticket["fidelity"]["state"])

    def test_raising_the_same_planning_exception_again_writes_nothing(self):
        self.measured_slice()
        self.raise_exception("liste")
        before = self.tracker.read_bytes()

        answer = self.raise_exception("liste")

        self.assertEqual({}, answer["written"])
        self.assertEqual(before, self.tracker.read_bytes())

    def test_raise_planning_exception_refuses_what_is_outside_its_lists(self):
        self.marked_slice()
        base = ("raise-planning-exception", CONVOY, T1)
        for args, mention in (
            (("--kind", "repair", "--summary", "x"), "genre de Planning Exception"),
            (("--kind", "semantic"), "résumé"),
            (("--kind", "semantic", "--summary", "x", "--anchor", "une ancre"), "ancre"),
            (("--kind", "semantic", "--summary", "x", "--anchor", "liste", "--anchor", "liste", "--accept-option", "c"), "deux fois"),
            (("--kind", "semantic", "--summary", "x", "--anchor", "liste"), "option"),
            (("--kind", "semantic", "--summary", "x", "--anchor", "liste", "--accept-option", "oui"), "option"),
        ):
            with self.subTest(args=args):
                self.assert_refused_and_nothing_written(*base, *args, mention=mention)

    def test_fidelity_or_planning_exception_written_outside_the_command_is_a_state_without_rule(self):
        self.marked_slice()
        self.edit_tracker(T1, **{
            "gc.flow.fidelity": json.dumps({"commit": self.HEAD, "verdict": "favorable", "piece": "fidelity",
                                            "screens": ["accueil"], "states": self.FIDELITY["states"],
                                            "deviations": [self.DEVIATION], "at": "x"}),
            "gc.flow.planning_exceptions": json.dumps({"entries": [{"kind": "semantic", "accepted": True}]})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["fidelity"])
        self.assertIn("unruled", ticket["planning_exceptions"])
        self.assertLessEqual({"gc.flow.fidelity", "gc.flow.planning_exceptions"},
                             {entry["field"] for entry in ticket["unruled"]})

    def test_fidelity_and_planning_exception_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (("set-fidelity", CONVOY, T1, "--commit", self.HEAD, "--piece", "fidelity", "--file", self.fidelity_file()),
                        ("raise-planning-exception", CONVOY, T1, "--kind", "semantic", "--summary", "x")):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())


    # --- the single correction round, a ticket still refused, the override (T17) ----

    NOT_OBSERVED = {"state": "not_observed", "reason": "le nombre n'est pas sur la page"}
    APPROVER = "benjamin-hurand"
    WORDS = "Je passe outre : ce constat ne vaut pas un arrêt."

    def evaluated(self, commit=None, **first_criterion):
        """A Ticket Evaluation recorded at `commit`: every state « observed »
        but what `first_criterion` says of the first criterion."""
        self.open_evaluation(commit=commit)
        content = self.states(commit=commit)
        content["criteria"][0].update(first_criterion)
        return self.record_evaluation(content)

    def refused_by_both(self):
        """A finished slice whose code review left the Blocking Finding F1.1
        and whose evaluation did not observe its first criterion, both at
        REVIEWED."""
        self.refused_review()
        self.evaluated(**self.NOT_OBSERVED)

    def correction(self, expect=0):
        return self.ticket(self.show(expect=expect), T1)["correction"]

    def still_refused(self):
        """A ticket refused by both, whose correction round is taken, and
        that code stopped because it is still refused."""
        self.refused_by_both()
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)
        self.ok("stop-ticket", CONVOY, T1, "--reason", "still_refused",
                "--detail", "encore refusé après son tour de correction : revue (F1.1) ; évaluation (critère 1)")

    def override(self, *args):
        return ("override-finding", CONVOY, T1, *args)

    def test_open_correction_records_what_both_refused_and_counts_among_the_resumes(self):
        self.refused_by_both()
        self.assertIsNone(self.correction())

        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        shown = self.ticket(self.show(), T1)
        correction = shown["correction"]
        self.assertEqual((self.REVIEWED, ["F1.1"], ["critère 1"], []),
                         tuple(correction[name] for name in ("commit", "blocking_findings", "not_observed", "launches")))
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, shown["counters"])

    def test_open_correction_takes_what_only_one_of_the_two_refused(self):
        self.refused_review()
        self.evaluated()

        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        correction = self.correction()
        self.assertEqual((["F1.1"], []), (correction["blocking_findings"], correction["not_observed"]))

    def test_open_correction_again_at_the_same_commit_writes_nothing_and_counts_nothing_more(self):
        self.refused_by_both()
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        again = self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        self.assertEqual({}, again["written"])
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.ticket(self.show(), T1)["counters"])

    def test_open_correction_refuses_while_the_code_review_or_the_evaluation_has_not_answered(self):
        self.refused_review()
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="Ticket Evaluation")
        self.open_evaluation()
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="Ticket Evaluation")

    def test_open_correction_refuses_an_evaluation_refused_while_the_code_review_is_still_open(self):
        self.finished_slice()
        self.evaluated(**self.NOT_OBSERVED)
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="revue de code")
        self.open_code_review()
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="revue de code")

    def test_open_correction_refuses_a_ticket_nothing_refused_or_another_commit_than_the_judged_one(self):
        self.finished_slice()
        self.open_code_review()
        self.record_code_review()
        self.evaluated()
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="rien à corriger")
        self.assert_refused_and_nothing_written("open-correction", CONVOY, T1, "--commit", "HEAD", mention="commit")
        self.assert_refused_and_nothing_written("open-correction", CONVOY, T1, mention="commit")

    def test_a_second_correction_round_is_refused(self):
        self.refused_by_both()
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.CORRECTED, mention="un seul tour de correction")

    def test_open_correction_is_refused_on_a_stopped_or_a_parked_ticket(self):
        self.refused_by_both()
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "un secret manque")
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="parqué")
        self.edit_tracker(T1, **{"gc.flow.stop": json.dumps(
            {"reason": "code_review_no_result", "detail": "aucun verdict", "at": "2026-10-07T00:00:00Z"})})
        self.assert_refused_and_nothing_written(
            "open-correction", CONVOY, T1, "--commit", self.REVIEWED, mention="arrêté")

    def test_launch_correction_records_the_single_author_session_and_refuses_a_second(self):
        self.refused_by_both()
        self.assert_refused_and_nothing_written("launch-correction", CONVOY, T1, "--bead", "fx-c1", mention="aucun tour")
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)
        self.assert_refused_and_nothing_written("launch-correction", CONVOY, T1, mention="bead")

        self.ok("launch-correction", CONVOY, T1, "--bead", "fx-c1")

        self.assertEqual(["fx-c1"], [launch["bead"] for launch in self.correction()["launches"]])
        self.assert_refused_and_nothing_written(
            "launch-correction", CONVOY, T1, "--bead", "fx-c2", mention="une seule session")

    def test_a_ticket_still_refused_after_its_correction_round_is_stopped_for_that_reason(self):
        self.still_refused()

        stop = self.ticket(self.show(), T1)["stop"]
        self.assertEqual("still_refused", stop["reason"])
        self.assertIn("F1.1", stop["detail"])

    def test_a_commit_of_the_correction_round_invalidates_the_verdicts_without_a_second_resume(self):
        self.refused_by_both()
        self.ok("open-correction", CONVOY, T1, "--commit", self.REVIEWED)

        answer = self.ok("invalidate-verdicts", CONVOY, T1, "--tip", self.CORRECTED,
                         "--kind", "code_review", "--kind", "evaluation")

        self.assertEqual(["code_review", "evaluation"], answer["invalidated"])
        shown = self.ticket(self.show(), T1)
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, shown["counters"])
        self.assertIn("invalidated", shown["verdicts"]["code_review"])

    def test_an_override_of_a_blocking_finding_is_read_back_as_a_recorded_override(self):
        self.still_refused()
        self.assertEqual([], self.ticket(self.show(), T1)["overrides"])

        self.ok(*self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", self.WORDS))

        (override,) = self.ticket(self.show(), T1)["overrides"]
        self.assertEqual(("F1.1", self.APPROVER, self.WORDS, self.REVIEWED, "dérogation enregistrée"),
                         tuple(override[name] for name in ("finding", "approver", "words", "commit", "state")))
        # The finding keeps its unfavorable verdict: the override is read beside it.
        self.assertEqual(["F1.1"], self.code_review()["state"]["unsettled"])

    def test_the_same_override_again_writes_nothing_and_other_words_are_refused(self):
        self.still_refused()
        given = self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", self.WORDS)
        self.ok(*given)

        self.assertEqual({}, self.ok(*given)["written"])
        self.assert_refused_and_nothing_written(
            *self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", "Autres mots."),
            mention="déjà")

    def test_an_override_is_refused_without_words_or_without_its_approver(self):
        self.still_refused()
        for words in ("", "   ", "\n"):
            self.assert_refused_and_nothing_written(
                *self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", words), mention="mots")
        self.assert_refused_and_nothing_written(
            *self.override("--finding", "F1.1", "--approver", self.APPROVER), mention="mots")
        self.assert_refused_and_nothing_written(
            *self.override("--finding", "F1.1", "--words", self.WORDS), mention="approbateur")

    def test_an_override_is_refused_on_a_ticket_that_is_not_stopped(self):
        self.refused_by_both()
        self.assert_refused_and_nothing_written(
            *self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", self.WORDS),
            mention="n'est pas arrêté")

    def test_an_override_is_refused_for_what_is_not_a_blocking_finding_left_without_favorable_verdict(self):
        self.still_refused()
        self.assert_refused_and_nothing_written(
            *self.override("--finding", "F9.9", "--approver", self.APPROVER, "--words", self.WORDS),
            mention="Blocking Finding")
        self.assert_refused_and_nothing_written(
            *self.override("--approver", self.APPROVER, "--words", self.WORDS), mention="Blocking Finding")

    def test_an_override_of_a_criterion_that_was_not_observed_is_refused_towards_the_planning_exception(self):
        self.still_refused()
        for named in ("critère 1", "1", "ligne de démonstration"):
            self.assert_refused_and_nothing_written(
                *self.override("--finding", named, "--approver", self.APPROVER, "--words", self.WORDS),
                mention="Planning Exception")

    def test_a_correction_or_an_override_written_outside_the_command_is_a_state_without_rule(self):
        self.refused_by_both()
        self.edit_tracker(T1, **{"gc.flow.correction": json.dumps({"commit": self.REVIEWED}),
                                 "gc.flow.overrides": json.dumps({"entries": [{"finding": "F1.1"}]})})

        shown = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", shown["correction"])
        self.assertIn("unruled", shown["overrides"])
        self.assertEqual({"gc.flow.correction", "gc.flow.overrides"}, {entry["field"] for entry in shown["unruled"]})

    def test_a_correction_and_an_override_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (
            ("open-correction", CONVOY, T1, "--commit", ABSENT_COMMIT),
            ("launch-correction", CONVOY, T1, "--bead", "fx-c1"),
            self.override("--finding", "F1.1", "--approver", self.APPROVER, "--words", self.WORDS),
        ):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- T19: the criteria frozen with the approved graph ------------------------

    APPROVED_CRITERIA = "## Acceptance criteria\n\n- [ ] Point d'entrée : GET / — Observable : liste — Faux si : une ligne manque"
    GRAPH_ONE, GRAPH_TWO = "sha256:" + "11" * 32, "sha256:" + "22" * 32

    def describe(self, ticket_id, description, **metadata):
        """What the publication door writes of a ticket: its description
        and the digest of the approved graph it is published under."""
        state = self.tracker_state()
        state["beads"][ticket_id]["description"] = description
        state["beads"][ticket_id].setdefault("metadata", {}).update(metadata)
        self.tracker.write_text(json.dumps(state))

    def frozen(self, ticket_id=T1):
        return self.ticket(self.show(), ticket_id)["criteria_frozen"]

    def test_mark_freezes_the_fingerprint_of_the_criteria_with_the_digest_of_the_approved_graph(self):
        self.init_repo()
        self.describe(T1, self.APPROVED_CRITERIA, **{"gc.graph_digest": self.GRAPH_ONE})

        self.ok("mark", CONVOY)

        frozen = self.frozen()
        self.assertRegex(frozen["digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual((self.GRAPH_ONE, frozen["digest"], self.GRAPH_ONE, True),
                         tuple(frozen[name] for name in ("graph_digest", "current", "current_graph_digest", "identical")))
        # A ticket the door published under no digest is frozen all the same.
        self.assertEqual((None, True), (self.frozen(T2)["graph_digest"], self.frozen(T2)["identical"]))

    def test_a_criterion_edited_on_the_ticket_is_no_longer_the_frozen_one_and_a_new_mark_does_not_refreeze_it(self):
        self.init_repo()
        self.describe(T1, self.APPROVED_CRITERIA, **{"gc.graph_digest": self.GRAPH_ONE})
        self.ok("mark", CONVOY)
        approved = self.frozen()["digest"]

        self.describe(T1, self.APPROVED_CRITERIA + " ou deux")
        self.ok("mark", CONVOY)

        frozen = self.frozen()
        self.assertEqual(approved, frozen["digest"])
        self.assertNotEqual(approved, frozen["current"])
        self.assertFalse(frozen["identical"])

    def test_a_ticket_published_again_under_another_approved_digest_is_frozen_again_by_the_mark(self):
        self.init_repo()
        self.describe(T1, self.APPROVED_CRITERIA, **{"gc.graph_digest": self.GRAPH_ONE})
        self.ok("mark", CONVOY)
        approved = self.frozen()["digest"]

        # A patch of the graph: the door rewrites the ticket under the new digest.
        self.describe(T1, self.APPROVED_CRITERIA + " ou deux", **{"gc.graph_digest": self.GRAPH_TWO})
        self.assertFalse(self.frozen()["identical"])
        self.ok("mark", CONVOY)

        frozen = self.frozen()
        self.assertNotEqual(approved, frozen["digest"])
        self.assertEqual((self.GRAPH_TWO, True), (frozen["graph_digest"], frozen["identical"]))

    def test_the_criteria_of_a_closed_ticket_are_never_frozen_again(self):
        tip = self.started_ticket()
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)
        before = self.tracker_state()["beads"][T1]["metadata"]["gc.flow.criteria"]

        self.describe(T1, self.APPROVED_CRITERIA, **{"gc.graph_digest": self.GRAPH_TWO})
        self.ok("mark", CONVOY)

        self.assertEqual(before, self.tracker_state()["beads"][T1]["metadata"]["gc.flow.criteria"])

    def test_a_frozen_fingerprint_written_outside_the_command_is_a_state_without_rule(self):
        self.started_ticket()
        self.edit_tracker(T1, **{"gc.flow.criteria": json.dumps({"digest": "à la main"})})

        shown = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", shown["criteria_frozen"])
        self.assertEqual(["gc.flow.criteria"], [entry["field"] for entry in shown["unruled"]])
        self.assert_refused_and_nothing_written("mark", CONVOY, mention="gc.flow.criteria")

    # --- T19: the reference of the Validated Prototype of an interface ticket -----

    def prototype_section(self, **fields):
        lines = {"branche": "prototype/fx", "commit": "ab" * 20, "chemin": "prototype/", "états": "empty, content",
                 **fields}
        return "## Validated Prototype\n\n" + "\n".join(
            f"- {name} : {value}" for name, value in lines.items() if value is not None) + "\n- Prototype Fold : ce ticket"

    def test_show_renders_the_reference_of_the_validated_prototype_of_an_interface_ticket(self):
        self.started_ticket()
        self.describe(T1, self.APPROVED_CRITERIA + "\n\n" + self.prototype_section() + "\n\n## Target rigs\n\nfx-rig")

        shown = self.show()

        ticket = self.ticket(shown, T1)
        self.assertTrue(ticket["interface"])
        self.assertEqual({"branch": "prototype/fx", "commit": "ab" * 20, "path": "prototype", "states": ["empty", "content"]},
                         ticket["validated_prototype"])
        # A ticket without the section touches no screen.
        other = self.ticket(shown, T2)
        self.assertEqual((False, None), (other["interface"], other["validated_prototype"]))

    def test_a_reference_of_the_validated_prototype_that_is_incomplete_is_a_state_without_rule(self):
        self.started_ticket()
        for broken, mention in (({"commit": None}, "commit"), ({"commit": "pas-un-sha"}, "commit"),
                                ({"états": " , "}, "état")):
            with self.subTest(broken=broken):
                self.describe(T1, self.prototype_section(**broken))

                ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

                self.assertIn(mention, ticket["validated_prototype"]["unruled"])
                self.assertEqual(["description"], [entry["field"] for entry in ticket["unruled"]])

    # --- T19: the ticket-end gate closes a ticket -------------------------------------

    def gate_report(self, **changes):
        report = json.loads(GATE_REPORT.read_text())
        report.update(changes)
        path = self.tmp / "gate-report.json"
        path.write_text(json.dumps(report, ensure_ascii=False))
        return path

    def test_close_ticket_writes_the_record_of_the_gate_and_the_closed_status_in_one_tracker_write(self):
        tip = self.started_ticket()
        self.write_log.write_text("")

        answer = self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)

        self.assertTrue(answer["closed"])
        writes = [line for line in self.write_log.read_text().splitlines() if line.strip()]
        self.assertEqual(1, len(writes), writes)
        ticket = self.ticket(self.show(), T1)
        record = ticket["gates"]["ticket_end"]
        self.assertEqual(("closed", tip, "ticket-end/v1", list(range(1, 10))),
                         (ticket["status"], record["commit"], record["version"],
                          [entry["number"] for entry in record["conditions"]]))
        self.assertEqual({"pass"}, {entry["verdict"] for entry in record["conditions"]})
        self.assertEqual([], ticket["unruled"])

    def test_close_ticket_refuses_a_record_that_is_not_the_nine_passing_verdicts_of_the_known_version(self):
        tip = self.started_ticket()
        conditions = json.loads(GATE_REPORT.read_text())["conditions"]
        failing = [dict(entry, verdict="fail") if entry["number"] == 6 else entry for entry in conditions]
        renamed = [dict(entry, name="autre") if entry["number"] == 2 else entry for entry in conditions]
        silent = [dict(entry, detail=" ") if entry["number"] == 9 else entry for entry in conditions]
        for changes, mention in (
            ({"version": "ticket-end/v0"}, "version"),
            ({"conditions": conditions[:8]}, "neuf"),
            ({"conditions": failing}, "condition 6"),
            ({"conditions": renamed}, "condition 2"),
            ({"conditions": silent}, "condition 9"),
            ({"closed_by": "auteur"}, "closed_by"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(
                    "close-ticket", CONVOY, T1, "--commit", tip, "--file", self.gate_report(**changes), mention=mention)
        self.assert_refused_and_nothing_written(
            "close-ticket", CONVOY, T1, "--commit", tip, "--file", self.tmp / "absent.json", mention="relevé")
        self.assert_refused_and_nothing_written(
            "close-ticket", CONVOY, T1, "--commit", "pas-un-sha", "--file", GATE_REPORT, mention="commit")
        self.assertEqual("in_progress", self.ticket(self.show(), T1)["status"])

    def test_close_ticket_refuses_a_ticket_already_closed_or_withdrawn(self):
        tip = self.started_ticket()
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)

        self.assert_refused_and_nothing_written(
            "close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT, mention="déjà fermé")

        self.ok("record-gate", CONVOY, T2, "--gate", "withdrawn")
        self.assert_refused_and_nothing_written(
            "close-ticket", CONVOY, T2, "--commit", tip, "--file", GATE_REPORT, mention="relevé de fermeture")

    def test_a_ticket_end_record_without_its_nine_verdicts_is_a_state_without_rule(self):
        tip = self.started_ticket()
        self.edit_tracker(T1, status="closed", **{"gc.flow.gate.ticket_end": json.dumps({"at": "2026-01-01T00:00:00Z",
                                                                                           "commit": tip})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("gc.flow.gate.ticket_end", [entry["field"] for entry in ticket["unruled"]])

    def test_close_ticket_on_an_unmarked_convoy_writes_nothing(self):
        before = self.tracker.read_text()

        proc = self.run_tool("close-ticket", CONVOY, T1, "--commit", ABSENT_COMMIT, "--file", GATE_REPORT)

        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_text())

    # --- resumes counted and bounded, a parking lifted, one grouped request (T20) ---

    def interrupted_ticket(self, session="auteur-1"):
        """A started ticket whose author session declared an interruption."""
        self.seed_chain()
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.ok("set-session", CONVOY, T1, "--session", session)
        self.ok("set-exit", CONVOY, T1, "--exit", "interrupted")

    def resumes(self, ticket_id=T1):
        return self.ticket(self.show(), ticket_id)["counters"]["resumes"]

    def test_open_resume_counts_one_resume_records_it_and_clears_the_exit_it_replaces(self):
        self.interrupted_ticket()

        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")

        ticket = self.ticket(self.show(), T1)
        self.assertEqual(1, ticket["counters"]["resumes"])
        self.assertEqual(0, ticket["counters"]["correction_rounds"])
        self.assertIsNone(ticket["exit"])
        self.assertEqual(2, ticket["resumes_left"])
        [entry] = ticket["resume"]["entries"]
        self.assertEqual(("interrupted", "session:auteur-1", "auteur-1", "interrupted", []),
                         (entry["cause"], entry["ref"], entry["session"], entry["exit"]["exit"], entry["launches"]))

    def test_open_resume_again_for_the_same_fact_counts_nothing_more(self):
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")
        before = self.tracker.read_text()

        answer = self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")

        self.assertEqual({}, answer["written"])
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual(1, self.resumes())

    def test_each_cause_of_resume_is_bounded_on_its_own_and_all_add_to_the_counter(self):
        # ADR-0030 L2: three different causes are not three of the same.
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")
        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:1")
        self.ok("open-resume", CONVOY, T1, "--cause", "unblocked", "--ref", "exit:2")

        ticket = self.ticket(self.show(), T1)

        self.assertEqual(3, ticket["counters"]["resumes"])
        self.assertEqual(2, ticket["resumes_left"])
        self.assertEqual({"interrupted": 2, "returned": 2, "unblocked": 2, "answered": 3, "behind": 3,
                          "evaluation_no_result": 3, "stage_removed": 3, "code_review_no_result": 3,
                          "commit_after_verdict": 3},
                         ticket["resumes_left_by_cause"])
        self.assertEqual(["interrupted", "returned", "unblocked"], [e["cause"] for e in ticket["resume"]["entries"]])

    def test_an_interruption_a_correction_round_and_a_red_merge_do_not_park_the_ticket(self):
        # The af-ltchro case: interrupted, corrected, returned by a red merge.
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:1")

        ticket = self.ticket(self.show(), T1)

        self.assertEqual((3, 2), (ticket["counters"]["resumes"], ticket["resumes_left"]))
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "x", mention="reprises")
        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:2")

    def test_the_same_cause_at_its_bound_exhausts_the_ticket_whatever_the_others(self):
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:1")
        for ref in ("a", "b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)

        ticket = self.ticket(self.show(), T1)

        self.assertEqual((0, 0, 2), (ticket["resumes_left"], ticket["resumes_left_by_cause"]["interrupted"],
                                     ticket["resumes_left_by_cause"]["returned"]))
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:2", mention="cause interrupted")
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 reprises interrupted")

    def test_commits_after_a_verdict_are_a_cause_of_their_own(self):
        # Counted without an entry: what the counter holds beyond the
        # entries and the correction round.
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "a")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        for _ in range(2):
            self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.assertEqual(1, self.ticket(self.show(), T1)["resumes_left_by_cause"]["commit_after_verdict"])
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")

        ticket = self.ticket(self.show(), T1)

        self.assertEqual((0, 2), (ticket["resumes_left"], ticket["resumes_left_by_cause"]["interrupted"]))
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 commits après verdict")

    def test_the_commit_of_a_returned_ticket_resumed_by_code_invalidates_its_verdicts_without_a_second_resume(self):
        judged, base = self.integrated()
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.edit_tracker(T1, status="in_progress")
        for kind in ("code_review", "evaluation"):
            self.ok("set-verdict", CONVOY, T1, "--kind", kind, "--state", "favorable", "--commit", judged)
        self.ok("set-merge", CONVOY, T1, "--outcome", "conflict", "--ticket-commit", judged, "--integration", base)
        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:1")
        tip = self.commit_on("ticket/t1")

        answer = self.ok("invalidate-verdicts", CONVOY, T1, "--tip", tip, "--kind", "code_review", "--kind", "evaluation")

        self.assertEqual(["code_review", "evaluation"], answer["invalidated"])
        self.assertEqual(1, self.resumes())

    def test_a_commit_on_a_returned_ticket_no_resume_was_opened_for_still_counts_one_resume(self):
        judged, base = self.integrated()
        self.ok("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.edit_tracker(T1, status="in_progress")
        self.ok("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", judged)
        self.ok("set-merge", CONVOY, T1, "--outcome", "red", "--ticket-commit", judged, "--integration", base,
                "--commit", ABSENT_COMMIT)

        self.ok("invalidate-verdicts", CONVOY, T1, "--tip", self.commit_on("ticket/t1"), "--kind", "code_review")

        self.assertEqual(1, self.resumes())

    def test_open_resume_refuses_what_is_not_a_resume_and_writes_nothing(self):
        self.interrupted_ticket()
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "fatigue", "--ref", "x", mention="cause de reprise")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "interrupted", mention="repère de la reprise")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T2, "--cause", "interrupted", "--ref", "x", mention="porte de dispatch")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, "fx-absent", "--cause", "interrupted", "--ref", "x", mention="n'appartient pas")

    def test_open_resume_refuses_a_stopped_a_parked_a_closed_or_an_exhausted_ticket(self):
        self.interrupted_ticket()
        self.ok("record-gate", CONVOY, "fx-t4", "--gate", "dispatch")
        self.ok("stop-ticket", CONVOY, "fx-t4", "--reason", "still_refused", "--detail", "encore refusé")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, "fx-t4", "--cause", "interrupted", "--ref", "x", mention="arrêté")
        for ref in ("a", "b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "d", mention="reprises épuisées")
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 reprises")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "d", mention="parqué")

    def test_open_resume_lifts_a_stop_without_evaluation_result_only_and_keeps_it(self):
        self.interrupted_ticket()
        cause = "evaluation_no_result"
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", cause, "--ref", "x", mention="pas arrêté")
        self.ok("record-gate", CONVOY, "fx-t4", "--gate", "dispatch")
        self.ok("stop-ticket", CONVOY, "fx-t4", "--reason", "still_refused", "--detail", "encore refusé")
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, "fx-t4", "--cause", cause, "--ref", "x", mention="arrêté (still_refused)")
        self.ok("stop-ticket", CONVOY, T1, "--reason", cause, "--detail", "aucun état en 2 lancements")

        self.ok("open-resume", CONVOY, T1, "--cause", cause, "--ref", "integration:abc/stop:1")

        shown = self.ticket(self.show(), T1)
        self.assertEqual((None, 1), (shown["stop"], shown["counters"]["resumes"]))
        self.assertEqual((cause, "aucun état en 2 lancements"),
                         (shown["resume"]["entries"][-1]["stop"]["reason"], shown["resume"]["entries"][-1]["stop"]["detail"]))

    def test_launch_resume_records_the_one_session_a_resume_is_sent_to(self):
        self.interrupted_ticket()
        self.assert_refused_and_nothing_written("launch-resume", CONVOY, T1, "--bead", "fx-new1", mention="aucune reprise")
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "session:auteur-1")

        self.ok("launch-resume", CONVOY, T1, "--bead", "fx-new1")

        [entry] = self.ticket(self.show(), T1)["resume"]["entries"]
        self.assertEqual(["fx-new1"], [launch["bead"] for launch in entry["launches"]])
        self.assertEqual(1, self.resumes())
        self.assert_refused_and_nothing_written("launch-resume", CONVOY, T1, "--bead", "fx-new2", mention="déjà")
        self.assert_refused_and_nothing_written("launch-resume", CONVOY, T1, "--bead", "pas un bead", mention="bead")

    def test_a_ticket_is_parked_for_exhausted_resumes_only_once_they_are(self):
        self.interrupted_ticket()
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "a")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "x", mention="reprises")
        for ref in ("b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)

        answer = self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 reprises")

        self.assertEqual([T1, T2, "fx-t3"], answer["parked"])
        shown = self.show()
        self.assertEqual(("resumes_exhausted", T1), tuple(self.ticket(shown, "fx-t3")["park"][k] for k in ("cause", "origin")))
        self.assertIsNone(self.ticket(shown, "fx-t4")["park"])

    def test_lift_park_unparks_the_ticket_and_those_it_parked_and_keeps_the_record(self):
        self.seed_chain()
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès à l'horloge")
        self.ok("park", CONVOY, "fx-t4", "--cause", "operator_request", "--detail", "Autre accès")

        answer = self.ok("lift-park", CONVOY, T1, "--request", T1, "--option", "a")

        self.assertEqual([T1, T2, "fx-t3"], answer["lifted"])
        shown = self.show()
        for ticket_id in (T1, T2, "fx-t3"):
            self.assertIsNone(self.ticket(shown, ticket_id)["park"], ticket_id)
        self.assertEqual("operator_request", self.ticket(shown, "fx-t4")["park"]["cause"])
        [lift] = self.ticket(shown, T1)["park_lifts"]
        self.assertEqual(("operator_request", "Accès à l'horloge", T1, "a"),
                         (lift["cause"], lift["detail"], lift["request"], lift["option"]))
        self.assertEqual([], self.ticket(shown, T2)["park_lifts"])

    def test_lifting_an_exhausted_ticket_gives_it_its_resumes_back_without_erasing_the_count(self):
        self.interrupted_ticket()
        for ref in ("a", "b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 reprises")

        self.ok("lift-park", CONVOY, T1, "--request", "fx-new1", "--option", "a")

        ticket = self.ticket(self.show(), T1)
        self.assertEqual(3, ticket["counters"]["resumes"])
        self.assertEqual(3, ticket["resumes_left"])
        self.assertEqual({3}, set(ticket["resumes_left_by_cause"].values()))
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "d")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        ticket = self.ticket(self.show(), T1)
        self.assertEqual((2, 2, 2), (ticket["resumes_left"], ticket["resumes_left_by_cause"]["interrupted"],
                                     ticket["resumes_left_by_cause"]["commit_after_verdict"]))

    def test_a_lift_recorded_before_the_bounds_per_cause_still_gives_the_resumes_back(self):
        # A lift written before ADR-0030 L2 carries no per-cause count: what
        # was taken before it is read from the entries older than the lift.
        self.interrupted_ticket()
        for ref in ("a", "b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 reprises")
        self.ok("lift-park", CONVOY, T1, "--request", "fx-new1", "--option", "a")
        metadata = self.tracker_state()["beads"][T1]["metadata"]
        resume = json.loads(metadata["gc.flow.resume"])
        for entry in resume["entries"]:
            entry["at"] = "2000-01-01T00:00:00Z"
        lifts = json.loads(metadata["gc.flow.park_lifts"])
        for lift in lifts["entries"]:
            lift.pop("taken")
        self.edit_tracker(T1, **{"gc.flow.resume": json.dumps(resume), "gc.flow.park_lifts": json.dumps(lifts)})

        self.assertEqual(3, self.ticket(self.show(), T1)["resumes_left"])
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "d")
        self.assertEqual(2, self.ticket(self.show(), T1)["resumes_left"])

    def test_an_old_lift_takes_out_only_the_correction_round_recorded_before_it(self):
        # Three commits after a verdict exhausted the ticket; the lift, written
        # before ADR-0030 L2, carries no per-cause count; the correction round
        # came after it and takes nothing back from what was taken before.
        self.interrupted_ticket()
        for _ in range(3):
            self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "3 commits après verdict")
        self.ok("lift-park", CONVOY, T1, "--request", "fx-new1", "--option", "a")
        metadata = self.tracker_state()["beads"][T1]["metadata"]
        lifts = json.loads(metadata["gc.flow.park_lifts"])
        for lift in lifts["entries"]:
            lift.pop("taken")
        correction = {"commit": "c" * 40, "blocking_findings": ["F1.1"], "not_observed": [], "launches": [],
                      "at": "2999-01-01T00:00:00Z"}
        self.edit_tracker(T1, **{"gc.flow.park_lifts": json.dumps(lifts), "gc.flow.correction": json.dumps(correction)})
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")

        ticket = self.ticket(self.show(), T1)

        self.assertEqual((3, 3), (ticket["resumes_left"], ticket["resumes_left_by_cause"]["commit_after_verdict"]))

    def test_a_ticket_that_still_waits_for_another_parked_one_stays_parked_behind_it(self):
        self.seed(tickets=(T1, T2, "fx-t3"))
        state = self.tracker_state()
        state["beads"]["fx-t3"]["blocks"] = [T1, T2]
        self.tracker.write_text(json.dumps(state))
        self.ok("mark", CONVOY)
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès")
        self.ok("park", CONVOY, T2, "--cause", "planning_exception", "--detail", "Question")

        answer = self.ok("lift-park", CONVOY, T1, "--request", T1)

        self.assertEqual([T1], answer["lifted"])
        park = self.ticket(self.show(), "fx-t3")["park"]
        self.assertEqual(("planning_exception", T2), (park["cause"], park["origin"]))

    def test_lift_park_refuses_a_ticket_that_parked_nothing_and_writes_nothing(self):
        self.seed_chain()
        self.assert_refused_and_nothing_written("lift-park", CONVOY, T1, "--request", T1, mention="n'est pas parqué")
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès")
        self.assert_refused_and_nothing_written("lift-park", CONVOY, T2, "--request", T2, mention="parqué par")
        self.assert_refused_and_nothing_written("lift-park", CONVOY, T1, mention="demande")
        self.assert_refused_and_nothing_written("lift-park", CONVOY, T1, "--request", T1, "--option", "ab", mention="option")

    def test_show_renders_the_answer_given_to_the_request_of_a_parked_ticket(self):
        self.seed_chain()
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès")
        self.assertIsNone(self.ticket(self.show(), T1)["park"]["answer"])
        # What bin/escalation-door repondre writes on the ticket.
        self.edit_tracker(T1, **{"gc.needs_benjamin": "none", "gc.escalation_response_option": "b",
                                 "gc.escalation_response_at": "2999-01-01T00:00:00Z"})

        shown = self.show()

        self.assertEqual({"option": "b", "at": "2999-01-01T00:00:00Z"}, self.ticket(shown, T1)["park"]["answer"])
        # The answer is the one of the ticket that was asked, not of those behind it.
        self.assertIsNone(self.ticket(shown, T2)["park"]["answer"])

    def test_an_answer_older_than_the_parking_or_a_request_still_open_is_no_answer(self):
        self.seed_chain()
        self.ok("park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès")
        self.edit_tracker(T1, **{"gc.needs_benjamin": "none", "gc.escalation_response_option": "b",
                                 "gc.escalation_response_at": "2000-01-01T00:00:00Z"})
        self.assertIsNone(self.ticket(self.show(), T1)["park"]["answer"])
        self.edit_tracker(T1, **{"gc.needs_benjamin": "Accès", "gc.escalation_response_at": "2999-01-01T00:00:00Z"})
        self.assertIsNone(self.ticket(self.show(), T1)["park"]["answer"])

    def test_the_grouped_request_of_a_convoy_is_recorded_read_back_and_cleared(self):
        self.ok("mark", CONVOY)
        self.assertIsNone(self.show()["convoy"]["grouped_request"])

        self.ok("record-grouped-request", CONVOY, "--bead", "fx-new1", "--signature", DIGEST, "--lift-option", "a",
                "--lifts", T1)

        record = self.show()["convoy"]["grouped_request"]
        self.assertEqual(("fx-new1", DIGEST, "a", [T1]),
                         (record["bead"], record["signature"], record["lift_option"], record["lifts"]))
        self.ok("clear-grouped-request", CONVOY)
        self.assertIsNone(self.show()["convoy"]["grouped_request"])

    def test_record_grouped_request_refuses_a_malformed_record_and_writes_nothing(self):
        self.ok("mark", CONVOY)
        self.assert_refused_and_nothing_written("record-grouped-request", CONVOY, "--bead", "pas un bead", mention="bead")
        self.assert_refused_and_nothing_written(
            "record-grouped-request", CONVOY, "--bead", "fx-new1", "--signature", "abc", mention="digest")
        self.assert_refused_and_nothing_written(
            "record-grouped-request", CONVOY, "--bead", "fx-new1", "--lifts", T1, mention="option")

    def test_a_resume_a_lift_or_a_grouped_request_written_outside_the_command_is_a_state_without_rule(self):
        self.ok("mark", CONVOY)
        self.edit_tracker(T1, **{"gc.flow.resume": json.dumps({"entries": [{"cause": "fatigue"}]}),
                                 "gc.flow.park_lifts": "x"})
        self.edit_tracker(CONVOY, **{"gc.flow.grouped_request": json.dumps({"bead": "pas un bead", "at": "x"})})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertEqual({"gc.flow.resume", "gc.flow.park_lifts"},
                         {entry["field"] for entry in self.ticket(shown, T1)["unruled"]})
        self.assertEqual(["gc.flow.grouped_request"], [entry["field"] for entry in shown["convoy"]["unruled"]])

    def test_resume_lift_and_grouped_request_on_an_unmarked_convoy_write_nothing(self):
        before = self.tracker.read_text()
        for command in (("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "x"),
                        ("launch-resume", CONVOY, T1, "--bead", "fx-new1"),
                        ("lift-park", CONVOY, T1, "--request", T1),
                        ("record-grouped-request", CONVOY, "--bead", "fx-new1"),
                        ("clear-grouped-request", CONVOY)):
            proc = self.run_tool(*command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertEqual(before, self.tracker.read_text())

    # --- T21: the red of the integration branch, the bounds read in one place ---

    RED_CONTROL = "commande de régression (python3 regression.py) : code 1, sur integration/fx-spec après reprise de main"
    REPAIR = "fx-r1"

    def red_convoy(self):
        """A marked convoy that tracks a repair, its integration branch
        recorded and red at its tip; returns that tip."""
        self.seed(tickets=(T1, T2, self.REPAIR), kinds={self.REPAIR: "repair"})
        self.init_repo()
        self.ok("mark", CONVOY, "--demonstration-line", f"{self.REPAIR}=La commande de régression se termine avec le code 0")
        tip = self.git("rev-parse", "main")
        self.ok("set-integration", CONVOY, "--branch", "integration/fx-spec", "--protected", "main", "--base", tip)
        self.ok("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", tip,
                "--control", self.RED_CONTROL)
        return tip

    def red(self):
        return self.show()["convoy"]["integration_red"]

    def test_record_integration_red_is_read_back_by_show(self):
        tip = self.red_convoy()

        red = self.red()
        self.assertEqual((self.RED_CONTROL, tip, tip, tip),
                         tuple(red[name] for name in ("control", "commit", "integration", "protected")))
        self.assertIn("at", red)
        self.assertNotIn("repair", red)

    def test_a_convoy_whose_integration_branch_is_not_red_shows_none(self):
        self.integrated()

        self.assertIsNone(self.red())

    def test_the_same_red_recorded_again_writes_nothing(self):
        tip = self.red_convoy()
        self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)
        before = self.tracker.read_bytes()

        answer = self.ok("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", tip,
                         "--control", self.RED_CONTROL)

        self.assertEqual({}, answer["written"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(self.REPAIR, self.red()["repair"])

    def test_a_branch_found_red_elsewhere_while_it_is_red_keeps_its_one_repair(self):
        tip = self.red_convoy()
        self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)

        self.ok("record-integration-red", CONVOY, "--commit", ABSENT_COMMIT, "--integration", tip, "--protected", tip,
                "--control", self.RED_CONTROL, "--detail", "AssertionError: items absent from the home page")

        red = self.red()
        self.assertEqual((ABSENT_COMMIT, "AssertionError: items absent from the home page"), (red["commit"], red["detail"]))
        self.assertEqual(self.REPAIR, red["repair"])

    def test_the_same_red_recorded_once_its_repair_is_closed_is_a_red_without_repair(self):
        tip = self.red_convoy()
        self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)
        self.ok("close-ticket", CONVOY, self.REPAIR, "--commit", tip, "--file", GATE_REPORT)

        self.ok("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", tip,
                "--control", self.RED_CONTROL)

        self.assertNotIn("repair", self.red())

    def test_record_integration_red_refuses_what_is_not_a_red_and_writes_nothing(self):
        tip = self.red_convoy()
        red = ("record-integration-red", CONVOY)
        self.assert_refused_and_nothing_written(
            *red, "--commit", "abc", "--integration", tip, "--protected", tip, "--control", "x", mention="commit")
        self.assert_refused_and_nothing_written(
            *red, "--commit", tip, "--integration", tip, "--protected", tip, mention="contrôle rouge")
        self.assert_refused_and_nothing_written(
            *red, "--commit", tip, "--integration", tip, "--control", "x", mention="branche protégée")
        self.assert_refused_and_nothing_written(
            *red, "--commit", tip, "--integration", tip, "--protected", tip, "--control", "x", "--detail", "a\nb",
            mention="détail")

    def test_record_integration_red_refuses_a_convoy_without_integration_branch(self):
        tip = self.started_ticket()

        self.assert_refused_and_nothing_written(
            "record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", tip,
            "--control", self.RED_CONTROL, mention="branche d'intégration")

    def test_the_repair_of_a_red_is_one_tracked_repair_ticket(self):
        self.red_convoy()
        self.assert_refused_and_nothing_written(
            "set-integration-repair", CONVOY, "--ticket", T1, mention="repair")
        self.assert_refused_and_nothing_written(
            "set-integration-repair", CONVOY, "--ticket", "fx-absent", mention="n'appartient pas")

        self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)

        self.assertEqual(self.REPAIR, self.red()["repair"])
        self.assertEqual({}, self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)["written"])

    def test_a_red_takes_one_repair_only_while_that_repair_is_open(self):
        tip = self.red_convoy()
        state = self.tracker_state()
        state["beads"]["fx-r2"] = {"title": "second repair", "status": "open", "issue_type": "task",
                                   "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append("fx-r2")
        self.tracker.write_text(json.dumps(state))
        self.ok("mark", CONVOY, "--demonstration-line", "fx-r2=La commande de régression se termine avec le code 0")
        self.ok("set-integration-repair", CONVOY, "--ticket", self.REPAIR)

        self.assert_refused_and_nothing_written(
            "set-integration-repair", CONVOY, "--ticket", "fx-r2", mention="un seul repair par rouge")

        self.ok("close-ticket", CONVOY, self.REPAIR, "--commit", tip, "--file", GATE_REPORT)
        self.ok("set-integration-repair", CONVOY, "--ticket", "fx-r2")
        self.assertEqual("fx-r2", self.red()["repair"])

    def test_set_integration_repair_refuses_a_convoy_that_is_not_red(self):
        self.seed(tickets=(T1, self.REPAIR), kinds={self.REPAIR: "repair"})
        self.init_repo()
        self.ok("mark", CONVOY, "--demonstration-line", f"{self.REPAIR}=La commande de régression se termine avec le code 0")

        self.assert_refused_and_nothing_written(
            "set-integration-repair", CONVOY, "--ticket", self.REPAIR, mention="n'est pas rouge")

    def test_clear_integration_red_removes_it(self):
        self.red_convoy()

        self.ok("clear-integration-red", CONVOY)

        self.assertIsNone(self.red())
        self.assertNotIn("gc.flow.integration_red", self.tracker_state()["beads"][CONVOY]["metadata"])

    def test_the_red_of_an_unmarked_convoy_is_not_recorded(self):
        before = self.tracker.read_text()

        for command in (("record-integration-red", CONVOY, "--commit", ABSENT_COMMIT, "--integration", ABSENT_COMMIT,
                         "--protected", ABSENT_COMMIT, "--control", self.RED_CONTROL),
                        ("set-integration-repair", CONVOY, "--ticket", T1), ("clear-integration-red", CONVOY)):
            with self.subTest(command=command[0]):
                proc = self.run_tool(*command)
                self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual(before, self.tracker.read_text())

    def test_an_integration_red_written_outside_the_command_is_a_state_without_rule(self):
        self.red_convoy()
        self.edit_tracker(CONVOY, **{"gc.flow.integration_red": "à la main"})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("unruled", shown["convoy"]["integration_red"])
        self.assertEqual("gc.flow.integration_red", shown["convoy"]["unruled"][0]["field"])

    def bounds(self, **values):
        """A Factory root whose delivery-flow settings give these bounds."""
        root = self.tmp / "root"
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "config" / "delivery-flow.json").write_text(json.dumps({"bounds": values}))
        self.env["FACTORY_ROOT"] = str(root)

    def test_the_bound_of_the_resumes_is_the_one_of_the_delivery_flow_settings(self):
        self.interrupted_ticket()
        self.bounds(resumes=2, open_planning_exceptions=2)

        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "a")
        self.assertEqual(1, self.ticket(self.show(), T1)["resumes_left"])
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "b")

        # The second resume is the last one: the ticket is out of resumes, and parked for it.
        self.assertEqual(0, self.ticket(self.show(), T1)["resumes_left"])
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "c", mention="ses 2 reprises")
        self.ok("park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "2 reprises")

    def test_a_larger_bound_of_the_resumes_leaves_the_ticket_at_work_after_three(self):
        self.interrupted_ticket()
        self.bounds(resumes=4, open_planning_exceptions=2)
        for ref in ("a", "b", "c"):
            self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", ref)

        self.assertEqual(1, self.ticket(self.show(), T1)["resumes_left"])
        self.assert_refused_and_nothing_written(
            "park", CONVOY, T1, "--cause", "resumes_exhausted", "--detail", "x", mention="reprises")

    def test_the_bound_of_the_resumes_may_be_set_per_cause(self):
        self.interrupted_ticket()
        per_cause = {"interrupted": 1, "returned": 2, "unblocked": 3, "answered": 3, "behind": 3,
                     "evaluation_no_result": 3, "stage_removed": 3, "code_review_no_result": 3,
                     "commit_after_verdict": 3}
        self.bounds(resumes=per_cause, open_planning_exceptions=2)

        self.ok("open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:1")
        self.assertEqual(1, self.ticket(self.show(), T1)["resumes_left"])
        self.ok("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "a")

        ticket = self.ticket(self.show(), T1)
        self.assertEqual((0, 1), (ticket["resumes_left"], ticket["resumes_left_by_cause"]["returned"]))
        self.assert_refused_and_nothing_written(
            "open-resume", CONVOY, T1, "--cause", "returned", "--ref", "merge:2", mention="ses 1 reprises")

    def test_a_malformed_bound_of_the_resumes_is_refused_and_nothing_is_written(self):
        self.interrupted_ticket()
        all_causes = ("interrupted", "returned", "unblocked", "answered", "behind", "evaluation_no_result",
                      "stage_removed", "code_review_no_result", "commit_after_verdict")
        missing = {cause: 3 for cause in all_causes[1:]}
        unknown = {**missing, "interrupted": 3, "fatigue": 3}
        zero = {**missing, "interrupted": 0}
        for value in (0, "trois", True, None, {}, missing, unknown, zero):
            with self.subTest(value=value):
                self.bounds(resumes=value, open_planning_exceptions=2)
                before = self.tracker.read_bytes()
                proc = self.run_tool("open-resume", CONVOY, T1, "--cause", "interrupted", "--ref", "a")
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("bounds.resumes", json.loads(proc.stdout)["error"])
                self.assertEqual(before, self.tracker.read_bytes())
                self.assertEqual(1, self.run_tool("show", CONVOY, "--repo", self.repo).returncode)

    # --- T23: the tracked elements of a Ticket Handoff, the end-of-Spec gate ----

    ITEM_REPAIR = "fx-r1"

    def handed_off(self):
        """A marked convoy -- a slice, a prefactoring and a repair -- whose
        slice left two « non faits » in its Ticket Handoff; returns the tip
        of the repository."""
        self.seed(tickets=(T1, T2, self.ITEM_REPAIR), kinds={T1: "vertical_slice", self.ITEM_REPAIR: "repair"})
        self.init_repo()
        self.ok("mark", CONVOY, "--demonstration-line", f"{T1}=La page affiche 3", "--user-stories", f"{T1}=1",
                "--demonstration-line", f"{self.ITEM_REPAIR}=La sonde est branchée")
        self.sealed_records()
        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file())
        return self.git("rev-parse", "main")

    def ask(self, *items, option="b", summary="Fin de Spec, ticket fx-t1, sans état final"):
        return self.ok("raise-planning-exception", CONVOY, T1, "--kind", "semantic", "--summary", summary,
                       *[arg for item in items for arg in ("--item", item)], "--accept-option", option)

    def items(self, ticket_id=T1):
        return self.ticket(self.show(), ticket_id)["tracked_items"]

    def test_show_renders_each_deviation_and_not_done_of_a_handoff_as_an_open_tracked_element(self):
        self.handed_off()

        self.assertEqual(
            [("not_done.1", "not_done", 1, "La sonde n'est pas branchée.", "ouvert", None, None),
             ("not_done.2", "not_done", 2, "Le libellé manque.", "ouvert", None, None)],
            [tuple(item[name] for name in ("id", "section", "number", "text", "state", "request", "repair"))
             for item in self.items()])
        # A ticket without a Handoff, or a section that says « aucun », tracks nothing.
        self.assertEqual([], self.items(T2))

    def test_a_deviation_of_a_handoff_is_a_tracked_element_too(self):
        self.handed_off()
        self.ok("set-handoff", CONVOY, T1, "--file", self.handoff_file(
            sections={**self.SECTIONS, "deviations": ["La liste est triée par nom."], "not_done": "aucun"}))

        self.assertEqual([("deviations.1", "La liste est triée par nom.", "ouvert")],
                         [(item["id"], item["text"], item["state"]) for item in self.items()])

    def test_a_tracked_element_is_accepted_only_by_the_accepting_answer_to_the_exception_that_names_it(self):
        self.handed_off()

        self.ask("not_done.1")

        first, second = self.items()
        self.assertEqual(("ouvert", "open", False), (first["state"], first["request"]["state"], first["request"]["accepted"]))
        raised = self.ticket(self.show(), T1)["planning_exceptions"][-1]
        self.assertEqual((["not_done.1"], [], "b", "open"),
                         (raised["items"], raised["anchors"], raised["accept_option"], raised["state"]))

        self.answer("b")

        first, second = self.items()
        self.assertEqual(("accepté par Benjamin", "resolved", True),
                         (first["state"], first["request"]["state"], first["request"]["accepted"]))
        # The element the exception does not name stays without a final state.
        self.assertEqual(("ouvert", None), (second["state"], second["request"]))

    def test_a_handoff_rendered_again_starts_its_tracked_elements_over(self):
        self.handed_off()
        self.ask("not_done.1")
        self.answer("b")
        self.assertEqual("accepté par Benjamin", self.items()[0]["state"])

        handoff = json.loads(self.tracker_state()["beads"][T1]["metadata"]["gc.flow.handoff"])
        self.edit_tracker(T1, **{"gc.flow.handoff": json.dumps({**handoff, "at": "2999-01-01T00:00:00Z"})})

        self.assertEqual(("ouvert", None), (self.items()[0]["state"], self.items()[0]["request"]))

    def test_raise_planning_exception_refuses_an_item_the_handoff_does_not_carry(self):
        self.handed_off()
        base = ("raise-planning-exception", CONVOY, T1, "--kind", "semantic", "--summary", "x")
        for args, mention in (
            (("--item", "not_done.0", "--accept-option", "b"), "élément suivi mal formé"),
            (("--item", "out_of_ticket.1", "--accept-option", "b"), "élément suivi mal formé"),
            (("--item", "not_done.3", "--accept-option", "b"), "ne porte pas l'élément not_done.3"),
            (("--item", "deviations.1", "--accept-option", "b"), "ne porte pas l'élément deviations.1"),
            (("--item", "not_done.1", "--item", "not_done.1", "--accept-option", "b"), "deux fois"),
            (("--item", "not_done.1"), "option"),
        ):
            with self.subTest(args=args):
                self.assert_refused_and_nothing_written(*base, *args, mention=mention)
        # A ticket that rendered no Handoff carries no element at all.
        self.assert_refused_and_nothing_written(
            "raise-planning-exception", CONVOY, T2, "--kind", "semantic", "--summary", "x", "--item", "not_done.1",
            "--accept-option", "b", mention="ne porte pas l'élément")

    def test_raising_the_same_exception_on_the_same_items_again_writes_nothing(self):
        self.handed_off()
        self.ask("not_done.1", "not_done.2")
        before = self.tracker.read_bytes()

        self.assertEqual({}, self.ask("not_done.1", "not_done.2")["written"])

        self.assertEqual(before, self.tracker.read_bytes())

    def test_an_element_to_repair_is_repaired_once_the_ticket_end_gate_closed_its_repair(self):
        tip = self.handed_off()
        self.ask("not_done.1")
        # Answered by the option that asks for a repair.
        self.answer("a")
        item = self.items()[0]
        self.assertEqual(("ouvert", "resolved", False, None),
                         (item["state"], item["request"]["state"], item["request"]["accepted"], item["repair"]))

        self.ok("set-item-repair", CONVOY, T1, "--repair", self.ITEM_REPAIR)

        # Naming the repair repairs nothing.
        item = self.items()[0]
        self.assertEqual(("ouvert", self.ITEM_REPAIR), (item["state"], item["repair"]))
        raised = self.ticket(self.show(), T1)["planning_exceptions"][-1]
        self.assertEqual((self.ITEM_REPAIR, "a"), (raised["repair"], raised["response"]["option"]))

        self.ok("close-ticket", CONVOY, self.ITEM_REPAIR, "--commit", tip, "--file", GATE_REPORT)

        first, second = self.items()
        self.assertEqual(("réparé", self.ITEM_REPAIR), (first["state"], first["repair"]))
        self.assertEqual("ouvert", second["state"])
        self.assertFalse(self.show()["unruled"])

    def test_a_repair_closed_outside_the_ticket_end_gate_repairs_nothing(self):
        self.handed_off()
        self.ask("not_done.1")
        self.answer("a")
        self.ok("set-item-repair", CONVOY, T1, "--repair", self.ITEM_REPAIR)

        self.edit_tracker(self.ITEM_REPAIR, status="closed")

        shown = self.show(expect=EXIT_UNRULED)
        self.assertEqual("ouvert", self.ticket(shown, T1)["tracked_items"][0]["state"])

    def test_naming_the_same_item_repair_again_writes_nothing(self):
        self.handed_off()
        self.ask("not_done.1")
        self.answer("a")
        self.ok("set-item-repair", CONVOY, T1, "--repair", self.ITEM_REPAIR)
        before = self.tracker.read_bytes()

        self.assertEqual({}, self.ok("set-item-repair", CONVOY, T1, "--repair", self.ITEM_REPAIR)["written"])

        self.assertEqual(before, self.tracker.read_bytes())

    def test_set_item_repair_refuses_without_an_answer_that_asks_for_the_repair(self):
        self.handed_off()
        repair = ("set-item-repair", CONVOY, T1, "--repair", self.ITEM_REPAIR)
        # No Planning Exception names an element.
        self.assert_refused_and_nothing_written(*repair, mention="ne nomme aucun élément suivi")
        # Raised, not answered.
        self.ask("not_done.1")
        self.assert_refused_and_nothing_written(*repair, mention="pas de réponse de l'opérateur")
        # Accepted by the operator.
        self.answer("b")
        self.assert_refused_and_nothing_written(*repair, mention="a accepté")

    def test_set_item_repair_refuses_what_is_not_one_tracked_repair_of_the_convoy(self):
        self.handed_off()
        self.ask("not_done.1")
        self.answer("a")
        base = ("set-item-repair", CONVOY, T1)
        self.assert_refused_and_nothing_written(*base, "--repair", T2, mention="n'est pas un repair")
        self.assert_refused_and_nothing_written(*base, "--repair", "fx-absent", mention="n'appartient pas")
        self.assert_refused_and_nothing_written(*base, mention="ticket absent")

        state = self.tracker_state()
        state["beads"]["fx-r2"] = {"title": "second repair", "status": "open", "issue_type": "task",
                                   "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append("fx-r2")
        self.tracker.write_text(json.dumps(state))
        self.ok("mark", CONVOY, "--demonstration-line", "fx-r2=La sonde est branchée")
        self.ok(*base, "--repair", self.ITEM_REPAIR)
        self.assert_refused_and_nothing_written(*base, "--repair", "fx-r2", mention="un seul repair par demande")

    def test_a_repair_written_on_an_exception_outside_the_command_is_a_state_without_rule(self):
        self.handed_off()
        self.ask("not_done.1")
        entries = json.loads(self.tracker_state()["beads"][T1]["metadata"]["gc.flow.planning_exceptions"])["entries"]
        # A repair named while the operator has not answered.
        entries[-1]["repair"] = self.ITEM_REPAIR
        self.edit_tracker(T1, **{"gc.flow.planning_exceptions": json.dumps({"entries": entries})})

        ticket = self.ticket(self.show(expect=EXIT_UNRULED), T1)

        self.assertIn("unruled", ticket["planning_exceptions"])
        self.assertIn("gc.flow.planning_exceptions", [entry["field"] for entry in ticket["unruled"]])

    SPEC_END_NAMES = ("registry", "tests", "fidelity")

    def spec_end_file(self, **changes):
        report = {"version": "spec-end/v4",
                  "conditions": [{"number": number, "name": name, "verdict": "pass", "detail": "réunie (relevé d'essai)"}
                                 for number, name in enumerate(self.SPEC_END_NAMES, start=1)],
                  "records": {"tests": {"command": "python3 regression.py", "exit_code": 0}, "fidelity": {"prototypes": []}},
                  **changes}
        path = self.tmp / "spec-end.json"
        path.write_text(json.dumps({key: value for key, value in report.items() if value is not None}, ensure_ascii=False))
        return path

    def delivered_convoy(self):
        """A marked convoy whose integration branch is recorded and whose
        two tickets were closed by the ticket-end gate; returns its tip."""
        tip, base = self.integrated()
        for ticket in (T1, T2):
            self.ok("close-ticket", CONVOY, ticket, "--commit", tip, "--file", GATE_REPORT)
        return tip, base

    def test_record_spec_end_ties_three_passing_verdicts_to_one_commit_and_show_reads_them_back(self):
        tip, base = self.delivered_convoy()
        self.assertIsNone(self.show()["convoy"]["spec_end"])
        self.write_log.write_text("")

        self.ok("record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file())

        self.assertEqual(1, len([line for line in self.write_log.read_text().splitlines() if line.strip()]))
        shown = self.show()
        record = shown["convoy"]["spec_end"]
        self.assertEqual(("spec-end/v4", tip, base), (record["version"], record["commit"], record["protected"]))
        self.assertEqual([(number, name, "pass") for number, name in enumerate(self.SPEC_END_NAMES, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in record["conditions"]])
        self.assertEqual({"tests", "fidelity"}, set(record["records"]))
        self.assertIn("at", record)
        self.assertFalse(shown["unruled"])

    def test_record_spec_end_refuses_a_record_that_is_not_the_three_passing_verdicts_of_the_known_version(self):
        tip, base = self.delivered_convoy()
        conditions = json.loads(self.spec_end_file().read_text())["conditions"]
        failing = [dict(entry, verdict="fail") if entry["number"] == 2 else entry for entry in conditions]
        renamed = [dict(entry, name="autre") if entry["number"] == 3 else entry for entry in conditions]
        silent = [dict(entry, detail=" ") if entry["number"] == 1 else entry for entry in conditions]
        for changes, mention in (
            ({"version": "spec-end/v0"}, "version"),
            # The list of T23, three conditions: no longer recorded (T24).
            ({"version": "spec-end/v1"}, "version"),
            # The list of T25, six conditions: no longer recorded (T27).
            ({"version": "spec-end/v3"}, "version"),
            ({"conditions": conditions[:2]}, "3 verdicts attendus"),
            ({"conditions": failing}, "condition 2 (tests) non réunie"),
            ({"conditions": renamed}, "verdict 3"),
            ({"conditions": silent}, "condition 1"),
            ({"records": {"registre": {}}}, "relevés"),
            ({"records": {"tests": "vert"}}, "relevés"),
            ({"closed_by": "auteur"}, "champs inconnus"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(
                    "record-spec-end", CONVOY, "--commit", tip, "--protected", base,
                    "--file", self.spec_end_file(**changes), mention=mention)
        record = ("record-spec-end", CONVOY)
        self.assert_refused_and_nothing_written(
            *record, "--commit", "pas-un-sha", "--protected", base, "--file", self.spec_end_file(), mention="commit")
        self.assert_refused_and_nothing_written(
            *record, "--commit", tip, "--file", self.spec_end_file(), mention="branche protégée")
        self.assert_refused_and_nothing_written(
            *record, "--commit", tip, "--protected", base, "--file", self.tmp / "absent.json", mention="illisible")
        self.assertIsNone(self.show()["convoy"]["spec_end"])

    def test_record_spec_end_refuses_a_convoy_with_a_ticket_left_open_or_closed_outside_its_gate(self):
        tip, base = self.integrated()
        record = ("record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file())
        self.ok("close-ticket", CONVOY, T1, "--commit", tip, "--file", GATE_REPORT)

        proc = self.assert_refused_and_nothing_written(*record, mention="tickets ouverts ou fermés hors porte")
        self.assertIn(T2, json.loads(proc.stdout)["error"])
        self.assertNotIn(T1, json.loads(proc.stdout)["error"])

        self.edit_tracker(T2, status="closed")
        self.assert_refused_and_nothing_written(*record, mention=T2)

    def test_record_spec_end_refuses_a_red_integration_branch_and_a_convoy_without_one(self):
        tip, base = self.delivered_convoy()
        self.ok("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", base,
                "--control", self.RED_CONTROL)

        self.assert_refused_and_nothing_written(
            "record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file(),
            mention="est rouge")

        self.seed()
        tip = self.git("rev-parse", "main")
        self.ok("mark", CONVOY)
        self.assert_refused_and_nothing_written(
            "record-spec-end", CONVOY, "--commit", tip, "--protected", tip, "--file", self.spec_end_file(),
            mention="pas de branche d'intégration")

    def test_a_spec_end_record_written_outside_the_command_is_a_state_without_rule(self):
        tip, base = self.delivered_convoy()
        for written in ("à la main", json.dumps({"commit": tip, "protected": base, "version": "spec-end/v4", "at": "x",
                                                 "conditions": [{"number": 1, "name": "registry", "verdict": "pass",
                                                                 "detail": "seul"}]})):
            with self.subTest(written=written[:12]):
                self.edit_tracker(CONVOY, **{"gc.flow.spec_end": written})

                shown = self.show(expect=EXIT_UNRULED)

                self.assertIn("unruled", shown["convoy"]["spec_end"])
                self.assertEqual(["gc.flow.spec_end"], [entry["field"] for entry in shown["convoy"]["unruled"]])

    # --- T27: the Evidence Pack code generated, tied to one commit ---------------------------

    PACK_DIGEST = "sha256:" + "5e" * 32

    def pack(self, tip, *more, digest=None, path="/var/packs/fx-spec/fx-convoy"):
        return ("record-evidence-pack", CONVOY, "--commit", tip, "--digest", digest or self.PACK_DIGEST, "--path", path,
                *(more or ("--conforming",)))

    def test_record_evidence_pack_ties_the_page_to_one_commit_and_show_reads_it_back(self):
        tip, _ = self.integrated()
        self.assertIsNone(self.show()["convoy"]["evidence_pack"])
        self.write_log.write_text("")

        self.ok(*self.pack(tip))

        self.assertEqual(1, len([line for line in self.write_log.read_text().splitlines() if line.strip()]))
        record = self.show()["convoy"]["evidence_pack"]
        self.assertEqual((tip, self.PACK_DIGEST, "/var/packs/fx-spec/fx-convoy", True, 0, "evidence-pack/v1"),
                         tuple(record[name] for name in ("commit", "digest", "path", "conforming", "inadmissible", "version")))
        self.assertIn("at", record)
        # The same pack again writes nothing; another page replaces the record.
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok(*self.pack(tip))["written"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.ok(*self.pack(tip, "--non-conforming", "--inadmissible", "2", digest="sha256:" + "6f" * 32))
        record = self.show()["convoy"]["evidence_pack"]
        self.assertEqual(("sha256:" + "6f" * 32, False, 2), (record["digest"], record["conforming"], record["inadmissible"]))

    def test_record_evidence_pack_refuses_a_malformed_record_and_writes_nothing(self):
        tip, _ = self.integrated()
        for command, mention in (
            (self.pack("pas-un-sha"), "commit"),
            (self.pack(tip, digest="5e5e"), "sha256"),
            (self.pack(tip, path="packs/relatif"), "chemin absolu"),
            (self.pack(tip, "--inadmissible", "1"), "conformité"),
            (self.pack(tip, "--conforming", "--inadmissible", "-1"), "irrecevables"),
            (self.pack(tip, "--conforming", "--inadmissible", "deux"), "irrecevables"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written(*command, mention=mention)
        self.assertIsNone(self.show()["convoy"]["evidence_pack"])

    def test_record_evidence_pack_refuses_a_convoy_without_an_integration_branch_or_without_the_mark(self):
        tip = "a" * 40
        before = self.tracker.read_bytes()

        proc = self.run_tool(*self.pack(tip))

        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_bytes())
        self.ok("mark", CONVOY)
        self.assert_refused_and_nothing_written(*self.pack(tip), mention="pas de branche d'intégration")

    def test_an_evidence_pack_record_written_outside_the_command_is_a_state_without_rule(self):
        tip, _ = self.integrated()
        self.edit_tracker(CONVOY, **{"gc.flow.evidence_pack": json.dumps({"commit": tip, "digest": self.PACK_DIGEST})})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("unruled", shown["convoy"]["evidence_pack"])
        self.assertEqual(["gc.flow.evidence_pack"], [entry["field"] for entry in shown["convoy"]["unruled"]])

    def test_show_renders_the_digest_of_the_spec_the_publication_door_wrote_on_the_convoy(self):
        self.ok("mark", CONVOY)
        self.assertIsNone(self.show()["convoy"]["spec_digest"])

        self.edit_tracker(CONVOY, **{"gc.spec_digest": self.PACK_DIGEST})

        self.assertEqual(self.PACK_DIGEST, self.show()["convoy"]["spec_digest"])

    def test_a_red_names_the_control_that_is_red_when_it_is_not_the_regression_command(self):
        tip, base = self.integrated()
        red = ("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", base,
               "--control", "fidélité mécanique au Validated Prototype : écart(s) ouvert(s)")

        self.assert_refused_and_nothing_written(*red, "--check", "revue", mention="contrôle rouge (--check)")

        self.ok(*red, "--check", "fidelity")
        self.assertEqual("fidelity", self.red()["check"])
        self.assertEqual({"end_rounds": 0}, self.show()["convoy"]["counters"])

    def test_a_red_of_the_end_of_the_spec_counts_one_round_in_the_write_that_records_it(self):
        tip, base = self.integrated()
        red = ("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", base,
               "--control", self.RED_CONTROL, "--end-round")
        self.write_log.write_text("")

        self.ok(*red)

        self.assertEqual(1, len([line for line in self.write_log.read_text().splitlines() if line.strip()]))
        self.assertEqual({"end_rounds": 1}, self.show()["convoy"]["counters"])
        self.assertNotIn("check", self.red())

        # The same red seen again is recorded once, and counted once.
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok(*red)["written"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual({"end_rounds": 1}, self.show()["convoy"]["counters"])

    # --- the end code review of the Spec (T25) ---------------------------------------------

    END_EXTENT = {"files": 3, "commits": 2, "insertions": 40, "deletions": 4, "digest": DIGEST}
    END_SPEC_LINE = "As Benjamin, I want la page d'accueil afficher le nombre d'éléments."
    END_DRAFT = {
        "title": "Afficher le nombre d'éléments sur la page d'accueil",
        "what_it_delivers": "La page d'accueil affiche de nouveau le nombre d'éléments que deux tickets se disputent.",
        "restores": {"kind": "spec_line", "ref": END_SPEC_LINE},
        "demonstration_line": "Sur le produit lancé, la page d'accueil affiche le nombre d'éléments.",
        "acceptance_criteria": [{"entry_point": "GET /", "observable": "le nombre d'éléments",
                                 "false_if": "le nombre d'éléments n'y est pas"}],
    }
    END_BLOCKING = {"axis": "spec", "blocking": True, "summary": "Deux tickets se contredisent sur le nombre affiché.",
                    "citation": {"source": "spec", "quote": END_SPEC_LINE}, "repair": END_DRAFT}
    END_TASTE = {"axis": "standards", "blocking": True, "summary": "Possible Feature Envy dans render()."}
    END_COVERED = {"axes": ["standards", "spec"], "files": 3, "missing": []}

    def verified_convoy(self):
        """A delivered convoy whose three mechanical verdicts are recorded
        at the tip of its integration branch."""
        tip, base = self.delivered_convoy()
        self.ok("record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file())
        return tip, base

    def end_request_file(self, **changes):
        return self.json_file("end-review-request.json", {
            "extent": self.END_EXTENT, "reviewer": {"agent": "delivery-reviewer", "provider": "p-codex", "model": "gpt-5"},
            **changes})

    def end_review_file(self, tip, findings=(), coverage=None, **changes):
        return self.json_file("end-review.json", {
            "commit": tip, "recorded_by": "delivery-reviewer-fx", "findings": list(findings),
            "coverage": self.END_COVERED if coverage is None else coverage, **changes})

    def end_review(self, expect=0):
        return self.show(expect)["convoy"]["end_review"]

    def opened_end_review(self):
        tip, base = self.verified_convoy()
        self.ok("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())
        return tip, base

    def refused_end_review(self):
        """An end review that handed in one cited Blocking Finding with its
        drafted repair."""
        tip, base = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [self.END_BLOCKING]))
        return tip, base

    def test_open_end_review_ties_the_request_to_the_commit_of_the_gate_and_its_whole_diff(self):
        tip, base = self.verified_convoy()
        self.assertIsNone(self.end_review())
        self.write_log.write_text("")

        self.ok("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())

        self.assertEqual(1, len([line for line in self.write_log.read_text().splitlines() if line.strip()]))
        review = self.end_review()
        request = review["request"]
        # The diff under review is the whole one: from the tip of the
        # protected branch the commit of the gate holds, to that commit.
        self.assertEqual((tip, base, self.END_EXTENT, []),
                         (request["commit"], request["base"], request["extent"], request["launches"]))
        self.assertEqual("gpt-5", request["models"]["reviewer"])
        self.assertEqual(([], {"commit": None, "outcome": None, "unsettled": []}), (review["rounds"], review["state"]))
        # The same request again writes nothing.
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())["written"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertFalse(self.show()["unruled"])

    def test_open_end_review_refuses_a_commit_the_three_mechanical_verdicts_were_not_rendered_on(self):
        tip, base = self.delivered_convoy()
        open_ = ("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())
        self.assert_refused_and_nothing_written(*open_, mention="verdicts mécaniques")
        self.ok("record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file())
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", base, "--file", self.end_request_file(), mention="verdicts mécaniques")
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file(extent={"files": "trois"}),
            mention="étendue")
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file(verdict="favorable"),
            mention="champs inconnus")
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", tip, "--file", self.tmp / "absent.json", mention="illisible")
        self.assertIsNone(self.end_review())

    def test_launch_end_review_counts_the_first_launch_and_one_relaunch(self):
        tip, _ = self.verified_convoy()
        self.assert_refused_and_nothing_written("launch-end-review", CONVOY, "--bead", "fx-review1", mention="rien à lancer")
        self.ok("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review2")

        self.assertEqual(["fx-review1", "fx-review2"], [entry["bead"] for entry in self.end_review()["request"]["launches"]])
        self.assert_refused_and_nothing_written("launch-end-review", CONVOY, "--bead", "fx-review3", mention="une seule relance")
        self.assert_refused_and_nothing_written("launch-end-review", CONVOY, "--bead", "pas un bead", mention="bead")

    def test_a_complete_end_review_without_blocking_finding_is_favorable_at_its_commit(self):
        tip, base = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")

        answer = self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [self.END_TASTE]))

        self.assertEqual(("favorable", [], True), (answer["outcome"], answer["blocking"], answer["complete"]))
        # A finding of taste given as blocking is recorded, and blocks nothing.
        self.assertEqual(["F1.1"], [entry["id"] for entry in answer["demoted"]])
        review = self.end_review()
        self.assertNotIn("request", review)
        round_ = review["rounds"][0]
        self.assertEqual((tip, base, "favorable", self.END_EXTENT, "delivery-reviewer-fx"),
                         (round_["commit"], round_["base"], round_["outcome"], round_["extent"], round_["recorded_by"]))
        self.assertFalse(round_["findings"][0]["blocking"])
        # The record says whether the review held: its duration, and that its output is complete.
        self.assertIsInstance(round_["duration_seconds"], int)
        self.assertEqual(self.END_COVERED, round_["coverage"])
        self.assertEqual({"commit": tip, "outcome": "favorable", "unsettled": []}, review["state"])
        self.assertEqual({"end_rounds": 0}, self.show()["convoy"]["counters"])

    def test_a_cited_blocking_finding_with_its_drafted_repair_is_unfavorable_and_counts_one_round_of_the_end(self):
        tip, _ = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.write_log.write_text("")

        answer = self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [self.END_BLOCKING, self.END_TASTE]))

        # The round and its count are one tracker write.
        self.assertEqual(1, len([line for line in self.write_log.read_text().splitlines() if line.strip()]))
        self.assertEqual(("unfavorable", ["F1.1"]), (answer["outcome"], answer["blocking"]))
        shown = self.show()["convoy"]
        review = shown["end_review"]
        finding = review["rounds"][0]["findings"][0]
        self.assertEqual((True, self.END_BLOCKING["citation"], self.END_DRAFT),
                         (finding["blocking"], finding["citation"], finding["repair_draft"]))
        self.assertEqual({"commit": tip, "outcome": "unfavorable", "unsettled": ["F1.1"]}, review["state"])
        self.assertEqual({"end_rounds": 1}, shown["counters"])
        self.assertEqual((tip, "end_review"), (shown["end_round"]["commit"], shown["end_round"]["source"]))
        self.assertFalse(self.show()["unruled"])

    def test_record_end_review_refuses_what_is_outside_its_contract_and_writes_nothing(self):
        tip, base = self.opened_end_review()
        undrafted = {name: value for name, value in self.END_BLOCKING.items() if name != "repair"}
        hollow = {**self.END_BLOCKING, "repair": {**self.END_DRAFT, "acceptance_criteria": []}}
        unrestored = {**self.END_BLOCKING, "repair": {**self.END_DRAFT, "restores": {"kind": "red_check", "ref": "x"}}}
        for build, mention in (
            (lambda: self.end_review_file(tip, verdict="favorable"), "calculée par du code"),
            (lambda: self.end_review_file(base), "porte sur le commit"),
            (lambda: self.end_review_file(tip, [undrafted]), "sans repair rédigé"),
            (lambda: self.end_review_file(tip, [hollow]), "sans critère d'acceptation"),
            (lambda: self.end_review_file(tip, [unrestored]), "restores"),
            (lambda: self.end_review_file(tip, [{**self.END_TASTE, "axis": "goût"}]), "axe hors de la liste fermée"),
            (lambda: self.end_review_file(tip, coverage={"axes": ["spec"]}), "coverage"),
            (lambda: self.end_review_file(tip, recorded_by=" "), "session du relecteur"),
            (lambda: self.tmp / "absent.json", "illisible"),
        ):
            with self.subTest(mention=mention):
                self.assert_refused_and_nothing_written("record-end-review", CONVOY, "--file", build(), mention=mention)
        self.assertEqual([], self.end_review()["rounds"])

    def test_a_blocking_finding_whose_citation_does_not_hold_blocks_nothing_and_needs_no_repair(self):
        tip, _ = self.opened_end_review()
        refused = {name: value for name, value in self.END_BLOCKING.items() if name != "repair"}
        refused["citation_refused"] = "la ligne citée n'est pas une ligne de la Spec"

        answer = self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [refused]))

        self.assertEqual(("favorable", []), (answer["outcome"], answer["blocking"]))
        finding = self.end_review()["rounds"][0]["findings"][0]
        self.assertEqual((False, True), (finding["blocking"], "n'est pas une ligne de la Spec" in finding["demoted"]))

    def test_an_incomplete_end_review_is_not_a_passed_one_and_leaves_the_request_open(self):
        tip, _ = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        partial = {"axes": ["standards", "spec"], "files": 2, "missing": ["docs/fx-t2.md"]}

        answer = self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, coverage=partial))

        self.assertEqual(("incomplete", False), (answer["outcome"], answer["complete"]))
        review = self.end_review()
        self.assertEqual(("incomplete", partial), (review["rounds"][0]["outcome"], review["rounds"][0]["coverage"]))
        # No verdict: the request stays open, and its launch gave no result.
        self.assertEqual("incomplete", review["request"]["launches"][0]["result"])
        self.assertEqual({"commit": tip, "outcome": "incomplete", "unsettled": []}, review["state"])
        self.assertEqual({"end_rounds": 0}, self.show()["convoy"]["counters"])
        # One axis left out is an incomplete output too.
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review2")
        one_axis = {"axes": ["spec"], "files": 3, "missing": []}
        self.assertEqual("incomplete", self.ok(
            "record-end-review", CONVOY, "--file", self.end_review_file(tip, coverage=one_axis))["outcome"])

    def test_set_end_review_repair_names_the_published_repair_on_its_blocking_finding(self):
        self.refused_end_review()
        state = self.tracker_state()
        state["beads"]["fx-r1"] = {"title": "repair de la revue de fin", "status": "open", "issue_type": "task",
                                   "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append("fx-r1")
        self.tracker.write_text(json.dumps(state))
        self.ok("mark", CONVOY, "--demonstration-line", "fx-r1=Le nombre d'éléments est affiché")
        name = ("set-end-review-repair", CONVOY, "--finding", "F1.1")

        self.assert_refused_and_nothing_written(*name, "--ticket", T2, mention="n'est pas un repair")
        self.assert_refused_and_nothing_written(*name, "--ticket", "fx-absent", mention="n'appartient pas")
        self.assert_refused_and_nothing_written(*name, mention="--ticket ou --refused")
        self.assert_refused_and_nothing_written(
            "set-end-review-repair", CONVOY, "--finding", "F9.9", "--ticket", "fx-r1", mention="Blocking Finding")
        self.ok(*name, "--ticket", "fx-r1")

        self.assertEqual("fx-r1", self.end_review()["rounds"][0]["findings"][0]["repair"])
        # The same name again writes nothing; another one is refused.
        self.assertEqual({}, self.ok(*name, "--ticket", "fx-r1")["written"])
        self.assert_refused_and_nothing_written(*name, "--refused", "la porte a refusé", mention="déjà")

    def test_a_drafted_repair_the_patch_door_refused_is_recorded_on_its_finding(self):
        self.refused_end_review()

        self.ok("set-end-review-repair", CONVOY, "--finding", "F1.1", "--refused", "critère qui nomme un fichier")

        finding = self.end_review()["rounds"][0]["findings"][0]
        self.assertEqual("critère qui nomme un fichier", finding["repair_refused"])
        self.assertNotIn("repair", finding)

    def test_an_end_review_stopped_without_result_opens_nothing_more_on_that_commit(self):
        tip, _ = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review2")
        stop = ("stop-end-review", CONVOY, "--reason", "end_review_no_result", "--detail", "aucun verdict en 2 lancements")
        self.assert_refused_and_nothing_written(
            "stop-end-review", CONVOY, "--reason", "fatigue", "--detail", "x", mention="raison")

        self.ok(*stop)

        review = self.end_review()
        self.assertEqual((tip, "end_review_no_result"), (review["stop"]["commit"], review["stop"]["reason"]))
        self.assertNotIn("raised", review["stop"])
        self.assert_refused_and_nothing_written(
            "record-end-review", CONVOY, "--file", self.end_review_file(tip), mention="arrêtée")
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file(), mention="arrêtée")
        self.ok("end-review-stop-raised", CONVOY, "--bead", "fx-request")
        self.assertEqual("fx-request", self.end_review()["stop"]["bead"])
        self.assertIn("raised", self.end_review()["stop"])

    def test_a_new_tip_has_the_end_review_opened_again_and_no_earlier_round_stands_for_it(self):
        tip, base = self.refused_end_review()
        # One commit more on the integration branch, the gate replayed on it.
        new_tip = self.commit_on("ticket/t1")
        self.ok("record-spec-end", CONVOY, "--commit", new_tip, "--protected", base, "--file", self.spec_end_file())

        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file(), mention="verdicts mécaniques")
        self.ok("open-end-review", CONVOY, "--commit", new_tip, "--file", self.end_request_file())

        review = self.end_review()
        self.assertEqual((new_tip, 1), (review["request"]["commit"], len(review["rounds"])))
        # What the state says is still the round of the earlier tip: it names its commit.
        self.assertEqual((tip, "unfavorable"), (review["state"]["commit"], review["state"]["outcome"]))
        self.ok("record-end-review", CONVOY, "--file", self.end_review_file(new_tip))
        review = self.end_review()
        self.assertEqual([(tip, "unfavorable"), (new_tip, "favorable")],
                         [(round_["commit"], round_["outcome"]) for round_ in review["rounds"]])
        # A review already complete at a commit is not opened again on it.
        self.assert_refused_and_nothing_written(
            "open-end-review", CONVOY, "--commit", new_tip, "--file", self.end_request_file(), mention="déjà revue")
        self.assertEqual({"end_rounds": 1}, self.show()["convoy"]["counters"])

    def test_an_end_review_written_outside_the_command_is_a_state_without_rule(self):
        self.verified_convoy()
        self.edit_tracker(CONVOY, **{"gc.flow.end_review": json.dumps({"rounds": [{"outcome": "favorable"}]})})

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("unruled", shown["convoy"]["end_review"])
        self.assertIn("gc.flow.end_review", [entry["field"] for entry in shown["convoy"]["unruled"]])

    # --- the bound of the rounds of the end, and the stop « non conforme » (T26) ----------------

    OTHER_CONTROL = "fidélité mécanique au Validated Prototype : écart(s) ouvert(s) sur integration/fx-spec"

    def red_of_the_end(self, commit, base, control=None, *more):
        return ("record-integration-red", CONVOY, "--commit", commit, "--integration", commit, "--protected", base,
                "--control", control or self.RED_CONTROL, "--end-round", *more)

    def end_stop(self, expect=0):
        return self.show(expect)["convoy"]["end_stop"]

    def writes(self):
        return [line for line in self.write_log.read_text().splitlines() if line.strip()]

    def test_a_round_of_the_end_names_the_tip_and_the_source_that_counted_it(self):
        tip, base = self.integrated()

        self.ok(*self.red_of_the_end(tip, base))

        convoy = self.show()["convoy"]
        self.assertEqual({"end_rounds": 1}, convoy["counters"])
        self.assertEqual((tip, "regression"), (convoy["end_round"]["commit"], convoy["end_round"]["source"]))
        self.assertIsNone(convoy["end_stop"])

    def test_a_refusal_once_the_two_rounds_are_consumed_counts_no_round_and_stops_the_rounds_of_the_end(self):
        tip, base = self.integrated()
        self.ok("set-counter", CONVOY, "--counter", "end_rounds", "--value", "2")
        self.write_log.write_text("")

        self.ok(*self.red_of_the_end(tip, base))

        # The red and the stop are one tracker write; no third round is counted.
        self.assertEqual(1, len(self.writes()))
        convoy = self.show()["convoy"]
        self.assertEqual({"end_rounds": 2}, convoy["counters"])
        self.assertEqual(self.RED_CONTROL, convoy["integration_red"]["control"])
        stop = convoy["end_stop"]
        self.assertEqual(("end_rounds_exhausted", tip, "regression", 2),
                         tuple(stop[name] for name in ("reason", "commit", "source", "rounds")))
        self.assertIn(self.RED_CONTROL, stop["detail"])
        self.assertIn("at", stop)
        self.assertNotIn("request", stop)
        self.assertFalse(self.show()["unruled"])
        # Seen again by another pass: nothing more is written.
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok(*self.red_of_the_end(tip, base))["written"])
        self.assertEqual(before, self.tracker.read_bytes())

    def test_the_rounds_of_the_end_are_one_counter_whatever_the_source_of_the_findings(self):
        tip, base = self.delivered_convoy()
        # Round 1: a mechanical red, repaired since.
        self.ok(*self.red_of_the_end(base, base))
        self.ok("clear-integration-red", CONVOY)
        # Round 2: a Blocking Finding of the end review, on the tip the mechanical verdicts are green on.
        self.ok("record-spec-end", CONVOY, "--commit", tip, "--protected", base, "--file", self.spec_end_file())
        self.ok("open-end-review", CONVOY, "--commit", tip, "--file", self.end_request_file())
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [self.END_BLOCKING]))
        convoy = self.show()["convoy"]
        self.assertEqual({"end_rounds": 2}, convoy["counters"])
        self.assertEqual((tip, "end_review"), (convoy["end_round"]["commit"], convoy["end_round"]["source"]))
        self.assertIsNone(convoy["end_stop"])

        # A mechanical red again: the red and the review do not have two rounds each.
        self.ok(*self.red_of_the_end(tip, base, self.OTHER_CONTROL, "--check", "fidelity"))

        convoy = self.show()["convoy"]
        self.assertEqual({"end_rounds": 2}, convoy["counters"])
        self.assertEqual(("end_rounds_exhausted", tip, "fidelity", 2),
                         tuple(convoy["end_stop"][name] for name in ("reason", "commit", "source", "rounds")))
        self.assertEqual((tip, "end_review"), (convoy["end_round"]["commit"], convoy["end_round"]["source"]))

    def test_an_unfavorable_end_review_once_the_rounds_are_consumed_stops_the_rounds_and_counts_none(self):
        tip, _ = self.opened_end_review()
        self.ok("launch-end-review", CONVOY, "--bead", "fx-review1")
        self.ok("set-counter", CONVOY, "--counter", "end_rounds", "--value", "2")
        self.write_log.write_text("")

        answer = self.ok("record-end-review", CONVOY, "--file", self.end_review_file(tip, [self.END_BLOCKING]))

        # The round of the review and the stop are one tracker write.
        self.assertEqual(1, len(self.writes()))
        self.assertEqual("unfavorable", answer["outcome"])
        convoy = self.show()["convoy"]
        self.assertEqual({"end_rounds": 2}, convoy["counters"])
        self.assertIsNone(convoy["end_round"])
        self.assertEqual(("end_rounds_exhausted", tip, "end_review", 2),
                         tuple(convoy["end_stop"][name] for name in ("reason", "commit", "source", "rounds")))
        self.assertIn("F1.1", convoy["end_stop"]["detail"])

    def test_a_refusal_on_a_convoy_whose_rounds_are_stopped_writes_no_other_stop_and_counts_nothing(self):
        tip, base = self.delivered_convoy()
        self.ok("set-counter", CONVOY, "--counter", "end_rounds", "--value", "2")
        self.ok(*self.red_of_the_end(base, base))
        stop = self.end_stop()
        self.ok("clear-integration-red", CONVOY)

        self.ok(*self.red_of_the_end(tip, base, self.OTHER_CONTROL, "--check", "fidelity"))

        convoy = self.show()["convoy"]
        self.assertEqual(stop, convoy["end_stop"])
        self.assertEqual({"end_rounds": 2}, convoy["counters"])
        self.assertEqual(self.OTHER_CONTROL, convoy["integration_red"]["control"])

    def test_the_bound_of_the_rounds_of_the_end_is_the_one_of_the_delivery_flow_settings(self):
        tip, base = self.integrated()
        self.bounds(resumes=3, open_planning_exceptions=2, end_rounds=1)

        self.ok(*self.red_of_the_end(base, base))
        self.assertEqual(({"end_rounds": 1}, None), (self.show()["convoy"]["counters"], self.end_stop()))
        self.ok("clear-integration-red", CONVOY)
        self.ok(*self.red_of_the_end(tip, base))

        self.assertEqual({"end_rounds": 1}, self.show()["convoy"]["counters"])
        self.assertEqual(("end_rounds_exhausted", 1), (self.end_stop()["reason"], self.end_stop()["rounds"]))

    def test_a_missing_or_malformed_bound_of_the_rounds_of_the_end_refuses_the_count_and_writes_nothing(self):
        tip, base = self.integrated()
        for value in (None, 0, "deux", True):
            with self.subTest(value=value):
                self.bounds(resumes=3, open_planning_exceptions=2, **({} if value is None else {"end_rounds": value}))
                self.assert_refused_and_nothing_written(*self.red_of_the_end(tip, base), mention="bounds.end_rounds")
        # A red that counts no round of the end reads no bound of the rounds.
        self.ok("record-integration-red", CONVOY, "--commit", tip, "--integration", tip, "--protected", base,
                "--control", self.RED_CONTROL)

    def stopped_convoy(self):
        """A convoy whose rounds of the end are consumed and whose tip is
        refused once more: stopped. Returns that tip."""
        tip, base = self.integrated()
        self.ok("set-counter", CONVOY, "--counter", "end_rounds", "--value", "2")
        self.ok(*self.red_of_the_end(tip, base))
        return tip

    def test_end_stop_raised_records_the_request_and_the_non_conforming_pack_it_carries(self):
        tip = self.stopped_convoy()
        self.ok(*self.pack(tip, "--non-conforming"))
        self.write_log.write_text("")

        self.ok("end-stop-raised", CONVOY, "--bead", CONVOY)

        self.assertEqual(1, len(self.writes()))
        request = self.end_stop()["request"]
        self.assertEqual((CONVOY, tip, self.PACK_DIGEST, "/var/packs/fx-spec/fx-convoy/index.html"),
                         tuple(request[name] for name in ("bead", "commit", "digest", "page")))
        self.assertIn("at", request)
        self.assertFalse(self.show()["unruled"])
        # Raised once: the same request again writes nothing.
        before = self.tracker.read_bytes()
        self.assertEqual({}, self.ok("end-stop-raised", CONVOY, "--bead", CONVOY)["written"])
        self.assertEqual(before, self.tracker.read_bytes())

    def test_end_stop_raised_refuses_a_convoy_that_is_not_stopped_or_has_no_non_conforming_pack(self):
        tip, base = self.integrated()
        raised = ("end-stop-raised", CONVOY, "--bead", CONVOY)
        self.assert_refused_and_nothing_written(*raised, mention="pas arrêtés")
        self.ok("set-counter", CONVOY, "--counter", "end_rounds", "--value", "2")
        self.ok(*self.red_of_the_end(tip, base))
        self.assert_refused_and_nothing_written(*raised, mention="Evidence Pack")
        self.ok(*self.pack(tip))
        self.assert_refused_and_nothing_written(*raised, mention="non conforme")
        self.ok(*self.pack(tip, "--non-conforming"))
        self.assert_refused_and_nothing_written("end-stop-raised", CONVOY, "--bead", "pas un bead", mention="bead")
        self.assert_refused_and_nothing_written("end-stop-raised", CONVOY, mention="bead")
        self.assertNotIn("request", self.end_stop())

    def test_a_stop_of_the_rounds_of_the_end_written_outside_the_command_is_a_state_without_rule(self):
        tip, _ = self.integrated()
        for record in ({"reason": "lassitude", "detail": "x", "commit": tip, "source": "regression", "rounds": 2, "at": "x"},
                       {"reason": "end_rounds_exhausted", "commit": tip}):
            with self.subTest(record=record):
                self.edit_tracker(CONVOY, **{"gc.flow.end_stop": json.dumps(record)})

                shown = self.show(expect=EXIT_UNRULED)

                self.assertIn("unruled", shown["convoy"]["end_stop"])
                self.assertIn("gc.flow.end_stop", [entry["field"] for entry in shown["convoy"]["unruled"]])

    def test_the_end_of_the_spec_of_an_unmarked_convoy_is_not_recorded(self):
        before = self.tracker.read_text()

        for command in (("set-item-repair", CONVOY, T1, "--repair", T2),
                        ("record-spec-end", CONVOY, "--commit", ABSENT_COMMIT, "--protected", ABSENT_COMMIT,
                         "--file", self.spec_end_file()),
                        ("open-end-review", CONVOY, "--commit", ABSENT_COMMIT, "--file", self.end_request_file()),
                        ("record-end-review", CONVOY, "--file", self.end_review_file(ABSENT_COMMIT)),
                        ("stop-end-review", CONVOY, "--reason", "end_review_no_result", "--detail", "x"),
                        ("end-stop-raised", CONVOY, "--bead", CONVOY),
                        ("record-delivered", CONVOY, "--commit", ABSENT_COMMIT, "--pack-digest", DIGEST)):
            with self.subTest(command=command[0]):
                proc = self.run_tool(*command)
                self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual(before, self.tracker.read_text())


if __name__ == "__main__":
    unittest.main()
