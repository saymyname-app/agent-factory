#!/usr/bin/env python3
"""Criterion test 1 of R12 « Revue de fin 96b3429f0dee F1.5 : Prouver les
lignes de roadmap par /projet/<id> ou bin/project-roadmap » (af-0p3nfo;
Spec af-fgcw0d, decision « Projets et données » 10, Testing Decisions 1, 3
and 8; docs/TEST_GUIDELINE.md, point 1, « The internal functions stay
forbidden: a test that calls one is not a test of the tool »): each line
of the roadmap of a project and its expected flag are read on the page of
the project the launched cockpit serves -- the cases tests/
cockpit-roadmap-rows-test.py proved by calling the functions of
lib/cockpit/projects.

The cases the criterion tests of R3 and R5 already read on the page (a
step in progress no chantier targets, one whose chantier is accepted, one
whose chantier is open heading the roadmap; a step done before a step it
requires; a step waiting on a required step whose chantier is closed) are
not proven again here. This file reads the others:

- a step whose result Benjamin returned is in progress, without reserve,
  and heads the roadmap;
- a roadmap whose every step in progress carries a reserve heads with no
  step, and the line « Roadmap : … » of the project names the first step
  in progress with its reserve;
- a step waiting on a required step is not flagged for its result merged
  or accepted, and never heads the roadmap;
- a roadmap all done names its last step on the line « Roadmap : … » of
  the project, without reserve;
- a tracker not read flags no step, and the roadmap heads with its first
  step in progress.

Each case declares a dataset of its own in the profile of the tree under
test and starts the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case sees
none of it): the Factory and SayMyName as the tree declares them, their
knowledge repositories -- disposable Git repositories the case commits --
and a tracker in the shapes the flow writes (a Spec carries the Roadmap
Step it targets, `planning_run_target`; its convoy names it, `gc.spec_id`;
Benjamin's answer and the proof of the merge are the records the D01
commands write on the convoy). The case of a tracker not read starts the
cockpit on the dataset projects-content of the profile, the view of the
tracker that fails (« error »), with one step more in its roadmap. The page
of the project, /projet/<project>, is read as a headless Chromium renders
it (home_destination.measure). The line « Roadmap : … » of a project is
not on that page: it is read in the zone « Projets » of the home page,
GET /, over HTTP -- the one page that shows it.

False if a line or its flag differs from what the case writes, or if the
roadmap heads with another step than the case names.
"""

from __future__ import annotations

import copy
import html
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, fetch, measure, says  # noqa: E402
from project_destination import (dataset_of, descriptor_of, knowledge_repository, launch_declared, part,  # noqa: E402
                                 part_name, rows)

