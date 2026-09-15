#!/usr/bin/env python3
"""Prove the cockpit core carries no identity of its own.

Neither the product it happens to ship with nor the human it happens to serve
may appear in `lib/factory_cockpit.py`, `bin/factory-cockpit` or the SPA. Both
are declared by the product pack — configuration plus a documentation folder,
never code — and the core must project a second, unrelated pack unchanged.
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
    _operator_name,
    active_product_config_path,
    load_product_config,
)

EXAMPLE_CONFIG = ROOT / "config" / "products" / "example.json"
SHIPPED_SLUG = json.loads(
    (ROOT / "config" / "cockpit.json").read_text(encoding="utf-8")
)["active_product"]
SHIPPED = json.loads(
    (ROOT / "config" / "products" / f"{SHIPPED_SLUG}.json").read_text(encoding="utf-8")
)

# Core sources that must name neither a product nor an operator.
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
        shipped = (str(ROOT / "bin" / f"{SHIPPED_SLUG}-product-queue"), "list", "--json")
        example = (str(ROOT / "bin" / "example-product-queue"), "list", "--json")
        self.responses[example] = self.responses.pop(shipped)


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

    def assertNoShippedIdentity(self, value, where):
        rendered = json.dumps(value, ensure_ascii=False, default=str).lower()
        # `needs_benjamin` is the Gas City bead metadata key echoed through the
        # projection — an external protocol identifier, not the cockpit naming
        # its human. Renaming it is a Gas City / product-status change.
        rendered = rendered.replace("needs_benjamin", "").replace("needs benjamin", "")
        for needle in (SHIPPED_SLUG, SHIPPED["name"], SHIPPED["operator_name"]):
            self.assertNotIn(
                needle.lower(), rendered,
                f"{where} leaks the shipped identity ({needle}).",
            )

    def _temporary_pack(self, **overrides):
        value = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        for key, item in overrides.items():
            if item is None:
                value.pop(key, None)
            else:
                value[key] = item
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "product.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    # -- the core names nobody -------------------------------------------------

    def test_core_sources_name_no_product_and_no_operator(self):
        for path in CORE_FILES:
            text = path.read_text(encoding="utf-8").lower()
            # `gc.needs_benjamin` / `NEEDS BENJAMIN` are the Beads metadata key and
            # the product-status field name — an external protocol identifier, not
            # the cockpit naming its human. Renaming those is a Gas City change.
            text = text.replace("needs_benjamin", "").replace("needs benjamin", "")
            text = text.replace("needs-benjamin", "")
            for needle in (SHIPPED_SLUG, SHIPPED["name"], SHIPPED["operator_name"]):
                self.assertNotIn(
                    needle.lower(), text, f"{path.name} still hard-codes {needle}.",
                )

    def test_the_operator_must_be_configured_not_assumed(self):
        with self.assertRaisesRegex(SourceError, "opérateur"):
            _operator_name({})
        self.assertEqual("Alex", _operator_name(self.config))
        with self.assertRaisesRegex(SourceError, "incomplète|opérateur"):
            load_product_config(self._temporary_pack(operator_name=None))

    def test_active_product_is_configuration_not_code(self):
        self.assertEqual(
            ROOT / "config" / "products" / f"{SHIPPED_SLUG}.json",
            active_product_config_path(),
        )
        with patch.dict("os.environ", {"FACTORY_COCKPIT_PRODUCT_CONFIG": str(EXAMPLE_CONFIG)}):
            self.assertEqual(EXAMPLE_CONFIG, active_product_config_path())

    # -- a second pack projects through the same core --------------------------

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
        self.assertNoShippedIdentity(memory, "The projected product memory")

    def test_second_product_projects_a_coherent_snapshot(self):
        snapshot = FactoryCollector(
            runner=ExampleRunner(),
            gas_city=HARNESS.FakeGasCity(),
            product_config=self.config,
        ).collect()
        self.assertEqual("Example Product", snapshot["product_memory"]["product"])
        self.assertEqual("Alex", snapshot["operator"])
        self.assertEqual("example", snapshot["release"]["product"])
        self.assertEqual(0, snapshot["zero_token_contract"]["model_calls"])
        self.assertNoShippedIdentity(snapshot, "The projected snapshot")

    def test_the_po_prompt_names_the_configured_product_and_operator(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = POBridge(config=self.config, state_path=Path(directory) / "po.json")
            prompt = bridge._prompt("Bonjour", "discuss", None)
        self.assertIn("Example Product", prompt)
        self.assertIn("Alex", prompt)
        self.assertNoShippedIdentity(prompt, "The PO prompt")

    def test_the_po_state_file_is_namespaced_per_product(self):
        self.assertEqual(
            ROOT / ".gc" / "runtime" / "factory-cockpit-po-example.json",
            POBridge(config=self.config).state_path,
        )

    # -- preview is a pack capability, not a core assumption --------------------

    def test_a_product_without_a_preview_wrapper_is_supported(self):
        bridge = PreviewBridge(config=self.config)
        status = bridge.status()
        self.assertEqual("unconfigured", status["state"])
        self.assertEqual([], status["components"])
        with self.assertRaisesRegex(ValueError, "non configurée"):
            bridge.submit("start")

    def test_the_shipped_product_keeps_its_preview_contract(self):
        config = load_product_config()
        self.assertEqual(
            (ROOT / "bin" / f"{SHIPPED_SLUG}-preview").resolve(),
            config["preview_command_path"],
        )
        self.assertEqual(
            ["frontend", "backend"],
            [item["id"] for item in config["preview_components"]],
        )

    def test_the_pack_contract_refuses_a_foreign_preview_wrapper(self):
        with self.assertRaisesRegex(SourceError, "contrat dédié"):
            load_product_config(self._temporary_pack(
                preview_command=[f"bin/{SHIPPED_SLUG}-preview"],
                preview_browser_url="http://127.0.0.1:5173/",
                preview_version_policy="test",
                preview_components=[{"id": "frontend", "label": "Frontend", "command": "npm run dev"}],
            ))

    def test_the_preview_target_must_stay_on_the_loopback_interface(self):
        with self.assertRaisesRegex(SourceError, "boucle locale"):
            load_product_config(self._temporary_pack(
                preview_command=["bin/example-preview"],
                preview_browser_url="http://example.test/",
                preview_version_policy="test",
                preview_components=[{"id": "frontend", "label": "Frontend", "command": "npm run dev"}],
            ))

    def test_a_preview_wrapper_must_describe_what_it_shows(self):
        with self.assertRaisesRegex(SourceError, "Composants de prévisualisation"):
            load_product_config(self._temporary_pack(
                preview_command=["bin/example-preview"],
                preview_browser_url="http://127.0.0.1:5173/",
                preview_version_policy="test",
            ))

    # -- the UI takes both identities as data ----------------------------------

    def test_the_ui_shell_declares_both_identities_as_data(self):
        html = (ROOT / "ui" / "factory-cockpit" / "index.html").read_text(encoding="utf-8")
        products = re.findall(r'data-product-text="([^"]+)"', html)
        operators = re.findall(r'data-operator-text="([^"]+)"', html)
        self.assertGreaterEqual(len(products), 5)
        self.assertGreaterEqual(len(operators), 3)
        self.assertTrue(all("%s" in slot for slot in products + operators))
        app = (ROOT / "ui" / "factory-cockpit" / "app.js").read_text(encoding="utf-8")
        self.assertIn("applyIdentity", app)


if __name__ == "__main__":
    unittest.main(verbosity=1)
