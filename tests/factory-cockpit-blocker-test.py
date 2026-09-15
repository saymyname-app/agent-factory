#!/usr/bin/env python3
"""af-5cmd: a blocking bead must become an answerable decision, not a dead-end banner."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    ProductMemory,
    _collect_blockers,
    _decision_aids,
    _read_blockers,
    _write_blockers,
    load_product_config,
)


BLOCKER_TEXT = (
    "Faut-il autoriser l'import CSV administré sans consentement individuel préalable ? "
    "Le choix conditionne la suite de la livraison."
)


class BlockerDecisionTest(unittest.TestCase):
    def test_blocking_metadata_becomes_a_workspace_compatible_decision(self):
        blockers = _collect_blockers(
            "af-1vr4",
            {"gc.needs_benjamin": BLOCKER_TEXT, "gc.decision_domain": "product"},
            [],
        )
        self.assertEqual(1, len(blockers))
        decision = blockers[0]
        self.assertEqual("pending", decision["status"])
        self.assertEqual("product", decision["domain"])
        self.assertEqual("blocker", decision["origin"])
        self.assertEqual("af-1vr4", decision["bead"])
        self.assertTrue(decision["id"].startswith("pending-product-blocker-"))
        self.assertEqual(
            "Faut-il autoriser l'import CSV administré sans consentement individuel préalable ?",
            decision["title"],
        )
        self.assertEqual(BLOCKER_TEXT.replace("  ", " "), decision["detail"])
        self.assertIn("gc.needs_benjamin", decision["source"])

    def test_none_and_empty_metadata_produce_no_decision(self):
        self.assertEqual([], _collect_blockers("af-1vr4", {"gc.needs_benjamin": "none"}, []))
        self.assertEqual([], _collect_blockers("af-1vr4", {"gc.needs_benjamin": "   "}, []))
        self.assertEqual([], _collect_blockers("af-1vr4", {}, []))

    def test_unknown_domain_falls_back_to_product_and_ids_are_stable(self):
        first = _collect_blockers("af-9zz", {"gc.needs_benjamin": "Choix A ou B ?", "gc.decision_domain": "marketing"}, [])
        second = _collect_blockers("af-9zz", {"gc.needs_benjamin": "Choix A ou B ?"}, [])
        self.assertEqual("product", first[0]["domain"])
        self.assertEqual(first[0]["id"], second[0]["id"])

    def test_product_work_blockers_are_collected_and_deduplicated(self):
        blockers = _collect_blockers(
            "af-1vr4",
            {"gc.needs_benjamin": BLOCKER_TEXT},
            [
                {"id": "af-1vr4", "needs_benjamin": BLOCKER_TEXT},
                {"id": "af-u8id", "needs_benjamin": "Quel canal tester en premier ?", "decision_domain": "enterprise"},
                {"id": "af-xxxx", "needs_benjamin": None},
            ],
        )
        self.assertEqual(2, len(blockers))
        self.assertEqual({"product", "enterprise"}, {item["domain"] for item in blockers})

    def test_blockers_reach_product_memory_so_the_po_bridge_can_resolve_them(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / "blockers.json"
            blockers = _collect_blockers("af-1vr4", {"gc.needs_benjamin": BLOCKER_TEXT}, [])
            _write_blockers(blockers, store)
            self.assertEqual(blockers, _read_blockers(store))

            memory = ProductMemory(config=load_product_config(), blockers=store)
            decisions = memory.collect()["decisions"]
            pending = [item for item in decisions if item["status"] == "pending"]
            self.assertTrue(pending, "a blocking bead must yield at least one answerable decision")
            self.assertEqual(blockers[0]["id"], pending[0]["id"])
            self.assertIn(blockers[0]["domain"], {"enterprise", "product", "project"})

    def test_missing_or_corrupt_store_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            self.assertEqual([], _read_blockers(missing))
            corrupt = Path(directory) / "corrupt.json"
            corrupt.write_text("{ not json", encoding="utf-8")
            self.assertEqual([], _read_blockers(corrupt))

    def test_decision_aid_carries_the_workspace_id_and_drops_the_duplicate_card(self):
        aids = _decision_aids(
            True,
            [],
            {"state": "working", "steps": {}},
            [],
            [{"state": "blocked", "title": "Import CSV"}],
            BLOCKER_TEXT,
            {"ci": "success"},
            "pending-product-blocker-af-1vr4",
        )
        decision_aids = [item for item in aids if item["severity"] == "decision"]
        self.assertEqual(1, len(decision_aids))
        self.assertEqual("pending-product-blocker-af-1vr4", decision_aids[0]["decision_id"])
        self.assertEqual(
            [], [item for item in aids if "bloqué" in item["title"]],
            "the generic blocked card duplicates the decision card and must be suppressed",
        )

    def test_blocked_card_still_appears_without_a_human_decision(self):
        aids = _decision_aids(
            True, [], {"state": "working", "steps": {}}, [],
            [{"state": "blocked", "title": "Import CSV"}], None, {"ci": "success"}, None,
        )
        self.assertTrue([item for item in aids if "bloqué" in item["title"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
