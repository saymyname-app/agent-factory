#!/usr/bin/env python3
"""Criterion test 2 of G1 « Usine — observation, fraîcheur et rôles réels »
(af-wrxrmg; Spec af-fgcw0d, user story 65, Testing Decisions 1 and 8): the
button « Revérifier » of a section of the destination Usine.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset health-content, reads the page GET /usine
as a headless Chromium renders it, activates the button « Revérifier… » that
one section holds, and reads the page again (usine_page.py). A section
says the time it was read to the second: a reading done again a few seconds
later is seen there.

False if the button reads nothing again (the time of its section does not
change) or reads the whole page again without saying so (the time or the
text of another section changes).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import (  # noqa: E402
    PAGE, TIME_TO_THE_SECOND, LaunchTree, anchors_by_name, measure, recheck_of, section_titled, sections,
)


class FactoryRecheck(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_rechecks_only_its_section(self, title: str) -> None:
        address = self.tree.launch("health-content")
        frame = measure(address, PAGE)[0]
        section, said = section_titled(self, frame, title)
        control = recheck_of(self, frame, section)
        self.assertFalse(control["disabled"], f"« {control['name']} » cannot be activated")
        read_at = TIME_TO_THE_SECOND.findall(said)
        self.assertTrue(read_at, f"the section « {title} » does not say when it was read, to the second: « {said} »")

        frame = measure(address, PAGE, click=control["name"])[0]
        before = sections(frame)
        after_frame = frame["after"]
        self.assertTrue(after_frame["found"], f"« {control['name']} » is not on the page")
        self.assertEqual(PAGE, after_frame["path"], "the button does not lead back to the page Usine")
        after = sections(after_frame)
        _, said_after = section_titled(self, after_frame, title)
        self.assertNotEqual(TIME_TO_THE_SECOND.findall(before[section]), TIME_TO_THE_SECOND.findall(said_after),
                            f"the section « {title} » was not read again: « {said_after} »")

        by_name = anchors_by_name(frame)
        nested = {section, *by_name[section]["chain"]}
        others = {name: text for name, text in before.items()
                  if name not in nested and section not in by_name[name]["chain"]}
        self.assertTrue(others, "the page has no other section")
        self.assertEqual(others, {name: after.get(name) for name in others},
                         f"rechecking « {title} » changed another section")

    def test_rechecking_the_connections_reads_them_again_and_no_other_section(self):
        self.assert_rechecks_only_its_section("Connexions")

    def test_rechecking_the_machine_reads_it_again_and_no_other_section(self):
        self.assert_rechecks_only_its_section("Machine d’exécution")


if __name__ == "__main__":
    unittest.main()
