"""The destination Usine (cockpit.ui.factory): the machine read where the
cockpit runs, the sources and their freshness, the agents seen on runs."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.ui.factory.page import read_machine, render_factory_page  # noqa: E402

NOW = 1760000000.0
MACHINE = {"host": "vm", "system": "Linux 6", "cores": 8, "load": 2.0, "mem_total": 24 * 1024 ** 3,
           "mem_used": 6 * 1024 ** 3, "disk_total": 200 * 1024 ** 3, "disk_used": 50 * 1024 ** 3}
SNAPSHOT = {"gc": {"display_name": "superviseur", "freshness": "fresh", "read_at": NOW},
            "beads": {"display_name": "tickets", "freshness": "unknown", "read_at": None},
            "sessions": {"display_name": "agents au travail", "freshness": "fresh", "read_at": NOW,
                         "value": {"sessions": [{"bead_id": "af-a"}]}}}
RUNS = [{"href": "/runs/run?id=af-a", "ticket": "T1",
         "models": {"author": {"model": "claude-opus-5-5", "provider": "claude-standard"}}}]


class FactoryPageTest(unittest.TestCase):
    def page(self):
        return render_factory_page(MACHINE, SNAPSHOT, RUNS, False, "<p>santé</p>", "<p>arrêt</p>", NOW)

    def test_the_machine_says_its_load_memory_and_disk(self):
        page = self.page()
        self.assertIn("25 %", page)
        self.assertIn("Charge moyenne : 2,0 / 8 cœurs", page)
        self.assertIn("6,0 Go", page)
        self.assertIn("50,0 Go utilisés sur 200,0 Go", page)

    def test_every_source_says_its_freshness_never_guessed(self):
        page = self.page()
        self.assertIn("Superviseur", page)
        self.assertIn("jamais lu", page)
        self.assertIn("Non configurées", page)

    def test_the_agents_are_those_seen_on_runs(self):
        page = self.page()
        self.assertIn("claude-opus-5-5", page)
        self.assertIn('href="/runs/run?id=af-a"', page)
        self.assertIn("Aucun run lu ne l’a lancé", page)
        self.assertIn("au travail maintenant : 1", page)

    def test_the_machine_read_here_is_complete_or_none(self):
        machine = read_machine()
        self.assertTrue(machine["cores"])
        for key in ("load", "mem_total", "disk_total"):
            self.assertTrue(machine[key] is None or machine[key] > 0)


if __name__ == "__main__":
    unittest.main()
