#!/usr/bin/env python3
"""Criterion test of R13 « Faire lire aux Analyses les records D01 par le
lecteur de convoy-state » (af-lxk1nm; Spec af-fgcw0d, implementation
decision « État D01 commun aux vues » 2 -- « Une lecture illisible reste
inconnue » --, user stories 123, 148 and 149, Testing Decisions 1, 2 and 8;
Blocking Finding F1.6 of the end review at 96b3429f0dee).

The records are produced as Testing Decisions 2 says, as
home-d01-records-test.py (A1) produces them: the reference driver of the
Fixture City walks one convoy to its Delivered Outcome (the harness
FixtureCityWalk of tests/convoy-stops-fixture-city-test.py), then the case
accepts it with bin/owner-answer (verdict, record) and has its merge proven
by bin/outcome-promote (run). The tracker those commands wrote is the
tracker of a cockpit the launcher of the profile, bin/project-launch,
starts on a dataset of the profile that carries it. A1's own steps
(accepted, serve, …) are borrowed from its class, not inherited: its cases
are not run here.

Each case then makes one record of that convoy one the reader of
convoy-state does not take as a merge -- a proof of the merge it refuses,
or an acceptance voided under a proof of merge -- and reads, over HTTP, the
page « Analyses » at GET /analyses on its views « Résultats » and « Délais »
(analyses_destination.served), beside the page of the project of the
chantier at GET /projet/<project>, which reads the same records.

False if /analyses counts as merged, or measures as judged, a result whose
proof of merge the reader of convoy-state refuses or whose acceptance it
voided, while the page of the project does not say it merged.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from analyses_destination import served  # noqa: E402
from home_destination import LaunchTree  # noqa: E402

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

# What « Délais » says when no merged result of the period gives a delay.
NO_DELAY = "Délai médian indisponible : aucun résultat fusionné sur la période"


class AnalysesD01Records(stops.FixtureCityWalk):
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
    project_key = d01_records.HomeD01Records.project_key

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

    def merged_by_the_commands(self) -> dict:
        """The convoy accepted by bin/owner-answer and its merge proven by
        bin/outcome-promote: the tracker they wrote."""
        self.accepted()
        self.promote_ok()
        tracker = self.records()
        self.assertIn("gc.flow.promotion", self.convoy_record(tracker)["metadata"],
                      "bin/outcome-promote recorded no proof of merge")
        return tracker

    def assert_not_counted(self, address: str, tracker: dict, project_says: str) -> None:
        """/analyses neither counts the result of the convoy as merged nor
        measures its judgement, and the page of the project says
        `project_says` of the chantier, never merged."""
        title = self.convoy_record(tracker)["title"]
        results = served(address, "Résultats")
        self.assertEqual("Aucun résultat sur sept jours · fusion prouvée", results.says("p-1"),
                         "/analyses counts as merged a result the reader of convoy-state does not")
        self.assertNotIn(title, results.says("metrics-history-1"),
                         "/analyses lists as merged a result the reader of convoy-state does not")
        self.assertEqual(NO_DELAY, served(address, "Délais").says("p-1"),
                         "/analyses measures the judgement and the merge of a result the reader of convoy-state "
                         "does not take as merged")
        project = d01_records.page_text(address, f"/projet/{self.project_key(tracker)}")
        self.assertIn(project_says, project, f"the page of the project does not say « {project_says} »")
        self.assertNotIn("Fusion confirmée", project, "the page of the project says the merge confirmed")

    # --- Criterion 1 ------------------------------------------------------------

    def test_a_proof_of_merge_the_reader_refuses_is_counted_neither_merged_nor_judged(self):
        tracker = self.merged_by_the_commands()
        title = self.convoy_record(tracker)["title"]
        # As the commands wrote it, the merge is counted.
        results = served(self.serve(tracker), "Résultats")
        self.assertEqual("1 résultat sur sept jours · fusion prouvée", results.says("p-1"),
                         "/analyses does not count the merge bin/outcome-promote proved")
        self.assertIn(title, results.says("metrics-history-1"))
        # The proof of merge, its instant kept, names no commit merged: a
        # record the reader of convoy-state refuses.
        promotion = json.loads(self.convoy_record(tracker)["metadata"]["gc.flow.promotion"])
        promotion["merged"] = "pas-un-commit"
        self.convoy_record(tracker)["metadata"]["gc.flow.promotion"] = json.dumps(promotion)
        self.assert_not_counted(self.serve(tracker), tracker, "Inconnu")

    def test_a_proof_of_merge_over_a_voided_acceptance_is_counted_neither_merged_nor_judged(self):
        tracker = self.merged_by_the_commands()
        # The acceptance voided, as a red replay voids it: it stays in the
        # judgement, with the control that voided it.
        judgement = json.loads(self.convoy_record(tracker)["metadata"]["gc.flow.judgement"])
        judgement["answers"][-1]["voided"] = {"cause": "regression", "at": judgement["answers"][-1]["at"]}
        self.convoy_record(tracker)["metadata"]["gc.flow.judgement"] = json.dumps(judgement, ensure_ascii=False)
        self.assert_not_counted(self.serve(tracker), tracker, "Incohérence")


if __name__ == "__main__":
    unittest.main()
