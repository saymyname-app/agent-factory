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
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import ticket_proofs  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "convoy-advance"
STATE = ROOT / "bin" / "convoy-state"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
DOOR = ROOT / "bin" / "dispatch-door"
ESCALATION = ROOT / "bin" / "escalation-door"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"

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
CONVOY_CLOSED_OUTSIDE = "fermé hors commande"
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
        """What stands for the flow's own ticket end (T19, bin/ticket-end):
        the record of the gate, written with the closing."""
        self.run_ok(STATE, "close-ticket", convoy, ticket_id, "--commit", COMMIT, "--file", GATE_REPORT)

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

    def test_a_marked_convoy_closed_outside_acceptance_or_abandon_is_raised_on_the_escalation_list(self):
        self.edit(CONVOY, status="closed", close_reason="convoy autoclose: all children closed")

        answer = self.advance("--all", expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assertEqual(["fx-o1"], self.slung())
        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(CONVOY, incidents[0])
        self.assertIn(CONVOY_CLOSED_OUTSIDE, incidents[0])

    def test_a_convoy_closed_outside_is_raised_once_and_withdrawn_once_reopened(self):
        self.edit(CONVOY, status="closed")
        self.advance("--all", "--stopped-ok")
        self.advance("--all", "--stopped-ok")
        self.assertEqual(1, len(self.escalation_list()))
        self.assertEqual(1, len(self.log("mail")))
        self.edit(CONVOY, status="open")  # factory maintenance restored a valid state

        answer = self.advance("--all")

        self.assertEqual([T1, T2], self.started(answer))
        self.assertEqual([], self.escalation_list())

    def test_an_unmarked_convoy_closed_like_today_raises_nothing(self):
        self.edit(PLAIN, status="closed", close_reason="convoy autoclose: all children closed")
        before = self.bead(PLAIN)

        answer = self.advance("--all")

        self.assertNotIn(PLAIN, [convoy["id"] for convoy in answer["convoys"]])
        self.assertEqual([], self.escalation_list())
        self.assertEqual(before, self.bead(PLAIN))

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

    def test_check_only_fails_when_no_marked_convoy_exists(self):
        state = self.tracker_state()
        for convoy in (CONVOY, OTHER):
            del state["beads"][convoy]
        self.tracker.write_text(json.dumps(state))

        proc = self.run_cmd(TOOL, "--check-only")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)

    def test_check_only_passes_when_the_only_marked_convoys_were_closed_outside_acceptance_or_abandon(self):
        """Otherwise the order would never run the pass that signals them."""
        self.edit(CONVOY, status="closed")
        self.edit(OTHER, status="closed")
        before = self.tracker.read_text()

        proc = self.run_cmd(TOOL, "--check-only")

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.tracker.read_text())

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
        # The product the profile launches: what an evaluation is made on.
        shutil.copytree(ROOT / FIXTURE, self.root / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.run_ok(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.root, "--protected", "main")
        self.code_reviewed("favorable")
        self.evaluated()
        self.outcome_evaluated()
        return self.git("rev-parse", "main")

    def evaluated(self, *plan, timeout_seconds=3600):
        """The Ticket Evaluation of the finished tickets (T15): its settings,
        where the launch records of the products are kept, and what the
        Evaluator session does at each launch
        (tests/fixtures/ticket-evaluation/evaluator), the last one repeated."""
        (self.tmp / "evaluation-plan.json").write_text(json.dumps(list(plan or ({},))))
        self.env.update({
            "TICKET_EVALUATION_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "ticket-evaluation" / "evaluator"),
            "TICKET_EVALUATION_STATE_DIR": str(self.tmp / "launches"),
            "TICKET_EVALUATION_FAKE_LOG": str(self.tmp / "evaluation-door.log"),
            "TICKET_EVALUATION_FAKE_PLAN": str(self.tmp / "evaluation-plan.json"),
        })
        self.addCleanup(self.stop_every_product)
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        settings["evaluation"] = {"formula": "mol-ticket-evaluation", "role": "evaluator", "rig": "fx-rig",
                                  "timeout_seconds": timeout_seconds, "start_timeout_seconds": 15}
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

    def outcome_evaluated(self, *plan, timeout_seconds=3600):
        """The Outcome Evaluation of the assembled product (T24): the Spec
        of the convoy with its numbered user stories, its settings, and what
        the Evaluator session of the end does at each launch
        (tests/fixtures/outcome-evaluation/evaluator), the last one repeated."""
        state = self.tracker_state()
        state["beads"].setdefault("fx-spec", {
            "title": "Spec de la fixture", "status": "open", "issue_type": "task",
            "description": (ROOT / FIXTURE / "spec.md").read_text(), "metadata": {}})
        self.tracker.write_text(json.dumps(state))
        (self.tmp / "outcome-plan.json").write_text(json.dumps(list(plan or ({},))))
        self.env.update({
            "OUTCOME_EVALUATION_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "outcome-evaluation" / "evaluator"),
            "OUTCOME_EVALUATION_STATE_DIR": str(self.tmp / "launches" / "outcome"),
            "OUTCOME_EVALUATION_FAKE_LOG": str(self.tmp / "outcome-door.log"),
            "OUTCOME_EVALUATION_FAKE_PLAN": str(self.tmp / "outcome-plan.json"),
        })
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        settings["outcome_evaluation"] = {"formula": "mol-outcome-evaluation", "role": "evaluator", "rig": "fx-rig",
                                          "timeout_seconds": timeout_seconds, "start_timeout_seconds": 15}
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

    def stop_every_product(self):
        for record in (self.tmp / "launches").rglob("*.json"):
            subprocess.run((str(ROOT / "bin" / "project-launch"), "stop", "--state-file", str(record)),
                           env=self.env, capture_output=True)

    def evaluation_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("evaluation")

    def evaluation_launches(self):
        log = self.tmp / "evaluation-door.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def code_reviewed(self, *plan, timeout_seconds=3600):
        """The code review of the finished tickets (T14): its settings, the
        Spec the convoy delivers, and what the reviewer session does at each
        launch (tests/fixtures/code-review/reviewer), the last one repeated."""
        state = self.tracker_state()
        state["beads"].setdefault("fx-spec", {"title": "Spec d'essai", "status": "open", "issue_type": "task",
                                              "description": "## User Stories\n\n1. As Benjamin, I want un essai."})
        self.tracker.write_text(json.dumps(state))
        (self.tmp / "code-review-plan.json").write_text(json.dumps(list(plan)))
        self.env.update({
            "CODE_REVIEW_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "code-review" / "reviewer"),
            "CODE_REVIEW_FAKE_LOG": str(self.tmp / "code-review-door.log"),
            "CODE_REVIEW_FAKE_PLAN": str(self.tmp / "code-review-plan.json"),
            "CODE_REVIEW_FAKE_REPO": str(self.root),
        })
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        settings["code_review"] = {"formula": "mol-code-review", "role": "reviewer", "rig": "fx-rig",
                                   "timeout_seconds": timeout_seconds}
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

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
        # The regression of the prefactoring proven at the tip (bin/tdd-step),
        # the sealed records, the Handoff and the exit (bin/ticket-exit).
        ticket_proofs.finish(self.env, self.root, CONVOY, ticket_id, tip, self.git("rev-parse", "main"), branch,
                             sections=dict.fromkeys(("done", "deviations", "not_done", "out_of_ticket"), "aucun"))
        return tip

    def code_review_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("code_review")

    def code_review_launches(self):
        log = self.tmp / "code-review-door.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

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

    # --- a merged ticket is closed by the ticket-end gate, and by nothing else (T19) ---

    def ticket_end_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("ticket_end")

    def test_a_pass_closes_the_ticket_it_merged_through_the_ticket_end_gate_with_its_nine_verdicts(self):
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])
        closing = self.ticket_end_of(answer)
        self.assertEqual([(T1, tip, "ticket-end/v1")],
                         [(entry["id"], entry["commit"], entry["version"]) for entry in closing["closed"]])
        shown = self.shown(T1)
        record = shown["gates"]["ticket_end"]
        self.assertEqual(("closed", tip, "ticket-end/v1", [1, 2, 3, 4, 5, 6, 7, 8, 9]),
                         (shown["status"], record["commit"], record["version"],
                          [entry["number"] for entry in record["conditions"]]))
        self.assertEqual({"pass"}, {entry["verdict"] for entry in record["conditions"]})
        self.assertEqual([], self.escalation_list())
        # Nothing is left to settle: the next pass does not call the gate.
        self.assertIsNone(self.ticket_end_of(self.advance(CONVOY)))

    def test_a_merged_ticket_that_misses_a_condition_stays_open_and_the_pass_names_the_condition(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        # Reviewed, evaluated and merged; then a criterion is edited on the
        # ticket before the gate reads it.
        self.run_ok(ROOT / "bin" / "code-review", "settle", CONVOY, "--repo", self.root)
        self.run_ok(ROOT / "bin" / "ticket-evaluation", "settle", CONVOY, "--repo", self.root)
        self.run_ok(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.root, "--profile",
                    self.root / "config" / "project-descriptors" / "fx.json")
        self.assertEqual("merged", self.shown(T1)["merge"]["outcome"])
        self.edit(T1, description=self.bead(T1)["description"] + "\n\n## Acceptance criteria\n\n- [ ] ajouté à la main")

        answer = self.advance(CONVOY)

        closing = self.ticket_end_of(answer)
        self.assertNotIn("closed", closing)
        self.assertEqual([(T1, [1])], [(entry["id"], entry["missing"]) for entry in closing["open"]])
        self.assertIn("condition 1", closing["open"][0]["reason"])
        self.assertTrue(answer["ok"])
        shown = self.shown(T1)
        self.assertEqual("in_progress", shown["status"])
        self.assertNotIn("ticket_end", shown["gates"])
        # Its dependent is not started on a ticket the gate left open.
        self.assert_not_started(T3)

    def test_a_ticket_closed_with_a_gate_record_that_lacks_the_nine_verdicts_stops_the_convoy(self):
        self.edit(T1, status="closed")
        state = self.tracker_state()
        state["beads"][T1]["metadata"]["gc.flow.gate.ticket_end"] = json.dumps({"at": "2026-01-01T00:00:00Z",
                                                                               "commit": COMMIT})
        self.tracker.write_text(json.dumps(state))

        answer = self.advance(CONVOY, expect=EXIT_UNRULED)

        self.assertEqual([], self.started(answer))
        self.assert_not_started(T2)
        incidents = self.escalation_list()
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(T1, incidents[0])

    def test_a_merged_pull_request_and_a_green_ci_close_no_ticket_of_a_marked_convoy(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        # What closes a ticket of the flow before: a merged pull request.
        self.edit(T1, **{"metadata": {**self.bead(T1)["metadata"], "gc.pr_number": 12, "gc.pr_state": "MERGED",
                                      "gc.ci_state": "SUCCESS"}})
        self.code_reviewed("silent")

        answer = self.advance(CONVOY)

        self.assertIsNone(self.ticket_end_of(answer))
        self.assertEqual("in_progress", self.shown(T1)["status"])

    def test_a_pass_measures_the_fidelity_of_an_interface_ticket_before_its_merge_and_the_gate_reads_it(self):
        base = self.integrated()
        self.env.update({
            "EVIDENCE_CAPTURE_BROWSER": str(ROOT / "tests" / "fixtures" / "prototype-fidelity" / "browser"),
            "EVIDENCE_FAKE_BROWSER_LOG": str(self.tmp / "browser.log"),
            "TICKET_END_WORK_DIR": str(self.tmp / "gate-work"),
        })
        # An interface slice: the publication door posed the reference of
        # the Validated Prototype in it, before the convoy was marked.
        state = self.tracker_state()
        for bead_id in (CONVOY, T1, T2, T3):
            metadata = state["beads"][bead_id]["metadata"]
            state["beads"][bead_id]["metadata"] = {k: v for k, v in metadata.items() if not k.startswith("gc.flow.")}
        state["beads"][T1]["metadata"]["gc.ticket_kind"] = "vertical_slice"
        state["beads"][T1]["description"] = (
            "## Acceptance criteria\n\n- [ ] Point d'entrée : GET / — Observable : liste — Faux si : une ligne manque\n\n"
            f"## Validated Prototype\n\n- branche : main\n- commit : {base}\n- chemin : {FIXTURE}/prototype\n"
            "- états : empty, content\n- Prototype Fold : ce ticket\n\n## Target rigs\n\nfx-rig")
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "mark", CONVOY, "--demonstration-line", f"{T1}=La page d'accueil affiche les trois éléments",
                    "--user-stories", f"{T1}=1", "--prototype-fold", T1)
        self.run_ok(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.root, "--protected", "main")
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        result = next(c for c in answer["convoys"] if c["id"] == CONVOY)
        self.assertEqual([(T1, tip, "vert")],
                         [(entry["id"], entry["commit"], entry["result"]) for entry in result["fidelity"]["checked"]], result)
        self.assertEqual([T1], [entry["id"] for entry in result["integration"]["merged"]], result)
        self.assertEqual([T1], [entry["id"] for entry in result["ticket_end"]["closed"]], result)
        shown = self.shown(T1)
        self.assertEqual((tip, "vert"), (shown["fidelity"]["commit"], shown["fidelity"]["state"]))
        fidelity = shown["gates"]["ticket_end"]["conditions"][3]
        self.assertEqual(("fidelity", "pass"), (fidelity["name"], fidelity["verdict"]))
        self.assertIn(tip[:12], fidelity["detail"])

    def test_a_refusal_of_the_ticket_end_gate_is_a_failure_of_the_pass(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)

        # The pass is run from an agent session: no agent closes a ticket.
        answer = self.advance(CONVOY, expect=EXIT_REFUSED, env={**self.env, "GC_SESSION_NAME": "delivery-author-fx"})

        self.assertFalse(answer["ok"])
        self.assertEqual("in_progress", self.shown(T1)["status"])

    # --- the code of a finished ticket is reviewed before its merge (T14) -------

    def test_a_pass_sends_a_finished_ticket_to_the_reviewer_role_and_merges_it_once_reviewed(self):
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "review", tip)], [(entry["ticket"], entry["kind"], entry["commit"])
                                                 for entry in self.code_review_of(answer)["launched"]])
        (call,) = self.code_review_launches()
        self.assertEqual(["--rig", "fx-rig", "--formula", "mol-code-review", "--role", "reviewer"], call[1:])
        self.assertEqual("favorable", self.shown(T1)["code_review"]["state"]["verdict"])
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])

    def test_a_pass_merges_nothing_of_a_ticket_whose_code_review_gave_no_verdict(self):
        base = self.integrated()
        self.code_reviewed("silent")
        self.advance(CONVOY)
        self.finished(T1)

        first = self.advance(CONVOY)
        second = self.advance(CONVOY)

        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(first)["launched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(second)["pending"]])
        for answer in (first, second):
            self.assertEqual(([], [T1]), (self.integration_of(answer)["merged"],
                                          [entry["id"] for entry in self.integration_of(answer)["waiting"]]))
        self.assertTrue(second["ok"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        self.assertEqual(1, len(self.code_review_launches()))

    def test_a_pass_stops_a_ticket_whose_code_review_gave_no_result_twice_and_raises_it_once(self):
        base = self.integrated()
        self.code_reviewed("silent", timeout_seconds=0)
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)

        relaunched = self.advance(CONVOY)
        stopped = self.advance(CONVOY)
        after = self.advance(CONVOY)

        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(relaunched)["relaunched"]])
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(stopped)["stopped"]])
        self.assertIsNone(self.code_review_of(after))
        self.assertEqual(2, len(self.code_review_launches()))
        stop = json.loads(self.bead(T1)["metadata"]["gc.flow.stop"])
        self.assertEqual("code_review_no_result", stop["reason"])
        self.assertIn("raised", stop)
        listed = self.run_ok(ESCALATION, "list").stdout
        self.assertEqual(1, listed.count(f"{T1} — "), listed)
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_code_review_that_cannot_be_sent_fails_the_pass_and_merges_nothing(self):
        base = self.integrated()
        self.code_reviewed("door-refuses")
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("rôle relecteur", self.code_review_of(answer)["refused"][0]["reason"])
        self.assertEqual([], self.integration_of(answer)["merged"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    # --- a finished ticket is evaluated on the launched product before its merge (T15) ---

    def test_a_pass_checks_that_the_product_of_a_finished_prefactoring_starts_and_merges_it(self):
        self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, tip, "favorable")], [(entry["ticket"], entry["commit"], entry["verdict"])
                                                    for entry in self.evaluation_of(answer)["started"]])
        # No Evaluator session for a prefactoring, and the review is sent by the same pass.
        self.assertEqual([], self.evaluation_launches())
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(answer)["launched"]])
        evaluation = self.shown(T1)["evaluation"]
        self.assertEqual(("startup", True, tip), tuple(evaluation["rounds"][0][name] for name in ("kind", "started", "commit")))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])
        self.assertEqual([], list((self.tmp / "launches").rglob("*.json")))
        self.assertIsNone(self.evaluation_of(self.advance(CONVOY)))

    def test_an_evaluation_that_cannot_run_fails_the_pass_and_merges_nothing(self):
        base = self.integrated()
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        del settings["evaluation"]
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("la Ticket Evaluation n'est pas réglée", self.evaluation_of(answer)["error"])
        self.assertEqual([], self.integration_of(answer)["merged"])
        self.assertIn("aucune Ticket Evaluation rendue", self.integration_of(answer)["waiting"][0]["reason"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    # --- one correction round, then the ticket stops (T17) ----------------------

    BLOCKS = {"findings": [{"axis": "spec", "blocking": True, "summary": "Le diff ne livre pas l'essai demandé.",
                            "citation": {"source": "spec", "quote": "As Benjamin, I want un essai."}}]}

    def corrected(self, *plan):
        """The correction round of a refused ticket (T17): its settings, and
        what the author session does at each launch
        (tests/fixtures/correction-round/author), the last one repeated."""
        (self.tmp / "correction-plan.json").write_text(json.dumps(list(plan)))
        self.env.update({
            "CORRECTION_ROUND_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "correction-round" / "author"),
            "CORRECTION_ROUND_FAKE_LOG": str(self.tmp / "correction-door.log"),
            "CORRECTION_ROUND_FAKE_PLAN": str(self.tmp / "correction-plan.json"),
            "CORRECTION_ROUND_FAKE_REPO": str(self.root),
            "CORRECTION_ROUND_FAKE_BRIEFS": str(self.tmp / "correction-briefs"),
        })
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        settings["correction"] = {"formula": "mol-ticket-correction", "role": "author", "rig": "fx-rig"}
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

    def correction_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("correction")

    def correction_launches(self):
        log = self.tmp / "correction-door.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def refused_by_its_review(self, *plan):
        """A finished ticket whose code review, sent by the next pass,
        leaves a Blocking Finding. Returns the tip of the ticket."""
        base = self.integrated()
        self.code_reviewed(self.BLOCKS)
        self.corrected(*plan)
        self.advance(CONVOY)
        return base, self.finished(T1)

    def test_a_pass_sends_a_ticket_its_review_refused_to_one_author_session_and_merges_nothing(self):
        base, tip = self.refused_by_its_review("works")

        first = self.advance(CONVOY)
        second = self.advance(CONVOY)

        # The review and the control of the product run in the same pass, on
        # the same tip; the round is opened once both have answered there.
        self.assertEqual([T1], [entry["ticket"] for entry in self.code_review_of(first)["launched"]])
        self.assertEqual([(T1, tip)], [(entry["ticket"], entry["commit"]) for entry in self.evaluation_of(first)["started"]])
        self.assertEqual([(T1, tip)], [(entry["ticket"], entry["commit"]) for entry in self.correction_of(first)["launched"]])
        (call,) = self.correction_launches()
        self.assertEqual(["--rig", "fx-rig", "--formula", "mol-ticket-correction", "--role", "author"], call[1:])
        self.assertEqual([T1], [entry["ticket"] for entry in self.correction_of(second)["pending"]])
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown(T1)["counters"])
        brief = json.loads((self.tmp / "correction-briefs" / "brief-1.json").read_text())
        self.assertEqual(["F1.1"], [finding["id"] for finding in brief["code_review"]["blocking_findings"]])
        for answer in (first, second):
            self.assertEqual([], self.integration_of(answer)["merged"])
            self.assertTrue(answer["ok"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_pass_stops_a_ticket_still_refused_after_its_round_and_raises_it_once(self):
        base, _ = self.refused_by_its_review("leaves")
        self.advance(CONVOY)

        stopped = self.advance(CONVOY)
        after = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "stop": "still_refused"}], self.correction_of(stopped)["stopped"])
        self.assertIsNone(self.correction_of(after))
        self.assertEqual(1, len(self.correction_launches()))
        stop = json.loads(self.bead(T1)["metadata"]["gc.flow.stop"])
        self.assertEqual("still_refused", stop["reason"])
        self.assertIn("raised", stop)
        listed = self.run_ok(ESCALATION, "list").stdout
        self.assertEqual(1, listed.count(f"{T1} — "), listed)
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        self.assertTrue(after["ok"])

    def test_a_correction_round_that_cannot_be_sent_fails_the_pass(self):
        base, _ = self.refused_by_its_review("door-refuses")

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("rôle auteur", self.correction_of(answer)["refused"][0]["reason"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))

    def test_a_refused_ticket_without_settings_of_the_correction_round_fails_the_pass(self):
        self.refused_by_its_review("works")
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        del settings["correction"]
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertIn("le tour de correction n'est pas réglé", self.correction_of(answer)["refused"][0]["reason"])
        self.assertEqual([], self.correction_launches())

    def test_a_pass_reports_no_correction_round_for_tickets_nothing_refused(self):
        self.integrated()
        self.advance(CONVOY)
        self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertIsNone(self.correction_of(answer))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])

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

    # --- resumes counted and bounded, parked tickets, one grouped request (T20) ---

    GROUPED = "Demande groupée"
    LIFT, LEAVE = "a", "b"

    def resumable(self, ceiling=5):
        """The settings of a resume, and a project that allows its formula."""
        (self.root / "config" / "projects" / "fx-rig.toml").write_text(
            'rig_dir = "."\nrepo = "example/fx"\nprotected_branch = "main"\nrequired_ci = "CI"\n'
            'sling_target = "fx-worker"\nformulas = "fx-start,fx-resume"\n')
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": ceiling,
            "start": {"formula": "fx-start", "role": None}, "resume": {"formula": "fx-resume", "role": None}}))

    def taken(self, ticket_id, name, alive=False):
        """An author session took the ticket; it is over unless `alive`."""
        self.run_ok(STATE, "set-session", CONVOY, ticket_id, "--session", name)
        self.edit(sessions=[{"id": f"s-{name}", "name": name, "template": "fx-worker", "state": "active",
                             "closed": False}] if alive else [])

    def interrupted(self, ticket_id, name):
        """The session that took the ticket left by the Ticket Exit « interrompu »."""
        self.taken(ticket_id, name)
        self.run_ok(STATE, "set-exit", CONVOY, ticket_id, "--exit", "interrupted")

    def started_convoy(self):
        self.resumable()
        self.advance(CONVOY)
        self.write_log.write_text("")

    def of(self, answer, name, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get(name, [])

    def resumes(self, ticket_id=T1):
        return self.bead(ticket_id)["metadata"]["gc.flow.counter.resumes"]

    def park_of(self, ticket_id):
        return self.shown_state(ticket_id)["park"]

    def shown_state(self, ticket_id):
        proc = self.run_cmd(STATE, "show", CONVOY, "--repo", self.root)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket_id)

    def resume_launches(self):
        return [entry for entry in self.log("sling") if entry[3] == "fx-resume"]

    def needs(self):
        """Every line of the operator's list, as bin/escalation-door prints it."""
        out = self.run_ok(ESCALATION, "list").stdout
        body = out.split("NEEDS BENJAMIN:", 1)[1].split("Pending proposals", 1)[0]
        return [line.strip() for line in body.splitlines() if line.strip() and "(none)" not in line]

    def grouped_bead(self):
        record = self.bead(CONVOY)["metadata"].get("gc.flow.grouped_request")
        return json.loads(record)["bead"] if record else None

    def exhausted_and_alone(self):
        """T1 interrupted three times and parked with T3; T2 closed: nothing
        but parked tickets is left in the convoy."""
        self.started_convoy()
        for name in ("auteur-1", "auteur-2", "auteur-3"):
            self.interrupted(T1, name)
            self.advance(CONVOY)
        self.close_through_gate(T2)
        self.write_log.write_text("")

    def test_a_pass_sends_an_interrupted_ticket_to_a_fresh_author_session_and_counts_the_resume(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")

        answer = self.advance(CONVOY)

        [resumed] = self.of(answer, "resumed")
        self.assertEqual((T1, "interrupted"), (resumed["id"], resumed["cause"]))
        self.assertEqual(1, self.resumes())
        self.assertEqual([["sling", "fx-worker", resumed["bead"], "fx-resume"]], self.resume_launches())
        sent = self.bead(resumed["bead"])["description"]
        self.assertIn(f"convoy: {CONVOY}", sent)
        self.assertIn(f"ticket: {T1}", sent)
        # The ticket is at work again: it will exit again.
        self.assertIsNone(self.shown_state(T1)["exit"])
        self.assertEqual(0, self.resumes(T2))

    def test_a_session_that_ended_without_an_exit_is_resumed_as_interrupted(self):
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(0, self.resumes())
        self.edit(sessions=[])

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "interrupted")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())

    def test_a_second_pass_on_the_same_interruption_counts_and_sends_nothing_more(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(before, self.tickets_snapshot())
        self.assertEqual(1, len(self.resume_launches()))

    def test_a_resume_whose_session_ended_without_taking_the_ticket_is_one_more_interruption(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        [first] = self.of(self.advance(CONVOY), "resumed")
        self.edit(first["bead"], status="closed")

        [second] = self.of(self.advance(CONVOY), "resumed")

        self.assertNotEqual(first["bead"], second["bead"])
        self.assertEqual(2, self.resumes())

    def test_a_resume_that_cannot_be_sent_fails_the_pass_is_counted_once_and_is_sent_by_the_next(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        env = {**self.env, "CONVOY_STATE_FAKE_SLING_FAIL": "fx-new1"}

        proc = self.run_cmd(TOOL, CONVOY, env=env)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([T1], [entry["id"] for entry in self.of(json.loads(proc.stdout), "refused")])
        self.assertEqual([], self.resume_launches())
        self.assertEqual(1, self.resumes())

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_to_resume_without_resume_settings_is_refused_and_nothing_is_written(self):
        self.advance(CONVOY)
        self.interrupted(T1, "auteur-1")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        [refused] = self.of(answer, "refused")
        self.assertEqual(T1, refused["id"])
        self.assertIn("resume.formula", refused["reason"])
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_resume_waits_for_a_free_place_under_the_ceiling_and_counts_nothing_meanwhile(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.resumable(ceiling=1)
        self.edit(sessions=[session("delivery-reviewer")])

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertIn(T1, [entry["id"] for entry in self.of(answer, "waiting")])
        self.assertEqual(0, self.resumes())
        self.assertEqual([], self.resume_launches())

    def test_a_resume_sent_and_not_yet_taken_by_a_session_holds_its_place(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        # T2 alone awaits its session when this pass counts, then T1 is sent.
        self.assertEqual([T2], self.advance(CONVOY)["awaiting_a_session"])

        answer = self.advance(CONVOY)

        self.assertEqual([T1, T2], answer["awaiting_a_session"])
        self.assertEqual(2, answer["occupied"])

    def test_a_resume_whose_session_ended_without_taking_the_ticket_holds_no_place(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        [sent] = self.of(self.advance(CONVOY), "resumed")
        self.edit(sent["bead"], status="closed")

        answer = self.advance(CONVOY)

        self.assertEqual([T2], answer["awaiting_a_session"])

    def test_a_stopped_ticket_is_never_resumed_as_interrupted(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "amendment_exhausted", "--detail", "second amendement")
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_ticket_blocked_by_a_repair_is_resumed_once_the_repair_is_closed(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "technically_blocked")
        self.edit(T1, blocks=["fx-o1"])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(0, self.resumes())
        self.run_ok(STATE, "record-gate", OTHER, "fx-o1", "--gate", "withdrawn")
        self.edit("fx-o1", status="closed")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "unblocked")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())

    def test_a_ticket_the_merge_returned_is_resumed_and_the_resume_is_counted(self):
        self.integrated(regression="false")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)  # the merge returns it: red tests on the merged result

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "returned")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(1, self.resumes())
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_ticket_at_its_third_resume_whatever_the_causes_is_parked_with_its_descendants_and_not_restarted(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)  # an interruption: one resume
        # A correction round, as bin/convoy-state open-correction counts it,
        # then a commit after a verdict, as invalidate-verdicts counts it.
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [parked] = self.of(answer, "parked")
        self.assertEqual((T1, "resumes_exhausted", [T1, T3]), (parked["id"], parked["cause"], parked["parked"]))
        for ticket_id in (T1, T3):
            park = self.park_of(ticket_id)
            self.assertEqual(("resumes_exhausted", T1), (park["cause"], park["origin"]), ticket_id)
        self.assertIsNone(self.park_of(T2))
        self.assertEqual([], self.slung())
        # Interrupted once more, it is not restarted.
        self.interrupted(T1, "auteur-2")
        again = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(again, "resumed"), self.slung()))
        self.assertEqual(3, self.resumes())

    def test_a_ticket_interrupted_three_times_is_restarted_twice_and_parked_at_the_third(self):
        self.started_convoy()
        seen = []
        for name in ("auteur-1", "auteur-2", "auteur-3"):
            self.interrupted(T1, name)
            answer = self.advance(CONVOY)
            seen.append((len(self.of(answer, "resumed")), len(self.of(answer, "parked"))))

        self.assertEqual([(1, 0), (1, 0), (0, 1)], seen)
        self.assertEqual(2, len(self.resume_launches()))
        self.assertEqual(3, self.resumes())
        self.assertEqual("resumes_exhausted", self.park_of(T3)["cause"])

    def test_the_tickets_that_wait_for_no_parked_ticket_keep_starting(self):
        self.resumable(ceiling=1)
        self.advance(CONVOY)  # T1 alone: the ceiling
        self.run_ok(STATE, "set-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--value", 3)
        self.close_through_gate("fx-o1", OTHER)
        self.resumable()

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "parked")])
        self.assertEqual([T2], self.started(answer))
        self.assert_started_through_door(T2)
        self.assertEqual({T3}, {entry["id"] for entry in self.of(answer, "waiting")})

    def test_a_convoy_left_with_parked_tickets_only_raises_exactly_one_request_naming_each_and_its_cause(self):
        self.exhausted_and_alone()

        answer = self.advance(CONVOY)

        needs = self.needs()
        self.assertEqual(1, len(needs), needs)
        self.assertTrue(needs[0].startswith(f"{self.grouped_bead()} — "), needs)
        for named in (CONVOY, T1, T3, "reprises épuisées"):
            self.assertIn(named, needs[0])
        self.assertEqual([["mail", "human", f"NEEDS BENJAMIN: {self.grouped_bead()}"]], self.log("mail"))
        self.assertTrue(self.of(answer, "grouped_request")["raised"])
        # One request for the convoy, none per ticket.
        for ticket_id in (T1, T3):
            self.assertNotIn("gc.needs_benjamin", self.bead(ticket_id)["metadata"], ticket_id)
        description = self.bead(self.grouped_bead())["description"]
        for named in (T1, T3, "reprises épuisées"):
            self.assertIn(named, description)

    def test_the_grouped_request_names_a_ticket_its_own_exit_parked_with_that_cause(self):
        self.exhausted_and_alone()
        self.edit(T2, status="open", metadata={k: v for k, v in self.bead(T2)["metadata"].items()
                                                if k != "gc.flow.gate.ticket_end"})
        self.run_ok(STATE, "park", CONVOY, T2, "--cause", "operator_request", "--detail", "Accès à l'horloge")

        self.advance(CONVOY)

        description = self.bead(self.grouped_bead())["description"]
        self.assertIn(T2, description)
        self.assertIn("demande opérateur", description)

    def test_no_grouped_request_while_a_ticket_that_is_not_parked_is_left(self):
        self.started_convoy()
        for name in ("auteur-1", "auteur-2", "auteur-3"):
            self.interrupted(T1, name)
            self.advance(CONVOY)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.needs())
        self.assertIsNone(self.grouped_bead())
        self.assertEqual({}, self.of(answer, "grouped_request") or {})

    def test_the_same_parked_convoy_seen_on_several_passes_raises_one_request(self):
        self.exhausted_and_alone()

        for _ in range(3):
            self.advance(CONVOY)

        self.assertEqual(1, len(self.needs()))
        self.assertEqual(1, len(self.log("mail")))
        self.assertEqual(1, len([entry for entry in self.log("create") if self.GROUPED in entry[2]]))

    def test_a_grouped_request_that_could_not_be_raised_fails_the_pass_and_is_raised_by_the_next(self):
        self.exhausted_and_alone()

        proc = self.run_cmd(TOOL, CONVOY, env={**self.env, "CONVOY_STATE_FAKE_MAIL_FAIL": "1"})

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.advance(CONVOY)
        self.assertEqual(1, len(self.needs()))
        self.assertEqual(1, len([entry for entry in self.log("create") if self.GROUPED in entry[2]]))

    def test_the_answer_that_lifts_makes_the_ticket_and_its_descendants_startable_again(self):
        self.exhausted_and_alone()
        self.advance(CONVOY)
        request = self.grouped_bead()
        self.run_ok(ESCALATION, "repondre", request, self.LIFT)
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [lifted] = self.of(answer, "lifted")
        self.assertEqual((T1, [T1, T3]), (lifted["id"], lifted["lifted"]))
        self.assertIsNone(self.park_of(T1))
        self.assertIsNone(self.park_of(T3))
        # The ticket is sent again to an author session by the pass itself.
        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "resumed")])
        self.assertEqual(1, len(self.resume_launches()))
        self.assertEqual(3, self.shown_state(T1)["resumes_left"])
        # The request is over: off the list, its bead closed, its record gone.
        self.assertEqual([], self.needs())
        self.assertEqual("closed", self.bead(request)["status"])
        self.assertIsNone(self.grouped_bead())
        # And the ticket that waited for it starts once it is closed.
        self.close_through_gate(T1)
        self.assertEqual([T3], self.started(self.advance(CONVOY)))

    def test_the_answer_that_leaves_the_tickets_parked_lifts_nothing_and_is_not_asked_again(self):
        self.exhausted_and_alone()
        self.advance(CONVOY)
        self.run_ok(ESCALATION, "repondre", self.grouped_bead(), self.LEAVE)
        self.write_log.write_text("")

        for _ in range(2):
            answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "lifted"))
        self.assertEqual("resumes_exhausted", self.park_of(T1)["cause"])
        self.assertEqual([], self.needs())
        self.assertEqual(([], []), (self.log("mail"), self.slung()))

    def test_an_answer_to_the_request_of_a_ticket_its_own_exit_parked_lifts_it_and_resumes_it(self):
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {"quoi": "Accès à l'horloge de référence", "pourquoi": "L'auteur n'a pas cet accès",
                   "que_faire": [{"option": "Donner l'accès", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "operator_request")
        unanswered = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(unanswered, "lifted"), self.of(unanswered, "resumed")))
        self.assertEqual("operator_request", self.park_of(T3)["cause"])
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking
        self.run_ok(ESCALATION, "repondre", T1, "a")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, [T1, T3])], [(entry["id"], entry["lifted"]) for entry in self.of(answer, "lifted")])
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertIsNone(self.park_of(T3))
        self.assertEqual(1, self.resumes())

    # --- the stops of the convoy: red integration branch, open Planning Exceptions (T21, af-cbp84n) ---

    RED_BRANCH = "branche d'intégration rouge"
    RED_CONTROL = "commande de régression (true) : code 1, sur integration/fx-spec"
    REPAIR = "fx-r1"

    def stop_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("stop")

    def waiting_reasons(self, answer, convoy=CONVOY):
        return {entry["id"]: entry["reason"] for entry in self.of(answer, "waiting", convoy)}

    def red_recorded(self, base):
        """The false state of the ticket: tests red at the tip of the
        integration branch, the repair of that red published and named."""
        state = self.tracker_state()
        state["beads"][self.REPAIR] = {**ticket(self.REPAIR), "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append(self.REPAIR)
        self.tracker.write_text(json.dumps(state))
        self.run_ok(STATE, "mark", CONVOY, "--demonstration-line",
                    f"{self.REPAIR}=La commande de régression se termine avec le code 0")
        self.run_ok(STATE, "record-integration-red", CONVOY, "--commit", base, "--integration", base,
                    "--protected", base, "--control", self.RED_CONTROL)
        self.run_ok(STATE, "set-integration-repair", CONVOY, "--ticket", self.REPAIR)
        self.write_log.write_text("")

    def test_a_red_integration_branch_starts_no_ticket_but_its_repair(self):
        self.red_recorded(self.integrated())
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY)

        # T1 and T2 are ready and places are free: neither starts.
        self.assertEqual([self.REPAIR], self.started(answer))
        self.assertEqual([self.REPAIR], self.slung())
        self.assertEqual(before, self.tickets_snapshot())
        stop = self.stop_of(answer)
        self.assertEqual(("integration_red", self.RED_CONTROL, self.REPAIR), (stop["reason"], stop["control"], stop["repair"]))
        for ticket_id, reason in self.waiting_reasons(answer).items():
            self.assertIn(self.RED_BRANCH, reason, ticket_id)
            self.assertIn(self.RED_CONTROL, reason, ticket_id)
        self.assertEqual({T1, T2, T3}, set(self.waiting_reasons(answer)))
        self.assertTrue(answer["ok"])

    def test_a_red_integration_branch_merges_no_finished_ticket(self):
        base = self.integrated()
        self.advance(CONVOY)
        self.finished(T1)
        self.red_recorded(base)

        answer = self.advance(CONVOY)

        integration = self.integration_of(answer)
        self.assertEqual(self.RED_CONTROL, integration["red"]["control"])
        self.assertEqual(self.RED_BRANCH, integration["stopped"])
        self.assertNotIn("merged", integration)
        self.assertIsNone(self.shown(T1)["merge"])
        self.assertEqual(base, self.git("rev-parse", self.INTEGRATION))
        # The convoy is stopped, the pass is not a failure.
        self.assertTrue(answer["ok"])

    def test_several_passes_on_the_same_red_start_and_merge_nothing_more(self):
        self.red_recorded(self.integrated())
        self.advance(CONVOY)
        self.write_log.write_text("")
        before = self.tracker.read_bytes()

        for _ in range(2):
            answer = self.advance(CONVOY)
            self.assertEqual([], self.started(answer))

        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([], self.slung())
        self.assertEqual([], self.log("create"))

    def test_the_starts_and_the_merges_resume_by_themselves_once_the_red_is_withdrawn(self):
        base = self.integrated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        self.red_recorded(base)
        self.advance(CONVOY)
        # What the merge command writes once the control is green again.
        self.run_ok(STATE, "clear-integration-red", CONVOY)
        self.close_through_gate(T2)

        answer = self.advance(CONVOY)

        self.assertIsNone(self.stop_of(answer))
        self.assertEqual([T1], [entry["id"] for entry in self.integration_of(answer)["merged"]])
        self.assertEqual(tip, self.shown(T1)["merge"]["ticket_commit"])
        # T3 waited for T1 and T2: closed by the pass and by the gate, it starts at the next one.
        self.assertEqual([T3], self.started(self.advance(CONVOY)))

    def test_a_red_without_its_repair_that_the_patch_door_cannot_publish_fails_the_pass_and_starts_nothing(self):
        base = self.integrated()
        self.run_ok(STATE, "record-integration-red", CONVOY, "--commit", base, "--integration", base,
                    "--protected", base, "--control", self.RED_CONTROL)
        self.write_log.write_text("")
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        # This convoy was not published by the publication door: nothing to revise.
        self.assertIn("porte de patch", self.of(answer, "repair")["error"])
        self.assertEqual(([], []), (self.started(answer), self.slung()))
        self.assertEqual(before, self.tickets_snapshot())

    # A convoy of four tickets that wait for nothing.
    A, B, C, D = "fx-a", "fx-b", "fx-c", "fx-d"

    def four_tickets(self, ceiling, bounds=None):
        beads = {CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                          "metadata": {"gc.spec_id": "fx-spec"}, "tracks": [self.A, self.B, self.C, self.D]},
                 **{ticket_id: ticket(ticket_id) for ticket_id in (self.A, self.B, self.C, self.D)}}
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.run_ok(STATE, "mark", CONVOY)
        self.resumable(ceiling)
        if bounds is not None:
            settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
            settings["bounds"] = bounds
            (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))
        self.write_log.write_text("")

    def planning_exception(self, ticket_id):
        """The author of the ticket left by the Ticket Exit « Planning
        Exception » (bin/ticket-exit): the request, the exception, the parking."""
        request = {"quoi": f"Planning Exception (semantic) sur {ticket_id} : la Spec dit X, le produit fait Y",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "raise-planning-exception", CONVOY, ticket_id, "--kind", "semantic",
                    "--summary", "la Spec dit X, le produit fait Y")
        self.run_ok(ESCALATION, "benjamin", ticket_id, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, ticket_id, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, ticket_id, "--exit", "planning_exception")

    def three_at_work(self, bounds=None):
        """A, B and C started and taken by their authors; D still waits for
        a place. C's session then left by « interrompu »."""
        self.four_tickets(ceiling=3, bounds=bounds)
        self.assertEqual([self.A, self.B, self.C], self.started(self.advance(CONVOY)))
        for ticket_id in (self.A, self.B):
            self.taken(ticket_id, f"auteur-{ticket_id}")
        self.interrupted(self.C, "auteur-c")
        self.write_log.write_text("")

    def test_two_open_planning_exceptions_start_no_new_ticket_and_the_tickets_at_work_go_on(self):
        self.three_at_work()
        self.planning_exception(self.A)
        self.planning_exception(self.B)
        before = self.bead(self.D)

        answer = self.advance(CONVOY)

        # D is ready and places are free: it does not start.
        self.assertEqual([], self.started(answer))
        self.assertEqual(before, self.bead(self.D))
        stop = self.stop_of(answer)
        self.assertEqual(("planning_exceptions", [self.A, self.B], 2), (stop["reason"], stop["open"], stop["bound"]))
        self.assertIn("2 Planning Exceptions ouvertes", self.waiting_reasons(answer)[self.D])
        # C was at work: its resume is sent, it finishes.
        self.assertEqual([(self.C, "interrupted")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertTrue(answer["ok"])

    def test_one_open_planning_exception_lets_the_tickets_that_are_not_parked_start(self):
        self.three_at_work()
        self.planning_exception(self.A)

        answer = self.advance(CONVOY)

        self.assertEqual([self.D], self.started(answer))
        self.assertIsNone(self.stop_of(answer))
        # B's session is over without an exit, C left by « interrompu »: both are resumed.
        self.assertEqual([self.B, self.C], [r["id"] for r in self.of(answer, "resumed")])
        self.assertEqual("planning_exception", self.park_of(self.A)["cause"])

    def test_the_starts_resume_by_themselves_once_one_of_the_two_planning_exceptions_is_answered(self):
        self.three_at_work()
        self.planning_exception(self.A)
        self.planning_exception(self.B)
        self.assertEqual([], self.started(self.advance(CONVOY)))
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the exception
        self.run_ok(ESCALATION, "repondre", self.B, "a")

        answer = self.advance(CONVOY)

        self.assertEqual([self.D], self.started(answer))
        self.assertIsNone(self.stop_of(answer))

    def test_a_planning_exception_raised_by_an_evaluation_counts_as_an_open_one(self):
        self.three_at_work()
        self.planning_exception(self.A)
        # What bin/ticket-evaluation leaves of a criterion the Evaluator cannot observe: the parking alone.
        self.run_ok(STATE, "park", CONVOY, self.B, "--cause", "planning_exception",
                    "--detail", f"Planning Exception sur {self.B} : inobservable sur le produit lancé (critère 1)")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.started(answer))
        self.assertEqual([self.A, self.B], self.stop_of(answer)["open"])

    def test_the_bound_of_the_open_planning_exceptions_is_the_one_of_the_settings(self):
        for bound, exceptions, started in ((1, (self.A,), []), (3, (self.A, self.B), [self.D])):
            with self.subTest(bound=bound):
                self.three_at_work(bounds={"resumes": 3, "open_planning_exceptions": bound})
                for ticket_id in exceptions:
                    self.planning_exception(ticket_id)

                answer = self.advance(CONVOY)

                self.assertEqual(started, self.started(answer))
                self.assertEqual(bound if not started else None, (self.stop_of(answer) or {}).get("bound"))

    def test_a_malformed_bound_of_the_open_planning_exceptions_refuses_the_pass_and_starts_nothing(self):
        for value in (0, "deux", None):
            with self.subTest(value=value):
                self.four_tickets(ceiling=3, bounds={"resumes": 3, "open_planning_exceptions": value})
                before = self.tracker.read_bytes()

                answer = self.advance(CONVOY, expect=EXIT_REFUSED)

                self.assertIn("bounds.open_planning_exceptions", answer["error"])
                self.assertEqual(before, self.tracker.read_bytes())
                self.assertEqual([], self.slung())

    # --- the end of the Spec: the gate is run by the pass (T23, af-s5uysn), and the
    # --- assembled product evaluated once its mechanical verdicts are green (T24) ---

    GATE = "spec-end/v2"
    MECHANICAL_GREEN = {"registry": "pass", "tests": "pass", "fidelity": "pass"}
    NOT_LAUNCHED = {"outcome_evaluation": "not_run", "findings": "not_run"}

    def outcome_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("outcome_evaluation")

    def outcome_launches(self):
        log = self.tmp / "outcome-door.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def spec_end_of(self, answer, convoy=CONVOY):
        return next(c for c in answer["convoys"] if c["id"] == convoy).get("spec_end")

    def convoy_shown(self):
        return json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"]

    def every_ticket_closed(self, but=()):
        """The convoy with its integration branch, its tickets closed by the
        ticket-end gate (but those named); returns the tip of that branch."""
        self.integrated()
        self.env["SPEC_END_LOCK_DIR"] = str(self.tmp / "locks")
        self.env["SPEC_END_WORK_DIR"] = str(self.tmp / "gate-work")
        for ticket_id in (T1, T2, T3):
            if ticket_id not in but:
                self.close_through_gate(ticket_id)
        self.write_log.write_text("")
        return self.git("rev-parse", self.INTEGRATION)

    def regression(self, command):
        path = self.root / "config" / "project-descriptors" / "fx.json"
        descriptor = json.loads(path.read_text())
        descriptor["launch"]["regression_command"] = command
        path.write_text(json.dumps(descriptor))

    def test_a_pass_runs_the_end_of_spec_gate_once_every_ticket_of_the_convoy_is_closed(self):
        tip = self.every_ticket_closed()

        answer = self.advance(CONVOY)

        # The three mechanical verdicts are rendered and recorded; the gate
        # waits for the Outcome Evaluation of that commit, which is no failure.
        ending = self.spec_end_of(answer)
        self.assertEqual({**self.MECHANICAL_GREEN, "outcome_evaluation": "fail", "findings": "not_run"}, ending["verdicts"])
        self.assertEqual((self.GATE, tip, True, [4]),
                         (ending["version"], ending["commit"], ending["replayed"], ending["missing"]))
        self.assertIn("aucune Outcome Evaluation rendue", ending["reason"])
        self.assertTrue(answer["ok"])
        record = self.convoy_shown()["spec_end"]
        self.assertEqual((tip, self.GATE), (record["commit"], record["version"]))
        self.assertEqual({"end_rounds": 0}, self.convoy_shown()["counters"])
        self.assertEqual([], self.escalation_list())

        # The next passes, on the same tip: nothing is replayed, and once the
        # launched products are stopped nothing is written.
        again = self.spec_end_of(self.advance(CONVOY))
        self.assertEqual((tip, False), (again["commit"], again["replayed"]))
        before = self.tracker.read_bytes()
        self.advance(CONVOY)
        self.assertEqual(before, self.tracker.read_bytes())

    def test_a_pass_has_the_assembled_product_evaluated_once_the_mechanical_verdicts_are_green(self):
        tip = self.every_ticket_closed()

        first = self.advance(CONVOY)

        # The same pass that rendered the verdicts launches the product at
        # their commit and sends it to the Evaluator role, once.
        launched = self.outcome_of(first)
        self.assertEqual(("launched", tip, 1), (launched["action"], launched["commit"], launched["launches"]))
        (call,) = self.outcome_launches()
        self.assertEqual([launched["bead"], "--rig", "fx-rig", "--formula", "mol-outcome-evaluation", "--role", "evaluator"],
                         call)
        rounds = self.convoy_shown()["outcome_evaluation"]["rounds"]
        self.assertEqual([("favorable", tip)], [(entry["outcome"], entry["commit"]) for entry in rounds])
        self.assertEqual([1, 2, 3], [story["number"] for story in rounds[0]["stories"]])

        # Every story observed with its piece: the five conditions are met.
        second = self.advance(CONVOY)

        ending = self.spec_end_of(second)
        self.assertEqual({**self.MECHANICAL_GREEN, "outcome_evaluation": "pass", "findings": "pass"}, ending["verdicts"])
        self.assertEqual(([], False), (ending["missing"], ending["replayed"]))
        self.assertNotIn("reason", ending)
        self.assertIsNone(self.outcome_of(second))
        self.assertEqual(1, len(self.outcome_launches()))
        self.assertEqual([], self.convoy_shown()["outcome_evaluation"].get("live") or [])
        self.assertEqual([], self.escalation_list())

    def test_a_pass_waits_for_an_outcome_evaluation_that_has_not_answered_and_launches_no_other(self):
        tip = self.every_ticket_closed()
        self.outcome_evaluated("silent")
        self.advance(CONVOY)
        before = self.tracker.read_bytes()

        answer = self.advance(CONVOY)

        pending = self.outcome_of(answer)
        self.assertEqual(("pending", tip, 1), (pending["action"], pending["commit"], pending["launches"]))
        self.assertIn("deadline", pending)
        self.assertTrue(answer["ok"])
        self.assertEqual(1, len(self.outcome_launches()))
        self.assertNotIn("outcome_repairs", next(c for c in answer["convoys"] if c["id"] == CONVOY))
        self.assertEqual(before, self.tracker.read_bytes())

    def test_a_drafted_repair_of_a_story_not_observed_that_the_patch_door_cannot_publish_fails_the_pass(self):
        self.every_ticket_closed()
        # The story of the Spec is looked for on a page the assembled product does not serve.
        self.outcome_evaluated({"stories": {"1": {"path": "/version"}}})
        self.advance(CONVOY)
        state = self.convoy_shown()["outcome_evaluation"]["state"]
        self.assertEqual(("unfavorable", [1]), (state["verdict"], state["not_observed"]))
        before = self.tickets_snapshot()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        # This convoy was not published by the publication door: nothing to revise.
        (refused,) = self.of(answer, "outcome_repairs")
        self.assertEqual(1, refused["story"])
        self.assertIn("porte de patch", refused["error"])
        self.assertFalse(answer["ok"])
        # The gate names the story; nothing is started, no ticket is touched.
        ending = self.spec_end_of(answer)
        self.assertEqual([4], ending["missing"])
        self.assertIn("user story 1", ending["reason"])
        self.assertEqual(([], []), (self.started(answer), self.slung()))
        self.assertEqual(before, self.tickets_snapshot())
        self.assertEqual(1, len(self.outcome_launches()))

    def test_an_outcome_evaluation_that_cannot_be_settled_fails_the_pass_and_says_why(self):
        tip = self.every_ticket_closed()
        settings = json.loads((self.root / "config" / "delivery-flow.json").read_text())
        del settings["outcome_evaluation"]
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps(settings))

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("outcome_evaluation", self.outcome_of(answer)["error"])
        # The mechanical verdicts are rendered all the same; no evaluation is opened.
        self.assertEqual(tip, self.convoy_shown()["spec_end"]["commit"])
        self.assertIsNone(self.convoy_shown()["outcome_evaluation"])
        self.assertEqual([], self.outcome_launches())

    def test_a_pass_does_not_run_the_end_of_spec_gate_while_a_ticket_is_open(self):
        self.every_ticket_closed(but=(T3,))

        answer = self.advance(CONVOY)

        self.assertIsNone(self.spec_end_of(answer))
        self.assertEqual([T3], self.started(answer))
        self.assertIsNone(self.convoy_shown()["spec_end"])

    def test_a_pass_runs_no_end_of_spec_gate_on_a_convoy_without_the_mark_or_without_integration_branch(self):
        # Every ticket closed, and no integration branch: a convoy the flow has not integrated.
        for ticket_id in (T1, T2, T3):
            self.close_through_gate(ticket_id)

        self.assertIsNone(self.spec_end_of(self.advance(CONVOY)))
        self.assertNotIn("spec_end", json.dumps(self.advance(PLAIN, expect=EXIT_NOT_NEW_FLOW)))

    def test_a_registry_that_refuses_is_an_outcome_of_the_pass_and_launches_nothing_else(self):
        tip = self.every_ticket_closed()
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "La Spec fixe un tri par date, le produit trie par nom.")
        # Red tests would be recorded: the registry stops the gate before them.
        self.regression("false")
        before = self.tracker.read_bytes()

        answer = self.advance(CONVOY)

        ending = self.spec_end_of(answer)
        self.assertEqual({"registry": "fail", "tests": "not_run", "fidelity": "not_run", **self.NOT_LAUNCHED},
                         ending["verdicts"])
        self.assertEqual([1], ending["missing"])
        self.assertEqual([("planning_exception", T1)], [(entry["kind"], entry["ticket"]) for entry in ending["refused"]])
        self.assertIn("Planning Exception ouverte", ending["reason"])
        self.assertIn(T1, ending["reason"])
        self.assertNotIn("error", ending)
        self.assertTrue(answer["ok"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(tip, self.git("rev-parse", self.INTEGRATION))
        # No product is launched while the mechanical verdicts are not green.
        self.assertEqual("waiting", self.outcome_of(answer)["action"])
        self.assertEqual([], self.outcome_launches())

    def test_red_tests_at_the_end_of_the_spec_are_an_outcome_of_the_pass_and_count_one_round(self):
        tip = self.every_ticket_closed()
        self.regression("false")

        answer = self.advance(CONVOY)

        ending = self.spec_end_of(answer)
        self.assertEqual({"registry": "pass", "tests": "fail", "fidelity": "not_run", **self.NOT_LAUNCHED},
                         ending["verdicts"])
        self.assertEqual(([2], 1), (ending["missing"], ending["end_rounds"]))
        self.assertIn("condition 2", ending["reason"])
        self.assertTrue(answer["ok"])
        shown = self.convoy_shown()
        self.assertEqual(ending["red"]["control"], shown["integration_red"]["control"])
        self.assertIn("commande de régression (false)", shown["integration_red"]["control"])
        self.assertEqual(({"end_rounds": 1}, None), (shown["counters"], shown["spec_end"]))
        self.assertEqual(tip, self.git("rev-parse", self.INTEGRATION))

    def test_a_red_integration_branch_gets_no_end_of_spec_verdict(self):
        tip = self.every_ticket_closed()
        self.red_recorded(tip)

        answer = self.advance(CONVOY)

        self.assertIsNone(self.spec_end_of(answer))
        self.assertEqual(self.RED_CONTROL, self.stop_of(answer)["control"])
        self.assertEqual(({"end_rounds": 0}, None), (self.convoy_shown()["counters"], self.convoy_shown()["spec_end"]))

    def test_an_end_of_spec_gate_that_cannot_run_fails_the_pass_and_says_why(self):
        self.every_ticket_closed()
        shutil.rmtree(self.root / "config" / "project-descriptors")

        answer = self.advance(CONVOY, expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("profil", self.spec_end_of(answer)["error"])
        self.assertIsNone(self.convoy_shown()["spec_end"])

    def test_the_end_of_spec_gate_run_from_an_agent_session_renders_no_verdict(self):
        self.every_ticket_closed()
        before = self.tracker.read_bytes()

        answer = self.advance(CONVOY, expect=EXIT_REFUSED, env={**self.env, "GC_SESSION_NAME": "delivery-author-fx"})

        self.assertFalse(answer["ok"])
        self.assertNotIn("verdicts", self.spec_end_of(answer) or {})
        self.assertEqual(before, self.tracker.read_bytes())


if __name__ == "__main__":
    unittest.main()
