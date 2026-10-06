#!/usr/bin/env python3
"""bin/convoy-state on a fake tracker state (T33, af-p4d6ec; Spec af-wf4w5r
§0 rule 2, Testing Decisions seam 2): one test per refusal and per pass, each
refusal re-reading the tracker to prove nothing was written. Only the command
line is exercised; ticket branches live in a throwaway Git repository."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "convoy-state"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY = "fx-convoy"
T1 = "fx-t1"
T2 = "fx-t2"
ABSENT_COMMIT = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "sha256:" + "ab" * 32

EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4


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

    def run_tool(self, *args):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), env=self.env, text=True, capture_output=True,
        )

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

    def assert_refused_and_nothing_written(self, *args, mention=None):
        before_bytes = self.tracker.read_bytes()
        before_show = self.run_tool("show", CONVOY, "--repo", self.repo).stdout
        writes_before = self.write_log.read_text() if self.write_log.exists() else ""
        proc = self.run_tool(*args)
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
        for kind in ("test_review", "code_review", "evaluation", "fidelity"):
            self.ok("set-verdict", CONVOY, T1, "--kind", kind, "--state", "favorable", "--commit", tip)
        self.ok("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "unfavorable", "--commit", tip)
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.ok("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.ok("bump-counter", CONVOY, "--counter", "end_rounds")
        self.ok("add-evidence", CONVOY, T1, "--piece", "red_proof", "--digest", DIGEST, "--commit", tip)
        self.ok("record-gate", CONVOY, T1, "--gate", "ticket_end", "--commit", tip)
        self.edit_tracker(T1, status="closed")

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
        self.assertEqual({"test_review", "code_review", "evaluation", "fidelity"}, set(t1["verdicts"]))
        for kind, state in (("test_review", "favorable"), ("code_review", "favorable"),
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
        with ThreadPoolExecutor(max_workers=8) as pool:
            procs = list(pool.map(
                lambda _: self.run_tool("bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes"),
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

    def test_gate_outside_the_closed_list_or_ticket_end_without_commit_is_refused(self):
        self.started_ticket()
        self.assert_refused_and_nothing_written("record-gate", CONVOY, T1, "--gate", "by-hand", mention="by-hand")
        self.assert_refused_and_nothing_written("record-gate", CONVOY, T1, "--gate", "ticket_end", mention="commit")

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
        self.assert_refused_and_nothing_written("mark", T1, mention=T1)

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

        proc = subprocess.run((str(TOOL), "ticket", T1, "--bead-json", "-"), env=env, text=True,
                              capture_output=True, input=json.dumps(bead))

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["new_flow"])

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
        self.ok("record-gate", CONVOY, T1, "--gate", "ticket_end", "--commit", tip)
        self.edit_tracker(T1, status="closed")
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


if __name__ == "__main__":
    unittest.main()
