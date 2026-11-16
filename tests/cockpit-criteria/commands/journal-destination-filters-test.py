#!/usr/bin/env python3
"""Criterion test 1 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user story 157, Testing Decisions 1, 5 and 8):
on journal-content, where the link of each useful event leads, and which
events each category of the journal keeps.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on journal-content, and takes on GET /journal, in a
headless Chromium, the steps a person takes there: a link of an event
activated (home_destination.measure), a category chosen
(journal_destination.journey). It holds what follows to the Validated
Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-journal/states/journal-content.html).
The events themselves are in journal-destination-events-test.py.

False if a link leads elsewhere than it says, or if a category shows
another one's events or is not said to be the one chosen.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    CATEGORIES, TITLES, LaunchTree, assert_found, assert_open, click, journey, measure, shown,
)


class JournalDestinationFilters(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # Criterion 1 ---------------------------------------------------------

    def test_each_link_of_an_event_leads_where_it_says(self):
        # « Voir les propositions » and « Voir le résultat » lead to the
        # overview, where the propositions and the result to judge are;
        # « Voir le projet » to the page of the project of the event (the
        # first is of Notes); « Voir les connexions » to the factory, where
        # its connections are.
        address = self.tree.launch("journal-content")
        reached = {}
        for link in ("Voir les propositions", "Voir le résultat", "Voir le projet", "Voir les connexions"):
            after = measure(address, "/journal", click=link)[0]["after"]
            reached[link] = after["path"] if after["found"] else None
        self.assertEqual({"Voir les propositions": "/", "Voir le résultat": "/", "Voir le projet": "/projet/notes",
                          "Voir les connexions": "/usine"}, reached)

    def test_a_category_shows_its_own_events_only(self):
        # Each category is chosen by its own name: « Événements » is the
        # category of that name, not the tab « Événements utiles » before it
        # whose name it starts (journal_journey.js takes the control of the
        # exact name first).
        address = self.tree.launch("journal-content")
        chosen = {}
        for category in CATEGORIES[1:]:
            page = journey(address, steps=(click(category),))
            assert_found(self, page)
            assert_open(self, page, CATEGORIES, category)
            chosen[category] = shown(page, TITLES)
        self.assertEqual({
            "Bugs": ["Une recherche sur des notes longues échoue"],
            "Propositions": ["Deux améliorations proposées après une revue"],
            "Changements": ["Le cockpit est prêt à essayer", "La présentation a été fusionnée"],
            "Décisions": ["Le format CSV a été choisi"],
            "Événements": ["La connexion au superviseur a été rétablie"],
        }, chosen)
        # « Tout », chosen again, shows them all.
        page = journey(address, steps=(click("Bugs"), click("Tout")))
        assert_found(self, page)
        self.assertEqual(TITLES, shown(page, TITLES))


if __name__ == "__main__":
    unittest.main()
