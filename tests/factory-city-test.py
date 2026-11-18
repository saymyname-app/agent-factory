#!/usr/bin/env python3
"""af-zry5xu: a Factory tool launched from an agent's work tree talks to the
live city, never to the work tree (which lacks the generated
city.provider.toml, so `gc --city <tree>` fails before reading anything).

Proves: lib/factory_city.py names the main checkout for a linked work tree,
and the checkout itself for a main checkout or a directory outside git; and
every tool of bin/ and lib/ that names a city to gc takes its default from
lib/factory_city.py, or is in EXEMPT with why. The dispatch from a work tree
is proven end to end by tests/factory-work-dispatch-test.sh.
"""

import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "lib" / "factory_city.py"
sys.path.insert(0, str(ROOT / "lib"))
import factory_city  # noqa: E402

# A tool that names a city to gc without lib/factory_city.py, and why.
EXEMPT = {
    "bin/factory-guard": "its default is the live city's fixed path",
    "bin/factory-dispatch-guard": "its default is the live city's fixed path",
    "bin/dispatch-door-guard": "its default is the live city's fixed path",
    "bin/factory-waiting-guard": "its default is the live city's fixed path",
    "bin/role-adoption-trial": "it names the trial city it builds itself",
    "bin/factory-maintain": "it names only the city given by its --city argument",
}
NAMES_A_CITY = re.compile(r'--city "\$|"--city",')


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


class FactoryCityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name).resolve()
        cls.main, cls.tree, cls.outside = base / "main", base / "tree", base / "outside"
        git("init", "-q", str(cls.main))
        git("-C", str(cls.main), "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "-q", "--allow-empty", "-m", "init")
        git("-C", str(cls.main), "worktree", "add", "-q", str(cls.tree), "-b", "do-work/x")
        cls.outside.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def city(self, checkout):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(factory_city.main([str(checkout)]), 0)
        return out.getvalue().strip()

    def test_a_work_tree_names_its_main_checkout(self):
        self.assertEqual(self.city(self.tree), str(self.main))

    def test_a_main_checkout_names_itself(self):
        self.assertEqual(self.city(self.main), str(self.main))

    def test_a_directory_outside_git_names_itself(self):
        self.assertEqual(self.city(self.outside), str(self.outside))

    def test_the_command_line_prints_the_city(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), str(self.tree)],
                              capture_output=True, text=True)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, str(self.main)))

    def test_the_command_line_refuses_a_missing_checkout(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_every_tool_naming_a_city_resolves_it_here(self):
        stray = []
        for path in sorted([*(ROOT / "bin").iterdir(), *(ROOT / "lib").rglob("*.py")]):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8", errors="replace")
            if NAMES_A_CITY.search(text) and "factory_city" not in text and rel not in EXEMPT:
                stray.append(rel)
        self.assertEqual(stray, [], "these tools name a city to gc without lib/factory_city.py; "
                         "from an agent's work tree they name the tree")


if __name__ == "__main__":
    unittest.main()
