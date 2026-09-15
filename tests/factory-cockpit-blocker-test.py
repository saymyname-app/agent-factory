#!/usr/bin/env python3
"""af-5cmd: route gc.needs_benjamin blockers through the decision workspace.

A bead exposing gc.needs_benjamin (coordination or a product bead) must
synthesize into the same pending-decision shape as a DECISIONS.md Open entry,
so it appears in the normal "à décider" list and resolves through
today.effective_blockers[...].decision_id instead of a dead-end banner.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    FactoryCollector,
    ProductMemory,
    _blocker_decision,
    _collect_blockers,
    _product_bead,
    _read_blockers,
    _write_blockers,
)


class FakeGasCity:
    def json(self, path):
        if path == "/v0/city/agent-factory/workflow/smf-flow":
            return {"beads": [{"kind": "workflow", "status": "completed"}]}
        raise AssertionError(path)


class FakeRunner:
    """Minimal coordination + product-work fixture with one blocked product bead."""

    def __init__(self, coordination_needs_benjamin=None):
        coordination_metadata = {
            "gc.current_jit": "smf-now",
            "gc.last_delivered": "smb-done",
            "gc.current_workflow": "smf-flow",
        }
        if coordination_needs_benjamin is not None:
            coordination_metadata["gc.needs_benjamin"] = coordination_needs_benjamin
        self.responses = {
            ("gc", "status", "--json"): {
                "ok": True,
                "running": True,
                "city_name": "agent-factory",
                "health": {"usable": True, "degraded": False},
                "rigs": [],
            },
            ("gc", "session", "list", "--json"): {"sessions": []},
            ("gc", "bd", "show", "af-1vr4", "--json"): [{
                "id": "af-1vr4",
                "metadata": coordination_metadata,
            }],
            (str(ROOT / "bin" / "saymyname-product-queue"), "list", "--json"): [],
            ("bd", "list", "--status", "in_progress", "--limit", "0", "--json"): [],
            (
                "bd", "list", "--all", "--label-any",
                "product-goal,roadmap,product-queue,jit", "--limit", "0", "--json",
            ): [{
                "id": "af-u8id",
                "title": "Administered CSV import",
                "status": "open",
                "labels": ["jit"],
                "metadata": {
                    "gc.needs_benjamin": (
                        "Décision af-u8id.3 : approuver ou amender les recommandations UX."
                    ),
                    "gc.decision_domain": "product",
                },
            }],
            ("gc", "bd", "show", "smf-now", "--json"): [{
                "id": "smf-now",
                "title": "Finaliser l’onboarding sans organisation",
                "status": "open",
                "created_at": "2026-09-14T08:00:00Z",
                "updated_at": "2026-09-14T09:59:00Z",
                "metadata": {"gc.current_workflow": "smf-flow", "gc.work_outcome": "shipped"},
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
        }

    def json(self, *args):
        if args not in self.responses:
            raise AssertionError(f"Unexpected command: {args}")
        return self.responses[args]


class BlockerDecisionWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self._blocker_state_dir = tempfile.TemporaryDirectory()
        self._blocker_state_patch = patch(
            "factory_cockpit.BLOCKER_STATE_PATH",
            Path(self._blocker_state_dir.name) / "factory-cockpit-blockers.json",
        )
        self._blocker_state_patch.start()
        self.addCleanup(self._blocker_state_patch.stop)
        self.addCleanup(self._blocker_state_dir.cleanup)

    def test_product_bead_exposes_needs_benjamin_and_decision_domain(self):
        bead = {
            "id": "af-u8id",
            "title": "Administered CSV import",
            "status": "open",
            "labels": ["jit"],
            "metadata": {
                "gc.needs_benjamin": "Choisir le périmètre de l'import administré.",
                "gc.decision_domain": "product",
            },
        }
        item = _product_bead(bead, "city", None)
        self.assertEqual("Choisir le périmètre de l'import administré.", item["needs_benjamin"])
        self.assertEqual("product", item["decision_domain"])

    def test_product_bead_without_blocker_metadata_reports_none(self):
        bead = {"id": "af-clean", "title": "Nothing to see", "status": "open", "labels": ["jit"]}
        item = _product_bead(bead, "city", None)
        self.assertIsNone(item["needs_benjamin"])
        self.assertIsNone(item["decision_domain"])

    def test_collect_blockers_covers_coordination_and_product_beads(self):
        coordination_meta = {"gc.needs_benjamin": "none"}
        product_work = [
            {"id": "af-u8id", "needs_benjamin": "Approuver les recommandations UX.", "decision_domain": "product"},
            {"id": "af-clean", "needs_benjamin": None, "decision_domain": None},
        ]
        decisions = _collect_blockers("af-1vr4", coordination_meta, product_work)
        self.assertEqual(1, len(decisions))
        self.assertEqual("pending-product-blocker-af-u8id", decisions[0]["id"])
        self.assertEqual("pending", decisions[0]["status"])
        self.assertEqual("Approuver les recommandations UX.", decisions[0]["detail"])
        self.assertEqual("blocker", decisions[0]["origin"])

    def test_collect_blockers_falls_back_to_product_domain_when_unset(self):
        decision = _blocker_decision("af-u8id", "Some free text blocker.", domain_hint="not-a-real-domain")
        self.assertEqual("product", decision["domain"])

    def test_collect_blockers_deduplicates_identical_ids(self):
        coordination_meta = {"gc.needs_benjamin": "Approuver les recommandations UX."}
        product_work = [{
            "id": "af-1vr4", "needs_benjamin": "Approuver les recommandations UX.", "decision_domain": "product",
        }]
        decisions = _collect_blockers("af-1vr4", coordination_meta, product_work)
        self.assertEqual(1, len(decisions))

    def test_product_memory_merges_blockers_into_pending_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            strategy = Path(directory) / "strategy.md"
            decisions_doc = Path(directory) / "decisions.md"
            blockers_path = Path(directory) / "blockers.json"
            strategy.write_text(
                "# Product\n\n## Product thesis\n\nA useful product.\n\n"
                "## Product roadmap\n\n1. First outcome.\n\nItems remain queued.\n\n",
                encoding="utf-8",
            )
            decisions_doc.write_text(
                "# Decisions\n\n## Accepted\n\n## Open\n\n### Product\n\n"
                "- **Choose the pilot** — Decide who should test.\n",
                encoding="utf-8",
            )
            _write_blockers([{
                "id": "pending-product-blocker-af-u8id",
                "title": "Décision af-u8id.3 à prendre",
                "status": "pending",
                "domain": "product",
                "detail": "Approuver ou amender les recommandations UX.",
                "source": "Bead af-u8id · gc.needs_benjamin",
                "origin": "blocker",
                "bead": "af-u8id",
            }], blockers_path)

            result = ProductMemory(strategy, decisions_doc, blockers=blockers_path).collect()
            pending = [item for item in result["decisions"] if item["status"] == "pending"]
            self.assertEqual(2, len(pending))
            self.assertEqual("pending-product-blocker-af-u8id", pending[0]["id"])
            self.assertEqual("blocker", pending[0]["origin"])

    def test_product_memory_dedupes_blocker_matching_existing_pending_title(self):
        with tempfile.TemporaryDirectory() as directory:
            strategy = Path(directory) / "strategy.md"
            decisions_doc = Path(directory) / "decisions.md"
            blockers_path = Path(directory) / "blockers.json"
            strategy.write_text(
                "# Product\n\n## Product thesis\n\nA useful product.\n\n"
                "## Product roadmap\n\n1. First outcome.\n\nItems remain queued.\n\n",
                encoding="utf-8",
            )
            decisions_doc.write_text(
                "# Decisions\n\n## Accepted\n\n## Open\n\n### Product\n\n"
                "- **Choose the pilot** — Decide who should test.\n",
                encoding="utf-8",
            )
            _write_blockers([{
                "id": "pending-product-blocker-dup",
                "title": "Choose the pilot",
                "status": "pending",
                "domain": "product",
                "detail": "Duplicate of the markdown entry.",
                "source": "Bead af-dup · gc.needs_benjamin",
                "origin": "blocker",
                "bead": "af-dup",
            }], blockers_path)

            result = ProductMemory(strategy, decisions_doc, blockers=blockers_path).collect()
            pending = [item for item in result["decisions"] if item["status"] == "pending"]
            self.assertEqual(1, len(pending))

    def test_read_blockers_ignores_missing_or_malformed_store(self):
        self.assertEqual([], _read_blockers(Path("/nonexistent/blockers.json")))

    def test_product_bead_only_blocker_surfaces_and_resolves_through_workspace(self):
        runner = FakeRunner(coordination_needs_benjamin=None)
        result = FactoryCollector(runner, FakeGasCity()).collect()

        self.assertTrue(result["needs_benjamin"])
        blocker = result["today"]["effective_blockers"][0]
        self.assertIsNotNone(blocker["decision_id"])
        matched = next(
            item for item in result["product_memory"]["decisions"]
            if item["id"] == blocker["decision_id"]
        )
        self.assertEqual("pending", matched["status"])
        self.assertEqual("blocker", matched.get("origin"))
        self.assertEqual("blocking_decision", result["human_state"]["resume"]["mode"])
        self.assertIn(
            matched["id"],
            {item["id"] for item in result["product_memory"]["decisions"] if item["status"] == "pending"},
        )

    def test_coordination_blocker_takes_precedence_and_still_resolves(self):
        runner = FakeRunner(coordination_needs_benjamin="Choisir le périmètre du prochain résultat.")
        result = FactoryCollector(runner, FakeGasCity()).collect()

        self.assertEqual(
            "Choisir le périmètre du prochain résultat.", result["needs_benjamin"]
        )
        blockers_written = json.loads(
            (Path(self._blocker_state_dir.name) / "factory-cockpit-blockers.json").read_text(
                encoding="utf-8"
            )
        )
        bead_ids = {item["bead"] for item in blockers_written["decisions"]}
        self.assertIn("af-1vr4", bead_ids)
        self.assertIn("af-u8id", bead_ids)


if __name__ == "__main__":
    unittest.main()
