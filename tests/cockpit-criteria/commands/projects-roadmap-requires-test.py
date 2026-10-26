#!/usr/bin/env python3
"""Criterion tests of R5 « Roadmap — D01 remis « en cours », et une étape
terminée avant sa condition de fin est signalée » (af-3r1tmr; Spec
af-fgcw0d, decision « Projets et données » 10, « Lecture fraîche ne
signifie pas contenu exact : corriger une roadmap Factory obsolète »,
Testing Decisions 1, 3 and 8): a step of a structured roadmap may declare
the steps its end condition requires (`done_requires`, a list of step
ids); the page of a project flags a step said done one of whose required
steps is not done, and the roadmap the Factory delivers shows D01 in
progress.

Each case declares a dataset of its own in the profile of the tree under
test and starts the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case
sees none of it), as the roadmap cases of E do: the descriptors of the
Factory and of SayMyName, the knowledge repository of each -- a disposable
Git repository the case commits, or the tree under test itself for the
roadmap the Factory delivers -- and the tracker. The page of the project,
/projet/<project>, is read as a headless Chromium renders it
(home_destination.measure). Criterion 2 also reads docs/roadmap.toml of the
tree under test with the command of the Factory that validates a structured
roadmap (project-roadmap validate, run as a process), as its criterion
names it.

False if a step done one of whose required steps is still in progress is
shown « Terminé », with or without reserve, if a step done whose required
steps are all done is flagged, if a step in progress whose required steps
are done is no longer flagged when its chantier is closed or its result
merged, or if the roadmap the Factory delivers does not show D01 in
progress.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part, part_name, rows  # noqa: E402

ROADMAP = "Roadmap"
FACTORY = "agent-factory"
SAYMYNAME = "saymyname"
AT = "2026-10-25T16:00:00+01:00"


def spec(bead_id: str, target: str, status: str) -> dict:
    """A Spec of the Factory that targets the step `target`."""
    return {"id": bead_id, "title": f"Spec {bead_id}", "status": status, "issue_type": "task", "labels": [],
            "created_at": "2026-10-01T10:00:00+02:00",
            "metadata": {"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC", "planning_run_target": target}}


def convoy(bead_id: str, spec_id: str, status: str) -> dict:
    """The convoy of the graph of the Spec `spec_id`."""
    return {"id": bead_id, "title": f"Convoi {bead_id}", "status": status, "issue_type": "convoy",
            "labels": ["approved-ticket-graph"], "created_at": "2026-10-02T10:00:00+02:00",
            "metadata": {"gc.project_id": FACTORY, "gc.graph_digest": f"sha256:{bead_id}", "gc.spec_id": spec_id}}


def ticket(bead_id: str, convoy_id: str, status: str, **metadata) -> dict:
    """A ticket of the convoy `convoy_id`, as its graph was published."""
    return {"id": bead_id, "title": f"Ticket {bead_id}", "status": status, "issue_type": "task",
            "labels": ["approved-ticket-graph", "delivery-plane"], "created_at": "2026-10-02T10:00:00+02:00",
            "metadata": {"gc.graph_digest": f"sha256:{convoy_id}", "gc.dispatch_rig": FACTORY, **metadata}}


class ProjectsRoadmapRequires(unittest.TestCase):
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

    def serve(self, repos: dict[str, Path], beads: list[dict]) -> str:
        """The address of the cockpit started on a dataset holding the
        Factory and SayMyName as the tree declares them, the knowledge
        repositories `repos` (by the name the descriptors give them) and
        the tracker `beads`."""
        type(self).declared += 1
        name = f"projects-roadmap-requires-{self.declared}"
        dataset = {"generated_at": AT, "synthetic": True, "ui": {"id": name, "page": "projects"},
                   "projects": [descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)],
                   "repos": {repo: str(path) for repo, path in repos.items()},
                   "tracker": {"beads": {bead["id"]: bead for bead in beads}}}
        return launch_declared(self.tree, name, dataset)

    def lines(self, address: str, project: str) -> list[str]:
        """The lines of the roadmap of `project` on its page."""
        page = measure(address, f"/projet/{project}")[0]
        self.assertTrue(part(page, ROADMAP),
                        f"the page of {project} shows no roadmap; it says « {page.get('text', '')[:400]} »")
        return rows(page, part_name(page, ROADMAP))

    def line(self, lines: list[str], title: str) -> str:
        found = [line for line in lines if line.startswith(title)]
        self.assertEqual(1, len(found), f"not one line of « {title} » in the roadmap: {lines}")
        return found[0]

    # --- Criterion 1 ------------------------------------------------------------

    def test_a_step_done_before_a_required_step_is_flagged_and_one_whose_required_steps_are_done_is_not(self):
        factory_roadmap = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "done"

[[step]]
id = "F2"
title = "Contrat d’entrée des tickets"
done_when = "le contrat d’entrée publié, et l’ancien code isolé"
order = 2
status = "done"
done_requires = ["F1"]

[[step]]
id = "F3"
title = "Flux de livraison jugé"
done_when = "un résultat jugé puis fusionné, et le cockpit relivré par ce flux"
order = 3
status = "done"
done_requires = ["F4"]

[[step]]
id = "F4"
title = "Cockpit relivré par le flux"
done_when = "le cockpit livré par le flux jugé"
order = 4
status = "in_progress"
"""
        saymyname_roadmap = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "in_progress"
