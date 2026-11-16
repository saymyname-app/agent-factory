#!/usr/bin/env python3
"""Criterion test 1 of BR « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-eyc5ah, replacement of B
af-4uzgzm; Spec af-fgcw0d, user stories 34, 73, 75 and 175, Testing
Decisions 1, 3 and 8), its first half: Pour moi visible without unfolding
anything, on each dataset the criterion names, home-content-full,
home-long and home-gestes.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on its dataset, opens at GET / the request « Choisir le
format d’export » of « Ce qui t’attend » as a person does -- its line
activated in a headless Chromium (pour_moi.walk) -- and holds the request
open to its gesture, « Reporter »: shown, usable, and held by no folded
part of the page. On the overview served before this ticket, opening the
line unfolded the old zone « Détails techniques et actions », where the
request and its gestures were.

On home-gestes, every request of « Ce qui t’attend » is opened, one after
the other, and holds open each of its gestures: a proposal its « Accepter
», « Refuser » and « Reporter », a question its « Reporter », a session the
Factory paused and an order paused by bin/order-pause their « Relancer ».

False if a gesture of the request stays under the technical details, or
cannot be reached without unfolding them.

Each gesture of home-gestes done and traced at its source is held by
pour-moi-confirmed-gestures-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import LEGACY_SUMMARY, control, requests_of, visible_text, wait_for, walk  # noqa: E402

# The request of « Ce qui t’attend » both datasets hold besides the result:
# a question of the project Notes, « À faire ».
REQUEST = "Choisir le format d’export"
# Its gesture: hidden until later, then it comes back.
PUT_OFF = "Reporter"
# What home-gestes holds, by the beads its doors wrote, and the gestures each
# one opens with: a proposal, a session the Factory paused, a question, an
# order paused by bin/order-pause.
GESTES = {
    "af-p7k2m": ["Accepter", "Refuser", "Reporter"],
    "af-s4l9q": ["Relancer"],
    "af-q8n3v": ["Reporter"],
    "af-o2d7k": ["Relancer"],
}


class PourMoiUnfolded(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_unfolded(self, page: dict, name: str, request: str) -> None:
        gesture = control(page, name)
        self.assertIsNotNone(gesture, f"« {request} » open shows no « {name} »; it shows "
                                      f"{[c['name'] for c in page['controls']]}")
        self.assertFalse(gesture["disabled"], f"« {name} » cannot be used on « {request} » open")
        self.assertNotIn(LEGACY_SUMMARY, gesture["folds"], f"« {name} » is still under « {LEGACY_SUMMARY} »")
        self.assertEqual([], gesture["folds"], f"« {name} » of « {request} » is reached only by unfolding "
                                               f"{gesture['folds']}")

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

    def test_each_dataset_opens_its_requests_with_their_gestures_unfolded(self):
        # The criterion names three datasets: Pour moi is visible without
        # unfolding on each, one criterion observed whole.
        self.assert_open_with_its_gesture("home-content-full")
        self.assert_open_with_its_gesture("home-long")
        self.assert_each_request_of_home_gestes_unfolded()

    def assert_each_request_of_home_gestes_unfolded(self) -> None:
        address = self.tree.launch("home-gestes")
        requests = wait_for(lambda: requests_of(address),
                            lambda found: set(GESTES) <= {r["id"] for r in found}, 20)
        titles = {r["id"]: r["quoi"] for r in requests}
        self.assertEqual([], [bead for bead in GESTES if bead not in titles],
                         f"« Ce qui t’attend » does not list them: it lists {sorted(titles)}")
        lines = [titles[bead] for bead in GESTES]
        walked = walk(address, [{"click": line} for line in lines])
        self.assertEqual(len(lines), len(walked["steps"]), "the walk stopped before its end")
        for line, step in zip(lines, walked["steps"]):
            self.assertTrue(step["found"], f"the line « {line} » cannot be activated")
            self.assertEqual("/", step["page"]["path"], f"opening « {line} » left the overview")
        for bead, line, step in zip(GESTES, lines, walked["steps"]):
            for name in GESTES[bead]:
                self.assert_unfolded(step["page"], name, line)


if __name__ == "__main__":
    unittest.main()
