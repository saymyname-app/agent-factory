#!/usr/bin/env python3
"""Criterion tests of R14 « Cartes de runs : état D01 lu depuis les records
du flux, abandon jamais « Fusionné » » (af-5p4b3w; Spec af-fgcw0d,
implementation decision « État D01 commun aux vues » 2 -- « Ticket
fermé/intégré ne signifie pas fusion du résultat dans la branche protégée »
--, user stories 119, 123 and 136, Testing Decisions 1, 2 and 8; Blocking
Finding F1.22 of the end review at 96b3429f0dee).

The records are produced as Testing Decisions 2 says, as
home-d01-records-test.py (A1) produces them: the reference driver of the
Fixture City walks one convoy to its Delivered Outcome (the harness
FixtureCityWalk of tests/convoy-stops-fixture-city-test.py), then the case
answers with bin/owner-answer (verdict, record) and settles the answer with
bin/outcome-promote (run). The tracker those commands wrote is the tracker
of a cockpit the launcher of the profile, bin/project-launch, starts on a
dataset of the profile that carries it. A1's own steps (judged, accepted,
serve, …) are borrowed from its class, not inherited: its cases are not run
here.

Each case reads the card of the run of the convoy (`/runs/run?id=<convoy>`)
over HTTP, on the page Runs at GET /runs (filter « Tous ») and, for the
abandon, in « Derniers runs » at GET /, as home-recent-runs-test.py (K)
reads them; and the result open on the home, as a headless Chromium renders
it (home_destination.measure).

False if the card of an abandoned convoy says « Fusionné » or « Terminé »,
or ticks its status, while the result says « Abandonné »; or if a card says
« Fusionné » for a convoy whose tickets are merged into the integration
branch with no proof of the final merge recorded.
"""

from __future__ import annotations

import html
import importlib.machinery
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from home_destination import LaunchTree, measure, says  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load(path: Path):
    loader = importlib.machinery.SourceFileLoader(path.name.replace("-", "_").removesuffix(".py"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The modules are bound, not their classes: the test classes named at the
# top of a file are the ones collected there.
stops = load(ROOT / "tests" / "convoy-stops-fixture-city-test.py")
d01_records = load(HERE / "home-d01-records-test.py")
recent_runs = load(HERE / "home-recent-runs-test.py")

REASON = "Le besoin a disparu avec la nouvelle version du tableau."
WORDS = "Accepté, c'est ce que je voulais."
# The status of a card, as its badge draws it.
BADGE = re.compile(r'<span class="rn-badge[^"]*"[^>]*>(.*?)</span></div>', re.S)


def badge(card: str) -> str:
    """The text of the status of a card, its mark included."""
    found = BADGE.search(card)
    assert found, f"a card without its status: {card}"
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))).split())


class RunsD01Outcome(stops.FixtureCityWalk):
    maxDiff = None

    # The records by the commands of D01 and the cockpit launched on them,
    # as A1 has them -- its steps, never its class, which would be collected.
    owner_ok = d01_records.HomeD01Records.owner_ok
    promote_ok = d01_records.HomeD01Records.promote_ok
    judged = d01_records.HomeD01Records.judged
    accepted = d01_records.HomeD01Records.accepted
    records = d01_records.HomeD01Records.records
    serve = d01_records.HomeD01Records.serve
    convoy_record = d01_records.HomeD01Records.convoy_record

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tree = LaunchTree()
        cls.served = 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        super().tearDownClass()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def card(self, cards: dict[str, str], where: str) -> str:
        """The card of the run of the convoy among `cards`."""
        href = f"/runs/run?id={self.convoy}"
        self.assertIn(href, cards, f"{where} draws no card of the run of the convoy: {list(cards)}")
        return cards[href]

    # --- Criterion 1 ------------------------------------------------------------

    def test_an_abandoned_convoy_is_abandoned_on_its_run_card_as_on_the_result(self):
        self.judged()
        self.owner_ok("record", "--response", "abandonné", "--reason", REASON)
        self.promote_ok()
        address = self.serve(self.records())
        home = measure(address)[0]
        # The result says it: « Chantier abandonné. Rien n’a été fusionné. »
        self.assertIn("abandonné", says(home, "panel-3"), "the result open on the home does not say the abandon")
        for where, cards in (("the page Runs", recent_runs.runs_cards(address)),
                             ("« Derniers runs » of the home", recent_runs.home_cards(address))):
            status = badge(self.card(cards, where))
            self.assertIn("Abandonné", status, f"the card on {where} does not say the abandon: « {status} »")
            self.assertNotIn("✓", status, f"the card on {where} ticks an abandon: « {status} »")
            self.assertNotRegex(status, r"Fusionné|Terminé",
                                f"the card on {where} lets one believe in a merge: « {status} »")

    # --- Criterion 2 ------------------------------------------------------------

    def test_a_card_says_merged_only_with_the_proof_of_the_final_merge(self):
        self.accepted()
        tracker = self.records()
        # The tickets merged into the integration branch, the convoy closed
        # as accepted, and no proof of the merge into the protected branch.
        record = self.convoy_record(tracker)
        record["status"] = "closed"
        record["closed_at"] = "2026-10-12T11:00:00+02:00"
        record["metadata"]["gc.flow.closed"] = json.dumps(
            {"how": "accepted", "said": WORDS, "approver": "benjamin", "at": "2026-10-12T11:00:00+02:00"})
        record["metadata"].pop("gc.flow.promotion", None)
        status = badge(self.card(recent_runs.runs_cards(self.serve(tracker)), "the page Runs"))
        self.assertNotIn("Fusionné", status, f"the card says merged with no proof of the final merge: « {status} »")
        # The proof recorded by bin/outcome-promote: now merged.
        self.promote_ok()
        status = badge(self.card(recent_runs.runs_cards(self.serve(self.records())), "the page Runs"))
        self.assertIn("Fusionné", status, f"the card does not say the merge its proof records: « {status} »")


if __name__ == "__main__":
    unittest.main()
