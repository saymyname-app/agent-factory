#!/usr/bin/env python3

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-approve"
FIXTURES = ROOT / "tests" / "fixtures" / "spec-approve"
FAKE_BD = FIXTURES / "bd"
PROJECTS_CONFIG_DIR = FIXTURES / "projects"


class SpecApproveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec-approve-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_tool(self, *args, check=False):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), text=True, capture_output=True, check=check
        )

    def draft_spec(self):
        path = self.tmp / "spec.json"
        shutil.copy(FIXTURES / "draft-spec.json", path)
        return path

    def load(self, path):
        return json.loads(path.read_text())

    def approve(self, spec_path, map_path=None, approved_by="benjamin", evidence="af-fixture-evidence", check=True):
        args = ["approve", spec_path, "--approved-by", approved_by, "--evidence", evidence]
        if map_path is not None:
            args += ["--map", map_path]
        return self.run_tool(*args, check=check)

    # --- AC1: approval names identity/digest and flips the same artifact ---

    def test_approve_names_identity_and_digest_and_flips_state(self):
        spec_path = self.draft_spec()
        before = self.load(spec_path)

        proc = self.approve(spec_path)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(before["spec_id"], result["spec_id"])
        self.assertEqual(before["content_digest"], result["digest"])

        after = self.load(spec_path)
        self.assertEqual(before["spec_id"], after["spec_id"])
        self.assertEqual("APPROVED_SPEC", after["state"])
        self.assertEqual("benjamin", after["approved_by"])
        self.assertEqual(before["content_digest"], after["content_digest"])

    def test_approve_rejects_declared_digest_that_does_not_match_content(self):
        spec_path = self.draft_spec()
        spec = self.load(spec_path)
        spec["content_digest"] = "sha256:" + "0" * 64
        spec_path.write_text(json.dumps(spec))

        proc = self.approve(spec_path, check=False)
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("does not match", error["error"])
        self.assertEqual("DRAFT_SPEC", self.load(spec_path)["state"])

    # --- AC2: approval closes the map and never duplicates the document ----

    def test_approve_closes_map_without_duplicating_the_document(self):
        spec_path = self.draft_spec()
        map_path = self.tmp / "map.json"
        shutil.copy(FIXTURES / "to-spec-ready-map.json", map_path)

        proc = self.approve(spec_path, map_path=map_path)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["map_closed"])

        map_state = self.load(map_path)
        self.assertEqual("closed", map_state["status"])
        # approval mutates the existing spec and map files only -- no third
        # document is ever materialized.
        self.assertCountEqual(["spec.json", "map.json"], [p.name for p in self.tmp.glob("*.json")])

    def test_approve_rejects_reapproving_an_already_approved_spec(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)

        proc = self.approve(spec_path, approved_by="someone-else", check=False)
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("already approved", error["error"])
        self.assertEqual("benjamin", self.load(spec_path)["approved_by"])

    def test_approve_rejects_closing_a_map_that_is_not_to_spec_ready(self):
        spec_path = self.draft_spec()
        map_path = self.tmp / "map.json"
        map_state = json.loads((FIXTURES / "to-spec-ready-map.json").read_text())
        map_state["status"] = "active"
        map_path.write_text(json.dumps(map_state))

        proc = self.approve(spec_path, map_path=map_path, check=False)
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("to_spec_ready", error["error"])
        self.assertEqual("DRAFT_SPEC", self.load(spec_path)["state"])

    # --- AC3: mutation of a frozen artifact is rejected; genuine change ----
    # --- creates a new digest with provenance -------------------------------

    def test_revise_rejects_wrong_expected_current_digest(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)

        proc = self.run_tool(
            "revise",
            spec_path,
            "--expected-current-digest",
            "sha256:" + "1" * 64,
            "--new-sections",
            FIXTURES / "revised-sections.json",
            "--revised-by",
            "benjamin",
            "--provenance",
            "af-fixture-evidence",
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("mutation of a frozen artifact is rejected", error["error"])
        self.assertEqual("APPROVED_SPEC", self.load(spec_path)["state"])

    def test_revise_rejects_no_semantic_change(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)
        digest = self.load(spec_path)["content_digest"]

        proc = self.run_tool(
            "revise",
            spec_path,
            "--expected-current-digest",
            digest,
            "--new-sections",
            FIXTURES / "unchanged-sections.json",
            "--revised-by",
            "benjamin",
            "--provenance",
            "af-fixture-evidence",
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("no semantic change", error["error"])
        self.assertEqual("APPROVED_SPEC", self.load(spec_path)["state"])

    def test_revise_creates_new_digest_with_provenance_and_requires_reapproval(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)
        before = self.load(spec_path)

        proc = self.run_tool(
            "revise",
            spec_path,
            "--expected-current-digest",
            before["content_digest"],
            "--new-sections",
            FIXTURES / "revised-sections.json",
            "--revised-by",
            "benjamin",
            "--provenance",
            "af-fixture-evidence",
            check=True,
        )
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertNotEqual(before["content_digest"], result["digest"])
        self.assertEqual(before["content_digest"], result["prior_digest"])

        after = self.load(spec_path)
        self.assertEqual(before["spec_id"], after["spec_id"])  # identity stable across revisions
        self.assertEqual("DRAFT_SPEC", after["state"])
        self.assertNotIn("approved_by", after)
        self.assertEqual(1, len(after["revisions"]))
        self.assertEqual(before["content_digest"], after["revisions"][0]["prior_digest"])
        self.assertEqual("af-fixture-evidence", after["revisions"][0]["provenance"])

        # the revision is a new DRAFT_SPEC: it can be approved again as its own artifact.
        proc = self.approve(spec_path)
        self.assertTrue(json.loads(proc.stdout)["ok"])

    def test_revise_rejects_a_spec_that_is_not_yet_approved(self):
        spec_path = self.draft_spec()
        proc = self.run_tool(
            "revise",
            spec_path,
            "--expected-current-digest",
            self.load(spec_path)["content_digest"],
            "--new-sections",
            FIXTURES / "revised-sections.json",
            "--revised-by",
            "benjamin",
            "--provenance",
            "af-fixture-evidence",
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("APPROVED_SPEC", error["error"])

    # --- AC5: freeze-check reports distinct value, not another fog audit ---

    def test_freeze_check_localizes_drift_instead_of_a_bare_boolean(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)

        spec = self.load(spec_path)
        spec["sections"]["behavior"] = [{"statement": "tampered", "confirmed_by": "nobody"}]
        spec_path.write_text(json.dumps(spec))

        proc = self.run_tool("freeze-check", spec_path)
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertEqual(["behavior"], error["drifted_sections"])

    def test_freeze_check_passes_an_untouched_frozen_artifact(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)
        digest = self.load(spec_path)["content_digest"]

        proc = self.run_tool("freeze-check", spec_path, "--expected-digest", digest, check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(digest, result["digest"])

    def test_freeze_check_is_optional_not_a_mandatory_second_audit(self):
        # approve and revise both succeed end-to-end without ever calling
        # freeze-check -- it exists for callers who want the extra integrity
        # signal, it is never required to make the lifecycle progress.
        spec_path = self.draft_spec()
        self.assertTrue(json.loads(self.approve(spec_path).stdout)["ok"])
        digest = self.load(spec_path)["content_digest"]
        proc = self.run_tool(
            "revise",
            spec_path,
            "--expected-current-digest",
            digest,
            "--new-sections",
            FIXTURES / "revised-sections.json",
            "--revised-by",
            "benjamin",
            "--provenance",
            "af-fixture-evidence",
            check=True,
        )
        self.assertTrue(json.loads(proc.stdout)["ok"])

    # --- AC4: recoverable during the convoy, expire-eligible only after ----
    # --- closure, while durable truth stays out of the artifact ------------

    def test_expire_check_recoverable_while_open_eligible_after_closure(self):
        spec_path = self.draft_spec()
        self.approve(spec_path)

        open_report = json.loads(self.run_tool("expire-check", spec_path, "--convoy-status", "open", check=True).stdout)
        self.assertTrue(open_report["ok"])
        self.assertTrue(open_report["recoverable"])
        self.assertFalse(open_report["expire_eligible"])
        self.assertFalse(open_report["durable_truth_lives_here"])

        closed_report = json.loads(
            self.run_tool("expire-check", spec_path, "--convoy-status", "closed", check=True).stdout
        )
        self.assertTrue(closed_report["ok"])
        self.assertFalse(closed_report["recoverable"])
        self.assertTrue(closed_report["expire_eligible"])


class SpecApproveBeadModeTest(unittest.TestCase):
    """W04: spec-approve approves a planning-plane Spec bead by id, with or
    without a map, against the live Beads/reservation/profile tools."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec-approve-bd-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()

    def invoke(self, *args, check=False):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "SPEC_APPROVE_BD_STATE": str(self.state_path),
        }
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), env=env, text=True, capture_output=True, check=check,
        )

    def seed(self, beads, next_id=1):
        self.state_path.write_text(json.dumps({"beads": beads, "next_id": next_id}))

    def bead(self, **kwargs):
        base = {
            "labels": [], "metadata": {}, "parent": None, "status": "open",
            "title": "", "description": "spec body",
        }
        base.update(kwargs)
        return base

    def current_state(self):
        return json.loads(self.state_path.read_text())

    def write_reservation(self, reserved_for):
        runtime_path = self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(json.dumps({
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "cleared_at": None,
        }))

    def bd_approve(self, spec_id, approved_by="benjamin", evidence="Benjamin's exact words, 2026-09-30 Paris", project="acme", check=False):
        return self.invoke(
            "bd-approve", "--spec", spec_id, "--approved-by", approved_by, "--evidence", evidence,
            "--project", project, "--repo-root", self.repo_root, "--config-dir", PROJECTS_CONFIG_DIR,
            check=check,
        )

    def mapped_spec_beads(self, target="A6b", map_finished=True):
        return {
            "spec-1": self.bead(id="spec-1", metadata={"planning_run_target": target, "planning_map": "map-1"}),
            "map-1": self.bead(id="map-1", labels=["wayfinder:map"]),
            "map-1.1": self.bead(
                id="map-1.1", parent="map-1", status="closed" if map_finished else "open",
                labels=["wayfinder:task"], metadata={"gc.plane": "planning"},
            ),
        }

    # --- refusals: Spec bead and map are left untouched ---------------------

    def test_bd_approve_refuses_wrong_target_while_reserved(self):
        self.seed(self.mapped_spec_beads(target="A6b"))
        self.write_reservation(reserved_for="C01")

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("C01", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_unfinished_map(self):
        self.seed(self.mapped_spec_beads(map_finished=False))

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("not finished", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_wrong_approver(self):
        self.seed(self.mapped_spec_beads())

        proc = self.bd_approve("spec-1", approved_by="someone-else")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("declared human approver", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_empty_evidence(self):
        self.seed(self.mapped_spec_beads())

        proc = self.bd_approve("spec-1", evidence="")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    def test_bd_approve_refuses_no_map_and_no_no_fog_evidence(self):
        self.seed({
            "spec-1": self.bead(id="spec-1", metadata={"planning_run_target": "A6b", "planning_map": "none"}),
        })

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("No-fog", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    # --- success: mapped and unmapped ----------------------------------------

    def test_bd_approve_approves_valid_mapped_spec_records_digest_and_closes_map(self):
        beads = self.mapped_spec_beads()
        beads["spec-1"]["description"] = "prose spec body"
        self.seed(beads)

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["map_closed"])
        self.assertEqual("APPROVED_SPEC", result["state"])

        expected_digest = "sha256:" + hashlib.sha256(b"prose spec body").hexdigest()
        self.assertEqual(expected_digest, result["digest"])

        state = self.current_state()
        spec_metadata = state["beads"]["spec-1"]["metadata"]
        self.assertEqual("APPROVED_SPEC", spec_metadata["spec_state"])
        self.assertEqual("benjamin", spec_metadata["approved_by"])
        self.assertEqual(expected_digest, spec_metadata["approved_digest"])
        self.assertEqual("closed", state["beads"]["map-1"]["status"])

    def test_bd_approve_approves_valid_unmapped_spec_with_no_fog_evidence(self):
        self.seed({
            "spec-1": self.bead(
                id="spec-1",
                metadata={
                    "planning_run_target": "A6b", "planning_map": "none",
                    "no_fog_evidence": "« pas de brouillard » (Benjamin, 2026-09-30 Paris)",
                },
                description="prose spec body",
            ),
        })

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["map_closed"])
        self.assertIsNone(result["map"])

        state = self.current_state()
        self.assertEqual("APPROVED_SPEC", state["beads"]["spec-1"]["metadata"]["spec_state"])

    # --- status: an edit after approval voids it -----------------------------

    def test_bd_status_reports_void_after_spec_edited_post_approval(self):
        beads = self.mapped_spec_beads()
        self.seed(beads)
        self.assertTrue(json.loads(self.bd_approve("spec-1", check=True).stdout)["ok"])

        state = self.current_state()
        state["beads"]["spec-1"]["description"] = "edited after approval"
        self.state_path.write_text(json.dumps(state))

        proc = self.invoke("bd-status", "--spec", "spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["void"])

    def test_bd_status_reports_not_void_when_unchanged(self):
        beads = self.mapped_spec_beads()
        self.seed(beads)
        self.assertTrue(json.loads(self.bd_approve("spec-1", check=True).stdout)["ok"])

        proc = self.invoke("bd-status", "--spec", "spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["void"])


if __name__ == "__main__":
    unittest.main()
