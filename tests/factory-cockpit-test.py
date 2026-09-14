#!/usr/bin/env python3

import sys
import tempfile
import threading
import unittest
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    FactoryCollector,
    ProductMemory,
    ProductReferenceReader,
    POBridge,
    QueueBridge,
    MayorBridge,
    SnapshotCache,
    SourceError,
    TokenReader,
    _last_matching_json,
    _safe_identifier,
    load_product_config,
    _human_objective,
    _human_phase,
)


class FakeRunner:
    def __init__(self, fail_factory=False):
        self.fail_factory = fail_factory
        self.calls = []
        self.responses = {
            ("gc", "status", "--json"): {
                "running": True,
                "city_name": "agent-factory",
                "health": {"usable": True},
                "rigs": [],
            },
            ("gc", "session", "list", "--json"): {
                "sessions": [
                    {
                        "id": "af-mayor",
                        "alias": "mayor",
                        "template": "mayor",
                        "state": "active",
                        "last_active": "2026-09-14T10:00:00Z",
                    },
                    {
                        "id": "af-dog",
                        "alias": "bd.dog-1",
                        "template": "bd.dog",
                        "title": "bd.dog-1",
                        "state": "active",
                        "created_at": "2026-09-14T09:55:00Z",
                        "last_active": "2026-09-14T10:01:00Z",
                    },
                    {
                        "id": "af-control",
                        "alias": "core.control-dispatcher",
                        "template": "core.control-dispatcher",
                        "state": "active",
                    },
                ]
            },
            ("gc", "bd", "show", "af-1vr4", "--json"): [{
                "id": "af-1vr4",
                "metadata": {
                    "gc.current_jit": "smf-now",
                    "gc.last_delivered": "smb-done",
                    "gc.needs_benjamin": "none",
                    "gc.current_workflow": "smf-flow",
                },
            }],
            (str(ROOT / "bin" / "saymyname-product-queue"), "list", "--json"): [{
                "position": 1,
                "id": "af-next",
                "title": "Simplifier le premier écran",
                "state": "queued",
                "urgency": "normal",
                "goal": "af-u8id",
            }],
            ("bd", "list", "--status", "in_progress", "--limit", "0", "--json"): [{
                "id": "af-ui",
                "title": "Create the human cockpit",
                "status": "in_progress",
                "created_at": "2026-09-14T09:00:00Z",
            }],
            (
                "bd",
                "list",
                "--all",
                "--label-any",
                "product-goal,roadmap,product-queue,jit",
                "--limit",
                "0",
                "--json",
            ): [
                {
                    "id": "af-goal",
                    "title": "Rendre l'onboarding autonome",
                    "status": "open",
                    "priority": 1,
                    "issue_type": "feature",
                    "labels": ["product-goal", "roadmap"],
                },
                {
                    "id": "af-internal",
                    "title": "Internal coordination",
                    "status": "in_progress",
                    "issue_type": "epic",
                    "labels": ["product-goal", "coordination"],
                },
            ],
            ("gc", "bd", "show", "smf-now", "--json"): [{
                "id": "smf-now",
                "title": "Finaliser l’onboarding sans organisation",
                "status": "open",
                "created_at": "2026-09-14T08:00:00Z",
                "updated_at": "2026-09-14T09:59:00Z",
                "metadata": {
                    "gc.current_workflow": "smf-flow",
                    "gc.work_outcome": "shipped",
                },
            }],
            ("gc", "bd", "show", "smb-done", "--json"): [{
                "id": "smb-done",
                "title": "Sécuriser les tentatives OTP",
                "closed_at": "2026-09-14T07:00:00Z",
                "metadata": {
                    "gc.pr_number": 33,
                    "gc.work_outcome": "shipped",
                    "gc.postmerge_ci_conclusion": "success",
                },
            }],
            ("gc", "bd", "show", "af-dog", "--json"): [{
                "id": "af-dog",
                "metadata": {"gc.trigger_bead_id": "af-clean"},
            }],
            ("gc", "bd", "show", "af-clean", "--json"): [{
                "id": "af-clean",
                "title": "mol-dog-stale-db",
            }],
        }

    def json(self, *args):
        self.calls.append(args)
        if self.fail_factory and args == ("gc", "status", "--json"):
            raise SourceError("factory unavailable")
        if args not in self.responses:
            raise AssertionError(f"Unexpected command: {args}")
        return self.responses[args]


