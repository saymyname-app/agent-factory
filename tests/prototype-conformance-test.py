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

    # --- T46 (af-lb9zkz): winning variant alone, anchors per region, branch ----

    def test_fails_when_the_directory_holds_a_page_the_manifest_does_not_reference(self):
        losing = self.prototype / "states" / "content-variant-b.html"
        shutil.copy(self.prototype / "states" / "content.html", losing)
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "variant")
        self.assertEqual(1, len(failures))
        self.assertIn("states/content-variant-b.html", failures[0])
        self.assertIn("variante perdante", failures[0])

    def test_fails_when_one_anchor_holds_every_visible_element_of_a_state(self):
        self.edit_page("content.html", "<body>", '<body><div data-anchor="page">')
        self.edit_page("content.html", "</body>", "</div></body>")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "anchors")
        self.assertEqual(1, len(failures))
        for fragment in ("content", "states/content.html", "<div>", "page", "tous les éléments visibles"):
            self.assertIn(fragment, failures[0])

    def test_fails_when_a_single_anchor_is_the_only_one_of_a_state(self):
        self.edit_page("empty.html", "<body>", '<body data-anchor="page">')
        for name in ("fixture-state", "fixture-generated-at", "fixture-items"):
            self.edit_page("empty.html", f' data-anchor="{name}"', "")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "anchors")
        self.assertIn("empty", failures[0])
        self.assertIn("<body>", failures[0])

    def test_fails_when_a_region_element_has_no_anchor_of_its_own(self):
        for region in ("header", "nav", "main", "aside", "footer", "form", "table", "dialog"):
            with self.subTest(region=region):
                shutil.rmtree(self.prototype)
                shutil.copytree(FIXTURE_PROTOTYPE, self.prototype)
                inner = "<tr><td>x</td></tr>" if region == "table" else "<span>x</span>"
                self.edit_page(
                    "content.html", "</body>",
                    f'<div data-anchor="extra"><{region}>{inner}</{region}></div></body>',
                )
                proc, report = self.check()
                failures = self.assert_only_property_fails(proc, report, "anchors")
                self.assertEqual(1, len(failures))
                for fragment in ("content", "states/content.html", f"<{region}>", "sa propre ancre"):
                    self.assertIn(fragment, failures[0])

    def test_passes_when_each_region_has_its_own_anchor_even_if_main_holds_the_page(self):
        self.edit_page("content.html", "<body>", '<body><main data-anchor="fixture-main">')
        self.edit_page(
            "content.html", "</body>",
            '<form data-anchor="fixture-form"><input name="q"></form></main></body>',
        )
        proc, report = self.check()
        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertTrue(report["ok"])

    def test_fails_when_a_region_anchor_holds_the_page_and_leaves_elements_without_a_nearer_anchor(self):
        self.edit_page("content.html", "<body>", '<body><main data-anchor="fixture-main">')
        self.edit_page("content.html", "</body>", "<p>hors ancre plus proche</p></main></body>")
        proc, report = self.check()
        failures = self.assert_only_property_fails(proc, report, "anchors")
        self.assertIn("<main>", failures[0])

    # --- T46: the reference lives on a prototype branch that was never merged ---

    def git(self, *args, cwd):
        env = {
            "PATH": "/usr/bin:/bin", "HOME": str(self.tmp), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        proc = subprocess.run(("git", *args), cwd=cwd, env=env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def remote_with(self, branch, merged):
        """A remote whose protected branch is main and whose `branch` holds the
        prototype; `merged` merges that branch into main."""
        work = self.tmp / "work"
        work.mkdir()
        self.git("init", "-q", "-b", "main", ".", cwd=work)
        (work / "README").write_text("produit\n")
        self.git("add", "-A", cwd=work)
        self.git("commit", "-q", "-m", "produit", cwd=work)
        self.git("checkout", "-q", "-b", branch, cwd=work)
        shutil.copytree(FIXTURE_PROTOTYPE, work / "prototype")
        self.git("add", "-A", cwd=work)
        self.git("commit", "-q", "-m", "prototype", cwd=work)
        commit = self.git("rev-parse", "HEAD", cwd=work)
        if merged:
            self.git("checkout", "-q", "main", cwd=work)
            self.git("merge", "-q", "--no-ff", "-m", "fusion", branch, cwd=work)
        remote = self.tmp / "remote.git"
        self.git("clone", "-q", "--bare", str(work), str(remote), cwd=self.tmp)
        return remote, commit

    def check_reference(self, branch, merged):
        remote, commit = self.remote_with(branch, merged)
        return self.check("--branch", branch, "--commit", commit, "--remote", str(remote), "--protected", "main")

    def test_passes_on_a_prototype_branch_never_merged_with_a_seventh_record_for_the_reference(self):
        proc, report = self.check_reference("prototype/fixture", merged=False)
        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertEqual([*PROPERTIES, "reference"], [record["property"] for record in report["properties"]])

    def test_fails_when_the_branch_is_not_a_prototype_branch(self):
        proc, report = self.check_reference("feature/fixture", merged=False)
        failures = self.assert_only_property_fails(proc, report, "reference")
        self.assertEqual(1, len(failures))
        self.assertIn("feature/fixture", failures[0])
        self.assertIn("prototype/", failures[0])

    def test_fails_when_the_commit_is_reachable_from_the_protected_branch_of_the_remote(self):
        proc, report = self.check_reference("prototype/fixture", merged=True)
        failures = self.assert_only_property_fails(proc, report, "reference")
        self.assertEqual(1, len(failures))
        for fragment in ("atteignable", "branche protégée main", "fusionnée"):
            self.assertIn(fragment, failures[0])

    def test_fails_when_the_commit_of_the_reference_is_not_in_the_remote(self):
        remote, _ = self.remote_with("prototype/fixture", merged=False)
        proc, report = self.check(
            "--branch", "prototype/fixture", "--commit", "0" * 40, "--remote", str(remote), "--protected", "main",
        )
        failures = self.assert_only_property_fails(proc, report, "reference")
        self.assertIn("introuvable", failures[0])

    def test_refuses_a_reference_given_in_part(self):
        proc = subprocess.run(
            (str(TOOL), "check", "--prototype", str(self.prototype), "--branch", "prototype/fixture"),
            text=True, capture_output=True,
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("--commit", json.loads(proc.stdout)["error"])


    def test_fails_without_a_manifest(self):
        (self.prototype / "validated-prototype.json").unlink()
        proc, report = self.check()
        self.assertNotEqual(0, proc.returncode)
        self.assertFalse(report["ok"])
        self.assertIn("validated-prototype.json", report["error"])


if __name__ == "__main__":
    unittest.main()