"""
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        work = self.tree.work / f"knowledge-{self.declared + 1}"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, "2026-10-24T10:00:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: saymyname_roadmap}, "2026-10-14T09:30:00+02:00"),
        }
        lines = self.lines(self.serve(repos, []), FACTORY)

        early = self.line(lines, "Flux de livraison jugé")
        self.assertRegex(early, r"Incohérent : marquée terminée, «?\s*Cockpit relivré par le flux\s*»? n['’]est pas terminée",
                         "a step done whose required step « Cockpit relivré par le flux » is in progress is not flagged")
        # Not counted as acquired (the ticket: « et ne la compte pas comme
        # acquise »): the line does not say it done.
        self.assertNotIn("Terminé", early, "a step done whose required step is in progress is still shown done")
        kept = self.line(lines, "Contrat d’entrée des tickets")
        self.assertIn("Terminé", kept, "a step done whose required steps are all done is not shown done")
        self.assertNotRegex(kept, r"(?i)incohéren", "a step done whose required steps are all done is flagged")
        self.assertNotRegex(self.line(lines, "Isoler l’ancien code"), r"(?i)incohéren",
                            "a step done that requires nothing is flagged")

    def test_a_step_in_progress_waiting_on_a_required_step_is_not_flagged_for_its_ended_chantier_and_one_whose_required_steps_are_done_still_is(self):
        # What `done_requires` leaves of the flags of E (Testing Decision 3,
        # « projets/roadmaps/provenance »): a step in progress whose
        # required steps are all done is flagged as before when its chantier
        # is closed or its result merged; one still waiting on a required
        # step is in progress until that step is done, whatever its own
        # chantier.
        factory_roadmap = """\
[[step]]
id = "G1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "done"

[[step]]
id = "G2"
title = "Livraison parallèle"
done_when = "deux auteurs livrent sans conflit, sur le code isolé"
order = 2
status = "in_progress"
done_requires = ["G1"]

[[step]]
id = "G3"
title = "Notifications groupées"
done_when = "une notification par lot, sur le code isolé"
order = 3
status = "in_progress"
done_requires = ["G1"]

[[step]]
id = "G4"
title = "Flux de livraison jugé"
done_when = "un résultat jugé puis fusionné, et le cockpit relivré par ce flux"
order = 4
status = "in_progress"
done_requires = ["G5"]

