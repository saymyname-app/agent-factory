#!/usr/bin/env python3
"""The records of bin/convoy-state that follow Benjamin's answer (T30, Spec
§9, §11), on a fake tracker state: the promotion to the protected branch,
the acceptance a red replay voids, the closing of the convoy by command,
and the refusal of every write on a convoy closed that way. One test per
pass and per refusal; each refusal re-reads the tracker to prove nothing
was written."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "convoy-state"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
CONVOY, T1 = "fx-convoy", "fx-t1"
EXIT_REFUSED, EXIT_UNRULED = 1, 3
JUDGED, MERGED, PROTECTED, TAKEOVER = "a" * 40, "b" * 40, "c" * 40, "d" * 40
DIGEST = "sha256:" + "e" * 64
WORDS = "Tout est bon, j'accepte."
REASON = "Le besoin a disparu."
AT = "2099-01-01T00:00:00Z"


def answer(response, **fields):
    return {"response": response, "approver": "benjamin", "commit": JUDGED, "pack": DIGEST, "at": AT, **fields}


ACCEPTED = answer("accepted", words=WORDS)
ABANDONED = answer("abandoned", reason=REASON)
FINDINGS = answer("findings", words="Le titre manque.", findings=[
    {"text": "Le titre manque.", "route": "later"}])


class ConvoyCloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="convoy-close-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
        }
        self.tracker.write_text(json.dumps({"beads": {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": "fx-spec"}, "tracks": [T1]},
            T1: {"title": "ticket 1", "status": "open", "issue_type": "task",
                 "metadata": {"gc.ticket_kind": "prefactoring"}},
        }}))
        self.ok("mark", CONVOY)

    # --- harness ------------------------------------------------------------

    def run_tool(self, *args):
        return subprocess.run((str(TOOL), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)

    def ok(self, *args):
        proc = self.run_tool(*args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def show(self, expect=0):
        proc = self.run_tool("show", CONVOY, "--repo", self.tmp)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)["convoy"]

    def bead(self, bead_id=CONVOY):
        return json.loads(self.tracker.read_text())["beads"][bead_id]

    def edit(self, status=None, **metadata):
        state = json.loads(self.tracker.read_text())
        bead = state["beads"][CONVOY]
        if status is not None:
            bead["status"] = status
        bead["metadata"].update({key.replace("__", "."): value for key, value in metadata.items()})
        self.tracker.write_text(json.dumps(state))

    def judged(self, *answers, delivered=True):
        """The convoy as bin/owner-answer leaves it: Delivered, requested,
        with Benjamin's answers."""
        metadata = {"gc.flow.judgement": json.dumps({"verdicts": [], "answers": list(answers)})}
        if delivered:
            metadata["gc.flow.acceptance"] = json.dumps({"commit": JUDGED, "at": AT})
        self.edit(**metadata)

    def promote(self, *extra):
        return self.ok("record-promotion", CONVOY, "--judged", JUDGED, "--merged", MERGED, "--protected", PROTECTED,
                       "--tip", JUDGED, *extra)

    def refused(self, *args, mention=None):
        before = self.tracker.read_bytes()
        writes = self.write_log.read_text() if self.write_log.exists() else ""
        proc = self.run_tool(*args)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout)["error"]
        if mention:
            self.assertIn(mention, error)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(writes, self.write_log.read_text() if self.write_log.exists() else "")
        return error

    def writes(self):
        return [line for line in self.write_log.read_text().splitlines() if line.strip()]

    # --- the promotion ------------------------------------------------------

    def test_the_promotion_notes_the_judged_and_the_merged_commit_and_show_reads_them_back(self):
        self.judged(ACCEPTED)
        self.write_log.write_text("")

        self.promote()

        self.assertEqual(1, len(self.writes()))
        promotion = self.show()["promotion"]
        self.assertEqual((JUDGED, MERGED, PROTECTED, JUDGED),
                         (promotion["judged"], promotion["merged"], promotion["protected"], promotion["tip"]))
        self.assertIn("at", promotion)

    def test_the_promotion_of_a_taken_up_tip_keeps_the_commit_benjamin_judged(self):
        self.judged(ACCEPTED)

        self.ok("record-promotion", CONVOY, "--judged", JUDGED, "--merged", MERGED, "--protected", PROTECTED,
                "--tip", TAKEOVER)

        promotion = self.show()["promotion"]
        self.assertEqual((JUDGED, TAKEOVER), (promotion["judged"], promotion["tip"]))

    def test_a_promotion_is_refused_without_an_accepted_answer(self):
        for answers in ((), (FINDINGS,), (ABANDONED,)):
            with self.subTest(answers=[entry["response"] for entry in answers]):
                self.judged(*answers)
                self.refused("record-promotion", CONVOY, "--judged", JUDGED, "--merged", MERGED,
                             "--protected", PROTECTED, "--tip", JUDGED, mention="accepté")

    def test_a_promotion_is_refused_for_another_commit_than_the_one_benjamin_accepted(self):
        self.judged(ACCEPTED)

        self.refused("record-promotion", CONVOY, "--judged", TAKEOVER, "--merged", MERGED, "--protected", PROTECTED,
                     "--tip", TAKEOVER, mention=JUDGED[:12])

    def test_a_promotion_is_recorded_once(self):
        self.judged(ACCEPTED)
        self.promote()

        self.refused("record-promotion", CONVOY, "--judged", JUDGED, "--merged", TAKEOVER, "--protected", PROTECTED,
                     "--tip", JUDGED, mention="déjà")

    # --- the acceptance a red replay voids ------------------------------------

    def test_a_voided_acceptance_withdraws_delivered_and_the_request_and_lets_benjamin_answer_again(self):
        self.judged(ACCEPTED)
        self.edit(gc__flow__counter__end_rounds="2")
        self.write_log.write_text("")

        self.ok("void-acceptance", CONVOY, "--cause", "conflict")

        self.assertEqual(1, len(self.writes()))
        shown = self.show()
        last = shown["judgement"]["answers"][-1]
        self.assertEqual(("accepted", "conflict"), (last["response"], last["voided"]["cause"]))
        self.assertIsNone(shown["acceptance"])
        self.assertIsNone(shown["delivered"])
        self.assertNotIn("gc.flow.acceptance", self.bead()["metadata"])
        # Benjamin's next answer is no longer refused as following an accepted Outcome.
        proc = self.run_tool("record-owner-answer", CONVOY, "--response", "accepted", "--approver", "benjamin",
                             "--words", WORDS, "--commit", JUDGED, "--pack-digest", DIGEST)
        self.assertNotIn("rien ne le rouvre", proc.stdout)

    def test_an_answer_may_follow_a_voided_acceptance_in_the_judgement(self):
        self.judged(ACCEPTED)
        self.ok("void-acceptance", CONVOY, "--cause", "regression")
        voided = self.show()["judgement"]["answers"][0]

        self.judged(voided, ACCEPTED, delivered=False)

        answers = self.show()["judgement"]["answers"]
        self.assertEqual(["accepted", "accepted"], [entry["response"] for entry in answers])
        self.assertNotIn("voided", answers[1])

    def test_voiding_is_refused_without_an_accepted_answer_and_for_an_unknown_cause(self):
        self.judged(FINDINGS)
        self.refused("void-acceptance", CONVOY, "--cause", "conflict", mention="accepté")
        self.judged(ACCEPTED)
        self.refused("void-acceptance", CONVOY, "--cause", "humeur", mention="cause")

    def test_a_promoted_acceptance_is_not_voided_and_a_voided_one_is_not_promoted(self):
        self.judged(ACCEPTED)
        self.promote()
        self.refused("void-acceptance", CONVOY, "--cause", "conflict", mention="fusionné")

        state = json.loads(self.tracker.read_text())
        del state["beads"][CONVOY]["metadata"]["gc.flow.promotion"]
        self.tracker.write_text(json.dumps(state))
        self.ok("void-acceptance", CONVOY, "--cause", "conflict")
        self.refused("record-promotion", CONVOY, "--judged", JUDGED, "--merged", MERGED, "--protected", PROTECTED,
                     "--tip", JUDGED, mention="accepté")
        self.refused("close-convoy", CONVOY, mention="accepté")

    # --- the two closings ---------------------------------------------------------

    def test_an_accepted_convoy_closes_with_benjamins_words_in_one_write_and_is_ruled(self):
        self.judged(ACCEPTED)
        self.edit(gc__flow__delivered=json.dumps({"commit": JUDGED, "protected": PROTECTED, "pack": DIGEST,
                                                  "version": "spec-end/v4", "at": AT}))
        self.assertEqual("delivered", self.show()["outcome"])
        self.promote()
        self.assertEqual("delivered", self.show()["outcome"])
        self.write_log.write_text("")

        closed = self.ok("close-convoy", CONVOY)

        self.assertTrue(closed["closed"])
        self.assertEqual(1, len(self.writes()))
        shown = self.show()
        self.assertEqual(("closed", [], "accepted"), (shown["status"], shown["unruled"], shown["outcome"]))
        self.assertEqual(("accepted", WORDS, "benjamin"),
                         (shown["closed"]["how"], shown["closed"]["said"], shown["closed"]["approver"]))
        listed = self.ok("list")
        self.assertEqual(([], [], [CONVOY]), (listed["convoys"], listed["closed_outside"], listed["closed"]))

    def test_an_accepted_convoy_does_not_close_before_its_merge(self):
        self.judged(ACCEPTED)

        self.refused("close-convoy", CONVOY, mention="fusion")

    def test_an_abandoned_convoy_closes_with_the_reason_and_without_any_merge(self):
        self.judged(ABANDONED)

        self.ok("close-convoy", CONVOY)

        shown = self.show()
        self.assertEqual(("closed", [], "abandoned"), (shown["status"], shown["unruled"], shown["outcome"]))
        self.assertEqual(("abandoned", REASON), (shown["closed"]["how"], shown["closed"]["said"]))
        self.assertIsNone(shown["promotion"])
        self.assertEqual("open", self.bead(T1)["status"])

    def test_a_convoy_without_a_final_answer_does_not_close(self):
        for answers in ((), (FINDINGS,)):
            with self.subTest(answers=len(answers)):
                self.judged(*answers)
                self.refused("close-convoy", CONVOY, mention="ni « accepté » ni « abandonné »")

    def test_a_judged_convoy_closed_by_hand_is_still_unruled(self):
        self.judged(ACCEPTED)
        self.promote()
        self.edit(status="closed")

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("fermé hors commande", shown["unruled"][0]["reason"])
        self.assertEqual([CONVOY], self.ok("list")["closed_outside"])

    def test_a_convoy_reopened_by_hand_after_its_closing_is_unruled(self):
        self.judged(ABANDONED)
        self.ok("close-convoy", CONVOY)
        self.edit(status="open")

        shown = self.show(expect=EXIT_UNRULED)

        self.assertIn("rouvert", shown["unruled"][0]["reason"])

    # --- nothing reopens it ---------------------------------------------------------

    def test_no_write_of_the_flow_touches_the_convoy_or_a_ticket_of_an_accepted_outcome(self):
        self.judged(ACCEPTED)
        self.promote()
        self.ok("close-convoy", CONVOY)

        for command in (
                ("mark", CONVOY),
                ("close-convoy", CONVOY),
                ("void-acceptance", CONVOY, "--cause", "conflict"),
                ("record-owner-answer", CONVOY, "--response", "findings", "--approver", "benjamin", "--words", "Non.",
                 "--commit", JUDGED, "--pack-digest", DIGEST),
                ("set-branch", CONVOY, T1, "--branch", "ticket/t1"),
                ("close-ticket", CONVOY, T1, "--commit", JUDGED, "--file", os.devnull),
                ("record-delivered", CONVOY, "--commit", JUDGED, "--pack-digest", DIGEST)):
            with self.subTest(command=command[0]):
                error = self.refused(*command, mention="rien ne le rouvre")
                self.assertIn("accepté", error)
                self.assertIn("travail nouveau", error)

    def test_no_write_of_the_flow_touches_an_abandoned_convoy(self):
        self.judged(ABANDONED)
        self.ok("close-convoy", CONVOY)

        error = self.refused("set-branch", CONVOY, T1, "--branch", "ticket/t1", mention="rien ne le rouvre")

        self.assertIn("abandonné", error)


if __name__ == "__main__":
    unittest.main()
