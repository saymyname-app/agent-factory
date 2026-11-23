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

    def test_every_class_lists_its_concrete_rules_each_with_its_sentence_and_passage(self):
        # af-56yoam.1: a family groups 3 to 30 rules; the measure counts by rule.
        for code, entry in defect_classes.load().items():
            self.assertTrue(entry["rules"], code)
            for rule_id, rule in entry["rules"].items():
                self.assertRegex(rule_id, rf"^{code}\.[a-z0-9-]+$")
                self.assertTrue(rule["rule"].endswith("."), rule_id)
                self.assertTrue(rule["passage"], rule_id)
        known = defect_classes.rules(defect_classes.load())
        self.assertLessEqual({"P.own", "P.budget", "P.load", "I.repair-resume"}, set(known))
        self.assertIn("lib/bounded_process.py", known["P.own"]["passage"])

    def test_a_rule_is_read_and_a_misplaced_or_incomplete_rule_is_refused(self):
        head = "## P — x\n\n- Invariant : y\n"
        tail = "- Contrôle : aucun — z\n- Occurrences : #1\n- Ouvertes : aucune connue.\n"
        cases = [
            # (rules block, expected rules or the refusal)
            ("", {}),
            ("- Règles :\n  - `P.own` : Meurt avec son\n    propriétaire. Passage : `lib/b.py`.\n",
             {"P.own": ("Meurt avec son propriétaire.", "`lib/b.py`")}),
            ("- Règles :\n  - `I.own` : Phrase. Passage : aucun.\n", "rangée sous la catégorie P"),
            ("- Règles :\n  - `P.own` : Phrase sans passage.\n", "sans sa phrase"),
            ("- Règles :\n  - `P.own` : A. Passage : aucun.\n  - `P.own` : B. Passage : aucun.\n", "en double"),
        ]
        for block, expected in cases:
            with self.subTest(block=block), tempfile.TemporaryDirectory() as tmp:
                registry = Path(tmp) / "r.md"
                registry.write_text(head + block + tail, encoding="utf-8")
                if isinstance(expected, str):
                    with self.assertRaisesRegex(defect_classes.RegistryError, expected):
                        defect_classes.load(registry)
                    continue
                entry = defect_classes.load(registry)["P"]
                self.assertEqual(expected, {k: (r["rule"], r["passage"]) for k, r in entry["rules"].items()})
                self.assertEqual("aucune connue.", entry["Ouvertes"])


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

    def test_an_optional_rule_line_must_name_a_rule_of_the_register(self):
        cases = [
            ("", 0),
            ("Règle : P.own\n", 0),
            ("**Règle :** `I.repair-resume` — prévue (af-x)\n", 0),
            ("Règle : aucune — décision\n", 0),
            ("Règle : P.ownership\n", 1),
            ("Règle : P\n", 1),
        ]
        for line, problems in cases:
            with self.subTest(line=line):
                found = self.check(BODY + line)
                self.assertEqual(problems, len(found), found)
                if problems:
                    self.assertIn("Règle", found[0])
        self.assertEqual(1, len(self.check("Catégorie : aucune — doc\nRègle : X.y\n")))

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


KNOWN = {"P.own": {}, "P.load": {}, "S.autre": {}, "I.repair-resume": {}}


def row(number, date, rule, nature):
    return {"pr": number, "date": date, "rule": rule, "nature": nature, "evidence": ""}