[[step]]
id = "G5"
title = "Cockpit relivré par le flux"
done_when = "le cockpit livré par le flux jugé"
order = 5
status = "in_progress"
"""
        saymyname_roadmap = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "in_progress"
"""
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        work = self.tree.work / f"knowledge-{self.declared + 1}"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, "2026-10-24T10:00:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: saymyname_roadmap}, "2026-10-14T09:30:00+02:00"),
        }
        beads = [
            # G2: its chantier closed in the tracker.
            spec("spec-g2", "G2", "closed"),
            convoy("convoy-g2", "spec-g2", "closed"),
            # G3: the PRs of its tickets merged, its Spec and convoy still open.
            spec("spec-g3", "G3", "in_progress"),
            convoy("convoy-g3", "spec-g3", "open"),
            ticket("ticket-g3-a", "convoy-g3", "closed", **{"gc.merge_commit": "3" * 40}),
            ticket("ticket-g3-b", "convoy-g3", "closed", **{"gc.merge_commit": "4" * 40}),
            # G4: its chantier closed too, while G5 it requires is in progress.
            spec("spec-g4", "G4", "closed"),
            convoy("convoy-g4", "spec-g4", "closed"),
        ]
        lines = self.lines(self.serve(repos, beads), FACTORY)

        self.assertIn("Incohérent : marqué en cours, son chantier est fermé", self.line(lines, "Livraison parallèle"),
                      "a step in progress whose required steps are done and whose chantier is closed is not flagged")
        self.assertIn("Incohérent : marqué en cours, son résultat est fusionné",
                      self.line(lines, "Notifications groupées"),
                      "a step in progress whose required steps are done and whose PRs are merged is not flagged")
        waiting = self.line(lines, "Flux de livraison jugé")
        self.assertIn("En cours", waiting, "a step in progress waiting on a required step is not shown in progress")
        self.assertNotRegex(waiting, r"(?i)incohéren",
                            "a step in progress waiting on a required step is flagged for its chantier being closed")

    # --- Criterion 2 ------------------------------------------------------------

    def test_the_roadmap_the_factory_delivers_has_d01_in_progress_requiring_c01_suite_and_stays_valid(self):
        # docs/roadmap.toml of the tree under test, read by the command of
        # the Factory that validates a structured roadmap, run as a process.
        delivered = self.tree.repo / "docs" / "roadmap.toml"
        done = subprocess.run([sys.executable, str(self.tree.repo / "bin" / "project-roadmap"), "validate",
                               str(delivered)], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, done.returncode, f"the roadmap the Factory delivers is not valid: {done.stdout}{done.stderr}")
        self.assertEqual({"valid": True}, json.loads(done.stdout))
        steps = {step["id"]: step for step in tomllib.loads(delivered.read_text(encoding="utf-8"))["step"]}
        self.assertEqual("in_progress", steps["C01-suite"]["status"], "C01-suite is no longer in progress")
        self.assertEqual("in_progress", steps["D01"]["status"],
                         "D01 is not in progress while C01-suite, which its end condition requires, is not done")
        self.assertEqual(["C01-suite"], steps["D01"].get("done_requires"),
                         "D01 does not declare C01-suite among the steps its end condition requires")

    def test_the_roadmap_the_factory_delivers_shows_d01_in_progress(self):
        # The demonstration line: the same roadmap, on the page of the
        # Factory.
        # The roadmap the tree under test delivers, in its own repository.
        factory = descriptor_of(self.tree, FACTORY)
        lines = self.lines(self.serve({factory["knowledge_repo"]: self.tree.repo}, []), FACTORY)
        d01 = self.line(lines, "Planning Run D01 \"Delivery Workflow\"")
        self.assertIn("En cours", d01, "the roadmap the Factory delivers does not show D01 in progress")
        self.assertNotIn("Terminé", d01, "the roadmap the Factory delivers shows D01 done")


if __name__ == "__main__":
    unittest.main()
