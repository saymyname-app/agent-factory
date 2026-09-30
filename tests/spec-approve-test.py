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

    # --- project key: map to Spec (T05) --------------------------------------

    def test_bd_approve_sets_spec_project_key_from_its_map(self):
        beads = self.mapped_spec_beads()
        beads["map-1"]["metadata"]["gc.project_id"] = "fixture-project"
        self.seed(beads)

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])

        state = self.current_state()
        self.assertEqual("fixture-project", state["beads"]["spec-1"]["metadata"]["gc.project_id"])

    def test_bd_approve_refuses_a_spec_whose_project_key_contradicts_its_map(self):
        beads = self.mapped_spec_beads()
        beads["map-1"]["metadata"]["gc.project_id"] = "fixture-project"
        beads["spec-1"]["metadata"]["gc.project_id"] = "another-project"
        self.seed(beads)

        proc = self.bd_approve("spec-1")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("contradicts", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    def test_bd_approve_keeps_an_unmapped_specs_own_project_key(self):
        self.seed({
            "spec-1": self.bead(
                id="spec-1",
                metadata={
                    "planning_run_target": "A6b", "planning_map": "none",
                    "no_fog_evidence": "« pas de brouillard » (Benjamin, 2026-09-30 Paris)",
                    "gc.project_id": "its-own-project",
                },
                description="prose spec body",
            ),
        })

        proc = self.bd_approve("spec-1", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])

        state = self.current_state()
        self.assertEqual("its-own-project", state["beads"]["spec-1"]["metadata"]["gc.project_id"])

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
