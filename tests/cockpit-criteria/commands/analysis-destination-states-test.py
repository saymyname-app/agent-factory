#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Analyses » (T42, af-muqyxm;
Spec af-2zseit, user stories 149 and 150, Testing Decisions 1 and 5): the
four states analysis-* of its reference.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at its address GET /analyses -- the same
entry point as the ordinary data -- as a headless Chromium renders it. It
holds the page to the Validated Prototype (prototype/cockpit-b-zones-20261012
at 632deea, prototypes/c01-complete/frozen-panorama-analysis): the named
parts of the state, each its element inside the same named part, the
navigation B with this destination open, its tabs with the one open, and
what the reference says there. analysis-time is the destination open on
« Délais », as the reference opens it from analysis-content: the tab is
activated on the served page.

False if a state is omitted (its parts or its words missing), if the page
is an artificial one distinct from the product (served elsewhere than at
GET /analyses, or not following the data the cockpit serves), if a
command answers as if it were done, or if the destination cannot be
reached from the navigation of the others or does not lead to them.

Criterion 2 is in analysis-destination-layout-test.py, the anchors and
tokens of each state in analysis-destination-fidelity-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_destination import (  # noqa: E402
    PATH, RESULTS_PARTS, TIME_PARTS, assert_analyses, assert_says,
)
from home_destination import LaunchTree, measure, says, text_of  # noqa: E402


class AnalysisDestinationStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def served(self, dataset: str, commit: str | None = None, theme: str = "dark", width: int = 1440,
               click: str | None = None) -> tuple[str, dict]:
        """The address of the cockpit launched on `dataset`, and its page at
        GET /analyses, `width` px wide, in `theme` (the colour scheme the
        browser prefers); with `click`, the page once the control named so
        was activated on it."""
        address = self.tree.launch(dataset, commit)
        frame = measure(address, PATH, theme=theme, widths=(width,), click=click)[0]
        if click is None:
            return address, frame
        self.assertEqual(PATH, frame["path"], "the destination is not served at its own address")
        self.assertTrue(frame["after"]["found"], f"no control « {click} » on the destination")
        return address, frame["after"]

    def assert_theme(self, page: dict, theme: str) -> None:
        """The page is drawn in `theme`: a dark background (relative
        luminance at most 0.1) or a light one (at least 0.5), its texts
        readable on it (contrast at least 4.5:1, 3:1 when large)."""
        background = page["background"]
        self.assertTrue(background is not None and (background <= 0.1 if theme == "dark" else background >= 0.5),
                        f"the page is not drawn in the {theme} theme (background luminance {background})")
        self.assertEqual([], page["contrast"], f"texts unreadable in the {theme} theme")

    def assert_tab_marked(self, page: dict, tab: str) -> None:
        """The tab open is said to be the one open -- a state a screen
        reader reads, that the other tabs have not --, and is told from
        them by more than its colour."""
        tabs = {c["name"]: c for c in page["controls"] if c["name"] in ("Résultats", "Délais", "Vérifications",
                                                                      "Activité")}
        marked = [name for name, control in tabs.items()
                  if any(value not in (None, "false") for value in control["state"].values())]
        self.assertEqual([tab], marked, "the tab open is not marked as the one open")
        others = [control["shape"] for name, control in tabs.items() if name != tab]
        self.assertNotIn(tabs[tab]["shape"], others, "the tab open is told from the others by its colour alone")

    def assert_results(self, page: dict) -> None:
        """What the reference says of the destination open on « Résultats »:
        its scope, the merged results of seven days, their chart day by
        day, the last of them, and how they are counted."""
        assert_says(self, page, "h1-1", "Analyses")
        assert_says(self, page, "page-lead-1", "Toute l’usine · 7 derniers jours")
        assert_says(self, page, "metric-tabs-1", "Résultats", "Délais", "Vérifications", "Activité")
        self.assert_tab_marked(page, "Résultats")
        assert_says(self, page, "panel-1", "Résultats fusionnés", "6 résultats sur sept jours · fusion prouvée")
        assert_says(self, page, "chart-key-1", "Résultats fusionnés")
        # The chart says each day's count, Monday to Sunday, on a scale
        # from 0 to 9.
        self.assertEqual(
            ["Résultats fusionnés · Lundi : 1", "Résultats fusionnés · Mardi : 1",
             "Résultats fusionnés · Mercredi : 0", "Résultats fusionnés · Jeudi : 1",
             "Résultats fusionnés · Vendredi : 0", "Résultats fusionnés · Samedi : 2",
             "Résultats fusionnés · Dimanche : 1"],
            [says(page, f"title-{n}") for n in range(1, 8)],
            "the chart does not say the merged results of each day",
        )
        self.assertEqual(["0", "3", "6", "9", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
                         [text_of(page, f"text-{n}") for n in range(1, 12)], "the axes of the chart are not said")
        self.assertEqual(
            ["Présentation du projet", "Portfolio · hier", "Import des documents", "Notes · hier",
             "Fiabilisation des reprises", "Usine · avant-hier"],
            text_of(page, "metrics-history-1").split("\n"),
            "the last merged results are not listed",
        )
        assert_says(self, page, "summary-1", "Définition et sources")

    def assert_time(self, page: dict) -> None:
        """What the reference says of the destination open on « Délais »:
        the median lead time, its parts -- work and waits told apart --,
        the wait to look at, and how it is computed."""
        assert_says(self, page, "h1-1", "Analyses")
        assert_says(self, page, "page-lead-1", "Toute l’usine · 7 derniers jours")
        self.assert_tab_marked(page, "Délais")
        assert_says(self, page, "panel-1", "Où passe le temps ?", "Délai médian : 2 h 40 · 6 résultats fusionnés")
        assert_says(self, page, "chart-key-1", "Travail et vérifications", "Attentes")
        self.assertEqual(
            ["Préparation 18 min", "Attente de départ 12 min", "Réalisation 45 min", "Relectures 20 min",
             "Évaluation 15 min", "Attente de jugement 40 min", "Fusion 10 min"],
            [says(page, f"duration-row-{n}") for n in range(1, 8)],
            "the parts of the lead time are not said, in their order",
        )
        assert_says(self, page, "notice-1", "À examiner : attente de jugement de 3 h 10 sur un résultat.",
                    "Référence habituelle non collectée : aucune anomalie automatique affirmée.")
        assert_says(self, page, "summary-1", "Méthode et couverture")

    # Criterion 1 ---------------------------------------------------------

    def test_analysis_content_is_the_destination_open_on_the_merged_results(self):
        # The reference draws analysis-content dark, at 1440 px.
        address, page = self.served("analysis-content")
        assert_analyses(self, page, RESULTS_PARTS, "Résultats")
        self.assert_results(page)
        self.assert_theme(page, "dark")
        # Opened, « Définition et sources » says how a result is counted.
        opened = measure(address, PATH, click="Définition et sources")[0]["after"]
        self.assertTrue(opened["found"], "no control « Définition et sources »")
        assert_says(self, opened, "details-1", "Un résultat est compté sur sa preuve de fusion.",
                    "Les PR et les tickets ne sont pas des résultats distincts par défaut.")

    def test_analysis_narrow_is_the_destination_open_on_the_merged_results_at_390_px(self):
        # The reference draws analysis-narrow dark, 390 px wide: the same
        # named parts in the same hierarchy, the same content, within the
        # width of the phone.
        address, page = self.served("analysis-narrow", width=390)
        self.assertEqual(390, page["width"])
        assert_analyses(self, page, RESULTS_PARTS, "Résultats")
        self.assert_results(page)
        self.assert_theme(page, "dark")
        self.assertEqual(0, page["overflow"], "the page is wider than the phone")

    def test_analysis_light_is_the_destination_open_on_the_merged_results_in_the_light_theme(self):
        # The reference draws analysis-light in the light theme, at 1440 px:
        # the browser prefers the light colour scheme, and the destination
        # is drawn light, with the same parts and the same content.
        address, page = self.served("analysis-light", theme="light")
        assert_analyses(self, page, RESULTS_PARTS, "Résultats")
        self.assert_results(page)
        self.assert_theme(page, "light")

    def test_analysis_time_is_the_destination_open_on_the_lead_times(self):
        # The reference opens analysis-time from the destination, on the
        # tab « Délais »: the tab, activated on the page served, opens it
        # at the same address.
        address, page = self.served("analysis-time", click="Délais")
        assert_analyses(self, page, TIME_PARTS, "Délais")
        self.assert_time(page)
        self.assert_theme(page, "dark")
        # « Méthode et couverture » opens what the lead time covers.
        details = [c for c in page["controls"] if c["name"] == "Méthode et couverture"]
        self.assertEqual(1, len(details), "no control « Méthode et couverture » once « Délais » is open")
        self.assertEqual("summary", details[0]["tag"])

    def test_the_tabs_lead_from_one_view_to_the_other_and_back(self):
        # On the same data, « Délais » then « Résultats »: each tab opens
        # its own view, with its own parts, and nothing of the other.
        address = self.tree.launch("analysis-time")
        time_view = measure(address, PATH, click="Délais")[0]["after"]
        self.assertTrue(time_view["found"], "no tab « Délais » on the destination")
        assert_analyses(self, time_view, TIME_PARTS, "Délais")
        self.assertNotIn("Présentation du projet", time_view["text"])
        results = measure(address, PATH, click="Résultats")[0]["after"]
        self.assertTrue(results["found"], "no tab « Résultats » on the destination")
        assert_analyses(self, results, RESULTS_PARTS, "Résultats")
        self.assertNotIn("Où passe le temps ?", results["text"])

    def test_the_destination_is_reached_from_the_other_destinations_and_leads_to_them(self):
        # From the other destinations the cockpit serves, the entry
        # « Analyses » of their navigation opens this destination, at
        # GET /analyses, with its content.
        address = self.tree.launch("analysis-content")
        for start in ("/", "/journal"):
            frame = measure(address, start, click="Analyses")[0]
            self.assertEqual(start, frame["path"], f"{start} is not served at its own address")
            after = frame["after"]
            self.assertTrue(after["found"], f"no entry « Analyses » in the navigation of {start}")
            assert_analyses(self, after, RESULTS_PARTS, "Résultats")
            assert_says(self, after, "panel-1", "6 résultats sur sept jours · fusion prouvée")

        # From this destination, each other entry of the navigation B opens
        # the address of its destination.
        reached = {}
        for entry in ("Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Rituels"):
            after = measure(address, PATH, click=entry)[0]["after"]
            reached[entry] = after["path"] if after["found"] else None
        self.assertEqual(
            {"Vue d’ensemble": "/", "Projets": "/projets", "Runs": "/runs", "Journal": "/journal",
             "Usine": "/usine", "Rituels": "/rituels"},
            reached,
        )

    def test_the_destination_follows_the_data_the_cockpit_serves_not_a_page_of_its_own(self):
        # The same dataset, at another commit, where a merged result has
        # another title: the page says the new title, where the reference
        # says the first one -- a page drawn for the state would not change.
        reworded = self.tree.reword("analysis-content", {"Import des documents": "Import des archives"})
        address, page = self.served("analysis-content", commit=reworded)
        assert_analyses(self, page, RESULTS_PARTS, "Résultats")
        self.assertIn("Import des archives", says(page, "metrics-history-1"))
        self.assertNotIn("Import des documents", page["text"])


if __name__ == "__main__":
    unittest.main()
