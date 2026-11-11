#!/usr/bin/env python3
"""At a ticket's green, the cockpit's criterion tests keep to the ticket's
families and the end-to-end launch (study C, T4, af-npz9v1.31); anywhere
else they run whole. They start longest first (af-8a246o). Reads `selected`
and `longest_first` of tests/cockpit-criteria-test.py."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cockpit_criteria", ROOT / "tests" / "cockpit-criteria-test.py")
CRITERIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CRITERIA)

COMMANDS = Path("tests/cockpit-criteria/commands")
ALL = [COMMANDS / name for name in (
    "factory-roles-test.py", "home-d01-records-test.py", "isolated-launch-test.py",
    "runs-destination-job-test.py", "runs-destination-list-test.py", "journal-destination-events-test.py")]


class Selection(unittest.TestCase):
    def names(self, ticket_tests):
        return [path.name for path in CRITERIA.selected(ALL, ticket_tests)]

    def test_a_ticket_of_one_screen_runs_that_screen_and_the_end_to_end_launch(self):
        self.assertEqual(["isolated-launch-test.py", "runs-destination-job-test.py", "runs-destination-list-test.py"],
                         self.names("tests/cockpit-criteria/commands/runs-destination-sessions-test.py"))

    def test_a_ticket_of_two_screens_runs_both(self):
        self.assertEqual(
            ["home-d01-records-test.py", "isolated-launch-test.py", "journal-destination-events-test.py"],
            self.names("tests/cockpit-criteria/commands/home-x-test.py tests/cockpit-criteria/http/journal-y-test.py"))

    def test_no_ticket_named_runs_every_file(self):
        self.assertEqual([path.name for path in ALL], self.names(""))
        self.assertEqual([path.name for path in ALL], self.names("   "))

    def test_a_ticket_of_a_new_screen_still_runs_the_end_to_end_launch(self):
        self.assertEqual(["isolated-launch-test.py"],
                         self.names("tests/cockpit-criteria/commands/analyses-indicators-test.py"))


class Order(unittest.TestCase):
    def test_the_longest_measured_class_starts_first_and_an_unmeasured_one_before_it(self):
        self.assertEqual(["new.py::New", "a.py::Long", "c.py::Mid", "b.py::Short"],
                         CRITERIA.longest_first(["a.py::Long", "b.py::Short", "c.py::Mid", "new.py::New"],
                                                {"a.py::Long": 900, "b.py::Short": 40, "c.py::Mid": 300}))

    def test_without_any_measure_the_classes_keep_their_order(self):
        self.assertEqual(["a.py::A", "b.py::B"], CRITERIA.longest_first(["a.py::A", "b.py::B"], {}))


if __name__ == "__main__":
    unittest.main()
