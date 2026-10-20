"""The destination Journal of Panorama (cockpit.ui.journal.panorama): the
answered requests, the deliveries of the runs and the events held for the
journal, day by day, by category; the logs of the technical sources apart."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.ui.journal.entries import JournalEntry  # noqa: E402
from cockpit.ui.journal.panorama import journal_items, journal_view, render_journal_panorama  # noqa: E402
from cockpit.ui.panorama.shell import Anchors  # noqa: E402

NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc).timestamp()
ENTRIES = [
    JournalEntry(bead_id="af-t1", quoi="répondu b — attendre", quand="2026-10-19T13:50:00Z", par="benjamin",
                 voie="escalation-door", demande="Ticket af-t1 arrêté"),
    JournalEntry(bead_id="af-c1", quoi="Effacée sans réponse enregistrée", quand="2026-10-18T10:00:00Z", par="",
                 voie="clear", demande="Incident d'usine"),
    JournalEntry(bead_id="af-u1", quoi="sans date", quand="", par="", voie="proposal-door", demande="Une proposition"),
    JournalEntry(bead_id="af-e1", quoi="Rapport nocturne reçu", quand="2026-10-19T12:00:00Z", par="", voie="ci",
                 texte=["La nuit s’est bien passée."], plie=["ci.nightly outcome=success"]),
    JournalEntry(bead_id="af-e2", quoi="Une note étrange", quand="2026-10-19T11:00:00Z", par="", voie="mystere",
                 projet="notes"),
]
RUNS = [{"id": "af-t1", "ticket": "T1", "title": "Une page", "href": "/runs/run?id=af-t1", "branch": "ticket/af-t1",
         "events": [{"at": NOW - 600, "lane": "Code", "text": "Fusionné dans l’intégration"},
                    {"at": NOW - 900, "lane": "Code", "text": "Tests verts"}]}]
READ = {"value": {"entries": []}, "freshness": "fresh", "read_at": NOW, "failed_at": None}
GC = {"freshness": "fresh"}


def page(query, entries=ENTRIES, row=READ):
    view = journal_view(row, entries, RUNS, {"notes": "Notes"}, GC)
    return render_journal_panorama(view, query, NOW, Anchors())


class JournalPanoramaTest(unittest.TestCase):
    def test_requests_merges_and_events_are_one_timeline_newest_first(self):
        items = [item for item in journal_items(ENTRIES, RUNS, {"notes": "Notes"}) if not item["log"]]
        self.assertEqual(["changements", "decisions", None, "evenements", "propositions"],
                         [item["category"] for item in items])
        self.assertEqual(("Voir le run", "/runs/run?id=af-t1"), items[1]["link"], "an answered ticket links its run")

    def test_days_are_named_and_a_category_keeps_its_own(self):
        everything = page({})
        self.assertIn("Aujourd’hui", everything)
        self.assertIn("Hier", everything)
        self.assertIn("Date inconnue", everything)
        self.assertIn("T1 fusionné", everything)
        changes = page({"categorie": "changements"})
        self.assertIn("T1 fusionné", changes)
        self.assertNotIn("Ticket af-t1 arrêté", changes)
        self.assertIn('aria-current="true" data-anchor="primary-2">Changements', changes)
        # The former filters of the journal still name their category.
        self.assertIn('aria-current="true" data-anchor="primary-2">Changements', page({"filtre": "livraisons"}))

    def test_an_event_of_an_unknown_nature_is_said_by_the_fallback_with_its_words_folded(self):
        useful = page({})
        start = useful.index('data-bead-id="af-e2"')
        event = useful[start:useful.index("</article>", start)]
        self.assertIn("Signal non reconnu venant de Notes", event)
        self.assertIn("Nature reçue : mystere", event.partition("<details")[2])
        self.assertIn("Titre reçu : Une note étrange", event.partition("<details")[2])

    def test_a_technical_event_is_a_log_with_its_raw_event(self):
        self.assertNotIn("Rapport nocturne reçu", page({}))
        logs = page({"vue": "logs", "source": "ci"})
        self.assertIn("Rapport nocturne reçu", logs)
        self.assertIn("ci.nightly outcome=success", logs)
        self.assertNotIn("Une note étrange", logs)
        self.assertIn("Événement non reconnu", page({"vue": "logs", "source": "autres"}))
        self.assertIn("Aucun log ne contient « absent ».", page({"vue": "logs", "q": "absent"}))

    def test_an_unread_journal_is_never_an_empty_one(self):
        never = {"value": None, "freshness": "unknown", "read_at": None, "failed_at": None}
        self.assertIn("Lecture en cours…", page({}, row=never))
        failed = {**never, "failed_at": NOW}
        self.assertIn("Cette vue est indisponible", page({}, row=failed))
        self.assertIn("CI</strong> · inconnue", page({"vue": "sources"}, row=failed))
        self.assertNotIn("Rien à afficher ici", page({}, row=failed))


if __name__ == "__main__":
    unittest.main()
