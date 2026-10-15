#!/usr/bin/env python3
"""CLI ratchet on disposable Git repositories, including rename and exceptions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "project-standards"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
       "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


class RatchetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        (self.repo / ".factory").mkdir()
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 2}])
        self.write(".factory/never-frozen.json", {"contract": "agent-factory-never-frozen/v1",
                                                   "rules": ["bugs/no-unsafe"]})
        self.write("src/App.tsx", "old source\n")
        self.write("STANDARDS.md", "# Standards\n\n## Dérogations\n\nAucune.\n")
        self.commit("base")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], env=ENV, check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n" if not isinstance(value, str) else value)

    def entries(self, entries):
        self.write(".factory/frozen-list.json", {"contract": "agent-factory-frozen-list/v1", "entries": entries})

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def check(self):
        result = subprocess.run([str(TOOL), "ratchet", "--target", str(self.repo),
                                 "--base-ref", "HEAD^", "--head-ref", "HEAD"],
                                capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def test_decrease_passes_and_increase_refuses_with_location(self):
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 1}])
        self.commit("reduce")
        code, answer = self.check()
        self.assertEqual((0, True), (code, answer["ok"]), answer)
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 3}])
        self.commit("increase")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("style/color", answer["error"])
        self.assertIn("src/App.tsx", answer["error"])

    def test_rename_carries_the_existing_count(self):
        self.git("mv", "src/App.tsx", "src/Home.tsx")
        self.entries([{"rule": "style/color", "path": "src/Home.tsx", "count": 2}])
        self.commit("rename")
        code, answer = self.check()
        self.assertEqual(0, code, answer)

    def test_eslint_native_suppressions_are_counted(self):
        self.write("eslint-suppressions.json", {"src/App.tsx": {"@typescript-eslint/no-explicit-any": {"count": 2}}})
        self.commit("eslint baseline")
        self.write("eslint-suppressions.json", {"src/App.tsx": {"@typescript-eslint/no-explicit-any": {"count": 3}}})
        self.commit("more suppressed lint")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("@typescript-eslint/no-explicit-any", answer["error"])

    def test_probable_bug_cannot_be_frozen_as_eslint_suppression(self):
        self.write("eslint-suppressions.json", {"src/App.tsx": {
            "@typescript-eslint/no-unsafe-assignment": {"count": 1}}})
        self.commit("unsafe baseline")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("seuls les écarts", answer["error"])

    def test_adopted_project_requires_initial_photo(self):
        self.write(".factory/standards-origin.json", {"contract": "agent-factory-standards-origin/v1",
                                                    "stack": "react-typescript", "version": "2"})
        self.commit("adopt without photo")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("photo initiale absente", answer["error"])

    def test_first_adoption_accepts_recorded_existing_violation(self):
        self.write(".factory/standards-origin.json", {"contract": "agent-factory-standards-origin/v1",
                                                    "stack": "react-typescript", "version": "2"})
        self.write(".factory/baseline-record.json", {"contract": "agent-factory-baseline/v1",
                                                "stack": "react-typescript"})
        self.write("eslint-suppressions.json", {"src/App.tsx": {
            "@typescript-eslint/no-explicit-any": {"count": 2},
            "@typescript-eslint/naming-convention": {"count": 1}}})
        self.commit("first photo")
        code, answer = self.check()
        self.assertEqual(0, code, answer)
        self.assertTrue(answer["initial_photo"])

    def test_eslint_rename_carries_count(self):
        self.write("eslint-suppressions.json", {"src/App.tsx": {"@typescript-eslint/no-explicit-any": {"count": 2}}})
        self.commit("eslint baseline")
        self.git("mv", "src/App.tsx", "src/Home.tsx")
        self.entries([{"rule": "style/color", "path": "src/Home.tsx", "count": 2}])
        self.write("eslint-suppressions.json", {"src/Home.tsx": {"@typescript-eslint/no-explicit-any": {"count": 2}}})
        self.commit("rename with suppression")
        code, answer = self.check()
        self.assertEqual(0, code, answer)

    def test_archunit_store_increase_is_counted_without_manifest_edit(self):
        self.write(".factory/archunit-freeze/stored.rules", "architecture=sample-id\n")
        self.write(".factory/archunit-freeze/sample-id",
                   "Field <example.persistence.Dao.api> has type <example.web.Api> in (Dao.java:1)\n")
        self.commit("architecture baseline")
        self.write(".factory/archunit-freeze/sample-id",
                   "Field <example.persistence.Dao.api> has type <example.web.Api> in (Dao.java:1)\n"
                   "Constructor <example.persistence.Dao.<init>()> calls constructor <example.web.Api.<init>()> in (Dao.java:2)\n")
        self.commit("refreeze architecture")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("archunit/persistence-to-web", answer["error"])

    def test_depcruise_baseline_increase_is_counted_without_manifest_edit(self):
        self.write(".dependency-cruiser-known-violations.json", [
            {"type": "dependency", "from": "src/domain/a.ts", "to": "src/ui/a.ts",
             "rule": {"name": "domain-isolation", "severity": "error"}}])
        self.commit("architecture baseline")
        self.write(".dependency-cruiser-known-violations.json", [
            {"type": "dependency", "from": "src/domain/a.ts", "to": "src/ui/a.ts",
             "rule": {"name": "domain-isolation", "severity": "error"}},
            {"type": "dependency", "from": "src/domain/a.ts", "to": "src/ui/b.ts",
             "rule": {"name": "domain-isolation", "severity": "error"}}])
        self.commit("refreeze architecture")
        code, answer = self.check()
        self.assertNotEqual(0, code)
        self.assertIn("dependency-cruiser/domain-isolation", answer["error"])

    def test_never_frozen_rule_refuses_even_with_snapshot(self):
        self.entries([{"rule": "bugs/no-unsafe", "path": "src/App.tsx", "count": 1}])
        self.write(".factory/ratchet-snapshot.json", {"rule": "bugs/no-unsafe", "config": "eslint.config.mjs"})
        self.write("eslint.config.mjs", "export default {}\n")
        self.commit("bug baseline")
        self.assertNotEqual(0, self.check()[0])

    def test_one_new_snapshot_requires_matching_config_change(self):
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 4}])
        self.write(".factory/ratchet-snapshot.json", {"rule": "style/color", "config": "eslint.config.mjs"})
        self.commit("snapshot without config")
        self.assertNotEqual(0, self.check()[0])
        self.git("reset", "--soft", "HEAD^")
        self.write("eslint.config.mjs", "export default {}\n")
        self.commit("snapshot and configuration")
        self.assertNotEqual(0, self.check()[0], "un fichier sans la règle ne justifie pas la photo")
        self.write("eslint.config.mjs", "export default {'style/color': 'warn'}\n")
        self.commit("configuration of this rule")
        code, answer = self.check()
        self.assertEqual(0, code, answer)

    def test_depcruise_snapshot_needs_real_rule_change(self):
        rule = "dependency-cruiser/domain-isolation"
        old_config = "module.exports={forbidden:[{name:'domain-isolation',from:{path:'^src/domain/'},to:{path:'^src/ui/'}}]}\n"
        self.write(".dependency-cruiser.cjs", old_config)
        self.entries([{"rule": rule, "path": "src/App.tsx", "count": 1}])
        self.commit("old architecture")
        self.entries([{"rule": rule, "path": "src/App.tsx", "count": 2}])
        self.write(".factory/ratchet-snapshot.json", {"rule": rule, "config": ".dependency-cruiser.cjs"})
        self.write(".dependency-cruiser.cjs", old_config + "// cosmetic\n")
        self.commit("cosmetic change")
        self.assertNotEqual(0, self.check()[0])
        self.git("reset", "--soft", "HEAD^")
        self.write(".dependency-cruiser.cjs", old_config.replace("^src/ui/", "^src/(ui|app)/"))
        self.commit("changed forbidden target")
        self.assertEqual(0, self.check()[0])

    def test_archunit_snapshot_needs_real_rule_change(self):
        rule = "archunit/persistence-to-web"
        old_config = ('noClasses().that().resideInAPackage("..persistence..")'
                      '.should().dependOnClassesThat().resideInAPackage("..web..");\n')
        path = "src/test/java/example/ArchitectureTest.java"
        self.write(path, old_config)
        self.entries([{"rule": rule, "path": "src/App.tsx", "count": 1}])
        self.commit("old architecture")
        self.entries([{"rule": rule, "path": "src/App.tsx", "count": 2}])
        self.write(".factory/ratchet-snapshot.json", {"rule": rule, "config": path})
        self.write(path, old_config + "// cosmetic\n")
        self.commit("cosmetic change")
        self.assertNotEqual(0, self.check()[0])
        self.git("reset", "--soft", "HEAD^")
        self.write(path, old_config.replace("..web..", "..webx.."))
        self.commit("changed forbidden package")
        self.assertEqual(0, self.check()[0])

    def test_derogation_is_bounded_to_rule_and_location(self):
        self.write("STANDARDS.md", "# Standards\n\n## Derogations\n\n"
                   "| Standard | Endroit | Intent | Date | Fin |\n"
                   "| --- | --- | --- | --- | --- |\n"
                   "| style/color | src/App.tsx | « Je garde cette couleur. » | 2026-10-13 13:49 Paris | 2026-12-01 |\n")
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 3}])
        self.commit("unapproved simultaneous increase")
        self.assertNotEqual(0, self.check()[0])
        self.git("reset", "--soft", "HEAD^")
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 2}])
        self.commit("record bounded derogation first")
        self.entries([{"rule": "style/color", "path": "src/App.tsx", "count": 3}])
        self.commit("increase under prior derogation")
        code, answer = self.check()
        self.assertEqual(0, code, answer)


if __name__ == "__main__":
    unittest.main()
