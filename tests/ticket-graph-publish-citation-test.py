#!/usr/bin/env python3
"""The patch door on what a `repair` cites outside the text of the Spec
(T40, af-o6tu3z; Spec af-wf4w5r §2 and §11, Testing Decisions seam 2): an
anchor is read in the Validated Prototype the Spec names, a rule of the
repository in its file at the commit of the integration branch, a red
control on the convoy (bin/convoy-state show). Only the command lines are
exercised (bin/ticket-graph-publish, bin/convoy-state), on a fake tracker
state and a real repository: one test per refusal and per pass, each
refusal re-reading the tracker to prove nothing was written. The harness is
the one of tests/ticket-graph-publish-coverage-test.py."""

import copy
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"
sys.path.insert(0, str(ROOT / "tests" / "lib"))
from fixture_prototype import BRANCH, FROZEN_COMMIT, materialize  # noqa: E402

_loaded = importlib.util.spec_from_file_location(
    "ticket_graph_publish_coverage_harness", ROOT / "tests" / "ticket-graph-publish-coverage-test.py")
_coverage = importlib.util.module_from_spec(_loaded)
_loaded.loader.exec_module(_coverage)
Harness, FIXTURE_SPEC, digest_of = _coverage.Harness, _coverage.FIXTURE_SPEC, _coverage.digest_of

RULES = "STYLE.md"
RULE = "Toute page porte un pied de page."
CONTROL = "commande de régression (python3 -m unittest) : code 1 sur la branche d'intégration"

REPAIR = {
    "id": "R1", "kind": "repair", "title": "La liste retrouve son troisième élément",
    "blocked_by": [], "target_rigs": ["fixture_city"],
    "what_it_delivers": "La page affiche de nouveau les trois éléments.",
    "restores": {"kind": "spec_line", "ref": "La page d'accueil porte les ancres du Validated Prototype."},
    "demonstration_line": "Sur le produit lancé, la page (GET /) affiche de nouveau « Gamma ».",
    "acceptance_criteria": [{
        "entry_point": "GET / sur le produit lancé", "observable": "la région « liste » contient « Gamma »",
        "false_if": "« Gamma » manque",
    }],
}


