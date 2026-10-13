#!/usr/bin/env python3
"""A cancelled evaluation releases only the workflow and session it owns."""

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "bin" / "evaluation-launch-cancel"
loader = importlib.machinery.SourceFileLoader("evaluation_launch_cancel", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)


class CancelTest(unittest.TestCase):
    def run_case(self, extra=None, template="delivery-evaluator", already_closed=False):
        writes = []

        def data(*args):
            if args[:2] == ("bd", "show"):
                return [{"id": "launch", "status": "closed" if already_closed else "open"}]
            if args[:3] == ("bd", "dep", "list"):
                return [{"id": "input"}]
            if args[:2] == ("convoy", "status"):
                return {"children": [{"id": "launch"}]}
            if args[:2] == ("session", "list"):
                return {"sessions": [{"id": "own-session", "template": template, "closed": False},
                                     {"id": "other-session", "template": "delivery-evaluator", "closed": False}]}
            if args[:2] == ("bd", "list"):
                if "gc.input_convoy_id=input" in args:
                    return [{"id": "workflow", "status": "closed" if already_closed else "in_progress",
                             "metadata": {"gc.formula_name": "mol-ticket-evaluation"}}]
                if "gc.root_bead_id=workflow" in args:
                    return [{"id": "step", "assignee": "delivery-evaluator",
                             "metadata": {"gc.session_id": "own-session"}}]
                if "gc.session_id=own-session" in args:
                    return extra or []
            raise AssertionError(args)

        previous_data, previous_call = tool.data, tool.call
        tool.data = data
        tool.call = lambda *args: writes.append(args) or ""
        try:
            if extra or template != "delivery-evaluator":
                with self.assertRaises(RuntimeError):
                    tool.cancel("launch")
            else:
                tool.cancel("launch")
        finally:
            tool.data, tool.call = previous_data, previous_call
        return writes

    def test_closes_exact_workflow_bead_and_own_session(self):
        writes = self.run_case()
        self.assertIn(("convoy", "delete", "workflow", "--force"), writes)
        self.assertIn(("bd", "update", "launch", "--set-metadata", "gc.outcome=fail",
                       "--set-metadata", "gc.work_outcome=abandoned", "--status", "closed"), writes)
        self.assertEqual([("session", "close", "own-session")],
                         [call for call in writes if call[:2] == ("session", "close")])

    def test_never_closes_session_with_other_in_progress_work(self):
        writes = self.run_case(extra=[{"id": "other-work"}])
        self.assertFalse(any(call[:2] == ("session", "close") for call in writes))

    def test_never_closes_a_foreign_role(self):
        writes = self.run_case(template="delivery-author")
        self.assertFalse(any(call[:2] == ("session", "close") for call in writes))

    def test_retries_session_close_after_bead_and_workflow_were_closed(self):
        writes = self.run_case(already_closed=True)
        self.assertEqual([("session", "close", "own-session")], writes)


if __name__ == "__main__":
    unittest.main()
