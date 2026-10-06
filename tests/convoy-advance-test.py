#!/usr/bin/env python3
"""bin/convoy-advance on a fake tracker state (T04, af-gfyj6k; Spec af-wf4w5r
§0 rule 3, §4, user story 82; Testing Decisions seam 2).

The advance command starts the ready tickets of a convoy that carries the
new-flow mark, through the real bin/dispatch-door, under the factory-wide
ceiling N. One test per pass and per refusal; a refusal re-reads the tracker
to prove nothing was written. Only command lines are exercised: the tracker
is tests/fixtures/convoy-state/gc, the Factory root is a synthetic one."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "convoy-advance"
STATE = ROOT / "bin" / "convoy-state"
DOOR = ROOT / "bin" / "dispatch-door"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY = "fx-convoy"
OTHER = "fx-other"
PLAIN = "fx-plain"
T1, T2, T3 = "fx-t1", "fx-t2", "fx-t3"
COMMIT = "0123456789abcdef0123456789abcdef01234567"

EXIT_REFUSED = 1
EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4

DOOR_STAMP = "gc.dispatched_via"
DISPATCH_GATE = "gc.flow.gate.dispatch"


def ticket(ticket_id, blocks=(), rig="fx-rig"):
    return {"title": f"ticket {ticket_id}", "status": "open", "issue_type": "task",
            "description": f"## What to build\n\nessai\n\n## Target rigs\n\n{rig}\n\n## Autonomous execution contract\n\n- none",
            "metadata": {"gc.ticket_kind": "vertical_slice"}, "blocks": list(blocks)}


def session(template, state="active"):
    return {"id": f"s-{template}", "template": template, "state": state, "closed": False}


class ConvoyAdvanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="convoy-advance-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.root = self.tmp / "root"
        (self.root / "config" / "projects").mkdir(parents=True)
        (self.root / "config" / "projects" / "fx-rig.toml").write_text(
            'rig_dir = "."\nrepo = "example/fx"\nprotected_branch = "main"\nrequired_ci = "CI"\n'
            'sling_target = "fx-worker"\nformulas = "fx-start"\n')
        shutil.copy(ROOT / "config" / "delivery-roles.json", self.root / "config" / "delivery-roles.json")
        provider_failover = self.tmp / "provider-failover"
        provider_failover.write_text("#!/bin/sh\nprintf '{}\\n'\n")
        provider_failover.chmod(0o755)
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "CONVOY_ADVANCE_LOCK_DIR": str(self.tmp / "locks"),
            "DISPATCH_DOOR_PROVIDER_FAILOVER_BIN": str(provider_failover),
            "DISPATCH_DOOR_MEMINFO_FILE": str(self.tmp / "no-meminfo"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.env.pop("CONVOY_STATE_FAKE_SLING_FAIL", None)
        self.settings(ceiling=5)
        self.seed()

    # --- harness ------------------------------------------------------------

    def settings(self, ceiling=5, formula="fx-start", role=None):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1",
            "max_sessions": ceiling,
            "start": {"formula": formula, "role": role},
        }))

    def seed(self, sessions=()):
        """A marked convoy of three tickets, the third blocked by the two
        others; a second marked convoy of one ticket; an unmarked convoy."""
        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": "fx-spec"}, "tracks": [T1, T2, T3]},
            T1: ticket(T1), T2: ticket(T2), T3: ticket(T3, blocks=(T1, T2)),
            OTHER: {"title": "convoi d'une autre Spec", "status": "open", "issue_type": "convoy",
                    "metadata": {"gc.spec_id": "fx-spec-2"}, "tracks": ["fx-o1"]},
            "fx-o1": ticket("fx-o1"),
            PLAIN: {"title": "convoi sans marque", "status": "open", "issue_type": "convoy",
                    "metadata": {"gc.spec_id": "fx-spec-3"}, "tracks": ["fx-p1"]},
            "fx-p1": ticket("fx-p1"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": list(sessions)}))
        for convoy in (CONVOY, OTHER):
            self.run_ok(STATE, "mark", convoy)
        self.write_log.write_text("")

    def tracker_state(self):
        return json.loads(self.tracker.read_text())

    def bead(self, bead_id):
        return self.tracker_state()["beads"][bead_id]

    def edit(self, bead_id=None, status=None, sessions=None, **fields):
        state = self.tracker_state()
        if bead_id is not None:
            bead = state["beads"][bead_id]
            if status is not None:
                bead["status"] = status
            bead.update(fields)
        if sessions is not None:
            state["sessions"] = list(sessions)
        self.tracker.write_text(json.dumps(state))

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=env or self.env, text=True, capture_output=True)

    def run_ok(self, tool, *args):
        proc = self.run_cmd(tool, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def advance(self, *args, expect=0, env=None):
        proc = self.run_cmd(TOOL, *args, env=env)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def slung(self):
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [entry[2] for entry in lines if entry[0] == "sling"]

    def started(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy)["started"]

    def close_through_gate(self, ticket_id, convoy=CONVOY):
        """What the trial does in place of the flow's own ticket end (not in T04)."""
        self.run_ok(STATE, "record-gate", convoy, ticket_id, "--gate", "ticket_end", "--commit", COMMIT)
        self.edit(ticket_id, status="closed")

    def assert_started_through_door(self, ticket_id):
        metadata = self.bead(ticket_id)["metadata"]
        self.assertEqual("dispatch-door", metadata.get(DOOR_STAMP), ticket_id)
        self.assertIn(DISPATCH_GATE, metadata, ticket_id)

    def assert_not_started(self, ticket_id):
        metadata = self.bead(ticket_id)["metadata"]
        self.assertNotIn(DOOR_STAMP, metadata, ticket_id)
        self.assertNotIn(DISPATCH_GATE, metadata, ticket_id)
        self.assertNotIn(ticket_id, self.slung())

    # --- ready frontier, in dependency order ---------------------------------

    def test_only_tickets_whose_blockers_are_all_closed_start_and_carry_the_door_mark(self):
        answer = self.advance(CONVOY)

        self.assertEqual([T1, T2], self.started(answer))
        self.assertEqual([T1, T2], self.slung())
        self.assert_started_through_door(T1)
        self.assert_started_through_door(T2)
        self.assert_not_started(T3)

    def test_a_ticket_with_one_blocker_still_open_does_not_start(self):
        self.advance(CONVOY)
        self.close_through_gate(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T3)

    def test_the_blocked_ticket_starts_once_its_blockers_are_closed(self):
        self.advance(CONVOY)
        self.close_through_gate(T1)
        self.close_through_gate(T2)

        answer = self.advance(CONVOY)

        self.assertEqual([T3], self.started(answer))
        self.assert_started_through_door(T3)
        self.assertEqual([T1, T2, T3], self.slung())

    def test_the_door_dispatches_with_the_rig_and_formula_of_the_settings(self):
        self.advance(CONVOY)

        log = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        self.assertIn(["sling", "fx-worker", T1, "fx-start"], log)
        self.assertEqual("fx-rig", self.bead(T1)["metadata"]["gc.dispatch_rig"])

    # --- ceiling N ------------------------------------------------------------

    def test_never_more_than_n_tickets_started_at_once(self):
        self.settings(ceiling=1)

        answer = self.advance(CONVOY)

        self.assertEqual([T1], self.started(answer))
        self.assert_not_started(T2)
        self.assertEqual(1, answer["ceiling"])

    def test_a_started_ticket_not_yet_picked_by_a_session_holds_its_place(self):
        self.settings(ceiling=1)
        self.advance(CONVOY)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T2)
        self.assertEqual(1, answer["occupied"])

    def test_the_place_is_freed_when_the_started_ticket_is_closed(self):
        self.settings(ceiling=1)
        self.advance(CONVOY)
        self.close_through_gate(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([T2], self.started(answer))

    def test_a_reviewer_session_counts_in_the_ceiling(self):
        self.settings(ceiling=2)
        self.edit(sessions=[session("delivery-reviewer")])

        answer = self.advance(CONVOY)

        self.assertEqual([T1], self.started(answer))
        self.assert_not_started(T2)
        self.assertEqual(1, answer["sessions"]["reviewer"])

    def test_an_evaluator_session_counts_in_the_ceiling(self):
        self.settings(ceiling=2)
        self.edit(sessions=[session("delivery-evaluator")])

        answer = self.advance(CONVOY)

        self.assertEqual([T1], self.started(answer))
        self.assert_not_started(T2)
        self.assertEqual(1, answer["sessions"]["evaluator"])

    def test_reviewer_and_evaluator_sessions_alone_can_fill_the_ceiling(self):
        self.settings(ceiling=2)
        self.edit(sessions=[session("delivery-reviewer"), session("delivery-evaluator")])

        answer = self.advance(CONVOY)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T1)
        self.assertEqual([], self.slung())

    def test_an_author_session_on_a_ticket_in_progress_counts_once(self):
        self.settings(ceiling=1)
        self.advance(CONVOY)
        self.settings(ceiling=2)
        self.edit(T1, status="in_progress", sessions=[session("delivery-author")])

        answer = self.advance(CONVOY)

        self.assertEqual(1, answer["occupied"])
        self.assertEqual([T2], self.started(answer))

    def test_sessions_of_other_agents_and_closed_sessions_do_not_count(self):
        self.settings(ceiling=1)
        self.edit(sessions=[session("mayor"), session("factory-worker"),
                            {**session("delivery-reviewer"), "state": "closed", "closed": True}])

        answer = self.advance(CONVOY)

        self.assertEqual([T1], self.started(answer))

    def test_the_ceiling_is_shared_between_specs(self):
        self.settings(ceiling=2)
        self.advance(CONVOY)

        answer = self.advance(OTHER)

        self.assertEqual([], self.started(answer, OTHER))
        self.assert_not_started("fx-o1")
        self.assertEqual(2, answer["occupied"])

    def test_one_pass_over_every_marked_convoy_stays_under_the_ceiling(self):
        self.settings(ceiling=2)

        answer = self.advance("--all")

        self.assertEqual(2, sum(len(c["started"]) for c in answer["convoys"]))
        self.assertEqual(2, len(self.slung()))
        self.assertEqual({CONVOY, OTHER}, {c["id"] for c in answer["convoys"]})

    # --- opt-in: the mark ------------------------------------------------------

    def test_an_unmarked_convoy_starts_nothing_and_writes_nothing(self):
        before = self.tracker.read_text()

        proc = self.run_cmd(TOOL, PLAIN)

        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_a_pass_over_every_marked_convoy_leaves_the_unmarked_one_alone(self):
        before = self.bead("fx-p1")

        answer = self.advance("--all")

        self.assertNotIn(PLAIN, {c["id"] for c in answer["convoys"]})
        self.assertEqual(before, self.bead("fx-p1"))
        self.assertNotIn("fx-p1", self.slung())

    # --- idempotence -----------------------------------------------------------

    def test_a_second_pass_on_the_same_state_starts_nothing_more(self):
        first = self.advance(CONVOY)
        after_first = self.tracker.read_text()

        second = self.advance(CONVOY)

        self.assertEqual([T1, T2], self.started(first))
        self.assertEqual([], self.started(second))
        self.assertEqual([T1, T2], self.slung())
        self.assertEqual(after_first, self.tracker.read_text())

    # --- refusals: nothing is started ------------------------------------------

    def test_a_convoy_in_a_state_without_rule_starts_nothing(self):
        self.edit(T1, status="in_progress")  # started outside the dispatch door
        before = self.tracker.read_text()

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assertIn("état sans règle", json.dumps(answer, ensure_ascii=False))
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_no_start_formula_in_the_settings_refuses_and_writes_nothing(self):
        self.settings(formula=None)
        before = self.tracker.read_text()

        proc = self.run_cmd(TOOL, CONVOY)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("formule", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_a_ceiling_that_is_not_a_positive_integer_refuses_and_writes_nothing(self):
        for bad in (0, -1, "2", None, 1.5, True):
            with self.subTest(ceiling=bad):
                self.settings(ceiling=bad)
                before = self.tracker.read_text()

                proc = self.run_cmd(TOOL, CONVOY)

                self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("max_sessions", json.loads(proc.stdout)["error"])
                self.assertEqual(before, self.tracker.read_text())
                self.assertEqual("", self.write_log.read_text())

    def test_a_ticket_that_names_no_single_known_rig_is_not_started(self):
        self.edit(T1, description="## Target rigs\n\nfx-rig, fx-elsewhere\n")

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assert_not_started(T1)
        self.assertEqual([T1], [r["id"] for r in answer["convoys"][0]["refused"]])
        self.assertEqual([T2], self.started(answer))

    def test_a_refusal_of_the_door_is_reported_and_the_ticket_is_not_marked_started(self):
        env = {**self.env, "CONVOY_STATE_FAKE_SLING_FAIL": T1}

        answer = self.advance(CONVOY, expect=EXIT_REFUSED, env=env)

        refused = answer["convoys"][0]["refused"]
        self.assertEqual([T1], [r["id"] for r in refused])
        self.assertIn("gc sling failed", refused[0]["reason"])
        self.assertNotIn(DISPATCH_GATE, self.bead(T1)["metadata"])
        self.assertEqual([T2], self.started(answer))

    def test_a_ticket_that_is_not_open_does_not_start(self):
        self.edit(T1, status="blocked")

        answer = self.advance(CONVOY)

        self.assertEqual([T2], self.started(answer))
        self.assert_not_started(T1)

    def test_an_unknown_convoy_refuses(self):
        proc = self.run_cmd(TOOL, "fx-absent")

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", self.write_log.read_text())

    # --- the order's cheap check -------------------------------------------------

    def test_check_only_passes_when_a_marked_convoy_is_open_and_writes_nothing(self):
        before = self.tracker.read_text()

        proc = self.run_cmd(TOOL, "--check-only")

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_check_only_fails_when_no_marked_convoy_is_open(self):
        self.edit(CONVOY, status="closed")
        self.edit(OTHER, status="closed")

        proc = self.run_cmd(TOOL, "--check-only")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)

    # --- the dispatch door records the start -------------------------------------

    def test_the_door_refuses_a_ticket_that_is_not_in_the_named_convoy(self):
        before = self.tracker.read_text()

        proc = self.run_cmd(DOOR, "fx-o1", "--rig", "fx-rig", "--formula", "fx-start", "--convoy", CONVOY)

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual([], self.slung())

    def test_the_door_refuses_to_record_a_start_on_an_unmarked_convoy(self):
        before = self.tracker.read_text()

        proc = self.run_cmd(DOOR, "fx-p1", "--rig", "fx-rig", "--formula", "fx-start", "--convoy", PLAIN)

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("pas un convoi du nouveau flux", proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual([], self.slung())

    def test_the_door_without_a_convoy_dispatches_as_before_and_records_no_gate(self):
        self.run_ok(DOOR, "fx-p1", "--rig", "fx-rig", "--formula", "fx-start")

        metadata = self.bead("fx-p1")["metadata"]
        self.assertEqual("dispatch-door", metadata[DOOR_STAMP])
        self.assertFalse([key for key in metadata if key.startswith("gc.flow.")])

    def test_state_list_names_the_open_marked_convoys_only(self):
        self.edit(OTHER, status="closed")

        answer = json.loads(self.run_ok(STATE, "list").stdout)

        self.assertEqual([CONVOY], answer["convoys"])


if __name__ == "__main__":
    unittest.main()
