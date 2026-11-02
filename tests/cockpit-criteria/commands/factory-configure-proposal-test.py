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
changes. So with an effort no door sets (the author on effort élevé, its
provider runs on effort moyen) and with a fallback the role was not tried
on (Codex added to its chain): each is prepared as a proposal, and nothing
of the role changes.

Each case launches the real cockpit with the launcher of the profile,
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
EFFORT_STEPS = [{"click": "Configurer"}, {"click": "Effort : Élevé"}, {"click": "Voir la portée"},
                {"click": "Préparer ce changement"}]
FALLBACK_STEPS = [{"click": "Configurer"}, {"click": "Ajouter en secours : " + CODEX}, {"click": "Voir la portée"},
                  {"click": "Préparer ce changement"}]
GPT_5_6 = re.compile(r"gpt[\s-]*5[.,]6", re.I)


class FactoryConfigureProposal(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own per case: serve_usine commits the dataset of the
        # case in it, and a case never sees what another case left.
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

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
        self.assertNotRegex(prepared, r"(?i)\b(appliqué|relu)\b", f"a success is shown: « {prepared} »")
        # The page Usine says elsewhere what is « configuré » (a provider's
        # account, an effort no file sets): what it says of the proposal is
        # never that.
        said = re.findall(r"(?i)\bproposition\b[^.]*", prepared)
        self.assertNotRegex(" ".join(said), r"(?i)\bconfiguré\b", f"the proposal is said configured: {said}")
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

    def prepared(self, address: str, steps: list[dict], new_value: str) -> dict:
        """The proposal prepared by walking `steps` on the author: the scope
        says `new_value` and offers no « Appliquer », the page says a
        proposal and no success, and one request waits for the operator."""
        waiting_before = {request["id"] for request in requests_of(address)}
        walked = walk(address, steps, path=AUTHOR)
        found = walked["steps"]
        for index, step in enumerate(steps):
            self.assertLess(index, len(found), f"the walk stopped before « {step['click']} »: {walked}")
            self.assertTrue(found[index]["found"], f"no control « {step['click']} » to activate: {found[index]}")
        scope, prepared = visible_text(found[2]["page"]), visible_text(found[3]["page"])
        self.assertRegex(scope, rf"(?i)Nouvelle valeur((?!Portée).)*{new_value}",
                         f"the scope does not say the new value: « {scope} »")
        self.assertRegex(scope, r"(?i)adoption|validation", f"the scope does not say what it needs first: « {scope} »")
        self.assertIsNone(control(found[2]["page"], "Appliquer"), "a change no door supports is offered to be applied")
        self.assertRegex(prepared, r"(?i)proposition", f"the page does not say a proposal was prepared: « {prepared} »")
        self.assertNotRegex(prepared, r"(?i)\b(appliqué|relu)\b", f"a success is shown: « {prepared} »")
        waiting = wait_for(lambda: requests_of(address),
                           lambda found: any(r["id"] not in waiting_before for r in found), 20)
        new = [r for r in waiting if r["id"] not in waiting_before]
        self.assertEqual(1, len(new), f"not one proposal prepared for the operator: {new}")
        self.assertRegex(new[0]["quoi"], r"(?i)auteur", f"the proposal does not say the role: {new[0]}")
        return new[0]

    def test_a_change_of_effort_no_door_supports_is_prepared_as_a_proposal_and_changes_nothing(self):
        address = serve_usine(self.tree)
        proposal = self.prepared(address, EFFORT_STEPS, r"effort élevé")
        self.assertRegex(proposal["quoi"], r"(?i)effort élevé", f"the proposal does not say the effort: {proposal}")
        again = visible_text(walk(address, [], path=AUTHOR)["start"])
        self.assertRegex(again, r"Effort\s*:?\s*Moyen", f"the effort of the author changed: « {again} »")

    def test_a_fallback_no_door_supports_is_prepared_as_a_proposal_and_changes_nothing(self):
        address = serve_usine(self.tree)
        proposal = self.prepared(address, FALLBACK_STEPS, r"puis " + re.escape(CODEX) + r" en secours")
        self.assertRegex(proposal["quoi"], r"(?i)secours", f"the proposal does not say the fallback: {proposal}")
        self.assertRegex(proposal["quoi"], GPT_5_6, f"the proposal does not say the provider: {proposal}")
        again = visible_text(walk(address, [], path=AUTHOR)["start"])
        self.assertRegex(again, r"Aucun secours inter-fournisseur configuré",
                         f"the fallbacks of the author changed: « {again} »")


if __name__ == "__main__":
    unittest.main()
