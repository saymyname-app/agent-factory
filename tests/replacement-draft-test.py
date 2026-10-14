#!/usr/bin/env python3
"""Public-command regression for the bounded stopped-ticket replacement draft door."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin/replacement-draft"
FAKE_BD = ROOT / "tests/fixtures/spec-approve/bd"
COMMIT = "4bf4fbf3ba28ba502bbf1dc014a63ae259b2f9f1"


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class ReplacementDraftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="replacement-draft-test-")
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        source = yaml.safe_dump({
            "flow_contract": "new-flow/v1",
            "operator_needs": [],
            "tickets": [
                {
                    "id": "T01R2", "kind": "vertical_slice", "title": "Launch",
                    "blocked_by": [], "target_rigs": ["agent-factory"], "user_stories": [126],
                    "scope": {"paths": ["bin/project-launch"]},
                    "what_it_delivers": "Launch the approved product.",
                    "demonstration_line": "The approved product answers.",
                    "acceptance_criteria": [{"entry_point": "start", "observable": "answers", "false_if": "absent"}],
                    "establishes_launch_recipe": True,
                },
                {
                    "id": "T02", "kind": "vertical_slice", "title": "Next slice",
                    "blocked_by": ["T01R2"], "target_rigs": ["agent-factory"], "user_stories": [127],
                    "what_it_delivers": "Build on the launch.",
                    "demonstration_line": "The next slice answers.",
                    "acceptance_criteria": [{"entry_point": "next", "observable": "answers", "false_if": "absent"}],
                },
            ],
        }, allow_unicode=True, sort_keys=False)
        spec_body = "## User Stories\n126. Launch\n127. Continue\n"
        graph_digest = digest(source)

        def bead(identifier, description="", metadata=None, comments=None, status="open"):
            return {"id": identifier, "title": identifier, "description": description, "status": status,
                    "labels": [], "metadata": metadata or {}, "comments": comments or [], "parent": None}

        state = {"next_id": 1, "beads": {
            "decision": bead("decision", comments=[{"text": "Benjamin: ok go, create this exact replacement"}]),
            "spec": bead("spec", spec_body, {"gc.plane": "planning", "gc.project_id": "agent-factory",
                "spec_state": "APPROVED_SPEC", "approved_digest": digest(spec_body)}),
            "source": bead("source", source, {"gc.plane": "planning", "gc.project_id": "agent-factory",
                "spec_id": "spec", "approved_by": "benjamin", "approved_digest": graph_digest}),
            "convoy": bead("convoy", metadata={"gc.flow.mark": "new-flow/v1", "gc.project_id": "agent-factory",
                "gc.spec_id": "spec", "gc.spec_digest": digest(spec_body), "gc.graph_digest": graph_digest}),
            "stopped": bead("stopped", metadata={"gc.ticket_id": "T01R2", "gc.ticket_kind": "vertical_slice",
                "gc.spec_id": "spec", "gc.spec_digest": digest(spec_body), "gc.graph_digest": graph_digest,
                "gc.flow.stop": json.dumps({"reason": "evaluation_no_result"}),
                "gc.flow.criteria": json.dumps({"graph_digest": graph_digest, "digest": "sha256:criteria"}),
                "gc.flow.handoff": json.dumps({"commit": COMMIT, "records": {"declared_scope": ["bin/project-launch"]}})},
                status="in_progress"),
        }}
        self.state_path.write_text(json.dumps(state))
        self.env = {**os.environ, "BD_BIN": str(FAKE_BD), "SPEC_APPROVE_BD_STATE": str(self.state_path)}

    def test_creates_one_immutable_replacement_draft_and_preserves_the_stopped_ticket(self):
        self.assertTrue(TOOL.exists(), "missing official replacement-draft door")
        refused_before = json.loads(self.state_path.read_text())
        refused = subprocess.run([
            str(TOOL), "create", "--decision", "decision", "--evidence", "not authorized",
            "--stopped-ticket", "stopped", "--convoy", "convoy", "--source-draft", "source",
            "--replacement-id", "T01R3", "--useful-commit", COMMIT,
            "--planning-exception", "pe-replacement", "--approved-by", "benjamin",
            "--author-session", "po-agent/test",
        ], env=self.env, text=True, capture_output=True)
        self.assertNotEqual(0, refused.returncode)
        self.assertEqual(refused_before, json.loads(self.state_path.read_text()))

        before = json.loads(self.state_path.read_text())
        proc = subprocess.run([
            str(TOOL), "create", "--decision", "decision",
            "--evidence", "ok go, create this exact replacement",
            "--stopped-ticket", "stopped", "--convoy", "convoy", "--source-draft", "source",
            "--replacement-id", "T01R3", "--useful-commit", COMMIT,
            "--planning-exception", "pe-replacement", "--approved-by", "benjamin",
            "--author-session", "po-agent/test",
        ], env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        after = json.loads(self.state_path.read_text())
        self.assertEqual(before["beads"]["stopped"], after["beads"]["stopped"])
        self.assertEqual(1, len(after["beads"]) - len(before["beads"]))
        draft = after["beads"][result["draft"]]
        parsed = yaml.safe_load(draft["description"])
        replacement = next(ticket for ticket in parsed["tickets"] if ticket["id"] == "T01R3")
        original = yaml.safe_load(before["beads"]["source"]["description"])["tickets"][0]
        self.assertEqual(original["acceptance_criteria"], replacement["acceptance_criteria"])
        self.assertEqual(original["scope"], replacement["scope"])
        self.assertIn(COMMIT, replacement["what_it_delivers"])
        self.assertIn("decision", replacement["what_it_delivers"])
        self.assertEqual(["T01R3"], next(t for t in parsed["tickets"] if t["id"] == "T02")["blocked_by"])
        self.assertEqual([{"ticket": "T01R2", "planning_exception": "pe-replacement"}], parsed["withdrawn"])
        self.assertEqual(digest(draft["description"]), draft["metadata"]["approved_digest"])
        self.assertEqual(graph_digest := before["beads"]["convoy"]["metadata"]["gc.graph_digest"],
                         draft["metadata"]["revises_digest"])
        self.assertEqual("stopped", draft["metadata"]["replacement_of"])
        self.assertEqual("convoy", draft["metadata"]["replacement_convoy"])
        self.assertEqual("spec", draft["metadata"]["spec_id"])
        self.assertEqual("decision", draft["metadata"]["replacement_decision"])
        self.assertEqual("sha256:criteria", draft["metadata"]["replacement_criteria_digest"])
        self.assertEqual("sha256:" + hashlib.sha256(b"bin/project-launch").hexdigest(),
                         draft["metadata"]["replacement_scope_digest"])
        self.assertEqual(graph_digest, before["beads"]["stopped"]["metadata"]["gc.graph_digest"])


if __name__ == "__main__":
    unittest.main()
