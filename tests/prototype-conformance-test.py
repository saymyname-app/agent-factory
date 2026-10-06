#!/usr/bin/env python3
"""T07 (af-tvda3w): bin/prototype-conformance checks a Validated Prototype
against the six properties of spec af-wf4w5r section 3, observed only
through its command line on a copy of the Delivery Fixture City's frozen
prototype."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "prototype-conformance"
FIXTURE_PROTOTYPE = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "prototype"
PROPERTIES = ["variant", "states", "encoding", "viewports_themes", "anchors", "datasets"]


class PrototypeConformanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prototype-conformance-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.prototype = self.tmp / "prototype"
        shutil.copytree(FIXTURE_PROTOTYPE, self.prototype)

    def check(self, *extra):
        proc = subprocess.run(
            (str(TOOL), "check", "--prototype", str(self.prototype), *extra), text=True, capture_output=True,
        )
        return proc, json.loads(proc.stdout)

    def manifest(self):
        return json.loads((self.prototype / "validated-prototype.json").read_text(encoding="utf-8"))

    def write_manifest(self, manifest):
        (self.prototype / "validated-prototype.json").write_text(json.dumps(manifest), encoding="utf-8")

    def edit_page(self, name, old, new):
        page = self.prototype / "states" / name
        text = page.read_text(encoding="utf-8")
        self.assertIn(old, text)
        page.write_text(text.replace(old, new), encoding="utf-8")

    def assert_only_property_fails(self, proc, report, name):
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(report["ok"])
        failed = [record["property"] for record in report["properties"] if not record["ok"]]
        self.assertEqual([name], failed)
        record = next(r for r in report["properties"] if r["property"] == name)
        self.assertTrue(record["failures"])
        return record["failures"]

    # --- passage --------------------------------------------------------------

    def test_fixture_prototype_passes_with_one_record_per_property(self):
        proc, report = self.check()
        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(PROPERTIES, [record["property"] for record in report["properties"]])
        for record in report["properties"]:
            self.assertTrue(record["ok"], record)
            self.assertEqual([], record["failures"])

    def test_fixture_prototype_passes_for_the_states_a_spec_names(self):
        proc, report = self.check("--states", "empty,content")
        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertTrue(report["ok"])

    # --- refus : un par propriété ----------------------------------------------

    def test_fails_when_a_visible_element_is_outside_every_anchor(self):
        self.edit_page("content.html", "</ul>", "</ul>\n<p>hors ancre</p>")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "anchors")
        self.assertIn("states/content.html", failures[0])

    def test_fails_when_an_anchor_is_removed_from_a_page(self):
        self.edit_page("empty.html", '<h1 data-anchor="fixture-state">', "<h1>")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "anchors")
        self.assertIn("states/empty.html", failures[0])

    def test_fails_when_a_prototyped_state_has_no_address(self):
        manifest = self.manifest()
        del manifest["states"][0]["address"]
        self.write_manifest(manifest)
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "states")
        self.assertIn("empty", failures[0])

    def test_fails_when_a_state_the_spec_names_is_not_in_the_prototype(self):
        proc, report = self.check("--states", "empty,content,error")
        failures = self.assert_only_property_fails(proc, report, "states")
        self.assertIn("error", failures[0])

    def test_fails_when_an_address_names_no_page_of_the_prototype(self):
        manifest = self.manifest()
        manifest["states"][1]["address"] = "states/absent.html"
        self.write_manifest(manifest)
        proc, report = self.check()
        self.assertNotEqual(0, proc.returncode)
        states = next(r for r in report["properties"] if r["property"] == "states")
        self.assertFalse(states["ok"])
        self.assertIn("states/absent.html", states["failures"][0])

    def test_fails_when_a_state_dataset_is_missing(self):
        (self.prototype / "data" / "content.json").unlink()
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "datasets")
        self.assertIn("content", failures[0])

    def test_fails_when_a_state_declares_no_dataset(self):
        manifest = self.manifest()
        del manifest["states"][0]["dataset"]
        self.write_manifest(manifest)
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "datasets")
        self.assertIn("empty", failures[0])

    def test_fails_when_a_dataset_has_no_fixed_time(self):
        (self.prototype / "data" / "empty.json").write_text('{"state": "empty", "items": []}', encoding="utf-8")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "datasets")
        self.assertIn("generated_at", failures[0])

    def test_fails_when_a_page_still_carries_the_variant_command_bar(self):
        self.edit_page(
            "content.html", "</body>",
            '<nav class="prototype-switcher" data-anchor="bar"><a href="?variant=B">B</a></nav></body>',
        )
        proc, report = self.check()
        self.assert_only_property_fails(proc, report, "variant")

    def test_fails_when_several_variants_are_declared(self):
        manifest = self.manifest()
        manifest["variant"] = ["A", "B"]
        self.write_manifest(manifest)
        proc, report = self.check()
        self.assert_only_property_fails(proc, report, "variant")

    def test_fails_when_the_encoding_is_not_declared(self):
        manifest = self.manifest()
        del manifest["encoding"]
        self.write_manifest(manifest)
        proc, report = self.check()
        self.assert_only_property_fails(proc, report, "encoding")

    def test_fails_when_a_page_does_not_declare_the_encoding(self):
        self.edit_page("empty.html", '<meta charset="utf-8">\n', "")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "encoding")
        self.assertIn("states/empty.html", failures[0])

    def test_fails_when_reference_themes_are_not_declared(self):
        manifest = self.manifest()
        manifest["themes"] = []
        self.write_manifest(manifest)
        proc, report = self.check()
        self.assert_only_property_fails(proc, report, "viewports_themes")

    def test_fails_when_reference_screen_sizes_are_not_declared(self):
        manifest = self.manifest()
        del manifest["viewports"]
        self.write_manifest(manifest)
        proc, report = self.check()
        self.assert_only_property_fails(proc, report, "viewports_themes")

    def test_fails_without_a_manifest(self):
        (self.prototype / "validated-prototype.json").unlink()
        proc, report = self.check()
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(report["ok"])
        self.assertIn("validated-prototype.json", report["error"])


if __name__ == "__main__":
    unittest.main()
