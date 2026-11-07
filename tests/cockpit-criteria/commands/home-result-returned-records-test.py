#!/usr/bin/env python3
"""Criterion test 3 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 31, 115 and 116, Implementation Decision 7 of af-2zseit kept,
Testing Decisions 1, 2 and 8), on the records of D01: findings returned,
then a new result.

The records are produced as Testing Decisions 2 says: the reference driver
of the Fixture City walks one convoy to its Delivered Outcome (the harness
FixtureCityWalk of tests/convoy-stops-fixture-city-test.py, walked once and
restored); Benjamin's answer « constats rendus » is recorded by
bin/owner-answer, then the passes of the order publish the repair of his
finding, deliver it and run the end of the Spec again, as
tests/owner-answer-promotion-fixture-city-test.py walks them. At each step,
the tracker the commands wrote is the tracker of a cockpit the launcher of
the profile, bin/project-launch, starts (pour_moi.serve_tracker), walked in
a headless Chromium (result_trial.walk).

- findings returned: the result says so, and each finding stays in his
  exact words;
- the repair published: the take-up of his finding is shown, its words
  unchanged;
- the new result: a new dossier to judge, which shows what changed since
  his last judgement -- his finding and what was done for it --, Essai and
  Avis usable on it again.

False if a finding is shown in other words than his, or the new dossier
does not show what changed since the last judgement.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import serve_tracker  # noqa: E402
from result_trial import controls, folded, last, shown, walk  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


stops = load("convoy-stops-fixture-city-test.py")
# bin/owner-answer, the entry point of the profile that records the answer.
OWNER = ROOT / "bin" / "owner-answer"
APPROVER = "benjamin"
HISTORY = "Historique et preuves"
SINCE = "Depuis ton dernier jugement"


class HomeResultReturnedRecords(stops.FixtureCityWalk):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        super().tearDownClass()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def owner_ok(self, command: str, *args) -> dict:
        proc = self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", APPROVER, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def page(self, steps: list[dict]) -> tuple[dict, str]:
        """The home page of a cockpit started on the records as the commands
        left them, walked through `steps`; and its whole text, every folded
        part included."""
        self.tree.stop_all()
        tracker = json.loads(self.tracker.read_text(encoding="utf-8"))
        page = last(walk(serve_tracker(self.tree, tracker["beads"]), steps))
        return page, " ".join([shown(page), *(d["text"] for d in page["folded"])])

    # --- Criterion 3 ------------------------------------------------------------

    def test_findings_returned_stay_in_their_words_then_the_new_dossier_shows_what_changed_since(self):
        finding = "La liste des éléments ne se relit pas en JSON à l'adresse /items."
        later = "Un export CSV de la liste serait utile."
        repair = {
            "title": "Servir la liste des éléments en JSON",
            "what_it_delivers": "Le produit sert la liste des éléments du jeu de données en JSON à l'adresse /items.",
            "demonstration_line": "Sur le produit lancé avec le jeu de données « content », GET /items rend les trois éléments.",
            "acceptance_criteria": [{
                "entry_point": "GET /items sur le produit lancé avec le jeu de données « content »",
                "observable": "le champ items contient « alpha », « beta », « gamma »",
                "false_if": "un élément manque, ou /items ne répond pas"}]}
        first = self.walk_to_delivered(inject="proposition")
        for ticket in self.shown()["tickets"]:
            for found in ticket.get("findings") or []:
                if found["classification"] == "proposal":
                    self.owner_ok("verdict", "--proposition", found["id"], "--verdict", "sans suite", "--words", "Vu.")
        findings = self.workspace / "owner-findings.json"
        findings.write_text(json.dumps({"findings": [
            {"text": finding, "cites": {"kind": "user_story", "ref": "user story 2"}, "repair": repair},
            {"text": later, "later": True}]}, ensure_ascii=False), encoding="utf-8")
        self.owner_ok("record", "--response", "constats rendus", "--words", "Il manque le JSON.",
                      "--commit", first["commit"], "--pack-digest", first["pack"], "--findings", findings)

        # Returned: said, and each finding in his exact words.
        page, text = self.page([{"click": HISTORY}])
        self.assertIn("Tes constats ont été rendus.", text, "the findings returned are not said")
        for words in (finding, later):
            self.assertIn(words, text, f"the finding is not shown in his exact words: « {words} »")

        # The repair of his finding published by the next pass: its take-up shown.
        (self.workspace / "proposal-door").write_text(
            '#!/bin/sh\n[ "$1" = create ] && echo "PROPOSITION CRÉÉE: fx-later — notée" || echo 0\n')
        self.order_pass()
        page, text = self.page([{"click": HISTORY}])
        self.assertIn("L’usine corrige tes constats.", text, "the take-up of the findings is not said")
        self.assertIn(finding, text, "the finding taken up is no longer shown in his exact words")
        self.assertIn(repair["title"], text, "what the factory does for the finding is not shown")

        # The flow passes again by itself to a new result.
        second = None
        for _ in range(48):
            event = self.driver("advance")
            second = self.shown()["convoy"]["delivered"]
            if second:
                break
            self.assertFalse(event["idle"], "the walk settled before the Outcome was Delivered again")
        self.assertTrue(second, "the Outcome is not Delivered again after 48 events")
        self.assertNotEqual(first["commit"], second["commit"])

        page, text = self.page([])
        self.assertIn("Le cockpit attend ton avis", text, "the new result is not to judge")
        changes = " ".join(folded(page, SINCE)) or text
        self.assertIn(SINCE, text, "the new dossier does not show what changed since the last judgement")
        self.assertIn(finding, changes, "what changed since the last judgement does not name his finding")
        self.assertIn(second["commit"][:7], text, "the new dossier is not the new version")
        essai, avis = controls(page, "Essai"), controls(page, "Avis")
        self.assertEqual(([False], [False]), ([c["disabled"] for c in essai], [c["disabled"] for c in avis]),
                         "Essai and Avis cannot be used on the new dossier")


if __name__ == "__main__":
    unittest.main()
