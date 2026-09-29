#!/usr/bin/env python3
"""Generate docs/CONTEXT_INDEX.md and docs/FACTORY_TOOLS.md from per-entry
source files, so adding one tool or one doc pointer touches only its own
new file under docs/<catalogue>/entries/ (P02, af-ulqtp).

Each catalogue is a directory (docs/context-index/, docs/factory-tools/)
holding:
  intro.md          -- static text before the first entry (title, table
                        header for context-index; title/warnings for
                        factory-tools)
  outro.md          -- optional static text after the last entry
  entries/*.md      -- one file per catalogue entry, sorted by filename

The generated file is exactly intro + entries (in filename order) + outro,
concatenated with no separator inserted by this script: every byte that
separates one entry from the next (blank lines, a `---` rule, or nothing)
lives inside the entry files themselves, so the generator never has to
guess formatting.

context-index entries are two plain lines, "Need: ..." and "Read: ...",
rendered as one Markdown table row. factory-tools entries are raw Markdown
sections (starting with "## ") copied through verbatim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class Catalogue:
    name: str
    source_dir: Path
    target: Path
    row_format: str  # "table-row" or "raw"


def _entries(source_dir: Path) -> list[Path]:
    entries_dir = source_dir / "entries"
    if not entries_dir.is_dir():
        raise FileNotFoundError(f"{entries_dir} does not exist")
    files = sorted(p for p in entries_dir.glob("*.md") if p.is_file())
    if not files:
        raise ValueError(f"{entries_dir} has no entries")
    return files


def _read_static(source_dir: Path, name: str) -> str:
    path = source_dir / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


_ROW_RE = re.compile(r"^Need:\s?(?P<need>.*)$\nRead:\s?(?P<read>.*)$", re.MULTILINE)


def _render_table_row(entry_path: Path) -> str:
    text = entry_path.read_text(encoding="utf-8")
    match = _ROW_RE.match(text)
    if not match:
        raise ValueError(f"{entry_path}: expected 'Need: ...' / 'Read: ...' lines")
    return f"| {match['need']} | {match['read']} |\n"


def render(catalogue: Catalogue) -> str:
    intro = _read_static(catalogue.source_dir, "intro.md")
    outro = _read_static(catalogue.source_dir, "outro.md")
    entries = _entries(catalogue.source_dir)

    if catalogue.row_format == "table-row":
        body = "".join(_render_table_row(p) for p in entries)
    elif catalogue.row_format == "raw":
        body = "".join(p.read_text(encoding="utf-8") for p in entries)
    else:
        raise ValueError(f"unknown row_format: {catalogue.row_format}")

    return intro + body + outro


def catalogues(root: Path) -> list[Catalogue]:
    return [
        Catalogue(
            name="context-index",
            source_dir=root / "docs" / "context-index",
            target=root / "docs" / "CONTEXT_INDEX.md",
            row_format="table-row",
        ),
        Catalogue(
            name="factory-tools",
            source_dir=root / "docs" / "factory-tools",
            target=root / "docs" / "FACTORY_TOOLS.md",
            row_format="raw",
        ),
    ]


def generate(catalogue: Catalogue) -> None:
    catalogue.target.write_text(render(catalogue), encoding="utf-8")


def check(catalogue: Catalogue) -> str | None:
    """Return None if catalogue.target is up to date, else a mismatch reason."""
    expected = render(catalogue)
    if not catalogue.target.is_file():
        return f"{catalogue.target} does not exist"
    actual = catalogue.target.read_text(encoding="utf-8")
    if actual != expected:
        return (
            f"{catalogue.target} is stale relative to "
            f"{catalogue.source_dir}/ -- run bin/generate-docs-catalogue to refresh it"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        default=[],
        help="which catalogues to process (default: all; "
        "choices: context-index, factory-tools)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if a generated file is stale instead of writing it",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: this repo)",
    )
    args = parser.parse_args(argv)

    all_catalogues = {c.name: c for c in catalogues(args.root)}
    unknown = [n for n in args.targets if n not in all_catalogues]
    if unknown:
        parser.error(f"invalid target(s): {', '.join(unknown)}")
    selected = [all_catalogues[n] for n in (args.targets or all_catalogues.keys())]

    if args.check:
        problems = [check(c) for c in selected]
        problems = [p for p in problems if p]
        for problem in problems:
            print(f"factory-docs-catalogue: {problem}", file=sys.stderr)
        return 1 if problems else 0

    for c in selected:
        generate(c)
        print(f"factory-docs-catalogue: wrote {c.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