class FakeGasCity:
    def json(self, path):
        if path == "/v0/city/agent-factory/workflow/smf-flow":
            return {
                "beads": [
                    {"kind": "workflow", "status": "completed"},
                    {"kind": "task", "status": "completed"},
                    {"kind": "workflow-finalize", "status": "completed"},
                ]
            }
        if path == "/v0/city/agent-factory/session/af-mayor/transcript":
            return {
                "turns": [
                    {"role": "user", "text": "system bootstrap"},
                    {
                        "role": "user",
                        "text": "[Cockpit Benjamin] Est-ce que tout va bien ?",
                        "timestamp": "2026-09-14T10:00:00Z",
                    },
                    {"role": "assistant", "text": "[thinking]"},
                    {
                        "role": "assistant",
                        "text": "Oui, sauf une livraison à finaliser.",
                        "timestamp": "2026-09-14T10:00:02Z",
                    },
                ]
            }
        raise AssertionError(path)


class FactoryCockpitTest(unittest.TestCase):
    def test_saymyname_governance_domains_and_inventory_are_complete(self):
        memory = ProductMemory().collect()
        pending = [item for item in memory["decisions"] if item["status"] == "pending"]
        counts = {domain: sum(item.get("domain") == domain for item in pending) for domain in ("enterprise", "product", "project")}
        self.assertEqual({"enterprise": 5, "product": 2, "project": 3}, counts)
        self.assertGreaterEqual(len(memory["view_inventory"]), 10)
        self.assertEqual(0, memory["inventory_freshness"]["model_calls"])
        self.assertEqual(7, len(memory["delivery_workflow"]))
        self.assertEqual(4, len(memory["business"]["objectives"]))
        self.assertGreaterEqual(len(memory["product_reference"]), 7)
        self.assertTrue(all(item["state"] == "ready" for item in memory["product_reference"]))
        self.assertEqual(5, len(memory["journeys"]))
        self.assertTrue(memory["project_graph"]["nodes"][0]["sources"])
        related = next(item for item in pending if item["title"] == "Premier connecteur externe")
        self.assertTrue(related["capabilities"])
        self.assertTrue(related["journeys"] or related["roadmap"])

    def test_product_config_rejects_dangling_graph_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "product.json"
            config_path.write_text(json.dumps({
                "schema_version": 2,
                "slug": "test-product",
                "name": "Test Product",
                "strategy": "docs/products/saymyname/PRODUCT_STRATEGY.md",
                "decisions": "docs/products/saymyname/DECISIONS.md",
                "project_inventory": "docs/products/saymyname/PROJECT_INVENTORY.md",
                "design_governance": "docs/products/saymyname/DESIGN_GOVERNANCE.md",
                "po_workspace": "/tmp/test-product",
                "queue_command": ["bin/test-queue"],
                "queue_mutation_command": ["bin/test-queue"],
                "capabilities": [{"id": "known", "title": "Known", "area": "Core", "roadmap": 1, "source_refs": ["reference"], "decision_refs": []}],
                "relations": [["known", "missing"]],
                "journeys": [],
                "business_objectives": [],
                "product_reference": [{"id": "reference", "title": "Reference", "summary": "Summary", "status": "live", "status_label": "Live", "sources": [{"path": "docs/products/saymyname/PRODUCT_STRATEGY.md", "sections": ["Product thesis"]}]}],
                "view_inventory": [],
                "delivery_workflow": [],
            }), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "Relation"):
                load_product_config(config_path)

    def test_product_reference_is_structured_safe_and_has_provenance(self):
        reader = ProductReferenceReader()
        result = reader.get("vision")
        self.assertEqual("ready", result["state"])
        self.assertEqual(0, result["model_calls"])
        document = result["documents"][0]
        self.assertEqual("docs/products/saymyname/PRODUCT_STRATEGY.md", document["configured_path"])
        self.assertRegex(document["sha256"], r"^[0-9a-f]{64}$")
        blocks = [block for section in document["sections"] for block in section["blocks"]]
        self.assertIn("heading", {block["type"] for block in blocks})
        self.assertIn("table", {block["type"] for block in blocks})
        anchors = [block["anchor"] for block in blocks if block["type"] == "heading"]
        self.assertEqual(len(anchors), len(set(anchors)))

    def test_product_reference_rejects_active_external_and_traversal_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            target = root / "target.md"
            target.write_text("# Target\n\n## Safe target\n\nSafe.\n", encoding="utf-8")
            config = {
                "product_reference": [{
                    "id": "safe", "title": "Safe", "summary": "Safe reference",
                    "status": "live", "status_label": "Live",
                    "sources": [
                        {"path": "source.md", "sections": ["Section"]},
                        {"path": "target.md", "sections": ["Safe target"]},
                    ],
                }],
            }
            source.write_text(
                "# Source\n\n## Section\n\nA <strong>safe</strong> [link](target.md#safe-target).\n",
                encoding="utf-8",
            )
            reader = ProductReferenceReader(config, root)
            result = reader.get("safe")
            paragraph = result["documents"][0]["sections"][0]["blocks"][1]
            self.assertNotIn("<strong>", str(paragraph))
            self.assertEqual("safe", next(part for part in paragraph["inlines"] if part["type"] == "link")["reference_id"])

            for unsafe in (
                "[outside](https://example.com)",
                "[traversal](../secret.md)",
                '<script>alert("x")</script>',
                '<img src=x onerror="alert(1)">',
            ):
                source.write_text(f"# Source\n\n## Section\n\n{unsafe}\n", encoding="utf-8")
                with self.assertRaises(SourceError, msg=unsafe):
                    reader.get("safe")

    def test_queue_bridge_allows_only_structured_record_actions(self):
        inventory = [{
            "position": 1, "id": "af-next", "title": "Next", "state": "queued",
            "urgency": "normal", "goal": "af-goal",
        }]

        def execute(command, **kwargs):
            if command[-2:] == ["list", "--json"]:
                return subprocess.CompletedProcess(command, 0, json.dumps(inventory), "")
            return subprocess.CompletedProcess(command, 0, "UPDATED", "")

        config = load_product_config()
        cases = [
            ("add", {"title": "Outcome", "why": "Useful", "acceptance": "Observable", "urgency": "normal"}),
            ("move", {"id": "af-next", "position": 1}),
            ("urgency", {"id": "af-next", "urgency": "urgent"}),
            ("pause", {"id": "af-next", "reason": "Waiting for evidence"}),
            ("resume", {"id": "af-next"}),
            ("cancel", {"id": "af-next", "reason": "No longer useful", "confirmed": True}),
        ]
        for action, payload in cases:
            result = QueueBridge(config, execute).mutate(action, payload)
            self.assertEqual(0, result["model_calls"])
            self.assertEqual(action, result["action"])
        bridge = QueueBridge(config, execute)
        with self.assertRaisesRegex(ValueError, "interdite"):
            bridge.mutate("materialize", {"id": "af-next"})
        with self.assertRaisesRegex(ValueError, "Champs"):
            bridge.mutate("move", {"id": "af-next", "position": 1, "command": "gc sling"})
        with self.assertRaisesRegex(ValueError, "confirmée"):
            bridge.mutate("cancel", {"id": "af-next", "reason": "No", "confirmed": False})

    def test_po_console_creates_one_on_demand_session_per_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def execute(command, **kwargs):
                calls.append(command)
                output = Path(command[command.index("-o") + 1])
                output.write_text("Voici les options produit.", encoding="utf-8")
                return subprocess.CompletedProcess(
                    command, 0,
                    stdout=json.dumps({"type": "thread.started", "thread_id": "01po-thread"}) + "\n",
                    stderr="",
                )

            bridge = POBridge(
                load_product_config(), Path(directory) / "po.json", execute
            )
            decision_id = next(
                item["id"] for item in bridge.memory.collect()["decisions"]
                if item["status"] == "pending"
            )
            untouched = bridge.conversation(decision_id)
            self.assertEqual("not_started", untouched["status"])
            self.assertIsNone(untouched["thread_id"])
            self.assertEqual([], calls)
            result = bridge.submit("Aide-moi à décider", "discuss", decision_id)
            self.assertTrue(result["accepted"])
            for _ in range(100):
                if bridge.conversation(decision_id)["status"] != "running":
                    time.sleep(0.01)
                if bridge.conversation(decision_id)["status"] == "idle":
                    break
            conversation = bridge.conversation(decision_id)
            self.assertEqual("01po-thread", conversation["thread_id"])
            self.assertEqual("Voici les options produit.", conversation["messages"][-1]["text"])
            index = bridge.index()
            self.assertEqual(0, index["model_calls"])
            self.assertEqual(decision_id, index["conversations"][0]["decision_id"])
            self.assertEqual("PO", index["conversations"][0]["last_role"])
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", calls[0])
            self.assertIn("DISCUSS", calls[0][-1])
            general = bridge.new_conversation()
            self.assertFalse(general["session_created"])
            self.assertEqual("not_started", bridge.conversation(conversation_key=general["key"])["status"])
            self.assertEqual(1, len(bridge.conversation(decision_id)["conversations"]))

    def test_product_memory_projects_roadmap_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            strategy = root / "strategy.md"
            decisions = root / "decisions.md"
            strategy.write_text(
                "# Product\n\n## Product thesis\n\nA useful product.\n\n"
                "## Product roadmap\n\n1. First outcome.\n2. Second outcome.\n\nItems remain queued.\n\n"
                "## Human decisions still required\n\n- Choose the pilot.\n",
                encoding="utf-8",
            )
            decisions.write_text(
                "# Decisions\n\n## Accepted\n\n### 2026-09-14 — Keep it simple\n\nA durable choice.\n\n"
                "## Open\n\n### Product\n\n- **Choose the pilot** — Decide who should test.\n",
                encoding="utf-8",
            )
            result = ProductMemory(strategy, decisions).collect()
            self.assertEqual(2, len(result["roadmap"]))
            self.assertEqual("First outcome.", result["roadmap"][0]["title"])
            self.assertEqual(2, len(result["decisions"]))
            self.assertEqual("pending", result["decisions"][0]["status"])
            self.assertEqual("product", result["decisions"][0]["domain"])

    def test_identifiers_are_strict(self):
        self.assertEqual("af-u8id.1", _safe_identifier("af-u8id.1"))
        with self.assertRaises(ValueError):
            _safe_identifier("../secret")

    def test_last_token_record_and_provider_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_dir = root / ".codex" / "sessions" / "2026" / "09" / "14"
            codex_dir.mkdir(parents=True)
            record = codex_dir / "rollout-session-key.jsonl"
            record.write_text(
                json.dumps({"type": "token_usage_record", "payload": {"thread_token_usage": {"input_tokens": 8, "cached_input_tokens": 5, "output_tokens": 3, "reasoning_output_tokens": 1, "total_tokens": 11}}}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual("token_usage_record", _last_matching_json(record, "token_usage_record")["type"])

            class TokenRunner:
                def json(self, *args):
                    return {"sessions": [{"id": "af-m", "alias": "mayor", "provider": "codex", "session_key": "session-key"}]}

            result = TokenReader(TokenRunner(), root).collect()
            self.assertEqual(11, result["factory"]["known_total_tokens"])
            self.assertEqual("exact", result["factory"]["sessions"][0]["confidence"])
            self.assertEqual(0, result["monitoring"]["tokens"])

    def test_stale_snapshot_returns_immediately_while_refreshing(self):
        refresh_started = threading.Event()
        refresh_release = threading.Event()

        class Collector:
            calls = 0

            def collect(self):
                self.calls += 1
                if self.calls == 2:
                    refresh_started.set()
                    refresh_release.wait(timeout=2)
                return {"version": self.calls}

        collector = Collector()
        cache = SnapshotCache(collector, ttl=0)
        self.assertEqual(1, cache.get()["version"])
        self.assertEqual(1, cache.get()["version"])
        self.assertTrue(refresh_started.wait(timeout=1))
        refresh_release.set()
        with cache.condition:
            self.assertTrue(cache.condition.wait_for(lambda: not cache.refreshing, timeout=1))
            self.assertEqual(2, cache.value["version"])

    def test_human_projection_and_zero_token_contract(self):
        result = FactoryCollector(FakeRunner(), FakeGasCity()).collect()
        self.assertEqual("À finaliser par le Mayor", result["focus"]["state_label"])
        self.assertEqual(2, result["focus"]["steps"]["completed"])
        self.assertEqual(2, result["focus"]["steps"]["total"])
        self.assertEqual(0, result["zero_token_contract"]["model_calls"])
        self.assertEqual(1, len(result["queue"]))
        self.assertEqual(33, result["last_delivery"]["pr"])
        self.assertEqual("success", result["last_delivery"]["ci"])
        self.assertEqual(2, len(result["agents"]))
        self.assertEqual(1, len(result["product_work"]))
        self.assertEqual("Rendre l'onboarding autonome", result["product_work"][0]["title"])
        self.assertGreaterEqual(len(result["decision_aids"]), 1)
        self.assertEqual("Agent de maintenance", result["agents"][1]["role"])
        self.assertEqual(
            "Maintenir la santé du magasin de tâches",
            result["agents"][1]["objective"],
        )
        self.assertNotIn("control-dispatcher", str(result["agents"]))
        self.assertIn("control-dispatcher", str(result["infrastructure"]))

    def test_source_failure_is_visible_and_fails_factory_health_closed(self):
        result = FactoryCollector(FakeRunner(fail_factory=True), FakeGasCity()).collect()
        self.assertEqual("down", result["factory"]["state"])
        self.assertFalse(result["sources"]["factory"])
        self.assertIn("factory unavailable", result["warnings"][0])

    def test_unknown_formula_is_humanized_without_model(self):
        self.assertEqual("Review stale branches", _human_objective("mol-review-stale-branches"))
        self.assertEqual(
            "L’agent réalise, vérifie et prépare la livraison",
            _human_phase("Read assignment, implement, verify, commit, and close"),
        )

    def test_closed_focus_does_not_reuse_stale_workflow_progress(self):
        runner = FakeRunner()
        runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]["metadata"][
            "gc.current_jit"
        ] = "none"
        result = FactoryCollector(runner, FakeGasCity()).collect()
        self.assertEqual("idle", result["focus"]["state"])
        self.assertEqual(0, result["focus"]["steps"]["total"])

    def test_mayor_conversation_exposes_only_cockpit_exchange(self):
        bridge = MayorBridge(FakeRunner(), FakeGasCity())
        result = bridge.conversation()
        self.assertEqual(2, len(result["messages"]))
        self.assertEqual("Benjamin", result["messages"][0]["role"])
        self.assertEqual("Mayor", result["messages"][1]["role"])
        self.assertNotIn("system bootstrap", str(result))

    def test_mayor_submit_is_bounded_and_non_interruptive(self):
        runner = FakeRunner()
        command = (
            "gc",
            "session",
            "submit",
            "mayor",
            "[Cockpit Benjamin] Explique l'état de l'usine",
            "--intent",
            "default",
            "--json",
        )
        runner.responses[command] = {"delivery": "queued"}
        bridge = MayorBridge(runner, FakeGasCity())
        result = bridge.submit("Explique l'état de l'usine", "question")
        self.assertTrue(result["accepted"])
        self.assertIn(command, runner.calls)
        with self.assertRaises(RuntimeError):
            bridge.submit("Une autre question", "question")
        with self.assertRaises(ValueError):
            MayorBridge(runner, FakeGasCity()).submit("x", "interrupt_now")


if __name__ == "__main__":
    unittest.main()
