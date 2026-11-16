#!/usr/bin/env python3
"""Criterion test 3 of G1 « Usine — observation, fraîcheur et rôles réels »
(af-wrxrmg; Spec af-fgcw0d, user stories 124, 161 and 175, Testing
Decisions 1, 5 and 8): the destination Usine on the datasets
health-empty, health-loading, health-light, at 1440 and 390 px, in the light and the
dark theme, with the keyboard. The roles and the drawing of the flow
themselves are in factory-roles-test.py.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on its dataset, and has a headless Chromium render GET
/usine in two frames, 1440 and 390 px wide, once with the dark and once with
the light colour scheme preferred (usine_page.assert_usable). The roles
come from the Factory's configuration on every dataset, whatever its
sources answer.

False if a state does not draw its connections and its flow, if the roles
it shows are not those of the configuration, if a state the reference draws
whole (health-content, -long, -narrow, -light) does not show the sections of
the reference in its order, or if the page overflows, cuts
or overlaps a text, lacks contrast, or has a control the keyboard cannot
reach, activate or show focused.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import LaunchTree, assert_usable  # noqa: E402


class FactoryLayoutStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_health_empty_is_readable_and_usable_at_both_widths_in_both_themes(self):
        # The reviewer on GPT-5.6 and the author on Opus 5.5, as the
        # Factory's configuration says, whatever the dataset's sources answer.
        assert_usable(self, self.tree, "health-empty", themes=("dark", "light"), widths=(1440, 390),
                      panels=("connection-row-1", "flow-down-1"),
                      agents_say=(r"gpt[\s-]*5[.,-]6", r"opus[\s-]*5[.,-]5"),
                      section_order=None)

    def test_health_loading_is_readable_and_usable_at_both_widths_in_both_themes(self):
        # The reviewer on GPT-5.6 and the author on Opus 5.5, as the
        # Factory's configuration says, whatever the dataset's sources answer.
        assert_usable(self, self.tree, "health-loading", themes=("dark", "light"), widths=(1440, 390),
                      panels=("connection-row-1", "flow-down-1"),
                      agents_say=(r"gpt[\s-]*5[.,-]6", r"opus[\s-]*5[.,-]5"),
                      section_order=None)

    def test_health_light_is_readable_and_usable_at_both_widths_in_both_themes(self):
        # The reviewer on GPT-5.6 and the author on Opus 5.5, as the
        # Factory's configuration says, whatever the dataset's sources answer.
        assert_usable(self, self.tree, "health-light", themes=("dark", "light"), widths=(1440, 390),
                      panels=("connection-row-1", "flow-down-1"),
                      agents_say=(r"gpt[\s-]*5[.,-]6", r"opus[\s-]*5[.,-]5"),
                      section_order=["Machine d’exécution", "Connexions", "Fournisseurs et accès API",
                                     "Agents dans le workflow", "Suspension, reprise et arrêt",
                                     "Nettoyer les espaces inutilisés"])


if __name__ == "__main__":
    unittest.main()
