#!/usr/bin/env python3
"""Criterion test 1 of R19 « Revue de fin 96b3429f0dee F1.36 : Lignes projet
de l'accueil sur les mêmes sources que la page projet » (af-dmsp3y; Spec
af-fgcw0d, decision 2 « en production, une donnée sans source réelle
s'affiche indisponible avec sa raison », Testing Decisions 1, 3 and 8): the
line of a project in the zone « Projets » of the home page says the release
the page of that project reads, or says it unavailable with its reason --
never « Release non cadrée » beside a page that shows a release plan.

Each case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: no other case sees
it). The dataset is the cockpit as in production, outside any synthetic
page: the Factory and SayMyName as the tree declares them, their knowledge
repositories -- disposable Git repositories the case commits -- and a
tracker that carries no gc.project_card, the record only synthetic sets
write. The Factory's knowledge repository holds its roadmap and, in the
first case, its release plan (`release.toml` beside the roadmap), in the
second case none.

The page of the Factory, /projet/agent-factory, is read as a headless
Chromium renders it (home_destination.measure); the line of the Factory in
the zone « Projets » of the home page, GET /, over HTTP.

False if the line of the home page says « Release non cadrée » while the
page of the project shows a release plan, if it does not say the target
that page reads, or, the release plan missing, if it does not say its
release unavailable with the reason the page gives.
"""

from __future__ import annotations

import html
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, fetch, measure  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part  # noqa: E402

FACTORY = "agent-factory"
SAYMYNAME = "saymyname"
RELEASE = "Prochaine release"
UNSET = "Release non cadrée"
ROADMAP = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "in_progress"
"""
SAYMYNAME_ROADMAP = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "in_progress"
"""


class HomeProjectsRelease(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def serve(self, name: str, factory_files: dict[str, str]) -> str:
        """The address of the cockpit started on a dataset holding the
        Factory and SayMyName as the tree declares them, the Factory's
        knowledge repository holding `factory_files` (path -> text), and a
        tracker without any gc.project_card."""
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        work = self.tree.work / f"knowledge-{name}"
        repos = {
            factory["knowledge_repo"]: knowledge_repository(work / "factory", factory_files,
                                                            "2026-10-19T14:05:00+02:00"),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: SAYMYNAME_ROADMAP}, "2026-10-14T09:30:00+02:00"),
        }
        return launch_declared(self.tree, name, {
            "generated_at": "2026-10-22T12:00:00+02:00", "synthetic": True,
            "ui": {"id": name, "page": "projects"},
            "projects": [factory, saymyname],
            "repos": {repo: str(path) for repo, path in repos.items()},
            "tracker": {"beads": {}}})

    def page_release(self, address: str) -> str:
        """« Prochaine release » on the page of the Factory, on one line."""
        page = measure(address, f"/projet/{FACTORY}")[0]
        release = part(page, RELEASE)
        self.assertTrue(release, f"the page of the Factory has no « {RELEASE} »; it says « {page.get('text', '')[:400]} »")
        return release

    def home_line(self, address: str) -> str:
        """What the line of the Factory in the zone « Projets » of GET /
        says, on one line: the whole line that opens its page."""
        status, _, body = fetch(address + "/")
        self.assertEqual(200, status, "the home page is not served")
        zone = re.search(r'<section class="pn-panel pn-projects".*?</section>', body, re.DOTALL)
        self.assertTrue(zone, "the home page has no zone « Projets »")
        found = re.findall(r'<a href="/projet/%s">(.*?)</a>' % re.escape(FACTORY), zone.group(0), re.DOTALL)
        self.assertEqual(1, len(found), "the zone « Projets » of the home page holds not one line of the Factory")
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", found[0])).split())

    # --- Criterion 1 ------------------------------------------------------------

    def test_the_line_of_the_home_page_says_the_release_the_page_of_the_project_reads(self):
        factory = descriptor_of(self.tree, FACTORY)
        self.assertEqual("docs/roadmap.toml", factory["roadmap_path"], "the Factory no longer declares its roadmap there")
        target = "Livrer le cockpit Panorama par le flux D01 et le faire juger par Benjamin."
        release_plan = f"""\
target = "{target}"

[[gain]]
title = "Vue d’ensemble servie sur la VM"
proof = "PR #683 fusionnée, page servie."

[[remaining]]
title = "Essai et Avis sur le résultat exact"

[milestone]
title = "Premier résultat jugé dans le cockpit"
check = "Un dossier jugé depuis le panneau résultat."
"""
        address = self.serve("home-projects-release-read", {"docs/roadmap.toml": ROADMAP, "docs/release.toml": release_plan})

        release = self.page_release(address)
        self.assertIn(target, release, "the page of the Factory does not show the release plan of its repository")
        line = self.home_line(address)
        self.assertNotIn(UNSET, line, "the line of the home page says « Release non cadrée » while the page of the "
                                      f"project shows the release plan « {target} »: « {line} »")
        self.assertIn(target, line, f"the line of the home page does not say the release its page reads: « {line} »")

    def test_a_missing_release_plan_is_said_unavailable_on_the_line_with_the_reason_the_page_gives(self):
        address = self.serve("home-projects-release-missing", {"docs/roadmap.toml": ROADMAP})

        release = self.page_release(address)
        self.assertIn("docs/release.toml", release, "the page of the Factory does not name its missing release plan")
        line = self.home_line(address)
        self.assertNotIn(UNSET, line, f"a release plan missing is said « {UNSET} », not unavailable: « {line} »")
        self.assertRegex(line, r"(?i)indisponible", f"the line of the home page does not say its release unavailable: "
                                                    f"« {line} »")
        self.assertIn("docs/release.toml", line,
                      f"the line of the home page does not give the reason the page gives, its missing release plan: "
                      f"« {line} »")


if __name__ == "__main__":
    unittest.main()
