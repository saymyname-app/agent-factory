#!/usr/bin/env python3
"""Criterion test of R16 « Proposition de réglage débloquée après relecture
de la source » (af-yv2g3n; Blocking Finding F1.25 of the end review on
96b3429f0dee; Spec af-fgcw0d, decision 8: « après une issue incertaine relire
la source avant toute répétition, sans masquer un succès déjà enregistré »;
Testing Decisions 1, 3 and 8): a proposal whose preparation had an uncertain
outcome, recorded, then decided.

The proposal is the one of G2 (factory-configure-proposal-test.py and
factory-configure-stale-test.py): the author of delivery on GPT-5.6 Sol
(Codex), a change no door supports. The case launches the real cockpit with
the launcher of the profile, bin/project-launch, on the Usine of
health-content (usine_reglages.serve_usine), the door of proposals writing
its record then never answering (`records-then-expires`):

- « Préparer ce changement » is sent as the browser sends it: the outcome is
  uncertain, and the door wrote the proposal;
- once what waits for the operator (GET /api/requests) shows it, the scope
  of the change, GET /usine?role=author&reglage=portee, says it recorded and
  waiting for a decision, its « Préparer ce changement » off;
- the proposal is decided in Pour moi, refused with its reason as the
  browser sends it (the door writes the refusal, then never answers);
- once what waits no longer shows it, the scope of the change, read again in
  a headless Chromium, offers « Préparer ce changement » again, and the
  gesture reaches the door of proposals: a second proposal waits.

False if, the proposal decided, the page still says « Proposition déjà
enregistrée … attend ta décision », or « Préparer ce changement » stays off,
or the gesture is refused without reaching the door.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_reglages import (  # noqa: E402
    DOOR_SECONDS, PAGE, Operator, frame_control, measure_until, requests_of, serve_usine, wait_for,
)

SCOPE = PAGE + "?role=author&reglage=portee&principal=codex&effort=&secours="
PROPOSAL = {"role": "author", "principal": "codex", "confirm": True}
PREPARE = "Préparer ce changement"
RECORDED = r"Proposition déjà enregistrée\s*:.*attend ta décision"
REASON = "Codex n’a pas passé l’essai d’adoption du rôle auteur."
# How long the cockpit is given to read what waits for the operator again.
REREAD_SECONDS = 30


def prepare(frame: dict) -> dict | None:
    return frame_control(frame, PREPARE)


class FactoryConfigureProposalDecided(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own: serve_usine commits the dataset of the case in it.
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def test_a_recorded_proposal_once_decided_in_pour_moi_lets_the_change_be_prepared_again(self):
        address = serve_usine(self.tree, doors={"proposal-door": "records-then-expires"})
        waiting_before = {request["id"] for request in requests_of(address)}
        operator = Operator(address)

        # Prepared: the door writes the proposal, then never answers.
        first = operator.gesture("preparer_reglage", PROPOSAL)
        self.assertEqual("", first.broken, f"the request broke: {first}")
        self.assertIsNotNone(first.status, f"no HTTP answer: {first}")
        self.assertGreaterEqual(first.status, 400, f"an uncertain preparation is answered as done: {first}")
        self.assertRegex(first.error(), r"(?i)expir|incertain", f"the outcome is not said uncertain: {first}")
        waiting = wait_for(lambda: requests_of(address),
                           lambda found: any(r["id"] not in waiting_before for r in found), REREAD_SECONDS)
        recorded = [r for r in waiting if r["id"] not in waiting_before]
        self.assertEqual(1, len(recorded), f"not the one proposal the door recorded: {recorded}")

        # Recorded and waiting: the scope says so, and prepares nothing more.
        frame = measure_until(address, lambda frames: (prepare(frames[0]) or {}).get("disabled") is True,
                              seconds=REREAD_SECONDS, path=SCOPE)[0]
        self.assertIsNotNone(prepare(frame), f"the scope has no « {PREPARE} »: « {frame['text']} »")
        self.assertTrue(prepare(frame)["disabled"], "a proposal waiting for a decision is offered to be prepared again")
        self.assertRegex(frame["text"], RECORDED, "the scope does not say the proposal waits for a decision")

        # Decided in Pour moi: refused with its reason, as the browser sends it.
        decided = operator.gesture("rejeter_proposition",
                                   {"bead_id": recorded[0]["id"], "raison": REASON, "confirm": True})
        self.assertEqual("", decided.broken, f"the request broke: {decided}")
        self.assertIsNotNone(decided.status, f"no HTTP answer: {decided}")
        self.assertNotEqual(500, decided.status, f"the cockpit broke: {decided}")
        left = wait_for(lambda: requests_of(address),
                        lambda found: all(r["id"] != recorded[0]["id"] for r in found), REREAD_SECONDS)
        self.assertNotIn(recorded[0]["id"], [r["id"] for r in left], "the proposal still waits for a decision")

        # Read again: « Préparer ce changement » is there again, unblocked.
        frame = measure_until(address, lambda frames: (prepare(frames[0]) or {}).get("disabled") is False,
                              seconds=REREAD_SECONDS, path=SCOPE)[0]
        self.assertIsNotNone(prepare(frame), f"the scope has no « {PREPARE} »: « {frame['text']} »")
        self.assertNotRegex(frame["text"], RECORDED, "the scope still says the decided proposal waits for a decision")
        self.assertFalse(prepare(frame)["disabled"],
                         f"« {PREPARE} » stays off once the proposal was decided: « {frame['text']} »")

        # And the gesture reaches the door of proposals again.
        again = operator.gesture("preparer_reglage", PROPOSAL)
        self.assertEqual("", again.broken, f"the request broke: {again}")
        self.assertNotRegex(again.error(), r"(?i)déjà enregistr|indisponible",
                            f"the preparation is refused once the proposal was decided: {again}")
        self.assertGreaterEqual(again.seconds, DOOR_SECONDS - 1, f"the preparation did not reach its door: {again}")
        seen = {recorded[0]["id"], *waiting_before}
        waiting = wait_for(lambda: requests_of(address), lambda found: any(r["id"] not in seen for r in found),
                           REREAD_SECONDS)
        self.assertEqual(1, len([r for r in waiting if r["id"] not in seen]),
                         f"not one new proposal prepared once the first was decided: {waiting}")


if __name__ == "__main__":
    unittest.main()