class CitedSourceTest(Harness):
    """A convoy published from the fixture's graph, whose project repository
    holds a written rule on its protected branch; a patch without approval
    then adds one repair."""

    def setUp(self):
        super().setUp()
        self.git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        (self.repo_root / RULES).write_text(f"# Règles\n\n{RULE}\n", encoding="utf-8")
        self.git("add", RULES)
        self.git("-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "commit", "-q", "-m", "règles")
        self.seed(self.conformant())
        self.first = self.published()
        self.ids = self.first["ids"]
        self.convoy = self.ids["_convoy"]

    def git(self, *argv):
        proc = subprocess.run(("git", "-C", str(self.repo_root), *argv), env=self.git_env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def fold_delivered(self):
        """The Prototype Fold is merged: a repair of the interface, written
        at the end of the Spec, has nothing left to wait for."""
        self.state_tool("close-ticket", self.convoy, self.ids["T2"], "--commit", "a" * 40, "--file", str(GATE_REPORT))

    def fetch_prototype(self):
        """The prototype branch of the fixture, never merged, reaches the
        repository of the project at the commit the Spec names."""
        self.fold_delivered()
        remote = self.tmp / "prototype-remote.git"
        self.assertEqual(FROZEN_COMMIT, materialize(remote))
        self.git("fetch", "-q", str(remote), f"refs/heads/{BRANCH}:refs/heads/{BRANCH}")

    def propose(self, kind, ref, **changes):
        repair = {**copy.deepcopy(REPAIR), "restores": {"kind": kind, "ref": ref}, **changes}
        draft = self.conformant()
        draft["tickets"] = [repair]
        self.add_draft("draft-2", draft, approved=False, revises_digest=self.first["graph_digest"])

    def refused(self, *mentions):
        proc = self.assert_refused_and_nothing_written(lambda: self.patch(), "rien n'est écrit", *mentions)
        return "\n".join(self.refusal_lines(proc, "R1"))

    def published_repair(self):
        result = self.patched()
        self.assertEqual(["R1"], result["created"])
        return self.beads()[result["ids"]["R1"]]

    # --- an anchor ------------------------------------------------------------

    def test_refuses_a_repair_that_cites_an_anchor_no_state_of_the_validated_prototype_holds(self):
        self.fetch_prototype()
        self.propose("anchor", "pied-de-page")

        line = self.refused()

        self.assertIn("pied-de-page", line)
        self.assertIn("Validated Prototype", line)
        # The anchors the prototype does hold are named: the citation is corrected in one pass.
        self.assertIn("fixture-items", line)

    def test_publishes_a_repair_that_cites_an_anchor_of_the_validated_prototype(self):
        self.fetch_prototype()
        self.propose("anchor", "fixture-items")

        repair = self.published_repair()

        self.assertIn("anchor : fixture-items", repair["description"])

    def test_refuses_a_repair_that_cites_an_anchor_when_the_prototype_cannot_be_read(self):
        # The commit the Spec names is not in the repository of the project.
        self.fold_delivered()
        self.propose("anchor", "fixture-items")

        line = self.refused()

        self.assertIn("fixture-items", line)
        self.assertIn("illisibles", line)

    # --- a written rule of the repository ------------------------------------

    def test_refuses_a_repair_that_cites_a_rule_of_a_file_the_integration_branch_does_not_hold(self):
        self.propose("repo_rule", f"CONVENTIONS.md : {RULE}")

        line = self.refused()

        self.assertIn("CONVENTIONS.md", line)
        self.assertIn("n'existe pas", line)

    def test_refuses_a_repair_that_cites_a_rule_its_file_does_not_contain(self):
        self.propose("repo_rule", f"{RULES} : Toute page porte un fil d'Ariane.")

        line = self.refused()

        self.assertIn(RULES, line)
        self.assertIn("ne contient pas la citation", line)

    def test_refuses_a_rule_of_a_file_added_after_the_integration_branch_left_the_protected_branch(self):
        # The file exists in the work tree and on the protected branch, not
        # at the commit of the integration branch: that commit is what is read.
        (self.repo_root / "LATE.md").write_text(f"{RULE}\n", encoding="utf-8")
        self.git("add", "LATE.md")
        self.git("-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "commit", "-q", "-m", "plus tard")
        self.propose("repo_rule", f"LATE.md : {RULE}")

        line = self.refused()

        self.assertIn("LATE.md", line)
        self.assertIn("n'existe pas", line)

    def test_refuses_a_rule_that_names_no_file(self):
        self.propose("repo_rule", RULE)

        self.assertIn("sans nommer son fichier", self.refused())

    def test_publishes_a_repair_that_cites_a_rule_its_file_contains(self):
        self.propose("repo_rule", f"{RULES} : {RULE}")

        repair = self.published_repair()

        self.assertIn(f"repo_rule : {RULES} : {RULE}", repair["description"])

    # --- a red control -----------------------------------------------------------

    def test_refuses_a_repair_that_cites_a_red_control_the_convoy_does_not_carry(self):
        self.propose("red_check", CONTROL)

        line = self.refused()

        self.assertIn(CONTROL[:40], line)
        self.assertIn("contrôles rouges enregistrés : aucun", line)

    def test_refuses_a_repair_that_cites_another_red_control_than_the_one_recorded(self):
        self.record_red()
        self.propose("red_check", "le harnais échoue au chargement du jeu de données « contenu »")

        line = self.refused()

        self.assertIn("le harnais échoue", line)
        self.assertIn(CONTROL[:40], line)

    def test_publishes_a_repair_that_cites_the_red_control_recorded_on_the_convoy(self):
        self.record_red()
        self.assertEqual([CONTROL], [check["name"] for check in self.convoy_state(self.convoy)["convoy"]["red_checks"]])
        self.propose("red_check", CONTROL)

        repair = self.published_repair()

        self.assertIn(f"red_check : {CONTROL}", repair["description"])

    def record_red(self):
        tip = self.git("rev-parse", "HEAD")
        self.state_tool("record-integration-red", self.convoy, "--control", CONTROL, "--commit", tip,
                        "--integration", tip, "--protected", tip)

    # --- the Spec a batch exception is resolved against ---------------------------

    def test_an_approved_patch_writes_the_digest_of_the_amended_spec_on_the_convoy(self):
        # What `convoy-state resolve-owner-exception` compares to the digest
        # the Planning Exception of a batch was raised on.
        self.assertEqual(digest_of(FIXTURE_SPEC), self.convoy_state(self.convoy)["convoy"]["spec_digest"])
        amended = FIXTURE_SPEC.replace("## Testing Decisions", "La page porte un mode sombre.\n\n## Testing Decisions")
        self.assertNotEqual(FIXTURE_SPEC, amended)
        self.amend_spec(amended)
        draft = self.conformant()
        draft["tickets"].append(copy.deepcopy(REPAIR))
        self.add_draft("draft-2", draft, revises_digest=self.first["graph_digest"])

        self.patched()

        self.assertEqual(digest_of(amended), self.convoy_state(self.convoy)["convoy"]["spec_digest"])


if __name__ == "__main__":
    unittest.main()
