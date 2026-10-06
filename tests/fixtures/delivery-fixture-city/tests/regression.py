#!/usr/bin/env python3
"""Regression command declared by descriptor.json's launch.regression_command.

A `prefactoring` ticket on this fixture project has this run before and
after its change by bin/tdd-step (T10, af-j8jo02): both runs must exit 0.
It characterises the home page of the fixture product on its `content`
dataset: the three anchors and what they hold.
"""

import importlib.util
import json
import sys
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]

EXPECTED = (
    '<h1 data-anchor="fixture-state">content</h1>',
    '<p data-anchor="fixture-generated-at">2026-01-01T00:00:00Z</p>',
    '<ul data-anchor="fixture-items"><li>alpha</li><li>beta</li><li>gamma</li></ul>',
)


def main():
    spec = importlib.util.spec_from_file_location("fixture_app", PRODUCT / "app.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    handler = app.FixtureHandler.__new__(app.FixtureHandler)
    handler.dataset = json.loads((PRODUCT / "datasets" / "content.json").read_text())
    page = handler._render_page()
    missing = [fragment for fragment in EXPECTED if fragment not in page]
    for fragment in missing:
        sys.stderr.write(f"regression: absent from the home page: {fragment}\n")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
