"""The destination Rituels (cockpit.ui.rituals): the catalogue of the Spec,
when each ritual last ran read from the rituals file, never example values."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.ui.panorama.shell import Anchors  # noqa: E402
from cockpit.ui.rituals.page import read_rituals, render_rituals  # noqa: E402

TOML = """
[[ritual]]
id = "architecture:factory"
kind = "pr_threshold"
repo = "o/r"
base_branch = "main"
threshold = 20
last_done = "paused"
paused_reason = "refactor churn"
resume_when = "A6 closed"

[[ritual]]
id = "incidents"
kind = "pr_threshold"
repo = "o/r"
base_branch = "main"
threshold = 5
last_done = "2026-10-11T21:30:00Z"
"""


def page(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rituals.toml"
        if text is not None:
            path.write_text(text)
        return render_rituals(read_rituals(str(path)), Anchors())


class RitualsTest(unittest.TestCase):
    def test_the_catalogue_of_the_spec_in_its_order(self):
        html = page(TOML)
        titles = ["Préparer la prochaine release", "Revue d’incidents", "Revue d’architecture",
                  "Qualité / AI Slop", "Diagnostic Factory"]
        self.assertEqual(sorted(titles, key=html.index), titles)
        self.assertNotIn("EXEMPLE", html)

    def test_a_paused_ritual_says_why_and_when_it_resumes(self):
        self.assertIn("Dernière revue (Usine) : en pause · refactor churn · reprise : A6 closed"
                      " · due après 20 PR fusionnées dans main", page(TOML))

    def test_a_ritual_done_says_its_day_in_paris(self):
        self.assertIn("Dernière revue : 11/10/2026 · due après 5 PR fusionnées dans main", page(TOML))

    def test_a_ritual_the_file_names_nothing_for_is_not_filled_in(self):
        html = page(TOML)
        self.assertIn("Dernier cadrage : non renseigné<", html)
        self.assertIn("Dernière revue : non renseignée<", html)

    def test_an_unreadable_file_says_unknown(self):
        self.assertIn("Dernière revue : inconnue, docs/rituals.toml n’est pas lu", page(None))
        self.assertIn("Dernière revue : inconnue", page("not = [toml"))

    def test_nothing_launches_from_here(self):
        html = page(TOML)
        self.assertNotIn("<button", html)
        self.assertNotIn("<form", html)
        self.assertIn("Lancer un rituel n’est pas encore raccordé à cette vue", html)

    def test_the_parts_carry_the_anchors_of_the_reference(self):
        html = page(TOML)
        for anchor in ("h1-1", "page-lead-1", "ritual-grid-1", "panel-5", "h2-5"):
            self.assertIn('data-anchor="%s"' % anchor, html)

    def test_the_factory_rituals_file_reads(self):
        rituals = read_rituals(str(ROOT / "docs" / "rituals.toml"))
        self.assertTrue(rituals and all(ritual.get("id") for ritual in rituals))


if __name__ == "__main__":
    unittest.main()
