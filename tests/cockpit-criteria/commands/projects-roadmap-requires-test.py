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
shown « Terminé » without reserve, if a step done whose required steps are
all done is flagged, or if the roadmap the Factory delivers does not show
D01 in progress.
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
        kept = self.line(lines, "Contrat d’entrée des tickets")
        self.assertIn("Terminé", kept, "a step done whose required steps are all done is not shown done")
        self.assertNotRegex(kept, r"(?i)incohéren", "a step done whose required steps are all done is flagged")
        self.assertNotRegex(self.line(lines, "Isoler l’ancien code"), r"(?i)incohéren",
                            "a step done that requires nothing is flagged")

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
