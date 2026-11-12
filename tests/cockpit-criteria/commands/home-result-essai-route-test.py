#!/usr/bin/env python3
"""Criterion test of R11 (af-ksan9t; Spec af-fgcw0d, user story 109,
Testing Decisions 1 and 8; Blocking Finding F1.4 of the final code review
at 96b3429f0dee): on the cockpit launched, POST /api/actions/essai on a
result to judge answers the address of the product launched at the exact
revision of the dossier; dataset result-essai.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset result-essai of the profile, whose
result says it is at a revision of its own (result_trial.serve): a commit
of the tree where the first dataset the profile declares, home-content,
says a sentence the tree as served does not say. The operator sends Essai
as the browser sends it, at the address of the launch (`operator_front`),
for the chantier and the commit of the dossier the cockpit serves at
GET /api/projects. The product at the address answered says the sentence of
that revision, and not the sentence of the tree as served: it is that
revision's product, and no other's.

False if the answer gives no address, names another revision than the
dossier's, or the product at its address is the product of another
revision. Nothing here calls the code of the cockpit: the proof of the
revision went through an internal function of the actions until R11.

The dossier may also move on between the moment the cockpit read it and the
launch: the result is delivered again at another revision once the page is
served (`redelivered`, the tracker of the launch rewritten as the Acceptance
Session reads it), so the session launches that other revision. Essai then
gives no address, and says the dossier changed: no tab on the product of a
revision the page does not show (F1.1 and F1.2 of the code review of R11).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from result_trial import Operator, product_text, result_of, serve  # noqa: E402

# How long a product launched by Essai may take to start.
STARTING_SECONDS = 60
# The sentence of the first dataset of the profile, what the revision of the
# dossier says instead, and what the revision it is delivered again at says.
SAID_AT_HEAD = "Recherche dans les notes"
SAID_AT_REVISION = "Recherche plein texte des notes, version du dossier"
SAID_REDELIVERED = "Recherche plein texte des notes, version livrée ensuite"


class HomeResultEssaiRoute(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_essai_answers_the_address_of_the_product_launched_at_the_revision_of_the_dossier(self):
        revision = self.tree.reword("home-content", {SAID_AT_HEAD: SAID_AT_REVISION})
        address = serve(self.tree, "result-essai", {"commit": revision})
        chantier, result = result_of(address)
        self.assertEqual(revision, result["commit"], "the dossier served is not at its revision")

        answer = Operator(address).gesture("essai", {"chantier": chantier, "commit": revision})
        self.assertEqual(200, answer.status, f"Essai on the dossier shown is not answered: {answer!r}")
        self.assertEqual(revision, answer.body.get("commit"), f"Essai names another revision: {answer!r}")
        launched = answer.body.get("address") or ""
        self.assertRegex(launched, r"^https?://", f"Essai answers no address: {answer!r}")
        self.assertFalse(launched.rstrip("/") == address or launched.startswith(address + "/"),
                         f"Essai answers the cockpit itself, not the product: {launched}")
        product = product_text(launched, STARTING_SECONDS)
        self.assertTrue(product, f"nothing answers at the address Essai gives: {launched}")
        self.assertIn(SAID_AT_REVISION, product,
                      "the product at the address is not the product at the revision of the dossier")
        self.assertNotIn(SAID_AT_HEAD, product, "the product at the address is of another revision")

    def test_essai_gives_no_address_when_the_session_launches_another_revision_than_the_dossier(self):
        revision = self.tree.reword("home-content", {SAID_AT_HEAD: SAID_AT_REVISION})
        redelivered = self.tree.reword("home-content", {SAID_AT_HEAD: SAID_REDELIVERED})
        address = serve(self.tree, "result-essai", {"commit": revision, "redelivered": redelivered})
        chantier, result = result_of(address)
        self.assertEqual(revision, result["commit"], "the dossier served is not at its revision")

        answer = Operator(address).gesture("essai", {"chantier": chantier, "commit": revision})
        self.assertIn(answer.status, (400, 409),
                      f"Essai answered though the session launched another revision: {answer!r}")
        self.assertNotIn("address", answer.body or {}, f"Essai gives the address of another revision: {answer!r}")
        self.assertRegex(answer.error(), r"(?i)n’est plus", f"the refusal does not say the dossier changed: {answer!r}")


if __name__ == "__main__":
    unittest.main()
