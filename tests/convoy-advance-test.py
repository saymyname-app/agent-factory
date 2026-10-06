#!/usr/bin/env python3
"""bin/convoy-advance on a fake tracker state (T04, af-gfyj6k; Spec af-wf4w5r
§0 rule 3, §4, user story 82; Testing Decisions seam 2).

The advance command starts the ready tickets of a convoy that carries the
new-flow mark, through the real bin/dispatch-door, under the factory-wide
ceiling N. One test per pass and per refusal; a refusal re-reads the tracker
to prove nothing was written. Only command lines are exercised: the tracker
is tests/fixtures/convoy-state/gc, the Factory root is a synthetic one.

T34 (af-ckwina; §0 rules 3 and 5, user stories 83 and 84): a state without
rule stops the convoy and raises one factory incident through the real
bin/escalation-door, read back from its list; the pass resumes by itself
once the state is valid again; the dispatch door refuses a ticket of a
marked convoy to an agent session."""

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
ESCALATION = ROOT / "bin" / "escalation-door"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
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
INCIDENT = "Incident d'usine"
STARTED_OUTSIDE = "démarré hors porte"
CLOSED_OUTSIDE = "fermé hors porte"
# What Gas City exports into every agent session, the Mayor's included.
SESSION_IDENTITY = ("GC_AGENT", "GC_ALIAS", "GC_SESSION_NAME", "GC_SESSION_ID", "GC_TEMPLATE")
MAYOR_SESSION = {"GC_AGENT": "mayor", "GC_ALIAS": "mayor", "GC_SESSION_NAME": "mayor",
                 "GC_SESSION_ID": "fx-mayor", "GC_TEMPLATE": "mayor"}