class ByRuleTest(unittest.TestCase):
    """af-56yoam.1: first fixes, planned repeats and slips per rule and month."""

    def test_the_baseline_is_complete_and_names_rules_of_the_register(self):
        known = defect_classes.rules(defect_classes.load())
        baseline = defect_classes.load_baseline(known=known)

        self.assertLessEqual(set(range(717, 930)) - {714, 715, 716}, set(baseline))
        self.assertEqual("aucune", baseline[737]["rule"])
        self.assertEqual(("I.repair-resume", "premiere"), (baseline[783]["rule"], baseline[783]["nature"]))
        decision = defect_classes.d1(baseline)
        self.assertEqual("2026-12-21", decision["review"])
        self.assertIn("I.repair-resume", decision["watched"])
        self.assertEqual(decision["reference_slips"] // 2, decision["monthly_max"])

    def test_a_baseline_row_with_an_unknown_rule_or_nature_is_refused(self):
        for line, refusal in [("1\t2026-11-01\tP.nope\tpremiere\tx\n", "P.nope"),
                              ("1\t2026-11-01\tP.own\tslip\tx\n", "nature"),
                              ("1\t2026-11-01\taucune\tpremiere\tx\n", "aucune")]:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "b.tsv"
                path.write_text("# c\npr\tdate\tregle\tnature\tpreuve\n" + line, encoding="utf-8")
                with self.assertRaisesRegex(defect_classes.RegistryError, refusal):
                    defect_classes.load_baseline(path, KNOWN)

    def test_each_pull_request_is_counted_by_rule_month_and_nature(self):
        baseline = {10: row(10, "2026-10-30", "P.own", "premiere"),
                    11: row(11, "2026-11-02", "P.own", "glissement"),
                    12: row(12, "2026-11-03", "aucune", "-"),
                    13: row(13, "2026-11-04", "S.autre", "premiere")}
        cases = [
            # (body of the later PR, its merge time UTC, expected rule and nature, or None if unclassified)
            ("Règle : P.own\n", "2026-11-30T23:30:00Z", ("P.own", "glissement", "2026-12")),
            ("Règle : P.own — prévue (af-x)\n", "2026-11-20T10:00:00Z", ("P.own", "prevue", "2026-11")),
            ("Règle : P.load\n", "2026-11-20T10:00:00Z", ("P.load", "premiere", "2026-11")),
            ("Règle : S.autre\n", "2026-11-20T10:00:00Z", ("S.autre", "premiere", "2026-11")),
            ("Règle : aucune — doc\n", "2026-11-20T10:00:00Z", None),
            ("Catégorie : P\n", "2026-11-20T10:00:00Z", "unclassified"),
            ("Règle : P.nope\n", "2026-11-20T10:00:00Z", "unclassified"),
        ]
        for body, merged_at, expected in cases:
            with self.subTest(body=body):
                prs = [{"number": 20, "body": body, "mergedAt": merged_at}, {"number": 11, "body": "", "mergedAt": "x"}]
                counted = defect_classes.by_rule(prs, baseline, KNOWN, "2026-10-01")
                if expected == "unclassified":
                    self.assertEqual([20], counted["unclassified"])
                    continue
                self.assertEqual([], counted["unclassified"])
                if expected is None:
                    self.assertEqual([12, 20], counted["no_defect"])
                    continue
                rule, nature, month = expected
                before = defect_classes.by_rule([], baseline, KNOWN, "2026-10-01")["rules"]
                self.assertEqual(before.get(rule, {}).get(month, {}).get(nature, 0) + 1,
                                 counted["rules"][rule][month][nature])
        counted = defect_classes.by_rule([], baseline, KNOWN, "2026-11-01")
        self.assertEqual({"2026-11": {"premiere": 1, "prevue": 0, "glissement": 1}}, counted["months"])
        self.assertEqual({"P.own": [11]}, counted["slips"])

    def test_a_rule_fixed_before_the_window_still_makes_a_later_fix_a_slip(self):
        baseline = {10: row(10, "2026-10-30", "P.own", "premiere")}
        prs = [{"number": 20, "body": "Règle : P.own\n", "mergedAt": "2026-12-02T10:00:00Z"}]

        counted = defect_classes.by_rule(prs, baseline, KNOWN, "2026-12-01")

        self.assertEqual({"P.own": [20]}, counted["slips"])

    def test_count_by_rule_reads_the_baseline_and_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            prs = [{"number": 9999, "body": BODY + "Règle : P.own\n", "mergedAt": "2026-12-02T10:00:00Z"}]
            gh.write_text(f"#!/bin/sh\ncat <<'JSON'\n{json.dumps(prs)}\nJSON\n")
            gh.chmod(0o755)
            proc = subprocess.run([sys.executable, str(TOOL), "count", "--by-rule", "--since", "2026-10-22"], text=True,
                                  capture_output=True, env={**os.environ, "GH_BIN": str(gh)}, cwd=tmp)

            self.assertEqual(0, proc.returncode, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(1, out["rules"]["P.own"]["2026-12"]["glissement"])
            self.assertIn("P.own", out["d1"]["watched"])
            self.assertEqual([], out["unclassified"])


if __name__ == "__main__":
    unittest.main()
