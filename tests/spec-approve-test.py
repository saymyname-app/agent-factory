#!/usr/bin/env python3

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-approve"
FIXTURES = ROOT / "tests" / "fixtures" / "spec-approve"


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


if __name__ == "__main__":
    unittest.main()
