#!/usr/bin/env python3
"""lib/integration_maintenance.py: the one rule of a maintenance PR into a
convoy's integration branch (af-41i8d0, decision af-wpzic4,
docs/DELIVERY.md). Its consumers (bin/factory-do-work-workspace,
bin/pr-autopilot, bin/deliver-close, bin/factory-delivery-guard) prove only
the transmission; every pass and refusal of the rule is proven here, through
the tool's entry function, with one pass and one refusal as a real process.
"""
import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "lib" / "integration_maintenance.py"
spec = importlib.util.spec_from_file_location("integration_maintenance", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

INTEGRATION = "integration/af-spec"


def bead(labels=("maintenance",), authorized_by="af-wpzic4", base=INTEGRATION, **extra):
    metadata = {"gc.authorized_by": authorized_by, "gc.work_base_branch": base, **extra}
    return {"id": "af-fix", "status": "closed", "labels": list(labels), "metadata": metadata}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                           "-c", "commit.gpgsign=false", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class IntegrationMaintenanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.projects = tmp / "projects"
        cls.projects.mkdir()
        (cls.projects / "factory.toml").write_text(
            'rig_dir = "."\nrepo = "example/factory"\nprotected_branch = "main"\nrequired_ci = "CI"\n')
        # main: two test files and a tool; the convoy changes tests/convoy.py
        # only. Each repair branch changes one file on the integration branch.
        cls.repo = repo = tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        for path in ("tests/convoy.py", "tests/shared.py", "bin/tool", "lib/synthetic_city.py"):
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_text("main\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "main")
        git(repo, "checkout", "-qb", INTEGRATION)
        for path in ("tests/convoy.py", "lib/synthetic_city.py"):
            (repo / path).write_text("convoy\n")
        git(repo, "commit", "-qam", "convoy")
        for name, path in (("ok", "tests/convoy.py"), ("harness", "lib/synthetic_city.py"),
                           ("tool", "bin/tool"), ("shared", "tests/shared.py")):
            git(repo, "checkout", "-qb", f"repair-{name}", INTEGRATION)
            (repo / path).write_text("repaired\n")
            git(repo, "commit", "-qam", name)
        git(repo, "checkout", "-q", "main")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def call(self, argv, stdin=""):
        out, real_stdin = io.StringIO(), sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = tool.main(argv)
        finally:
            sys.stdin = real_stdin
        return code, out.getvalue()

    def target(self, value, target, repo="example/factory"):
        return self.call(["target", "--target", target, "--repo", repo, "--projects", str(self.projects)],
                         json.dumps([value]))

    def files(self, branch):
        return self.call(["files", "--git", str(self.repo), "--protected", "main",
                          "--base", INTEGRATION, "--head", branch])

    # --- target ---

    def test_the_protected_branch_is_always_a_target(self):
        self.assertEqual((0, ""), self.target(bead(labels=()), "main"))

    def test_an_authorized_maintenance_bead_may_land_on_its_integration_branch(self):
        self.assertEqual((0, ""), self.target(bead(authorized_by="af-wpzic4 + af-3l6hbt answer b"), INTEGRATION))

    def test_an_integration_target_needs_the_maintenance_label(self):
        code, out = self.target(bead(labels=()), INTEGRATION)
        self.assertEqual(1, code)
        self.assertIn("label maintenance", out)

    def test_an_integration_target_needs_the_decision_named(self):
        for authority in ("af-lxk1nm operator_request", "af-wpzic4x", ""):
            code, out = self.target(bead(authorized_by=authority), INTEGRATION)
            self.assertEqual(1, code, authority)
            self.assertIn("ne nomme pas la décision af-wpzic4", out)

    def test_an_integration_target_must_be_the_beads_own_base(self):
        code, out = self.target(bead(base="main"), INTEGRATION)
        self.assertEqual(1, code)
        self.assertIn(f"gc.work_base_branch=main n'est pas {INTEGRATION}", out)

    def test_any_other_target_of_a_registered_repo_is_refused(self):
        code, out = self.target(bead(), "release")
        self.assertEqual(1, code)
        self.assertIn("ni la branche protégée main", out)

    def test_a_repo_not_registered_keeps_any_non_integration_target(self):
        self.assertEqual((0, ""), self.target(bead(labels=()), "dev", repo="other/repo"))

    # --- files ---

    def test_test_or_harness_code_the_convoy_changed_may_be_repaired_there(self):
        for branch, path in (("repair-ok", "tests/convoy.py"), ("repair-harness", "lib/synthetic_city.py")):
            code, out = self.files(branch)
            self.assertEqual(0, code, out)
            self.assertIn(f"Cible : {INTEGRATION} — code de test changé par le convoi ({path}", out)

    def test_code_outside_test_and_harness_is_refused(self):
        code, out = self.files("repair-tool")
        self.assertEqual(1, code)
        self.assertIn("bin/tool : hors code de test/harnais", out)

    def test_a_test_file_the_convoy_did_not_change_is_refused(self):
        code, out = self.files("repair-shared")
        self.assertEqual(1, code)
        self.assertIn("tests/shared.py : le convoi ne l'a pas modifié", out)

    def test_a_branch_with_no_change_is_refused(self):
        self.assertEqual((1, "aucun fichier changé\n"), self.files(INTEGRATION))

    # --- scan ---

    def test_scan_names_each_closed_delivery_on_a_refused_target(self):
        beads = [bead(merged_target=INTEGRATION, **{"gc.github_repo": "example/factory"}) | {"id": "af-ok"},
                 bead(labels=(), merged_target=INTEGRATION) | {"id": "af-bad"},
                 bead(merged_target="main", **{"gc.github_repo": "example/factory"}) | {"id": "af-main"},
                 bead(labels=(), merged_target=INTEGRATION) | {"id": "af-open", "status": "in_progress"}]
        code, out = self.call(["scan", "--projects", str(self.projects)], json.dumps(beads))
        self.assertEqual(0, code)
        self.assertEqual(["af-bad", INTEGRATION], out.strip().split("\x1f")[:2])
        self.assertEqual(1, len(out.strip().splitlines()))

    # --- the command line is wired to the entry function ---

    def test_a_process_passes_and_a_process_refuses(self):
        passed = subprocess.run([sys.executable, str(TOOL), "target", "--target", INTEGRATION],
                                input=json.dumps(bead()), capture_output=True, text=True)
        self.assertEqual(0, passed.returncode, passed.stdout + passed.stderr)
        refused = subprocess.run([sys.executable, str(TOOL), "files", "--git", str(self.repo), "--protected", "main",
                                  "--base", INTEGRATION, "--head", "repair-tool"], capture_output=True, text=True)
        self.assertEqual(1, refused.returncode)
        self.assertIn("bin/tool", refused.stdout)


if __name__ == "__main__":
    unittest.main()
