"""The indicators of the Analyses (cockpit.analyses.indicators; D,
af-ten1sp): what each says when its source is not read, has failed, or
gives nothing to count -- never a zero, never a value of example. The
values computed from full sources, the page and the chart are proven on the
launched cockpit by tests/cockpit-criteria/commands/analyses-destination-*."""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.analyses.indicators import CI, DECISIONS, DELAY, RESULTS, analyses  # noqa: E402
from cockpit.core.readmodel import PARIS  # noqa: E402

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=PARIS).timestamp()


def row(value, failed_at=None, freshness="fresh"):
    return {"value": value, "read_at": None if value is None else NOW, "failed_at": failed_at,
            "freshness": "unknown" if value is None else freshness}


def convoy(merged, accepted=None, voided=False):
    answers = [{"response": "accepted", "at": accepted, **({"voided": {"cause": "red"}} if voided else {})}]
    return {"id": "c", "title": "Export", "created_at": "2026-10-12T08:00:00+02:00", "metadata": {
        "gc.flow.promotion": json.dumps({"at": merged}),
        "gc.flow.delivered": json.dumps({"at": "2026-10-12T09:00:00+02:00"}),
        "gc.flow.judgement": json.dumps({"answers": answers if accepted else []})}}


class AnalysesIndicatorsTest(unittest.TestCase):
    def test_sources_not_read_yet_give_no_value_and_say_they_are_being_read(self):
        data = analyses({"flow": row(None), "github": row(None), "beads": row(None)}, [], NOW)
        for key in (DECISIONS, RESULTS, DELAY, CI):
            self.assertIsNone(data["indicators"][key]["value"], key)
            self.assertIn("en cours de lecture", data["indicators"][key]["reason"], key)
        self.assertEqual([None] * 4, [serie["values"] for serie in data["volumes"]])

    def test_a_failed_read_says_when_it_was_last_tried(self):
        data = analyses({"flow": row(None, failed_at=NOW), "github": row(None, failed_at=NOW)}, [], NOW)
        self.assertEqual("les tickets du flux n’ont pas pu être lus (dernier essai le 12/10 à 12:00 (Paris))",
                         data["indicators"][RESULTS]["reason"])
        self.assertEqual("GitHub n’a pas répondu (dernier essai le 12/10 à 12:00 (Paris))",
                         data["indicators"][CI]["reason"])

    def test_without_a_declared_repository_github_is_not_read_and_the_ci_says_why(self):
        data = analyses({"flow": row([])}, [], NOW)
        self.assertIsNone(data["indicators"][CI]["value"])
        self.assertIn("aucun dépôt GitHub n’est déclaré", data["indicators"][CI]["reason"])
        self.assertEqual("0", data["indicators"][RESULTS]["value"], "the flow was read: none merged is a count")

    def test_no_completed_ci_run_is_no_rate_rather_than_zero_percent(self):
        github = {"repository": "o/r", "pull_requests": [], "workflow_runs": [
            {"status": "in_progress", "conclusion": None, "created_at": "2026-10-12T11:00:00+02:00"}]}
        data = analyses({"github": row(github)}, [], NOW)
        self.assertIsNone(data["indicators"][CI]["value"])
        self.assertEqual("aucune exécution CI terminée sur la période", data["indicators"][CI]["reason"])
        self.assertEqual([0] * 7, data["volumes"][3]["values"], "the runs were read: none succeeded is a count")

    def test_no_merged_result_gives_no_median_delay(self):
        data = analyses({"flow": row([])}, [], NOW)
        self.assertIsNone(data["indicators"][DELAY]["value"])
        self.assertEqual("aucun résultat fusionné sur la période", data["indicators"][DELAY]["reason"])

    def test_a_voided_acceptance_dates_no_wait_for_the_judgement(self):
        merged = "2026-10-12T11:00:00+02:00"
        kept = analyses({"flow": row([convoy(merged, accepted="2026-10-12T10:00:00+02:00")])}, [], NOW)
        voided = analyses({"flow": row([convoy(merged, accepted="2026-10-12T10:00:00+02:00", voided=True)])}, [], NOW)
        self.assertEqual([3600, 3600], [p["median"] for p in kept["portions"][1:]])
        self.assertEqual([None, None], [p["median"] for p in voided["portions"][1:]])
        self.assertEqual("3 h 00", voided["indicators"][DELAY]["value"], "the merge is still proven")


if __name__ == "__main__":
    unittest.main()
