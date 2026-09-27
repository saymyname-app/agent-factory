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
    assess_claimed_shipped_bead,
    delivery_readiness,
    find_claimed_shipped,
    find_incomplete,
    is_claimed_shipped_bead,
    missing_proof_fields,
    missing_structural_pr_proof,
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


def structural_proof(**overrides):
    value = {
        **full_proof(),
        "gc.pr_url": "https://github.com/example-org/example-repo/pull/42",
        "pr_number": 42,
        "merge_result": "merged",
        "merged_sha": VALID_SHA_B,
        "merged_target": "main",
        "gc.required_ci_workflow": "Factory CI",
        "gc.ci_run_id": 35882143816,
        "gc.ci_head_sha": VALID_SHA_A,
        "gc.ci_conclusion": "success",
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
        delivery/goal outcome (see bin/factory-delivery-guard) are in scope — a random
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


class StructuralDeliveryReadiness(unittest.TestCase):
    def graph_bead(self, ticket, metadata=None, status="closed"):
        return {
            "id": f"zz-{ticket.lower()}",
            "status": status,
            "metadata": {
                "gc.ticket_id": ticket,
                "gc.plane": "delivery",
                "gc.graph_digest": "sha256:" + "5" * 64,
                **(metadata or {}),
            },
        }

    def test_p01_closed_under_review_is_not_delivery_complete(self):
        result = delivery_readiness(self.graph_bead("P01", {
            "gc.pr_url": "https://github.com/example-org/example-repo/pull/197",
        }))
        self.assertFalse(result["ready"])
        self.assertTrue(result["pr_backed"])
        self.assertIn("merge_result", result["missing"])
        self.assertIn("gc.ci_run_id", result["missing"])

    def test_p02_red_ci_and_head_mismatch_are_rejected(self):
        red = delivery_readiness(self.graph_bead("P02", structural_proof(**{
            "gc.ci_conclusion": "failure",
        })))
        self.assertFalse(red["ready"])
        self.assertIn("gc.ci_conclusion", red["missing"])

        mismatch = delivery_readiness(self.graph_bead("P02", structural_proof(**{
            "gc.ci_head_sha": "c" * 40,
        })))
        self.assertFalse(mismatch["ready"])
        self.assertIn("gc.ci_head_sha!=gc.pr_head", mismatch["missing"])

    def test_exact_green_ci_and_merge_proof_release_delivery(self):
        self.assertEqual([], missing_structural_pr_proof(structural_proof()))
        result = delivery_readiness(self.graph_bead("P02", structural_proof()))
        self.assertTrue(result["ready"])
        self.assertEqual("merged-ci-proven", result["reason"])

    def test_explicit_non_delivery_and_generic_closed_semantics_are_preserved(self):
        for outcome in ("no-op", "blocked", "abandoned"):
            with self.subTest(outcome=outcome):
                result = delivery_readiness(self.graph_bead("P02", {
                    "gc.work_outcome": outcome,
                }))
                self.assertTrue(result["ready"])
                self.assertFalse(result["pr_backed"])
        self.assertTrue(delivery_readiness({"id": "zz-generic", "status": "closed"})["ready"])


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


class ClaimedShippedBead(unittest.TestCase):
    """The adjacent gap (af-1xz1g): af-x45xw was closed gc.outcome=pass with
    its own gc.pr_url on 2026-09-18 while that PR was still OPEN -- and it
    carried no `product-goal` label, so assess_bead above never saw it."""

    def af_x45xw_shape(self, **overrides):
        value = {
            "id": "zz-fixture-af-x45xw",
            "title": "Closed pass while its own PR was still open",
            "status": "closed",
            "labels": [],
            "metadata": {
                "gc.outcome": "pass",
                "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
            },
        }
        value.update(overrides)
        return value

    def test_af_x45xw_shape_is_in_scope_with_no_label_at_all(self):
        self.assertTrue(is_claimed_shipped_bead(self.af_x45xw_shape()))

    def test_work_outcome_shipped_is_also_in_scope(self):
        bead = self.af_x45xw_shape(metadata={
            "gc.work_outcome": "shipped",
            "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
        })
        self.assertTrue(is_claimed_shipped_bead(bead))

    def test_an_open_bead_is_out_of_scope(self):
        self.assertFalse(is_claimed_shipped_bead(self.af_x45xw_shape(status="open")))

    def test_no_pr_url_is_out_of_scope(self):
        self.assertFalse(is_claimed_shipped_bead(self.af_x45xw_shape(metadata={"gc.outcome": "pass"})))

    def test_a_non_shipped_outcome_is_out_of_scope(self):
        bead = self.af_x45xw_shape(metadata={
            "gc.outcome": "fail",
            "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
        })
        self.assertFalse(is_claimed_shipped_bead(bead))

    def test_a_malformed_pr_url_is_out_of_scope(self):
        bead = self.af_x45xw_shape(metadata={
            "gc.outcome": "pass",
            "gc.pr_url": "not-a-github-pr-url",
        })
        self.assertFalse(is_claimed_shipped_bead(bead))

    def test_an_already_fully_proven_bead_has_nothing_new_to_verify(self):
        """If the six ADR-0016 fields are already present and valid, either
        deliver-close wrote them or assess_bead's own backfill already did --
        there is nothing left for this sibling check to verify."""
        bead = self.af_x45xw_shape(metadata={
            **full_proof(),
            "gc.outcome": "pass",
            "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
        })
        self.assertFalse(is_claimed_shipped_bead(bead))

    def test_assess_parses_repo_and_pr_number_from_the_url(self):
        report = assess_claimed_shipped_bead(self.af_x45xw_shape())
        self.assertIsNotNone(report)
        self.assertEqual("zz-fixture-af-x45xw", report["id"])
        self.assertEqual("example-org/example-repo", report["github_repo"])
        self.assertEqual("114", report["pr_number"])
        self.assertFalse(report["already_flagged"])

    def test_assess_returns_none_out_of_scope(self):
        self.assertIsNone(assess_claimed_shipped_bead(self.af_x45xw_shape(status="open")))

    def test_already_flagged_is_reported(self):
        bead = self.af_x45xw_shape(metadata={
            "gc.outcome": "pass",
            "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
            "gc.delivery_proof_flagged_at": "2026-09-18T12:00:00Z",
        })
        report = assess_claimed_shipped_bead(bead)
        self.assertIsNotNone(report)
        self.assertTrue(report["already_flagged"])

    def test_find_claimed_shipped_filters_a_mixed_list(self):
        beads = [
            self.af_x45xw_shape(id="zz-fixture-in-scope"),
            self.af_x45xw_shape(id="zz-fixture-open", status="open"),
            bead(id="zz-fixture-product-goal-complete"),  # unrelated, has its own label+proof
        ]
        found = {report["id"] for report in find_claimed_shipped(beads)}
        self.assertEqual({"zz-fixture-in-scope"}, found)


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

    def run_cli_mode(self, mode, payload):
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_delivery_proof.py"), "--mode", mode],
            input=payload, capture_output=True, text=True,
        )
        return result

    def test_claimed_shipped_mode_prints_one_line_per_bead_in_scope(self):
        payload = json.dumps([
            {
                "id": "zz-fixture-af-x45xw", "status": "closed",
                "metadata": {
                    "gc.outcome": "pass",
                    "gc.pr_url": "https://github.com/example-org/example-repo/pull/114",
                },
            },
            bead(id="zz-fixture-unrelated"),  # product-goal, fully proven, no gc.pr_url
        ])
        result = self.run_cli_mode("claimed-shipped", payload)
        self.assertEqual(0, result.returncode)
        lines = [line for line in result.stdout.splitlines() if line]
        self.assertEqual(1, len(lines))
        fields = lines[0].split("\x1f")
        self.assertEqual(
            ["zz-fixture-af-x45xw", "example-org/example-repo", "114", "0"], fields
        )

    def test_readiness_mode_reports_structural_failure_as_json(self):
        result = self.run_cli_mode("readiness", json.dumps({
            "id": "zz-p01", "status": "closed",
            "metadata": {
                "gc.plane": "delivery", "gc.graph_digest": "sha256:" + "5" * 64,
                "gc.pr_url": "https://github.com/example-org/example-repo/pull/197",
            },
        }))
        self.assertEqual(0, result.returncode, result.stderr)
        readiness = json.loads(result.stdout)
        self.assertFalse(readiness["ready"])
        self.assertIn("merge_result", readiness["missing"])

    def test_unknown_mode_fails_loudly(self):
        result = self.run_cli_mode("bogus", "[]")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
