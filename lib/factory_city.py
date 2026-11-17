#!/usr/bin/env python3
"""The city a Factory tool talks to when FACTORY_ROOT does not name one.

    python3 lib/factory_city.py CHECKOUT

prints the city CHECKOUT belongs to: the main checkout of its repository
when CHECKOUT is a linked work tree (an agent's do-work tree), CHECKOUT
itself otherwise. FACTORY_ROOT, when set, still names the city: each caller
reads it first, as before.

A tool's own directory is not a city when it runs from a work tree: the tree
carries city.toml but never the generated city.provider.toml it includes, so
`gc --city <tree>` fails before reading anything. On 17/11/2026 an agent's
`bin/proposal-door` filed maintenance bead af-oa01l3 from its work tree and
its dispatch died on that missing file; the fix waited for a manual relaunch
(af-zry5xu). Every `gc --city` default of bin/ and lib/ comes from here;
tests/factory-city-test.py holds that.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def city_root(checkout: Path) -> Path:
    """The main checkout of CHECKOUT's repository, or CHECKOUT itself."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "--path-format=absolute",
             "--git-dir", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return checkout
    lines = proc.stdout.splitlines()
    if proc.returncode or len(lines) != 2 or lines[0] == lines[1]:
        return checkout
    common = Path(lines[1])
    # A bare repository has no main checkout to fall back to.
    return common.parent if common.name == ".git" else checkout


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: factory_city.py CHECKOUT", file=sys.stderr)
        return 2
    print(city_root(Path(argv[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
