#!/usr/bin/env python3
"""Criterion test 2 of E « Projet — release, estimation, roadmap Factory et
historique » (af-8rbceu; Spec af-fgcw0d, user stories 46 and 103, decision
« Projets et données » 10, Testing Decisions 1, 3 and 8): the roadmap of
the Factory, read from its structured source in the repository of the
Factory, apart from the roadmap of SayMyName, and the history of a project.

Each case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case sees
none of it). The dataset holds:

- `projects`: the descriptors of the projects, as the tree under test
  declares them (config/project-descriptors/agent-factory.json and
  saymyname.json): the knowledge repository of each and the path of its
  structured roadmap there;
- `repos`: where each knowledge repository is, a Git repository on this
  host -- a disposable one the case commits at a date it writes, or the
  tree under test itself for the roadmap the Factory delivers;
- `tracker`: the beads as the tracker holds them (`{"beads": {id: bead}}`),
  in the shapes the flow writes: a Spec carries the Roadmap Step it targets
  (`planning_run_target`), its convoy names it (`gc.spec_id`); a result of
  the D01 flow carries the records its convoy state writes (as the datasets
  result-merging, result-merged and result-abandoned carry them); a ticket
  of a convoy carries its graph (`gc.graph_digest`), and the commit its PR
  was merged as once merged (`gc.merge_commit`, as the closing of a
  delivered ticket writes it).

The page of each project, /projet/<project>, is read as a headless
Chromium renders it (home_destination.measure), and its historique in the
page served (the rows A1 reads the Outcome into).

False if the roadmap of the Factory shows content of SayMyName, an item
« en cours » whose chantier is closed, whose result is merged or whose PRs
are merged is not flagged, the structured source delivered still holds such an item, or an
abandon shows without its reason.
"""

from __future__ import annotations

import html
import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, fetch, measure  # noqa: E402
from project_destination import descriptor_of, knowledge_repository, launch_declared, part, part_name, rows  # noqa: E402

ROADMAP = "Roadmap"
FACTORY = "agent-factory"
SAYMYNAME = "saymyname"
AT = "2026-10-21T12:00:00+02:00"


def records(issue: str, judged: str = "1" * 40, merged: str = "2" * 40, reason: str = "") -> dict:
    """The metadata a convoy of the new flow carries once its result is
    `issue`: merging (the merge recorded, the convoy still open), merged,
    or abandoned for `reason`. The result `judged` is the commit merged as
    `merged`."""
    pack = "sha256:" + "a" * 64
    delivered = {"at": "2026-10-20T14:30:00+02:00", "commit": judged, "pack": pack, "protected": "0" * 40,
                 "version": "spec-end/v4"}
    answer = {"approver": "benjamin", "commit": judged, "pack": pack, "at": "2026-10-20T14:48:00+02:00",
              "words": "C’est ce que je voulais."}
    out = {"gc.flow.mark": "new-flow/v1", "gc.flow.delivered": delivered,
           "gc.flow.evidence_pack": {"at": delivered["at"], "commit": judged, "digest": pack, "path": "/nonexistent/pack",
                                     "conforming": True, "inadmissible": 0, "version": "evidence-pack/v1"}}
    if issue == "abandoned":
        out["gc.flow.judgement"] = {"verdicts": [], "answers": [{**answer, "response": "abandoned", "reason": reason}]}
        out["gc.flow.closed"] = {"how": "abandoned", "said": reason, "approver": "benjamin",
                                 "at": "2026-10-20T14:50:00+02:00"}
        return {key: json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
                for key, value in out.items()}
    out["gc.flow.judgement"] = {"verdicts": [], "answers": [{**answer, "response": "accepted"}]}
    out["gc.flow.promotion"] = {"at": "2026-10-20T14:50:00+02:00", "judged": judged, "merged": merged,
                                "protected": "0" * 40, "tip": judged}
    if issue == "merged":
        out["gc.flow.closed"] = {"how": "accepted", "said": answer["words"], "approver": "benjamin",
                                 "at": "2026-10-20T14:50:00+02:00"}
    return {key: json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            for key, value in out.items()}


def spec(bead_id: str, project: str, title: str, target: str, status: str = "closed", **metadata) -> dict:
    return {"id": bead_id, "title": title, "status": status, "issue_type": "task", "labels": [],
            "created_at": "2026-10-01T10:00:00+02:00",
            "metadata": {"gc.project_id": project, "spec_state": "APPROVED_SPEC", "planning_run_target": target,
                         **metadata}}


