#!/usr/bin/env python3
"""T52 (af-ezqgma; Spec af-wf4w5r section 11, « Spec amendée et graphe
révisé ») on the convoy the reference driver walks to its Delivered Outcome:
the Planning Exception of a batch of returned findings is resolved by the
real doors, one after the other -- bin/spec-approve on the amended Spec,
bin/ticket-graph-publish bd-patch on the revised graph, then bin/owner-answer
resolve-exception -- and refused, nothing written, while one of them is
missing.

Nothing here writes `gc.spec_digest` or the approval of the Spec: the Spec of
the fixture is approved by bin/spec-approve (the driver), the convoy is
published by the real publication door, and this test only amends the text
of the Spec and hands in the revised Ticket Graph Draft, as a Planning Run
does. Harness: FixtureCityWalk of tests/convoy-stops-fixture-city-test.py.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "bin" / "owner-answer"
SPEC_APPROVE = ROOT / "bin" / "spec-approve"
PUBLISHER = ROOT / "bin" / "ticket-graph-publish"
FAKE_BD = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "bd-bead-mode"
EXIT_REFUSED = 1


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


walks = load("convoy-stops-fixture-city-test.py")

APPROVER = "benjamin"
SPEC, DRAFT, REVISED_DRAFT, RIG = "fx-spec", "fx-draft", "fx-draft-2", "fx-rig"
WISH = "Je veux aussi l'état du jeu de données en JSON à l'adresse /etat."
STORY_3 = ("3. As an intégrateur, I want l'état du jeu de données en JSON à l'adresse /etat, "
           "so that je puisse le surveiller par programme.\n")
WORDS = "La Spec amendée et le graphe révisé me conviennent."
NEW_TICKET = {
    "id": "T-etat", "kind": "vertical_slice", "title": "Servir l'état du jeu de données en JSON",
    "blocked_by": [], "target_rigs": [RIG],
    "what_it_delivers": "Le produit sert l'état du jeu de données en JSON à l'adresse /etat.",
    "demonstration_line": "Sur le produit lancé avec le jeu de données « content », GET /etat rend l'état « content ».",
    "user_stories": [3],
    "acceptance_criteria": [{
        "entry_point": "GET /etat sur le produit lancé avec le jeu de données « content »",
        "observable": "le champ etat vaut « content »",
        "false_if": "le champ manque, ou /etat ne répond pas"}]}


def digest_of(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class AmendedSpecResolvesTheBatchException(walks.FixtureCityWalk):
    def door(self, tool, *args):
        """One of the doors of a Planning Run, on the tracker of the city."""
        self.env.update({"BD_BIN": str(FAKE_BD), "TICKET_GRAPH_BD_STATE": str(self.tracker),
                         "TICKET_GRAPH_BD_WORKSPACE": str(self.workspace)})
        return self.tool(tool, *args)

    def door_ok(self, tool, *args):
        proc = self.door(tool, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def owner(self, command, *args):
        return self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", APPROVER, *args)

    def bead(self, bead_id):
        return json.loads(self.tracker.read_text(encoding="utf-8"))["beads"][bead_id]

    def exception(self):
        return self.shown()["convoy"]["judgement"]["answers"][-1]["exception"]

    def refused_to_resolve(self, *said):
        """`resolve-exception` refused, saying what is missing; nothing written."""
        tracker, shown = self.tracker.read_bytes(), self.shown()
        proc = self.owner("resolve-exception", "--words", WORDS)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout)["error"]
        self.assertTrue(error.startswith("refus : "), error)
        for fragment in said:
            self.assertIn(fragment, error)
        self.assertEqual(tracker, self.tracker.read_bytes())
        self.assertEqual(shown, self.shown())
        return error

    def approve_the_spec(self):
        return self.door(SPEC_APPROVE, "bd-approve", "--spec", SPEC, "--approved-by", APPROVER,
                         "--evidence", "« j'approuve la Spec amendée » (Benjamin, fixture)", "--project", self.project,
                         "--repo-root", self.repo, "--prototype-remote", self.repo)

    def patch_the_graph(self):
        return self.door(PUBLISHER, "bd-patch", REVISED_DRAFT, "--project", self.project, "--repo-root", self.repo,
                         "--author", "essai", "--reason", "Planning Exception du lot : la Spec est amendée")

    def test_the_batch_exception_is_resolved_once_the_amended_spec_is_approved_and_the_revised_graph_published(self):
        delivered = self.walk_to_delivered(inject="story-not-observed")
        self.resolved_through_the_doors(delivered)

    def resolved_through_the_doors(self, delivered):
        self.project = json.loads(self.profile.read_text(encoding="utf-8"))["project_id"]
        # The project the tickets target declares who answers for it.
        declared = Path(self.env["FACTORY_ROOT"]) / "config" / "projects" / f"{RIG}.toml"
        declared.write_text(f'human_approver = "{APPROVER}"\n' + declared.read_text(encoding="utf-8"), encoding="utf-8")
        # The convoy is published from the Spec bin/spec-approve approved.
        status = self.door_ok(SPEC_APPROVE, "bd-status", "--spec", SPEC)
        raised_on = self.shown()["convoy"]["spec_digest"]
        self.assertEqual(("APPROVED_SPEC", False, raised_on), (status["state"], status["void"], status["approved_digest"]))

        # Benjamin returns a wish the Spec does not require: the Planning Exception of the batch.
        findings = self.workspace / "owner-findings.json"
        findings.write_text(json.dumps({"findings": [{"text": WISH}]}), encoding="utf-8")
        answered = self.owner("record", "--response", "constats rendus", "--words", "Il manque quelque chose.",
                              "--commit", delivered["commit"], "--pack-digest", delivered["pack"], "--findings", findings)
        self.assertEqual(0, answered.returncode, answered.stdout + answered.stderr)
        self.assertEqual(raised_on, self.exception()["spec_digest"])
        self.assertNotIn("resolved", self.exception())

        # Before anything: refused, the Spec is not amended.
        self.refused_to_resolve("n'a pas été amendée")

        # The Spec is amended, not approved again: the new approval is missing.
        spec = self.bead(SPEC)["description"]
        amended = spec.replace("\n## Validated Prototype", STORY_3 + "\n## Validated Prototype", 1)
        self.assertNotEqual(spec, amended)
        self.door_ok_plain(str(FAKE_BD), "update", SPEC, "--description", amended)
        self.refused_to_resolve("n'est pas approuvée", "bin/spec-approve")
        # The patch door does not publish from a Spec that is not approved as it reads.
        self.hand_in_the_revised_draft()
        tracker = self.tracker.read_bytes()
        early = self.patch_the_graph()
        self.assertNotEqual(0, early.returncode, early.stdout)
        self.assertEqual(tracker, self.tracker.read_bytes())

        # The amended Spec is approved by the real door; the graph is not revised yet.
        approved = self.approve_the_spec()
        self.assertEqual(0, approved.returncode, approved.stdout + approved.stderr)
        approved = json.loads(approved.stdout)
        self.assertEqual((digest_of(amended), True), (approved["digest"], approved["amended"]))
        self.assertEqual(raised_on, self.shown()["convoy"]["spec_digest"])
        self.refused_to_resolve("bin/ticket-graph-publish bd-patch", "n'est pas publié", approved["digest"])

        # The revised graph is published from it by the real patch door.
        patched = self.patch_the_graph()
        self.assertEqual(0, patched.returncode, patched.stdout + patched.stderr)
        self.assertEqual(approved["digest"], self.shown()["convoy"]["spec_digest"])

        # The Planning Exception is resolved, with the words of the approver.
        resolved = self.owner("resolve-exception", "--words", WORDS)
        self.assertEqual(0, resolved.returncode, resolved.stdout + resolved.stderr)
        exception = self.exception()
        self.assertEqual((APPROVER, WORDS), (exception["resolved"]["approver"], exception["resolved"]["words"]))
        self.assertEqual(raised_on, exception["spec_digest"])

    def door_ok_plain(self, *argv):
        proc = self.door(*argv)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def hand_in_the_revised_draft(self):
        """What the Planning Run leaves after the amendment: the slice of
        the new user story, approved by Benjamin -- a patch does not take up
        the delivered tickets again."""
        draft = yaml.safe_load(self.bead(DRAFT)["description"])
        draft["tickets"] = [NEW_TICKET]
        text = yaml.safe_dump(draft, allow_unicode=True, sort_keys=False)
        state = json.loads(self.tracker.read_text(encoding="utf-8"))
        state["beads"][REVISED_DRAFT] = {
            "id": REVISED_DRAFT, "title": "Draft", "description": text, "status": "open", "labels": [], "metadata": {
                **{key: value for key, value in self.bead(DRAFT)["metadata"].items()
                   if key in ("spec_id", "display_title", "language")},
                "revises_digest": self.bead(self.convoy)["metadata"]["gc.graph_digest"],
                "approved_by": APPROVER, "approved_evidence": "« j'approuve le graphe révisé » (Benjamin, fixture)",
                "approved_digest": digest_of(text)}}
        self.tracker.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
