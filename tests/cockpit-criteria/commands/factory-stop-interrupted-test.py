#!/usr/bin/env python3
"""Criterion test 3 of H « Usine — arrêt propre et reprise vérifiée exposés »
(af-69qhlk; Spec af-fgcw0d, user stories 83 and 90, the choice « Maintenance » :
« Suspension ne signifie pas VM éteignable ; arrêt complet seulement renvoi
vers procédure/prérequis et autorité ADMIN existants, sans extinction depuis
ce périmètre », Testing Decisions 1, 4 and 8): a host restarted during the
suspension, and the procedure of the machine.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, with a synthetic supervisor the case writes
(usine_arret.serve_stop) and reads GET /usine, as served and in a headless
Chromium.

False if the interruption goes unnoticed, or if the cockpit offers to power
off the VM.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_arret import PAGE, control, said_until, serve_stop, visible_text, walk, written  # noqa: E402

AUTHOR = {"session": "auteur-recus", "role": "Auteur", "ticket": "tk-recus", "title": "Trier les reçus du mois"}
REVIEWER = {"session": "relecteur-notes", "role": "Relecteur", "ticket": "tk-notes",
            "title": "Relire les notes de frais"}
MACHINE = "Préparer l’arrêt de la machine"
# What a control that powers off, or stops all, would be called.
POWER_OFF = re.compile(r"(?i)\b(éteindre|extinction|couper|arrêter la (vm|machine)|arrêt complet)\b")


class FactoryStopInterrupted(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def test_a_host_restarted_during_the_suspension_shows_the_interruption_and_its_gaps(self):
        address, writes = serve_stop(self.tree, "health-content", {
            "work": [AUTHOR, REVIEWER], "missing_after_restart": ["relecteur-notes"]}, restarted=True)
        text = said_until(address, "Arrêt interrompu")
        self.assertIn("Arrêt interrompu", text, f"the interruption goes unnoticed: « {text} »")
        self.assertRegex(text, rf"Écarts?[^.]*{REVIEWER['title']}", f"the gap does not name its work: « {text} »")
        self.assertNotRegex(text, rf"Écarts?[^.]*{AUTHOR['title']}", "a work found as it was is said to be a gap")
        self.assertRegex(text, r"(?i)reprise[^.]*à vérifier", f"the resume is not said to be checked: « {text} »")
        self.assertNotIn("Suspension confirmée", text, "confirmed after an interruption")
        start = walk(address, [], path=PAGE)["start"]
        self.assertIsNotNone(control(start, "Redémarrer"), f"nothing to go on with: « {visible_text(start)} »")
        self.assertEqual([], written(writes), "the supervisor was asked something")

    def test_the_procedure_of_the_machine_is_read_and_nothing_powers_it_off(self):
        address, writes = serve_stop(self.tree, "health-content", {"work": [AUTHOR]})
        walked = walk(address, [{"click": MACHINE}], path=PAGE)
        self.assertTrue(walked["steps"] and walked["steps"][0]["found"], f"no control « {MACHINE} »: {walked}")
        page = walked["steps"][0]["page"]
        text = visible_text(page)
        self.assertIn("Arrêt complet de la VM à préparer", text, f"the procedure is not shown: « {text} »")
        self.assertIn("Machine non déclarée éteignable", text, f"the machine is not said: « {text} »")
        self.assertIn("procédure d’arrêt complète", text, f"the procedure is not named: « {text} »")
        for shown in [walked["start"], page]:
            offered = [item["name"] for item in shown["controls"] if POWER_OFF.search(item["name"])]
            self.assertEqual([], offered, "a control offers to power off the VM")
        self.assertEqual([], written(writes), "the supervisor was asked something")


if __name__ == "__main__":
    unittest.main()
