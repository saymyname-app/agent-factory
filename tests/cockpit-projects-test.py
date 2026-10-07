"""Tests for T19 (af-95l8ki, Spec af-oohx2x §"Suivre les projets"): the
"Projets" section's data (lib/cockpit/projects/**) and rendering
(lib/cockpit/ui/projects/**).

Neither module has a CLI or HTTP surface of its own -- wiring them into the
running cockpit process (readmodel pollers, server.py routes,
ui/base/page.py's extra_sections_html) is out of this ticket's declared
scope (gc.scope_paths: lib/cockpit/projects/**, lib/cockpit/ui/projects/**,
tests/cockpit-projects-test.py, tests/fixtures/cockpit/projects/** only),
the same precedent tests/cockpit-more-requests-test.py (T15) sets: every
assertion here drives the pure functions that *are* this ticket's whole
public interface, with bead fixtures shaped exactly like real
``bd show``/``bd list``/``bd children --json`` output.

Stage fixtures (AC2, "un test par étape (1 à 5)"): map-cadrage.json (1),
spec-draft.json (2), graphe-a-approuver.json (3), convoy-livraison.json (4)
and convoy-livre.json (5) -- each proven true from the fixture, then proven
to flip at-source exactly like the existing Operator Request sources do.

The roadmap read (AC3) uses a real disposable git repository (like
tests/cockpit-health-test.py's GitFixture), never a fake ``git`` binary --
the "faux clone git" of the Testing Decisions is a throwaway repo, not a
stubbed command, so a genuine fetch/show round trip is exercised.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "projects"

sys.path.insert(0, str(ROOT / "lib"))

from cockpit.projects.builder import build_projects  # noqa: E402
from cockpit.projects.descriptors import load_descriptors  # noqa: E402
from cockpit.projects.model import CADRAGE, GRAPHE, LIVRAISON, LIVRE, SPEC  # noqa: E402
from cockpit.projects.roadmap import (  # noqa: E402
    RoadmapReadError,
    pick_current_step,
    read_current_step,
)
from cockpit.projects.stage import (  # noqa: E402
    build_chantiers,
    cadrage_chantiers,
    convoy_chantiers,
    graphe_chantiers,
    spec_chantiers,
)
from cockpit.requests.defects import DefectCounter  # noqa: E402
from cockpit.ui.projects.page import render_projects_section  # noqa: E402


def load_fixture(name):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


class CadrageStageTest(unittest.TestCase):
    def test_open_map_is_cadrage_with_decision_count_and_exits_when_closed(self):
        beads = load_fixture("map-cadrage.json")
        children = load_fixture("map-cadrage-children.json")
        chantiers = cadrage_chantiers(beads, {"af-map01": children})
        self.assertEqual(1, len(chantiers))
        chantier = chantiers[0]
        self.assertEqual(CADRAGE, chantier.stage)
        self.assertEqual("agent-factory", chantier.projet)
        self.assertEqual("Cadrage : 2/4 décisions", chantier.detail)

        # Exit at-source: the map bead closes (Spec approved and map closed
        # by spec-approve).
        beads[0]["status"] = "closed"
        self.assertEqual([], cadrage_chantiers(beads, {"af-map01": children}))

    def test_map_with_no_known_children_shows_zero_of_zero(self):
        beads = load_fixture("map-cadrage.json")
        self.assertEqual(
            "Cadrage : 0/0 décisions", cadrage_chantiers(beads, {})[0].detail
        )


class SpecStageTest(unittest.TestCase):
    def test_draft_spec_is_spec_stage_and_exits_when_approved(self):
        beads = load_fixture("spec-draft.json")
        chantiers = spec_chantiers(beads)
        self.assertEqual(1, len(chantiers))
        self.assertEqual(SPEC, chantiers[0].stage)
        self.assertEqual("agent-factory", chantiers[0].projet)

        beads[0]["metadata"]["spec_state"] = "APPROVED_SPEC"
        self.assertEqual([], spec_chantiers(beads))


class GrapheStageTest(unittest.TestCase):
    def test_draft_graph_of_approved_spec_is_graphe_and_exits_when_published(self):
        beads = load_fixture("graphe-a-approuver.json")
        chantiers = graphe_chantiers(beads)
        self.assertEqual(1, len(chantiers))
        self.assertEqual(GRAPHE, chantiers[0].stage)
        self.assertEqual("agent-factory", chantiers[0].projet)

        # Exit at-source: publish adds the approved label.
        for bead in beads:
            if bead["id"] == "af-draft01":
                bead["labels"].append("approved-ticket-graph")
        self.assertEqual([], graphe_chantiers(beads))

    def test_draft_graph_of_unapproved_spec_is_not_yet_graphe(self):
        """Stage table: Graphe requires "Spec APPROVED_SPEC" -- a draft
        graph bead whose source Spec is still DRAFT_SPEC names no chantier
        stage yet (its chantier is still showing as Spec)."""
        beads = load_fixture("graphe-not-ready.json")
        self.assertEqual([], graphe_chantiers(beads))


class ConvoyStageTest(unittest.TestCase):
    def test_open_convoy_is_livraison_with_merged_en_cours_en_pr_counts(self):
        beads = load_fixture("convoy-livraison.json")
        chantiers = convoy_chantiers(beads)
        self.assertEqual(1, len(chantiers))
        chantier = chantiers[0]
        self.assertEqual(LIVRAISON, chantier.stage)
        self.assertEqual("saymyname", chantier.projet)
        self.assertEqual("1/4 tickets mergés · 1 en cours · 1 en PR", chantier.detail)

    def test_convoy_closes_only_once_and_becomes_livre(self):
        beads = load_fixture("convoy-livraison.json")
        for bead in beads:
            if bead["issue_type"] == "task":
                bead["status"] = "closed"
                bead["metadata"].pop("gc.delivery_status", None)
        beads[0]["status"] = "closed"
        # A convoy of the Delivery Workflow: the one that waits for an
        # acceptance once delivered (cockpit.projects.stage).
        beads[0]["metadata"]["gc.flow.mark"] = "new-flow/v1"
        chantiers = convoy_chantiers(beads)
        self.assertEqual(1, len(chantiers))
        self.assertEqual(LIVRE, chantiers[0].stage)
        self.assertEqual("Livré : 4/4 tickets mergés", chantiers[0].detail)

    def test_closed_convoy_fixture_is_livre(self):
        beads = load_fixture("convoy-livre.json")
        chantiers = convoy_chantiers(beads)
        self.assertEqual(1, len(chantiers))
        self.assertEqual(LIVRE, chantiers[0].stage)
        self.assertEqual("Livré : 2/2 tickets mergés", chantiers[0].detail)

    def test_closed_beads_outside_the_digest_are_never_counted(self):
        """A ticket that merely shares issue_type "task" but a different
        gc.graph_digest (or none) must never inflate another convoy's
        count -- guards the digest-based grouping, not just its presence."""
        beads = load_fixture("convoy-livraison.json") + [
            {
                "id": "af-unrelated",
                "title": "Unrelated ticket",
                "status": "closed",
                "issue_type": "task",
                "labels": ["approved-ticket-graph", "delivery-plane"],
                "metadata": {"gc.graph_digest": "sha256:zzz"},
            }
        ]
        chantier = convoy_chantiers(beads)[0]
        self.assertEqual("1/4 tickets mergés · 1 en cours · 1 en PR", chantier.detail)


class BuildChantiersTest(unittest.TestCase):
    def test_build_chantiers_covers_every_stage_at_once(self):
        beads = (
            load_fixture("map-cadrage.json")
            + load_fixture("spec-draft.json")
            + load_fixture("graphe-a-approuver.json")
            + load_fixture("convoy-livraison.json")
            + load_fixture("convoy-livre.json")
        )
        children = {"af-map01": load_fixture("map-cadrage-children.json")}
        stages = sorted(c.stage for c in build_chantiers(beads, children))
        self.assertEqual(
            sorted([CADRAGE, SPEC, GRAPHE, LIVRAISON, LIVRE]), stages
        )


class SansProjetTest(unittest.TestCase):
    def test_chantier_with_no_project_key_goes_to_sans_projet_and_is_counted_once(self):
        beads = load_fixture("sans-projet.json")
        descriptors = load_descriptors(FIXTURES / "descriptors")
        defects = DefectCounter()

        projects, sans_projet = build_projects(descriptors, beads, defects=defects)
        self.assertEqual(1, len(sans_projet))
        self.assertEqual("af-map99", sans_projet[0].id)
        self.assertEqual(0, sum(len(p.chantiers) for p in projects))
        self.assertEqual(1, defects.count)

        # Re-render (e.g. next poll) with the same still-unresolved bead:
        # not counted a second time (spec .19/.78: a persisting defect is
        # not a new one; requests/defects.DefectCounter.record_once already
        # proves this contract elsewhere -- this proves this ticket wires
        # it the same way).
        build_projects(descriptors, beads, defects=defects)
        self.assertEqual(1, defects.count)


class DescriptorsTest(unittest.TestCase):
    def test_new_descriptor_appears_with_no_code_change(self):
        """AC1: a project appears purely from its descriptor file -- this
        loader names no project in code."""
        descriptors = load_descriptors(FIXTURES / "descriptors")
        ids = sorted(d["project_id"] for d in descriptors)
        self.assertEqual(["agent-factory", "saymyname"], ids)

    def test_wrong_contract_is_skipped(self):
        descriptors = load_descriptors(FIXTURES / "descriptors")
        self.assertNotIn("ignored", [d["project_id"] for d in descriptors])

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual([], load_descriptors(FIXTURES / "no-such-directory"))


def run_git(repo_dir, *args):
    subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


class RoadmapGitFixture:
    """A disposable bare "origin" plus a read-only clone -- the "faux clone
    git" of the Testing Decisions. AC5: the clone's own working tree is
    never touched by a read (no checkout, ever) and no project repo is ever
    written to -- both provable here because the clone starts on an
    unrelated branch and is never told to switch."""

    def __init__(self, tmp_path):
        self.origin_dir = tmp_path / "origin.git"
        self.clone_dir = tmp_path / "clone"
        run_git(tmp_path, "init", "--bare", str(self.origin_dir))
        run_git(self.origin_dir, "symbolic-ref", "HEAD", "refs/heads/main")
        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(self.clone_dir)],
            check=True, capture_output=True, text=True,
        )
        self._commit_roadmap(
            "[[step]]\nid = \"A1\"\ntitle = \"Un\"\ndone_when = \"x\"\norder = 1\nstatus = \"done\"\n"
            "[[step]]\nid = \"A2\"\ntitle = \"Deux\"\ndone_when = \"y\"\norder = 2\nstatus = \"in_progress\"\n"
        )
        # The clone itself never checks anything out after cloning -- its
        # working tree stays whatever `git clone` left it at (main, here),
        # and read_current_step never runs `checkout`/`reset`/`pull`.

    def _commit_roadmap(self, toml_text):
        work = self.origin_dir.parent / ("seed-work-%d" % len(list(self.origin_dir.parent.glob("seed-work-*"))))
        subprocess.run(
            ["git", "clone", str(self.origin_dir), str(work)],
            check=True, capture_output=True, text=True,
        )
        (work / "roadmap.toml").write_text(toml_text)
        run_git(work, "add", "roadmap.toml")
        run_git(work, "commit", "-m", "roadmap")
        run_git(work, "push", "origin", "HEAD:refs/heads/main")

    def advance_roadmap(self, toml_text):
        self._commit_roadmap(toml_text)


class RoadmapReadTest(unittest.TestCase):
    def test_reads_current_step_from_origin_via_the_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapGitFixture(Path(tmp))
            step = read_current_step(fixture.clone_dir, "roadmap.toml")
            self.assertEqual("A2", step["id"])
            self.assertEqual("in_progress", step["status"])

            # AC5: the clone's own working tree was never touched -- no
            # roadmap.toml checked out into it by the read.
            self.assertFalse((fixture.clone_dir / "roadmap.toml").exists())

    def test_sees_a_later_commit_on_origin_without_a_manual_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapGitFixture(Path(tmp))
            fixture.advance_roadmap(
                "[[step]]\nid = \"A1\"\ntitle = \"Un\"\ndone_when = \"x\"\norder = 1\nstatus = \"done\"\n"
                "[[step]]\nid = \"A2\"\ntitle = \"Deux\"\ndone_when = \"y\"\norder = 2\nstatus = \"done\"\n"
                "[[step]]\nid = \"A3\"\ntitle = \"Trois\"\ndone_when = \"z\"\norder = 3\nstatus = \"todo\"\n"
            )
            step = read_current_step(fixture.clone_dir, "roadmap.toml")
            self.assertEqual("A3", step["id"])

    def test_unreadable_roadmap_path_raises_for_the_caller_to_turn_into_inconnu(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RoadmapGitFixture(Path(tmp))
            with self.assertRaises(RoadmapReadError):
                read_current_step(fixture.clone_dir, "does-not-exist.toml")

    def test_pick_current_step_prefers_in_progress_then_todo_then_last_done(self):
        all_done = [
            {"id": "A1", "order": 1, "status": "done"},
            {"id": "A2", "order": 2, "status": "done"},
        ]
        self.assertEqual("A2", pick_current_step(all_done)["id"])
        self.assertIsNone(pick_current_step([]))


class RenderProjectsSectionTest(unittest.TestCase):
    def test_empty_state(self):
        html_out = render_projects_section([], [])
        self.assertIn('data-state="empty"', html_out)

    def test_project_with_chantier_shows_stepper_and_roadmap(self):
        beads = load_fixture("convoy-livraison.json")
        descriptors = load_descriptors(FIXTURES / "descriptors")
        projects, sans_projet = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, sans_projet)
        self.assertIn("SayMyName", html_out)
        self.assertIn("1/4 tickets mergés", html_out)
        self.assertIn("cockpit-stepper", html_out)
        # Usine (agent-factory) is declared but has no active chantier here.
        self.assertIn("Aucun chantier actif.", html_out)

    def test_sans_projet_section_shows_defect_count(self):
        beads = load_fixture("sans-projet.json")
        descriptors = load_descriptors(FIXTURES / "descriptors")
        projects, sans_projet = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, sans_projet)
        self.assertIn("Sans projet", html_out)
        self.assertIn("1 défaut producteur", html_out)

    def test_escapes_html_in_titles(self):
        beads = json.loads(json.dumps(load_fixture("spec-draft.json")))
        beads[0]["title"] = "<script>alert(1)</script>"
        descriptors = load_descriptors(FIXTURES / "descriptors")
        projects, _ = build_projects(descriptors, beads)
        html_out = render_projects_section(projects, [])
        self.assertNotIn("<script>", html_out)


if __name__ == "__main__":
    unittest.main()
