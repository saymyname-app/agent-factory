#!/usr/bin/env python3
"""Criterion test 2 of H « Usine — arrêt propre et reprise vérifiée exposés »
(af-69qhlk; Spec af-fgcw0d, user stories 85, 86 and 165, the decision
« Arrêt/reprise indépendant » : « Après trente minutes sans progression,
proposer seulement à Benjamin le forcé avec risques, garder les
affectations », Testing Decisions 1, 4 and 8): a stop that no longer moves.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on factory-blocked with a synthetic supervisor the case
writes (usine_arret.serve_stop): a stop asked minutes before the launch, a
session silent since. The requests are read at GET /api/requests, the
decision is taken in a headless Chromium on the home page, as Benjamin does.

False if a forced stop happens without Benjamin's decision, or if an
assignment is lost.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_arret import (  # noqa: E402
    Operator, PAGE, requests_of, said_until, serve_stop, stays, visible_text, wait_for, walk, written,
)

AUTHOR = {"session": "auteur-recus", "role": "Auteur", "ticket": "tk-recus", "title": "Trier les reçus du mois"}
NOT_MOVING = "L'arrêt n'avance plus"
FORCE = "Forcer l'arrêt"
STOPPED_SESSION = ("POST", "/session/auteur-recus/stop", {})


def blocked(requests: list[dict]) -> list[dict]:
    return [request for request in requests if request.get("quoi", "").startswith(NOT_MOVING)]


class FactoryStopBlocked(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def test_thirty_minutes_without_progress_ask_benjamin_with_the_risks_and_force_nothing(self):
        address, writes = serve_stop(self.tree, "factory-blocked", {"work": [AUTHOR], "asked_minutes_ago": 31})
        found = blocked(wait_for(lambda: requests_of(address), lambda got: bool(blocked(got)), 25))
        self.assertEqual(1, len(found), f"no request « {NOT_MOVING} »")
        request = found[0]
        self.assertEqual("À faire", request["niveau"])
        options = {option["option"]: option for option in request["que_faire"]}
        self.assertIn(FORCE, options, f"the forced stop is not offered: {options}")
        self.assertIn(AUTHOR["title"], options[FORCE]["consequence"], "what is at risk is not listed")
        self.assertRegex(options[FORCE]["consequence"], r"(?i)perd", "the risk of losing is not said")
        self.assertNotIn(AUTHOR["ticket"], options[FORCE]["consequence"], "an identifier in the main text")
        self.assertFalse(options[FORCE]["recommande"], "a forced stop is recommended")

        for text in stays(address):
            self.assertIn("Suspension bloquée", text, f"the panel does not say it is blocked: « {text} »")
            self.assertIn("Aucune autorisation d’éteindre", text, f"the panel leaves it open: « {text} »")
        self.assertEqual([], written(writes), "the supervisor was asked something without a decision")

    def test_the_forced_stop_benjamin_decides_keeps_the_assignments_for_the_resume(self):
        address, writes = serve_stop(self.tree, "factory-blocked", {"work": [AUTHOR], "asked_minutes_ago": 31})
        wait_for(lambda: requests_of(address), lambda got: bool(blocked(got)), 25)
        steps = [{"click": NOT_MOVING}, {"click": FORCE}, {"click": "Confirmer", "wait": 4000}]
        found = walk(address, steps)["steps"]
        for index, step in enumerate(steps):
            self.assertLess(index, len(found), f"the walk stopped before {step}: {found}")
            self.assertTrue(found[index]["found"], f"no control {step}: {visible_text(found[index]['page'])}")
        self.assertEqual([STOPPED_SESSION], written(writes), "not the session held, or not it alone")

        text = said_until(address, "Arrêt forcé")
        self.assertIn("Arrêt forcé", text, f"the forced stop is not said: « {text} »")
        self.assertRegex(text, rf"{AUTHOR['title']}[^.]*(gardé|affecté)", f"the assignment is not kept: « {text} »")

        walked = walk(address, [{"click": "Redémarrer"}], path=PAGE)["steps"]
        self.assertTrue(walked and walked[0]["found"], f"no control « Redémarrer »: {walked}")
        resumed = said_until(address, "Reprise vérifiée à")
        self.assertRegex(resumed, r"Reprise vérifiée à \d{2}:\d{2}", f"the work is not back as it was: « {resumed} »")

    def test_no_forced_stop_before_the_thirty_minutes(self):
        address, writes = serve_stop(self.tree, "factory-blocked", {"work": [AUTHOR], "asked_minutes_ago": 10})
        text = said_until(address, "Travaux en cours de mise au repos")
        self.assertIn("Travaux en cours de mise au repos", text, f"the stop is not under way: « {text} »")
        self.assertEqual([], blocked(requests_of(address)), "a request raised before thirty minutes")
        answer = Operator(address).gesture("forcer_arret", {})
        self.assertEqual(409, answer.status, f"the forced stop is not refused: {answer}")
        self.assertEqual([], written(writes), "the supervisor was asked something")


if __name__ == "__main__":
    unittest.main()
