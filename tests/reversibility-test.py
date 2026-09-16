#!/usr/bin/env python3
"""Reversibility classification (af-l463, ADR-0019).

The SQL fixtures are the backend's own migrations V2, V4, V6, V7, V8 and V9,
verbatim in substance: five of its eleven migrations would have deserved a
declaration, and nothing noticed at the time.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import reversibility as rv  # noqa: E402

MIG = "webapp/src/main/resources/db/migration"
RB = "webapp/src/main/resources/db/rollback"

V2 = "ALTER TABLE workspaces\n    ADD CONSTRAINT uq_workspaces_tenant_id\n    UNIQUE (tenant_id, id);"
V4 = "ALTER TABLE tenants\n    DROP COLUMN migration_test_note;\n"
V6 = """-- GENDER enum options previously used code == label.
DELETE eo FROM attribute_enum_options eo
JOIN attributes a ON a.id = eo.attribute_id
WHERE a.code = 'GENDER';
INSERT INTO attribute_enum_options (code) SELECT 'MALE';
"""
V7 = "-- backfill derived columns\nUPDATE attributes\nSET filter = (type <> 'TEXT'),\n    sort = (type <> 'TEXT');\n"
V8 = "ALTER TABLE attributes\n    CHANGE COLUMN required expected TINYINT(1) NOT NULL;\n"
V9 = """-- These overrides have no backend readers or writers.
ALTER TABLE workspace_attributes
    DROP COLUMN expected_override,
    DROP COLUMN filter_override,
    DROP COLUMN sort_override;
