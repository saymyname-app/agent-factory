#!/usr/bin/env python3
"""docs/DEFECT_CLASSES.md and lib/defect_classes.py (af-npz9v1.25, study B,
PR #720). The register is complete, every control it names exists, and a
maintenance pull request without its three lines (« Catégorie : », « Où
ailleurs : », « Contrôle de catégorie : ») is named as such: from 15 to
22/10 every fix repaired the case it saw and wrote the rest « hors
périmètre », and the rest came back. Since af-56yoam.2 a fix also names its
rule, its « Où ailleurs » is a command and its result, and a rule already
fixed comes back « prévue (<bead>) » or as a slip through its passage point."""

import json
import os
import re
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
Règle : P.own
Où ailleurs : `grep -rn 'subprocess.run(.*timeout=' bin lib` → 6 chemins, af-npz9v1.26.
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

        self.assertEqual(4, len(problems))
        for label in ("Catégorie :", "Où ailleurs :", "Contrôle de catégorie :", "Règle :"):
            self.assertTrue(any(label in p for p in problems), label)

    def test_a_class_missing_from_the_register_is_named(self):
        problems = self.check(BODY.replace("Catégorie : P", "Catégorie : Q"))

        self.assertEqual(1, len(problems))
        self.assertIn("« Q »", problems[0])

    def test_a_change_that_fixes_no_defect_says_why(self):
        self.assertEqual([], self.check("Catégorie : aucune — ajoute une porte décidée par Benjamin\n"))
        self.assertEqual(1, len(self.check("Catégorie : aucune\n")))
        self.assertEqual(1, len(self.check("Catégorie : aucune — doc\nRègle : X.y\n")))

    def test_the_rule_and_where_else_lines_of_a_fix(self):
        # af-56yoam.2: these rules already have a merged fix.
        fixed = {"P.own", "I.repair-resume", "P.proc-gone", "S.autre"}
        rule = "Règle : P.own\n"
        first = BODY.replace(rule, "Règle : P.load\n")
        cases = [
            # (name, body, the words its one problem holds; [] when the body passes)
            ("PR sans défaut", "Catégorie : aucune — décision D2 exécutée\n", []),
            ("première correction", first, []),
            ("prévue", BODY.replace(rule, "Règle : P.own — prévue (af-npz9v1.26)\n"), []),
            ("prévue, gras et accents graves", BODY.replace(rule, "**Règle :** `P.own` — prévue (af-x)\n"), []),
            ("prévue sans son bead", BODY.replace(rule, "Règle : P.own — prévue\n"), ["sans son bead"]),
            ("règle déjà corrigée, ni prévue ni glissement", BODY, ["déjà corrigée", "glissement"]),
            ("glissement sans point de passage", BODY.replace(rule, "Règle : P.own — glissement\n"),
             ["sans ligne « Point de passage :"]),
            ("glissement par le point de passage de la règle",
             BODY.replace(rule, "Règle : P.own — glissement\nPoint de passage : `lib/bounded_process.py`\n"), []),
            ("glissement par un autre point",
             BODY.replace(rule, "Règle : P.own — glissement\nPoint de passage : `bin/ticket-end`\n"),
             ["« `bin/ticket-end` »", "docs/DEFECT_CLASSES.md"]),
            ("glissement d'une règle sans point de passage",
             BODY.replace(rule, "Règle : P.proc-gone — glissement\nPoint de passage : `lib/procfs.py`\n"),
             ["P.proc-gone", "aucun"]),
            ("défaut isolé : .autre ne glisse jamais", BODY.replace(rule, "Règle : S.autre\n"), []),
            ("identifiant inconnu", BODY.replace(rule, "Règle : P.ownership\n"), ["« P.ownership »"]),
            ("famille sans règle", BODY.replace(rule, "Règle : P\n"), ["« P »"]),
            ("règle aucune sur un correctif", BODY.replace(rule, "Règle : aucune — doc\n"), ["Règle : aucune"]),
            ("règle absente", BODY.replace(rule, ""), ["« Règle : » absente"]),
            ("Où ailleurs sans commande",
             first.replace("`grep -rn 'subprocess.run(.*timeout=' bin lib` → 6", "grep dans bin/ et lib/ : 6"),
             ["sans « `<commande>` → <résultat> »"]),
            ("Où ailleurs sans résultat",
             first.replace("→ 6 chemins, af-npz9v1.26.", ""), ["sans « `<commande>` → <résultat> »"]),
            ("Où ailleurs avec ->", first.replace("→", "->"), []),
        ]
        for name, body, expected in cases:
            with self.subTest(name):
                found = defect_classes.check_pr_body(body, self.classes, fixed)
                self.assertEqual(1 if expected else 0, len(found), found)
                for words in expected:
                    self.assertIn(words, found[0])

    def test_a_slip_may_move_the_passage_point_in_its_own_register(self):
        text = (ROOT / "docs" / "DEFECT_CLASSES.md").read_text(encoding="utf-8")
        old = "erreur. Passage : aucun."
        self.assertEqual(1, text.count(old))
        body = BODY.replace("Règle : P.own\n", "Règle : P.proc-gone — glissement\nPoint de passage : `lib/procfs.py`\n")
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "r.md"
            registry.write_text(text.replace(old, "erreur. Passage : `proc_state` de `lib/procfs.py`."),
                                encoding="utf-8")

            self.assertEqual([], defect_classes.check_pr_body(body, defect_classes.load(registry), {"P.proc-gone"}))

    def test_the_fixed_rules_are_asked_only_when_a_plain_rule_line_needs_them(self):
        asked = []

        def fixed():
            asked.append(1)
            return {"P.own"}

        defect_classes.check_pr_body(BODY.replace("Règle : P.own", "Règle : P.own — prévue (af-x)"), self.classes, fixed)
        defect_classes.check_pr_body("Catégorie : aucune — doc\n", self.classes, fixed)
        self.assertEqual([], asked)
        self.assertEqual(1, len(defect_classes.check_pr_body(BODY, self.classes, fixed)))
        self.assertEqual([1], asked)

    def test_the_fixed_rules_are_the_baseline_and_the_rule_lines_merged_since(self):
        baseline = {10: row(10, "2026-10-30", "P.own", "premiere"), 12: row(12, "2026-11-03", "aucune", "-")}
        prs = [{"number": 10, "body": "Règle : P.load\n"}, {"number": 20, "body": "Règle : P.load — prévue (af-x)\n"},
               {"number": 21, "body": "Règle : P.nope\n"}, {"number": 22, "body": "Catégorie : aucune — doc\n"}]

        self.assertEqual({"P.own", "P.load"}, defect_classes.fixed_rules(baseline, prs, KNOWN))

    def test_markdown_emphasis_is_read(self):
        body = BODY.replace("Catégorie : P", "**Catégorie :** `P`").replace("Où ailleurs :", "- **Où ailleurs :**")

        self.assertEqual([], self.check(body))

    def test_the_command_line_names_what_is_missing(self):
        proc = subprocess.run([sys.executable, str(TOOL), "check-pr-body"], input="Catégorie : P\n", text=True,
                              capture_output=True)

        self.assertEqual(1, proc.returncode)
        self.assertIn("Où ailleurs :", proc.stdout)
        planned = BODY.replace("Règle : P.own", "Règle : P.own — prévue (af-x)")
        ok = subprocess.run([sys.executable, str(TOOL), "check-pr-body", "--branch", "fix/x"], input=planned,
                            text=True, capture_output=True)
        self.assertEqual((0, ""), (ok.returncode, ok.stdout.strip()))

    def test_the_command_line_reads_the_fixed_rules_from_the_baseline_and_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            # Every named rule of the register has a fix in the baseline: two new ones.
            registry = Path(tmp) / "r.md"
            registry.write_text((ROOT / "docs" / "DEFECT_CLASSES.md").read_text(encoding="utf-8").replace(
                "- Règles :\n", "- Règles :\n  - `P.fresh` : Une. Passage : aucun.\n"
                "  - `P.fresher` : Deux. Passage : aucun.\n", 1), encoding="utf-8")
            merged = [{"number": 9999, "body": "Règle : P.fresh\n", "mergedAt": "2026-12-01T10:00:00Z"}]
            gh.write_text("#!/bin/sh\necho \"$*\" > \"$(dirname \"$0\")/args\"\n"
                          f"cat <<'JSON'\n{json.dumps(merged)}\nJSON\n")
            gh.chmod(0o755)
            env = {**os.environ, "GH_BIN": str(gh)}
            # P.own: in the baseline; P.fresh: merged since; P.fresher: neither.
            for rule, code in [("P.own", 1), ("P.fresh", 1), ("P.fresher", 0)]:
                with self.subTest(rule=rule):
                    proc = subprocess.run([sys.executable, str(TOOL), "--registry", str(registry), "check-pr-body",
                                           "--github-repo", "o/r"],
                                          input=BODY.replace("P.own", rule), text=True, capture_output=True,
                                          env=env, cwd=tmp)
                    self.assertEqual(code, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("-R o/r", (Path(tmp) / "args").read_text())
            gh.write_text("#!/bin/sh\nexit 1\n")
            proc = subprocess.run([sys.executable, str(TOOL), "check-pr-body"], input=BODY, text=True,
                                  capture_output=True, env=env, cwd=tmp)
            self.assertEqual(2, proc.returncode, "a list of fixed rules that cannot be read is never « not fixed »")

    def test_the_maintenance_lines_are_written_out_in_one_place(self):
        # af-56yoam.2: five copies of the form had drifted from docs/DELIVERY.md
        # (three lines here, four there); the others point to it.
        template = re.compile(r"^\W*(Où ailleurs|Contrôle de catégorie) : <", re.M)
        found = []
        for top in ("bin", "lib", "formulas", "agents", "orders", "docs", "config"):
            for path in (ROOT / top).rglob("*"):
                rel = path.relative_to(ROOT).as_posix()
                if not path.is_file() or rel == "docs/DELIVERY.md" or rel.startswith("docs/research/"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                if template.search(text):
                    found.append(rel)
        self.assertTrue(template.search((ROOT / "docs" / "DELIVERY.md").read_text(encoding="utf-8")))
        self.assertEqual([], found, "point to docs/DELIVERY.md, « Where else? », instead of copying its lines")

    def test_a_branch_that_is_not_a_maintenance_branch_passes_unread(self):
        listed = subprocess.run([sys.executable, str(TOOL), "maintenance-branches"], text=True, capture_output=True)
        self.assertEqual(["fix/", "do-work/"], listed.stdout.split())
        for branch, code in [("feat/cockpit", 0), ("maint/af-x", 0), ("do-work/af-x", 1), ("fix/x", 1)]:
            with self.subTest(branch=branch):
                proc = subprocess.run([sys.executable, str(TOOL), "check-pr-body", "--branch", branch],
                                      input="rien\n", text=True, capture_output=True)
                self.assertEqual(code, proc.returncode, proc.stdout + proc.stderr)


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
        self.assertEqual("prevue", baseline[738]["nature"])
        decision = defect_classes.d1(defect_classes.by_rule([], baseline, known)["fixes"], known)
        self.assertEqual("2026-12-21", decision["review"])
        # The reference D1 was frozen on (comment of 23/11/2026 19:50 on af-56yoam).
        self.assertEqual((86, 140), (decision["reference_share"]["slips"], decision["reference_share"]["fixes"]))
        # No rule carries proof in the register that its passage point was delivered.
        self.assertEqual(({}, []), (decision["closed_rules"], decision["closed_slips"]))

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
            self.assertEqual({"start": "2026-12-01", "end": "2026-12-20", "slips": 1, "fixes": 1, "share": 1.0},
                             out["d1"]["period_share"])
            self.assertEqual([], out["unclassified"])


class D1Test(unittest.TestCase):
    """af-56yoam.5: D1 as frozen on 23/11/2026, the share of slips among the
    fix pull requests of a period, and zero slip on a closed rule."""

    def test_the_share_of_slips_among_the_fixes_of_a_period(self):
        fixes = [{"pr": 1, "date": "2026-11-30", "rule": "P.own", "nature": "glissement"},
                 {"pr": 2, "date": "2026-12-01", "rule": "P.own", "nature": "glissement"},
                 {"pr": 3, "date": "2026-12-10", "rule": "P.load", "nature": "premiere"},
                 {"pr": 4, "date": "2026-12-20", "rule": "P.load", "nature": "prevue"},
                 {"pr": 5, "date": "2026-12-21", "rule": "P.own", "nature": "glissement"}]
        cases = [
            # (start, end, slips, fixes, share): both days included; no fix, no share.
            ("2026-12-01", "2026-12-20", 1, 3, 0.333),
            ("2026-11-30", "2026-12-01", 2, 2, 1.0),
            ("2026-12-02", "2026-12-09", 0, 0, None),
            ("2026-12-01", "2026-11-24", 0, 0, None),
        ]
        for start, end, slips, count, share in cases:
            with self.subTest(start=start, end=end):
                self.assertEqual({"start": start, "end": end, "slips": slips, "fixes": count, "share": share},
                                 defect_classes.slip_share(fixes, start, end))

    def test_a_slip_on_a_closed_rule_counts_only_after_the_day_it_was_closed(self):
        known = {"P.own": {"closed": {"date": "2026-12-05", "pr": 950}}, "P.load": {}}
        cases = [
            # (fix, counted as a slip on a closed rule)
            ({"pr": 960, "date": "2026-12-06", "rule": "P.own", "nature": "glissement"}, True),
            ({"pr": 950, "date": "2026-12-05", "rule": "P.own", "nature": "glissement"}, False),
            ({"pr": 940, "date": "2026-12-01", "rule": "P.own", "nature": "glissement"}, False),
            ({"pr": 961, "date": "2026-12-07", "rule": "P.own", "nature": "prevue"}, False),
            ({"pr": 962, "date": "2026-12-07", "rule": "P.load", "nature": "glissement"}, False),
        ]
        for fix, counted in cases:
            with self.subTest(fix=fix):
                expected = [{"rule": "P.own", "pr": fix["pr"], "date": fix["date"],
                             "closed": {"date": "2026-12-05", "pr": 950}}] if counted else []
                self.assertEqual(expected, defect_classes.closed_slips([fix], known))
        decision = defect_classes.d1([], known, until="2026-11-24")
        self.assertEqual({"P.own": {"date": "2026-12-05", "pr": 950}}, decision["closed_rules"])
        self.assertEqual(("2026-12-01", "2026-11-24", None), (decision["period_share"]["start"],
                         decision["period_share"]["end"], decision["period_share"]["share"]))

    def test_the_closed_mark_of_a_rule_is_read_from_the_register(self):
        head = "## P — x\n\n- Invariant : y\n- Règles :\n"
        tail = "- Contrôle : aucun — z\n- Occurrences : #1\n- Ouvertes : aucune connue.\n"
        cases = [
            # (rule line, (passage, closed) or the refusal)
            ("  - `P.own` : A. Passage : `lib/b.py`. Fermée le 05/12/2026 par #950.\n",
             ("`lib/b.py`", {"date": "2026-12-05", "pr": 950})),
            ("  - `P.own` : A. Passage : `lib/b.py`.\n    Fermée le 05/12/2026 par #950.\n",
             ("`lib/b.py`", {"date": "2026-12-05", "pr": 950})),
            ("  - `P.own` : A. Passage : `lib/b.py`.\n", ("`lib/b.py`", None)),
            ("  - `P.own` : A. Passage : `lib/b.py`. Fermée le 5 décembre.\n", "JJ/MM/AAAA"),
            ("  - `P.own` : A. Passage : aucun. Fermée le 05/12/2026 par #950.\n", "sans point de passage"),
        ]
        for line, expected in cases:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                registry = Path(tmp) / "r.md"
                registry.write_text(head + line + tail, encoding="utf-8")
                if isinstance(expected, str):
                    with self.assertRaisesRegex(defect_classes.RegistryError, expected):
                        defect_classes.load(registry)
                    continue
                rule = defect_classes.load(registry)["P"]["rules"]["P.own"]
                self.assertEqual(expected, (rule["passage"], rule.get("closed")))


if __name__ == "__main__":
    unittest.main()
