#!/usr/bin/env python3
"""Criterion test of the Blocking Finding F2.13 of the end review, tour 2
(Spec af-fgcw0d, user story 117: « je veux distinguer accepté, fusion en
attente, fusion en cours et fusion confirmée, afin de ne pas confondre mon
accord avec son exécution »; implementation decision « État D01 commun aux
vues »): the card of the run of an open D01 convoy says the issue its
result says.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset of the profile whose convoy of the
chantier « Reprise du cockpit » (project Usine) is still open and carries
the records of its state -- result-accepted (the acceptance recorded, no
proof of merge), result-merging (the proof of the merge recorded, the
convoy not closed yet), result-conflict (the acceptance voided by a
conflict) -- and reads, over HTTP, the card of the run of that convoy on
the page Runs at GET /runs (filter « Tous ») and in « Derniers runs » at
GET /, as home-recent-runs-test.py (K) reads them. The result open on the
home says the same issue (home-result-states-test.py, A1).

False if the card says « En cours · En attente d'un agent » while the
result says « Accepté », « Fusion en cours » or « Acceptation annulée ».
"""

from __future__ import annotations

import html
import importlib.machinery
import importlib.util
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from home_destination import LaunchTree  # noqa: E402


def load(path: Path):
    loader = importlib.machinery.SourceFileLoader(path.name.replace("-", "_").removesuffix(".py"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its class: the test classes named at the top of
# a file are the ones collected there.
recent_runs = load(HERE / "home-recent-runs-test.py")

# The run of the convoy of the chantier of the result, in every result-* state.
RUN = "/runs/run?id=synthetic-chantier-usine"
# The status of a card, as its badge draws it.
BADGE = re.compile(r'<span class="rn-badge[^"]*"[^>]*>(.*?)</span></div>', re.S)


def badge(card: str) -> str:
    found = BADGE.search(card)
    assert found, f"a card without its status: {card}"
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))).split())


class RunsD01OpenOutcome(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_card_says(self, state: str, issue: str) -> None:
        address = self.tree.launch(state)
        for where, cards in (("the page Runs", recent_runs.runs_cards(address)),
                             ("« Derniers runs » of the home", recent_runs.home_cards(address))):
            self.assertIn(RUN, cards, f"{where} draws no card of the run of the convoy: {list(cards)}")
            card = cards[RUN]
            status = badge(card)
            self.assertIn(issue, status, f"{state}: the card on {where} does not say « {issue} »: « {status} »")
            self.assertNotIn("En attente d'un agent", recent_runs.text(card),
                             f"{state}: the card on {where} waits for an agent while the result says « {issue} »")
            self.assertNotIn("✓", status, f"{state}: the card on {where} ticks a result not merged: « {status} »")

    def test_an_accepted_result_is_accepted_on_its_run_card(self):
        self.assert_card_says("result-accepted", "Accepté")

    def test_a_merge_under_way_is_said_on_its_run_card(self):
        self.assert_card_says("result-merging", "Fusion en cours")

    def test_a_voided_acceptance_is_said_on_its_run_card(self):
        self.assert_card_says("result-conflict", "Acceptation annulée")


if __name__ == "__main__":
    unittest.main()
