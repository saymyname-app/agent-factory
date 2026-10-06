#!/usr/bin/env python3
"""Test command of the Delivery Fixture City (descriptor.json,
launch.test_command; T10, af-j8jo02).

    harness.py TEST REPORT

Runs one criterion test and writes a JUnit XML report of it, one `testcase`
per test, where an assertion failure (`failure`) is distinct from any other
exception (`error`, with its type) and from a skipped test (`skipped`):
what bin/tdd-step reads. TEST is a test file, optionally followed by
`::Class` or `::Class.method`. The criterion tests reach the launched
product at the address given in PRODUCT_ADDRESS.

Frozen harness path: a change to this file after the freeze of a ticket's
criterion tests is refused by the green step without an amendment.
"""

import importlib.util
import sys
import unittest
from xml.etree import ElementTree


class Recorder(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.cases = []

    def record(self, test, outcome=None, error=None):
        case = ElementTree.Element("testcase", classname=type(test).__name__, name=test._testMethodName)
        if outcome is not None:
            child = ElementTree.SubElement(case, outcome)
            if error is not None:
                child.set("type", error[0].__name__)
                child.set("message", str(error[1]))
        self.cases.append(case)

    def addSuccess(self, test):
        self.record(test)

    def addFailure(self, test, err):
        self.record(test, "failure", err)

    def addError(self, test, err):
        self.record(test, "error", err)

    def addSkip(self, test, reason):
        self.record(test, "skipped")


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: harness.py TEST REPORT\n")
        return 2
    test_id, report = argv
    path, _, selector = test_id.partition("::")
    result = Recorder()
    try:
        spec = importlib.util.spec_from_file_location("criterion_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(selector, module) if selector else loader.loadTestsFromModule(module)
        suite.run(result)
    except Exception as exc:  # the test file itself cannot be loaded
        case = ElementTree.Element("testcase", classname="", name=selector or path)
        ElementTree.SubElement(case, "error", type=type(exc).__name__, message=str(exc))
        result.cases.append(case)
    suite_element = ElementTree.Element("testsuite", name=test_id, tests=str(len(result.cases)))
    suite_element.extend(result.cases)
    ElementTree.ElementTree(suite_element).write(report, encoding="utf-8", xml_declaration=True)
    return 0 if result.cases and all(len(case) == 0 for case in result.cases) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
