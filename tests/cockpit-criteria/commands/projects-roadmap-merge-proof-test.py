#!/usr/bin/env python3
"""Criterion test 1 of R18 « Revue de fin 96b3429f0dee F1.33 : Roadmap :
fusion du résultat lue depuis la preuve de fusion, pas les PR de tickets »
(af-gnplfy; Spec af-fgcw0d, decision « État D01 commun aux vues » 2,
« Ticket fermé/intégré ne signifie pas fusion du résultat dans la branche
protégée. », Testing Decisions 1, 3 and 8): on the page of a project, a
step « en cours » whose chantier has every ticket PR merged into the
integration branch, and no record of the final merge proof on its convoy,
is not said « son résultat est fusionné ».

The case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: no other case
sees it). The dataset holds the Factory and SayMyName as the tree declares
them, their knowledge repositories -- disposable Git repositories, the
Factory's holding the roadmap the case writes -- and a tracker in the
shapes the flow writes: a Spec carries the Roadmap Step it targets
(`planning_run_target`), its convoy names it (`gc.spec_id`) and is still
open, and each ticket of that convoy recorded the merge of its PR into the
integration branch (`gc.merge_commit`), the convoy holding no promotion
record (`gc.flow.promotion`).

The page of the Factory, /projet/agent-factory, is read as a headless
Chromium renders it (home_destination.measure).

False if the roadmap says « Incohérent : marqué en cours, son résultat est
fusionné » on that step.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part_name, rows  # noqa: E402

FACTORY = "agent-factory"
SAYMYNAME = "saymyname"


class ProjectsRoadmapMergeProof(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # --- Criterion 1 ------------------------------------------------------------

    def test_a_step_whose_ticket_prs_are_merged_into_integration_without_merge_proof_is_not_said_merged(self):
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        factory_roadmap = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "done"

[[step]]
id = "F2"
title = "Cockpit Panorama"
done_when = "son résultat jugé puis fusionné dans la branche protégée"
order = 2
status = "in_progress"
"""

        def bead(bead_id: str, title: str, status: str, issue_type: str, labels: list[str], **metadata) -> dict:
            return {"id": bead_id, "title": title, "status": status, "issue_type": issue_type, "labels": labels,
                    "created_at": "2026-10-02T10:00:00+02:00", "metadata": metadata}

        beads = [
            # F2: its convoy open, every ticket PR merged into the integration
            # branch, no record of the final merge proof.
            bead("spec-f2", "Spec — Cockpit Panorama", "in_progress", "task", [],
                 **{"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC", "planning_run_target": "F2"}),
            bead("convoy-f2", "Cockpit Panorama", "open", "convoy", ["approved-ticket-graph"],
                 **{"gc.project_id": FACTORY, "gc.graph_digest": "sha256:convoy-f2", "gc.spec_id": "spec-f2"}),
            bead("ticket-f2-a", "Ticket ticket-f2-a", "closed", "task", ["approved-ticket-graph", "delivery-plane"],
                 **{"gc.graph_digest": "sha256:convoy-f2", "gc.dispatch_rig": FACTORY, "gc.merge_commit": "3" * 40}),
            bead("ticket-f2-b", "Ticket ticket-f2-b", "closed", "task", ["approved-ticket-graph", "delivery-plane"],
                 **{"gc.graph_digest": "sha256:convoy-f2", "gc.dispatch_rig": FACTORY, "gc.merge_commit": "4" * 40}),
        ]
        work = self.tree.work / "knowledge-merge-proof"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: (
                    '[[step]]\nid = "S1"\ntitle = "Inscription par lien magique"\ndone_when = "un compte créé '
                    'sans mot de passe"\norder = 1\nstatus = "in_progress"\n')}, "2026-10-14T09:30:00+02:00"),
        }
        address = launch_declared(self.tree, "projects-roadmap-merge-proof", {
            "generated_at": "2026-10-21T12:00:00+02:00", "synthetic": True,
            "ui": {"id": "projects-roadmap-merge-proof", "page": "projects"},
            "projects": [factory, saymyname],
            "repos": {repo: str(path) for repo, path in repos.items()},
            "tracker": {"beads": {b["id"]: b for b in beads}}})
        page = measure(address, f"/projet/{FACTORY}")[0]

        roadmap = part_name(page, "Roadmap")
        self.assertTrue(roadmap, f"the page shows no roadmap; it says « {page.get('text', '')[:400]} »")
        lines = rows(page, roadmap)
        found = [text for text in lines if text.startswith("Cockpit Panorama")]
        self.assertEqual(1, len(found), f"not one line of « Cockpit Panorama » in the roadmap: {lines}")
        self.assertNotIn("son résultat est fusionné", found[0],
                         "a step whose ticket PRs are merged into integration, without merge proof, is said merged")
        self.assertIn("En cours", found[0], "the step whose chantier is at work is not said in progress")


if __name__ == "__main__":
    unittest.main()
