#!/usr/bin/env python3
"""Criterion test 3 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 31, 115, 118 and 120, Implementation Decisions 3 and 7 of
af-2zseit kept, Testing Decisions 1 and 8), on the datasets it names:
result-returned, result-conflict and result-outdated.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset -- with what its result says of itself
(`result`) when the case writes it -- and walks the page it serves at GET /
in a headless Chromium (result_trial.walk); a gesture is also sent over
HTTP as the browser sends it, behind the identity proxy (pour_moi.Operator).

- result-returned: the findings Benjamin returned stay visible in his exact
  words, with how the factory takes them up;
- result-conflict: an acceptance voided after a conflict is said voided,
  with the new judgement it needs, and no longer said accepted anywhere;
- result-outdated: Essai and Avis of the outdated dossier cannot be used,
  the bar says why, and a trial asked over HTTP is refused.

The records of D01 behind the same states -- findings returned and then a
new result, an acceptance voided by the pass -- are held by
home-result-returned-records-test.py and home-result-voided-records-test.py.

False if a voided acceptance stays effective, or an outdated dossier can be
accepted or launched.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import Operator  # noqa: E402
from result_trial import controls, folded, last, read_json, result_of, serve, shown, walk  # noqa: E402

HISTORY = "Historique et preuves"


class HomeResultRenewal(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # --- Criterion 3 ------------------------------------------------------------

    def test_result_returned_keeps_the_findings_in_their_exact_words_and_their_take_up(self):
        words = "Il manque l’export JSON de la liste, et le tri par date."
        address = serve(self.tree, "result-returned", {"words": words})
        page = last(walk(address, [{"click": HISTORY}]))
        text = shown(page) + " " + " ".join(folded(page, HISTORY))
        self.assertIn("Tes constats ont été rendus.", text)
        self.assertIn(words, text, "the findings returned are not shown in their exact words")
        # The dataset routes its finding « plus tard »: a proposition for later.
        self.assertRegex(text, r"(?i)plus tard", "how the factory takes the findings up is not shown")
        self.assertEqual([], [c["name"] for c in page["controls"]
                              if (c["name"].startswith("Essai") or c["name"] == "Avis") and not c["disabled"]],
                         "a result whose findings were returned is offered to judge again before its new dossier")

    def test_result_conflict_says_the_acceptance_voided_and_it_is_no_longer_effective(self):
        address = serve(self.tree, "result-conflict")
        page = last(walk(address, [{"click": HISTORY}]))
        text = shown(page)
        self.assertIn("Acceptation annulée", text, "the voided acceptance is not said")
        self.assertRegex(text, r"(?i)conflit", "the cause of the voiding is not said")
        self.assertRegex(text, r"(?i)nouveau jugement", "the new judgement it needs is not said")
        # Signalled where what waits for him is listed.
        waiting = [request["quoi"] + " " + (request.get("pourquoi") or "")
                   for request in read_json(address, "/api/requests")["requests"]]
        self.assertEqual(1, len([line for line in waiting if re.search(r"(?i)acceptation annulée", line)]),
                         f"the voided acceptance is not signalled among what waits for him: {waiting}")
        self.assertNotRegex(text, r"\bAccepté\b|Tu as accepté|fusion est en attente",
                            "the voided acceptance is still shown effective")
        _, result = result_of(address)
        self.assertNotIn(result["issue"], ("accepted", "merging", "merged"), "the voided acceptance is served effective")
        self.assertNotRegex(result["label"], r"\bAccepté\b", "the voided acceptance is served effective")

    def test_result_outdated_blocks_essai_and_avis_of_its_version(self):
        address = serve(self.tree, "result-outdated")
        chantier, before = result_of(address)
        walked = walk(address, [{"click": "Essai", "wait": 5000}, {"click": "Avis"}])
        page = last(walked)
        essai, avis = controls(page, "Essai"), controls(page, "Avis")
        self.assertEqual(([True], [True]), ([c["disabled"] for c in essai], [c["disabled"] for c in avis]),
                         "Essai or Avis of an outdated dossier can be used")
        self.assertRegex(shown(page), r"(?i)périmé", "the page does not say the dossier is outdated")
        self.assertEqual([], page["opened"], "Essai opened a tab on an outdated dossier")
        self.assertEqual([], controls(page, "Ton avis"), "Avis opened on an outdated dossier")
        # Asked over HTTP, as a page would ask it: refused, nothing launched.
        answer = Operator(address).gesture("essai", {"chantier": chantier})
        self.assertIn(answer.status, (400, 409), f"a trial of an outdated dossier is not refused: {answer!r}")
        self.assertRegex(answer.error(), r"(?i)périmé", f"the refusal does not say the dossier is outdated: {answer!r}")
        self.assertEqual((chantier, before), result_of(address), "the refusal changed the result")


if __name__ == "__main__":
    unittest.main()
