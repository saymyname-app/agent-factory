#!/usr/bin/env python3
"""Criterion test 2 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user stories 76 and 158, Testing Decisions 1,
5 and 8): the technical logs of the journal, on journal-logs.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on journal-logs (journal-error for the case where no
source answers), opens GET /journal in a headless Chromium and takes there
the steps a person takes (journal_destination.journey): the tab
« Logs techniques », a raw event unfolded, the tab « Sources
disponibles ». It holds what the page shows to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-journal/states/journal-logs.html):
each log with its time, its title, what it means and its raw event,
folded, as received; its filters by source and its search field; the
labels fixed by type, without any model. What the filters and the search
keep is in journal-destination-logs-search-test.py.

The coverage of the sources (« Sources disponibles ») is not drawn by the
reference: what it says is held to what the cockpit reads (agent
interpretation of « couverture des sources raccordées et absentes
visible »): each source of the logs is said « raccordée » or « absente »
(« inconnue » when it does not answer); a source whose logs are listed is
« raccordée »; when no source answers (journal-error), none is said
« raccordée ».

A secret written in a raw event is never served: shown on a dataset at
another commit where a raw event of journal-logs carries two.

False if a log, its meaning or its raw event is missing, if a secret is
served, if a source is not said connected or absent, or if a source that
does not answer is said connected.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    FIXED_LABELS, LOG_FILTERS, LOG_SEARCH, LOG_TITLES, LOGS, SOURCES, TABS, LaunchTree, anchor_says, assert_found,
    assert_open, click, fetch, journey, shown, state_of,
)

LOGS_TAB = click("Logs techniques")
# Two secrets of the shapes the Factory holds (a GitHub token, a key of the
# model provider), written into the raw event of the first log.
SECRETS = ("ghp_q7Lz2Xv9KfR4mT8wYc1NbH6sJd3PaE0uGi5o", "sk-ant-api03-Vb7Qm2Lx9Kp4Rt8Wz1Nc6Hs3Jd0Fa5Ge")


class JournalDestinationLogs(unittest.TestCase):
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

    def test_the_technical_logs_are_a_tab_of_the_journal_with_each_log_and_its_raw_event(self):
        address = self.tree.launch("journal-logs")
        page = journey(address, steps=(LOGS_TAB,))
        assert_found(self, page)
        self.assertTrue(page["path"].startswith("/journal"), f"the logs are not a tab of the journal: {page['path']}")
        assert_open(self, page, TABS, "Logs techniques")
        assert_open(self, page, LOG_FILTERS, "Tous")
        self.assertEqual(1, sum(c["name"] == LOG_SEARCH for c in page["controls"]), "no search field in the logs")
        # Each log of the reference, in its order: its time, its title, what
        # it means; its raw event folded, as received -- the unrecognised
        # one too, with its fallback and what it carried.
        self.assertEqual(LOG_TITLES, shown(page, LOG_TITLES))
        for number, (time, title, meaning, raw) in enumerate(LOGS, 1):
            anchor_says(self, page, f"panel-{number}", time, title, meaning, "Événement brut")
            anchor_says(self, page, f"raw-event-{number}", raw, folded=True)
            self.assertNotIn(raw, page["anchors"][f"panel-{number}"]["text"], f"the raw event {number} is not folded")
        anchor_says(self, page, "readonly-note-1", FIXED_LABELS)
        # The useful events are not mixed with the logs.
        self.assertNotIn("Bugs", [c["name"] for c in page["controls"]])
        # Unfolded, a raw event is shown as received.
        opened = journey(address, steps=(LOGS_TAB, click("Événement brut")))
        assert_found(self, opened)
        anchor_says(self, opened, "raw-event-1", LOGS[0][3])

    def test_a_secret_in_a_raw_event_is_never_served(self):
        # The same dataset, at another commit, where the raw event of the
        # first log carries a token and a key after what it said.
        raw = LOGS[0][3]
        reworded = self.tree.reword("journal-logs", {raw: f"{raw} token={SECRETS[0]} api_key={SECRETS[1]}"})
        address = self.tree.launch("journal-logs", reworded)
        opened = journey(address, steps=(LOGS_TAB, click("Événement brut")))
        assert_found(self, opened)
        # What the raw event said otherwise is still shown, as received.
        anchor_says(self, opened, "raw-event-1", raw)
        served = {"the logs tab": opened["html"], "GET /journal": fetch(address + "/journal")[2],
                  "GET /api/journal": fetch(address + "/api/journal")[2],
                  f"GET {opened['path']}": fetch(address + opened["path"])[2]}
        self.assertEqual([], [(where, secret[:8]) for where, body in served.items() for secret in SECRETS
                              if secret in body or secret[8:] in body],
                         "a secret of a raw event is served")

    def test_the_coverage_says_each_source_of_the_logs_connected_when_its_logs_are_read(self):
        address = self.tree.launch("journal-logs")
        page = journey(address, steps=(click("Sources disponibles"),))
        assert_found(self, page)
        assert_open(self, page, TABS, "Sources disponibles")
        # Every source of the logs is named with what the cockpit knows of
        # it; those whose logs the tab lists -- all six here -- are read.
        self.assertEqual({source: "raccordée" for source in SOURCES},
                         {source: state_of(page, source) for source in SOURCES})

    def test_the_coverage_says_no_source_connected_when_none_answers(self):
        # Nothing answers: each source is said absent or unknown, none
        # connected -- an absence is never drawn as a source in service.
        address = self.tree.launch("journal-error")
        page = journey(address, steps=(click("Sources disponibles"),))
        assert_found(self, page)
        states = {source: state_of(page, source) for source in SOURCES}
        self.assertEqual({source: True for source in SOURCES},
                         {source: state in ("absente", "inconnue") for source, state in states.items()},
                         f"a source that does not answer is not said absent or unknown: {states}")


if __name__ == "__main__":
    unittest.main()
