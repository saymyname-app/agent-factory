#!/usr/bin/env python3
"""Regression tests for docs/CONTEXT_INDEX.md and docs/FACTORY_TOOLS.md
generation from per-entry sources (P02, af-ulqtp)."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.factory_docs_catalogue import catalogues, check, render  # noqa: E402


class GeneratedFilesAreUpToDate(unittest.TestCase):
    """The checked-in CONTEXT_INDEX.md / FACTORY_TOOLS.md must equal what the
    generator produces from the current per-entry sources -- this is exactly
    what CI's --check invocation asserts."""

    def test_context_index_and_factory_tools_match_sources(self):
        problems = [check(c) for c in catalogues(ROOT)]
        problems = [p for p in problems if p]
        self.assertEqual(problems, [], "\n".join(problems))


class StaleFileIsDetected(unittest.TestCase):
    """Editing a generated file without regenerating it must fail --check
    with an operator-readable message (acceptance criterion 3)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name) / "repo"
        source_dir = self.work / "docs" / "context-index"
        shutil.copytree(ROOT / "docs" / "context-index", source_dir)
        self.source_dir = source_dir

    def test_hand_edited_target_is_flagged_stale(self):
        source_dir = self.source_dir
        catalogue = [c for c in catalogues(self.work) if c.name == "context-index"][0]

        # Not generated yet: check reports the missing target.
        problem = check(catalogue)
        self.assertIsNotNone(problem)
        self.assertIn(str(catalogue.target), problem)

        catalogue.target.write_text(render(catalogue), encoding="utf-8")
        self.assertIsNone(check(catalogue))

        # Hand-edit one entry without regenerating: check must fail again.
        entries = sorted((source_dir / "entries").glob("*.md"))
        entries[0].write_text("Need: changed\nRead: `nowhere.md`\n", encoding="utf-8")
        problem = check(catalogue)
        self.assertIsNotNone(problem)
        self.assertIn("stale", problem)


class EntryIsolation(unittest.TestCase):
    """Adding one entry file must not require editing any other entry file
    or either static frame file (acceptance criterion 1)."""

    def test_new_entry_does_not_require_touching_siblings(self):
        for catalogue in catalogues(ROOT):
            entries_dir = catalogue.source_dir / "entries"
            before = {p: p.read_text(encoding="utf-8") for p in entries_dir.glob("*.md")}

            new_entry = entries_dir / "9999-test-isolation-probe.md"
            if catalogue.row_format == "table-row":
                new_entry.write_text("Need: probe\nRead: `PROBE.md`\n", encoding="utf-8")
            else:
                new_entry.write_text("## `./bin/probe` -- test only\n\nprobe.\n", encoding="utf-8")
            try:
                render(catalogue)  # must not raise
                after = {p: p.read_text(encoding="utf-8") for p in entries_dir.glob("*.md") if p != new_entry}
                self.assertEqual(before, after)
            finally:
                new_entry.unlink()


if __name__ == "__main__":
    unittest.main()
