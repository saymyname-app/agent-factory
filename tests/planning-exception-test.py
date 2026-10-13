#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "planning-exception"
FIXTURES = ROOT / "tests" / "fixtures" / "planning-exception"
GRAPH = FIXTURES / "graph.json"
FAKE_PUBLISH = FIXTURES / "ticket-graph-publish"
FAKE_GC = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "gc"


class PlanningExceptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="planning-exception-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_tool(self, *args, env=None, check=False):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), text=True, capture_output=True, check=check,
            env={**os.environ, "GC_BIN": str(FAKE_GC), **(env or {})},
        )

    def init(self, run_id="run-1", out=None, check=True):
        out = out or (self.tmp / "register.json")
        proc = self.run_tool("init", "--run", run_id, "--out", out, check=check)
        return out, proc

    def load(self, register_path):
        return json.loads(register_path.read_text())

    # --- AC1: technical repair stays in the slice ---------------------------

    def test_classify_repair_never_requires_a_planning_exception(self):
        result = json.loads(self.run_tool("classify", "--kind", "repair", check=True).stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["requires_planning_exception"])

    def test_classify_semantic_and_topology_require_a_planning_exception(self):
        for kind in ("semantic", "topology"):
            result = json.loads(self.run_tool("classify", "--kind", kind, check=True).stdout)
            self.assertTrue(result["requires_planning_exception"])

    def test_raise_rejects_a_repair_kind_signal(self):
        register, _ = self.init()
        proc = self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "repair",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1",
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertIn("bounded technical repair", error["error"])
        # nothing was recorded
        state = self.load(register)
        self.assertEqual({}, state["decisions"])

    # --- AC2/AC3: one planning-plane decision parks only descendants -------

    def test_raise_parks_only_the_affected_bead_and_its_descendants(self):
        register, _ = self.init()
        result = json.loads(self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "spec says X, delivery found Y",
            "--raised-by", "worker-1", check=True,
        ).stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["duplicate"])
        self.assertEqual(["af-b08", "af-b10"], result["parked"])

        state = self.load(register)
        decision = state["decisions"]["pd-1"]
        self.assertEqual("planning", decision["plane"])
        self.assertFalse(decision["delivery_routable"])
        self.assertEqual("open", decision["status"])
        self.assertEqual(["af-b08", "af-b10"], decision["parked"])

        # unrelated Ready Frontier beads never appear parked anywhere
        status = json.loads(self.run_tool("status", register, check=True).stdout)
        self.assertEqual(["af-b08", "af-b10"], status["parked"])
        self.assertNotIn("af-b09", status["parked"])
        self.assertNotIn("af-b11", status["parked"])

    def test_raise_on_a_bead_with_no_descendants_parks_only_itself(self):
        register, _ = self.init()
        result = json.loads(self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b11", "--kind", "topology",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-2",
            check=True,
        ).stdout)
        self.assertEqual(["af-b11"], result["parked"])

    # --- AC5: duplicate escalation is detected, not double-parked ----------

    def test_raise_on_an_already_open_bead_is_detected_as_duplicate_not_double_parked(self):
        register, _ = self.init()
        first = json.loads(self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "first signal", "--raised-by", "worker-1",
            check=True,
        ).stdout)
        second = json.loads(self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "topology",
            "--run", "run-1", "--decision-id", "pd-2", "--summary", "second signal", "--raised-by", "worker-2",
            check=True,
        ).stdout)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual("pd-1", second["decision"])

        state = self.load(register)
        self.assertNotIn("pd-2", state["decisions"])  # no second decision created
        self.assertEqual(1, len(state["decisions"]))
        duplicate_events = [e for e in state["history"] if e["event"] == "duplicate_detected"]
        self.assertEqual(1, len(duplicate_events))
        self.assertEqual("pd-1", duplicate_events[0]["existing_decision"])

    # --- AC4: tactical resolve resumes the slice with no artifact patch ----

    def test_resolve_tactical_unparks_with_no_artifact_patch(self):
        register, _ = self.init()
        self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1", check=True,
        )
        result = json.loads(self.run_tool(
            "resolve", register, "--decision", "pd-1", "--kind", "tactical",
            "--note", "just a naming clarification, resume as-is", check=True,
        ).stdout)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["patch"])
        self.assertEqual(["af-b08", "af-b10"], result["unparked"])

        state = self.load(register)
        decision = state["decisions"]["pd-1"]
        self.assertEqual("resolved", decision["status"])
        self.assertEqual("tactical", decision["resolution_kind"])
        self.assertEqual([], decision["parked"])

        status = json.loads(self.run_tool("status", register, check=True).stdout)
        self.assertEqual([], status["parked"])

    # --- AC4: behavioral/topology resolve routes through the sole
    # to-tickets authority before unparking -----------------------------

    def test_resolve_behavioral_requires_a_patched_draft(self):
        register, _ = self.init()
        self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1", check=True,
        )
        proc = self.run_tool("resolve", register, "--decision", "pd-1", "--kind", "behavioral", "--note", "n")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertIn("--patched-draft is required", error["error"])
        # decision remains open, still parked -- resolve never partially applied
        state = self.load(register)
        self.assertEqual("open", state["decisions"]["pd-1"]["status"])
        self.assertEqual(["af-b08", "af-b10"], state["decisions"]["pd-1"]["parked"])

    def test_resolve_behavioral_routes_through_ticket_graph_publish_patch(self):
        register, _ = self.init()
        self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1", check=True,
        )
        log = self.tmp / "publish.log"
        draft = self.tmp / "revised-draft.yaml"
        draft.write_text("placeholder revised draft\n")
        result = json.loads(self.run_tool(
            "resolve", register, "--decision", "pd-1", "--kind", "behavioral",
            "--note", "AC changed, revised draft published", "--patched-draft", draft,
            "--project", "agent-factory",
            env={
                "PLANNING_EXCEPTION_PUBLISH_BIN": str(FAKE_PUBLISH),
                "PLANNING_EXCEPTION_PUBLISH_LOG": str(log),
            },
            check=True,
        ).stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["patch"]["ok"])
        self.assertEqual(["B08"], result["patch"]["patched"])

        calls = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(
            [["bd-patch", str(draft), "--author", "planning-exception:pd-1",
              "--reason", "AC changed, revised draft published",
              "--planning-exception-register", str(register), "--project", "agent-factory"]],
            calls,
        )

        state = self.load(register)
        decision = state["decisions"]["pd-1"]
        self.assertEqual("resolved", decision["status"])
        self.assertEqual("behavioral", decision["resolution_kind"])
        self.assertEqual([], decision["parked"])
        self.assertNotIn("patch_authorization", decision)

    def test_resolve_behavioral_leaves_the_decision_open_when_the_patch_fails(self):
        register, _ = self.init()
        self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b08", "--kind", "topology",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1", check=True,
        )
        draft = self.tmp / "revised-draft.yaml"
        draft.write_text("placeholder revised draft\n")
        proc = self.run_tool(
            "resolve", register, "--decision", "pd-1", "--kind", "topology",
            "--note", "n", "--patched-draft", draft, "--project", "agent-factory",
            env={
                "PLANNING_EXCEPTION_PUBLISH_BIN": str(FAKE_PUBLISH),
                "PLANNING_EXCEPTION_PUBLISH_FAIL": "1",
            },
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertIn("to-tickets patch failed", error["error"])

        state = self.load(register)
        decision = state["decisions"]["pd-1"]
        self.assertEqual("open", decision["status"])
        self.assertEqual(["af-b08", "af-b10"], decision["parked"])
        self.assertNotIn("patch_authorization", decision)

    def test_resolve_rejects_an_already_resolved_decision(self):
        register, _ = self.init()
        self.run_tool(
            "raise", register, "--graph", GRAPH, "--bead", "af-b11", "--kind", "semantic",
            "--run", "run-1", "--decision-id", "pd-1", "--summary", "s", "--raised-by", "worker-1", check=True,
        )
        self.run_tool("resolve", register, "--decision", "pd-1", "--kind", "tactical", "--note", "n", check=True)
        proc = self.run_tool("resolve", register, "--decision", "pd-1", "--kind", "tactical", "--note", "n2")
        self.assertNotEqual(0, proc.returncode)


if __name__ == "__main__":
    unittest.main()
