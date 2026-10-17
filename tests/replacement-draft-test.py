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
            "convoy": {**bead("convoy", metadata={"gc.flow.mark": "new-flow/v1", "gc.project_id": "agent-factory",
                "gc.spec_id": "spec", "gc.spec_digest": digest(spec_body), "gc.graph_digest": graph_digest}),
                # What the convoy tracks, as `bd show --json` lists it: the resulting graph.
                "dependencies": [
                    {"id": "stopped", "dependency_type": "tracks", "status": "in_progress",
                     "metadata": {"gc.ticket_id": "T01R2", "gc.graph_digest": graph_digest}},
                    {"id": "next", "dependency_type": "tracks", "status": "open",
                     "metadata": {"gc.ticket_id": "T02", "gc.graph_digest": graph_digest, "gc.blocked_by": "T01R2"}},
                ]},
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

    def run_create(self, *extra):
        return subprocess.run([
            str(TOOL), "create", "--decision", "decision",
            "--evidence", "ok go, create this exact replacement",
            "--stopped-ticket", "stopped", "--convoy", "convoy", "--source-draft", "source",
            "--replacement-id", "T01R3", "--useful-commit", COMMIT,
            "--planning-exception", "pe-replacement", "--approved-by", "benjamin",
            "--author-session", "po-agent/test", *extra,
        ], env=self.env, text=True, capture_output=True)

    def revision_file(self, revision):
        path = Path(self.tmp.name) / "revision.json"
        path.write_text(json.dumps(revision))
        return str(path)

    def test_applies_a_bounded_revision_and_records_its_digests(self):
        criteria = [{"entry_point": "start on dataset A", "observable": "answers", "false_if": "absent"}]
        revision = {"scope": {"paths": ["bin/reduced"]}, "acceptance_criteria": criteria,
                    "demonstration_line": "Dataset A answers.", "what_it_delivers": "Reduced launch.",
                    "drop_establishes_launch_recipe": True}
        proc = self.run_create("--revision-file", self.revision_file(revision))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        draft = json.loads(self.state_path.read_text())["beads"][json.loads(proc.stdout)["draft"]]
        replacement = next(t for t in yaml.safe_load(draft["description"])["tickets"] if t["id"] == "T01R3")
        self.assertEqual(criteria, replacement["acceptance_criteria"])
        self.assertEqual({"paths": ["bin/reduced"]}, replacement["scope"])
        self.assertEqual("Dataset A answers.", replacement["demonstration_line"])
        self.assertNotIn("establishes_launch_recipe", replacement)
        self.assertTrue(replacement["what_it_delivers"].startswith("Reduced launch. Authorized replacement:"))
        criteria_digest = digest(json.dumps(criteria, sort_keys=True, separators=(",", ":")))
        scope_digest = digest("bin/reduced")
        self.assertEqual(criteria_digest, draft["metadata"]["replacement_revised_criteria_digest"])
        self.assertEqual(scope_digest, draft["metadata"]["replacement_revised_scope_digest"])
        self.assertIn(f"revised criteria {criteria_digest} scope {scope_digest}", replacement["what_it_delivers"])
        self.assertEqual("sha256:criteria", draft["metadata"]["replacement_criteria_digest"])

    def test_refuses_a_revision_outside_its_bounds_without_writing(self):
        before = json.loads(self.state_path.read_text())
        for revision in ({"title": "other"}, {"acceptance_criteria": []},
                         {"acceptance_criteria": [{"entry_point": "x", "observable": "", "false_if": "y"}]},
                         {"scope": {"paths": [""]}}, {"drop_establishes_launch_recipe": False}):
            proc = self.run_create("--revision-file", self.revision_file(revision))
            self.assertNotEqual(0, proc.returncode, revision)
            self.assertIn("refused: revision", json.loads(proc.stdout)["error"])
            self.assertEqual(before, json.loads(self.state_path.read_text()))

    # --- the resulting graph: a ticket published by an earlier revision (af-k08bi1) ----

    LATER = "sha256:" + "c" * 64

    def later_revision(self, waiter_digest=None, untrack=False):
        """A later partial revision (another ticket only) moved the convoy to
        LATER; the stopped ticket stays at the digest of the source draft."""
        state = json.loads(self.state_path.read_text())
        convoy = state["beads"]["convoy"]
        convoy["metadata"]["gc.graph_digest"] = self.LATER
        deps = convoy["dependencies"]
        deps.append({"id": "other", "dependency_type": "tracks", "status": "open",
                     "metadata": {"gc.ticket_id": "T03", "gc.graph_digest": self.LATER}})
        if waiter_digest:
            deps[1]["metadata"]["gc.graph_digest"] = waiter_digest
        if untrack:
            del deps[0]
        self.state_path.write_text(json.dumps(state))

    def test_replaces_a_ticket_published_by_an_earlier_revision_still_in_force(self):
        self.later_revision()
        proc = self.run_create()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        draft = json.loads(self.state_path.read_text())["beads"][json.loads(proc.stdout)["draft"]]
        parsed = yaml.safe_load(draft["description"])
        self.assertEqual(self.LATER, draft["metadata"]["revises_digest"])
        self.assertEqual(["T01R3", "T02"], [ticket["id"] for ticket in parsed["tickets"]])
        self.assertEqual(["T01R3"], parsed["tickets"][1]["blocked_by"])
        self.assertEqual([{"ticket": "T01R2", "planning_exception": "pe-replacement"}], parsed["withdrawn"])

    def test_refuses_a_ticket_the_convoy_does_not_track(self):
        self.later_revision(untrack=True)
        self.assert_refused_unwritten("does not track")

    def test_refuses_a_waiting_ticket_published_by_another_revision(self):
        self.later_revision(waiter_digest=self.LATER)
        self.assert_refused_unwritten("waits for T01R2")

    # --- a ticket parked by its own answered Planning Exception (af-6854ef) ----

    PARK_AT = "2026-10-15T02:34:40Z"

    def park_source(self, origin="stopped", answered=True, needs="none", response_at="2026-10-15T10:02:53Z"):
        """The source ticket is parked by a Planning Exception (no stop): its own,
        or one raised on another ticket; answered or not by the operator through
        the escalation door (repondre)."""
        state = json.loads(self.state_path.read_text())
        meta = state["beads"]["stopped"]["metadata"]
        del meta["gc.flow.stop"]
        meta["gc.flow.park"] = json.dumps({"cause": "planning_exception", "origin": origin,
                                           "detail": "Planning Exception (semantic)", "at": self.PARK_AT})
        meta["gc.flow.exit"] = json.dumps({"exit": "planning_exception", "at": self.PARK_AT})
        meta["gc.needs_benjamin"] = needs
        if answered:
            meta["gc.escalation_response_option"] = "a"
            meta["gc.escalation_response_at"] = response_at
        self.state_path.write_text(json.dumps(state))

    def assert_refused_unwritten(self, mention):
        before = json.loads(self.state_path.read_text())
        proc = self.run_create()
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn(mention, json.loads(proc.stdout)["error"])
        self.assertEqual(before, json.loads(self.state_path.read_text()))

    def test_replaces_a_ticket_parked_by_its_own_answered_planning_exception(self):
        self.park_source()
        before = json.loads(self.state_path.read_text())
        proc = self.run_create()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        after = json.loads(self.state_path.read_text())
        self.assertEqual(before["beads"]["stopped"], after["beads"]["stopped"])
        draft = after["beads"][json.loads(proc.stdout)["draft"]]
        self.assertEqual("stopped", draft["metadata"]["replacement_of"])
        parsed = yaml.safe_load(draft["description"])
        self.assertEqual([{"ticket": "T01R2", "planning_exception": "pe-replacement"}], parsed["withdrawn"])
        replacement = next(t for t in parsed["tickets"] if t["id"] == "T01R3")
        self.assertIn("parked by its own Planning Exception, answered a", replacement["what_it_delivers"])

    def test_refuses_a_parked_ticket_whose_request_has_no_answer(self):
        self.park_source(answered=False)
        self.assert_refused_unwritten("no answered Planning Exception parking")

    def test_refuses_a_parked_ticket_whose_request_is_still_open(self):
        self.park_source(needs="blocking")
        self.assert_refused_unwritten("no answered Planning Exception parking")

    def test_refuses_an_answer_older_than_the_parking(self):
        self.park_source(response_at="2026-10-15T01:00:00Z")
        self.assert_refused_unwritten("no answered Planning Exception parking")

    def test_refuses_a_ticket_parked_behind_another_one(self):
        self.park_source(origin="other")
        self.assert_refused_unwritten("no answered Planning Exception parking")

    def test_refuses_a_ticket_neither_stopped_nor_parked(self):
        state = json.loads(self.state_path.read_text())
        del state["beads"]["stopped"]["metadata"]["gc.flow.stop"]
        self.state_path.write_text(json.dumps(state))
        self.assert_refused_unwritten("has no active stop reason")


if __name__ == "__main__":
    unittest.main()
