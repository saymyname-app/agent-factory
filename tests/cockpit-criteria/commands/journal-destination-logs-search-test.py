#!/usr/bin/env python3
"""Criterion test 2 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user story 158, Testing Decisions 1, 5 and 8):
on journal-logs, which technical logs each filter by source and the search
keep.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on journal-logs, opens GET /journal in a headless
Chromium and takes there the steps a person takes
(journal_destination.journey): the tab « Logs techniques », then a filter,
or words written in the search field. It holds what the page shows to the
Validated Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-journal/states/journal-logs.html).
The logs themselves, their raw events and the coverage of the sources are
in journal-destination-logs-test.py.

False if a filter or the search shows a log it does not name or hides one
it names, or if a filter is not said to be the one chosen.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    LOG_FILTERS, LOG_SEARCH, LOG_TITLES, LOGS_BY_SOURCE, LaunchTree, assert_found, assert_open, click, journey, shown,
    write,
)

LOGS_TAB = click("Logs techniques")


class JournalDestinationLogsSearch(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # Criterion 2 ---------------------------------------------------------

    def test_a_source_filter_shows_the_logs_of_that_source_only(self):
        address = self.tree.launch("journal-logs")
        chosen = {}
        for source in LOG_FILTERS[1:]:
            page = journey(address, steps=(LOGS_TAB, click(source)))
            assert_found(self, page)
            assert_open(self, page, LOG_FILTERS, source)
            chosen[source] = shown(page, LOG_TITLES)
        self.assertEqual({source: [title] for source, title in LOGS_BY_SOURCE.items()}, chosen)

    def test_the_search_keeps_the_logs_that_say_the_words_searched(self):
        address = self.tree.launch("journal-logs")
        found = journey(address, steps=(LOGS_TAB, write(LOG_SEARCH, "superviseur")))
        assert_found(self, found)
        self.assertEqual(["Lecture du superviseur interrompue"], shown(found, LOG_TITLES))
        # Words of a raw event are searched too.
        raw = journey(address, steps=(LOGS_TAB, write(LOG_SEARCH, "clean-worktrees")))
        assert_found(self, raw)
        self.assertEqual(["Nettoyage terminé"], shown(raw, LOG_TITLES))
        # Words no log says: no log is shown, and the page says so.
        nothing = journey(address, steps=(LOGS_TAB, write(LOG_SEARCH, "aucunlogneditcela")))
        assert_found(self, nothing)
        self.assertEqual([], shown(nothing, LOG_TITLES))
        self.assertIn("Aucun élément dans cette vue.", nothing["text"])


if __name__ == "__main__":
    unittest.main()
