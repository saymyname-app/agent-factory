#!/usr/bin/env python3
"""Criterion test 3 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user stories 124, 157 and 175, Testing
Decisions 1, 5 and 8): the journal on journal-stale, journal-offline,
journal-loading, journal-narrow and journal-light -- what it says of the
freshness of what it shows, at 390 px and in the light theme.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads GET /journal as a headless Chromium renders it. It holds the page to
the Validated Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-journal): a reading that is no
longer current keeps the last events under a notice that says the state
is unknown and the actions unavailable, and the cockpit no longer says it
runs; a reading under way says so, and still says so later; on a phone
and in the light theme, the same journal.

The fidelity of these states is in journal-destination-states-fidelity-
test.py, their readability at both widths, in both themes and with the
keyboard in journal-destination-states-layout-test.py.

False if a journal no longer current is presented as current (no notice,
the cockpit said running), if its last events are dropped, if a reading
under way turns into another state, or if the journal is not the same at
390 px or in the light theme.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    EVENTS, TABS, TITLES, LaunchTree, anchor_says, assert_journal, assert_open, journey, measure, measure_until,
    says, shown,
)


class JournalDestinationFreshness(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_theme(self, frame: dict, theme: str) -> None:
        background = frame["background"]
        self.assertTrue(background is not None and (background <= 0.1 if theme == "dark" else background >= 0.5),
                        f"the journal is not drawn in the {theme} theme (background luminance {background})")
        self.assertEqual([], frame["contrast"], f"texts unreadable in the {theme} theme")

    def assert_same_journal(self, address: str, theme: str, width: int) -> None:
        """The journal of the reference, `width` px wide in `theme`: the
        destination, its tabs, its six events with their consequences."""
        frame = measure(address, "/journal", theme=theme, widths=(width,))[0]
        self.assertEqual(width, frame["width"])
        assert_journal(self, frame)
        self.assert_theme(frame, theme)
        self.assertEqual(0, frame["overflow"], f"the journal is wider than {width} px")
        page = journey(address, theme=theme, width=width)
        assert_open(self, page, TABS, "Événements utiles")
        self.assertEqual(TITLES, shown(page, TITLES))
        for number, (line, title, consequence, link, _) in enumerate(EVENTS, 1):
            anchor_says(self, page, f"timeline-item-{number}", line, title, consequence, link)

    def assert_stale(self, dataset: str) -> None:
        # The supervisor is read once, then answers no more: the journal
        # keeps what it read and says that the current state is unknown.
        address = self.tree.launch(dataset)
        frame = measure_until(address, lambda frames: "notice-1" in frames[0]["texts"], path="/journal")[0]
        assert_journal(self, frame)
        notice = says(frame, "notice-1").lower()
        self.assertEqual([], [words for words in ("état actuel inconnu", "conservées", "actions indisponibles")
                              if words not in notice], f"the notice does not say it; it says « {notice} »")
        self.assertIn("État actuel inconnu", says(frame, "live-1"))
        self.assertNotIn("En marche", says(frame, "live-1"), "the cockpit is said running on a stale reading")
        page = journey(address)
        self.assertEqual(TITLES, shown(page, TITLES), "the last events read are not kept")

    # Criterion 3 ---------------------------------------------------------

    def test_journal_stale_keeps_the_last_events_and_says_the_state_is_unknown(self):
        self.assert_stale("journal-stale")

    def test_journal_offline_keeps_the_last_events_and_says_the_state_is_unknown(self):
        self.assert_stale("journal-offline")

    def test_journal_loading_says_the_reading_is_under_way_and_still_says_so_later(self):
        address = self.tree.launch("journal-loading")
        frame = measure(address, "/journal")[0]
        assert_journal(self, frame)
        self.assertIn("Lecture en cours…", says(frame, "panel-1"))
        self.assertEqual(["skeleton-1", "skeleton-2", "skeleton-3"],
                         [name for name in ("skeleton-1", "skeleton-2", "skeleton-3") if name in frame["texts"]])
        later = measure_until(address, lambda frames: "error-1" in frames[0]["texts"], seconds=15, path="/journal")[0]
        self.assertIn("Lecture en cours…", says(later, "panel-1"))
        self.assertNotIn("Cette vue est indisponible", later["text"], "a reading under way is said failed")
        self.assertNotIn("Rien à afficher ici", later["text"], "a reading under way is said empty")

    def test_journal_narrow_is_the_journal_at_390_px(self):
        self.assert_same_journal(self.tree.launch("journal-narrow"), "dark", 390)

    def test_journal_light_is_the_journal_in_the_light_theme(self):
        self.assert_same_journal(self.tree.launch("journal-light"), "light", 1440)


if __name__ == "__main__":
    unittest.main()