def convoy(bead_id: str, project: str, title: str, spec_id: str, status: str, **metadata) -> dict:
    return {"id": bead_id, "title": title, "status": status, "issue_type": "convoy",
            "labels": ["approved-ticket-graph"], "created_at": "2026-10-02T10:00:00+02:00",
            "metadata": {"gc.project_id": project, "gc.graph_digest": f"sha256:{bead_id}", "gc.spec_id": spec_id,
                         **metadata}}


def ticket(bead_id: str, convoy_id: str, status: str, **metadata) -> dict:
    """A ticket of the convoy `convoy_id`, as its graph was published."""
    return {"id": bead_id, "title": f"Ticket {bead_id}", "status": status, "issue_type": "task",
            "labels": ["approved-ticket-graph", "delivery-plane"], "created_at": "2026-10-02T10:00:00+02:00",
            "metadata": {"gc.graph_digest": f"sha256:{convoy_id}", "gc.dispatch_rig": FACTORY, **metadata}}


def text_of(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


class ProjectsRoadmap(unittest.TestCase):
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

    def serve(self, beads: list[dict], repos: dict[str, Path]) -> str:
        """The address of the cockpit launched on a dataset holding the
        Factory and SayMyName as the tree declares them, the knowledge
        repositories `repos` (by the name the descriptors give them) and
        the tracker `beads`."""
        type(self).declared += 1
        name = f"projects-roadmap-{self.declared}"
        dataset = {"generated_at": AT, "synthetic": True, "ui": {"id": name, "page": "projects"},
                   "projects": [descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)],
                   "repos": {repo: str(path) for repo, path in repos.items()},
                   "tracker": {"beads": {bead["id"]: bead for bead in beads}}}
        return launch_declared(self.tree, name, dataset)

    def repositories(self, factory_roadmap: str, factory_changed: str, saymyname_roadmap: str,
                     saymyname_changed: str) -> dict[str, Path]:
        """The knowledge repositories of the Factory and of SayMyName, each
        holding its own roadmap where its descriptor says, committed at the
        date given."""
        factory, saymyname = descriptor_of(self.tree, FACTORY), descriptor_of(self.tree, SAYMYNAME)
        work = self.tree.work / f"knowledge-{self.declared + 1}"
        return {
            factory["knowledge_repo"]: knowledge_repository(
                work / "factory", {factory["roadmap_path"]: factory_roadmap}, factory_changed),
            saymyname["knowledge_repo"]: knowledge_repository(
                work / "saymyname", {saymyname["roadmap_path"]: saymyname_roadmap}, saymyname_changed),
        }

    def roadmap(self, address: str, project: str) -> tuple[str, list[str]]:
        """The roadmap of `project` on its page, and its lines."""
        page = measure(address, f"/projet/{project}")[0]
        text = part(page, ROADMAP)
        self.assertTrue(text, f"the page of {project} shows no roadmap; it says « {page.get('text', '')[:400]} »")
        return text, rows(page, part_name(page, ROADMAP))

    def line(self, lines: list[str], title: str) -> str:
        found = [line for line in lines if line.startswith(title)]
        self.assertEqual(1, len(found), f"not one line of « {title} » in the roadmap: {lines}")
        return found[0]

    def historique(self, address: str, project: str) -> list[str]:
        """The rows of the historique of the page of `project`, each on one
        line."""
        code, _, body = fetch(f"{address}/projet/{project}")
        self.assertEqual(200, code)
        return [text_of(row) for row in re.findall(r'<div class="cockpit-historique-row"[^>]*>(.*?)</div>', body, re.S)]

    # --- Criterion 2 ------------------------------------------------------------

    def test_the_factory_roadmap_comes_from_its_repository_with_its_date_and_flags_in_progress_items_already_ended(self):
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
done_when = "deux auteurs livrent sans conflit"
order = 2
status = "in_progress"

[[step]]
id = "F3"
title = "Flux de livraison jugé"
done_when = "un résultat jugé puis fusionné"
order = 3
status = "in_progress"

[[step]]
id = "F4"
title = "Cockpit Panorama"
done_when = "le cockpit lit ses sources réelles"
order = 4
status = "in_progress"

[[step]]
id = "F5"
title = "Notifications groupées"
done_when = "une notification par lot"
order = 5
status = "in_progress"