ROADMAP = "Roadmap"
FACTORY = "agent-factory"
SAYMYNAME = "saymyname"
AT = "2026-10-21T12:00:00+02:00"
SAYMYNAME_ROADMAP = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "in_progress"
"""


def answer(response: str) -> dict:
    """The metadata a convoy of the new flow carries once Benjamin's answer
    `response` is recorded (bin/owner-answer), its result delivered."""
    judged, pack = "1" * 40, "sha256:" + "a" * 64
    delivered = {"at": "2026-10-20T14:30:00+02:00", "commit": judged, "pack": pack, "protected": "0" * 40,
                 "version": "spec-end/v4"}
    return {
        "gc.flow.mark": "new-flow/v1",
        "gc.flow.delivered": json.dumps(delivered, ensure_ascii=False),
        "gc.flow.evidence_pack": json.dumps(
            {"at": delivered["at"], "commit": judged, "digest": pack, "path": "/nonexistent/pack",
             "conforming": True, "inadmissible": 0, "version": "evidence-pack/v1"}, ensure_ascii=False),
        "gc.flow.judgement": json.dumps(
            {"verdicts": [], "answers": [{"approver": "benjamin", "commit": judged, "pack": pack,
                                          "at": "2026-10-20T14:48:00+02:00", "words": "Ce n’est pas encore ça.",
                                          "response": response}]}, ensure_ascii=False),
    }


def merged() -> dict:
    """The metadata a convoy of the new flow carries once its accepted
    result is merged (bin/outcome-promote), the convoy still open."""
    judged = "1" * 40
    return {**answer("accepted"),
            "gc.flow.promotion": json.dumps({"at": "2026-10-20T14:50:00+02:00", "judged": judged, "merged": "2" * 40,
                                             "protected": "0" * 40, "tip": judged}, ensure_ascii=False)}


def spec(bead_id: str, target: str, status: str = "in_progress") -> dict:
    """A Spec of the Factory that targets the step `target`."""
    return {"id": bead_id, "title": f"Spec {bead_id}", "status": status, "issue_type": "task", "labels": [],
            "created_at": "2026-10-01T10:00:00+02:00",
            "metadata": {"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC", "planning_run_target": target}}


def convoy(bead_id: str, spec_id: str, status: str = "open", **metadata) -> dict:
    """The convoy of the graph of the Spec `spec_id`."""
    return {"id": bead_id, "title": f"Convoi {bead_id}", "status": status, "issue_type": "convoy",
            "labels": ["approved-ticket-graph"], "created_at": "2026-10-02T10:00:00+02:00",
            "metadata": {"gc.project_id": FACTORY, "gc.graph_digest": f"sha256:{bead_id}", "gc.spec_id": spec_id,
                         **metadata}}


class ProjectsRoadmapRows(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()
        cls.declared = 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def serve(self, factory_roadmap: str, beads: list[dict]) -> str:
        """The address of the cockpit started on a dataset holding the
        Factory and SayMyName as the tree declares them, the Factory's
        knowledge repository holding `factory_roadmap`, and the tracker
        `beads`."""
        type(self).declared += 1
        name = f"projects-roadmap-rows-{self.declared}"
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        work = self.tree.work / f"knowledge-{name}"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: SAYMYNAME_ROADMAP}, "2026-10-14T09:30:00+02:00"),
        }
        return launch_declared(self.tree, name, {
            "generated_at": AT, "synthetic": True, "ui": {"id": name, "page": "projects"},
            "projects": [factory, saymyname],
            "repos": {repo: str(path) for repo, path in repos.items()},
            "tracker": {"beads": {bead["id"]: bead for bead in beads}}})

    def roadmap(self, address: str, project: str) -> tuple[dict, list[str], list[str]]:
        """The page of `project` as measured, the lines of its roadmap, and
        the headings the roadmap opens with (the step it presents as
        current)."""
        page = measure(address, f"/projet/{project}")[0]
        holder = part_name(page, ROADMAP)
        self.assertTrue(holder, f"the page of {project} shows no roadmap; it says « {page.get('text', '')[:400]} »")
        headings = [says(page, anchor["name"]) for anchor in page.get("anchors", [])
                    if anchor["tag"] == "h2" and anchor["chain"] and anchor["chain"][0] == holder]
        return page, rows(page, holder), headings

    def line(self, lines: list[str], title: str) -> str:
        found = [line for line in lines if line.startswith(title)]
        self.assertEqual(1, len(found), f"not one line of « {title} » in the roadmap: {lines}")
        return found[0]

    def roadmap_line(self, address: str, project: str) -> str:
        """The line « Roadmap : … » of `project` in the zone « Projets » of
        the home page, GET / -- the page of a project does not show it."""
        status, _, body = fetch(address + "/")
        self.assertEqual(200, status, "the home page is not served")
        found = re.findall(r'data-project="%s".*?<span class="cockpit-project-roadmap"[^>]*>(.*?)</span>'
                           % re.escape(project), body, re.DOTALL)
        self.assertTrue(found, f"the zone « Projets » of the home page holds no line « Roadmap : … » for {project}")
        return html.unescape(re.sub(r"<[^>]+>", "", found[0])).strip()

    def test_a_step_whose_result_benjamin_returned_is_in_progress_without_reserve_and_heads_the_roadmap(self):
        factory_roadmap = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "done"

[[step]]
id = "F2"
title = "Livraison parallèle"
done_when = "son graphe livré, son résultat jugé"
order = 2
status = "in_progress"
"""
        beads = [spec("spec-f2", "F2"), convoy("convoy-f2", "spec-f2", **answer("returned"))]
        _, lines, headings = self.roadmap(self.serve(factory_roadmap, beads), FACTORY)

        returned = self.line(lines, "Livraison parallèle")
        self.assertIn("En cours", returned, "a step whose result Benjamin returned is not said in progress")
        self.assertNotRegex(returned, r"(?i)incohéren|aucun chantier",
                            "a step whose result Benjamin returned carries a reserve, as if accepted")
        self.assertEqual(["Livraison parallèle"], headings,
                         "the roadmap does not head with the step whose result Benjamin returned")

    def test_every_step_in_progress_carrying_a_reserve_heads_the_roadmap_with_none_and_its_line_names_the_first_with_its_reserve(self):
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
"""
        # F2: no Spec targets it. F3: its chantier closed in the tracker.
        beads = [spec("spec-f3", "F3", "closed"), convoy("convoy-f3", "spec-f3", "closed")]
        address = self.serve(factory_roadmap, beads)
        page, lines, headings = self.roadmap(address, FACTORY)

        self.assertIn("Aucun chantier relié : rien dans le suivi ne cible cette étape",
                      self.line(lines, "Opérations de l’usine"), "a step in progress no chantier targets is not flagged")
        self.assertIn("Incohérent : marqué en cours, son chantier est fermé", self.line(lines, "Livraison parallèle"),
                      "a step in progress whose chantier is closed is not flagged")
        self.assertEqual([], headings,
                         f"the roadmap heads with a step that carries a reserve; it says « {part(page, ROADMAP)} »")
        self.assertEqual(
            "Roadmap : Opérations de l’usine · Aucun chantier relié : rien dans le suivi ne cible cette étape",
            self.roadmap_line(address, FACTORY),
            "the line « Roadmap : … » does not name the first step in progress with its reserve")

    def test_a_step_waiting_on_a_required_step_is_not_flagged_for_its_merged_or_accepted_result_and_never_heads_the_roadmap(self):
        factory_roadmap = """\
