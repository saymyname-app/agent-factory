#!/usr/bin/env python3
"""Criterion test 2 of B « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-4uzgzm; Spec af-fgcw0d, user
story 122, Implementation Decisions 6 and, of af-2zseit, 8; Testing
Decisions 1 and 3; the defect af-fksj2c): a gesture whose command expires,
then one whose outcome is uncertain, at POST /api/actions/<geste>.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset that carries a tracker as the doors of the
Factory write it -- a proposal of class decision, as bin/proposal-door
(create) leaves it -- and says how the door of proposals answers in that
launch (pour_moi.serve_tracker, `doors`):

- `expires`: it never answers, and writes nothing;
- `records-then-expires`: it writes its record, as bin/proposal-door does,
  then never answers -- the gesture was done, the cockpit cannot know it
  from the command.

The gesture is the operator's refusal of that proposal with a reason,
confirmed, sent as the browser sends it from a page the cockpit served
behind the identity proxy of the host (pour_moi.Operator). What the cockpit
answers is read as HTTP; what it did, at GET /api/requests and
GET /api/journal (the requests resolved at their source).

False if the request breaks (no HTTP answer, or an answer that is no
readable error), if the gesture is repeated blindly (the door run again
before the source was read again: a second record), or if a success
recorded is hidden (the refusal written by the door missing from the
journal, the proposal still waiting).
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import Operator, journal_of, proposal, read_json, requests_of, serve_tracker, wait_for  # noqa: E402

AT = "2026-10-12T08:00:00Z"
PROPOSAL = "af-x5c8d"
TRACKER = {PROPOSAL: proposal("Ajouter un export des notes en CSV",
                              "Plusieurs lecteurs demandent à garder leurs notes hors du projet.", [
                                  {"lettre": "a", "option": "Ajouter l’export", "consequence": "un ticket est préparé",
                                   "recommande": True, "raison": "la demande revient souvent"},
                                  {"lettre": "b", "option": "Ne rien faire", "consequence": "rien ne change"},
                              ], AT)}
REASON = "Les notes restent dans le projet pour cette version."
REFUSE = {"bead_id": PROPOSAL, "raison": REASON, "confirm": True}
# How long the source may take to be read again after a gesture.
REREAD_SECONDS = 20


class ActionExpiry(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def launched(self, door: str) -> Operator:
        address = serve_tracker(self.tree, TRACKER, doors={"proposal-door": door})
        listed = wait_for(lambda: requests_of(address), lambda found: any(r["id"] == PROPOSAL for r in found), 20)
        self.assertIn(PROPOSAL, [r["id"] for r in listed], "« Ce qui t’attend » does not list the proposal")
        return Operator(address)

    def assert_readable_expiry(self, answer) -> None:
        """An HTTP answer, an error status that is no crash of the cockpit,
        and an error in words that says the command expired."""
        self.assertEqual("", answer.broken, f"the request broke: {answer}")
        self.assertIsNotNone(answer.status, f"no HTTP answer: {answer}")
        self.assertGreaterEqual(answer.status, 400, f"a command that expired is answered as done: {answer}")
        self.assertNotEqual(500, answer.status, f"the cockpit broke on a command that expired: {answer}")
        self.assertIsInstance(answer.body, dict, f"the answer is no readable error: {answer}")
        self.assertRegex(answer.error(), r"(?i)expir", f"the error does not say the command expired: {answer}")
        self.assertNotRegex(answer.error(), r"Traceback|TimeoutExpired|Errno", f"the error is not readable: {answer}")

    def reread_since(self, address: str, moment: float) -> None:
        """Wait until the cockpit read its tracker again after `moment`
        (epoch seconds)."""
        read = wait_for(lambda: read_json(address, "/api/requests"),
                        lambda served: (served.get("verified_at") or 0) > moment, REREAD_SECONDS)
        self.assertGreater(read.get("verified_at") or 0, moment, "the cockpit did not read its tracker again")

    def rejections(self, address: str) -> list[dict]:
        return [e for e in journal_of(address) if e["bead_id"] == PROPOSAL]

    # --- Criterion 2 ------------------------------------------------------------

    def test_a_command_that_expires_answers_a_readable_error_then_the_gesture_comes_back_once_reread(self):
        operator = self.launched("expires")
        answer = operator.gesture("rejeter_proposition", REFUSE)
        answered_at = time.time()
        self.assert_readable_expiry(answer)
        # Nothing was recorded: the proposal still waits, nothing resolved it.
        self.assertIn(PROPOSAL, [r["id"] for r in requests_of(operator.address)],
                      "a command that expired is shown as done")
        self.assertEqual([], self.rejections(operator.address), "a command that expired is shown as done")
        # Once the tracker was read again, the gesture is there again: the
        # door is reached once more, and expires once more.
        self.reread_since(operator.address, answered_at)
        again = operator.gesture("rejeter_proposition", REFUSE)
        self.assert_readable_expiry(again)

    def test_an_uncertain_outcome_blocks_the_gesture_until_reread_and_keeps_the_success_recorded(self):
        operator = self.launched("records-then-expires")
        answer = operator.gesture("rejeter_proposition", REFUSE)
        self.assert_readable_expiry(answer)
        # At once, the same gesture: not sent blindly to the door again.
        again = operator.gesture("rejeter_proposition", REFUSE)
        self.assertEqual("", again.broken, f"the request broke: {again}")
        self.assertIsNotNone(again.status, f"no HTTP answer: {again}")
        self.assertGreaterEqual(again.status, 400, f"the gesture was done again before the source was read: {again}")
        self.assertNotEqual(500, again.status, f"the cockpit broke: {again}")
        self.assertIsInstance(again.body, dict, f"the answer is no readable error: {again}")
        self.assertTrue(again.error().strip(), f"the gesture refused says nothing: {again}")
        # The success the door recorded is shown, once.
        recorded = wait_for(lambda: self.rejections(operator.address), lambda found: len(found) >= 1, REREAD_SECONDS)
        self.assertEqual([f"proposition rejetée — {REASON}"], [e["quoi"] for e in recorded],
                         "the refusal the door recorded is hidden, or was written twice")
        left = wait_for(lambda: requests_of(operator.address), lambda found: all(r["id"] != PROPOSAL for r in found),
                        REREAD_SECONDS)
        self.assertNotIn(PROPOSAL, [r["id"] for r in left], "the proposal refused still waits: the success is hidden")
        self.assertEqual(1, len(self.rejections(operator.address)), "the gesture was repeated blindly")


if __name__ == "__main__":
    unittest.main()
