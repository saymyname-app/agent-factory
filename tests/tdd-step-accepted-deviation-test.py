#!/usr/bin/env python3
"""bin/tdd-step amend on another ticket's frozen test that names no
successor (af-axppkz): the operator's answer that accepts the deviation of
the ticket's own Planning Exception lets it change, once, the one frozen
test the « Écarts » of its Ticket Handoff name, and the succession records
that answer; without such an answer, or for another test, amend refuses as
before. Same harness as tests/tdd-step-test.py, loaded from there: command
lines on a fake tracker state, the Delivery Fixture City launched for real,
the proofs filed for real."""

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


# The module is bound, not its classes: unittest would run the cases of
# tests/tdd-step-test.py here too.
first = load("tdd-step-test.py")

RAISED_AT, PARKED_AT = "2026-11-09T22:46:41Z", "2026-11-09T22:48:38Z"
ANSWERED_AT, LIFTED_AT, HANDOFF_AT = "2026-11-10T07:54:07Z", "2026-11-10T07:54:22Z", "2026-11-10T08:05:14Z"
# The words of R18's Handoff (af-gnplfy): the frozen test by its file name.
DEVIATION = ("Le cas HealthTest du test figé de fx-t1, test_health.py, est changé par A2 pour nommer le ticket : "
             "écart accepté par Benjamin (option c).")


class AcceptedDeviationTest(first.TddStepTest):
    def health_changed_by_a2(self):
        """fx-t1 froze a health test that names no successor; A2 froze its
        own test, then changed fx-t1's along with its code."""
        self.successor_frozen(owner_health=first.HEALTH_TEST)
        self.commit("code de A2 et test de fx-t1 repris", {
            first.APP: self.successor_app(), first.HEALTH_FILE: first.HEALTH_TEST + "# A2 names the ticket.\n"})

    def answer(self, option="c", deviation=DEVIATION):
        """A2's Planning Exception, its parking lifted by the operator's
        `option` (c accepts its deviation), and its Handoff's « Écarts »."""
        state = json.loads(self.tracker.read_text())
        state["beads"][first.SUCCESSOR]["metadata"].update({
            "gc.escalation_response_actor": "benjamin",
            "gc.escalation_response_at": ANSWERED_AT,
            "gc.escalation_response_option": option,
            "gc.needs_benjamin": "A2 : tdd-step amend refuse l'écart accepté",
            "gc.flow.planning_exceptions": json.dumps({"entries": [{
                "kind": "semantic", "summary": "le test figé de fx-t1 contredit A2", "anchors": [],
                "accept_option": "c", "prior_response_at": None, "at": RAISED_AT}]}),
            "gc.flow.park_lifts": json.dumps({"entries": [{
                "at": LIFTED_AT, "cause": "planning_exception", "detail": "Planning Exception (semantic) sur A2",
                "option": option, "parked_at": PARKED_AT, "request": first.SUCCESSOR, "resumes": 0}]}),
            "gc.flow.handoff": json.dumps({
                "sections": {"deviations": [deviation]}, "partial": True,
                "commit": self.git("rev-parse", "HEAD"), "at": HANDOFF_AT}),
        })
        self.tracker.write_text(json.dumps(state))

    def test_the_accepted_deviation_lets_the_ticket_amend_the_frozen_test_it_names_once(self):
        self.health_changed_by_a2()
        self.answer()

        self.ok("amend", first.SUCCESSOR, "--reason", "écart accepté (option c) : A2 reprend le test de fx-t1")

        _, proof = self.piece("tdd_amendment", first.SUCCESSOR)
        self.assertEqual({first.HEALTH_FILE: {
            "owner": first.SLICE, "digest": first.sha256_of(self.repo / first.HEALTH_FILE),
            "accepted": {"request": first.SUCCESSOR, "option": "c", "lifted_at": LIFTED_AT, "raised_at": RAISED_AT,
                         "actor": "benjamin", "answered_at": ANSWERED_AT, "deviation": DEVIATION}}},
            proof["amendment"]["succession"])
        self.ok("green", first.SUCCESSOR)
        self.open_correction_after_the_amendment(first.SUCCESSOR)
        self.commit("test de fx-t1 changé une seconde fois", {
            first.HEALTH_FILE: first.HEALTH_TEST + "# A2 names the ticket.\n# encore\n"})
        error = self.refused("amend", first.SUCCESSOR, "--reason", "seconde consommation de l'écart accepté")
        self.assertIn(f"test gelé du ticket {first.SLICE} déjà changé une fois par {first.SUCCESSOR}", error)

    def test_without_an_accepting_answer_amend_refuses_as_before(self):
        self.health_changed_by_a2()
        expected = f"test gelé du ticket {first.SLICE} modifié : {first.HEALTH_FILE} ; il ne nomme pas {first.SUCCESSOR}"

        self.assertIn(expected, self.refused("amend", first.SUCCESSOR, "--reason", "aucune réponse"))
        # Answered by an option that does not accept the deviation.
        self.answer(option="a")
        self.assertIn(expected, self.refused("amend", first.SUCCESSOR, "--reason", "réponse a, pas c"))

    def test_the_accepted_deviation_does_not_authorize_another_frozen_test(self):
        self.health_changed_by_a2()
        self.answer(deviation="Le test figé de fx-t1, test_count.py, est changé par A2 : écart accepté (option c).")

        error = self.refused("amend", first.SUCCESSOR, "--reason", "l'écart accepté nomme un autre test")

        self.assertIn(f"test gelé du ticket {first.SLICE} modifié : {first.HEALTH_FILE} ; il ne nomme pas "
                      f"{first.SUCCESSOR}", error)


def load_tests(loader, tests, pattern):
    """Only the cases written here: those of the harness run in their own file."""
    return unittest.TestSuite(AcceptedDeviationTest(name) for name in loader.getTestCaseNames(AcceptedDeviationTest)
                              if name in vars(AcceptedDeviationTest))


if __name__ == "__main__":
    unittest.main()