[[step]]
id = "C1"
title = "Cockpit relivré"
done_when = "le cockpit livré par le flux jugé"
order = 1
status = "in_progress"

[[step]]
id = "D1"
title = "Flux D01"
done_when = "un résultat jugé puis fusionné, et le cockpit relivré"
order = 2
status = "in_progress"
done_requires = ["C1"]

[[step]]
id = "D2"
title = "Flux D02"
done_when = "un résultat jugé puis fusionné, et le cockpit relivré"
order = 3
status = "in_progress"
done_requires = ["C1"]

[[step]]
id = "D3"
title = "Flux D03"
done_when = "son graphe livré, son résultat jugé"
order = 4
status = "in_progress"
"""
        beads = [
            # C1: its chantier closed, nothing merged.
            spec("spec-c1", "C1", "closed"), convoy("convoy-c1", "spec-c1", "closed"),
            # D1: its result merged, its convoy still open.
            spec("spec-d1", "D1"), convoy("convoy-d1", "spec-d1", **merged()),
            # D2: its result accepted, its convoy still open.
            spec("spec-d2", "D2"), convoy("convoy-d2", "spec-d2", **answer("accepted")),
            # D3: its chantier open.
            spec("spec-d3", "D3"), convoy("convoy-d3", "spec-d3"),
        ]
        _, lines, headings = self.roadmap(self.serve(factory_roadmap, beads), FACTORY)

        for title in ("Flux D01", "Flux D02"):
            with self.subTest(step=title):
                waiting = self.line(lines, title)
                self.assertIn("En cours", waiting, "a step waiting on a required step is not said in progress")
                self.assertNotRegex(waiting, r"(?i)incohéren|aucun chantier",
                                    "a step waiting on a required step is flagged for its own result")
        self.assertIn("Incohérent : marqué en cours, son chantier est fermé", self.line(lines, "Cockpit relivré"),
                      "a step in progress whose chantier is closed is not flagged")
        self.assertEqual(["Flux D03"], headings,
                         "the roadmap heads with another step than the one whose chantier is open -- a step whose "
                         "result is merged or accepted is never the current step")

    def test_a_roadmap_all_done_names_its_last_step_without_reserve(self):
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
status = "done"
"""
        address = self.serve(factory_roadmap, [])
        _, lines, _ = self.roadmap(address, FACTORY)

        for title in ("Isoler l’ancien code", "Opérations de l’usine"):
            with self.subTest(step=title):
                done = self.line(lines, title)
                self.assertIn("Terminé", done, "a step done is not said done")
                self.assertNotRegex(done, r"(?i)incohéren|aucun chantier", "a step done carries a reserve")
        self.assertEqual("Roadmap : Opérations de l’usine", self.roadmap_line(address, FACTORY),
                         "a roadmap all done does not name its last step, without reserve, on its line « Roadmap : … »")

    def test_a_tracker_not_read_flags_no_step_and_the_roadmap_heads_with_its_first_step_in_progress(self):
        # The dataset projects-content of the profile, in the view where the
        # tracker fails, its roadmap holding one step more in progress that
        # no chantier targets: read, the tracker would flag it.
        dataset = copy.deepcopy(dataset_of(self.tree, "projects-content"))
        name = "projects-roadmap-rows-unread"
        dataset["ui"] = {**dataset["ui"], "id": name, "state": "error"}
        shown = "Recherche dans les notes\nEn cours\n"
        self.assertIn(shown, dataset["visible_text"], "the roadmap of projects-content is no longer the one read here")
        dataset["visible_text"] = dataset["visible_text"].replace(shown, shown + "Partage des notes\nEn cours\n", 1)
        _, lines, headings = self.roadmap(launch_declared(self.tree, name, dataset), "notes")

        for title in ("Recherche dans les notes", "Partage des notes"):
            with self.subTest(step=title):
                unread = self.line(lines, title)
                self.assertIn("En cours", unread, "a step in progress is not said in progress")
                self.assertNotRegex(unread, r"(?i)incohéren|aucun chantier",
                                    "a step is flagged while the tracker is not read")
        self.assertEqual(["Recherche dans les notes"], headings,
                         "the roadmap does not head with its first step in progress while the tracker is not read")


if __name__ == "__main__":
    unittest.main()
