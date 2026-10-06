#!/usr/bin/env python3
"""Regression tests for per-rig formula check wiring (af-uxz57)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "bin" / "factory-build-gates"
CHECK_PATH = ".gc/scripts/checks/build-artifact-valid.sh"
VALIDATOR_PATH = ".gc/scripts/validate_build_artifact.py"


class BuildGateWiring(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.city = self.base / "city"
        self.city.mkdir()
        (self.city / "city.toml").write_text(
            textwrap.dedent(
                """\
                [[rigs]]
                name = "backend"

                [[rigs]]
                name = "frontend"
                """
            ),
            encoding="utf-8",
        )
        for name in ("backend", "frontend"):
            (self.city / "rigs" / name / ".gc").mkdir(parents=True)

        self.manifest = self.base / "formulas.json"
        self.formula_list_map = self.base / "formula-list-map.json"
        self.gc = self.base / "gc"
        self.gc.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "mapping_file = os.environ.get('FORMULA_LIST_MAP')\n"
            "if mapping_file:\n"
            "    mapping = json.loads(pathlib.Path(mapping_file).read_text())\n"
            "    rig = sys.argv[sys.argv.index('--rig') + 1]\n"
            "    manifest = mapping[rig]\n"
            "else:\n"
            "    manifest = os.environ['FORMULA_LIST_FILE']\n"
            "print(pathlib.Path(manifest).read_text())\n",
            encoding="utf-8",
        )
        self.gc.chmod(0o755)

    def _pack(self, version: str, gate_body: str = "echo valid") -> tuple[Path, Path]:
        gascity = self.base / version / "gascity"
        formulas = gascity / "formulas"
        checks = gascity / "assets" / "scripts" / "checks"
        formulas.mkdir(parents=True)
        checks.mkdir(parents=True)
        formula = formulas / "build-base.formula.toml"
        formula.write_text(
            textwrap.dedent(
                f"""\
                formula = "build-base"
                version = 1

                [[steps]]
                id = "one"
                [steps.check.check]
                mode = "exec"
                path = "{CHECK_PATH}"

                [[steps]]
                id = "two"
                [steps.check.check]
                mode = "exec"
                path = "{CHECK_PATH}"
                """
            ),
            encoding="utf-8",
        )
        gate = checks / "build-artifact-valid.sh"
        gate.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{gate_body}\n", encoding="utf-8")
        gate.chmod(gate.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        validator = gascity / "assets" / "scripts" / "validate_build_artifact.py"
        validator.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        validator.chmod(validator.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return formula, gate

    def _select(self, *formulas: Path) -> None:
        payload = {
            "ok": True,
            "formulas": [
                {"name": f"formula-{index}", "source": str(path)}
                for index, path in enumerate(formulas)
            ],
        }
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(
            os.environ,
            FACTORY_ROOT=str(self.city),
            GC_BIN=str(self.gc),
            FORMULA_LIST_FILE=str(self.manifest),
        )
        return subprocess.run(
            [sys.executable, str(COMMAND), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def _run_with_formula_map(
        self, mapping: dict[str, Path], *args: str
    ) -> subprocess.CompletedProcess[str]:
        self.formula_list_map.write_text(
            json.dumps({rig: str(path) for rig, path in mapping.items()}),
            encoding="utf-8",
        )
        env = dict(
            os.environ,
            FACTORY_ROOT=str(self.city),
            GC_BIN=str(self.gc),
            FORMULA_LIST_FILE=str(self.manifest),
            FORMULA_LIST_MAP=str(self.formula_list_map),
        )
        return subprocess.run(
            [sys.executable, str(COMMAND), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def _target(self, rig: str) -> Path:
        return self.city / "rigs" / rig / CHECK_PATH

    def test_check_only_names_each_missing_rig_path_once(self):
        formula, _gate = self._pack("pack-v1")
        self._select(formula)

        result = self._run("--check-only")

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(1, result.stdout.count(f"rig 'backend' missing {CHECK_PATH}"))
        self.assertEqual(1, result.stdout.count(f"rig 'frontend' missing {CHECK_PATH}"))
        self.assertFalse(self._target("backend").exists(), "check-only must not write")

    def test_repair_materialises_both_rigs_and_the_gate_really_executes(self):
        formula, gate = self._pack("pack-v1", "echo validator-v1")
        self._select(formula)

        repaired = self._run()

        self.assertEqual(0, repaired.returncode, repaired.stdout + repaired.stderr)
        self.assertEqual(4, repaired.stdout.count("FIXED:"), repaired.stdout)
        for rig in ("backend", "frontend"):
            target = self._target(rig)
            self.assertTrue(target.is_file())
            self.assertFalse(target.is_symlink())
            self.assertEqual(gate.read_bytes(), target.read_bytes())
            validator = self.city / "rigs" / rig / VALIDATOR_PATH
            self.assertTrue(validator.is_file())
            self.assertTrue(validator.is_symlink())
            self.assertTrue((self.city / "rigs" / rig / ".gc/scripts/.factory-build-gates.json").is_file())
            executed = subprocess.run(
                [str(target)], check=False, capture_output=True, text=True, cwd=target.parents[3]
            )
            self.assertEqual(0, executed.returncode, executed.stderr)
            self.assertEqual("validator-v1", executed.stdout.strip())

        clean = self._run("--check-only")
        self.assertEqual(0, clean.returncode, clean.stdout + clean.stderr)
        self.assertIn("2 managed gate path(s)", clean.stdout)

    def test_materialised_gate_dependency_runs_from_the_real_pack_path(self):
        formula, gate = self._pack("pack-v1")
        validator = gate.parent.parent / "validate_build_artifact.py"
        validator.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "print(Path(__file__).resolve())\n",
            encoding="utf-8",
        )
        validator.chmod(0o755)
        gate.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
            'python3 "$SCRIPT_DIR/../validate_build_artifact.py"\n',
            encoding="utf-8",
        )
        gate.chmod(0o755)
        self._select(formula)
        self.assertEqual(0, self._run().returncode)

        target = self._target("backend")
        executed = subprocess.run(
            [str(target)], check=False, capture_output=True, text=True, cwd=target.parents[3]
        )

        self.assertEqual(0, executed.returncode, executed.stderr)
        self.assertEqual(str(validator.resolve()), executed.stdout.strip())

    def test_repair_refreshes_copies_when_the_resolved_pack_changes(self):
        formula_v1, _gate_v1 = self._pack("pack-v1", "echo validator-v1")
        formula_v2, gate_v2 = self._pack("pack-v2", "echo validator-v2")
        self._select(formula_v1)
        self.assertEqual(0, self._run().returncode)

        self._select(formula_v2)
        stale = self._run("--check-only")
        self.assertEqual(1, stale.returncode)
        self.assertIn(f"stale {CHECK_PATH}", stale.stdout)

        refreshed = self._run()
        self.assertEqual(0, refreshed.returncode, refreshed.stdout + refreshed.stderr)
        for rig in ("backend", "frontend"):
            self.assertEqual(gate_v2.read_bytes(), self._target(rig).read_bytes())
            validator = self.city / "rigs" / rig / VALIDATOR_PATH
            self.assertEqual(
                (gate_v2.parent.parent / "validate_build_artifact.py").resolve(),
                validator.resolve(),
            )

    def test_repair_rematerialises_after_a_rig_reclone(self):
        formula, gate = self._pack("pack-v1", "echo validator-v1")
        self._select(formula)
        self.assertEqual(0, self._run().returncode)
        backend_gc = self.city / "rigs" / "backend" / ".gc"
        shutil.rmtree(backend_gc)
        backend_gc.mkdir()

        repaired = self._run()

        self.assertEqual(0, repaired.returncode, repaired.stdout + repaired.stderr)
        self.assertEqual(gate.read_bytes(), self._target("backend").read_bytes())
        self.assertTrue((backend_gc / "scripts/.factory-build-gates.json").is_file())

    def test_each_rig_uses_its_own_resolved_formula_layer(self):
        backend_formula, backend_gate = self._pack("pack-backend", "echo backend")
        frontend_formula, frontend_gate = self._pack("pack-frontend", "echo frontend")
        backend_manifest = self.base / "backend-formulas.json"
        frontend_manifest = self.base / "frontend-formulas.json"
        for manifest, formula in (
            (backend_manifest, backend_formula),
            (frontend_manifest, frontend_formula),
        ):
            manifest.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "formulas": [{"name": "build-base", "source": str(formula)}],
                    }
                ),
                encoding="utf-8",
            )

        result = self._run_with_formula_map(
            {"backend": backend_manifest, "frontend": frontend_manifest}
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(backend_gate.read_bytes(), self._target("backend").read_bytes())
        self.assertEqual(frontend_gate.read_bytes(), self._target("frontend").read_bytes())

    def test_conflicting_active_pack_sources_fail_loudly(self):
        formula_v1, _gate_v1 = self._pack("pack-v1", "echo one")
        formula_v2, _gate_v2 = self._pack("pack-v2", "echo two")
        self._select(formula_v1, formula_v2)

        result = self._run()

        self.assertEqual(1, result.returncode)
        self.assertIn("resolved conflicting pack sources", result.stdout)
        self.assertFalse(self._target("backend").exists())

    def test_repair_replaces_pack_symlinks_rejected_by_containment(self):
        formula, gate = self._pack("pack-v1")
        self._select(formula)
        for rig in ("backend", "frontend"):
            target = self._target(rig)
            target.parent.mkdir(parents=True)
            target.symlink_to(gate)

        rejected = self._run("--check-only")
        self.assertEqual(1, rejected.returncode)
        self.assertIn("symlinked .gc/scripts/checks/build-artifact-valid.sh", rejected.stdout)
        self.assertIn("outside rig containment", rejected.stdout)

        repaired = self._run()
        self.assertEqual(0, repaired.returncode, repaired.stdout + repaired.stderr)
        for rig in ("backend", "frontend"):
            target = self._target(rig)
            self.assertTrue(target.is_file())
            self.assertFalse(target.is_symlink())
            self.assertEqual(gate.read_bytes(), target.read_bytes())

    def test_repair_never_overwrites_a_modified_managed_copy(self):
        formula, _gate = self._pack("pack-v1")
        self._select(formula)
        self.assertEqual(0, self._run().returncode)
        target = self._target("backend")
        target.write_text("#!/usr/bin/env bash\necho rig-owned edit\n", encoding="utf-8")

        result = self._run()

        self.assertEqual(1, result.returncode)
        self.assertIn("managed copy was modified outside factory-build-gates", result.stdout)
        self.assertIn("rig-owned edit", target.read_text(encoding="utf-8"))

    def test_missing_rig_root_is_reported_without_creating_it(self):
        formula, _gate = self._pack("pack-v1")
        self._select(formula)
        missing = self.city / "rigs" / "frontend"
        (missing / ".gc").rmdir()
        missing.rmdir()

        result = self._run()

        self.assertEqual(1, result.returncode)
        self.assertIn("rig 'frontend' root is missing", result.stdout)
        self.assertFalse(missing.exists())

    def test_missing_pack_asset_is_loud_and_never_stubbed(self):
        formula, gate = self._pack("pack-v1")
        gate.unlink()
        self._select(formula)

        result = self._run()

        self.assertEqual(1, result.returncode)
        self.assertIn(f"cannot resolve pack source for {CHECK_PATH}", result.stdout)
        self.assertFalse(self._target("backend").exists())

    # The city root's own store (T12, af-i3q5a5): a check the city owns,
    # beside its formulas, is materialised in the city root too.

    def _city_check(self, body: str = "echo city-check") -> tuple[Path, Path, str]:
        check_path = ".gc/scripts/checks/own-check.sh"
        formulas = self.city / "formulas"
        checks = self.city / "assets" / "scripts" / "checks"
        formulas.mkdir(parents=True, exist_ok=True)
        checks.mkdir(parents=True, exist_ok=True)
        formula = formulas / "own.formula.toml"
        formula.write_text(
            f'formula = "own"\nversion = 1\n\n[[steps]]\nid = "one"\n'
            f'[steps.check.check]\nmode = "exec"\npath = "{check_path}"\n',
            encoding="utf-8",
        )
        source = checks / "own-check.sh"
        source.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
        source.chmod(0o755)
        return formula, source, check_path

    def test_check_only_names_a_city_owned_check_missing_in_the_city_root(self):
        formula, _source, check_path = self._city_check()
        self._select(formula)

        result = self._run("--check-only")

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(1, result.stdout.count(f"rig '(city root)' missing {check_path}"), result.stdout)
        self.assertFalse((self.city / check_path).exists(), "check-only must not write")

    def test_repair_materialises_a_city_owned_check_in_the_city_root_and_each_rig(self):
        formula, source, check_path = self._city_check("echo city-check-v1")
        self._select(formula)

        repaired = self._run()

        self.assertEqual(0, repaired.returncode, repaired.stdout + repaired.stderr)
        for store in (self.city, self.city / "rigs" / "backend", self.city / "rigs" / "frontend"):
            target = store / check_path
            self.assertTrue(target.is_file() and not target.is_symlink(), target)
            self.assertEqual(source.read_bytes(), target.read_bytes())
            executed = subprocess.run([str(target)], check=False, capture_output=True, text=True, cwd=store)
            self.assertEqual("city-check-v1", executed.stdout.strip(), executed.stderr)
        clean = self._run("--check-only")
        self.assertEqual(0, clean.returncode, clean.stdout + clean.stderr)

    def test_the_city_root_receives_no_pack_gate(self):
        own, _source, check_path = self._city_check()
        pack, _gate = self._pack("pack-v1")
        self._select(own, pack)

        repaired = self._run()

        self.assertEqual(0, repaired.returncode, repaired.stdout + repaired.stderr)
        self.assertTrue((self.city / check_path).is_file())
        self.assertFalse((self.city / CHECK_PATH).exists(), "a pack gate is for rigs, not for the city root")
        self.assertTrue(self._target("backend").is_file())


if __name__ == "__main__":
    unittest.main()
