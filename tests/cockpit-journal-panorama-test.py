"""The destination Journal of Panorama (cockpit.ui.journal.panorama): the
answered requests and the deliveries of the runs, day by day, by filter."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.ui.journal.entries import JournalEntry  # noqa: E402
from cockpit.ui.journal.panorama import journal_items, render_journal_panorama  # noqa: E402

NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc).timestamp()
ENTRIES = [
    JournalEntry(bead_id="af-t1", quoi="répondu b — attendre", quand="2026-10-19T13:50:00Z", par="benjamin",
                 voie="escalation-door", demande="Ticket af-t1 arrêté"),
    JournalEntry(bead_id="af-c1", quoi="Effacée sans réponse enregistrée", quand="2026-10-18T10:00:00Z", par="",
                 voie="clear", demande="Incident d'usine"),
    JournalEntry(bead_id="af-u1", quoi="sans date", quand="", par="", voie="proposal-door", demande="Une proposition"),
]
RUNS = [{"id": "af-t1", "ticket": "T1", "title": "Une page", "href": "/runs/run?id=af-t1", "branch": "ticket/af-t1",
         "events": [{"at": NOW - 600, "lane": "Code", "text": "Fusionné dans l’intégration"},
                    {"at": NOW - 900, "lane": "Code", "text": "Tests verts"}]}]


class JournalPanoramaTest(unittest.TestCase):
    def test_requests_and_merges_are_one_timeline_newest_first(self):
        items = journal_items(ENTRIES, RUNS)
        self.assertEqual(["livraisons", "decisions", "effacees", "propositions"], [i["kind"] for i in items])
        self.assertEqual("/runs/run?id=af-t1", items[1]["href"], "an answered ticket links its run")

    def test_useful_hides_cleared_requests_and_days_are_named(self):
        page = render_journal_panorama(journal_items(ENTRIES, RUNS), "utiles", NOW)
        self.assertIn("Aujourd’hui", page)
        self.assertIn("Date inconnue", page)
        self.assertIn("T1 fusionné", page)
        self.assertNotIn("Incident d&#x27;usine", page)
        self.assertIn("Hier", render_journal_panorama(journal_items(ENTRIES, RUNS), "tout", NOW))

    def test_a_filter_keeps_its_kind_only(self):
        page = render_journal_panorama(journal_items(ENTRIES, RUNS), "livraisons", NOW)
        self.assertIn("T1 fusionné", page)
        self.assertNotIn("Ticket af-t1 arrêté", page)
        self.assertIn('aria-current="page">Livraisons', page)


if __name__ == "__main__":
    unittest.main()
