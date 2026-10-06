#!/usr/bin/env python3
"""The publication door and the integration branch of a Spec (T18,
af-gmz9s1; Spec af-wf4w5r §4, Testing Decisions seam 2): publishing a convoy
that carries the new-flow mark opens the integration branch of its Spec in
the repository of the project, at the tip of the protected branch; a convoy
without the mark gets none. Only the command lines are exercised
(bin/ticket-graph-publish, bin/convoy-state), on a fake tracker state and a
throwaway repository; each refusal re-reads the tracker and the branches to
prove nothing was written. The harness is the one of
tests/ticket-graph-publish-coverage-test.py."""

import importlib.util
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_loaded = importlib.util.spec_from_file_location(
    "ticket_graph_publish_coverage_harness", ROOT / "tests" / "ticket-graph-publish-coverage-test.py")
_coverage = importlib.util.module_from_spec(_loaded)
_loaded.loader.exec_module(_coverage)
Harness, MARK = _coverage.Harness, _coverage.MARK

INTEGRATION = "integration/spec-1"
PROTECTED = "main"
EXIT_NOT_NEW_FLOW = 4

LEGACY_DRAFT = (
    "tickets:\n"
    "  - id: T1\n"
    "    title: First\n"
    "    blocked_by: []\n"
    "    target_rigs: [fixture_city]\n"
    "    what_it_delivers: does a thing\n"
    "    acceptance_criteria: [La chose est faite]\n"
)


class IntegrationBranchAtPublicationTest(Harness):
    def git(self, *args):
        proc = subprocess.run(
            ("git", "-C", str(self.repo_root), *args), text=True, capture_output=True,
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
        return proc.stdout.strip() if proc.returncode == 0 else None

    def branches(self):
        return sorted((self.git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads") or "").splitlines())

    def assert_refused_and_nothing_written(self, *mentions):
        before = (self.state_path.read_bytes(), self.branches())
        proc = self.door()
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        for mention in mentions:
            self.assertIn(mention, proc.stderr)
        self.assertEqual(before, (self.state_path.read_bytes(), self.branches()))
        self.assertEqual({"draft-1", "spec-1"}, set(self.beads()))

    def test_publishing_a_marked_convoy_opens_the_integration_branch_at_the_protected_tip(self):
        self.seed(self.conformant())
        tip = self.git("rev-parse", PROTECTED)
        self.assertIsNone(self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{INTEGRATION}"))

        result = self.published()
        self.assertEqual({"branch": INTEGRATION, "protected": PROTECTED, "base": tip, "created": True},
                         result["integration"])
        # The branch exists in the repository, left from the tip of the protected branch.
        self.assertEqual(tip, self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{INTEGRATION}"))
        self.assertEqual(tip, self.git("rev-parse", PROTECTED))
        convoy = self.convoy_state(result["ids"]["_convoy"])["convoy"]
        self.assertEqual(MARK, convoy["mark"])
        self.assertEqual((INTEGRATION, PROTECTED, tip),
                         tuple(convoy["integration"][name] for name in ("branch", "protected", "base")))

    def test_publishing_a_convoy_without_the_mark_opens_no_branch(self):
        self.seed(LEGACY_DRAFT)
        before = self.branches()

        result = self.published()
        self.assertNotIn("integration", result)
        self.assertEqual(before, self.branches())
        shown = self.convoy_state(result["ids"]["_convoy"], expect=EXIT_NOT_NEW_FLOW)
        self.assertIn("pas un convoi du nouveau flux", shown["message"])

    def test_a_convoy_without_the_mark_is_published_whatever_its_rigs_and_its_repository(self):
        # What the new flow asks of a marked convoy is asked of no other.
        shutil.rmtree(self.repo_root / ".git")
        self.seed(LEGACY_DRAFT.replace("[fixture_city]", "[rig_inconnu, autre_rig]"))

        self.assertNotIn("integration", self.published())

    def test_publishing_again_opens_nothing_more(self):
        self.seed(self.conformant())
        first = self.published()
        before = (self.state_path.read_bytes(), self.branches())

        second = self.published()
        self.assertEqual({**first["integration"], "created": False}, second["integration"])
        self.assertEqual(before, (self.state_path.read_bytes(), self.branches()))

    def test_refuses_a_marked_graph_whose_rig_has_no_project_file(self):
        draft = self.conformant()
        for ticket in draft["tickets"]:
            ticket["target_rigs"] = ["rig_inconnu"]
        self.seed(draft)

        self.assert_refused_and_nothing_written("branche d'intégration", "rig_inconnu", "rien n'est écrit")

    def test_refuses_a_marked_graph_that_targets_several_rigs(self):
        draft = self.conformant()
        draft["tickets"][-1]["target_rigs"] = ["acme"]
        self.seed(draft)

        self.assert_refused_and_nothing_written("branche d'intégration", "2 rigs", "acme, fixture_city")

    def test_refuses_a_marked_graph_whose_rig_has_no_repository(self):
        shutil.rmtree(self.repo_root / ".git")
        self.seed(self.conformant())

        self.assert_refused_and_nothing_written("branche d'intégration", "n'est pas un dépôt Git")

    def test_a_branch_that_could_not_be_opened_is_said_and_opened_by_a_rerun(self):
        self.seed(self.conformant())
        failing = self.tmp / "spec-integration"
        failing.write_text('#!/bin/sh\necho \'{"ok": false, "error": "refus : dépôt injoignable"}\'\nexit 1\n')
        failing.chmod(0o755)

        proc = self.door(env={"SPEC_INTEGRATION_BIN": str(failing)})
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("branche d'intégration", proc.stderr)
        self.assertIn("dépôt injoignable", proc.stderr)
        self.assertIn("relancer", proc.stderr)
        self.assertIsNone(self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{INTEGRATION}"))

        result = self.published()
        self.assertTrue(result["integration"]["created"])
        self.assertEqual(self.git("rev-parse", PROTECTED),
                         self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{INTEGRATION}"))


if __name__ == "__main__":
    unittest.main()
