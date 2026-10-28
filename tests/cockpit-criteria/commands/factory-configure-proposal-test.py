#!/usr/bin/env python3
"""Criterion test 1 of G2 « Usine — réglages et nettoyage par les portes
existantes » (af-f8nlhr; Spec af-fgcw0d, user story 164, the choice « Usine »
of af-2zseit: « Modèle/effort/chaîne non supportés : préparer une
proposition, ne pas simuler un succès »; Testing Decisions 1 and 8): a
change no door supports.

The change: the author of delivery on GPT-5.6 Sol (Codex). Its chain,
config/provider-policy.json at the commit, holds Claude Opus 5.5 · effort
moyen alone: Codex has not passed the trial of adoption of the role, and no
door puts a provider in a chain it was not tried for. The change is prepared
as a proposal, through the door of proposals, and nothing of the role
changes.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the Usine of health-content (usine_reglages.serve_usine), walks GET
/usine?role=author in a headless Chromium behind the identity proxy of the
host, and reads what waits for the operator at GET /api/requests.

False if the change is said done, or the role runs on it, or nothing is
prepared for the operator to decide.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_reglages import (  # noqa: E402
    PAGE, control, in_service, requests_of, serve_usine, visible_text, wait_for, walk,
)

AUTHOR = PAGE + "?role=author"
CODEX = "GPT-5.6 Sol (Codex)"
STEPS = [{"click": "Configurer"}, {"click": CODEX}, {"click": "Voir la portée"}, {"click": "Préparer ce changement"}]
GPT_5_6 = re.compile(r"gpt[\s-]*5[.,]6", re.I)


class FactoryConfigureProposal(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_a_change_of_model_no_door_supports_is_prepared_as_a_proposal_and_changes_nothing(self):
        address = serve_usine(self.tree)
        waiting_before = {request["id"] for request in requests_of(address)}
        walked = walk(address, STEPS, path=AUTHOR)
        steps = walked["steps"]
        for index, step in enumerate(STEPS):
            self.assertLess(index, len(steps), f"the walk stopped before « {step['click']} »: {walked}")
            self.assertTrue(steps[index]["found"], f"no control « {step['click']} » to activate: {steps[index]}")
        scope_page, prepared_page = steps[2]["page"], steps[3]["page"]
        scope, prepared = visible_text(scope_page), visible_text(prepared_page)

        # Before it is prepared: what it would be, and that it is not applied.
        self.assertRegex(scope, rf"Nouvelle valeur\s*:?\s*{re.escape(CODEX)}",
                         f"the scope does not say the new value: « {scope} »")
        self.assertRegex(scope, r"(?i)adoption|validation", f"the scope does not say what it needs first: « {scope} »")
        self.assertIsNone(control(scope_page, "Appliquer"), "a change no door supports is offered to be applied")

        # Prepared: a proposal waits for the operator, nothing is said done.
        self.assertRegex(prepared, r"(?i)proposition", f"the page does not say a proposal was prepared: « {prepared} »")
        self.assertNotRegex(prepared, r"(?i)\b(appliqué|configuré|relu)\b", f"a success is shown: « {prepared} »")
        waiting = wait_for(lambda: requests_of(address),
                           lambda found: any(r["id"] not in waiting_before for r in found), 20)
        new = [r for r in waiting if r["id"] not in waiting_before]
        self.assertEqual(1, len(new), f"not one proposal prepared for the operator: {new}")
        self.assertRegex(new[0]["quoi"], GPT_5_6, f"the proposal does not say the model: {new[0]}")
        self.assertRegex(new[0]["quoi"], r"(?i)auteur", f"the proposal does not say the role: {new[0]}")

        # The role runs on what it ran on.
        again = visible_text(walk(address, [], path=AUTHOR)["start"])
        self.assertNotRegex(in_service(again), GPT_5_6, f"the author runs on a model no door set: « {again} »")
        self.assertRegex(again, r"Modèle configuré\s*:?\s*Claude Opus 5\.5",
                         f"the configured model of the author changed: « {again} »")


if __name__ == "__main__":
    unittest.main()
