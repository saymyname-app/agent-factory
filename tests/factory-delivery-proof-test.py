#!/usr/bin/env python3
"""Rules of lib/factory_delivery_proof.py that the guard integration test does
not reach: which closed beads count as an undocumented delivery, and which do
not.

af-7700 was closed on 2026-09-16 via a raw `gc bd close`, bypassing
bin/deliver-close, with none of ADR-0016's six proof fields set
(gc.delivery_status, gc.work_outcome, gc.github_repo, gc.pr_number,
gc.pr_head, gc.merge_commit). This checks the detection logic in isolation,
using synthetic bead ids only (never a real af-* id from the live store).
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_delivery_proof import (  # noqa: E402
    assess_bead,
    find_incomplete,
    missing_proof_fields,
)

VALID_SHA_A = "a" * 40
VALID_SHA_B = "b" * 40


def full_proof(**overrides):
    value = {
        "gc.delivery_status": "merged",
        "gc.work_outcome": "shipped",
        "gc.github_repo": "example-org/example-repo",
        "gc.pr_number": 42,
        "gc.pr_head": VALID_SHA_A,
        "gc.merge_commit": VALID_SHA_B,
    }
    value.update(overrides)
    return value


def bead(**overrides):
    value = {
        "id": "zz-fixture1",
        "title": "Synthetic fixture delivery bead",
        "status": "closed",
        "labels": ["product-goal"],
        "metadata": full_proof(),
    }
    value.update(overrides)
    return value


class MissingProofFields(unittest.TestCase):
    def test_fully_documented_bead_is_missing_nothing(self):
        self.assertEqual([], missing_proof_fields(full_proof()))

    def test_raw_close_like_af7700_is_missing_all_six(self):
        """The exact af-7700 shape: closed via `gc bd close`, no fields at all."""
        self.assertEqual(
            [
                "gc.delivery_status",
                "gc.work_outcome",
                "gc.github_repo",
                "gc.pr_number",
                "gc.pr_head",
                "gc.merge_commit",
            ],
            missing_proof_fields({}),
        )

    def test_invalid_values_count_as_missing_not_merely_absent(self):
        self.assertIn("gc.github_repo", missing_proof_fields(full_proof(**{"gc.github_repo": "not-a-repo"})))
        self.assertIn("gc.pr_number", missing_proof_fields(full_proof(**{"gc.pr_number": "not-a-number"})))
        self.assertIn("gc.pr_number", missing_proof_fields(full_proof(**{"gc.pr_number": 0})))
        self.assertIn("gc.pr_head", missing_proof_fields(full_proof(**{"gc.pr_head": "abc123"})))
        self.assertIn("gc.merge_commit", missing_proof_fields(full_proof(**{"gc.merge_commit": ""})))
        self.assertIn("gc.delivery_status", missing_proof_fields(full_proof(**{"gc.delivery_status": "closed"})))
        self.assertIn("gc.work_outcome", missing_proof_fields(full_proof(**{"gc.work_outcome": "pass"})))

    def test_string_pr_number_is_accepted(self):
        self.assertEqual([], missing_proof_fields(full_proof(**{"gc.pr_number": "42"})))


class AssessBead(unittest.TestCase):
    def test_a_fully_documented_delivery_bead_is_not_flagged(self):
        self.assertIsNone(assess_bead(bead()))

    def test_an_open_bead_is_out_of_scope_regardless_of_metadata(self):
        self.assertIsNone(assess_bead(bead(status="open", metadata={})))

    def test_a_closed_bead_without_the_product_goal_label_is_out_of_scope(self):
        """Only beads carrying the label the rest of the Factory calls a
        delivery/goal outcome (lib/factory_cockpit.py) are in scope — a random
        closed task bead missing unrelated metadata is not this check's job."""
        self.assertIsNone(assess_bead(bead(labels=["task"], metadata={})))

    def test_a_deliberately_not_shipped_goal_is_never_flagged(self):
        for outcome in ("no-op", "cancelled", "dropped", "wont-fix", "descoped"):
            with self.subTest(outcome=outcome):
                self.assertIsNone(assess_bead(bead(metadata={"gc.work_outcome": outcome})))

    def test_af7700_shape_is_flagged_and_unverifiable_without_repo_or_pr(self):
        report = assess_bead(bead(id="zz-fixture-raw-close", metadata={}))
        self.assertIsNotNone(report)
        self.assertEqual("zz-fixture-raw-close", report["id"])
        self.assertEqual(6, len(report["missing"]))
        self.assertFalse(report["verifiable"])
        self.assertFalse(report["already_flagged"])

    def test_partial_proof_with_repo_and_pr_is_verifiable(self):
        """A bead that names a repo+PR but is missing the derived SHAs/outcome
        fields (e.g. an interrupted deliver-close, or a hand-edited bead) can
        still be independently checked against GitHub."""
        report = assess_bead(bead(metadata={
            "gc.github_repo": "example-org/example-repo",
            "gc.pr_number": 7,
        }))
        self.assertIsNotNone(report)
        self.assertTrue(report["verifiable"])
        self.assertEqual("example-org/example-repo", report["github_repo"])
        self.assertEqual("7", report["pr_number"])

    def test_an_invalid_repo_is_not_treated_as_verifiable(self):
        report = assess_bead(bead(metadata={"gc.github_repo": "not-a-repo", "gc.pr_number": 7}))
        self.assertIsNotNone(report)
        self.assertFalse(report["verifiable"])

    def test_already_flagged_beads_report_that_fact(self):
        report = assess_bead(bead(metadata={"gc.delivery_proof_flagged_at": "2026-09-16T12:00:00Z"}))
        self.assertIsNotNone(report)
        self.assertTrue(report["already_flagged"])


class FindIncomplete(unittest.TestCase):
    def test_finds_only_the_incomplete_ones_among_a_mixed_list(self):
        beads = [
            bead(id="zz-fixture-complete"),
            bead(id="zz-fixture-incomplete", metadata={}),
            bead(id="zz-fixture-cancelled", metadata={"gc.work_outcome": "cancelled"}),
            bead(id="zz-fixture-not-a-goal", labels=["task"], metadata={}),
        ]
        found = {report["id"] for report in find_incomplete(beads)}
        self.assertEqual({"zz-fixture-incomplete"}, found)


class Cli(unittest.TestCase):
    def run_cli(self, payload):
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_delivery_proof.py")],
            input=payload, capture_output=True, text=True,
        )
        return result

    def test_prints_one_tsv_line_per_incomplete_bead(self):
        payload = json.dumps([
            bead(id="zz-fixture-a", metadata={}),
            bead(id="zz-fixture-b"),
        ])
        result = self.run_cli(payload)
        self.assertEqual(0, result.returncode)
        lines = [line for line in result.stdout.splitlines() if line]
        self.assertEqual(1, len(lines))
        fields = lines[0].split("\x1f")
        self.assertEqual("zz-fixture-a", fields[0])
        self.assertIn("gc.delivery_status", fields[1])
        self.assertEqual("0", fields[4])

    def test_empty_list_prints_nothing_and_exits_zero(self):
        result = self.run_cli("[]")
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_invalid_json_fails_loudly_rather_than_silently(self):
        result = self.run_cli("not json")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unreadable", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
