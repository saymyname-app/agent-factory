#!/usr/bin/env python3
"""docs/DEFECT_CLASSES.md and lib/defect_classes.py (af-npz9v1.25, study B,
PR #720). The register is complete, every control it names exists, and a
maintenance pull request without its three lines (« Catégorie : », « Où
ailleurs : », « Contrôle de catégorie : ») is named as such: from 15 to
22/10 every fix repaired the case it saw and wrote the rest « hors
périmètre », and the rest came back."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import defect_classes  # noqa: E402

TOOL = ROOT / "lib" / "defect_classes.py"
BODY = """Corrige af-kky570.

Catégorie : P — programme qui survit à son lanceur
Où ailleurs : grep de `subprocess.run(..., timeout=` dans bin/ et lib/ : 6 chemins, af-npz9v1.26.
Contrôle de catégorie : tests/project-launch-test.py, balayage d'un dossier supprimé.
"""


class RegisterTest(unittest.TestCase):
    def test_the_register_is_complete(self):
        classes = defect_classes.load()

        self.assertLessEqual({"P", "I", "D", "R", "S", "A"}, set(classes))
        for entry in classes.values():
            for field in defect_classes.FIELDS:
                self.assertTrue(entry[field], f"{entry['code']} : {field}")

    def test_every_control_names_a_file_that_exists(self):
        for entry in defect_classes.load().values():
            for command in entry["commands"]:
                script = command.split()[1]
                self.assertTrue((ROOT / script).is_file(), f"{entry['code']} : {command}")

    def test_an_incomplete_entry_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "r.md"
            registry.write_text("## P — x\n\n- Invariant : y\n- Contrôle : aucun — z\n- Occurrences : #1\n")
            with self.assertRaisesRegex(defect_classes.RegistryError, "Ouvertes"):
                defect_classes.load(registry)

    def test_a_long_value_continues_on_indented_lines(self):
        entry = defect_classes.load()["P"]

        self.assertIn("quelle que soit", entry["Invariant"])
        self.assertTrue(entry["Invariant"].endswith("mesure."))


class PullRequestBodyTest(unittest.TestCase):
    def setUp(self):
        self.classes = defect_classes.load()

    def check(self, body):
        return defect_classes.check_pr_body(body, self.classes)

    def test_a_complete_body_passes(self):
        self.assertEqual([], self.check(BODY))

    def test_each_missing_line_is_named(self):
        problems = self.check("Corrige le cas observé.\n")

        self.assertEqual(3, len(problems))
        for label in ("Catégorie :", "Où ailleurs :", "Contrôle de catégorie :"):
            self.assertTrue(any(label in p for p in problems), label)

    def test_a_class_missing_from_the_register_is_named(self):
        problems = self.check(BODY.replace("Catégorie : P", "Catégorie : Q"))

        self.assertEqual(1, len(problems))
        self.assertIn("« Q »", problems[0])

    def test_a_change_that_fixes_no_defect_says_why(self):
        self.assertEqual([], self.check("Catégorie : aucune — ajoute une porte décidée par Benjamin\n"))
        self.assertEqual(1, len(self.check("Catégorie : aucune\n")))

    def test_markdown_emphasis_is_read(self):
        body = BODY.replace("Catégorie : P", "**Catégorie :** `P`").replace("Où ailleurs :", "- **Où ailleurs :**")

        self.assertEqual([], self.check(body))

    def test_the_command_line_names_what_is_missing(self):
        proc = subprocess.run([sys.executable, str(TOOL), "check-pr-body"], input="Catégorie : P\n", text=True,
                              capture_output=True)

        self.assertEqual(1, proc.returncode)
        self.assertIn("Où ailleurs :", proc.stdout)
        ok = subprocess.run([sys.executable, str(TOOL), "check-pr-body"], input=BODY, text=True,
                            capture_output=True)
        self.assertEqual((0, ""), (ok.returncode, ok.stdout.strip()))


class CountTest(unittest.TestCase):
    def test_merged_pull_requests_are_counted_by_class(self):
        prs = [{"number": 801, "body": BODY}, {"number": 802, "body": "Catégorie : I\n"},
               {"number": 803, "body": "Catégorie : aucune — doc\n"}, {"number": 804, "body": "rien"},
               {"number": 805, "body": BODY}]

        counted = defect_classes.count(prs, defect_classes.load())

        self.assertEqual([801, 805], counted["by_class"]["P"])
        self.assertEqual([802], counted["by_class"]["I"])
        self.assertEqual(([803], [804]), (counted["no_defect"], counted["untagged"]))

    def test_count_reads_the_merged_pull_requests_from_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            gh.write_text("#!/bin/sh\necho \"$*\" > \"$(dirname \"$0\")/args\"\n"
                          f"cat <<'JSON'\n{json.dumps([{'number': 9, 'body': BODY}])}\nJSON\n")
            gh.chmod(0o755)
            proc = subprocess.run([sys.executable, str(TOOL), "count", "--since", "2026-10-27"], text=True,
                                  capture_output=True, env={**os.environ, "GH_BIN": str(gh)}, cwd=tmp)

            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual([9], json.loads(proc.stdout)["by_class"]["P"])
            self.assertIn("merged:>=2026-10-27", (Path(tmp) / "args").read_text())


if __name__ == "__main__":
    unittest.main()
