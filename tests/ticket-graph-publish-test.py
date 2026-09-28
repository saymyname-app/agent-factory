#!/usr/bin/env python3

import hashlib
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
FAKE_GC = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "gc"

SPEC_DIGEST = "sha256:" + "0" * 64


def scoped_digest(raw: bytes) -> str:
    marker = b"\nlegacy_boundary:"
    start = raw.index(marker) + 1
    return "sha256:" + hashlib.sha256(raw[start:]).hexdigest()


def build_draft(tickets_yaml: str, revises: str | None = None) -> tuple[bytes, str]:
    body = (
        "legacy_boundary:\n"
        "  note: test fixture\n"
        "\n"
        "global_execution_contract:\n"
        "  models: no Astra or Fable\n"
        "\n"
        "tickets:\n"
        f"{tickets_yaml}"
    ).encode("utf-8")
    digest = scoped_digest(b"\n" + body)
    revises_line = f"  revises: {revises}\n" if revises else ""
    header = (
        "artifact:\n"
        "  id: test-graph\n"
        "  state: APPROVED_TICKET_GRAPH_DRAFT\n"
        "  approved_by: Test\n"
        "  approved_at: 2026-09-24\n"
        f"  content_digest: {digest}\n"
        "  digest_scope: UTF-8 bytes from the legacy_boundary key through end of file, with LF line endings\n"
        "  source_spec:\n"
        "    id: test-spec\n"
        "    state: APPROVED_SPEC\n"
        f"    digest: {SPEC_DIGEST}\n"
        "  publication_authorized: true\n"
        f"{revises_line}"
        "\n"
    ).encode("utf-8")
    return header + body, digest


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

    def test_convoy_title_and_labels_come_from_the_draft(self):
        raw, _ = build_draft(
            "  - id: T1\n"
            "    title: One ticket\n"
            "    blocked_by: []\n"
            "    target_rigs: [r]\n"
            "    what_it_delivers: w\n"
            "    acceptance_criteria: [c]\n"
        )
        raw = raw.replace(
            b"  id: test-graph\n",
            b"  id: test-graph\n  title: Ops v2\n  labels: [approved-ticket-graph, ops-v2]\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft.yaml"
            draft.write_bytes(raw)
            capture = root / "graph.json"
            self.invoke("publish", str(draft), env={
                "BD_BIN": str(FAKE_BD),
                "TICKET_GRAPH_CAPTURE": str(capture),
                "TICKET_GRAPH_BD_LOG": str(root / "bd.log"),
            })
            plan = json.loads(capture.read_text(encoding="utf-8"))
        convoy, ticket = plan["nodes"][0], plan["nodes"][1]
        self.assertEqual("Ops v2", convoy["title"])
        self.assertEqual(["approved-ticket-graph", "ops-v2"], convoy["labels"])
        self.assertEqual(["approved-ticket-graph", "delivery-plane", "ops-v2"], ticket["labels"])

    def test_patch_updates_unfinished_tickets_and_creates_new_ones(self):
        old_digest = "sha256:" + "1" * 64
        raw, new_digest = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1 revised\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a revised thing\n"
            "    acceptance_criteria: [does the revised thing]\n"
            "  - id: X2\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X2 new\n"
            "    blocked_by: [X1]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a new thing\n"
            "    acceptance_criteria: [does the new thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                },
            ).stdout)
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(result["ok"])
        self.assertEqual(new_digest, result["graph_digest"])
        self.assertEqual(["X1"], result["patched"])
        self.assertEqual(["X2"], result["created"])
        self.assertEqual("af-x1", result["ids"]["X1"])
        self.assertEqual("af-conv", result["ids"]["_convoy"])
        self.assertIn("X2", result["ids"])
        update_x1 = next(c for c in calls if c[0] == "update" and c[1] == "af-x1")
        self.assertIn("Ticket X1 revised", " ".join(update_x1))
        create_x2 = next(c for c in calls if c[0] == "create")
        self.assertIn(f"blocks:af-x1", ",".join(create_x2))
        update_convoy = next(c for c in calls if c[0] == "update" and c[1] == "af-conv")
        self.assertIn(f"gc.graph_digest={new_digest}", update_convoy)

    def test_publish_wakes_the_mayor_exactly_once_on_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gc_log = root / "gc.log"
            result = json.loads(self.invoke(
                "publish", str(DRAFT), env={
                    "BD_BIN": str(FAKE_BD),
                    "GC_BIN": str(FAKE_GC),
                    "TICKET_GRAPH_CAPTURE": str(root / "graph.json"),
                    "TICKET_GRAPH_BD_LOG": str(root / "bd.log"),
                    "TICKET_GRAPH_GC_LOG": str(gc_log),
                },
            ).stdout)
            calls = [json.loads(line) for line in gc_log.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(calls))
        self.assertEqual(["mail", "send", "mayor", "--notify"], calls[0][:4])
        self.assertIn(result["graph_digest"], " ".join(calls[0]))

    def test_publish_does_not_wake_the_mayor_when_the_graph_transaction_fails(self):
        broken_bd = (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('boom', file=sys.stderr)\n"
            "raise SystemExit(1)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            broken = root / "bd"
            broken.write_text(broken_bd, encoding="utf-8")
            broken.chmod(0o755)
            gc_log = root / "gc.log"
            result = self.invoke(
                "publish", str(DRAFT), env={
                    "BD_BIN": str(broken),
                    "GC_BIN": str(FAKE_GC),
                    "TICKET_GRAPH_GC_LOG": str(gc_log),
                },
                check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(gc_log.exists())

    def test_patch_wakes_the_mayor_exactly_once_on_success(self):
        old_digest = "sha256:" + "3" * 64
        raw, new_digest = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1 revised\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a revised thing\n"
            "    acceptance_criteria: [does the revised thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            gc_log = root / "gc.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), env={
                    "BD_BIN": str(FAKE_BD),
                    "GC_BIN": str(FAKE_GC),
                    "TICKET_GRAPH_BD_LOG": str(root / "bd.log"),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                    "TICKET_GRAPH_GC_LOG": str(gc_log),
                },
            ).stdout)
            calls = [json.loads(line) for line in gc_log.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(calls))
        self.assertEqual(["mail", "send", "mayor", "--notify"], calls[0][:4])
        self.assertIn(new_digest, " ".join(calls[0]))

    def test_patch_does_not_wake_the_mayor_when_it_refuses_a_closed_ticket(self):
        old_digest = "sha256:" + "2" * 64
        raw, _ = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1 revised\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a revised thing\n"
            "    acceptance_criteria: [does the revised thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "closed", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            gc_log = root / "gc.log"
            result = self.invoke(
                "patch", str(draft_path), env={
                    "BD_BIN": str(FAKE_BD),
                    "GC_BIN": str(FAKE_GC),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                    "TICKET_GRAPH_GC_LOG": str(gc_log),
                },
                check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(gc_log.exists())
        self.assertIn("already delivered", result.stderr)
        self.assertIn("cannot modify a closed ticket", result.stderr)


if __name__ == "__main__":
    unittest.main()
