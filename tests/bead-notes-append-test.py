#!/usr/bin/env python3
"""Category H (af-2cuvon): a write on an existing bead adds to its notes,
it never replaces them.

On 2026-11-11 and again on 2026-11-17 the close of af-icbz5h wiped every
note written on the ticket: `bin/deliver-close` passed `--notes` (which
replaces) instead of `--append-notes`. Every `bd update` of `bin/`, `lib/`,
`formulas/` and `orders/`, and the rule AGENTS.md gives agents, writes its
notes with `--append-notes`. `bd create --notes` stays allowed: a new bead
has no notes to lose."""

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `--notes` as a flag, not the tail of `--append-notes`.
REPLACE = re.compile(r"""(?<![\w-])--notes(?![\w-])""")


def logical_lines(text):
    """Each command of a text, its shell continuation lines joined."""
    command = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        command += " " + stripped
        if stripped.endswith("\\"):
            command = command[:-1]
            continue
        yield command
        command = ""
    if command:
        yield command


def scanned(root):
    for folder in ("bin", "lib", "formulas", "orders"):
        base = root / folder
        if base.is_dir():
            yield from (p for p in sorted(base.rglob("*")) if p.is_file())
    if (root / "AGENTS.md").is_file():
        yield root / "AGENTS.md"


def offenders(root):
    bad = []
    for path in scanned(root):
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="replace")
        for command in logical_lines(text):
            if REPLACE.search(command) and " create" not in command:
                bad.append(f"{rel}: {command.strip()[:160]}")
    return bad


class BeadNotesAppendTest(unittest.TestCase):
    def test_no_write_replaces_the_notes_of_a_bead(self):
        self.assertEqual([], offenders(ROOT))

    def test_a_replacing_write_is_named_and_an_appending_one_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "bin").mkdir()
            (fake / "lib").mkdir()
            (fake / "bin" / "tool").write_text(
                '#!/usr/bin/env bash\n'
                'gc bd update "$id" --status=closed \\\n'
                '  --notes "closed"\n'
                'gc bd update "$id" --status=closed --append-notes "closed"\n'
                'gc bd create "title" --notes "first note"\n'
            )
            (fake / "lib" / "tool.py").write_text(
                'run(["bd", "update", bead, "--notes", reason])\n'
            )

            bad = offenders(fake)

        self.assertEqual(2, len(bad), bad)
        self.assertIn('bin/tool: gc bd update "$id" --status=closed  --notes "closed"', bad[0])
        self.assertIn("lib/tool.py:", bad[1])


if __name__ == "__main__":
    unittest.main()
