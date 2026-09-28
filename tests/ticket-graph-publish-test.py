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
FAKE_ESCALATION_DOOR = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "escalation-door"

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
                "patch", str(draft_path), "--author", "Test", "--reason", "test patch", env={
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
        self.assertIn("gc.patch_author=Test", update_convoy)
        self.assertIn("gc.patch_reason=test patch", update_convoy)
        self.assertIn("PATCH by Test: test patch", update_convoy)

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
                "patch", str(draft_path), "--author", "Test", "--reason", "test patch", env={
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
                "patch", str(draft_path), "--author", "Test", "--reason", "test patch", env={
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

    # --- O09: decision 8 (ADR-0028 amended) ---------------------------------

    def test_patch_reorders_dependencies_between_unfinished_tickets(self):
        old_digest = "sha256:" + "4" * 64
        raw, _ = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1\n"
            "    blocked_by: [X2]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does the thing]\n"
            "  - id: X2\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X2\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does another thing\n"
            "    acceptance_criteria: [does the other thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1", "gc.blocked_by": "",
            }},
            {"id": "af-x2", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X2", "gc.blocked_by": "X1",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), "--author", "Test", "--reason", "reorder", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                },
            ).stdout)
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(result["ok"])
        self.assertEqual(["X1", "X2"], result["patched"])
        self.assertIn(["dep", "add", "af-x1", "af-x2"], calls)
        self.assertIn(["dep", "remove", "af-x2", "af-x1"], calls)

    def test_patch_merges_an_unfinished_ticket_into_another(self):
        old_digest = "sha256:" + "5" * 64
        raw, new_digest = build_draft(
            "  - id: Y1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket Y1 absorbs Y2\n"
            "    blocked_by: []\n"
            "    merges: [Y2]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does the merged thing\n"
            "    acceptance_criteria: [does the merged thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-y1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "Y1", "gc.blocked_by": "",
            }},
            {"id": "af-y2", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "Y2", "gc.blocked_by": "",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), "--author", "Test", "--reason", "merge Y2 into Y1", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                },
            ).stdout)
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(result["ok"])
        self.assertEqual({"Y2": "af-y1"}, result["merged"])
        close_y2 = next(c for c in calls if c[0] == "update" and c[1] == "af-y2")
        self.assertIn("--status", close_y2)
        self.assertIn("closed", close_y2)
        self.assertIn("gc.merged_into=af-y1", close_y2)
        self.assertIn("MERGED by Test: merge Y2 into Y1", close_y2)

    def test_patch_refuses_to_merge_an_already_closed_ticket(self):
        old_digest = "sha256:" + "6" * 64
        raw, _ = build_draft(
            "  - id: Y1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket Y1 absorbs Y2\n"
            "    blocked_by: []\n"
            "    merges: [Y2]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does the merged thing\n"
            "    acceptance_criteria: [does the merged thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-y1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "Y1", "gc.blocked_by": "",
            }},
            {"id": "af-y2", "status": "closed", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "Y2", "gc.blocked_by": "",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            result = self.invoke(
                "patch", str(draft_path), "--author", "Test", "--reason", "merge Y2 into Y1", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                },
                check=False,
            )
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        self.assertNotEqual(0, result.returncode)
        self.assertIn("already delivered", result.stderr)
        self.assertEqual(["list"], [call[0] for call in calls])

    def test_patch_supersedes_an_unfinished_ticket_with_a_new_one(self):
        old_digest = "sha256:" + "7" * 64
        raw, new_digest = build_draft(
            "  - id: Z2\n"
            "    kind: vertical_slice\n"
            "    title: Ticket Z2 supersedes Z1\n"
            "    blocked_by: []\n"
            "    supersedes: Z1\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does the replacement thing\n"
            "    acceptance_criteria: [does the replacement thing]\n",
            revises=old_digest,
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-z1", "status": "open", "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "Z1", "gc.blocked_by": "",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), "--author", "Test", "--reason", "supersede Z1 with Z2", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                },
            ).stdout)
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(result["ok"])
        z2_id = result["ids"]["Z2"]
        self.assertEqual({"Z1": z2_id}, result["superseded"])
        close_z1 = next(c for c in calls if c[0] == "update" and c[1] == "af-z1")
        self.assertIn(f"gc.superseded_by={z2_id}", close_z1)
        self.assertIn("SUPERSEDED by Test: supersede Z1 with Z2", close_z1)

    def test_reslice_patch_refuses_and_escalates_when_acceptance_criteria_change(self):
        old_digest = "sha256:" + "8" * 64
        raw, new_digest = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does a NEW thing]\n",
            revises=old_digest,
        )
        old_description = (
            "## What to build\n\ndoes a thing\n\n"
            "## Acceptance criteria\n\n- [ ] does the old thing\n\n"
            "## Target rigs\n\nfixture_city\n\n"
            "## Autonomous execution contract\n\n- models: none\n"
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "open", "description": old_description, "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1", "gc.blocked_by": "",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            escalation_log = root / "escalation.log"
            result = self.invoke(
                "patch", str(draft_path), "--author", "Mayor", "--reason", "reslice", "--reslice", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                    "ESCALATION_DOOR_BIN": str(FAKE_ESCALATION_DOOR),
                    "TICKET_GRAPH_ESCALATION_LOG": str(escalation_log),
                },
                check=False,
            )
            escalation_calls = [json.loads(line) for line in escalation_log.read_text(encoding="utf-8").splitlines()]
            # nothing was written: only the read-only `list` call happened
            bd_calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertNotEqual(0, result.returncode)
        self.assertIn("acceptance criteria changed", result.stderr)
        self.assertIn("escalated", result.stderr)
        self.assertEqual(1, len(escalation_calls))
        self.assertEqual(["benjamin", "af-conv"], escalation_calls[0][:2])
        self.assertIn("X1", escalation_calls[0][2])
        self.assertEqual(["list"], [call[0] for call in bd_calls])

    def test_reslice_patch_succeeds_when_acceptance_criteria_are_unchanged(self):
        old_digest = "sha256:" + "9" * 64
        raw, new_digest = build_draft(
            "  - id: X1\n"
            "    kind: vertical_slice\n"
            "    title: Ticket X1 renamed\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does the same thing]\n",
            revises=old_digest,
        )
        old_description = (
            "## What to build\n\ndoes a thing\n\n"
            "## Acceptance criteria\n\n- [ ] does the same thing\n\n"
            "## Target rigs\n\nfixture_city\n\n"
            "## Autonomous execution contract\n\n- models: none\n"
        )
        existing = [
            {"id": "af-conv", "status": "open", "metadata": {"gc.graph_digest": old_digest}},
            {"id": "af-x1", "status": "open", "description": old_description, "metadata": {
                "gc.graph_digest": old_digest, "gc.ticket_id": "X1", "gc.blocked_by": "",
            }},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "revised.yaml"
            draft_path.write_bytes(raw)
            log = root / "bd.log"
            escalation_log = root / "escalation.log"
            result = json.loads(self.invoke(
                "patch", str(draft_path), "--author", "Mayor", "--reason", "reslice", "--reslice", env={
                    "BD_BIN": str(FAKE_BD),
                    "TICKET_GRAPH_BD_LOG": str(log),
                    "TICKET_GRAPH_EXISTING": json.dumps(existing),
                    "ESCALATION_DOOR_BIN": str(FAKE_ESCALATION_DOOR),
                    "TICKET_GRAPH_ESCALATION_LOG": str(escalation_log),
                },
            ).stdout)
            escalated = escalation_log.exists()
        self.assertTrue(result["ok"])
        self.assertEqual(["X1"], result["patched"])
        self.assertFalse(escalated)


if __name__ == "__main__":
    unittest.main()
