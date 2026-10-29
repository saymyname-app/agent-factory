#!/usr/bin/env python3
"""Criterion test 1 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 109, 110 and 121, Implementation Decisions 4, 5 and 7 of
af-2zseit kept, Testing Decisions 1, 2 and 8): on the cockpit launched, a
result to judge, Essai; datasets result-ready, result-outage and
result-repairing.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset of the profile -- as it is, or with what
its result says of itself (`result`) at a commit of its own -- and walks the
page it serves at GET / in a headless Chromium (result_trial.walk): what the
page asks to open in another tab is recorded there, and read afterwards.

- result-ready: Essai opens a new tab on the product launched at the
  revision of the dossier, by the isolated recipe of the project. The
  dossier is given a revision of its own, `revision`, a commit of the tree
  where the first dataset the profile declares, home-content, says a
  sentence the tree as served does not say: the product the tab shows says
  it, so it is that revision's, and no other's.
- a revision whose product does not start: Essai opens no tab on a product
  that is not there; the cockpit says the launch is down, and it is no
  judgement -- the result is still to judge.
- result-outage: the launch is down and the factory repairs it; the page
  says both, in those words, and Avis stays available: an outage is not a
  judgement.
- result-repairing: the factory corrects the findings Benjamin gave; the
  page says so, and says no outage: a judgement is not an outage.

False if Essai is a fake trial (no tab, or a tab on nothing that answers),
opens a product of another revision, or an outage is shown as a judgement.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from result_trial import controls, last, product_text, result_of, serve, shown, walk  # noqa: E402

# The sentence of the first dataset of the profile, and what the revision of
# the dossier says instead.
SAID_AT_HEAD = "Recherche dans les notes"
SAID_AT_REVISION = "Recherche plein texte des notes, version du dossier"
# The words that would make an outage, or a correction, a judgement.
JUDGEMENTS = ("Tu as accepté", "Accepté", "Tes constats ont été rendus", "Abandonné")
# How long a product launched by Essai may take to start, and the walk to
# wait for it once Essai is activated.
STARTING_SECONDS = 60
ESSAI_WAIT_MS = 75000


class HomeResultEssai(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def essai(self, address: str) -> dict:
        """The page at `address` walked: Essai activated, the page then read
        again once the trial had the time to start."""
        walked = walk(address, [{"click": "Essai", "wait": ESSAI_WAIT_MS}], seconds=150)
        self.assertEqual(1, len(controls(walked["start"], "Essai")), "the result has not one Essai")
        self.assertTrue(walked["steps"] and walked["steps"][0]["found"], "Essai is not on the page")
        return walked

    def assert_not_judged(self, page: dict, address: str) -> None:
        """The result is still to judge: nothing on the page, nor in the
        result the cockpit serves, says a judgement."""
        text = shown(page)
        self.assertEqual([], [words for words in JUDGEMENTS if words in text], "a judgement is said")
        _, result = result_of(address)
        self.assertIsNone(result["judged"], "the result is served as judged")

    # --- Criterion 1 ------------------------------------------------------------

    def test_essai_opens_a_new_tab_on_the_product_launched_at_the_revision_of_the_dossier(self):
        revision = self.tree.reword("home-content", {SAID_AT_HEAD: SAID_AT_REVISION})
        address = serve(self.tree, "result-ready", {"commit": revision})
        _, result = result_of(address)
        self.assertEqual(revision, result["commit"], "the dossier served is not at its revision")

        walked = self.essai(address)
        opened = last(walked)["opened"]
        self.assertEqual(1, len(opened), f"Essai did not open one new tab: {opened}")
        self.assertFalse(opened[0].startswith(address + "/") or opened[0] == address,
                         f"Essai opened the cockpit itself, not the product: {opened[0]}")
        product = product_text(opened[0], STARTING_SECONDS)
        self.assertTrue(product, f"nothing answers at the address of the tab: {opened[0]}")
        self.assertIn(SAID_AT_REVISION, product, "the tab does not show the product at the revision of the dossier")
        self.assertNotIn(SAID_AT_HEAD, product, "the tab shows the product of another revision")
        self.assert_not_judged(last(walked), address)

    def test_a_revision_whose_product_does_not_start_is_an_outage_said_as_such(self):
        # The first dataset of the profile, at this revision, is one its
        # recipe refuses to serve: the product does not start.
        revision = self.tree.reword("home-content", {'"visible_text": "Vue d’ensemble\\n':
                                                     '"visible_text": "Écran qu’aucune règle ne lit\\n'})
        address = serve(self.tree, "result-ready", {"commit": revision})

        walked = self.essai(address)
        page = last(walked)
        answering = [tab for tab in page["opened"] if product_text(tab, 5)]
        self.assertEqual([], answering, "Essai opened a tab on a product that does not start")
        self.assertRegex(shown(page), r"(?i)ne démarre pas", "the page does not say the product does not start")
        self.assert_not_judged(page, address)

    def test_result_outage_says_the_launch_down_and_its_repair_and_keeps_avis(self):
        address = serve(self.tree, "result-outage")
        walked = self.essai(address)
        page = last(walked)
        self.assertEqual([], page["opened"], "Essai opened a tab while the launch is down")
        text = shown(page)
        self.assertRegex(text, r"(?i)le produit ne démarre pas", "the outage is not said")
        self.assertRegex(text, r"(?i)l’usine répare le lancement", "the repair of the launch is not said")
        avis = controls(page, "Avis")
        self.assertEqual([False], [c["disabled"] for c in avis], "Avis is not available during the outage")
        self.assert_not_judged(page, address)

    def test_result_repairing_says_the_correction_of_the_findings_and_no_outage(self):
        address = serve(self.tree, "result-repairing")
        walked = self.essai(address)
        page = last(walked)
        self.assertEqual([], page["opened"], "Essai opened a tab on a result already judged")
        text = shown(page)
        self.assertIn("L’usine corrige tes constats.", text, "the correction of the findings is not said")
        self.assertNotRegex(text, r"(?i)ne démarre pas|en panne|répare le lancement",
                            "the correction of the findings is shown as an outage")


if __name__ == "__main__":
    unittest.main()
