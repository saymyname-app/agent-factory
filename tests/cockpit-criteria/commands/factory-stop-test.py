#!/usr/bin/env python3
"""Criterion test 1 of H « Usine — arrêt propre et reprise vérifiée exposés »
(af-69qhlk; Spec af-fgcw0d, user stories 80 to 84, 87 and 165, the decision
« Arrêt/reprise indépendant » and the choice « Maintenance », Testing
Decisions 1, 4 and 8): the clean stop of the Factory, from the page Usine.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content with a synthetic supervisor the case
writes (usine_arret.serve_stop). The page GET /usine is walked in a headless
Chromium behind the identity proxy of the host, then followed over HTTP while
the supervisor changes; what the cockpit asked of it is what it recorded.

False if a progress is read on a timer, if a complete stop or a power-off is
asked, or if a resume is said verified without a comparison.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_arret import (  # noqa: E402
    Operator, PAGE, control, said_until, serve_stop, stays, visible_text, walk, written,
)

AUTHOR = {"session": "auteur-recus", "role": "Auteur", "ticket": "tk-recus", "title": "Trier les reçus du mois"}
REVIEWER = {"session": "relecteur-notes", "role": "Relecteur", "ticket": "tk-notes",
            "title": "Relire les notes de frais"}
ASK = {"click": "Demander la suspension"}
CONFIRM = {"click": "Confirmer"}
RESTART = {"click": "Redémarrer"}
SUSPENDED_WRITE = ("PATCH", "", {"suspended": True})
RESUMED_WRITE = ("PATCH", "", {"suspended": False})


class FactoryStop(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own per case: serve_stop commits the dataset of the
        # case in it, and a case never sees what another case left.
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def walked(self, address: str, steps: list[dict]) -> list[dict]:
        found = walk(address, steps, path=PAGE)["steps"]
        for index, step in enumerate(steps):
            self.assertLess(index, len(found), f"the walk stopped before {step}: {found}")
            self.assertTrue(found[index]["found"], f"no control {step} to activate: {found[index]}")
        return [step["page"] for step in found[:len(steps)]]

    def test_a_clean_stop_shows_its_work_is_followed_on_facts_then_is_confirmed_and_verified_at_the_resume(self):
        address, writes = serve_stop(self.tree, "health-content", {
            "work": [AUTHOR, REVIEWER], "drains_in_seconds": {"relecteur-notes": 1, "auteur-recus": 15}})

        # Before the confirmation: what the stop will wait for, and nothing asked.
        [before] = self.walked(address, [ASK])
        text = visible_text(before)
        self.assertIn(AUTHOR["title"], text, f"the work in flight is not listed: « {text} »")
        self.assertIn(REVIEWER["title"], text, f"the work in flight is not listed: « {text} »")
        self.assertIsNotNone(control(before, "Confirmer"), f"no confirmation is asked: « {text} »")
        self.assertEqual([], written(writes), "the supervisor was asked something before the confirmation")

        # The confirmation sends the suspension, and that only.
        self.walked(address, [ASK, CONFIRM])
        self.assertEqual([SUSPENDED_WRITE], written(writes))

        # Step by step: each point of resuming is the one the session reached.
        draining = said_until(address, "Relecteur : point conservé")
        self.assertIn("Relecteur : point conservé", draining, f"no point observed for the review: « {draining} »")
        self.assertIn("Auteur : sauvegarde en cours", draining, f"the author is not still saving: « {draining} »")
        self.assertIn("Travaux en cours de mise au repos", draining)
        self.assertNotIn("Suspension confirmée", draining, "confirmed while a session still saves its work")

        # Confirmed on its proofs, and told apart from a machine one may power off.
        suspended = said_until(address, "Suspension confirmée")
        self.assertIn("Suspension confirmée", suspended, f"the stop is not confirmed: « {suspended} »")
        self.assertIn("2 travaux retrouvés, aucun écart", suspended, f"no comparison shown: « {suspended} »")
        self.assertIn("La suspension des agents n’est pas l’arrêt de la VM", suspended)
        self.assertIn("Fermer ou éteindre ce PC client n’arrête pas la VM", suspended)

        # The restart compares what came back with the photo.
        self.walked(address, [RESTART])
        resumed = said_until(address, "Reprise vérifiée à")
        self.assertRegex(resumed, r"Reprise vérifiée à \d{2}:\d{2}", f"the resume is not verified: « {resumed} »")
        self.assertEqual([SUSPENDED_WRITE, RESUMED_WRITE], written(writes))

    def test_a_progress_is_read_on_facts_never_on_a_timer(self):
        # A session that never reaches its point: nothing happens, whatever the time.
        address, writes = serve_stop(self.tree, "health-content", {"work": [AUTHOR, REVIEWER],
                                                                   "drains_in_seconds": {"relecteur-notes": 1}})
        self.walked(address, [ASK, CONFIRM])
        said_until(address, "Relecteur : point conservé")
        for text in stays(address):
            self.assertIn("Relecteur : point conservé", text)
            self.assertIn("Auteur : sauvegarde en cours", text, f"the author moved by itself: « {text} »")
            self.assertNotIn("Suspension confirmée", text, "confirmed with a session still at work")
        self.assertEqual([SUSPENDED_WRITE], written(writes))

    def test_a_ticket_lost_during_the_stop_is_no_confirmation(self):
        address, _ = serve_stop(self.tree, "health-content", {
            "work": [AUTHOR, REVIEWER], "drains_in_seconds": {"relecteur-notes": 1, "auteur-recus": 1},
            "vanishes_when_drained": ["tk-recus"]})
        self.walked(address, [ASK, CONFIRM])
        text = said_until(address, "Suspension à vérifier")
        self.assertIn("Suspension à vérifier", text, f"the loss is not said: « {text} »")
        self.assertIn(AUTHOR["title"], text, f"the work lost is not named: « {text} »")
        self.assertNotIn("Suspension confirmée", text, "confirmed though a ticket of the photo is gone")

    def test_a_resume_that_changed_a_holder_lists_its_gap_and_is_not_verified(self):
        address, writes = serve_stop(self.tree, "health-content", {
            "work": [AUTHOR, REVIEWER], "drains_in_seconds": {"relecteur-notes": 1, "auteur-recus": 1},
            "reassigned_on_resume": {"tk-recus": "auteur-remplacant"}})
        self.walked(address, [ASK, CONFIRM])
        said_until(address, "Suspension confirmée")
        self.walked(address, [RESTART])
        text = said_until(address, "Reprise avec écarts")
        self.assertIn("Reprise avec écarts", text, f"the gap is not said: « {text} »")
        self.assertIn(AUTHOR["title"], text, f"the gap does not name the work: « {text} »")
        self.assertNotIn(REVIEWER["title"] + " : écart", text, "a work resumed as it was is said to be a gap")
        self.assertNotRegex(text, r"Reprise vérifiée à \d", "verified with a holder changed")
        self.assertEqual([SUSPENDED_WRITE, RESUMED_WRITE], written(writes))

    def test_a_stop_is_not_offered_while_the_work_in_flight_is_unknown(self):
        address, writes = serve_stop(self.tree, "health-offline", {"work": [AUTHOR]})
        start = walk(address, [], path=PAGE)["start"]
        ask = control(start, "Demander la suspension")
        self.assertIsNotNone(ask, f"the control is not shown with its reason: « {visible_text(start)} »")
        self.assertTrue(ask["disabled"], f"a stop can be asked over a work unknown: {ask}")
        self.assertRegex(visible_text(start), r"(?i)travail en vol[^.]*inconnu", "the reason is not said")
        answer = Operator(address).gesture("arreter", {})
        self.assertEqual(409, answer.status, f"the gesture is not refused: {answer}")
        self.assertEqual([], written(writes), "the supervisor was asked something")


if __name__ == "__main__":
    unittest.main()
