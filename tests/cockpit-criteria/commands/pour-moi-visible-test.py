#!/usr/bin/env python3
"""Criterion test 1 of B « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-4uzgzm; Spec af-fgcw0d, user
stories 34, 73, 75 and 175, Testing Decisions 1, 3 and 8), its first half:
Pour moi visible without unfolding anything, on the datasets the criterion
names, home-content-full and home-long.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on its dataset, opens at GET / the request « Choisir le
format d’export » of « Ce qui t’attend » as a person does -- its line
activated in a headless Chromium (pour_moi.walk) -- and holds the request
open to its gesture, « Reporter »: shown, usable, and held by no folded
part of the page. On the overview served before this ticket, opening the
line unfolded the old zone « Détails techniques et actions », where the
request and its gestures were.

False if a gesture of the request stays under the technical details, or
cannot be reached without unfolding them.

The other gestures of the criterion (refuse with a reason, put off, relaunch)
are held by pour-moi-gestures-test.py, on a tracker that holds what they
apply to: the two datasets named hold no proposal and no paused session.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import LEGACY_SUMMARY, control, visible_text, walk  # noqa: E402

# The request of « Ce qui t’attend » both datasets hold besides the result:
# a question of the project Notes, « À faire ».
REQUEST = "Choisir le format d’export"
# Its gesture: hidden until later, then it comes back.
PUT_OFF = "Reporter"


class PourMoiVisible(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_open_with_its_gesture(self, dataset: str) -> None:
        """On `dataset`, the line of the request opens it in « Pour moi »:
        its title and its gesture shown, the gesture usable and held by no
        folded part -- neither the old technical zone nor any other."""
        walked = walk(self.tree.launch(dataset), [{"click": REQUEST}])
        self.assertIn(REQUEST, visible_text(walked["start"]), "« Ce qui t’attend » does not list the request")
        step = walked["steps"][0]
        self.assertTrue(step["found"], "the line of the request cannot be activated")
        page = step["page"]
        self.assertEqual("/", page["path"], "opening the request left the overview")
        gesture = control(page, PUT_OFF)
        self.assertIsNotNone(gesture, f"the request open shows no « {PUT_OFF} »; it shows {[c['name'] for c in page['controls']]}")
        self.assertFalse(gesture["disabled"], f"« {PUT_OFF} » cannot be used on the request open")
        self.assertNotIn(LEGACY_SUMMARY, gesture["folds"], f"« {PUT_OFF} » is still under « {LEGACY_SUMMARY} »")
        self.assertEqual([], gesture["folds"], f"« {PUT_OFF} » is reached only by unfolding {gesture['folds']}")

    def test_home_content_full_opens_a_request_with_its_gesture_unfolded(self):
        self.assert_open_with_its_gesture("home-content-full")

    def test_home_long_opens_a_request_with_its_gesture_unfolded(self):
        self.assert_open_with_its_gesture("home-long")


if __name__ == "__main__":
    unittest.main()
