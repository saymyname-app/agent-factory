#!/usr/bin/env python3
"""Criterion test 1 of H « Usine — arrêt propre et reprise vérifiée exposés »,
its frozen states (af-69qhlk; Spec af-fgcw0d, user stories 82, 83, 165 and
175, Testing Decisions 1 and 5): the panel « Suspension, reprise et arrêt »
of the reference (prototype/cockpit-b-zones-20261012 at 632deea, states
factory-draining, factory-suspended and factory-resuming, anchors
`shutdown-phase-1` and `shutdown-step-N`) on the real page.

Each case launches the cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and reads GET /usine; what
the state is made of is the supervisor and the stop of that dataset, never
the words of the reference: « simulation », « exemple » are not served.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_arret import assert_usable, said_until  # noqa: E402

PANELS = ("shutdown-phase-1", "shutdown-step-1", "shutdown-step-2", "shutdown-step-3")
STEPS = ("Arrêter les nouveaux départs", "Atteindre les points de reprise", "Comparer le travail avant / après")


class FactoryStopStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_state(self, dataset: str, phase: str) -> None:
        text = said_until(self.tree.launch(dataset), phase)
        self.assertIn(phase, text, f"{dataset} does not show its phase: « {text} »")
        for step in STEPS:
            self.assertIn(step, text, f"{dataset} does not show the step « {step} »")
        for invented in ("simulation", "dans cet exemple", "sont simulées"):
            self.assertNotIn(invented, text, f"{dataset} serves the words of the reference")
        assert_usable(self, self.tree, dataset, themes=("dark", "light"), widths=(1440, 390), panels=PANELS,
                      agents_say=(), section_order=None)

    def test_factory_draining_shows_the_work_going_to_rest(self):
        self.assert_state("factory-draining", "Travaux en cours de mise au repos")

    def test_factory_suspended_shows_the_suspension_confirmed(self):
        self.assert_state("factory-suspended", "Suspension confirmée")

    def test_factory_resuming_shows_the_resume_under_way(self):
        self.assert_state("factory-resuming", "Reprise en cours")


if __name__ == "__main__":
    unittest.main()
