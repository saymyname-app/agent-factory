"""Tests for T22 (af-9tfjsc, Spec af-oohx2x .49, §"Étapes d'un chantier"):
the "Page projet" -- lib/cockpit/projects/hors_chantier.py and
lib/cockpit/ui/projects/project_page.py (plus the "Page projet" link T22
adds to lib/cockpit/ui/projects/page.py's project card).

Same precedent T19/T20/T21 set (tests/cockpit-projects-test.py,
tests/cockpit-chantiers-test.py): wiring a real ``/projet/<id>`` HTTP
route into the running cockpit process is out of this ticket's declared
scope -- every assertion here drives the pure functions that are this
ticket's whole public interface, with bead fixtures shaped like real
``bd show``/``bd list`` output (tests/fixtures/cockpit/project-page/).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "project-page"

sys.path.insert(0, str(ROOT / "lib"))

from cockpit.projects.builder import build_historique_par_projet, build_projects  # noqa: E402
from cockpit.projects.descriptors import load_descriptors  # noqa: E402
from cockpit.projects.hors_chantier import (  # noqa: E402
    KIND_BUG,
    KIND_CORRECTIF_DIRECT,
    KIND_PROPOSITION,
    hors_chantier_items,
    hors_chantier_par_projet,
)
from cockpit.projects.model import ACCEPTE, CADRAGE, GRAPHE, LIVRAISON, SPEC  # noqa: E402
from cockpit.ui.projects.page import render_historique_section, render_projects_section  # noqa: E402
from cockpit.ui.projects.project_page import (  # noqa: E402
    VIEW_BANDE,
    VIEW_TABLEAU,
    project_page_url,
    render_project_page,
)

DESCRIPTORS = FIXTURES / "descriptors"


def load_beads():
    with open(FIXTURES / "beads.json", encoding="utf-8") as fh:
        return json.load(fh)


def build(beads=None, defects=None):
    descriptors = load_descriptors(DESCRIPTORS)
    beads = beads if beads is not None else load_beads()
    return build_projects(descriptors, beads, defects=defects)


class LienPageProjetTest(unittest.TestCase):
    """AC1: "Un test montre le lien depuis chaque projet ... "."""

    def test_link_appears_on_every_project_card(self):
        projects, _sans_projet = build()
        html_out = render_projects_section(projects)
        self.assertIn('href="/projet/agent-factory"', html_out)
        self.assertIn("Page projet", html_out)

    def test_project_page_url_is_stable(self):
        self.assertEqual("/projet/agent-factory", project_page_url("agent-factory"))


class ChantiersParEtapeTest(unittest.TestCase):
    """AC1: "... et les chantiers groupés par étape."""

    def setUp(self):
        self.projects, _sans_projet = build()
        self.project = self.projects[0]
        self.assertEqual("agent-factory", self.project.project_id)
        # Fixture covers three distinct stages so "groupé par étape" is a
        # real assertion, not a single-row coincidence.
        self.stages = {c.stage for c in self.project.chantiers}
        self.assertEqual({CADRAGE, SPEC, LIVRAISON}, self.stages)

    def test_tableau_view_groups_each_chantier_under_its_stage_column(self):
        html_out = render_project_page(self.project, view=VIEW_TABLEAU)
        for stage in (CADRAGE, SPEC, GRAPHE, LIVRAISON):
            self.assertIn('data-stage="%s"' % stage, html_out)
        self.assertIn("Carte — Nettoyage des branches anciennes", html_out)
        self.assertIn("Spec — Invitations par lien", html_out)
        self.assertIn("Graphe de tickets — Cockpit V2", html_out)
        # Tableau shows every stage column even when empty, Accepté/Promu
        # included (no chantier reaches them in this fixture).
        self.assertIn('data-stage="%s"' % ACCEPTE, html_out)

    def test_bande_view_renders_every_chantier_with_its_own_stepper(self):
        html_out = render_project_page(self.project, view=VIEW_BANDE)
        self.assertIn('class="cockpit-pp-strip-item"', html_out)
        self.assertIn('data-stage="%s"' % LIVRAISON, html_out)
        self.assertIn("aria-label=\"Étape", html_out)
        # Every chantier from the fixture is present, not just one stage.
        for titre in (
            "Carte — Nettoyage des branches anciennes",
            "Spec — Invitations par lien",
            "Graphe de tickets — Cockpit V2",
        ):
            self.assertIn(titre, html_out)

    def test_view_selector_offers_tableau_and_bande_both_rendered(self):
        html_out = render_project_page(self.project, view=VIEW_TABLEAU)
        self.assertIn('data-view-choice="tableau"', html_out)
        self.assertIn('data-view-choice="bande"', html_out)
        self.assertIn('data-view="tableau"', html_out)
        # T21 (af-1al0t1 comment): both variants are server-rendered, the
        # client-side toggle only flips which one shows.
        self.assertIn('class="cockpit-pp-view cockpit-pp-view-tableau"', html_out)
        self.assertIn('class="cockpit-pp-view cockpit-pp-view-bande"', html_out)

    def test_unknown_view_falls_back_to_tableau(self):
        html_out = render_project_page(self.project, view="groupes-verticaux")
        self.assertIn('data-view="tableau"', html_out)