def ticket(ticket_id, blocks=(), rig="fx-rig"):
    # A ticket is marked with its kind (T05); a prefactoring needs no demonstration line.
    return {"title": f"ticket {ticket_id}", "status": "open", "issue_type": "task",
            "description": f"## What to build\n\nessai\n\n## Target rigs\n\n{rig}\n\n## Autonomous execution contract\n\n- none",
            "metadata": {"gc.ticket_kind": "prefactoring"}, "blocks": list(blocks)}


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
        proposal_door = self.tmp / "proposal-door"
        proposal_door.write_text("#!/bin/sh\necho 0\n")
        proposal_door.chmod(0o755)
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
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(proposal_door),
            "GC_ESCALATION_RECIPIENT": "human",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        # The tests run the advance command as the controller's order does:
        # outside any agent session, even when an agent runs the suite.
        for name in ("CONVOY_STATE_FAKE_SLING_FAIL", "CONVOY_STATE_FAKE_MAIL_FAIL", *SESSION_IDENTITY):
            self.env.pop(name, None)
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

    def log(self, kind):
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [entry for entry in lines if entry[0] == kind]

    def escalation_list(self):
        """The lines of bin/escalation-door list that carry a factory incident."""
        out = self.run_ok(ESCALATION, "list").stdout
        return [line.strip() for line in out.splitlines() if INCIDENT in line]

    def tickets_snapshot(self, *ticket_ids):
        return {ticket_id: self.bead(ticket_id) for ticket_id in ticket_ids or (T1, T2, T3)}

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

    def test_a_parked_ticket_is_not_started_and_the_unrelated_ones_are(self):
        # T11: a Ticket Exit parked T1, and T3 behind it; T2 waits for neither.
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", "Accès à l'horloge")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([T2], self.started(answer))
        self.assertEqual([T2], self.slung())
        waiting = {entry["id"]: entry["reason"] for entry in answer["convoys"][0]["waiting"]}
        self.assertEqual({T1, T3}, set(waiting))
        for reason in waiting.values():
            self.assertIn("parqué (operator_request", reason)

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
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assertIn("état sans règle", json.dumps(answer, ensure_ascii=False))
        self.assertEqual(before, self.tickets_snapshot())
        self.assertEqual([], self.slung())

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

    # --- état sans règle: the convoy stops, one factory incident (T34) ----------

    def test_a_ticket_started_outside_the_dispatch_door_stops_the_convoy_and_raises_a_factory_incident(self):
        self.edit(T1, status="in_progress")

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T2)
        self.assertEqual([], self.slung())
        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(T1, incidents[0])
        self.assertIn(STARTED_OUTSIDE, incidents[0])

    def test_a_ticket_closed_outside_a_gate_stops_the_convoy_and_raises_a_factory_incident(self):
        self.edit(T1, status="closed")  # closed by hand: no ticket_end, no withdrawn record

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T2)
        self.assert_not_started(T3)
        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(T1, incidents[0])
        self.assertIn(CLOSED_OUTSIDE, incidents[0])

    def test_an_incoherent_counter_stops_the_convoy_and_raises_a_factory_incident(self):
        state = self.tracker_state()
        state["beads"][T2]["metadata"]["gc.flow.counter.resumes"] = -1
        self.tracker.write_text(json.dumps(state))

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T1)
        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(T2, incidents[0])

    def test_the_incident_reaches_the_operator_once(self):
        self.edit(T1, status="closed")

        self.advance(CONVOY, expect=EXIT_UNRULED)

        mails = self.log("mail")
        self.assertEqual(1, len(mails), mails)
        self.assertEqual("human", mails[0][1])

    def test_the_same_anomaly_seen_on_several_passes_raises_one_incident(self):
        self.edit(T1, status="closed")

        for _ in range(3):
            answer = self.advance(CONVOY, expect=EXIT_UNRULED)
            self.assertEqual([], self.started(answer))

        self.assertEqual(1, len(self.escalation_list()))
        self.assertEqual(1, len(self.log("mail")))
        self.assertEqual(1, len(self.log("create")))
        self.assertEqual([], self.slung())

    def test_a_second_anomaly_updates_the_one_incident_line(self):
        self.edit(T1, status="closed")
        self.advance(CONVOY, expect=EXIT_UNRULED)
        self.edit(T2, status="in_progress")

        self.advance(CONVOY, expect=EXIT_UNRULED)

        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertEqual(1, len(self.log("create")))
        self.assertEqual(2, len(self.log("mail")))

    def test_the_tickets_of_a_stopped_convoy_are_not_written(self):
        self.edit(T1, status="closed")
        before = self.tickets_snapshot()

        self.advance(CONVOY, expect=EXIT_UNRULED)
        self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual(before, self.tickets_snapshot())

    def test_another_marked_convoy_keeps_advancing_while_one_is_stopped(self):
        self.edit(T1, status="closed")

        answer = self.advance("--all", expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assertEqual(["fx-o1"], self.started(answer, OTHER))
        self.assertEqual(["fx-o1"], self.slung())

    def test_the_convoy_resumes_by_itself_once_the_state_is_valid_again(self):
        self.edit(T1, status="closed")
        self.advance(CONVOY, expect=EXIT_UNRULED)
        self.assertEqual(1, len(self.escalation_list()))
        self.edit(T1, status="open")  # factory maintenance restored a valid state

        answer = self.advance(CONVOY)

        self.assertEqual([T1, T2], self.started(answer))
        self.assert_started_through_door(T1)
        self.assertEqual([], self.escalation_list())

    def test_a_resumed_convoy_that_stops_again_raises_a_new_incident(self):
        self.edit(T1, status="closed")
        self.advance(CONVOY, expect=EXIT_UNRULED)
        self.edit(T1, status="open")
        self.advance(CONVOY)
        self.edit(T3, status="closed")

        self.advance(CONVOY, expect=EXIT_UNRULED)

        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(T3, incidents[0])

    def test_the_order_run_does_not_fail_on_a_stopped_convoy_whose_incident_is_raised(self):
        self.edit(T1, status="closed")

        first = self.advance("--all", "--stopped-ok")
        second = self.advance("--all", "--stopped-ok")

        for answer in (first, second):
            self.assertEqual([], self.started(answer))
            self.assertIn("état sans règle", json.dumps(answer, ensure_ascii=False))
        self.assertEqual(1, len(self.escalation_list()))

    def test_an_incident_that_could_not_be_raised_fails_the_pass_and_is_raised_by_the_next(self):
        self.edit(T1, status="closed")
        env = {**self.env, "CONVOY_STATE_FAKE_MAIL_FAIL": "1"}

        proc = self.run_cmd(TOOL, "--all", "--stopped-ok", env=env)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([], [t for t in self.slung() if t in (T1, T2, T3)])
        self.assertEqual([], self.log("mail"))

        self.advance("--all", "--stopped-ok")

        self.assertEqual(1, len(self.escalation_list()))
        self.assertEqual(1, len(self.log("mail")))
        self.assertEqual(1, len(self.log("create")))

    # --- the dispatch door and the Mayor (T34) -----------------------------------

    def test_the_door_refuses_the_mayor_on_a_ticket_of_a_marked_convoy(self):
        before = self.tracker.read_text()
        env = {**self.env, **MAYOR_SESSION}

        proc = self.run_cmd(DOOR, T1, "--rig", "fx-rig", "--formula", "fx-start", env=env)

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("convoy-advance", proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_the_door_refuses_the_mayor_even_when_it_names_the_convoy(self):
        before = self.tracker.read_text()
        env = {**self.env, **MAYOR_SESSION}

        proc = self.run_cmd(DOOR, T1, "--rig", "fx-rig", "--formula", "fx-start", "--convoy", CONVOY, env=env)

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("mayor", proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_the_door_refuses_a_marked_ticket_dispatched_without_its_convoy(self):
        before = self.tracker.read_text()

        proc = self.run_cmd(DOOR, T1, "--rig", "fx-rig", "--formula", "fx-start")

        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_text())
        self.assertEqual("", self.write_log.read_text())

    def test_the_door_lets_the_advance_command_start_the_ticket(self):
        answer = self.advance(CONVOY)

        self.assertEqual([T1, T2], self.started(answer))
        self.assert_started_through_door(T1)

    def test_the_advance_command_run_from_an_agent_session_starts_nothing(self):
        before = self.tickets_snapshot()
        env = {**self.env, **MAYOR_SESSION}

        answer = self.advance(CONVOY, expect=EXIT_REFUSED, env=env)

        self.assertEqual([], self.started(answer))
        self.assertEqual({T1, T2}, {r["id"] for r in answer["convoys"][0]["refused"]})
        self.assertEqual(before, self.tickets_snapshot())
        self.assertEqual([], self.slung())

    def test_the_door_still_dispatches_an_unmarked_ticket_for_the_mayor(self):
        env = {**self.env, **MAYOR_SESSION}

        proc = self.run_cmd(DOOR, "fx-p1", "--rig", "fx-rig", "--formula", "fx-start", env=env)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(["fx-p1"], self.slung())

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

    # --- finished tickets are merged by the pass (T18) -------------------------

    INTEGRATION = "integration/fx-spec"

    def git(self, *args):
        proc = subprocess.run(
            ("git", "-C", str(self.root), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def integrated(self, regression="true"):
        """The repository and the profile of the convoy's project, and the
        integration branch of its Spec opened as the publication door does."""
        self.env["EVIDENCE_STORE_DIR"] = str(self.tmp / "store")
        self.env["SPEC_INTEGRATION_LOCK_DIR"] = str(self.tmp / "locks")
        self.env["SPEC_INTEGRATION_WORK_DIR"] = str(self.tmp / "work")
        descriptor = json.loads((ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json").read_text())
        descriptor["rigs"] = ["fx-rig"]
        descriptor["launch"]["regression_command"] = regression
        (self.root / "config" / "project-descriptors").mkdir()
        (self.root / "config" / "project-descriptors" / "fx.json").write_text(json.dumps(descriptor))
        (self.root / ".gitignore").write_text("config/\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.run_ok(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.root, "--protected", "main")
        return self.git("rev-parse", "main")

    def finished(self, ticket_id):
        """A ticket started by the pass, with one commit on its branch, that
        its author has finished; returns that commit."""
        branch = f"ticket/{ticket_id}"
        self.git("checkout", "-q", "-b", branch, self.INTEGRATION)
        (self.root / f"{ticket_id}.md").write_text("le travail du ticket\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"travail de {ticket_id}")
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", "main")
        self.run_ok(STATE, "set-branch", CONVOY, ticket_id, "--branch", branch)
        self.edit(ticket_id, status="in_progress")
        self.run_ok(STATE, "add-evidence", CONVOY, ticket_id, "--piece", "handoff_records",
                    "--digest", "sha256:" + "ab" * 32, "--commit", tip)
        handoff = self.tmp / f"handoff-{ticket_id}.json"
        handoff.write_text(json.dumps({
            "sections": dict.fromkeys(("done", "deviations", "not_done", "out_of_ticket"), "aucun"),
            "partial": False, "commit": tip, "records": {}}))
        self.run_ok(STATE, "set-handoff", CONVOY, ticket_id, "--file", handoff)
        self.run_ok(STATE, "set-exit", CONVOY, ticket_id, "--exit", "finished")
        return tip

    def integration_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("integration")

    def shown(self, ticket_id):
        proc = self.run_ok(STATE, "show", CONVOY, "--repo", self.root)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket_id)

    def test_a_pass_merges_one_finished_ticket_into_the_integration_branch(self):
        base = self.integrated()
        self.advance(CONVOY)
        tip1, tip2 = self.finished(T1), self.finished(T2)

        answer = self.advance(CONVOY)
        merged = self.integration_of(answer)["merged"]
        self.assertEqual([T1], [entry["id"] for entry in merged])
        self.assertEqual(merged[0]["commit"], self.git("rev-parse", self.INTEGRATION))
        self.assertEqual(f"{base} {tip1}", self.git("rev-list", "--parents", "-n", "1", merged[0]["commit"]).split(" ", 1)[1])
        self.assertEqual("merged", self.shown(T1)["merge"]["outcome"])
        self.assertEqual(merged[0]["commit"], self.shown(T1)["evidence"]["merged_tests"]["commit"])
        self.assertIsNone(self.shown(T2)["merge"])

        # One ticket per pass: the next pass merges the second on the first.
        second = self.integration_of(self.advance(CONVOY))["merged"]
        self.assertEqual([T2], [entry["id"] for entry in second])
        self.assertEqual(f"{merged[0]['commit']} {tip2}",
                         self.git("rev-list", "--parents", "-n", "1", second[0]["commit"]).split(" ", 1)[1])
        self.assertEqual(base, self.git("rev-parse", "main"))
        self.assertIsNone(self.integration_of(self.advance(CONVOY)))

    def test_a_pass_with_no_finished_ticket_runs_no_merge(self):
        self.integrated()
        # No profile at all: a merge pass would refuse.
        shutil.rmtree(self.root / "config" / "project-descriptors")

        answer = self.advance(CONVOY)
        self.assertEqual([T1, T2], self.started(answer))
        self.assertIsNone(self.integration_of(answer))

    def test_a_ticket_returned_by_red_tests_is_reported_and_the_pass_is_not_a_failure(self):
        base = self.integrated(regression="false")
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY)
        returned = self.integration_of(answer)["returned"]
        self.assertEqual([(T1, "red")], [(entry["id"], entry["cause"]) for entry in returned])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        self.assertTrue(answer["ok"])

    def test_a_merge_pass_that_cannot_run_fails_the_pass_and_says_why(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        shutil.rmtree(self.root / "config" / "project-descriptors")
        before = self.git("rev-parse", self.INTEGRATION)

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)
        self.assertFalse(answer["ok"])
        self.assertIn("profil", self.integration_of(answer)["error"])
        self.assertEqual(before, self.git("rev-parse", self.INTEGRATION))
        self.assertIsNone(self.shown(T1)["merge"])

    def test_a_stopped_convoy_merges_nothing(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        self.edit(T2, status="closed")
        before = self.git("rev-parse", self.INTEGRATION)

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)
        self.assertIsNone(self.integration_of(answer))
        self.assertEqual(before, self.git("rev-parse", self.INTEGRATION))
        self.assertIsNone(self.bead(T1)["metadata"].get("gc.flow.merge"))

    # --- review of the criterion tests left without result (T13) ---------------

    REVIEWED = "fx-review"
    R1 = "fx-r1"
    RED = "2" * 40

    def review_open(self, launches=1):
        """A marked convoy whose one slice, started through the door, has
        its criterion tests proven red and under review: `launches` reviewer
        sessions were sent and none answered. No author session is alive."""
        state = self.tracker_state()
        slice_ = ticket(self.R1)
        slice_["metadata"] = {"gc.ticket_kind": "vertical_slice"}
        state["beads"][self.REVIEWED] = {"title": "convoi en relecture", "status": "open", "issue_type": "convoy",
                                         "metadata": {"gc.spec_id": "fx-spec-4"}, "tracks": [self.R1]}
        state["beads"][self.R1] = slice_
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "mark", self.REVIEWED, "--demonstration-line", f"{self.R1}=La page affiche 3",
                    "--user-stories", f"{self.R1}=1")
        self.run_ok(STATE, "record-gate", self.REVIEWED, self.R1, "--gate", "dispatch")
        self.edit(self.R1, status="in_progress")
        self.run_ok(STATE, "set-tdd", self.REVIEWED, self.R1, "--step", "red", "--commit", self.RED, "--base", COMMIT)
        request = self.tmp / "request.json"
        request.write_text(json.dumps({"files": {"tests/test_count.py": "sha256:" + "c1" * 32},
                                       "criteria": {"1": ["tests/test_count.py::CountTest.test_count"]}}))
        self.run_ok(STATE, "open-test-review", self.REVIEWED, self.R1, "--commit", self.RED, "--file", request)
        for number in range(launches):
            self.run_ok(STATE, "launch-test-review", self.REVIEWED, self.R1, "--bead", f"fx-old{number + 1}")
        # The reviewer never answers, and a launch is over at once.
        (self.tmp / "plan.json").write_text(json.dumps(["silent"]))
        self.env.update({
            "TEST_REVIEW_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "test-review" / "reviewer"),
            "TEST_REVIEW_FAKE_LOG": str(self.tmp / "review-door.log"),
            "TEST_REVIEW_FAKE_PLAN": str(self.tmp / "plan.json"),
            "TEST_REVIEW_FAKE_REPO": str(self.tmp),
        })
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        settings["test_review"] = {"formula": "mol-test-review", "role": "reviewer", "rig": "fx-rig", "timeout_seconds": 0}
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))
        self.write_log.write_text("")

    def review_of(self, answer):
        return next(c for c in answer["convoys"] if c["id"] == self.REVIEWED).get("test_review")

    def review_launches(self):
        log = self.tmp / "review-door.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_a_pass_launches_once_more_a_test_review_left_without_result(self):
        self.review_open(launches=1)

        answer = self.advance(self.REVIEWED)

        self.assertEqual([self.R1], [entry["ticket"] for entry in self.review_of(answer)["relaunched"]])
        (call,) = self.review_launches()
        self.assertEqual(["--rig", "fx-rig", "--formula", "mol-test-review", "--role", "reviewer"], call[1:])
        self.assertNotIn("gc.flow.stop", self.bead(self.R1)["metadata"])

    def test_a_pass_stops_a_ticket_whose_test_review_gave_no_result_twice_and_raises_it_once(self):
        self.review_open(launches=2)

        first = self.advance(self.REVIEWED)
        second = self.advance(self.REVIEWED)

        self.assertEqual([self.R1], [entry["ticket"] for entry in self.review_of(first)["stopped"]])
        self.assertIsNone(self.review_of(second))
        self.assertEqual([], self.review_launches())
        stop = json.loads(self.bead(self.R1)["metadata"]["gc.flow.stop"])
        self.assertEqual("test_review_no_result", stop["reason"])
        needs = [line for line in self.run_ok(ESCALATION, "list").stdout.splitlines() if self.R1 in line]
        self.assertEqual(1, len(needs), needs)
        self.assertEqual(1, len(self.log("mail")))

    def test_a_pass_runs_no_test_review_settlement_when_none_is_due(self):
        answer = self.advance(CONVOY)

        self.assertNotIn("test_review", next(c for c in answer["convoys"] if c["id"] == CONVOY))


if __name__ == "__main__":
    unittest.main()
