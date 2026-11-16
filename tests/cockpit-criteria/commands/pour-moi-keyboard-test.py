#!/usr/bin/env python3
"""Criterion test 1 of BR « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-eyc5ah, replacement of B
af-4uzgzm; Spec af-fgcw0d, user stories 34 and 175, Testing Decisions 1, 5
and 8), its keyboard and narrow-screen half: on home-gestes, each request
of « Ce qui t’attend » opens, and each of its gestures goes on to its next
step, by the keyboard alone, at 1440 and 390 pixels, in the dark and the
light theme, on a page that stays readable and usable.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on home-gestes, and renders GET / in a headless
Chromium (home_destination.measure) at both widths:

- each request line is focused, then Enter is pressed on it; the request
  opens with its gestures, each one reachable by the keyboard, activated
  by it as the browser activates its own controls, with a focus a person
  sees;
- on the proposal, « Reporter » then « Refuser » are pressed the same way:
  the delays of Reporter, then the confirmation of the refusal, come up
  the same way usable -- and on the session the Factory paused and on the
  order paused by bin/order-pause, « Relancer »: its « Confirmer »;
- after each step, nothing makes the page unreadable or unusable
  (home_destination.problems: the document wider than the frame, a text
  cut or drawn on another, a contrast too low, a control without a name).

At 390 pixels, each gesture of the request open is also held by no folded
part of the page (pour_moi.walk), as at 1440 (pour-moi-unfolded-test.py).

False if a gesture or the field of its reason cannot be reached or
activated with the keyboard, or if the request open does not read at 390
pixels.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, problems  # noqa: E402
from pour_moi import control, requests_of, wait_for, walk  # noqa: E402

DATASET = "home-gestes"
WIDTHS = (1440, 390)
NARROW = 390
PROPOSAL = "af-p7k2m"
SESSION_BEAD = "af-s4l9q"
QUESTION = "af-q8n3v"
ORDER_PAUSE = "af-o2d7k"
# The gestures each request of home-gestes opens with.
GESTES = {
    PROPOSAL: ["Accepter", "Refuser", "Reporter"],
    SESSION_BEAD: ["Relancer"],
    QUESTION: ["Reporter"],
    ORDER_PAUSE: ["Relancer"],
}
# A gesture pressed, and the controls it brings up for its next step: the
# delays of Reporter, the confirmation of what changes the Factory.
NEXT = {
    (PROPOSAL, "Reporter"): ["Demain 09:00"],
    (PROPOSAL, "Refuser"): ["Raison"],
    (SESSION_BEAD, "Relancer"): ["Confirmer"],
    (ORDER_PAUSE, "Relancer"): ["Confirmer"],
}


class PourMoiKeyboard(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def lines(self, address: str) -> dict[str, str]:
        """The title « Ce qui t’attend » gives each request of home-gestes."""
        requests = wait_for(lambda: requests_of(address),
                            lambda found: set(GESTES) <= {r["id"] for r in found}, 20)
        titles = {r["id"]: r["quoi"] for r in requests}
        self.assertEqual([], [bead for bead in GESTES if bead not in titles],
                         f"« Ce qui t’attend » does not list them: it lists {sorted(titles)}")
        return titles

    def assert_by_the_keyboard(self, reading: dict, names: list[str], what: str) -> None:
        """Each control of `names` is on the page read, reachable by the
        keyboard, activated by it, with a focus a person sees."""
        width = reading["width"]
        for name in names:
            found = [c for c in reading["controls"] if c["name"] == name or c["name"].startswith(name)]
            self.assertTrue(found, f"{what}: no « {name} » at {width} px; the page shows "
                                   f"{[c['name'] for c in reading['controls']]}")
            gesture = found[0]
            self.assertFalse(gesture["disabled"], f"{what}: « {name} » cannot be used at {width} px")
            self.assertTrue(gesture["reachable"], f"{what}: the keyboard does not reach « {name} » at {width} px")
            self.assertTrue(gesture["native"], f"{what}: the keyboard cannot activate « {name} » at {width} px")
            self.assertTrue(gesture["focus_visible"], f"{what}: « {name} » draws no focus one sees at {width} px")

    def test_home_gestes_opens_each_request_and_its_gestures_by_the_keyboard_at_1440_and_390(self):
        address = self.tree.launch(DATASET)
        titles = self.lines(address)
        for bead, gestures in GESTES.items():
            line = titles[bead]
            pressed = [name for name in gestures if (bead, name) in NEXT]
            for theme in ("dark", "light"):
                for frame in measure(address, theme=theme, widths=WIDTHS,
                                     steps=({"click": line, "keys": True},
                                            *({"click": name, "keys": True} for name in pressed))):
                    opened, *after = frame["readings"][1:]
                    self.assertTrue(opened["step"]["found"], f"the keyboard finds no line « {line} »")
                    self.assert_by_the_keyboard(opened, gestures, f"« {line} » open, {theme}")
                    for name, reading in zip(pressed, after):
                        self.assertTrue(reading["step"]["found"], f"the keyboard finds no « {name} » on « {line} »")
                        self.assert_by_the_keyboard(reading, NEXT[(bead, name)],
                                                    f"« {name} » pressed on « {line} », {theme}")
                    self.assertEqual({}, problems(frame["readings"][1:], theme, ()),
                                     f"« {line} » open by the keyboard does not read")

    def test_home_gestes_holds_each_gesture_unfolded_at_390(self):
        address = self.tree.launch(DATASET)
        titles = self.lines(address)
        lines = [titles[bead] for bead in GESTES]
        walked = walk(address, [{"click": line} for line in lines], width=NARROW)
        self.assertEqual(len(lines), len(walked["steps"]), "the walk stopped before its end")
        for bead, line, step in zip(GESTES, lines, walked["steps"]):
            self.assertTrue(step["found"], f"the line « {line} » cannot be activated at {NARROW} px")
            for name in GESTES[bead]:
                gesture = control(step["page"], name)
                self.assertIsNotNone(gesture, f"« {line} » open shows no « {name} » at {NARROW} px")
                self.assertFalse(gesture["disabled"], f"« {name} » cannot be used at {NARROW} px")
                self.assertEqual([], gesture["folds"], f"« {name} » of « {line} » is reached only by unfolding "
                                                       f"{gesture['folds']} at {NARROW} px")


if __name__ == "__main__":
    unittest.main()
