#!/usr/bin/env python3
"""Criterion test 1 of R3 « Roadmap d'un projet — une étape « en cours »
sans chantier relié est signalée, pas tue » (af-plu8kn; Spec af-fgcw0d,
user story 103, decision « Projets et données » 10, Testing Decisions 1, 3
and 8): on the page of a project, a step « en cours » that no chantier
targets says « aucun chantier relié », a step « en cours » whose chantier
is accepted is flagged inconsistent, and only a step « en cours » whose
chantier is open is shown in progress without reserve -- the current step
the roadmap heads with.

The case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: no other case
sees it). The dataset holds the Factory and SayMyName as the tree declares
them, their knowledge repositories -- disposable Git repositories, the
Factory's holding the roadmap the case writes -- and a tracker in the
shapes the flow writes: a Spec carries the Roadmap Step it targets
(`planning_run_target`), its convoy names it (`gc.spec_id`); the accepted
result carries the records its convoy state writes once Benjamin's answer
is recorded (`gc.flow.delivered`, `gc.flow.evidence_pack`,
`gc.flow.judgement`), its convoy still open, nothing merged yet.

The page of the Factory, /projet/agent-factory, is read as a headless
Chromium renders it (home_destination.measure).

False if a step « en cours » no chantier targets is shown without reserve,
or if the roadmap heads with a step whose chantier is accepted (or with
any step but the one whose chantier is open).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, says  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part, part_name, rows  # noqa: E402

FACTORY = "agent-factory"
SAYMYNAME = "saymyname"


class ProjectsRoadmapUnlinked(unittest.TestCase):
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

    def test_a_step_in_progress_no_chantier_targets_says_so_and_the_roadmap_heads_with_the_step_whose_chantier_is_open(self):
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
title = "Opérations de l’usine"
done_when = "son graphe livré et fermé"
order = 2
status = "in_progress"

[[step]]
id = "F3"
title = "Livraison parallèle"
done_when = "son graphe livré, son résultat jugé"
order = 3
status = "in_progress"

[[step]]
id = "F4"
title = "Cockpit Panorama"
done_when = "le cockpit lit ses sources réelles"
order = 4
status = "in_progress"
"""
        judged, pack = "1" * 40, "sha256:" + "a" * 64
        delivered = {"at": "2026-10-20T14:30:00+02:00", "commit": judged, "pack": pack, "protected": "0" * 40,
                     "version": "spec-end/v4"}
        accepted = {
            "gc.flow.mark": "new-flow/v1",
            "gc.flow.delivered": json.dumps(delivered, ensure_ascii=False),
            "gc.flow.evidence_pack": json.dumps(
                {"at": delivered["at"], "commit": judged, "digest": pack, "path": "/nonexistent/pack",
                 "conforming": True, "inadmissible": 0, "version": "evidence-pack/v1"}, ensure_ascii=False),
            "gc.flow.judgement": json.dumps(
                {"verdicts": [], "answers": [{"approver": "benjamin", "commit": judged, "pack": pack,
                                              "at": "2026-10-20T14:48:00+02:00", "words": "C’est ce que je voulais.",
                                              "response": "accepted"}]}, ensure_ascii=False),
        }

        def bead(bead_id: str, title: str, status: str, issue_type: str, labels: list[str], **metadata) -> dict:
            return {"id": bead_id, "title": title, "status": status, "issue_type": issue_type, "labels": labels,
                    "created_at": "2026-10-02T10:00:00+02:00", "metadata": metadata}

        beads = [
            # F2: no Spec targets it.
            # F3: its chantier accepted by Benjamin's recorded answer, its convoy still open.
            bead("spec-f3", "Spec — Livraison parallèle", "in_progress", "task", [],
                 **{"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC", "planning_run_target": "F3"}),
            bead("convoy-f3", "Livraison parallèle", "open", "convoy", ["approved-ticket-graph"],
                 **{"gc.project_id": FACTORY, "gc.graph_digest": "sha256:convoy-f3", "gc.spec_id": "spec-f3",
                    **accepted}),
            # F4: its chantier open, a ticket at work.
            bead("spec-f4", "Spec — Cockpit Panorama", "in_progress", "task", [],
                 **{"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC", "planning_run_target": "F4"}),
            bead("convoy-f4", "Cockpit Panorama", "open", "convoy", ["approved-ticket-graph"],
                 **{"gc.project_id": FACTORY, "gc.graph_digest": "sha256:convoy-f4", "gc.spec_id": "spec-f4"}),
            bead("ticket-f4-a", "Ticket ticket-f4-a", "in_progress", "task", ["approved-ticket-graph", "delivery-plane"],
                 **{"gc.graph_digest": "sha256:convoy-f4", "gc.dispatch_rig": FACTORY}),
        ]
        work = self.tree.work / "knowledge-unlinked"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: (
                    '[[step]]\nid = "S1"\ntitle = "Inscription par lien magique"\ndone_when = "un compte créé '
                    'sans mot de passe"\norder = 1\nstatus = "in_progress"\n')}, "2026-10-14T09:30:00+02:00"),
        }
        address = launch_declared(self.tree, "projects-roadmap-unlinked", {
            "generated_at": "2026-10-21T12:00:00+02:00", "synthetic": True,
            "ui": {"id": "projects-roadmap-unlinked", "page": "projects"},
            "projects": [factory, saymyname],
            "repos": {repo: str(path) for repo, path in repos.items()},
            "tracker": {"beads": {b["id"]: b for b in beads}}})
        page = measure(address, f"/projet/{FACTORY}")[0]

        roadmap = part_name(page, "Roadmap")
        self.assertTrue(roadmap, f"the page shows no roadmap; it says « {page.get('text', '')[:400]} »")
        lines = rows(page, roadmap)

        def line(title: str) -> str:
            found = [text for text in lines if text.startswith(title)]
            self.assertEqual(1, len(found), f"not one line of « {title} » in the roadmap: {lines}")
            return found[0]

        unlinked, accepted_line, open_line = line("Opérations de l’usine"), line("Livraison parallèle"), \
            line("Cockpit Panorama")
        self.assertIn("aucun chantier relié", unlinked.lower(),
                      "a step in progress no chantier targets does not say « aucun chantier relié »")
        self.assertRegex(accepted_line, r"(?i)incohéren",
                         "a step in progress whose chantier is accepted is not flagged inconsistent")
        self.assertIn("En cours", open_line, "the step whose chantier is open is not said in progress")
        self.assertNotRegex(open_line, r"(?i)incohéren|aucun chantier",
                            "the step whose chantier is open carries a reserve")
        self.assertNotRegex(line("Isoler l’ancien code"), r"(?i)incohéren|aucun chantier", "a step done carries a reserve")

        headings = [says(page, anchor["name"]) for anchor in page.get("anchors", [])
                    if anchor["tag"] == "h2" and anchor["chain"] and anchor["chain"][0] == roadmap]
        self.assertEqual(["Cockpit Panorama"], headings,
                         f"the roadmap does not head with the step whose chantier is open; it says « {part(page, 'Roadmap')} »")


if __name__ == "__main__":
    unittest.main()
