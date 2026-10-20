#!/usr/bin/env python3
"""Criterion tests 1 and 2 of the Prototype Fold « Analyses » (D,
af-ten1sp; Spec af-fgcw0d, user stories 148, 149 and 150, Testing Decisions
1 and 8): the four indicators computed from real sources, their method, the
daily volumes, and a CI that cannot be read.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset -- one of the profile (analysis-content,
analysis-time) or one this file declares in a commit of its own tree
(analyses_destination.SOURCES: the records of the flow and what GitHub
answers) -- and reads the page « Analyses » the cockpit serves at GET
/analyses, following its tabs.

Criterion 1 is false if an indicator is a value of example (the page does
not follow the records of the dataset), if a count becomes a percentage,
or if two units are mixed on one chart. Criterion 2 is false if the
indicator of the CI shows zero or a value it did not read when GitHub
answers nothing, or if the other indicators stop being computed.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyses_destination import (  # noqa: E402
    DAYS, METHOD, SOURCES, VIEWS, WITHOUT_CI, LaunchTree, declare, served,
)


class AnalysesDestinationIndicators(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()
        cls.declared = declare(cls.tree, {"analysis-sources": SOURCES, "analysis-sources-without-ci": WITHOUT_CI})

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def launch(self, dataset: str) -> str:
        """The address of the cockpit launched on `dataset`: one of the
        profile, or one declared by this file."""
        commit = self.declared if dataset.startswith("analysis-sources") else None
        return self.tree.launch(dataset, commit)

    # --- criterion 1 -------------------------------------------------------------

    def test_analysis_content_shows_the_merged_results_its_sources_prove(self):
        """The state analysis-content of the reference: six results merged
        over the seven days, one a day but none on the third and fifth and
        two on the sixth, the last ones first. The reference says when each
        was merged in words its chart contradicts (« avant-hier », a day its
        chart counts none): a defect of the prototype, not copied -- the
        results are held to their order, by title and project."""
        page = served(self.launch("analysis-content"), "Résultats")
        self.assertEqual("Résultats fusionnés", page.says("h2-1"))
        self.assertEqual("6 résultats sur sept jours · fusion prouvée", page.says("p-1"))
        self.assertEqual([1, 1, 0, 1, 0, 2, 1], [value for _, value in page.series().get("Résultats fusionnés", [])],
                         "the merged results a day are not those of the reference")
        history = page.says("metrics-history-1")
        found = [history.find(item) for item in ("Présentation du projet Portfolio",
                                                  "Import des documents Notes",
                                                  "Fiabilisation des reprises Usine")]
        self.assertTrue(-1 not in found and found == sorted(found),
                        f"the last merged results are not listed, the last first: « {history} »")

    def test_analysis_time_shows_the_median_delivery_delay_its_sources_give(self):
        """The state analysis-time of the reference: the median delay of
        the six merged results."""
        page = served(self.launch("analysis-time"), "Délais")
        self.assertEqual("Où passe le temps ?", page.says("h2-1"))
        self.assertEqual("Délai médian : 2 h 40 · 6 résultats fusionnés", page.says("p-1"))

    def test_each_indicator_is_computed_from_the_records_of_the_flow_and_of_github(self):
        """Four results merged; from publication to proven merge, the median
        of 80, 130, 240 and 260 minutes, and per portion the medians of 60,
        90, 100, 180 (work and checks), 15, 30, 60, 120 (wait for the
        judgement) and 5, 10, 20, 20 (merge); 9 CI runs succeeded of the 13
        completed; three decisions open. None of these values is written in
        the dataset."""
        address = self.launch("analysis-sources")
        results = served(address, "Résultats")
        self.assertEqual("4 résultats sur sept jours · fusion prouvée", results.says("p-1"))
        history = results.says("metrics-history-1")
        found = [history.find(title) for title in ("Page Portfolio", "Reprise des sessions", "Recherche plein texte",
                                                   "Export des notes")]
        self.assertTrue(-1 not in found and found == sorted(found),
                        f"the merged results are not listed, the last first: « {history} »")
        self.assertNotIn("Ancienne livraison", history, "a result merged before the period is counted")
        self.assertNotIn("Résultat à juger", history, "a result not merged is counted as merged")

        delays = served(address, "Délais")
        self.assertEqual("Délai médian : 3 h 05 · 4 résultats fusionnés", delays.says("p-1"))
        rows = sorted((name for name in delays.anchors() if re.fullmatch(r"duration-row-\d+", name)),
                      key=lambda name: int(name.rsplit("-", 1)[1]))
        self.assertEqual(["Réalisation et vérifications 1 h 35", "Attente de jugement 45 min", "Fusion 15 min"],
                         [delays.says(row) for row in rows], "the portions of the delay are not those the records give")

        checks = served(address, "Vérifications")
        self.assertEqual("Vérifications CI réussies", checks.says("h2-1"))
        self.assertIn("69 %", checks.says("p-1"), "the rate of the CI runs that succeeded is not 9 of 13")
        self.assertRegex(checks.method().get("Calcul", ""), r"\b9\b.*\b13\b",
                         "the calculation does not say the 9 runs that succeeded of the 13 completed")

        activity = served(address, "Activité")
        self.assertEqual("Décisions ouvertes", activity.says("h2-1"))
        self.assertIn("3 décisions ouvertes", activity.says("p-1"))

    def test_each_indicator_states_its_population_period_sources_timestamp_and_calculation(self):
        """Each of the four views states, in the details of its method, its
        population, its period (the 06/10 to the 12/10), its sources -- the
        proof of merge of the flow, the CI GitHub of the declared repository
        --, when they were read (Paris) and its calculation."""
        address = self.launch("analysis-sources")
        # No subTest: the harness of the profile records none of them.
        for view in VIEWS:
            method = served(address, view).method()
            self.assertEqual([], [label for label in METHOD if not method.get(label)],
                             f"« {view} » does not state all of its method: {method}")
            self.assertIn("du 06/10 au 12/10", method["Période"], f"the period of « {view} »")
            self.assertRegex(method["Horodatage"], r"12/10.*\d\d:\d\d \(Paris\)", f"the timestamp of « {view} »")
        self.assertIn("preuve de fusion", served(address, "Résultats").method()["Sources"])
        self.assertIn("preuve de fusion", served(address, "Délais").method()["Sources"])
        self.assertIn("médiane", served(address, "Délais").method()["Calcul"])
        ci = served(address, "Vérifications").method()["Sources"]
        self.assertIn("CI GitHub", ci)
        self.assertIn("saymyname-app/agent-factory", ci)

    def test_the_daily_volumes_are_drawn_over_the_same_seven_days_in_one_unit_and_the_rate_apart(self):
        """One chart of volumes a day, every series over the same seven days
        06/10 -> 12/10, counted per day; the rate of the CI is not on it,
        and no count of the other views is a percentage."""
        address = self.launch("analysis-sources")
        page = served(address, "Résultats")
        series = page.series()
        self.assertEqual({
            "Résultats fusionnés": [1, 0, 1, 0, 0, 1, 1],
            "PR fusionnées": [1, 0, 2, 0, 0, 1, 1],
            "Tickets livrés": [2, 1, 3, 0, 0, 1, 2],
            "Exécutions CI réussies": [2, 1, 3, 0, 0, 2, 1],
        }, {name: [value for _, value in points] for name, points in series.items()},
            "the daily volumes are not those of the records")
        self.assertEqual({name: DAYS for name in series}, {name: [day for day, _ in points] for name, points in
                                                           series.items()}, "the series are not over the same days")
        chart = page.chart_text()
        self.assertIn("par jour", chart, "the unit of the chart is not said")
        self.assertNotIn("%", chart, "a rate is drawn among the volumes")
        for view in ("Résultats", "Délais", "Activité"):
            self.assertNotIn("%", served(address, view).text, f"a count is shown as a percentage in « {view} »")
        self.assertNotIn("exemple", page.text.lower(), "the page says its values are of example")

    def test_each_indicator_opens_its_view(self):
        """The four tabs of the Analyses each open the view of one
        indicator, under its heading."""
        address = self.launch("analysis-sources")
        self.assertEqual(list(VIEWS), list(served(address).links("metric-tabs-1")),
                         "the tabs are not the four views of the indicators")
        for view, heading in VIEWS.items():
            self.assertEqual(heading, served(address, view).says("h2-1"), f"the tab « {view} » opens another view")

    # --- criterion 2 -------------------------------------------------------------

    def test_without_a_readable_ci_the_ci_indicator_is_unavailable_with_its_reason(self):
        """GitHub answers nothing: the indicator of the CI says it is
        unavailable and why, and shows no figure."""
        page = served(self.launch("analysis-sources-without-ci"), "Vérifications")
        head = page.says("p-1")
        self.assertIn("indisponible", head.lower(), f"the indicator of the CI is not unavailable: « {head} »")
        self.assertNotRegex(head, r"\d", f"the unavailable indicator of the CI shows a figure: « {head} »")
        self.assertTrue(page.method().get("Raison"), f"the reason of the unavailability is not said: « {page.text} »")

    def test_without_a_readable_ci_the_other_indicators_are_still_computed(self):
        """GitHub answers nothing: the results, the delay and the decisions
        are computed from the flow as before, the tickets delivered a day
        too; the CI runs and the pull requests are drawn nowhere as zeros,
        and said unavailable."""
        address = self.launch("analysis-sources-without-ci")
        results = served(address, "Résultats")
        self.assertEqual("4 résultats sur sept jours · fusion prouvée", results.says("p-1"))
        series = {name: [value for _, value in points] for name, points in results.series().items()}
        self.assertEqual([2, 1, 3, 0, 0, 1, 2], series.get("Tickets livrés"))
        self.assertEqual([1, 0, 1, 0, 0, 1, 1], series.get("Résultats fusionnés"))
        self.assertNotIn("Exécutions CI réussies", series, "CI runs that were not read are drawn")
        self.assertNotIn("PR fusionnées", series, "pull requests that were not read are drawn")
        key = results.says("chart-key-1")
        self.assertRegex(key, r"Exécutions CI réussies\s*:?\s*indisponible", f"the key does not say it: « {key} »")
        self.assertRegex(key, r"PR fusionnées\s*:?\s*indisponible", f"the key does not say it: « {key} »")
        self.assertEqual("Délai médian : 3 h 05 · 4 résultats fusionnés", served(address, "Délais").says("p-1"))
        self.assertIn("3 décisions ouvertes", served(address, "Activité").says("p-1"))


if __name__ == "__main__":
    unittest.main()
