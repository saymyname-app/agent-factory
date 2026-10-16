#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/convoy-advance-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); what is left is the passes each case verifies
"""bin/convoy-advance on a fake tracker state: the cases of what a pass does with
a finished ticket before its merge -- the code review (T14), the Ticket
Evaluation on the launched product (T15), the one correction round (T17)
and the review of the criterion tests left without result (T13).

They were in tests/convoy-advance-test.py (af-vqew1x: no test file should hold a lot of a CI run alone).
The harness is the one of that file, loaded from there: the seeded tracker,
the settings, the stand-ins of the doors and the set-up helpers."""

import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: unittest collects the test classes
# named at the top of a file, and the cases of that file run there.
first = load("convoy-advance-test.py")
CONVOY = first.CONVOY
ESCALATION = first.ESCALATION
STATE = first.STATE
EXIT_REFUSED = first.EXIT_REFUSED
T1 = first.T1


class ConvoyAdvanceTest(first.ConvoyAdvanceHarness):
    # --- the code of a finished ticket is reviewed before its merge (T14) -------

    def test_a_pass_sends_a_finished_ticket_to_the_reviewer_role_and_merges_it_once_reviewed(self):
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "review", tip)], [(entry["ticket"], entry["kind"], entry["commit"])
                                                 for entry in self.code_review_of(answer)["launched"]])
        (call,) = self.code_review_launches()
        self.assertEqual(["--rig", "fx-rig", "--formula", "mol-code-review", "--role", "reviewer"], call[1:])
        self.assertEqual("favorable", self.shown(T1)["code_review"]["state"]["verdict"])
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])

    def test_a_pass_merges_nothing_of_a_ticket_whose_code_review_gave_no_verdict(self):
        base = self.integrated()
        self.code_reviewed("silent")
        self.advance(CONVOY)
        self.finished(T1)

        first = self.advance(CONVOY)
        second = self.advance(CONVOY)

        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(first)["launched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(second)["pending"]])
        for answer in (first, second):
            self.assertEqual(([], [T1]), (self.integration_of(answer)["merged"],
                                          [entry["id"] for entry in self.integration_of(answer)["waiting"]]))
        self.assertTrue(second["ok"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        self.assertEqual(1, len(self.code_review_launches()))

    def test_a_pass_stops_a_ticket_whose_code_review_gave_no_result_twice_and_raises_it_once(self):
        base = self.integrated()
        self.code_reviewed("silent", timeout_seconds=0)
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)

        relaunched = self.advance(CONVOY)
        stopped = self.advance(CONVOY)
        after = self.advance(CONVOY)

        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(relaunched)["relaunched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(stopped)["stopped"]])
        self.assertIsNone(self.code_review_of(after))
        self.assertEqual(2, len(self.code_review_launches()))
        stop = json.loads(self.bead(T1)["metadata"]["gc.flow.stop"])
        self.assertEqual("code_review_no_result", stop["reason"])
        self.assertIn("raised", stop)
        listed = self.run_ok(ESCALATION, "list").stdout
        self.assertEqual(1, listed.count(f"{T1} — "), listed)
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_code_review_that_cannot_be_sent_fails_the_pass_and_merges_nothing(self):
        base = self.integrated()
        self.code_reviewed("door-refuses")
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("rôle relecteur", self.code_review_of(answer)["refused"][0]["reason"])
        self.assertEqual([], self.integration_of(answer)["merged"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    # --- a finished ticket is evaluated on the launched product before its merge (T15) ---

    def test_a_pass_checks_that_the_product_of_a_finished_prefactoring_starts_and_merges_it(self):
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, tip, "favorable")], [(entry["ticket"], entry["commit"], entry["verdict"])
                                                    for entry in self.evaluation_of(answer)["started"]])
        # No Evaluator session for a prefactoring, and the review is sent by the same pass.
        self.assertEqual([], self.evaluation_launches())
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(answer)["launched"]])
        evaluation = self.shown(T1)["evaluation"]
        self.assertEqual(("startup", True, tip), tuple(evaluation["rounds"][0][name] for name in ("kind", "started", "commit")))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])
        self.assertEqual([], list((self.tmp / "launches").rglob("*.json")))
        self.assertIsNone(self.evaluation_of(self.advance(CONVOY)))

    def test_an_evaluation_that_cannot_run_fails_the_pass_and_merges_nothing(self):
        base = self.integrated()
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        del settings["evaluation"]
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("la Ticket Evaluation n'est pas réglée", self.evaluation_of(answer)["error"])
        self.assertEqual([], self.integration_of(answer)["merged"])
        self.assertIn("aucune Ticket Evaluation rendue", self.integration_of(answer)["waiting"][0]["reason"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    # --- one correction round, then the ticket stops (T17) ----------------------

    def test_a_pass_sends_a_ticket_its_review_refused_to_one_author_session_and_merges_nothing(self):
        base, tip = self.refused_by_its_review("works")

        first = self.advance(CONVOY)
        second = self.advance(CONVOY)

        # The review and the control of the product run in the same pass, on
        # the same tip; the round is opened once both have answered there.
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(first)["launched"]])
        self.assertEqual([(T1, tip)], [(entry["ticket"], entry["commit"]) for entry in self.evaluation_of(first)["started"]])
        self.assertEqual([(T1, tip)], [(entry["ticket"], entry["commit"]) for entry in self.correction_of(first)["launched"]])
        (call,) = self.correction_launches()
        self.assertEqual(["--rig", "fx-rig", "--formula", "mol-ticket-correction", "--role", "author"], call[1:])
        self.assertEqual([T1], [entry["ticket"] for entry in self.correction_of(second)["pending"]])
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown(T1)["counters"])
        brief = json.loads((self.tmp / "correction-briefs" / "brief-1.json").read_text())
        self.assertEqual(["F1.1"], [finding["id"] for finding in brief["code_review"]["blocking_findings"]])
        for answer in (first, second):
            self.assertEqual([], self.integration_of(answer)["merged"])
            self.assertTrue(answer["ok"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_pass_stops_a_ticket_still_refused_after_its_round_and_raises_it_once(self):
        base, _ = self.refused_by_its_review("leaves")
        self.advance(CONVOY)

        stopped = self.advance(CONVOY)
        after = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "stop": "still_refused"}], self.correction_of(stopped)["stopped"])
        self.assertIsNone(self.correction_of(after))
        self.assertEqual(1, len(self.correction_launches()))
        stop = json.loads(self.bead(T1)["metadata"]["gc.flow.stop"])
        self.assertEqual("still_refused", stop["reason"])
        self.assertIn("raised", stop)
        listed = self.run_ok(ESCALATION, "list").stdout
        self.assertEqual(1, listed.count(f"{T1} — "), listed)
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        self.assertTrue(after["ok"])

    def test_a_correction_round_that_cannot_be_sent_fails_the_pass(self):
        base, _ = self.refused_by_its_review("door-refuses")

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("rôle auteur", self.correction_of(answer)["refused"][0]["reason"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_refused_ticket_without_settings_of_the_correction_round_fails_the_pass(self):
        self.refused_by_its_review("works")
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        del settings["correction"]
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertIn("le tour de correction n'est pas réglé", self.correction_of(answer)["refused"][0]["reason"])
        self.assertEqual([], self.correction_launches())

    def test_a_pass_reports_no_correction_round_for_tickets_nothing_refused(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertIsNone(self.correction_of(answer))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])

    # --- no review of the criterion tests before the freeze (ADR-0030 L3) -------

    def test_a_pass_starts_no_test_review_even_on_one_left_open_before_l3(self):
        self.review_open(launches=1)
        before = self.bead(self.R1)["metadata"]["gc.flow.test_review"]

        answer = self.advance(self.REVIEWED)

        self.assertIsNone(self.review_of(answer))
        self.assertEqual(before, self.bead(self.R1)["metadata"]["gc.flow.test_review"])
        self.assertNotIn("gc.flow.stop", self.bead(self.R1)["metadata"])


if __name__ == "__main__":
    unittest.main()
