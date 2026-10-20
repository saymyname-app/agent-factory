#!/usr/bin/env python3
"""Criterion test 2 of A1 « Vue d’ensemble — résultat réel lu depuis le
flux, sans faux blocage » (af-c662qx; Spec af-fgcw0d, user stories 8, 37,
40, 44, 47, 108, 117, 119, 123 and 136, Testing Decisions 1, 2 and 8): the
records of a result, produced by the public commands of D01 on a synthetic
city, read back by the cockpit at GET / and on the page of the project of
the chantier.

The records are produced as Testing Decisions 2 says: the reference driver
of the Fixture City walks one convoy to its Delivered Outcome (the harness
FixtureCityWalk of tests/convoy-stops-fixture-city-test.py, walked once and
restored for each case), then the case answers with bin/owner-answer
(verdict, record) and settles the answer with bin/outcome-promote (run).
The tracker those commands wrote is then the tracker of a cockpit the
launcher of the profile, bin/project-launch, starts: a dataset of the
profile that carries it under `tracker`, as the commands wrote it
(`{"beads": {id: bead}}`), the project of each chantier declared. This
isolated proof does not claim that a real convoy went through the new flow.

Each case reads the home page as a headless Chromium renders it
(home_destination.measure) -- the line of the project under « Projets »
and the result open in « Ce qui t’attend » -- and the page of the project,
GET /projet/<project>, whole (its details folded included: the details and
the history), and holds them to the records:

- a Delivered result on an open convoy is « À juger », not blocked; its
  closed tickets are no merge;
- an answer « accepté » without a merge is « Accepté », the merge pending;
- a merge recorded by bin/outcome-promote is « Fusionné », with the commit
  judged and the commit merged;
- an abandon is « Abandonné », nothing merged, its reason kept, and no
  anomaly;
- a record that cannot be read is « inconnu », never a known state;
- an issue its proofs contradict (closed as accepted, no proof of merge)
  is flagged as an inconsistency;
- a dossier written by the demonstration datasets (`gc.result_dossier`)
  is not a result the cockpit shows.

False if two screens contradict each other, an unreadable value becomes a
known state, or production still reads the dossier written by the
demonstration datasets.
"""

from __future__ import annotations

import html
import importlib.machinery
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import PROFILE, LaunchTree, fetch, git, measure, says  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: the test classes named at the top
# of a file are the ones collected there.
stops = load("convoy-stops-fixture-city-test.py")
# bin/owner-answer and bin/outcome-promote, the entry points of the profile
# that produce the records.
OWNER = ROOT / "bin" / "owner-answer"
PROMOTE = ROOT / "bin" / "outcome-promote"

APPROVER = "benjamin"
WORDS = "Accepté, c'est ce que je voulais."
REASON = "Le besoin a disparu avec la nouvelle version du tableau."
# A dossier as the demonstration datasets write it, on a bead of its own:
# never a result the cockpit shows.
DEMONSTRATION_TITLE = "Dossier écrit par un jeu de démonstration"
DEMONSTRATION = {
    "id": "demo-dossier", "title": DEMONSTRATION_TITLE, "status": "open", "issue_type": "task",
    "metadata": {"gc.result_dossier": json.dumps({
        "about": "Usine · Démonstration", "title": DEMONSTRATION_TITLE, "summary": "Écrit par un jeu de démonstration.",
        "resources": [{"label": "Ce qui a été livré", "detail": "Démonstration"}], "reports": []},
        ensure_ascii=False)},
    "labels": [], "tracks": [], "blocks": [], "description": "",
}


def page_text(address: str, path: str) -> str:
    """The whole text of the page at `path`, its folded details included,
    on one line, spaces collapsed."""
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())