class HorsChantierTest(unittest.TestCase):
    """AC2: "Un test montre le travail hors chantier sans étape, ..."."""

    def test_hors_chantier_items_classified_by_kind(self):
        items = hors_chantier_items(load_beads())
        by_id = {item.id: item for item in items}
        self.assertEqual(KIND_BUG, by_id["af-bug01"].kind)
        self.assertEqual(KIND_PROPOSITION, by_id["af-prop01"].kind)
        self.assertEqual(KIND_CORRECTIF_DIRECT, by_id["af-corr01"].kind)
        # Chantier-defining beads (map, spec, convoy, delivery ticket) and
        # closed beads never appear here.
        self.assertNotIn("af-map01", by_id)
        self.assertNotIn("af-spec01", by_id)
        self.assertNotIn("af-convoy01", by_id)
        self.assertNotIn("af-tk01", by_id)
        self.assertNotIn("af-bug-closed", by_id)

    def test_hors_chantier_item_carries_no_stage_field(self):
        item = hors_chantier_items(load_beads())[0]
        self.assertFalse(hasattr(item, "stage"))
        self.assertFalse(hasattr(item, "stage_index"))

    def test_page_shows_hors_chantier_section_with_no_stage_markup(self):
        projects, _sans_projet = build()
        project = projects[0]
        by_projet = hors_chantier_par_projet(load_beads())
        html_out = render_project_page(
            project, hors_chantier=by_projet.get("agent-factory", [])
        )
        self.assertIn("Travail hors chantier", html_out)
        self.assertIn("Bug — le bouton Recommencer ne répond plus", html_out)
        self.assertIn("Proposition — regrouper les deux pages de réglages", html_out)
        self.assertIn("Correctif direct — faute de frappe sur l", html_out)
        self.assertIn('data-kind="Bug"', html_out)
        self.assertIn('data-kind="Proposition"', html_out)
        self.assertIn('data-kind="Correctif direct"', html_out)
        # No stage/stepper attached to a hors-chantier row.
        self.assertIn('data-chantier="af-bug01" data-stage=""', html_out)

    def test_empty_hors_chantier_shows_fixed_text(self):
        html_out = render_project_page(_project_with_no_chantiers(), hors_chantier=[])
        self.assertIn("Aucun travail hors chantier.", html_out)


class AccesHistoriqueTest(unittest.TestCase):
    """AC2: "... et l'accès à l'historique."""

    def test_project_page_links_to_its_own_historique_anchor(self):
        projects, _sans_projet = build()
        html_out = render_project_page(projects[0])
        self.assertIn('href="#cockpit-pp-historique"', html_out)
        self.assertIn("Historique du projet", html_out)
        self.assertIn('id="cockpit-pp-historique"', html_out)

    def test_historique_section_embedded_shows_termine_chantier(self):
        projects, _sans_projet = build()
        hist_projects, hist_sans_projet = build_historique_par_projet(
            load_descriptors(DESCRIPTORS), load_beads()
        )
        historique_html = render_historique_section(hist_projects, hist_sans_projet)
        html_out = render_project_page(projects[0], historique_html=historique_html)
        self.assertIn("Graphe de tickets — Export CSV", html_out)
        self.assertIn('class="cockpit-historique"', html_out)


def _project_with_no_chantiers():
    projects, _sans_projet = build(beads=[])
    return projects[0]


if __name__ == "__main__":
    unittest.main()