"""


def added(path, text):
    body = "\n".join("+" + line for line in text.splitlines())
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..1111111\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(text.splitlines())} @@\n{body}\n")


def modified(path, line):
    return (f"diff --git a/{path} b/{path}\nindex 1111111..2222222 100644\n"
            f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+{line}\n")


def deleted(path):
    return (f"diff --git a/{path} b/{path}\ndeleted file mode 100644\nindex 1111111..0000000\n"
            f"--- a/{path}\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n")


class Statements(unittest.TestCase):
    def test_the_backends_own_history(self):
        cases = {
            "V2 add unique key": (V2, []),
            "V4 drop column": (V4, ["schema_loss"]),
            "V6 delete rows": (V6, ["data_loss"]),
            "V7 rewrite a column": (V7, ["data_rewrite"]),
            "V8 rename (MySQL CHANGE COLUMN)": (V8, ["rename"]),
            "V9 three drops in one ALTER": (V9, ["schema_loss"]),
        }
        for name, (sql, expected) in cases.items():
            with self.subTest(name):
                got = sorted({c for s in rv.statements(sql) for c in rv.classify_statement(s)})
                self.assertEqual(expected, got)

    def test_recreatable_schema_objects_are_not_loss(self):
        for sql in ("ALTER TABLE t DROP INDEX idx_a", "ALTER TABLE t DROP FOREIGN KEY fk_a",
                    "ALTER TABLE t DROP CONSTRAINT uq_a", "ALTER TABLE t DROP PRIMARY KEY",
                    "ALTER TABLE t ALTER COLUMN c DROP DEFAULT", "CREATE TABLE x (id INT)",
                    "ALTER TABLE t ADD COLUMN c INT NULL", "INSERT INTO t VALUES (1)",
                    "CREATE INDEX i ON t(c)"):
            with self.subTest(sql):
                self.assertEqual([], rv.classify_statement(sql))

    def test_other_loss_and_rewrite_shapes(self):
        cases = {
            "ALTER TABLE t DROP legacy_col": ["schema_loss"],       # MySQL: COLUMN is optional
            "DROP TABLE IF EXISTS t": ["schema_loss"],
            "TRUNCATE TABLE t": ["schema_loss"],
            "RENAME TABLE a TO b": ["rename"],
            "ALTER TABLE t RENAME COLUMN a TO b": ["rename"],
            "ALTER TABLE t MODIFY COLUMN c VARCHAR(10)": ["data_rewrite"],
            "ALTER TABLE t ALTER COLUMN c TYPE bigint": ["data_rewrite"],
            "ALTER TABLE t ADD COLUMN x INT, DROP COLUMN y": ["schema_loss"],
        }
        for sql, expected in cases.items():
            with self.subTest(sql):
                self.assertEqual(expected, rv.classify_statement(sql))

    def test_comments_are_not_statements(self):
        sql = "-- DROP TABLE people;\n/* TRUNCATE people; */\nCREATE TABLE ok (id INT);"
        self.assertEqual([], sorted({c for s in rv.statements(sql) for c in rv.classify_statement(s)}))


class Assessment(unittest.TestCase):
    def verdict(self, diff):
        return rv.assess(diff)

    def test_additive_changes_flow_as_before(self):
        result = self.verdict(added(f"{MIG}/V12__add_unique_key.sql", V2)
                              + added("webapp/src/main/java/App.java", "class App {}"))
        self.assertEqual(("ok", 1), (result["verdict"], result["migrations"]))
        self.assertEqual(0, rv.EXIT[result["verdict"]])

    def test_a_pr_without_migrations_is_not_even_counted(self):
        self.assertEqual(("ok", 0), tuple(self.verdict(added("src/App.tsx", "x"))[k] for k in ("verdict", "migrations")))

    def test_undeclared_loss_needs_a_rollback_or_an_escalation(self):
        result = self.verdict(added(f"{MIG}/V12__drop_note.sql", V4))
        self.assertEqual("needs_declaration", result["verdict"])
        self.assertIn("-- rollback:", result["findings"][0]["detail"])
        self.assertNotIn("reversible: <why>`,", result["findings"][0]["detail"])  # not enough for a loss

    def test_a_reversible_claim_is_not_enough_for_loss(self):
        sql = "-- reversible: trust me\n" + V9
        self.assertEqual("needs_declaration", self.verdict(added(f"{MIG}/V12__drop.sql", sql))["verdict"])

    def test_a_reversible_claim_is_enough_for_a_rewrite_or_rename(self):
        for sql in (V7, V8):
            with self.subTest(sql=sql[:30]):
                declared = "-- reversible: backfill of a derived column, recomputed on every write\n" + sql
                self.assertEqual("ok", self.verdict(added(f"{MIG}/V12__x.sql", declared))["verdict"])

    def test_a_rollback_must_ship_in_the_same_change(self):
        sql = "-- rollback: R12__restore_note.sql\n" + V4
        missing = self.verdict(added(f"{MIG}/V12__drop_note.sql", sql))
        self.assertEqual("needs_declaration", missing["verdict"])
        self.assertIn("no such file", missing["findings"][0]["detail"])
        shipped = self.verdict(added(f"{MIG}/V12__drop_note.sql", sql)
                               + added(f"{RB}/R12__restore_note.sql", "ALTER TABLE tenants ADD COLUMN migration_test_note TEXT;"))
        self.assertEqual("ok", shipped["verdict"])
        # The rollback script itself is not a migration and is never classified.
        self.assertEqual(1, shipped["migrations"])

    def test_declared_irreversible_is_an_escalation(self):
        sql = "-- irreversible: GDPR erasure of the legacy table, no copy may remain\n" + V9
        result = self.verdict(added(f"{MIG}/V12__erase.sql", sql))
        self.assertEqual(("irreversible", 4), (result["verdict"], rv.EXIT[result["verdict"]]))
        self.assertIn("GDPR", result["findings"][0]["detail"])

    def test_applied_history_is_never_rewritten(self):
        for diff in (modified(f"{MIG}/V4__drop_tenants_migration_test_note.sql", "-- tweak"),
                     deleted(f"{MIG}/V4__drop_tenants_migration_test_note.sql")):
            with self.subTest(diff=diff[:60]):
                result = self.verdict(diff)
                self.assertEqual("history_rewrite", result["verdict"])
                self.assertEqual(3, rv.EXIT[result["verdict"]])

    def test_the_worst_file_decides(self):
        diff = (added(f"{MIG}/V12__a.sql", V2) + added(f"{MIG}/V13__b.sql", V4)
                + added(f"{MIG}/V14__c.sql", "-- irreversible: purge\n" + V9))
        self.assertEqual("irreversible", self.verdict(diff)["verdict"])

    def test_the_pr_comment_says_what_to_do_in_french(self):
        result = self.verdict(added(f"{MIG}/V12__drop_note.sql", V4))
        comment = rv.render_comment(result)
        self.assertIn("déclaration requise", comment)
        self.assertIn("V12__drop_note.sql", comment)
        self.assertIn("docs/DELIVERY.md", comment)


class Cli(unittest.TestCase):
    def run_cli(self, diff, *flags):
        with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False, encoding="utf-8") as handle:
            handle.write(diff)
        return subprocess.run([sys.executable, str(ROOT / "bin" / "reversibility-check"),
                               "--diff-file", handle.name, *flags],
                              text=True, capture_output=True)

    def test_exit_codes_and_outputs(self):
        ok = self.run_cli(added(f"{MIG}/V12__a.sql", V2))
        self.assertEqual(0, ok.returncode)
        self.assertIn("reversibility: ok", ok.stdout)
        held = self.run_cli(added(f"{MIG}/V12__b.sql", V4), "--json")
        self.assertEqual(3, held.returncode)
        self.assertEqual("needs_declaration", json.loads(held.stdout)["verdict"])
        irr = self.run_cli(added(f"{MIG}/V12__c.sql", "-- irreversible: purge\n" + V9), "--comment")
        self.assertEqual(4, irr.returncode)
        self.assertIn("décision humaine requise", irr.stdout)

    def test_a_missing_input_is_an_error_not_a_pass(self):
        result = subprocess.run([sys.executable, str(ROOT / "bin" / "reversibility-check")],
                                text=True, capture_output=True)
        self.assertEqual(2, result.returncode)

    def test_git_mode_on_a_real_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            git = lambda *a: subprocess.run(["git", "-C", tmp, *a], check=True, capture_output=True)
            git("init", "-q", "-b", "dev")
            git("config", "user.email", "t@t"); git("config", "user.name", "t")
            git("config", "commit.gpgsign", "false")
            path = Path(tmp) / MIG
            path.mkdir(parents=True)
            (path / "V1__init.sql").write_text("CREATE TABLE t (id INT);\n", encoding="utf-8")
            git("add", "-A"); git("commit", "-qm", "init")
            git("checkout", "-qb", "feature")
            (path / "V2__drop.sql").write_text(V4, encoding="utf-8")
            git("add", "-A"); git("commit", "-qm", "drop")
            result = subprocess.run([sys.executable, str(ROOT / "bin" / "reversibility-check"),
                                     "--git", tmp, "--base", "dev", "--head", "feature"],
                                    text=True, capture_output=True)
            self.assertEqual(3, result.returncode, result.stdout + result.stderr)
            self.assertIn("V2__drop.sql", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
