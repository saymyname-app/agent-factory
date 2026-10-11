#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/convoy-stops-fixture-city-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); each case starts from a convoy walked to its Delivered Outcome and launches the real product
"""The acceptance of the Outcome (T28, af-3x6zkb; Spec af-wf4w5r §11), on the
convoy the reference driver of the Fixture City Oracle walks to the end of
its Spec: the Acceptance Request sent once at the Delivered Outcome, the
delay that accepts nothing, the outage of a session, the session of a
« non conforme » request.

These cases were in tests/convoy-stops-fixture-city-test.py (af-vqew1x: that
file, alone on one core, set the duration of a CI run). The harness
FixtureCityWalk is loaded from there; the cases of the owner's answer and of
the promotion are in tests/owner-answer-promotion-fixture-city-test.py."""

import html
import importlib.machinery
import importlib.util
import json
import subprocess
import time
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
stops = load("convoy-stops-fixture-city-test.py")
ADVANCE = stops.ADVANCE
ESCALATION = stops.ESCALATION
SESSION = stops.SESSION
OWNER = stops.OWNER
EXIT_REFUSED = stops.EXIT_REFUSED
THIRTY_DAYS = stops.THIRTY_DAYS
CLOCKS = stops.CLOCKS
answers = stops.answers


class AcceptanceOnTheFixtureCity(stops.FixtureCityWalk):
    """T28 (af-3x6zkb; Spec §11) on the convoy the reference driver walks to
    the end of its Spec."""

    # --- the Acceptance Request ---------------------------------------------

    def test_the_pass_that_reaches_delivered_sends_one_acceptance_request_with_the_dossier_and_never_again(self):
        delivered = self.walk_to_delivered(real=True)

        request = self.assert_one_acceptance_request(delivered)
        mails = [entry for entry in self.written() if entry[0] == "mail"]
        self.assertEqual([["mail", "human", f"NEEDS BENJAMIN: {self.convoy}"]], mails)

        # Whatever the number of passes: nothing more is sent, nothing is written.
        before, log = self.tracker.read_bytes(), self.write_log.read_bytes()
        for _ in range(2):
            self.assertTrue(self.order_pass()["idle"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(log, self.write_log.read_bytes())
        self.assertEqual([request], self.requests())
        self.assertEqual(delivered, self.shown()["convoy"]["delivered"])

    def test_thirty_days_without_an_answer_the_outcome_is_still_delivered_nothing_merged_nothing_closed(self):
        delivered = self.walk_to_delivered()
        request = self.assert_one_acceptance_request(delivered)
        integration = self.shown()["convoy"]["integration"]["branch"]
        tips = (self.tip("main"), self.tip(integration))
        self.assertEqual(delivered["commit"], tips[1])
        self.assertNotEqual(*tips)
        before, log = self.tracker.read_bytes(), self.write_log.read_bytes()
        acceptance = self.shown()["convoy"]["acceptance"]

        # Every clock a tool of the flow reads is thirty days later; the request got no answer.
        later = str(int(time.time()) + THIRTY_DAYS)
        self.clock = {name: later for name in CLOCKS}
        self.assertIn("nothing due", self.tool_ok(ESCALATION, "sweep").stdout)
        for _ in range(3):
            self.order_pass()
        self.tool_ok(ESCALATION, "sweep")

        shown = self.shown()
        # Still Delivered, at the same commit, and not accepted: the request still waits, alone.
        self.assertEqual((delivered, acceptance), (shown["convoy"]["delivered"], shown["convoy"]["acceptance"]))
        self.assertEqual([request], self.requests())
        gate = json.loads(self.tool_ok(ROOT / "bin" / "spec-end", "check", self.convoy, "--repo", self.repo).stdout)
        self.assertEqual((True, delivered["commit"]), (gate["delivered"], gate["commit"]))
        # Nothing merged: the protected branch and the integration branch are where they were.
        self.assertEqual(tips, (self.tip("main"), self.tip(integration)))
        # Nothing closed, nothing cleared, nothing written at all.
        bead = json.loads(self.tracker.read_text())["beads"][self.convoy]
        self.assertNotEqual("closed", bead["status"])
        self.assertIn("Acceptance Request", bead["metadata"]["gc.needs_benjamin"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(log, self.write_log.read_bytes())
        self.assertFalse(shown["unruled"])

    # --- the outage of an Acceptance Session ----------------------------------

    def test_a_product_that_does_not_start_is_an_outage_and_the_next_pass_publishes_its_one_repair(self):
        delivered = self.walk_to_delivered(inject="story-not-observed")
        request = self.assert_one_acceptance_request(delivered)
        tracked = [ticket["id"] for ticket in self.shown()["tickets"]]
        broken = json.loads(self.profile.read_text())
        broken["launch"]["recipe"] = ["{python}", "-c", "import sys; sys.exit(3)"]
        profile = self.workspace / "broken-descriptor.json"
        profile.write_text(json.dumps(broken))

        proc = self.tool(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", profile)

        # An outage, not a judgment: said, no session, no address; noted on the convoy and nowhere else.
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertEqual((False, True), (answer["ok"], answer["outage"]))
        self.assertIn("panne", answer["error"])
        self.assertNotIn("address", answer)
        self.assertNotEqual(0, self.tool(SESSION, "close", self.convoy).returncode)
        outage = self.shown()["convoy"]["acceptance"]["panne"]
        self.assertTrue(outage["detail"])
        self.assertNotIn("ticket", outage)
        self.assertEqual(tracked, [ticket["id"] for ticket in self.shown()["tickets"]])
        self.assertEqual([request], self.requests())

        self.order_pass()

        # One `repair` more in the convoy, published by code, and the outage names it.
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual(("repair", "open"), (repair["kind"], repair["status"]))
        self.assertEqual(repair["id"], shown["convoy"]["acceptance"]["panne"]["ticket"])
        self.assertEqual(outage, {key: value for key, value in shown["convoy"]["acceptance"]["panne"].items() if key != "ticket"})
        self.assertFalse(shown["unruled"])

        # Whatever the number of passes: no second repair. The session stays refused meanwhile.
        self.order_pass()
        after = self.shown()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in after["tickets"]])
        self.assertEqual(repair["id"], after["convoy"]["acceptance"]["panne"]["ticket"])
        before = self.tracker.read_bytes()
        refused = self.tool(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", self.profile)
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout + refused.stderr)
        self.assertFalse(json.loads(refused.stdout)["ok"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([request], self.requests())

    # --- the Acceptance Session of a « non conforme » request ------------------

    def test_the_session_of_a_non_conforme_request_launches_the_product_with_three_issues_and_never_accepted(self):
        # The false state of the stopped rounds: two rounds of the end consumed, and the Outcome
        # Evaluation refuses the tip once more (the second user story is not served).
        stop = self.walk("story-not-observed", lambda convoy: (convoy["end_stop"] or {}).get("request") and convoy["end_stop"],
                         rounds_consumed=2)
        self.assertEqual("end_rounds_exhausted", stop["reason"])
        [request] = self.requests()
        self.assertIn("« non conforme »", request)
        self.assertTrue(request.endswith(f" — dossier : {stop['request']['page']}"), request)
        self.assertIsNone(self.shown()["convoy"]["delivered"])
        integration = self.shown()["convoy"]["integration"]["branch"]

        opened = json.loads(self.tool_ok(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", self.profile).stdout)

        # Same door, same session: the product at the commit of the dossier, the three issues, no « accepté ».
        self.assertEqual(("non_conforme", self.tip(integration), stop["request"]["page"]),
                         (opened["kind"], opened["commit"], opened["page"]))
        self.assertEqual(["relancer", "planification", "abandon"], [issue["response"] for issue in opened["issues"]])
        self.assertNotIn("accept", json.dumps(opened["issues"], ensure_ascii=False).lower())
        addresses = [product["address"] for product in opened["products"]]
        self.assertIn(opened["address"], addresses)
        for address in addresses:
            self.assertTrue(answers(address), address)

        # « accepté » is not an answer to a « non conforme » request: refused, nothing written.
        before = self.tracker.read_bytes()
        for word in ("accepte", "accepté"):
            proc = self.tool(SESSION, "record", self.convoy, "--repo", self.repo, "--response", word)
            self.assertNotEqual(0, proc.returncode, proc.stdout)
            self.assertNotIn('"ok": true', proc.stdout)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([request], self.requests())
        self.assertIsNone(self.shown()["convoy"]["delivered"])

        closed = json.loads(self.tool_ok(SESSION, "close", self.convoy).stdout)
        self.assertTrue(closed["closed"])
        self.assertEqual([True] * len(addresses), [product["free"] for product in closed["stopped"]])
        for address in addresses:
            self.assertFalse(answers(address), address)
        self.assertEqual(before, self.tracker.read_bytes())


if __name__ == "__main__":
    unittest.main()
