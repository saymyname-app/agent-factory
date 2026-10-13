#!/usr/bin/env python3
"""CLI recurrence against a throwaway project descriptor and fake tracker."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "project-standards"
FAKE_GC = Path(__file__).resolve().parent / "fixtures" / "convoy-state" / "gc"


class RecurrenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        descriptors = self.root / "config" / "project-descriptors"
        descriptors.mkdir(parents=True)
        (descriptors / "sample.json").write_text(json.dumps({
            "contract": "agent-factory-project-descriptor/v1", "project_id": "sample",
            "display_name": "Sample", "rigs": ["api", "web"],
            "stacks": {"api": ["java-spring-maven"], "web": ["react-typescript"]},
            "knowledge_repo": "owner/repo", "roadmap_path": "roadmap.toml",
            "rituals_status_command": "true"}))
        projects = self.root / "config" / "projects"
        projects.mkdir()
        rigs = self.root / "rigs"
        (rigs / "api").mkdir(parents=True)
        (rigs / "web").mkdir()
        (projects / "api.toml").write_text('rig_dir = "rigs/api"\n')
        (projects / "web.toml").write_text('rig_dir = "rigs/web"\n')
        (rigs / "api" / "STANDARDS.md").write_text(
            "## Rules cited by the reviewer\n\n- Toute fonction publique porte une docstring.\n"
            "\n## Choices\n\n- Formatting style: Google Java Style.\n")
        (rigs / "web" / "DESIGN.md").write_text(
            "## Rules cited by the reviewer\n\n- Le focus est visible au clavier.\n")

    def recurrence(self, beads, rig="api"):
        tracker = self.root / "tracker.json"
        tracker.write_text(json.dumps({"beads": beads}))
        result = subprocess.run([str(TOOL), "--repo-root", str(self.root), "recurrence", "--rig", rig],
                                text=True, capture_output=True,
                                env={**os.environ, "GC_BIN": str(FAKE_GC),
                                     "CONVOY_STATE_FAKE_TRACKER": str(tracker)})
        return result.returncode, json.loads(result.stdout), json.loads(tracker.read_text())["beads"]

    def test_second_blocking_citation_creates_one_planning_root_cause_ticket(self):
        citation = {"source": "repo_rule", "path": "STANDARDS.md",
                    "quote": "Toute fonction publique porte une docstring."}
        def ticket(rig, findings):
            return {"title": "Ticket", "status": "closed", "issue_type": "task",
                    "description": f"## Target rigs\n\n{rig}\n",
                    "metadata": {"gc.flow.code_review": json.dumps({"rounds": [
                        {"kind": "review", "findings": findings}]})}}
        def finding(blocking=True, cited=citation):
            return {"blocking": blocking, "citation": cited, "summary": "Docstring absente"}
        beads = {"fx-a": ticket("api", [finding()]),
                 "fx-b": ticket("api", [finding(cited={**citation, "quote": "fonction publique porte une docstring."})]),
                 "fx-c": ticket("web", [finding()]),
                 "fx-d": ticket("api", [finding(False)]),
                 "fx-e": ticket("api", [finding(cited={"source": "spec", "quote": citation["quote"]})]),
                 "fx-f": ticket("api", [finding(cited={**citation, "path": "README.md"})]),
                 "fx-g": ticket("api", [finding(cited={**citation, "path": "README.md"})])}
        code, result, stored = self.recurrence(beads)
        self.assertEqual(0, code, result)
        self.assertEqual(1, len(result["created"]))
        root = stored[result["created"][0]["ticket"]]
        self.assertEqual("planning", root["metadata"]["gc.plane"])
        self.assertEqual("sample", root["metadata"]["gc.project_id"])
        self.assertIn("ready-for-agent", root["labels"])
        self.assertIn("fx-a", root["description"])
        self.assertIn("fx-b", root["description"])
        self.assertIn("Acceptance Session", root["description"])
        code, again, stored = self.recurrence(stored)
        self.assertEqual(0, code, again)
        self.assertEqual([], again["created"])
        self.assertEqual(1, sum("gc.standard_recurrence" in (b.get("metadata") or {}) for b in stored.values()))

    def test_two_findings_in_one_review_are_one_refusal(self):
        cited = {"source": "repo_rule", "path": "DESIGN.md", "quote": "Focus visible au clavier."}
        finding = {"blocking": True, "citation": cited, "summary": "Focus invisible"}
        ticket = {"title": "Ticket", "status": "closed", "issue_type": "task",
                  "description": "## Target rigs\n\napi\n",
                  "metadata": {"gc.flow.code_review": json.dumps({"rounds": [
                      {"kind": "review", "findings": [finding, finding]}]})}}
        code, result, stored = self.recurrence({"fx-a": ticket})
        self.assertEqual(0, code, result)
        self.assertEqual([], result["created"])
        self.assertEqual({"fx-a"}, set(stored))

    def test_a_choice_is_not_a_citable_standard(self):
        citation = {"source": "repo_rule", "path": "STANDARDS.md",
                    "quote": "Formatting style: Google Java Style."}
        def ticket():
            return {"title": "Ticket", "status": "closed", "issue_type": "task",
                    "description": "## Target rigs\n\napi\n",
                    "metadata": {"gc.flow.code_review": json.dumps({"rounds": [
                        {"kind": "review", "findings": [
                            {"blocking": True, "citation": citation}]}]})}}
        code, result, _ = self.recurrence({"fx-a": ticket(), "fx-b": ticket()})
        self.assertEqual(0, code, result)
        self.assertEqual([], result["created"])

    def test_second_evaluator_screen_finding_cites_same_design_rule(self):
        def ticket():
            return {"title": "Ticket", "status": "closed", "issue_type": "task",
                    "description": "## Target rigs\n\nweb\n",
                    "metadata": {"gc.flow.evaluation": json.dumps({"rounds": [
                        {"kind": "evaluation", "screen_findings": [
                            {"check": "focus", "rule": "- Le focus est visible au clavier.",
                             "evidence": "piece", "reason": "focus absent"}]}]})}}
        code, result, stored = self.recurrence({"fx-a": ticket(), "fx-b": ticket()}, rig="web")
        self.assertEqual(0, code, result)
        self.assertEqual(1, len(result["created"]))
        self.assertIn("évaluation", stored[result["created"][0]["ticket"]]["description"])

    def test_rule_removed_since_refusals_no_longer_creates_root_cause_work(self):
        citation = {"source": "repo_rule", "path": "STANDARDS.md",
                    "quote": "Toute fonction publique porte une docstring."}
        def ticket():
            return {"title": "Ticket", "status": "closed", "issue_type": "task",
                    "description": "## Target rigs\n\napi\n",
                    "metadata": {"gc.flow.code_review": json.dumps({"rounds": [
                        {"kind": "review", "findings": [
                            {"blocking": True, "citation": citation}]}]})}}
        (self.root / "rigs/api/STANDARDS.md").write_text(
            "## Rules cited by the reviewer\n\n- Autre règle.\n")
        code, result, _ = self.recurrence({"fx-a": ticket(), "fx-b": ticket()})
        self.assertEqual(0, code, result)
        self.assertEqual([], result["created"])


if __name__ == "__main__":
    unittest.main()
