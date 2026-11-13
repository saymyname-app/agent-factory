#!/usr/bin/env python3
"""An alert script looks for its existing bead among every unfinished status
(af-yzojic, docs/DEFECT_CLASSES.md S). Scripts are named here without their
directory: this file only reads them (tests/sandbox-isolation-check-test.sh).

On 2026-11-13 on-order-failed looked for the bead of a failing order with
`--status open` only. That bead, af-65mbq2, was in_progress under its repair,
so three more beads of the same cause were filed and paged beside it
(af-0965hq, af-uzajg3, af-to7kkp). A bead taken for repair, or parked, is
still the bead of its cause. Every `bd list --title-contains` in bin/ either
reads the unfinished statuses below, or is a sweep that closes only the
alerts nobody took yet and says so on the line above (`# open only: ...`).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNFINISHED = "--status open,in_progress,blocked,deferred"
LOOKUP = re.compile(r"\bbd list\b.*--title-contains")
OPEN_ONLY = "# open only:"


def offenders(text: str) -> list[str]:
    found = []
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#") or not LOOKUP.search(line):
            continue
        if UNFINISHED in line or "--status closed" in line:
            continue
        if number > 1 and lines[number - 2].strip().startswith(OPEN_ONLY):
            continue
        found.append(f"{number}: {line.strip()}")
    return found


class AlertDedupStatusTest(unittest.TestCase):
    def test_every_title_lookup_in_bin_reads_the_unfinished_statuses(self):
        bad = {}
        for script in sorted((ROOT / "bin").iterdir()):
            if not script.is_file():
                continue
            try:
                text = script.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if found := offenders(text):
                bad[script.name] = found
        self.assertEqual(bad, {}, f"a title lookup reads open beads only; use `{UNFINISHED}`, "
                                  f"or mark a sweep that closes untaken alerts with `{OPEN_ONLY} <why>` "
                                  f"on the line above")

    def test_the_lookup_of_the_incident_is_refused(self):
        incident = 'done < <(gc bd list --status open --title-contains "$title" --json)'
        self.assertEqual(len(offenders(incident)), 1)

    def test_a_marked_sweep_and_the_unfinished_lookup_pass(self):
        sweep = "  # open only: closed by its repair\n  done < <(gc bd list --status open --title-contains \"$P\")"
        lookup = f'done < <(gc bd list {UNFINISHED} --title-contains "$title" --json)'
        self.assertEqual(offenders(sweep), [])
        self.assertEqual(offenders(lookup), [])


if __name__ == "__main__":
    unittest.main()
