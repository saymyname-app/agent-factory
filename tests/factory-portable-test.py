#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import factory_portable as portable
import factory_cockpit as cockpit


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.dest = self.base / "distribution"
        portable.export(self.dest)
        self.root_patch = patch.object(portable, "ROOT", self.dest)
        self.root_patch.start()
        portable.profile(argparse.Namespace(operator="Camille", po_model="test-po", writer_model="test-writer"))

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def project(self, mode="new", repos=None):
        return portable.project(argparse.Namespace(mode=mode, slug="demo", name="Demo",
                                                   repo=repos or []))

    def test_export_excludes_runtime_profile_products_and_history(self):
        target = self.base / "share-again"
        portable.export(target)
        for name in [".local", ".git", ".gc", ".beads", "city.toml", "docs/products", "config/products", "rigs"]:
            self.assertFalse((target / name).exists(), name)
        self.assertTrue((target / "distribution.json").is_file())
        self.assertTrue(os.access(target / "bin/factory-portable", os.X_OK))
        # A usable distribution can export itself, without consulting original repo.
        result = subprocess.run([str(target / "bin/factory-portable"), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_export_refuses_existing_and_factory_nested_targets(self):
        with self.assertRaises(ValueError): portable.export(self.dest)
        (self.base / "city.toml").write_text("[workspace]")
        with self.assertRaises(ValueError): portable.export(self.base / "nested")
        self.assertFalse((self.base / "nested").exists())

    def test_export_rejects_symlink_source(self):
        path = self.dest / "bin/product-queue"
        path.unlink()
        path.symlink_to(ROOT / "bin/product-queue")
        with self.assertRaises(ValueError): portable.export(self.base / "unsafe")
        self.assertFalse((self.base / "unsafe").exists())

    def test_profile_never_overwrites(self):
        with self.assertRaises(ValueError):
            portable.profile(argparse.Namespace(operator="Other", po_model="a", writer_model="b"))
        self.assertEqual(json.loads((self.dest / ".local/profile.json").read_text())["operator"], "Camille")

    def test_new_project_is_incomplete_and_not_runtime(self):
        self.project()
        result = portable.readiness("demo")
        self.assertFalse(result["definition_ready"])
        self.assertFalse(result["delivery_authorized"])
        self.assertFalse((self.dest / ".gc").exists())
        with self.assertRaises(ValueError): self.project()

    def test_import_preserves_dirty_repository(self):
        repo = self.base / "source"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "app.txt").write_text("original")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "initial"], check=True)
        (repo / "app.txt").write_text("user edit")
        before = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"])
        self.project("import", [str(repo)])
        self.assertEqual((repo / "app.txt").read_text(), "user edit")
        self.assertEqual(before, subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"]))
        self.assertFalse((repo / ".beads").exists())
        snapshot = json.loads((self.dest / "docs/products/demo/IMPORT.json").read_text())
        self.assertTrue(snapshot["sources"][0]["dirty"])
        self.assertNotIn("remote", snapshot["sources"][0])

    def test_import_requires_existing_root_and_slug_cannot_escape(self):
        with self.assertRaises(ValueError): self.project("import", [])
        with self.assertRaises(ValueError): self.project("import", [str(self.base / "missing")])
        with self.assertRaises(ValueError):
            portable.project(argparse.Namespace(mode="new", slug="../escape", name="X", repo=[]))
        self.assertFalse((self.dest / "docs/products/demo").exists())

    def complete(self):
        self.project()
        dossier = self.dest / "docs/products/demo"
        evidence = dossier / "evidence.md"
        evidence.write_text("Reviewed release scope, constraints and observable acceptance for this test fixture.")
        path = dossier / "readiness.json"
        data = json.loads(path.read_text())
        for item in data["requirements"].values():
            item.update(status="defined", evidence=["evidence.md"], reviewed_by="PO",
                        rationale="Reviewed fixture scope.")
        portable.write(path, data)
        digest = portable.readiness("demo")["evidence_digest"]
        data["po_review"] = {"reviewer": "PO", "summary": "Reviewed all definitions.", "evidence_digest": digest}
        portable.write(path, data)
        return path, data, evidence

    def test_readiness_stale_evidence_invalidates_review(self):
        path, data, evidence = self.complete()
        self.assertTrue(portable.readiness("demo")["definition_ready"])
        self.assertFalse(portable.readiness("demo")["delivery_authorized"])
        evidence.write_text("Changed release scope")
        result = portable.readiness("demo")
        self.assertFalse(result["definition_ready"])
        self.assertIn("PO final review missing or stale", result["blocking"])

    def test_placeholder_blocker_and_path_escape_fail_closed(self):
        path, data, evidence = self.complete()
        evidence.write_text("TODO")
        self.assertFalse(portable.readiness("demo")["definition_ready"])
        evidence.write_text("Resolved")
        data["requirements"]["vision"]["evidence"] = ["../../../portable/AGENTS.md"]
        data["decisions"] = [{"id": "price", "status": "deferred", "blocks_release": True}]
        portable.write(path, data)
        result = portable.readiness("demo")
        self.assertTrue(any("local dossier" in x for x in result["blocking"]))
        self.assertIn("blocking decision: price", result["blocking"])

    def test_bootstrap_is_plan_only_and_refuses_existing_runtime(self):
        result = portable.bootstrap_plan()
        self.assertFalse(result["executed"])
        self.assertIn("--no-start", result["commands"][0])
        self.assertFalse((self.dest / "city.toml").exists())
        (self.dest / ".gc").mkdir()
        with self.assertRaises(ValueError): portable.bootstrap_plan()

    def test_generic_cockpit_identity_preview_and_config(self):
        self.project()
        with patch.object(cockpit, "ROOT", self.dest):
            config = cockpit.load_product_config(self.dest / "config/products/demo.json")
            self.assertTrue(Path(config["queue_command"][0]).is_absolute())
            bridge = cockpit.POBridge(config, self.base / "po-state.json")
            prompt = bridge._prompt("Prepare scope", "discuss", None)
            self.assertIn("Demo", prompt)
            self.assertIn("Camille", prompt)
            self.assertNotIn("SayMyName", prompt)
            self.assertNotIn("Benjamin", prompt)
            def forbidden(*a, **kw): raise AssertionError("Unconfigured preview executed")
            preview = cockpit.PreviewBridge(executor=forbidden, config=config)
            self.assertEqual(preview.status()["state"], "unconfigured")
            with self.assertRaises(ValueError): preview.submit("start")

    def test_po_model_and_sandbox_apply_to_new_and_resumed_calls(self):
        self.project()
        commands = []
        def execute(command, **kwargs):
            commands.append(command)
            Path(command[command.index("-o") + 1]).write_text("Prepared")
            return subprocess.CompletedProcess(command, 0, '{"thread_id":"test-thread"}\n', "")
        with patch.object(cockpit, "ROOT", self.dest):
            config = cockpit.load_product_config(self.dest / "config/products/demo.json")
            bridge = cockpit.POBridge(config, self.base / "po-state.json", execute)
            # Drive synchronously to verify argv without paid model calls.
            state = bridge._empty()
            state["conversations"]["general:test"] = {"key": "general:test", "messages": [], "thread_id": None}
            bridge._write(state)
            bridge._run("general:test", "Prepare", "discuss", None)
            bridge._run("general:test", "Continue", "discuss", None)
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertIn("test-po", command)
            self.assertIn('sandbox_mode="workspace-write"', command)
        self.assertIn("resume", commands[1])


if __name__ == "__main__":
    unittest.main()
