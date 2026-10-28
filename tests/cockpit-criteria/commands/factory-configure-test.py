#!/usr/bin/env python3
"""Criterion test 1 of G2 « Usine — réglages et nettoyage par les portes
existantes » (af-f8nlhr; Spec af-fgcw0d, user story 163, the choice
« Usine » of af-2zseit: « L'édition soutenue par une porte montre valeur
actuelle, nouvelle valeur, portée, conséquences, confirmation puis
relecture ; sessions en cours non annoncées modifiées si seule la création
des suivantes est concernée … aucune écriture brute de configuration
contournant leur contrôle »; Testing Decisions 1 and 8): a setting a door
supports.

The setting: which provider the reviewer of delivery runs on first. Its
chain, config/provider-policy.json at the commit, is GPT-5.6 Sol (Codex) ·
lecture seule, then Claude Opus 5.5 · effort élevé · lecture seule; both
passed the trial of adoption of the role, and the door provider-failover
(set --action chain) orders it.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the Usine of health-content (usine_reglages.serve_usine), walks GET
/usine?role=reviewer in a headless Chromium behind the identity proxy of the
host, and reads the page again afterwards.

False if the setting is written around its door (the page then shows it
while the door did nothing), if a success is shown that the door did not
make, or if the sessions under way are said to be changed.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_reglages import PAGE, control, in_service, serve_usine, visible_text, walk  # noqa: E402

REVIEWER = PAGE + "?role=reviewer"
CODEX_READONLY = "GPT-5.6 Sol (Codex) · lecture seule"
CLAUDE_READONLY = "Claude Opus 5.5 · effort élevé · lecture seule"
# Choosing Claude first, then seeing its scope, then applying it.
STEPS = [{"click": "Configurer"}, {"click": CLAUDE_READONLY}, {"click": "Voir la portée"}, {"click": "Appliquer"}]
OPUS_5_5 = re.compile(r"opus[\s-]*5[.,]5", re.I)
# What would say the sessions under way change.
SESSIONS_CHANGED = re.compile(
    r"sessions (?:en cours|ouvertes)\s+(?:sont\s+|seront\s+)?(?:modifiées|basculées|basculent|changées|changent|"
    r"redémarrées|redémarrent)", re.I)


class FactoryConfigure(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def walked(self, walked: dict, count: int) -> list[dict]:
        """The pages after the first `count` steps; fails the case when one
        of them found no control to activate."""
        steps = walked["steps"]
        for index, step in enumerate(STEPS[:count]):
            self.assertLess(index, len(steps), f"the walk stopped before « {step['click']} »: {walked}")
            self.assertTrue(steps[index]["found"], f"no control « {step['click']} » to activate: {steps[index]}")
        return [step["page"] for step in steps[:count]]

    def test_a_supported_setting_says_its_value_scope_and_consequences_is_confirmed_then_read_back(self):
        address = serve_usine(self.tree)
        walked = walk(address, STEPS, path=REVIEWER)
        start = visible_text(walked["start"])
        self.assertNotRegex(in_service(start), OPUS_5_5, "Claude is already in service before the setting")
        pages = self.walked(walked, 4)
        editor, choice, scope, applied = (visible_text(page) for page in pages)

        # The editor: the current value and the one it may become.
        self.assertIn(CODEX_READONLY, editor, "the editor does not show the current provider")
        self.assertIn(CLAUDE_READONLY, editor, "the editor does not offer the other provider of the role")
        # Before it is applied, what changes, for whom and with what effect.
        self.assertRegex(scope, rf"Valeur actuelle\s*:?\s*{re.escape(CODEX_READONLY)}",
                         f"the scope does not say the current value: « {scope} »")
        self.assertRegex(scope, rf"Nouvelle valeur\s*:?\s*{re.escape(CLAUDE_READONLY)}",
                         f"the scope does not say the new value: « {scope} »")
        self.assertRegex(scope, r"Portée\s*:?\s*Relecteur livraison", f"the scope does not say whom: « {scope} »")
        self.assertIn("Nouvelles sessions uniquement", scope, f"the scope does not say which sessions: « {scope} »")
        self.assertRegex(scope, r"Conséquences\s*:?\s*\S", f"the scope does not say its consequences: « {scope} »")
        self.assertNotRegex(scope, SESSIONS_CHANGED, "the sessions under way are said to be changed")
        self.assertIsNone(control(pages[2], "Préparer ce changement"),
                          "a setting the door supports is offered as a proposal")
        self.assertNotRegex(in_service(choice), OPUS_5_5, "choosing the provider changed what is in service")

        # Once confirmed: read back from what the door wrote, never the form.
        self.assertRegex(applied, r"(?i)\brelue?s?\b", f"the setting does not say it was read back: « {applied} »")
        self.assertRegex(in_service(applied), OPUS_5_5,
                         f"the reviewer does not run on Claude once the setting applied: « {applied} »")
        self.assertNotRegex(applied, SESSIONS_CHANGED, "the sessions under way are said to be changed")
        again = visible_text(walk(address, [], path=REVIEWER)["start"])
        self.assertRegex(in_service(again), OPUS_5_5, f"the page read again does not keep the setting: « {again} »")

    def test_a_setting_whose_door_does_nothing_is_not_written_around_it_nor_said_done(self):
        address = serve_usine(self.tree, doors={"provider-failover": "expires"})
        walked = walk(address, STEPS, path=REVIEWER)
        applied = visible_text(self.walked(walked, 4)[3])
        self.assertRegex(applied, r"(?i)expir|incertain", f"the page does not say the command did not answer: "
                                                          f"« {applied} »")
        self.assertNotRegex(applied, r"(?i)\b(appliqué|relu)\b", f"a success the door did not make: « {applied} »")
        self.assertNotRegex(in_service(applied), OPUS_5_5, "the setting is shown in service though its door did nothing")
        again = visible_text(walk(address, [], path=REVIEWER)["start"])
        self.assertNotRegex(in_service(again), OPUS_5_5,
                            f"the setting was written around its door: « {in_service(again)} »")


if __name__ == "__main__":
    unittest.main()
