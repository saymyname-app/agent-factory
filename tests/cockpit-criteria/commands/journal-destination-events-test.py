#!/usr/bin/env python3
"""Criterion test 1 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user stories 76 and 157, Testing Decisions 1,
5 and 8): the useful events of the journal, on journal-content,
journal-long, journal-empty and journal-error.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at its address GET /journal as a headless
Chromium renders it -- measured (home_destination.measure), or after the
steps a person takes there (journal_destination.journey). It holds the
page to the Validated Prototype (prototype/cockpit-b-zones-20261012 at
632deea, prototypes/c01-complete/frozen-panorama-journal): the useful
events first, day by day, each with its time, its source and its
category, its title, its consequence, its link, and its detail and source
folded; the categories that filter them; the empty and the unavailable
journal. Where the links lead and what each category keeps is in
journal-destination-filters-test.py.

An event of a nature the cockpit has no label for keeps its place in the
journal, under the fallback « Signal non reconnu venant de … » (user story
76), with what its producer said, unchanged, in its details: shown on a
dataset at another commit where one event of journal-content is of such a
nature.

False if an event is missing, uncategorised or without its consequence,
source or link, if an unknown event disappears, is replaced
or is given a meaning (a known category, a label of its own), or if the
page is not the journal served at its own address.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    CATEGORIES, DAYS, EVENTS, SYNTHETIC_SOURCE, TABS, TITLES, LaunchTree, anchor_says, assert_found, assert_journal,
    assert_open, click, journey, measure, measure_until, says, shown,
)


class JournalDestinationEvents(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_events(self, address: str) -> None:
        """What the reference says of the journal with its content: the
        tabs, « Événements utiles » open; the categories, « Tout » chosen;
        the six events, four of the day of the dataset then two of the day
        before, each its line of time, source and category, its title, its
        consequence and its link, and, folded, its detail and its source."""
        frame = measure(address, "/journal")[0]
        assert_journal(self, frame)
        page = journey(address)
        assert_open(self, page, TABS, "Événements utiles")
        assert_open(self, page, CATEGORIES, "Tout")
        anchor_says(self, page, "page-lead-1", "Les changements qui comptent, leurs conséquences et la suite.")
        self.assertIn((page["anchors"].get("timeline-date-1", {}).get("text"),
                       page["anchors"].get("timeline-date-2", {}).get("text")), DAYS,
                      "the events are not listed under the day of the dataset and the day before")
        self.assertEqual(TITLES, shown(page, TITLES), "the page does not show the six events of the reference")
        for number, (line, title, consequence, link, detail) in enumerate(EVENTS, 1):
            item = f"timeline-item-{number}"
            anchor_says(self, page, item, line, title, consequence, link)
            anchor_says(self, page, item, detail, SYNTHETIC_SOURCE, folded=True)
            self.assertNotIn(detail, page["anchors"][item]["text"], f"the detail of {item} is not folded")
        # The first four events belong to the first day, the last two to
        # the second: each day holds its own.
        anchor_says(self, page, "timeline-1", *TITLES[:4])
        anchor_says(self, page, "timeline-2", *TITLES[4:])

    # Criterion 1 ---------------------------------------------------------

    def test_journal_content_lists_the_useful_events_with_their_consequence_source_and_link(self):
        address = self.tree.launch("journal-content")
        self.assert_events(address)

    def test_journal_long_lists_the_useful_events_with_their_consequence_source_and_link(self):
        # The reference draws journal-long as journal-content.
        address = self.tree.launch("journal-long")
        self.assert_events(address)

    def test_an_event_of_an_unknown_nature_keeps_its_place_with_the_fallback_and_its_original(self):
        # The same dataset, at another commit, where the decision of Notes
        # is of a nature the cockpit has no label for.
        reworded = self.tree.reword("journal-content", {
            "14:20 (Paris) · Notes · Décision": "14:20 (Paris) · Notes · relecture.reprise_partielle"})
        address = self.tree.launch("journal-content", reworded)
        page = journey(address)
        # Still six events, in the same order: the fourth is the unknown
        # one, said by the fallback, from its source.
        anchor_says(self, page, "timeline-item-4", "14:20 (Paris) · Notes", "Signal non reconnu venant de Notes")
        for number in (1, 2, 3, 5, 6):
            anchor_says(self, page, f"timeline-item-{number}", EVENTS[number - 1][1])
        self.assertNotIn("timeline-item-7", page["anchors"], "the unknown event is listed twice")
        # Its producer's words are kept, unchanged, in its details -- its
        # nature as received, its title, what it said --, not given a
        # meaning in the line that shows it.
        anchor_says(self, page, "timeline-item-4", "relecture.reprise_partielle", "Le format CSV a été choisi",
                    "L’usine peut poursuivre la préparation de l’export.", folded=True)
        shown_line = page["anchors"]["timeline-item-4"]["text"]
        self.assertEqual([], [category for category in ("Bug", "Proposition", "Changement", "Décision", "Événement")
                              if f"· {category}" in shown_line],
                         f"the unknown event is given a known category: « {shown_line} »")
        # It is under no known category, and among them all under « Tout ».
        decisions = journey(address, steps=(click("Décisions"),))
        assert_found(self, decisions)
        self.assertEqual([], shown(decisions, ["Signal non reconnu venant de Notes"]))

    def test_journal_empty_says_there_is_nothing_to_show(self):
        address = self.tree.launch("journal-empty")
        frame = measure(address, "/journal")[0]
        assert_journal(self, frame)
        page = journey(address)
        assert_open(self, page, TABS, "Événements utiles")
        anchor_says(self, page, "panel-1", "Rien à afficher ici", "Aucun élément dans cette vue.")
        self.assertEqual([], shown(page, TITLES))

    def test_journal_error_says_the_view_is_unavailable_and_offers_to_retry(self):
        # Nothing answers: once the cockpit has given up reading its
        # sources, the journal says it does not know, and offers to read
        # again -- not an empty journal.
        address = self.tree.launch("journal-error")
        frame = measure_until(address, lambda frames: "error-1" in frames[0]["texts"], path="/journal")[0]
        assert_journal(self, frame)
        self.assertEqual(["Cette vue est indisponible", "L’état réel est inconnu.", "Réessayer"],
                         [phrase for phrase in ("Cette vue est indisponible", "L’état réel est inconnu.", "Réessayer")
                          if phrase in says(frame, "error-1")])
        self.assertNotIn("Rien à afficher ici", frame["text"], "a journal that cannot be read is said empty")


if __name__ == "__main__":
    unittest.main()
