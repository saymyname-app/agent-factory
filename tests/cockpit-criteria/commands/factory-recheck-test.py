#!/usr/bin/env python3
"""Criterion test 2 of G1 « Usine — observation, fraîcheur et rôles réels »
(af-wrxrmg; Spec af-fgcw0d, user story 65, Testing Decisions 1 and 8): the
button « Revérifier maintenant » of a section of the destination Usine.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset health-content, reads the page GET /usine
as a headless Chromium renders it, activates the button « Revérifier
maintenant » that one section holds, and reads the page again
(usine_page.py). A section says the time it was read to the second: a
reading done again a few seconds later is seen there, and in what the
section read -- the connections read again after the section's last check,
the time in service of the machine grown by the time between its two
checks.

False if the button reads nothing again (the time of its section does not
change, or what it shows was not read again) or reads the whole page again
without saying so (the time or the text of another section changes).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from usine_page import (  # noqa: E402
    PAGE, TIME_TO_THE_SECOND, LaunchTree, anchors_by_name, connection_rows, measure, recheck_of, section_titled,
    sections,
)


def seconds(clock: str) -> int:
    """« 14:42:07 » in seconds of the day."""
    hours, minutes, secs = (int(part) for part in clock.split(":"))
    return hours * 3600 + minutes * 60 + secs


def in_service(said: str) -> int:
    """How long the machine says it has been in service, in seconds."""
    found = re.search(r"en service depuis ((?:\d+ (?:j|h|min) )*\d+ s)", said)
    assert found, f"the machine does not say how long it has been in service: « {said} »"
    sizes = {"j": 86400, "h": 3600, "min": 60, "s": 1}
    return sum(int(count) * sizes[unit] for count, unit in re.findall(r"(\d+) (j|h|min|s)\b", found.group(1)))


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

    def assert_rechecks_only_its_section(self, title: str, read_again) -> None:
        address = self.tree.launch("health-content")
        frame = measure(address, PAGE)[0]
        section, said = section_titled(self, frame, title)
        control = recheck_of(self, frame, section)
        self.assertTrue(control["name"].startswith("Revérifier maintenant"),
                        f"the button of « {title} » is not « Revérifier maintenant »: « {control['name']} »")
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
        read_again(frame, after_frame, before[section], said_after)

        by_name = anchors_by_name(frame)
        nested = {section, *by_name[section]["chain"]}
        others = {name: text for name, text in before.items()
                  if name not in nested and section not in by_name[name]["chain"]}
        self.assertTrue(others, "the page has no other section")
        self.assertEqual(others, {name: after.get(name) for name in others},
                         f"rechecking « {title} » changed another section")

    def test_rechecking_the_connections_reads_them_again_and_no_other_section(self):
        def read_again(frame, after_frame, said, said_after):
            checked = seconds(TIME_TO_THE_SECOND.findall(said)[0])
            before = [row for row in connection_rows(frame).values() if row.startswith("Superviseur")]
            after = [row for row in connection_rows(after_frame).values() if row.startswith("Superviseur")]
            self.assertTrue(before and after, "the connection « Superviseur » is not shown before and after")
            read_at = re.search(r"lu à (\d{1,2}:\d{2}:\d{2})", after[0])
            self.assertTrue(read_at, f"the supervisor does not say when it was read: « {after[0]} »")
            self.assertGreater(seconds(read_at.group(1)), checked,
                               f"the supervisor was not read again after the last check ({said}): « {after[0]} »")

        self.assert_rechecks_only_its_section("Connexions", read_again)

    def test_rechecking_the_machine_reads_it_again_and_no_other_section(self):
        def read_again(frame, after_frame, said, said_after):
            elapsed = (seconds(TIME_TO_THE_SECOND.findall(said_after)[0])
                       - seconds(TIME_TO_THE_SECOND.findall(said)[0]))
            grown = in_service(said_after) - in_service(said)
            self.assertLessEqual(abs(grown - elapsed), 2,
                                 f"the machine was not read again: in service {grown} s longer, checked {elapsed} s "
                                 "later")

        self.assert_rechecks_only_its_section("Machine d’exécution", read_again)


if __name__ == "__main__":
    unittest.main()
