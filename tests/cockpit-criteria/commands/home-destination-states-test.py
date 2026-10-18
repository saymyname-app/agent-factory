#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02R, af-vbb4ol, replacing T02 af-0gonc9; Spec af-2zseit, user
stories 111 and 147, Testing Decisions 1 and 5): the ten states home-* of
its reference.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at its address GET / -- the same entry
point as the ordinary data -- as a headless Chromium renders it. It holds
the page to the Validated Prototype (prototype/cockpit-b-zones-20261012 at
632deea, prototypes/c01-complete/frozen-panorama-home): the named parts
of the state, each its element inside the same named part, the navigation
B with this destination open, and what the reference says there.

False if a state is omitted (its parts or its words missing), if the page
is an artificial one distinct from the product (served elsewhere than at
GET /, or not following the data the cockpit serves), or if the
destination cannot be reached from its own navigation.

The result states result-* are the panels of T02S, not of this ticket;
criterion 2 is in home-destination-layout-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402
    CONTENT_PARTS, SHELL_PARTS, LaunchTree, assert_destination, assert_inbox_follows_requests, assert_says,
    measure, measure_until, says,
)


def without(parts: dict, *names: str) -> dict:
    return {name: value for name, value in parts.items() if name not in names}


# home-stale and home-offline: the content, under a notice in the main part.
STALE_PARTS = {**SHELL_PARTS, "notice-1": ("div", "main-1"), **without(CONTENT_PARTS, *SHELL_PARTS)}
# home-empty: the shell, and one section that says nothing is to be shown.
EMPTY_PARTS = {**SHELL_PARTS, "panel-1": ("section", "main-1")}
# home-loading: the same section, with three placeholders.
LOADING_PARTS = {**EMPTY_PARTS, "skeleton-1": ("div", "panel-1"), "skeleton-2": ("div", "panel-1"),
                 "skeleton-3": ("div", "panel-1")}
# home-error: the shell, and the section of the error instead of the content.
ERROR_PARTS = {**SHELL_PARTS, "error-1": ("section", "main-1")}


class HomeDestinationStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def served(self, dataset: str, commit: str | None = None, ready=None, theme: str = "dark",
               width: int = 1440) -> tuple[str, dict]:
        """The address of the cockpit launched on `dataset`, and its page at
        GET /, `width` px wide, in `theme` (the colour scheme the browser
        prefers); with `ready`, once the page shows what it says."""
        address = self.tree.launch(dataset, commit)
        options = {"theme": theme, "widths": (width,)}
        if ready is None:
            return address, measure(address, **options)[0]
        return address, measure_until(address, lambda frames: ready(frames[0]), seconds=15, **options)[0]

    def assert_theme(self, page: dict, theme: str) -> None:
        """The page is drawn in `theme`: a dark background (relative
        luminance at most 0.1) or a light one (at least 0.5), its texts
        readable on it (contrast at least 4.5:1, 3:1 when large)."""
        background = page["background"]
        self.assertTrue(background is not None and (background <= 0.1 if theme == "dark" else background >= 0.5),
                        f"the page is not drawn in the {theme} theme (background luminance {background})")
        self.assertEqual([], page["contrast"], f"texts unreadable in the {theme} theme")

    def assert_content(self, address: str, page: dict) -> None:
        """What the reference says of the destination with its content:
        the four indicators, the runs, the requests and the result open,
        its actions, the projects."""
        assert_says(self, page, "overview-head-1", "Vue d’ensemble")
        assert_says(self, page, "metric-1", "Décisions à prendre", "2")
        assert_says(self, page, "metric-label-2", "Résultats fusionnés")
        assert_says(self, page, "metric-label-3", "Délai de livraison")
        assert_says(self, page, "metric-label-4", "Vérifications CI réussies")
        assert_says(self, page, "bilan-1", "Activité sur 7 jours")
        assert_says(self, page, "panel-1", "Derniers runs", "Tout voir")
        assert_says(self, page, "panel-2", "Ce qui t’attend")
        assert_says(self, page, "request-1", "Le cockpit attend ton avis", "Usine")
        assert_says(self, page, "request-2", "Choisir le format d’export", "Notes")
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Usine · Reprise du cockpit", "Le cockpit attend ton avis",
                    "Les nouveaux parcours du cockpit sont prêts.")
        assert_says(self, page, "resource-list-1", "Ce qui a été livré", "Changements et version à essayer",
                    "Vérifications et preuves", "Parcours, tests et relecture", "Ce qui reste à vérifier",
                    "Version et sources")
        # One Essai and one Avis, side by side in the bar of the result, and
        # nowhere else on the page (user story 110).
        assert_says(self, page, "actions-possibles-1", "Essai", "Avis")
        self.assertEqual(
            (1, 1),
            (sum(c["name"].startswith("Essai") for c in page["controls"]),
             sum(c["name"] == "Avis" for c in page["controls"])),
            "the page has not exactly one Essai and one Avis",
        )
        assert_says(self, page, "panel-4", "Projets")
        assert_says(self, page, "row-1", "Usine", "Reprise du cockpit · À juger")
        assert_says(self, page, "small-stats-1", "6 résultats fusionnés", "12 PR · 7 jours")
        assert_says(self, page, "release-info-1", "Cible révisable · 2 acquis · 2 critères restants · 1 décision ouverte")
        assert_says(self, page, "row-2", "Notes", "Recherche dans les notes · En cours")
        assert_says(self, page, "small-stats-2", "3 résultats fusionnés", "7 PR · 7 jours")
        assert_says(self, page, "row-3", "Portfolio", "Présentation du projet · Fusionné")
        assert_says(self, page, "small-stats-3", "2 résultats fusionnés", "4 PR · 7 jours")

    # Criterion 1 ---------------------------------------------------------

    def test_home_content_is_the_destination_with_indicators_runs_requests_result_and_projects(self):
        # The reference draws home-content in the dark theme, at 1440 px.
        address, page = self.served("home-content")
        assert_destination(self, page, CONTENT_PARTS)
        self.assert_content(address, page)
        self.assert_theme(page, "dark")

    def test_home_content_full_is_the_destination_with_its_whole_content(self):
        # The reference draws home-content-full dark, at 1440 px.
        address, page = self.served("home-content-full")
        assert_destination(self, page, CONTENT_PARTS)
        self.assert_content(address, page)
        self.assert_theme(page, "dark")

    def test_home_narrow_is_the_destination_with_its_content_at_390_px(self):
        # The reference draws home-narrow dark, 390 px wide: the same named
        # parts in the same hierarchy, the same content, within the width
        # of the phone.
        address, page = self.served("home-narrow", width=390)
        self.assertEqual(390, page["width"])
        assert_destination(self, page, CONTENT_PARTS)
        self.assert_content(address, page)
        self.assert_theme(page, "dark")
        self.assertEqual(0, page["overflow"], "the page is wider than the phone")

    def test_home_light_is_the_destination_with_its_content_in_the_light_theme(self):
        # The reference draws home-light in the light theme, at 1440 px:
        # the browser prefers the light colour scheme, and the destination
        # is drawn light, with the same parts and the same content.
        address, page = self.served("home-light", theme="light")
        assert_destination(self, page, CONTENT_PARTS)
        self.assert_content(address, page)
        self.assert_theme(page, "light")

    def test_home_long_is_the_destination_with_its_long_report_in_the_result(self):
        address, page = self.served("home-long")
        assert_destination(self, page, CONTENT_PARTS)
        self.assert_content(address, page)
        assert_says(self, page, "panel-3", "Compte rendu long")
        # Opened, the report is the reference's: its eighteen findings, each
        # with its path too long for a line -- not a text standing in for
        # a content the page did not get.
        opened = measure(address, click="Compte rendu long")[0]["after"]
        self.assertTrue(opened["found"], "no control « Compte rendu long » in the result")
        report = says(opened, "panel-3")
        self.assertEqual(
            [],
            [n for n in range(18)
             if f"Constat {n + 1} — Le résultat doit garder sa version, ses preuves et les mots exacts de "
                f"l’utilisateur. Référence/synthétique/chemin_de_ressource_assez_long_pour_vérifier_le_retour_à_la_"
                f"ligne_{n}." not in report],
            f"findings of the long report not said in the result; it says « {report} »",
        )
        self.assertNotIn("Constat 19", report)
        self.assertNotIn("Contenu non fourni par la source", report)

    def test_home_empty_says_there_is_nothing_to_show(self):
        address, page = self.served("home-empty")
        assert_destination(self, page, EMPTY_PARTS)
        assert_says(self, page, "overview-head-1", "Vue d’ensemble")
        assert_says(self, page, "panel-1", "Rien à afficher ici", "Aucun élément dans cette vue.")

    def test_home_loading_says_the_reading_is_under_way(self):
        # Nothing is read yet: the page says so as soon as it is served.
        address, page = self.served("home-loading")
        assert_destination(self, page, LOADING_PARTS)
        assert_says(self, page, "panel-1", "Lecture en cours…")
        # And it still says so later: a reading under way is not a failed
        # one, the state is not home-error once some seconds have passed.
        later = measure_until(address, lambda frames: "error-1" in frames[0]["texts"], seconds=15)[0]
        assert_destination(self, later, LOADING_PARTS)
        assert_says(self, later, "panel-1", "Lecture en cours…")
        self.assertNotIn("Cette vue est indisponible", later["text"])

    def test_home_error_says_the_view_is_unavailable_and_offers_to_retry(self):
        # The sources never answer: once the cockpit has given up reading
        # them, the page says it does not know, and offers to read again.
        address, page = self.served("home-error", ready=lambda page: "error-1" in page["texts"])
        assert_destination(self, page, ERROR_PARTS)
        assert_says(self, page, "error-1", "Cette vue est indisponible", "L’état réel est inconnu.", "Réessayer")
        self.assertEqual([], [c["name"] for c in page["controls"] if c["name"] in ("Essai", "Avis")],
                         "an action is offered on a state that is not known")

    def test_home_stale_keeps_the_last_values_and_makes_the_actions_unavailable(self):
        # The supervisor is read once, then answers no more: the page keeps
        # what it read, says the reading is stale, and offers no action.
        address, page = self.served("home-stale", ready=lambda page: "notice-1" in page["texts"])
        self.assert_stale(address, page)

    def test_home_offline_keeps_the_last_values_and_makes_the_actions_unavailable(self):
        address, page = self.served("home-offline", ready=lambda page: "notice-1" in page["texts"])
        self.assert_stale(address, page)

    def assert_stale(self, address: str, page: dict) -> None:
        assert_destination(self, page, STALE_PARTS)
        assert_says(self, page, "notice-1", "Lecture périmée · état actuel inconnu.",
                    "Dernières valeurs conservées ; actions indisponibles.")
        assert_says(self, page, "live-1", "État actuel inconnu")
        assert_says(self, page, "request-1", "Le cockpit attend ton avis")
        assert_says(self, page, "panel-3", "Le cockpit attend ton avis")
        actions = [c for c in page["controls"] if c["anchor"] and c["name"].startswith(("Essai", "Avis"))]
        self.assertEqual([], [c["name"] for c in actions if not c["disabled"]],
                         "an action of the result is offered on a stale reading")

    def test_the_destination_is_reached_from_the_other_destinations_and_leads_to_them(self):
        # From the other destinations the cockpit serves, the entry
        # « Vue d’ensemble » of their navigation opens this destination, at
        # GET /, with its content: the page they start from is not this one.
        address = self.tree.launch("home-content")
        for start in ("/journal", "/projet/notes"):
            frame = measure(address, start, click="Vue d’ensemble")[0]
            self.assertEqual(start, frame["path"], f"{start} is not served at its own address")
            after = frame["after"]
            self.assertTrue(after["found"], f"no entry « Vue d’ensemble » in the navigation of {start}")
            assert_destination(self, after, CONTENT_PARTS)
            assert_says(self, after, "panel-2", "Ce qui t’attend")

        # From this destination, each other entry of the navigation B opens
        # the address of its destination.
        reached = {}
        for entry in ("Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses"):
            after = measure(address, click=entry)[0]["after"]
            path = after["path"] if after["found"] else None
            # The projects open under /projet: their list or the page of one.
            reached[entry] = "/projet…" if entry == "Projets" and str(path).startswith("/projet") else path
        self.assertEqual(
            {"Projets": "/projet…", "Runs": "/runs", "Journal": "/journal", "Usine": "/usine",
             "Rituels": "/rituels", "Analyses": "/analyses"},
            reached,
        )

    def test_the_destination_follows_the_data_the_cockpit_serves_not_a_page_of_its_own(self):
        # The same dataset, at another commit, where one request has
        # another title: the page says the new title, at the line of that
        # request -- a page drawn for the state would not change.
        reworded = self.tree.reword("home-content", {"Choisir le format d’export": "Choisir la langue des notes"})
        address, page = self.served("home-content", commit=reworded)
        assert_destination(self, page, CONTENT_PARTS)
        assert_inbox_follows_requests(self, address, page)
        self.assertIn("Choisir la langue des notes", says(page, "request-2"))
        self.assertNotIn("Choisir le format d’export", page["text"])


if __name__ == "__main__":
    unittest.main()