class HomeD01Records(stops.FixtureCityWalk):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tree = LaunchTree()
        cls.served = 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        super().tearDownClass()

    def tearDown(self) -> None:
        self.tree.stop_all()

    # --- the records, by the commands of D01 --------------------------------

    def owner_ok(self, command: str, *args) -> dict:
        proc = self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", APPROVER, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def promote_ok(self) -> None:
        proc = self.tool(PROMOTE, "run", self.convoy, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def judged(self) -> dict:
        """The Delivered Outcome, every proposition of its dossier given a
        verdict by bin/owner-answer. Returns its record."""
        delivered = self.walk_to_delivered(inject="proposition")
        for ticket in self.shown()["tickets"]:
            for finding in ticket.get("findings") or []:
                if finding["classification"] == "proposal":
                    self.owner_ok("verdict", "--proposition", finding["id"], "--verdict", "sans suite", "--words", "Vu.")
        return delivered

    def accepted(self) -> dict:
        delivered = self.judged()
        self.owner_ok("record", "--response", "accepté", "--words", WORDS,
                      "--commit", delivered["commit"], "--pack-digest", delivered["pack"])
        return delivered

    def records(self) -> dict:
        """What the commands wrote in the tracker of the city."""
        return json.loads(self.tracker.read_text(encoding="utf-8"))

    # --- the cockpit, on those records ------------------------------------

    def serve(self, tracker: dict) -> str:
        """The address of the cockpit the launcher of the profile starts on
        a dataset that carries `tracker`, declared in the profile at a
        commit of its own, on top of the others."""
        type(self).served += 1
        name = f"d01-records-{self.served}"
        dataset = {"generated_at": "2026-10-12T12:00:00+02:00", "synthetic": True,
                   "ui": {"id": name, "page": "home"}, "tracker": tracker}
        repo = self.tree.repo
        path = Path("config") / "cockpit-datasets" / f"{name}.json"
        (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
        profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
        profile["launch"]["datasets"][name] = path.as_posix()
        (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git(repo, "add", "--all")
        git(repo, "commit", "--quiet", "--message", f"{name}: the records of the D01 commands")
        # The launcher reads the profile in the tree: it stays at this commit.
        return self.tree.launch(name, git(repo, "rev-parse", "HEAD"))

    def convoy_record(self, tracker: dict) -> dict:
        return tracker["beads"][self.convoy]

    def project_key(self, tracker: dict) -> str:
        key = self.convoy_record(tracker)["metadata"].get("gc.project_id")
        self.assertTrue(key, "the convoy of the city carries no project")
        return key

    def screens(self, tracker: dict) -> tuple[dict, str, str]:
        """The home page as rendered, the line of the project of the
        chantier under « Projets » on it, and the whole text of the page of
        that project."""
        address = self.serve(tracker)
        home = measure(address)[0]
        rows = [anchor["name"] for anchor in home["anchors"]
                if re.fullmatch(r"row-\d+", anchor["name"]) and "rows-1" in anchor["chain"]]
        self.assertEqual(1, len(rows), f"not one project under « Projets »: {[says(home, row) for row in rows]}")
        project = page_text(address, f"/projet/{self.project_key(tracker)}")
        return home, says(home, rows[0]), project

    def assert_same_stage(self, line: str, project: str, stage: str) -> None:
        """The home and the page of the project say the chantier at the
        same stage, `stage`, and neither says it blocked."""
        self.assertRegex(line, rf"· {re.escape(stage)}\b", f"the home does not say « {stage} »: « {line} »")
        self.assertIn(stage, project, "the page of the project does not say the stage the home says")
        for screen, text in (("home", line), ("project page", project)):
            self.assertNotRegex(text, r"(?i)bloqué", f"the {screen} says the chantier blocked")
            self.assertNotRegex(text, r"(?i)tickets? mergés?", f"the {screen} counts closed tickets as merged")

    # --- Criterion 2 ------------------------------------------------------------

    def test_a_delivered_result_on_an_open_convoy_is_to_judge_on_the_home_and_the_project_page(self):
        self.judged()
        tracker = self.records()
        self.assertNotEqual("closed", self.convoy_record(tracker)["status"], "the convoy is not open")
        # A dossier written as the demonstration datasets write it, beside.
        tracker["beads"][DEMONSTRATION["id"]] = DEMONSTRATION
        home, line, project = self.screens(tracker)
        self.assert_same_stage(line, project, "À juger")
        self.assertNotRegex(line + " " + project, r"Fusionn", "a closed ticket is shown merged")
        # The result to judge is the one open in « Ce qui t’attend », with
        # its bar; Essai and Avis cannot be used yet.
        self.assertIn("actions-possibles-1", [a["name"] for a in home["anchors"] if "panel-3" in a["chain"]],
                      "the result to judge is not open with its bar of actions")
        self.assertNotIn(DEMONSTRATION_TITLE, home["text"], "the home shows the dossier of a demonstration dataset")
        self.assertNotIn(DEMONSTRATION_TITLE, project, "the project shows the dossier of a demonstration dataset")
        self.assertEqual([], [c["name"] for c in home["controls"]
                              if (c["name"].startswith("Essai") or c["name"] == "Avis") and not c["disabled"]],
                         "Essai or Avis looks usable")

    def test_an_accepted_result_not_merged_says_accepted_and_the_merge_pending(self):
        self.accepted()
        tracker = self.records()
        home, line, project = self.screens(tracker)
        self.assert_same_stage(line, project, "Accepté")
        self.assertIn("Tu as accepté. La fusion est en attente.", says(home, "panel-3"))
        self.assertIn("La fusion est en attente", project)
        self.assertNotRegex(line + " " + project, r"Fusionné|Fusion confirmée", "an acceptance is shown as a merge")

    def test_a_merge_recorded_says_merged_with_the_commit_judged_and_the_commit_merged(self):
        self.accepted()
        self.promote_ok()
        tracker = self.records()
        promotion = json.loads(self.convoy_record(tracker)["metadata"]["gc.flow.promotion"])
        home, line, project = self.screens(tracker)
        self.assert_same_stage(line, project, "Fusionné")
        # The history of the project holds the proof: the commit judged and
        # the commit merged, as the record says them.
        self.assertIn(f"Fusion confirmée · résultat jugé {promotion['judged'][:7]} → commit fusionné "
                      f"{promotion['merged'][:7]}", project)

    def test_an_abandon_says_nothing_merged_keeps_its_reason_and_is_no_anomaly(self):
        self.judged()
        self.owner_ok("record", "--response", "abandonné", "--reason", REASON)
        self.promote_ok()
        tracker = self.records()
        home, line, project = self.screens(tracker)
        self.assert_same_stage(line, project, "Abandonné")
        self.assertIn("Rien n’a été fusionné", project)
        self.assertIn(REASON, project, "the abandon does not keep its reason")
        self.assertNotRegex(line + " " + project, r"Fusionné|Fusion confirmée|fusion est en",
                            "an abandon lets one believe in a merge")
        self.assertNotRegex(line + " " + project, r"(?i)incohéren", "an abandon without merge is shown as an anomaly")

    def test_a_record_that_cannot_be_read_is_unknown_on_every_screen(self):
        self.accepted()
        tracker = self.records()
        # The answer recorded, no longer readable.
        self.convoy_record(tracker)["metadata"]["gc.flow.judgement"] = "{illisible"
        home, line, project = self.screens(tracker)
        self.assert_same_stage(line, project, "Inconnu")
        for stage in ("À juger", "Accepté", "Fusionné", "Abandonné"):
            self.assertNotIn(stage, line, f"an unreadable record became « {stage} » on the home")

    def test_an_issue_its_proofs_contradict_is_flagged_on_every_screen(self):
        self.accepted()
        tracker = self.records()
        # Closed as accepted, with no proof of merge recorded.
        record = self.convoy_record(tracker)
        record["status"] = "closed"
        record["metadata"]["gc.flow.closed"] = json.dumps(
            {"how": "accepted", "said": WORDS, "approver": APPROVER, "at": "2026-10-12T11:00:00+02:00"})
        record["metadata"].pop("gc.flow.promotion", None)
        home, line, project = self.screens(tracker)
        self.assertRegex(line, r"(?i)incohéren", f"the home does not flag the inconsistency: « {line} »")
        self.assertRegex(project, r"(?i)incohéren", "the page of the project does not flag the inconsistency")
        self.assertNotRegex(line + " " + project, r"Fusionné|Fusion confirmée", "an issue without proof is shown merged")


if __name__ == "__main__":
    unittest.main()