[[step]]
id = "F6"
title = "Évaluation bornée"
done_when = "une évaluation en moins d’une heure"
order = 6
status = "todo"
"""
        saymyname_roadmap = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "done"

[[step]]
id = "S2"
title = "Profil public partagé"
done_when = "un profil ouvert par son lien"
order = 2
status = "in_progress"
"""
        beads = [
            # F2: its chantier closed in the tracker.
            spec("spec-f2", FACTORY, "Spec — Livraison parallèle", "F2"),
            convoy("convoy-f2", FACTORY, "Livraison parallèle", "spec-f2", "closed"),
            # F3: its result merged by the D01 flow, the convoy still open.
            spec("spec-f3", FACTORY, "Spec — Flux de livraison jugé", "F3"),
            convoy("convoy-f3", FACTORY, "Flux de livraison jugé", "spec-f3", "open", **records("merging")),
            # F4: its chantier under way -- one PR merged, one ticket at work.
            spec("spec-f4", FACTORY, "Spec — Cockpit Panorama", "F4", status="in_progress"),
            convoy("convoy-f4", FACTORY, "Cockpit Panorama", "spec-f4", "open"),
            ticket("ticket-f4-a", "convoy-f4", "closed", **{"gc.merge_commit": "4" * 40}),
            ticket("ticket-f4-b", "convoy-f4", "in_progress"),
            # F5: the PRs of its tickets merged, its Spec and convoy still open.
            spec("spec-f5", FACTORY, "Spec — Notifications groupées", "F5", status="in_progress"),
            convoy("convoy-f5", FACTORY, "Notifications groupées", "spec-f5", "open"),
            ticket("ticket-f5-a", "convoy-f5", "closed", **{"gc.merge_commit": "5" * 40}),
            ticket("ticket-f5-b", "convoy-f5", "closed", **{"gc.merge_commit": "6" * 40}),
        ]
        address = self.serve(beads, self.repositories(factory_roadmap, "2026-10-19T14:05:00+02:00",
                                                      saymyname_roadmap, "2026-10-14T09:30:00+02:00"))
        roadmap, lines = self.roadmap(address, FACTORY)
        for title in ("Isoler l’ancien code", "Livraison parallèle", "Flux de livraison jugé", "Cockpit Panorama",
                      "Notifications groupées", "Évaluation bornée"):
            self.line(lines, title)
        for title in ("Inscription par lien magique", "Profil public partagé"):
            self.assertNotIn(title, roadmap, "the roadmap of the Factory shows content of SayMyName")
        self.assertRegex(roadmap, r"19(/| )(10|octobre)(/| )2026",
                         "the roadmap of the Factory does not say the date of its last change")
        for title, ended in (("Livraison parallèle", "its chantier is closed"),
                             ("Flux de livraison jugé", "its result is merged"),
                             ("Notifications groupées", "the PRs of its chantier are merged")):
            self.assertRegex(self.line(lines, title), r"(?i)incohéren",
                             f"« {title} » is in progress while {ended}, and is not flagged")
        self.assertNotRegex(self.line(lines, "Cockpit Panorama"), r"(?i)incohéren",
                            "an item in progress whose chantier is under way is flagged")
        self.assertNotRegex(self.line(lines, "Isoler l’ancien code"), r"(?i)incohéren", "an item done is flagged")

    def test_the_saymyname_page_shows_its_own_roadmap_and_a_history_of_its_results_with_issue_and_reason(self):
        factory_roadmap = """\
[[step]]
id = "F1"
title = "Isoler l’ancien code"
done_when = "plus aucune référence à l’ancien code"
order = 1
status = "in_progress"
"""
        saymyname_roadmap = """\
[[step]]
id = "S1"
title = "Inscription par lien magique"
done_when = "un compte créé sans mot de passe"
order = 1
status = "done"

[[step]]
id = "S2"
title = "Profil public partagé"
done_when = "un profil ouvert par son lien"
order = 2
status = "in_progress"
"""
        reason = "Le besoin a disparu avec la nouvelle version du tableau."
        old_spec_reason = "Remplacée par une Spec plus courte."
        beads = [
            spec("spec-merged", SAYMYNAME, "Spec — Partage du profil", "S2"),
            convoy("convoy-merged", SAYMYNAME, "Partage du profil", "spec-merged", "closed",
                   **records("merged", judged="1" * 40, merged="2" * 40)),
            spec("spec-abandoned", SAYMYNAME, "Spec — Tableau des invitations", "S2"),
            convoy("convoy-abandoned", SAYMYNAME, "Tableau des invitations", "spec-abandoned", "closed",
                   **records("abandoned", reason=reason)),
            # A delivery of the flow before D01: nothing to judge it on.
            spec("spec-old", SAYMYNAME, "Spec — Page d’accueil", "S1"),
            convoy("convoy-old", SAYMYNAME, "Page d’accueil", "spec-old", "closed"),
            # A Spec closed without successor, its reason recorded.
            spec("spec-dropped", SAYMYNAME, "Messagerie interne", "S2",
                 **{"gc.chantier_abandon_reason": old_spec_reason}),
        ]
        address = self.serve(beads, self.repositories(factory_roadmap, "2026-10-19T14:05:00+02:00",
                                                      saymyname_roadmap, "2026-10-14T09:30:00+02:00"))
        roadmap, lines = self.roadmap(address, SAYMYNAME)
        for title in ("Inscription par lien magique", "Profil public partagé"):
            self.line(lines, title)
        self.assertNotIn("Isoler l’ancien code", roadmap, "the roadmap of SayMyName shows content of the Factory")
        history = self.historique(address, SAYMYNAME)

        def row(title: str) -> str:
            found = [r for r in history if r.startswith(title)]
            self.assertEqual(1, len(found), f"not one row of « {title} » in the historique: {history}")
            return found[0]

        merged = row("Partage du profil")
        self.assertIn("Fusionné", merged)
        self.assertIn("résultat jugé 1111111 → commit fusionné 2222222", merged,
                      "the merged result does not keep its proof")
        abandoned = row("Tableau des invitations")
        self.assertIn("Abandonné", abandoned)
        self.assertIn(reason, abandoned, "the abandoned result does not keep its reason")
        self.assertNotRegex(abandoned, r"Fusionné|commit fusionné", "an abandon lets one believe in a merge")
        old = row("Page d’accueil")
        self.assertRegex(old, r"(?i)livré", "the old delivery does not say its issue")
        self.assertNotRegex(old, r"Accepté|Fusionné", "an old delivery is said accepted or merged")
        self.assertIn(old_spec_reason, row("Messagerie interne"), "the Spec abandoned does not keep its reason")
        self.assertEqual([], [r for r in history if re.search(r"(?i)abandonn", r)
                              and not (reason in r or old_spec_reason in r)],
                         "an abandon shows without its reason")

    def test_the_roadmap_the_factory_delivers_holds_no_item_in_progress_whose_chantier_is_closed(self):
        # The roadmap the tree under test delivers, in its own repository.
        factory = descriptor_of(self.tree, FACTORY)
        delivered = tomllib.loads((self.tree.repo / factory["roadmap_path"]).read_text(encoding="utf-8"))["step"]
        # What the tracker of the Factory holds on 21/10/2026 for the steps
        # of its roadmap: the Specs that target them and their convoys.
        beads = [
            spec("af-oohx2x", FACTORY, "Spec — C01 : Cockpit V2 de l'usine", "C01"),
            convoy("af-f71cgu", FACTORY, "Graphe de tickets — C01 : Cockpit V2 de l'usine", "af-oohx2x", "closed"),
            spec("af-2zseit", FACTORY, "Spec — Reprise complète du cockpit C01 après D01", "C01-reprise"),
            convoy("af-pqfxmd", FACTORY, "Reprise complète du cockpit — Panorama, Runs et rituels", "af-2zseit",
                   "closed"),
            spec("af-wf4w5r", FACTORY, "Spec — D01 : Delivery Workflow de l'usine", "D01"),
            convoy("af-wtjo2x", FACTORY, "D01 : Delivery Workflow de l'usine", "af-wf4w5r", "closed"),
            spec("af-fgcw0d", FACTORY, "Spec — Cockpit : ce que main ne couvre pas encore", "C01-suite",
                 status="in_progress"),
            convoy("af-strhoy", FACTORY, "Cockpit — ce que main ne couvre pas encore", "af-fgcw0d", "open"),
        ]
        address = self.serve(beads, {factory["knowledge_repo"]: self.tree.repo})
        roadmap, lines = self.roadmap(address, FACTORY)
        for step in delivered:
            self.line(lines, step["title"])
        self.assertEqual([], [line for line in lines if re.search(r"(?i)incohéren", line)],
                         "the roadmap the Factory delivers holds an item in progress whose chantier is closed")


if __name__ == "__main__":
    unittest.main()
