"""The rules of R3 (af-plu8kn; Spec af-fgcw0d, user story 103) at the
lowest level where they are observed -- the functions of
lib/cockpit/projects called in this process (docs/TEST_GUIDELINE.md, §2):
what the tracker says of each step « en cours » of a structured roadmap
(``source.roadmap_chantiers``, ``roadmap.roadmap_rows``), which step a page
heads with (``roadmap.current_step``) and which step the line « Roadmap :
… » of a project names (``depots.apply_to_projects``).

The criterion test of R3
(tests/cockpit-criteria/commands/projects-roadmap-unlinked-test.py) proves
the transmission to the launched cockpit only.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.projects.depots import apply_to_projects  # noqa: E402
from cockpit.projects.model import Project  # noqa: E402
from cockpit.projects.roadmap import current_step, roadmap_rows  # noqa: E402
from cockpit.projects.source import roadmap_chantiers  # noqa: E402

PROJECT = "agent-factory"


def step(step_id, title, status, order, **more):
    return {"id": step_id, "title": title, "status": status, "order": order, **more}


def spec(spec_id, target, status="in_progress"):
    return {"id": spec_id, "status": status, "issue_type": "task",
            "metadata": {"gc.project_id": PROJECT, "planning_run_target": target}}


def convoy(convoy_id, spec_id, status="open", **metadata):
    return {"id": convoy_id, "status": status, "issue_type": "convoy",
            "metadata": {"gc.project_id": PROJECT, "gc.spec_id": spec_id, "gc.graph_digest": f"sha256:{convoy_id}",
                         **metadata}}


def answered(response):
    """What the convoy of the D01 flow carries once Benjamin's answer is
    recorded (bin/owner-answer)."""
    return {"gc.flow.mark": "new-flow/v1",
            "gc.flow.judgement": json.dumps({"verdicts": [], "answers": [
                {"approver": "benjamin", "commit": "1" * 40, "pack": "sha256:" + "a" * 64,
                 "at": "2026-10-20T14:48:00+02:00", "words": "…", "response": response}]})}


class ChantiersOfAStepTest(unittest.TestCase):
    """What ``roadmap_chantiers`` reads of the chantier of a step."""

    def test_a_chantier_benjamin_accepted_is_accepted_its_convoy_still_open(self):
        chantiers = roadmap_chantiers([spec("spec-f3", "F3")],
                                      [convoy("convoy-f3", "spec-f3", **answered("accepted"))])
        self.assertEqual([{"id": "spec-f3", "closed": False, "merged": False, "accepted": True}],
                         chantiers[PROJECT]["F3"])

    def test_a_chantier_at_work_is_neither_accepted_closed_nor_merged(self):
        chantiers = roadmap_chantiers([spec("spec-f4", "F4")], [convoy("convoy-f4", "spec-f4")])
        self.assertEqual([{"id": "spec-f4", "closed": False, "merged": False, "accepted": False}],
                         chantiers[PROJECT]["F4"])

    def test_a_chantier_benjamin_returned_is_not_accepted(self):
        chantiers = roadmap_chantiers([spec("spec-f3", "F3")],
                                      [convoy("convoy-f3", "spec-f3", **answered("returned"))])
        self.assertFalse(chantiers[PROJECT]["F3"][0]["accepted"])


class StepsInProgressTest(unittest.TestCase):
    """What ``roadmap_rows`` flags, and which step ``current_step`` heads with."""

    STEPS = [step("F1", "Isoler l’ancien code", "done", 1),
             step("F2", "Opérations de l’usine", "in_progress", 2),
             step("F3", "Livraison parallèle", "in_progress", 3),
             step("F4", "Cockpit Panorama", "in_progress", 4)]
    OPEN = {"closed": False, "merged": False, "accepted": False}

    def flags(self, rows):
        return {row["id"]: row["flag"] for row in rows}

    def test_no_chantier_targets_it_accepted_and_open(self):
        rows = roadmap_rows(self.STEPS, {"F3": [{**self.OPEN, "accepted": True}], "F4": [self.OPEN]})
        self.assertEqual({"F1": None,
                          "F2": "Aucun chantier relié : rien dans le suivi ne cible cette étape",
                          "F3": "Incohérent : marqué en cours, son résultat est accepté",
                          "F4": None}, self.flags(rows))
        self.assertEqual("F4", current_step(rows)["id"])

    def test_the_tracker_not_read_flags_nothing(self):
        rows = roadmap_rows(self.STEPS, None)
        self.assertEqual({"F1": None, "F2": None, "F3": None, "F4": None}, self.flags(rows))
        self.assertEqual("F2", current_step(rows)["id"])

    def test_every_step_in_progress_with_a_reserve_heads_with_none(self):
        rows = roadmap_rows(self.STEPS, {"F3": [{**self.OPEN, "closed": True}]})
        self.assertIsNone(current_step(rows))

    def test_a_step_waiting_on_a_required_step_is_not_flagged_for_its_ended_chantier_and_never_heads(self):
        steps = [step("C1", "Cockpit relivré", "in_progress", 1),
                 step("D1", "Flux D01", "in_progress", 2, done_requires=["C1"]),
                 step("D2", "Flux D02", "in_progress", 3, done_requires=["C1"])]
        for ended in ({"closed": True}, {"merged": True}, {"accepted": True}):
            with self.subTest(ended=ended):
                rows = roadmap_rows(steps, {"C1": [{**self.OPEN, "closed": True}],
                                            "D1": [{**self.OPEN, **ended}], "D2": [self.OPEN]})
                self.assertIsNone(self.flags(rows)["D1"], "R5: a step waiting on a required step is in progress")
                self.assertEqual("D2", current_step(rows)["id"],
                                 "the current step is never a step whose chantier is closed, merged or accepted")


class LineRoadmapOfAProjectTest(unittest.TestCase):
    """The line « Roadmap : … » of a project (``apply_to_projects``)."""

    def presented(self, steps, chantiers):
        project = Project(project_id=PROJECT, display_name="Agent Factory")
        row = {"read_at": 1.0, "value": {"roadmaps": {PROJECT: {"ok": True, "step": {
            "id": steps[-1]["id"], "title": steps[-1]["title"], "status": steps[-1]["status"]}}},
            "steps": {PROJECT: steps}}}
        apply_to_projects([project], row, {PROJECT: chantiers})
        return project.roadmap_step

    def test_a_step_in_progress_no_chantier_targets_is_named_with_its_reserve(self):
        shown = self.presented([step("F1", "Isoler l’ancien code", "done", 1),
                                step("F2", "Opérations de l’usine", "in_progress", 2)], {})
        self.assertEqual(("Opérations de l’usine", "Aucun chantier relié : rien dans le suivi ne cible cette étape"),
                         (shown.title, shown.reserve))

    def test_a_roadmap_all_done_names_its_last_step(self):
        shown = self.presented([step("F1", "Isoler l’ancien code", "done", 1),
                                step("F2", "Opérations de l’usine", "done", 2)], {})
        self.assertIsNotNone(shown, "a roadmap all done loses its line « Roadmap : … »")
        self.assertEqual(("Opérations de l’usine", None), (shown.title, shown.reserve))


if __name__ == "__main__":
    unittest.main()
