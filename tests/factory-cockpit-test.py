#!/usr/bin/env python3

import sys
import tempfile
import threading
import unittest
import json
import http.client
import subprocess
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    FactoryCollector,
    DeliveryEvidenceReader,
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
    _today_projection,
    load_product_config,
    _human_objective,
    _human_phase,
    _product_bead,
    handler_factory,
)
from factory_state import (  # noqa: E402
    CONTRACT as HUMAN_STATE_CONTRACT,
    StateContractError,
    candidate_record_lifecycle,
    project_candidate,
    project_human_state,
)


class FakeRunner:
    def __init__(self, fail_factory=False):
        self.fail_factory = fail_factory
        self.calls = []
        self.responses = {
            ("gc", "status", "--json"): {
                "ok": True,
                "running": True,
                "city_name": "agent-factory",
                "health": {"usable": True, "degraded": False},
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
            (str(ROOT / "bin" / "saymyname-product-queue"), "list", "--json"): [project_candidate({
                "position": 1,
                "id": "af-next",
                "title": "Simplifier le premier écran",
                "queue_state": "queued",
                "technical_status": "deferred",
                "urgency": "normal",
                "goal": "af-u8id",
            })],
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


class ActiveWorkflowGasCity(FakeGasCity):
    def __init__(self, assignee="codex-workflow"):
        self.assignee = assignee

    def json(self, path):
        if path == "/v0/city/agent-factory/workflow/smf-flow":
            return {
                "beads": [
                    {"kind": "workflow", "status": "active"},
                    {
                        "kind": "task",
                        "status": "in_progress",
                        "title": "Implement the bounded result",
                        "assignee": self.assignee,
                    },
                ]
            }
        return super().json(path)


class FactoryCockpitTest(unittest.TestCase):
    def test_saymyname_governance_domains_and_inventory_are_complete(self):
        memory = ProductMemory().collect()
        pending = [item for item in memory["decisions"] if item["status"] == "pending"]
        counts = {domain: sum(item.get("domain") == domain for item in pending) for domain in ("enterprise", "product", "project")}
        self.assertEqual({"enterprise": 5, "product": 1, "project": 3}, counts)
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
                "status_command": ["bin/test-product-product-status"],
                "queue_command": ["bin/test-product-product-queue", "list", "--json"],
                "queue_mutation_command": ["bin/test-product-product-queue"],
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

    def test_product_config_rejects_an_arbitrary_queue_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "product.json"
            value = json.loads((ROOT / "config" / "products" / "saymyname.json").read_text(encoding="utf-8"))
            value["queue_mutation_command"] = ["/bin/sh"]
            config_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "relatif"):
                load_product_config(config_path)

            value["queue_command"] = ["bin/factory-cockpit", "list", "--json"]
            value["queue_mutation_command"] = ["bin/factory-cockpit"]
            config_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "contrats dédiés"):
                load_product_config(config_path)

    def test_product_config_rejects_invalid_decision_blocker_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "product.json"
            value = json.loads((ROOT / "config" / "products" / "saymyname.json").read_text(encoding="utf-8"))
            value["decision_blockers"] = [{"work_ref": "../af-hxji", "decision_ref": "Visibilité et conservation des groupes"}]
            config_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "blocage décisionnel"):
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

    def test_product_reference_anchors_distinguish_equal_stems_in_different_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for folder in ("one", "two"):
                path = root / folder / "reference.md"
                path.parent.mkdir()
                path.write_text("# Reference\n\n## Shared section\n\nSafe.\n", encoding="utf-8")
                sources.append({"path": f"{folder}/reference.md", "sections": ["Shared section"]})
            config = {
                "product_reference": [{
                    "id": "safe", "title": "Safe", "summary": "Safe reference",
                    "status": "live", "status_label": "Live", "sources": sources,
                }],
            }
            documents = ProductReferenceReader(config, root).get("safe")["documents"]
            anchors = [document["sections"][0]["anchor"] for document in documents]
            self.assertEqual(2, len(set(anchors)))

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

    def test_delivery_evidence_uses_exact_status_contract_without_a_model(self):
        class Runner:
            def text(self, *args):
                self.args = args
                return (
                    "SAYMYNAME\nCURRENT: Current outcome — implementation\nCURRENT AGENT: codex-1\n"
                    "LAST DELIVERED: Delivered outcome — PR 42 — merged as abcdef123456; CI green (3 checks)\n"
                    "NEXT: Next outcome\nNEEDS BENJAMIN: none\n"
                )

        runner = Runner()
        result = DeliveryEvidenceReader(load_product_config(), runner).collect()
        self.assertIn("PR 42", result["last_delivered"])
        self.assertIn("CI green", result["last_delivered"])
        self.assertEqual(0, result["model_calls"])
        self.assertEqual(str(ROOT / "bin" / "saymyname-product-status"), runner.args[0])

    def test_http_queue_guard_and_reference_endpoint(self):
        class Cache:
            invalidated = False

            def get(self):
                return {"ok": True}

            def invalidate(self):
                self.invalidated = True

        class Queue:
            calls = []

            def mutate(self, action, payload):
                if action not in {"add", "move", "urgency", "pause", "resume", "cancel"}:
                    raise ValueError("Action de file produit interdite.")
                self.calls.append((action, payload))
                return {"accepted": True, "queue": [], "model_calls": 0}

        class Stub:
            def conversation(self, *args):
                return {}

            def index(self):
                return {}

            def status(self):
                return {}

            def collect(self):
                return {
                    "last_delivered": "Delivered outcome — PR 42 — CI green",
                    "verified_by": "fixture",
                    "model_calls": 0,
                }

        cache, queue = Cache(), Queue()
        handler = handler_factory(
            cache, mayor_bridge=Stub(), detail_reader=Stub(), token_cache=cache,
            po_bridge=Stub(), preview_bridge=Stub(),
            reference_reader=ProductReferenceReader(), queue_bridge=queue,
            delivery_reader=Stub(),
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            body = json.dumps({"action": "resume", "payload": {"id": "af-next"}})
            headers = {
                "Content-Type": "application/json", "X-Factory-Cockpit": "human-queue-record",
                "Origin": f"http://127.0.0.1:{server.server_port}",
            }
            connection.request("POST", "/api/product-queue", body, headers)
            response = connection.getresponse()
            self.assertEqual(202, response.status)
            self.assertIn("object-src 'none'", response.getheader("Content-Security-Policy"))
            response.read()
            self.assertTrue(cache.invalidated)

            connection.request("POST", "/api/product-queue", body, {"Content-Type": "application/json", "Origin": headers["Origin"]})
            self.assertEqual(403, connection.getresponse().status)
            connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            forbidden = json.dumps({"action": "materialize", "payload": {"id": "af-next"}})
            connection.request("POST", "/api/product-queue", forbidden, headers)
            self.assertEqual(400, connection.getresponse().status)
            connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            connection.request("GET", "/api/reference?id=vision")
            response = connection.getresponse()
            value = json.loads(response.read())
            self.assertEqual(200, response.status)
            self.assertEqual("ready", value["state"])
            self.assertEqual(0, value["model_calls"])

            connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
            connection.request("GET", "/api/delivery-evidence")
            response = connection.getresponse()
            value = json.loads(response.read())
            self.assertEqual(200, response.status)
            self.assertIn("PR 42", value["last_delivered"])
            self.assertEqual(0, value["model_calls"])
        finally:
            server.shutdown()
            server.server_close()

    def test_static_product_navigation_accessibility_and_deep_links(self):
        html = (ROOT / "ui" / "factory-cockpit" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "ui" / "factory-cockpit" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "ui" / "factory-cockpit" / "styles.css").read_text(encoding="utf-8")
        self.assertLess(html.index('data-view="today"'), html.index('data-view="project"'))
        self.assertLess(html.index('data-view="project"'), html.index('data-view="roadmap"'))
        self.assertLess(html.index('data-view="roadmap"'), html.index('data-view="decisions"'))
        self.assertIn("<details class=\"nav-more\">", html)
        self.assertIn('for="reference-search"', html)
        self.assertIn("human-queue-record", script)
        self.assertIn("ENTERPRISE_IGNORE_KEY", script)
        self.assertIn("URLSearchParams", script)
        self.assertIn('id="attention-card"', html)
        self.assertNotIn('id="attention-card" tabindex="0"', html)
        self.assertIn('id="open-blocker-decision" class="primary hidden" type="button" aria-label="Ouvrir la décision bloquante"', html)
        self.assertIn('$("open-blocker-decision").addEventListener("click"', script)
        self.assertIn('if (id) openDecisionById(id)', script)
        self.assertIn('blocker?.text || "Aucun blocage effectif."', script)
        self.assertIn('id="health-label"', html)
        self.assertIn('id="activity-label"', html)
        self.assertIn('id="resume-condition"', html)
        self.assertIn("function renderOperationalState(data)", script)
        self.assertNotIn("si cet état persiste", script)
        self.assertNotIn('makeActivatable($("attention-card")', script)
        self.assertIn('[tabindex]:focus-visible', styles)
        self.assertIn('fetch("/api/delivery-evidence"', script)
        self.assertNotIn(".innerHTML", script)
        self.assertIn("@media(max-width:800px)", styles)

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

    def test_today_separates_general_decisions_from_one_effective_blocker(self):
        needs = "Approve or refine the af-hxji contract without changing this exact text."
        decisions = [
            {"id": f"general-{index}", "title": f"General {index}", "status": "pending", "domain": domain}
            for index, domain in enumerate(("enterprise", "enterprise", "product", "project", "project"), 1)
        ]
        decisions.append({
            "id": "pending-product-target",
            "title": "Visibilité et conservation des groupes",
            "status": "pending",
            "domain": "product",
        })
        result = _today_projection(needs, decisions, [{
            "work_ref": "af-hxji",
            "decision_ref": "Visibilité et conservation des groupes",
        }])
        self.assertEqual(5, len(result["general_decisions"]))
        self.assertEqual(needs, result["effective_blockers"][0]["text"])
        self.assertEqual("pending-product-target", result["effective_blockers"][0]["decision_id"])
        self.assertEqual(
            {"enterprise": 2, "product": 1, "project": 2},
            {
                domain: sum(item["domain"] == domain for item in result["general_decisions"])
                for domain in ("enterprise", "product", "project")
            },
        )

    def test_today_reports_zero_blockers_without_losing_general_decisions(self):
        decisions = [
            {"id": f"general-{index}", "title": f"General {index}", "status": "pending", "domain": "product"}
            for index in range(5)
        ]
        result = _today_projection(None, decisions, [])
        self.assertEqual([], result["effective_blockers"])
        self.assertEqual(5, len(result["general_decisions"]))

    def test_today_leaves_ambiguous_blocker_target_unlinked(self):
        needs = "Benjamin must decide before af-hxji can continue."
        decisions = [
            {"id": "one", "title": "One", "status": "pending", "domain": "product"},
            {"id": "two", "title": "Two", "status": "pending", "domain": "project"},
        ]
        result = _today_projection(needs, decisions, [
            {"work_ref": "af-hxji", "decision_ref": "One"},
            {"work_ref": "af-hxji", "decision_ref": "Two"},
        ])
        self.assertEqual(needs, result["effective_blockers"][0]["text"])
        self.assertIsNone(result["effective_blockers"][0]["decision_id"])
        self.assertEqual(2, len(result["general_decisions"]))

    def test_today_leaves_absent_configured_decision_target_unlinked(self):
        needs = "Benjamin must decide before af-hxji can continue without changing this exact text."
        decisions = [
            {"id": "enterprise-open", "title": "Enterprise open", "status": "pending", "domain": "enterprise"},
            {"id": "product-open", "title": "Product open", "status": "pending", "domain": "product"},
            {"id": "project-open", "title": "Project open", "status": "pending", "domain": "project"},
        ]
        result = _today_projection(needs, decisions, [{
            "work_ref": "af-hxji",
            "decision_ref": "Absent durable decision",
        }])
        blocker = result["effective_blockers"][0]
        self.assertEqual(needs, blocker["text"])
        self.assertIsNone(blocker["decision_id"])
        self.assertEqual(
            [{"id": item["id"], "title": item["title"], "domain": item["domain"]} for item in decisions],
            result["general_decisions"],
        )
        script = (ROOT / "ui" / "factory-cockpit" / "app.js").read_text(encoding="utf-8")
        self.assertIn('action.classList.toggle("hidden", !blocker?.decision_id)', script)

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
        self.assertEqual("En finalisation par le Mayor", result["focus"]["state_label"])
        self.assertEqual(2, result["focus"]["steps"]["completed"])
        self.assertEqual(2, result["focus"]["steps"]["total"])
        self.assertEqual(0, result["zero_token_contract"]["model_calls"])
        self.assertEqual(1, len(result["queue"]))
        self.assertEqual("eligible", result["queue"][0]["state"])
        self.assertEqual(HUMAN_STATE_CONTRACT, result["human_state"]["contract"])
        self.assertEqual("available", result["health"]["state"])
        self.assertEqual("mayor_finalization", result["resume"]["mode"])
        self.assertEqual(33, result["last_delivery"]["pr"])
        self.assertEqual("success", result["last_delivery"]["ci"])
        self.assertEqual(2, len(result["agents"]))
        self.assertEqual(1, len(result["product_work"]))
        self.assertEqual("Rendre l'onboarding autonome", result["product_work"][0]["title"])
        self.assertEqual([], result["today"]["effective_blockers"])
        self.assertEqual(9, len(result["today"]["general_decisions"]))
        self.assertGreaterEqual(len(result["decision_aids"]), 1)
        self.assertEqual("Agent de maintenance", result["agents"][1]["role"])
        self.assertEqual(
            "Maintenir la santé du magasin de tâches",
            result["agents"][1]["objective"],
        )
        self.assertNotIn("control-dispatcher", str(result["agents"]))
        self.assertIn("control-dispatcher", str(result["infrastructure"]))

    def test_direct_assignment_uses_exact_active_session_without_a_workflow(self):
        runner = FakeRunner()
        coordination = runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]
        coordination["metadata"]["gc.current_jit"] = "smb-direct"
        coordination["metadata"].pop("gc.current_workflow", None)
        runner.responses[("gc", "bd", "show", "smb-direct", "--json")] = [{
            "id": "smb-direct", "title": "Publish verified French presidents challenge",
            "status": "in_progress", "metadata": {
                "gc.session_id": "af-jqla", "gc.session_name": "codex-af-jqla",
                "gc.routed_to": "saymyname-backend/codex",
            },
        }]
        runner.responses[("gc", "session", "list", "--json")]["sessions"].append({
            "id": "af-jqla", "name": "saymyname-backend/codex-1",
            "qualified_name": "saymyname-backend/codex-1", "state": "active",
            "last_active": "2026-09-15T10:00:00Z",
        })
        result = FactoryCollector(runner, FakeGasCity()).collect()
        self.assertEqual(("working", "active", "saymyname-backend/codex-1"), (
            result["activity"]["state"], result["human_state"]["result"]["state"],
            result["human_state"]["result"]["agent"],
        ))

    def test_direct_assignment_never_infers_an_unrelated_session(self):
        runner = FakeRunner()
        coordination = runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]
        coordination["metadata"]["gc.current_jit"] = "smb-direct"
        coordination["metadata"].pop("gc.current_workflow", None)
        runner.responses[("gc", "bd", "show", "smb-direct", "--json")] = [{
            "id": "smb-direct", "title": "Direct result", "status": "in_progress",
            "metadata": {"gc.session_id": "af-wanted", "gc.session_name": "codex-af-wanted"},
        }]
        runner.responses[("gc", "session", "list", "--json")]["sessions"].append({
            "id": "af-other", "alias": "codex-unrelated", "state": "active",
        })
        result = FactoryCollector(runner, FakeGasCity()).collect()
        self.assertEqual(("materialized", None, "materialized_without_agent"), (
            result["human_state"]["result"]["state"], result["human_state"]["result"]["agent"],
            result["resume"]["mode"],
        ))

    def test_direct_assignment_ambiguity_fails_closed(self):
        runner = FakeRunner()
        coordination = runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]
        coordination["metadata"]["gc.current_jit"] = "smb-direct"
        coordination["metadata"].pop("gc.current_workflow", None)
        runner.responses[("gc", "bd", "show", "smb-direct", "--json")] = [{
            "id": "smb-direct", "title": "Direct result", "status": "in_progress",
            "metadata": {"gc.session_id": "af-duplicate", "gc.session_name": "codex-af-duplicate"},
        }]
        sessions = runner.responses[("gc", "session", "list", "--json")]["sessions"]
        sessions.extend([
            {"id": "af-duplicate", "alias": "worker-one", "state": "active"},
            {"id": "af-duplicate", "alias": "worker-two", "state": "active"},
        ])
        result = FactoryCollector(runner, FakeGasCity()).collect()
        self.assertEqual(("fail_closed", "degraded", False), (
            result["resume"]["mode"], result["health"]["state"], result["sources"]["current"],
        ))
        self.assertTrue(any("plusieurs identifiants" in item for item in result["warnings"]))

    def test_workflow_assignment_uses_one_exact_active_session_for_focus_and_card(self):
        runner = FakeRunner()
        current = runner.responses[("gc", "bd", "show", "smf-now", "--json")][0]
        current["status"] = "in_progress"
        current["metadata"].pop("gc.work_outcome")
        sessions = runner.responses[("gc", "session", "list", "--json")]["sessions"]
        sessions.extend([
            {
                "id": "af-workflow",
                "alias": "codex-workflow",
                "name": "saymyname-backend/codex-1",
                "qualified_name": "saymyname-backend/codex-1",
                "state": "active",
                "title": "Bounded implementation",
            },
            {
                "id": "af-unrelated",
                "alias": "codex-unrelated",
                "state": "active",
                "title": "Unrelated task",
            },
        ])

        result = FactoryCollector(runner, ActiveWorkflowGasCity()).collect()

        self.assertEqual(("working", "active", "saymyname-backend/codex-1"), (
            result["activity"]["state"], result["human_state"]["result"]["state"],
            result["focus"]["agent"],
        ))
        cards = {item["name"]: item for item in result["agents"]}
        self.assertEqual(result["focus"]["title"], cards["codex-workflow"]["objective"])
        self.assertEqual("Unrelated task", cards["codex-unrelated"]["objective"])

    def test_workflow_assignment_never_infers_an_unrelated_session(self):
        runner = FakeRunner()
        current = runner.responses[("gc", "bd", "show", "smf-now", "--json")][0]
        current["status"] = "in_progress"
        current["metadata"].pop("gc.work_outcome")
        runner.responses[("gc", "session", "list", "--json")]["sessions"].append({
            "id": "af-unrelated",
            "alias": "codex-unrelated",
            "state": "active",
        })

        result = FactoryCollector(runner, ActiveWorkflowGasCity()).collect()

        self.assertEqual(("materialized", None, "materialized_without_agent", "available"), (
            result["human_state"]["result"]["state"],
            result["human_state"]["result"]["agent"],
            result["resume"]["mode"], result["health"]["state"],
        ))
        self.assertTrue(all(result["sources"].values()))
        cards = {item["name"]: item for item in result["agents"]}
        self.assertNotEqual(result["focus"]["title"], cards["codex-unrelated"]["objective"])

    def test_workflow_assignment_ambiguity_fails_closed(self):
        runner = FakeRunner()
        current = runner.responses[("gc", "bd", "show", "smf-now", "--json")][0]
        current["status"] = "in_progress"
        current["metadata"].pop("gc.work_outcome")
        sessions = runner.responses[("gc", "session", "list", "--json")]["sessions"]
        sessions.extend([
            {"id": "af-first", "alias": "codex-workflow", "state": "active"},
            {"id": "af-second", "alias": "codex-workflow", "state": "active"},
        ])

        result = FactoryCollector(runner, ActiveWorkflowGasCity()).collect()

        self.assertEqual(("fail_closed", "degraded", False), (
            result["resume"]["mode"], result["health"]["state"],
            result["sources"]["workflow_session"],
        ))
        self.assertTrue(any(
            "plusieurs sessions" in item for item in result["warnings"]
        ))

    def test_human_projection_links_exact_needs_benjamin_decision(self):
        runner = FakeRunner()
        needs = "Approve or refine a design-ready contract for af-hxji, especially admission, profile visibility, revocation, and navigation for the participative event/community journey."
        runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]["metadata"]["gc.needs_benjamin"] = needs
        result = FactoryCollector(runner, FakeGasCity()).collect()
        blocker = result["today"]["effective_blockers"][0]
        target = next(
            item for item in result["product_memory"]["decisions"]
            if item["title"] == "Visibilité et conservation des groupes"
        )
        self.assertEqual(needs, blocker["text"])
        self.assertIsNone(blocker["decision_id"])
        self.assertNotIn(target["id"], {item["id"] for item in result["today"]["general_decisions"]})
        self.assertEqual(0, result["zero_token_contract"]["model_calls"])

    def test_cockpit_exposes_the_exact_persisted_campaign_decision_action(self):
        runner = FakeRunner()
        exact_action = "Valider le périmètre puis demander au Mayor de reprendre."
        coordination = runner.responses[("gc", "bd", "show", "af-1vr4", "--json")][0]
        coordination["metadata"].update({
            "gc.needs_benjamin": "Choisir le périmètre du prochain résultat.",
            "gc.resume_mode": "automatic_campaign",
            "gc.resume_condition": "Le Mayor enchaîne le premier candidat éligible",
            "gc.campaign_mode": "automatic",
            "gc.campaign_state": "blocked",
            "gc.campaign_candidate": "af-cm1l",
            "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
            "gc.campaign_owner": "Benjamin",
            "gc.campaign_action": exact_action,
            "gc.campaign_block_kind": "decision",
            "gc.campaign_cause": "La campagne attend le choix de périmètre.",
            "gc.campaign_wake_state": "none",
            "gc.campaign_failure_count": "0",
        })

        result = FactoryCollector(runner, FakeGasCity()).collect()

        self.assertEqual((exact_action, exact_action, exact_action), (
            result["resume"]["action"], result["campaign"]["action"],
            result["decision_aids"][0]["action"],
        ))
        self.assertEqual(("Benjamin", "La campagne attend le choix de périmètre."), (
            result["campaign"]["owner"], result["campaign"]["cause"],
        ))
        self.assertNotEqual("Répondre à la décision bloquante.", result["resume"]["action"])

    def test_source_failure_is_visible_and_fails_factory_health_closed(self):
        result = FactoryCollector(FakeRunner(fail_factory=True), FakeGasCity()).collect()
        self.assertEqual("down", result["factory"]["state"])
        self.assertEqual("unavailable", result["health"]["state"])
        self.assertEqual("stopped", result["activity"]["state"])
        self.assertEqual("fail_closed", result["resume"]["mode"])
        self.assertFalse(result["sources"]["factory"])
        self.assertIn("factory unavailable", result["warnings"][0])

    def test_human_state_contract_covers_health_activity_and_resume_matrix(self):
        candidate = project_candidate({
            "id": "af-next", "title": "Next result", "state": "queued",
            "status": "deferred", "urgency": "normal", "goal": "af-goal",
        })

        def state(**overrides):
            observed = {
                "infrastructure": {"running": True, "usable": True, "degraded": False},
                "sources_consistent": True,
                "current": None,
                "queue": [candidate],
                "needs_benjamin": None,
                "blockers": [],
                "resume_policy": {"mode": "manual"},
            }
            observed.update(overrides)
            return project_human_state(observed)

        healthy = state()
        self.assertEqual("available", healthy["health"]["state"])
        self.assertEqual("waiting_action", healthy["activity"]["state"])
        self.assertFalse(healthy["resume"]["automatic"])
        self.assertFalse(healthy["resume"]["required"])
        self.assertEqual("Benjamin", healthy["resume"]["owner"])
        self.assertEqual("Éligible · non programmé", healthy["next_candidate"]["state_label"])

        down = state(infrastructure={"running": False, "usable": False, "degraded": False})
        self.assertEqual(("unavailable", "stopped", "fail_closed"), (
            down["health"]["state"], down["activity"]["state"], down["resume"]["mode"],
        ))
        partial = state(infrastructure={"running": True, "usable": True, "degraded": True})
        self.assertEqual(("degraded", "stopped"), (
            partial["health"]["state"], partial["activity"]["state"],
        ))
        inconsistent = state(sources_consistent=False)
        self.assertEqual(("degraded", "fail_closed"), (
            inconsistent["health"]["state"], inconsistent["resume"]["mode"],
        ))

        active = state(current={
            "id": "af-exec", "title": "Delivery", "state": "active",
            "agent": "codex-exact", "phase": "Réalisation",
        })
        self.assertEqual(("working", "active_delivery"), (
            active["activity"]["state"], active["resume"]["mode"],
        ))
        materialized = state(current={
            "id": "af-exec", "title": "Delivery", "state": "materialized",
            "agent": None, "phase": "Aucun agent",
        })
        self.assertEqual(("waiting_action", "Mayor", "materialized"), (
            materialized["activity"]["state"], materialized["resume"]["owner"],
            materialized["result"]["state"],
        ))
        finalizing = state(current={
            "id": "af-exec", "title": "Delivery", "state": "finalizing",
            "agent": None, "phase": "Preuves et fusion",
        })
        self.assertEqual("mayor_finalization", finalizing["resume"]["mode"])
        dependency = state(
            current={
                "id": "af-exec", "title": "Delivery", "state": "waiting_dependency",
                "agent": None, "phase": "CI exacte",
            },
            resume_policy={"mode": "automatic_dependency", "condition": "CI exacte verte"},
        )
        self.assertEqual(("waiting_automatic", True, "system"), (
            dependency["activity"]["state"], dependency["resume"]["automatic"],
            dependency["resume"]["owner"],
        ))
        decision = state(needs_benjamin="Choisir le contrat de consentement")
        self.assertEqual(("blocking_decision", "Benjamin", True, "Répondre à la décision bloquante."), (
            decision["resume"]["mode"], decision["resume"]["owner"],
            decision["resume"]["required"], decision["resume"]["action"],
        ))
        blocked = state(current={
            "id": "af-exec", "title": "Delivery", "state": "blocked",
            "cause": "Preuve externe absente", "phase": "Bloqué",
        })
        self.assertEqual("Preuve externe absente", blocked["resume"]["condition"])

    def test_campaign_decision_preserves_its_exact_persisted_action(self):
        exact_action = (
            "Benjamin valide le périmètre, puis demande au Mayor de reprendre la campagne."
        )
        campaign_metadata = {
            "gc.campaign_mode": "automatic",
            "gc.campaign_state": "blocked",
            "gc.campaign_candidate": "af-cm1l",
            "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
            "gc.campaign_owner": "Benjamin",
            "gc.campaign_action": exact_action,
            "gc.campaign_block_kind": "decision",
            "gc.campaign_cause": "La campagne attend le choix de périmètre.",
            "gc.campaign_wake_state": "none",
            "gc.campaign_failure_count": "0",
        }
        observed = {
            "infrastructure": {"running": True, "usable": True, "degraded": False},
            "sources_consistent": True,
            "current": None,
            "queue": [],
            "needs_benjamin": "Choisir le périmètre du prochain résultat.",
            "blockers": [],
            "resume_policy": {
                "mode": "automatic_campaign",
                "condition": "Le Mayor enchaîne le premier candidat éligible",
            },
            "campaign_metadata": campaign_metadata,
        }

        value = project_human_state(observed)

        self.assertEqual((exact_action, exact_action), (
            value["resume"]["action"], value["campaign"]["action"],
        ))
        self.assertEqual(("Benjamin", "Benjamin", "La campagne attend le choix de périmètre."), (
            value["resume"]["owner"], value["campaign"]["owner"],
            value["campaign"]["cause"],
        ))
        self.assertNotEqual("Répondre à la décision bloquante.", value["resume"]["action"])

        campaign_metadata["gc.campaign_owner"] = "Mayor"
        with self.assertRaisesRegex(StateContractError, "Benjamin comme responsable"):
            project_human_state(observed)

    def test_canonical_state_matches_versioned_schema_shape(self):
        schema = json.loads(
            (ROOT / "config" / "factory-human-status.schema.json").read_text(encoding="utf-8")
        )
        value = project_human_state({
            "infrastructure": {"running": True, "usable": True, "degraded": False},
            "sources_consistent": True,
            "current": None,
            "queue": [project_candidate({
                "id": "af-next", "title": "Next", "status": "deferred",
                "state": "queued", "urgency": "normal", "goal": "af-goal",
            })],
            "needs_benjamin": None, "blockers": [],
            "resume_policy": {"mode": "manual"},
        })
        self.assertEqual(schema["properties"]["contract"]["const"], value["contract"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], value["schema_version"])
        self.assertTrue(set(schema["required"]).issubset(value))
        self.assertIn(
            value["health"]["state"],
            schema["properties"]["health"]["properties"]["state"]["enum"],
        )
        self.assertIn(
            value["activity"]["state"],
            schema["properties"]["activity"]["properties"]["state"]["enum"],
        )
        self.assertTrue(
            set(schema["$defs"]["candidate"]["required"]).issubset(value["queue"][0])
        )

    def test_human_state_contract_covers_idle_campaign_empty_and_paused(self):
        eligible = project_candidate({
            "id": "af-next", "title": "Next", "status": "deferred",
            "state": "queued", "urgency": "normal", "goal": "af-goal",
        })
        campaign = project_candidate({
            "id": "af-campaign", "title": "Maintenance campaign", "status": "deferred",
            "state": "queued", "urgency": "normal", "goal": "none",
        })
        paused = project_candidate({
            "id": "af-paused", "title": "Paused", "status": "deferred",
            "state": "paused", "pause_reason": "Attend les entretiens",
            "urgency": "normal", "goal": "af-goal",
        })
        legacy_paused = project_candidate({
            "id": "af-legacy", "title": "Legacy pause", "status": "deferred",
            "state": "paused", "notes": (
                "Unrelated prose must be ignored\n"
                "Product queue paused: Première raison\n"
                "Product queue paused: Dernière raison structurée"
            ),
            "urgency": "normal", "goal": "af-goal",
        })
        self.assertEqual("Dernière raison structurée", legacy_paused["pause_reason"])
        base = {
            "infrastructure": {"running": True, "usable": True, "degraded": False},
            "sources_consistent": True, "current": None, "needs_benjamin": None,
            "blockers": [],
        }
        automatic = project_human_state({
            **base, "queue": [campaign, eligible],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "active",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("af-next", automatic["next_candidate"]["id"])
        self.assertEqual(("waiting_automatic", True), (
            automatic["activity"]["state"], automatic["resume"]["automatic"],
        ))
        all_paused = project_human_state({
            **base, "queue": [campaign, paused], "resume_policy": {"mode": "manual"},
        })
        self.assertEqual(("all_paused", "Attend les entretiens"), (
            all_paused["resume"]["mode"], all_paused["queue"][1]["reason"],
        ))
        empty = project_human_state({
            **base, "queue": [campaign], "resume_policy": {"mode": "manual"},
        })
        self.assertEqual(("stopped", "no_candidate", "none"), (
            empty["activity"]["state"], empty["resume"]["mode"], empty["resume"]["owner"],
        ))
        with self.assertRaisesRegex(StateContractError, "condition"):
            project_human_state({
                **base, "queue": [eligible],
                "resume_policy": {"mode": "automatic_campaign"},
            })

        blocked = project_human_state({
            **base, "queue": [eligible],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "blocked",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Benjamin", "gc.campaign_action": "Autoriser l'action ADMIN exacte",
                "gc.campaign_block_kind": "admin", "gc.campaign_cause": "Action ADMIN requise",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual(("blocked", "campaign_blocked", "Benjamin", None), (
            blocked["campaign"]["state"], blocked["resume"]["mode"],
            blocked["campaign"]["owner"], blocked["needs_benjamin"],
        ))

    def test_candidate_history_never_reappears_as_eligible(self):
        materialized = {
            "id": "af-old", "status": "closed", "labels": ["product-queue"],
            "metadata": {"gc.queue_state": "materialized", "gc.materialized_bead": "af-exec"},
        }
        cancelled = {
            "id": "af-no", "status": "closed", "labels": ["product-queue"],
            "metadata": {"gc.queue_state": "cancelled"},
        }
        self.assertEqual(("materialized", "Matérialisé"), candidate_record_lifecycle(materialized))
        self.assertEqual(("cancelled", "Annulé"), candidate_record_lifecycle(cancelled))
        self.assertEqual("materialized", _product_bead(materialized, "city", None)["state"])
        self.assertEqual("cancelled", _product_bead(cancelled, "city", None)["state"])
        delivered = _product_bead({
            "id": "af-done", "title": "Done", "status": "closed", "labels": ["jit"],
            "metadata": {"gc.work_outcome": "shipped"},
        }, "city", None)
        self.assertEqual(("delivered", "Livré"), (delivered["state"], delivered["state_label"]))
        blocked_current = _product_bead({
            "id": "af-blocked", "title": "Blocked current", "status": "blocked",
            "labels": ["jit"], "metadata": {"gc.blocked_reason": "Preuve absente"},
        }, "city", "af-blocked")
        self.assertEqual(("blocked", "Bloqué", "Preuve absente"), (
            blocked_current["state"], blocked_current["state_label"], blocked_current["cause"],
        ))
        with self.assertRaisesRegex(StateContractError, "incohérent"):
            candidate_record_lifecycle({
                "id": "af-bad", "status": "closed",
                "metadata": {"gc.queue_state": "queued"},
            })
        with self.assertRaisesRegex(SourceError, "incohérent"):
            _product_bead({
                "id": "af-bad", "title": "Bad", "status": "closed",
                "labels": ["product-queue"],
                "metadata": {"gc.queue_state": "queued"},
            }, "city", None)

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
