#!/usr/bin/env python3
"""Criterion test 1 of R4 « Cadrage illisible d'un projet — la raison nomme
le bon fichier » (af-6weijp; Spec af-fgcw0d, decision 2 « en production,
une donnée sans source réelle s'affiche indisponible avec sa raison »,
Testing Decisions 1, 3 and 8): the page of a project whose knowledge
repository lacks both its release plan (cadrage de release) and its
roadmap says, for each, the file that lacks and its own reason.

The case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: no other case
sees it). The dataset holds the Factory and SayMyName as the tree declares
them, their knowledge repositories -- disposable Git repositories, the
Factory's holding its roadmap, SayMyName's holding a README only -- and an
empty tracker.

The page of SayMyName, /projet/saymyname, is read as a headless Chromium
renders it (home_destination.measure).

False if the reason of the release plan cites the file or the error of the
roadmap, if a zone does not name its own missing file, if the page says
« de le dépôt », or if a missing release plan or roadmap is shown as read.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part, part_name, rows  # noqa: E402


class ProjectsMissingFiles(unittest.TestCase):
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

    def test_a_missing_release_plan_and_a_missing_roadmap_each_name_their_own_file_and_reason(self):
        factory, saymyname = descriptor_of(self.tree, "agent-factory"), descriptor_of(self.tree, "saymyname")
        self.assertEqual("knowledge/roadmap.toml", saymyname["roadmap_path"],
                         "SayMyName no longer declares its roadmap there")
        work = self.tree.work / "knowledge-missing"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(work / "factory", {factory["roadmap_path"]: (
                '[[step]]\nid = "F1"\ntitle = "Isoler l’ancien code"\ndone_when = "plus aucune référence à '
                'l’ancien code"\norder = 1\nstatus = "in_progress"\n')}, "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {"README.md": "Le dépôt de connaissance de SayMyName.\n"},
                "2026-10-14T09:30:00+02:00"),
        }
        address = launch_declared(self.tree, "projects-missing-files", {
            "generated_at": "2026-10-22T12:00:00+02:00", "synthetic": True,
            "ui": {"id": "projects-missing-files", "page": "projects"},
            "projects": [factory, saymyname],
            "repos": {repo: str(path) for repo, path in repos.items()},
            "tracker": {"beads": {}}})
        page = measure(address, "/projet/saymyname")[0]

        release = part(page, "Prochaine release")
        self.assertTrue(release, f"the page has no « Prochaine release »; it says « {page.get('text', '')[:400]} »")
        self.assertIn("knowledge/release.toml", release, "the release does not name its missing release plan")
        self.assertRegex(release, r"(?i)aucun cadrage|absent|manque|introuvable|n.existe pas",
                         "the release does not say its release plan is missing")
        self.assertNotIn("knowledge/roadmap.toml", release, "the reason of the release plan cites the file of the roadmap")
        self.assertNotRegex(release, r"(?i)fatal|does not exist",
                            "the reason of the release plan is the error of another reading")
        for read in ("Cible révisable", "Acquis vérifiés", "Reste connu", "Fourchette", "Voir la preuve"):
            self.assertNotIn(read, release, f"a release plan the project does not have is shown as read: « {read} »")

        roadmap = part(page, "Roadmap")
        self.assertTrue(roadmap, f"the page has no « Roadmap »; it says « {page.get('text', '')[:400]} »")
        self.assertIn("knowledge/roadmap.toml", roadmap, "the roadmap does not name its missing file")
        self.assertRegex(roadmap, r"(?i)aucune roadmap|absente?|manque|introuvable|n.existe pas",
                         "the roadmap does not say its file is missing")
        self.assertNotIn("knowledge/release.toml", roadmap, "the roadmap cites the file of the release plan")
        self.assertEqual([], rows(page, part_name(page, "Roadmap")), "a missing roadmap is shown with steps, as read")

        self.assertNotIn("de le dépôt", page.get("text", ""), "the page says « de le dépôt »")


if __name__ == "__main__":
    unittest.main()
