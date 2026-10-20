"""The destination Analyses (cockpit.ui.analyses): numbers of the runs by
day -- merged, lead times, checks, activity -- never example values."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.ui.analyses.page import compute, render_analyses  # noqa: E402

NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc).timestamp()
H = 3600


def run(rid, start, events, human=()):
    return {"id": rid, "ticket": rid.upper(), "title": "t", "href": "/runs/run?id=%s" % rid, "start": start,
            "events": [{"at": at, "lane": "Code", "text": text} for at, text in events],
            "lanes": [{"kind": "human", "jobs": list(human)}]}


RUNS = [run("a", NOW - 5 * H, [(NOW - 5 * H, "Ticket lancé"), (NOW - 4 * H, "Revue de code : 2 bloquant(s) F1, F2"),
                               (NOW - 3 * H, "Évaluation : favorable"), (NOW - H, "Fusionné dans l’intégration")],
            human=[(H, 2 * H)]),
        run("b", NOW - 30 * 86400, [(NOW - 30 * 86400, "Ticket lancé"), (NOW - 29 * 86400, "Fusionné dans l’intégration")]),
        run("c", NOW - 2 * H, [(NOW - 2 * H, "Ticket lancé"), (NOW - H, "Revue de code : aucun bloquant"),
                               (NOW - 0.5 * H, "Arrêt : encore refusé")])]


class AnalysesTest(unittest.TestCase):
    def test_numbers_come_from_the_runs_of_the_period(self):
        data = compute(RUNS, [{"at": NOW - H, "kind": "decisions"}], NOW, 7)
        self.assertEqual(1, len(data["merged"]), "a merge 29 days ago is outside 7 days")
        self.assertEqual(1, sum(data["reviews_blocking"]))
        self.assertEqual(1, sum(data["reviews_clear"]))
        self.assertEqual(1, sum(data["evaluations_ok"]))
        self.assertEqual((2, 1, 1), (sum(data["launched_per_day"]), sum(data["stopped_per_day"]), sum(data["answers_per_day"])))
        self.assertEqual([4 * H], [d for _, d in data["lead"]])
        self.assertEqual([H], [d for _, d in data["waits"]])

    def test_each_view_says_its_numbers_and_their_definition(self):
        self.assertIn("1 résultat fusionné sur 7 jours", render_analyses(RUNS, [], NOW, "resultats", "7"))
        self.assertIn("Délai médian lancement → fusion : 4 h 00 min", render_analyses(RUNS, [], NOW, "delais", "7"))
        self.assertIn("2 résultats fusionnés sur 30 jours", render_analyses(RUNS, [], NOW, "resultats", "30"))
        page = render_analyses([], [], NOW, "inconnue", "x")
        self.assertIn("0 résultat fusionné", page)
        self.assertIn("Définition et sources", page)


if __name__ == "__main__":
    unittest.main()
