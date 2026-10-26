#!/usr/bin/env python3
"""Every criterion test of the cockpit that launches the product is named in
the closed list of the whole journeys (docs/TEST_GUIDELINE.md, point 3;
af-npz9v1.17).

« The whole journeys of a repository are a closed list, written in this
document. » Five tickets of convoy af-strhoy out of six (A1, E, C1, G1, F,
then D) were refused at their first code review because a new criterion
test launched the cockpit and the list did not name it: a round of
correction spent on what a reading of two files sees. This file is in the
regression of the profile (`tests/cockpit-*-test.py`,
tests/cockpit-criteria/regression.py), so an author meets it at
`bin/tdd-step green`, before the review, and CI meets it on main.

A file is a whole journey when its text speaks of a launch (the product
started by `bin/project-launch` or its harness): the criterion tests that
drive a command alone (`project-registry-list-test.py`,
`request-doors-test.py`) never do. The list names a file by its path in
backquotes, alternatives in braces (`home-destination-{states,fidelity}-test.py`)
counting for each of them.

Adding a file to the list stays what the guideline says: decided in the
testing section of a Spec, and written in the same change.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDELINE = "docs/TEST_GUIDELINE.md"
CRITERIA = "tests/cockpit-criteria"
LAUNCH = re.compile(r"\blaunch", re.IGNORECASE)


def named(guideline: str) -> set[str]:
    """The paths the guideline names in backquotes, braces expanded."""
    names = set()
    for token in re.findall(r"`([^`\s]+)`", guideline):
        braces = re.search(r"\{([^}]*)\}", token)
        alternatives = braces.group(1).split(",") if braces else [None]
        for alternative in alternatives:
            names.add(token if braces is None else token[:braces.start()] + alternative + token[braces.end():])
    return names


def unnamed_journeys(root: Path) -> list[str]:
    """The criterion tests that launch the product and the list does not name."""
    names = named((root / GUIDELINE).read_text(encoding="utf-8"))
    tests = sorted((root / CRITERIA).rglob("*-test.py"))
    return [path.relative_to(root).as_posix() for path in tests
            if LAUNCH.search(path.read_text(encoding="utf-8")) and path.relative_to(root).as_posix() not in names]


class ClosedList(unittest.TestCase):
    def test_every_launching_criterion_test_is_named(self) -> None:
        """The repository itself: what makes a ticket red at green."""
        missing = unnamed_journeys(ROOT)
        self.assertEqual(missing, [], (
            f"parcours complets absents de la liste fermée de {GUIDELINE} (point 3) : {', '.join(missing)} — "
            "les inscrire dans la table « In the battery », avec la décision de test de la Spec qui les permet"))

    def test_an_unnamed_journey_is_found_and_braces_name_each_alternative(self) -> None:
        """A tree written here: one listed by braces, one unlisted, one command alone."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / GUIDELINE).write_text(
                "| `tests/cockpit-criteria/commands/home-{states,layout}-test.py` | the cockpit launched |\n",
                encoding="utf-8")
            commands = root / CRITERIA / "commands"
            commands.mkdir(parents=True)
            (commands / "home-states-test.py").write_text("tree.launch('home-content')\n", encoding="utf-8")
            (commands / "home-layout-test.py").write_text("tree.launch('home-light')\n", encoding="utf-8")
            (commands / "journal-events-test.py").write_text("tree.launch('journal-content')\n", encoding="utf-8")
            (commands / "registry-list-test.py").write_text("run(['bin/project-planning-profile', 'list'])\n",
                                                            encoding="utf-8")
            self.assertEqual(unnamed_journeys(root), ["tests/cockpit-criteria/commands/journal-events-test.py"])


if __name__ == "__main__":
    unittest.main()
