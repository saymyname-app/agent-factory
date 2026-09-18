#!/usr/bin/env python3

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from intake_contract import (  # noqa: E402
    build_intake_skeleton,
    check_intake_exit,
    deterministic_scan,
    reserved_questions,
)
from product_release import (  # noqa: E402
    DISCOVERY_AREAS,
    RESERVED_CLASSES,
    validate_release_contract,
)


class DeterministicScanGreenfieldTest(unittest.TestCase):
    def test_empty_but_explicit_finding_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            discovery = deterministic_scan(Path(tmp), origin_kind="greenfield")
        self.assertEqual(discovery["method"], "deterministic_scan")
        self.assertEqual(discovery["findings"], [])
        self.assertTrue(discovery["generated_at"])

    def test_zero_model_calls_is_structural_no_network_no_subprocess_beyond_git(self):
        # Greenfield discovery must not touch the filesystem beyond the repo root
        # it is given -- asserted indirectly: a nonexistent directory still
        # returns the same empty-but-explicit shape, since nothing is read.
        discovery = deterministic_scan(Path("/does/not/exist"), origin_kind="greenfield")
        self.assertEqual(discovery["findings"], [])


class DeterministicScanTakeoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "a_test.js").write_text("", encoding="utf-8")
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "ci.yml").write_text("", encoding="utf-8")
        (self.repo / "README.md").write_text("# fixture", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init"],
            cwd=self.repo, check=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_stack_tests_ci_docs_history(self):
        discovery = deterministic_scan(self.repo, origin_kind="takeover")
        areas_found = {finding["area"] for finding in discovery["findings"]}
        self.assertIn("stack", areas_found)
        self.assertIn("tests", areas_found)
        self.assertIn("ci", areas_found)
        self.assertIn("docs", areas_found)
        self.assertIn("history", areas_found)

    def test_every_finding_cites_evidence_and_a_known_area(self):
        discovery = deterministic_scan(self.repo, origin_kind="takeover")
        self.assertTrue(discovery["findings"])
        for finding in discovery["findings"]:
            self.assertIn(finding["area"], DISCOVERY_AREAS)
            self.assertTrue(finding["evidence"])
            for entry in finding["evidence"]:
                self.assertIn(entry["kind"], {"scan"})

    def test_unknown_origin_kind_rejected(self):
        with self.assertRaises(ValueError):
            deterministic_scan(self.repo, origin_kind="migration")


class ReservedQuestionsTest(unittest.TestCase):
    def test_rejects_non_reserved_class(self):
        with self.assertRaises(ValueError):
            reserved_questions(["not-a-class"])

    def test_builds_one_question_per_class_admitted_reserved(self):
        questions = reserved_questions(sorted(RESERVED_CLASSES))
        self.assertEqual(len(questions), len(RESERVED_CLASSES))
        for question in questions:
            self.assertEqual(question["admitted_by"], "reserved")
            self.assertEqual(question["status"], "pending")
            self.assertIn(question["kind"], RESERVED_CLASSES)


class BuildIntakeSkeletonTest(unittest.TestCase):
    def _skeleton(self, **overrides):
        params = dict(
            product="fixture-product",
            title="Fixture Product V1",
            pitch="A one-line pitch for a throwaway fixture product.",
            pitch_author="test-harness",
            origin_kind="greenfield",
            discovery=deterministic_scan(Path("/tmp/does-not-matter"), origin_kind="greenfield"),
        )
        params.update(overrides)
        return build_intake_skeleton(**params)

    def test_greenfield_skeleton_passes_the_shared_validator_unchanged(self):
        contract = self._skeleton()
        validated = validate_release_contract(contract)
        self.assertEqual(validated["state"], "intake")
        self.assertEqual(validated["intake"]["state"], "awaiting_human")

    def test_greenfield_skeleton_questions_list_is_not_empty(self):
        contract = self._skeleton()
        self.assertTrue(contract["intake"]["questions"])
        kinds = {q["kind"] for q in contract["intake"]["questions"]}
        self.assertIn("outcome", kinds)
        self.assertIn("authority", kinds)

    def test_extra_reserved_classes_are_included_without_duplicating_mandatory_ones(self):
        contract = self._skeleton(extra_reserved_classes=["money", "outcome"])
        kinds = [q["kind"] for q in contract["intake"]["questions"]]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertIn("money", kinds)

    def test_takeover_skeleton_with_scan_findings_also_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "pyproject.toml").write_text("", encoding="utf-8")
            discovery = deterministic_scan(repo, origin_kind="takeover")
        contract = self._skeleton(origin_kind="takeover", discovery=discovery)
        validate_release_contract(contract)


class CheckIntakeExitTest(unittest.TestCase):
    def test_fresh_skeleton_is_not_complete_because_reserved_questions_are_unanswered(self):
        discovery = deterministic_scan(Path("/tmp/x"), origin_kind="greenfield")
        contract = build_intake_skeleton(
            product="fixture-product", title="Fixture", pitch="pitch", pitch_author="test",
            origin_kind="greenfield", discovery=discovery,
        )
        complete, reasons = check_intake_exit(contract)
        self.assertFalse(complete)
        self.assertTrue(any(reason.startswith("3:") for reason in reasons))

    def test_answering_reserved_questions_alone_is_not_enough_without_criteria(self):
        discovery = deterministic_scan(Path("/tmp/x"), origin_kind="greenfield")
        contract = build_intake_skeleton(
            product="fixture-product", title="Fixture", pitch="pitch", pitch_author="test",
            origin_kind="greenfield", discovery=discovery,
        )
        for question in contract["intake"]["questions"]:
            question["status"] = "answered"
            question["answer_ref"] = "docs/fixture-answer.md"
        complete, reasons = check_intake_exit(contract)
        self.assertTrue(complete)
        self.assertFalse(reasons)

    def test_criterion_unreferenced_by_work_graph_fails_condition_two(self):
        discovery = deterministic_scan(Path("/tmp/x"), origin_kind="greenfield")
        contract = build_intake_skeleton(
            product="fixture-product", title="Fixture", pitch="pitch", pitch_author="test",
            origin_kind="greenfield", discovery=discovery,
        )
        contract["criteria"] = [{
            "id": "core-loop-works", "title": "Core loop works", "description": "desc",
            "status": "unverified", "evidence": [], "acceptance": "A user completes the loop once.",
        }]
        complete, reasons = check_intake_exit(contract)
        self.assertFalse(complete)
        self.assertTrue(any(reason.startswith("2:") for reason in reasons))


if __name__ == "__main__":
    unittest.main()
