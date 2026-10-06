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

    def seed(self, tickets=(T1, T2)):
        beads = {CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                          "metadata": {"gc.spec_id": "fx-spec"}, "tracks": list(tickets)}}
        for ticket in tickets:
            beads[ticket] = {"title": f"ticket {ticket}", "status": "open", "issue_type": "task",
                             "metadata": {"gc.ticket_kind": "vertical_slice"}}
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
        state["beads"]["fx-t3"] = {"title": "ajouté par patch", "status": "open", "issue_type": "task"}
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


if __name__ == "__main__":
    unittest.main()
