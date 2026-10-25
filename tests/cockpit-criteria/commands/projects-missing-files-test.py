#!/usr/bin/env python3
"""Criterion test 1 of R4 « Cadrage illisible d'un projet — la raison nomme
le bon fichier » (af-6weijp; Spec af-fgcw0d, decision 2 « en production,
une donnée sans source réelle s'affiche indisponible avec sa raison »,
Testing Decisions 1, 3 and 8): the page of a project whose knowledge
repository lacks its release plan (cadrage) and its roadmap says, for each,
the file that lacks and its own reason.

Each case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case sees
none of it). The dataset holds the Factory and SayMyName as the tree
declares them, their knowledge repositories -- disposable Git repositories,
the Factory's holding its roadmap, SayMyName's holding neither roadmap nor,
in the first case, release plan -- and an empty tracker.

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

FACTORY = "agent-factory"
SAYMYNAME = "saymyname"
AT = "2026-10-22T12:00:00+02:00"
RELEASE = "Prochaine release"
ROADMAP = "Roadmap"
# The two files of the knowledge repository of SayMyName, where its
# descriptor (knowledge/roadmap.toml) and the release plan beside it say.
ROADMAP_FILE = "knowledge/roadmap.toml"
RELEASE_FILE = "knowledge/release.toml"
# The parts of a release plan read: shown, they would present it as read.
READ_RELEASE = ("Cible révisable", "Acquis vérifiés", "Reste connu", "Fourchette", "Voir la preuve")

FACTORY_ROADMAP = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "in_progress"
"""


class ProjectsMissingFiles(unittest.TestCase):
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

    def saymyname_page(self, saymyname_files: dict[str, str]) -> dict:
        """The page of SayMyName, measured, from the cockpit launched on a
        dataset whose knowledge repository of SayMyName holds only
        `saymyname_files`, the Factory's its roadmap, and an empty
        tracker."""
        type(self).declared += 1
        name = f"projects-missing-files-{self.declared}"
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        self.assertEqual(ROADMAP_FILE, saymyname["roadmap_path"], "SayMyName no longer declares its roadmap there")
        work = self.tree.work / f"knowledge-missing-{self.declared}"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: FACTORY_ROADMAP}, "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", saymyname_files, "2026-10-14T09:30:00+02:00"),
        }
        dataset = {"generated_at": AT, "synthetic": True, "ui": {"id": name, "page": "projects"},
                   "projects": [factory, saymyname],
                   "repos": {repo: str(path) for repo, path in repos.items()},
                   "tracker": {"beads": {}}}
        address = launch_declared(self.tree, name, dataset)
        return measure(address, f"/projet/{SAYMYNAME}")[0]

    def zone(self, page: dict, heading: str) -> str:
        text = part(page, heading)
        self.assertTrue(text, f"the page of SayMyName has no « {heading} »; it says « {page.get('text', '')[:400]} »")
        return text

    def assert_roadmap_names_its_own_missing_file(self, page: dict) -> None:
        roadmap = self.zone(page, ROADMAP)
        self.assertIn(ROADMAP_FILE, roadmap, "the roadmap does not name its missing file")
        self.assertRegex(roadmap, r"(?i)aucune roadmap|absente?|manque|introuvable|n.existe pas",
                         "the roadmap does not say its file is missing")
        self.assertNotIn(RELEASE_FILE, roadmap, "the roadmap cites the file of the release plan")
        self.assertEqual([], rows(page, part_name(page, ROADMAP)), "a missing roadmap is shown with steps, as read")

    def assert_release_not_shown_as_read(self, release: str) -> None:
        for read in READ_RELEASE:
            self.assertNotIn(read, release, f"a release plan the project does not have is shown as read: « {read} »")

    # --- Criterion 1 ------------------------------------------------------------

    def test_a_missing_release_plan_and_a_missing_roadmap_each_name_their_own_file_and_reason(self):
        page = self.saymyname_page({"README.md": "Le dépôt de connaissance de SayMyName.\n"})
        release = self.zone(page, RELEASE)
        self.assertIn(RELEASE_FILE, release, "the release does not name its missing release plan")
        self.assertRegex(release, r"(?i)aucun cadrage|absent|manque|introuvable|n.existe pas",
                         "the release does not say its release plan is missing")
        self.assertNotIn(ROADMAP_FILE, release, "the reason of the release plan cites the file of the roadmap")
        self.assertNotRegex(release, r"(?i)fatal|does not exist",
                            "the reason of the release plan is the error of another reading")
        self.assert_release_not_shown_as_read(release)
        self.assert_roadmap_names_its_own_missing_file(page)
        self.assertNotIn("de le dépôt", page.get("text", ""), "the page says « de le dépôt »")

    def test_an_unreadable_release_plan_gives_its_own_error_while_the_roadmap_is_missing(self):
        page = self.saymyname_page({RELEASE_FILE: "target = \n"})
        release = self.zone(page, RELEASE)
        self.assertIn(RELEASE_FILE, release, "the release does not name its unreadable release plan")
        self.assertRegex(release, r"(?i)illisible|ne se lit pas", "the release does not say its release plan is unreadable")
        self.assertNotIn(ROADMAP_FILE, release, "the reason of the release plan cites the file of the roadmap")
        self.assertNotRegex(release, r"(?i)fatal|does not exist",
                            "the reason of the release plan is the error of the roadmap")
        self.assertNotRegex(release, r"\bde le\b", "the reason of the release plan says « de le »")
        self.assert_release_not_shown_as_read(release)
        self.assert_roadmap_names_its_own_missing_file(page)


if __name__ == "__main__":
    unittest.main()
