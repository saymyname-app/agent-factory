#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    FactoryCollector,
    MayorBridge,
    SourceError,
    _human_objective,
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
