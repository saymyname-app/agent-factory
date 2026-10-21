"""The destination Projets of Panorama (cockpit.ui.projects.panorama): a
card per project with its counts, the whole card the link to its page."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.projects.model import Chantier, Project  # noqa: E402
from cockpit.ui.projects.panorama import render_projects_list  # noqa: E402

NOW = 1760000000.0


def chantier(cid, etat="normal", termine=False):
    return Chantier(id=cid, titre="Chantier %s" % cid, projet="p", stage="Livraison", detail="d", etat=etat,
                    etat_cible=None, promu_masque=False, promu_inconnu=False, termine=termine, a_regarder="",
                    abandonne=False, raison_abandon=None, planning_run_target=None, rig=None)


def run(ticket, status, state, end, rig="p"):
    return {"ticket": ticket, "status": status, "state": state, "end": end, "rig": rig, "href": "/runs/run?id=%s" % ticket,
            "type": "Livraison · %s" % ticket, "title": "t", "step": "s", "tone": None, "elapsed": 60,
            "started": "19/10 10:00", "lanes": []}


PROJECT = Project(project_id="p", display_name="Projet P",
                  chantiers=[chantier("a", etat="a_toi_de_jouer"), chantier("b")])
RUNS = [run("T2", "En cours", "live", NOW), run("T1", "Fusionné", "done", NOW - 3600),
        run("T0", "Fusionné", "done", NOW - 8 * 86400), run("X", "Fusionné", "done", NOW, rig="other")]


class ProjectsPanoramaTest(unittest.TestCase):
    def test_a_card_counts_what_waits_what_is_open_and_merged_this_week(self):
        page = render_projects_list([PROJECT], RUNS, NOW, checked="19:43")
        self.assertIn('href="/projet/p"', page)
        self.assertIn("À toi de jouer · 1", page)
        self.assertIn("Chantier actuel : Chantier b", page)
        self.assertIn("<dt>Chantiers ouverts</dt><dd>2</dd>", page)
        self.assertIn("<dt>Runs fusionnés · 7 j</dt><dd>1</dd>", page)
        self.assertIn("<dt>Runs ouverts</dt><dd>1</dd>", page)
        self.assertIn("Dernier run : T2 · En cours", page)

    def test_the_whole_card_is_the_link_to_the_page_of_the_project(self):
        page = render_projects_list([PROJECT], RUNS, NOW)
        self.assertIn('<a class="pj-card" href="/projet/p" aria-label="Page projet Projet P · À toi de jouer · 1 · '
                      'Chantier actuel : Chantier b">', page)
        self.assertEqual(1, page.count("<a "), "a link inside the card")

    def test_no_project_and_no_run_are_said(self):
        self.assertIn("Aucun projet déclaré", render_projects_list([], [], NOW))
        self.assertIn("Aucun run lu pour ce projet", render_projects_list([PROJECT], None, NOW))


if __name__ == "__main__":
    unittest.main()
