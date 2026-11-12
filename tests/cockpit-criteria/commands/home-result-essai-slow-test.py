#!/usr/bin/env python3
"""Criterion test 1 of R24 « Rétablir le contrôle rouge de la branche
d'intégration (d329136a3e2c) » (af-rayc44; Spec af-fgcw0d, user story 121,
Testing Decisions 1, 3 « erreurs/timeout » and 8): the regression command
of the project was red on integration/af-fgcw0d because, on a loaded host,
A2's `test_essai_opens_a_new_tab_on_the_product_launched_at_the_revision_of_the_dossier`
saw no tab: the page read « Unexpected token '<', "<!DOCTYPE "... is not
valid JSON ». Essai lasted more than a minute -- the product of the
revision took that long to start -- and the identity proxy in front of the
cockpit, which stands for Tailscale Serve, dropped the request at sixty
seconds, while the cockpit still waited for its answer.

The case makes that minute certain instead of waiting for a loaded host:
the dossier is given a revision of its own whose product never answers its
health probe, so the launch Essai asks for waits the whole time it is given
before it says the product does not start. The cockpit is launched with the
launcher of the profile, bin/project-launch, on result-ready (the identity
proxy in front, in HTTPS), and Essai is sent as the operator's browser sends
it, through that proxy.

False if the operator gets no answer of the cockpit -- a connection dropped,
a page that is not the cockpit's JSON -- or an answer that does not say the
product does not start.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, git  # noqa: E402
from result_trial import Operator, result_of, serve  # noqa: E402

# The launch recipe of the profile, at the revision of the dossier: alive,
# listening on nothing, until it is stopped.
RECIPE = "bin/cockpit-isolated"
NEVER_ANSWERS = "#!/usr/bin/env python3\nimport time\ntime.sleep(3600)\n"
# The proxy dropped the request at this many seconds; the launch of a
# product that never answers takes longer to give up.
PROXY_DROPPED_AT_SECONDS = 60


class HomeResultEssaiSlow(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def revision_whose_product_never_answers(self) -> str:
        """A commit of the tree where the launch recipe never answers; the
        tree is back at its first commit afterwards."""
        repo = self.tree.repo
        (repo / RECIPE).write_text(NEVER_ANSWERS, encoding="utf-8")
        git(repo, "commit", "--quiet", "--all", "--message", "the product of this revision never answers")
        revision = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "--quiet", self.tree.head)
        return revision

    # --- Criterion 1 ------------------------------------------------------------

    def test_an_essai_longer_than_a_minute_reaches_the_operator_as_the_cockpit_answers_it(self):
        revision = self.revision_whose_product_never_answers()
        address = serve(self.tree, "result-ready", {"commit": revision})
        self.assertTrue(address.startswith("https://"), f"result-ready is not served behind the identity proxy: {address}")
        chantier, result = result_of(address)
        self.assertEqual(revision, result["commit"], "the dossier served is not at its revision")

        answer = Operator(address).gesture("essai", {"chantier": chantier, "commit": revision})

        self.assertEqual("", answer.broken, f"the request of Essai broke before the cockpit answered: {answer!r}")
        self.assertIsInstance(answer.body, dict, f"the answer of Essai is not the cockpit's JSON: {answer!r}")
        self.assertGreater(answer.seconds, PROXY_DROPPED_AT_SECONDS,
                           f"Essai answered within a minute: the case does not prove its long wait: {answer!r}")
        self.assertIn(answer.status, (400, 409), f"a product that does not start is not refused: {answer!r}")
        self.assertRegex(answer.error(), r"(?i)ne démarre pas", f"the answer does not say the product does not start: {answer!r}")
        _, after = result_of(address)
        self.assertIsNone(after["judged"], "the outage is served as a judgement")


if __name__ == "__main__":
    unittest.main()
