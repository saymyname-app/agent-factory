#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "bin" / "ticket-graph-publish"
DRAFT = ROOT / "docs" / "planning" / "agent-factory-project-agnostic-refactor-ticket-graph-draft.yaml"
FAKE_BD = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "bd"


class TicketGraphPublishTest(unittest.TestCase):
    def invoke(self, *args, env=None, check=True):
        return subprocess.run(
            (str(PUBLISHER), *args), cwd=ROOT, env={**os.environ, **(env or {})},
            text=True, capture_output=True, check=check,
        )

    def test_validate_accepts_the_exact_approved_graph(self):
        result = json.loads(self.invoke("validate", str(DRAFT)).stdout)
        self.assertEqual((True, 18, 19, 59), (
            result["ok"], result["ticket_count"], result["node_count"], result["edge_count"],
        ))
        self.assertEqual(
            "sha256:53a663ab5841e8e43dd05f5a4c470496ce50613b3b9690b5102df881c83be417",
            result["graph_digest"],
        )

    def test_validate_rejects_content_changed_after_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.yaml"
            changed.write_text(DRAFT.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            result = self.invoke("validate", str(changed), check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("draft digest mismatch", result.stderr)

    def test_publish_uses_one_graph_transaction_with_positive_routing_and_convoy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "graph.json"
            log = root / "bd.log"
            result = json.loads(self.invoke(
                "publish", str(DRAFT), env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_CAPTURE": str(capture),
                    "TICKET_GRAPH_BD_LOG": str(log),
                },
            ).stdout)
            plan = json.loads(capture.read_text(encoding="utf-8"))
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(result["ok"])
        self.assertEqual(19, len(result["ids"]))
        self.assertEqual(["list", "create"], [call[0] for call in calls])
        self.assertEqual("--graph", calls[1][1])
        keys = {node["key"] for node in plan["nodes"]}
        self.assertEqual({"_convoy", *[f"P{i:02d}" for i in range(1, 7)],
                          *[f"B{i:02d}" for i in range(1, 13)]}, keys)
        self.assertNotIn("C01", keys)
        self.assertNotIn("V01", keys)
        for node in plan["nodes"]:
            self.assertEqual("delivery", node["metadata"]["gc.plane"])
            self.assertEqual(result["graph_digest"], node["metadata"]["gc.graph_digest"])
            self.assertEqual("true", node["metadata"]["gc.publication_validated"])
            if node["key"] != "_convoy":
                self.assertEqual(
                    "pr-ci-merged-v1", node["metadata"]["gc.delivery_contract"]
                )
        tracks = [edge for edge in plan["edges"] if edge["type"] == "tracks"]
        self.assertEqual(18, len(tracks))
        self.assertTrue(all(edge["from_key"] == "_convoy" for edge in tracks))


if __name__ == "__main__":
    unittest.main()
