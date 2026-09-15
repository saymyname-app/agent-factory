#!/usr/bin/env python3
"""Prove the cockpit core carries no product identity of its own.

The core must project a second, unrelated product pack — configuration plus a
documentation folder, no code — without leaking the identity of the product it
happens to ship with today.
"""

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import (  # noqa: E402
    FactoryCollector,
    POBridge,
    PreviewBridge,
    ProductMemory,
    SourceError,
    active_product_config_path,
    load_product_config,
)

EXAMPLE_CONFIG = ROOT / "config" / "products" / "example.json"
SHIPPED_SLUG = json.loads(
    (ROOT / "config" / "cockpit.json").read_text(encoding="utf-8")
)["active_product"]
SHIPPED_NAME = json.loads(
    (ROOT / "config" / "products" / f"{SHIPPED_SLUG}.json").read_text(encoding="utf-8")
)["name"]

# Core source files that must never name a product.
CORE_FILES = (
    ROOT / "lib" / "factory_cockpit.py",
    ROOT / "ui" / "factory-cockpit" / "index.html",
    ROOT / "ui" / "factory-cockpit" / "app.js",
    ROOT / "ui" / "factory-cockpit" / "styles.css",
    ROOT / "bin" / "factory-cockpit",
)


def _load_shared_harness():
    """Reuse the main suite's fake Gas City / command runner."""
    path = ROOT / "tests" / "factory-cockpit-test.py"
    spec = importlib.util.spec_from_file_location("factory_cockpit_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = _load_shared_harness()


class ExampleRunner(HARNESS.FakeRunner):
    """The shipped fake runner, re-keyed onto the example product's contracts."""

    def __init__(self):
        super().__init__()
        shipped_queue = (
            str(ROOT / "bin" / f"{SHIPPED_SLUG}-product-queue"), "list", "--json",
        )
        example_queue = (
            str(ROOT / "bin" / "example-product-queue"), "list", "--json",
        )
        self.responses[example_queue] = self.responses.pop(shipped_queue)


class ProductAgnosticCoreTest(unittest.TestCase):
    def setUp(self):
        self._blocker_state_dir = tempfile.TemporaryDirectory()
        self._blocker_state_patch = patch(
            "factory_cockpit.BLOCKER_STATE_PATH",
            Path(self._blocker_state_dir.name) / "factory-cockpit-blockers.json",
        )
        self._blocker_state_patch.start()
        self.addCleanup(self._blocker_state_patch.stop)
        self.addCleanup(self._blocker_state_dir.cleanup)
        self.config = load_product_config(EXAMPLE_CONFIG)

    def assertNoShippedProduct(self, value, where):
        rendered = json.dumps(value, ensure_ascii=False, default=str)
        for needle in {SHIPPED_SLUG, SHIPPED_NAME, SHIPPED_NAME.lower()}:
            self.assertNotIn(
                needle.lower(), rendered.lower(),
                f"{where} leaks the shipped product identity ({needle}).",
            )

    def test_core_sources_name_no_product(self):
        for path in CORE_FILES:
            text = path.read_text(encoding="utf-8").lower()
            for needle in {SHIPPED_SLUG.lower(), SHIPPED_NAME.lower()}:
                self.assertNotIn(needle, text, f"{path.name} still hard-codes {needle}.")

    def test_active_product_is_configuration_not_code(self):
        self.assertEqual(
            ROOT / "config" / "products" / f"{SHIPPED_SLUG}.json",
            active_product_config_path(),
        )
        with patch.dict("os.environ", {"FACTORY_COCKPIT_PRODUCT_CONFIG": str(EXAMPLE_CONFIG)}):
            self.assertEqual(EXAMPLE_CONFIG, active_product_config_path())

    def test_second_product_projects_a_coherent_memory(self):
        memory = ProductMemory(config=self.config).collect()
        self.assertEqual("Example Product", memory["product"])
        self.assertEqual("example", memory["slug"])
        self.assertEqual(self.config["north_star"], memory["business"]["north_star"])
        self.assertEqual(3, len(memory["roadmap"]))
        self.assertEqual(3, len(memory["project_graph"]["nodes"]))
        self.assertEqual(1, len(memory["journeys"]))
        self.assertTrue(all(item["state"] == "ready" for item in memory["product_reference"]))
        self.assertEqual(
            ["docs/products/example/PRODUCT_STRATEGY.md",
             "docs/products/example/DECISIONS.md",
             "docs/products/example/PROJECT_INVENTORY.md",
             "docs/products/example/DESIGN_GOVERNANCE.md"],
            memory["sources"],
        )
        pending = {item["title"] for item in memory["decisions"] if item["status"] == "pending"}
        self.assertIn("Example retention rule", pending)
        self.assertNoShippedProduct(memory, "The projected product memory")

    def test_second_product_projects_a_coherent_snapshot(self):
        collector = FactoryCollector(
            runner=ExampleRunner(),
            gas_city=HARNESS.FakeGasCity(),
            product_config=self.config,
        )
        snapshot = collector.collect()
        self.assertEqual("Example Product", snapshot["product_memory"]["product"])
        self.assertEqual("example", snapshot["release"]["product"])
        self.assertEqual(0, snapshot["zero_token_contract"]["model_calls"])
        self.assertNoShippedProduct(snapshot, "The projected snapshot")

    def test_a_product_without_a_preview_wrapper_is_supported(self):
        bridge = PreviewBridge(config=self.config)
        self.assertFalse(bridge.available)
        status = bridge.status()
        self.assertFalse(status["available"])
        self.assertEqual([], status["components"])
        with self.assertRaisesRegex(SourceError, "prévisualisation"):
            bridge.submit("start")

    def test_the_shipped_product_keeps_its_preview_contract(self):
        config = load_product_config()
        bridge = PreviewBridge(config=config)
        self.assertTrue(bridge.available)
        self.assertEqual(
            ROOT / "bin" / f"{SHIPPED_SLUG}-preview", config["preview"]["command_path"],
        )

    def test_the_po_prompt_names_the_configured_product(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = POBridge(
                config=self.config, state_path=Path(directory) / "po.json",
            )
            prompt = bridge._prompt("Bonjour", "discuss", None)
        self.assertIn("Example Product", prompt)
        self.assertNoShippedProduct(prompt, "The PO prompt")

    def test_the_pack_contract_refuses_a_product_without_a_north_star(self):
        value = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        value.pop("north_star")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "incomplète|Étoile"):
                load_product_config(path)

    def test_the_pack_contract_refuses_a_foreign_preview_wrapper(self):
        value = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        value["preview"] = {
            "command": [f"bin/{SHIPPED_SLUG}-preview"],
            "browser_url": "http://127.0.0.1:5173/",
            "version_policy": "test",
            "components": [{"id": "frontend", "label": "Frontend", "command": "npm run dev"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "contrat dédié"):
                load_product_config(path)

    def test_the_preview_target_must_stay_on_the_loopback_interface(self):
        value = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        value["slug"] = "example"
        value["preview"] = {
            "command": ["bin/example-preview"],
            "browser_url": "http://example.test/",
            "version_policy": "test",
            "components": [{"id": "frontend", "label": "Frontend", "command": "npm run dev"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "boucle locale"):
                load_product_config(path)

    def test_the_ui_shell_declares_product_text_as_data(self):
        html = (ROOT / "ui" / "factory-cockpit" / "index.html").read_text(encoding="utf-8")
        slots = re.findall(r'data-product-text="([^"]+)"', html)
        self.assertGreaterEqual(len(slots), 5)
        self.assertTrue(all("%s" in slot for slot in slots))
        app = (ROOT / "ui" / "factory-cockpit" / "app.js").read_text(encoding="utf-8")
        self.assertIn("applyProductIdentity", app)


if __name__ == "__main__":
    unittest.main(verbosity=1)
