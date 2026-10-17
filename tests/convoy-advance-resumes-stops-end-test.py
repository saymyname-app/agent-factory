#!/usr/bin/env python3
# ci: over-ceiling — second half of tests/convoy-advance-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); what is left is the passes each case verifies
"""bin/convoy-advance on a fake tracker state, the second half of the cases
(Spec CI01, af-q9urgr: tests/convoy-advance-test.py was the longest file of
the battery, cut in two files of about the same duration).

The harness is the one of tests/convoy-advance-test.py, loaded from there:
the seeded tracker, the settings, the stand-ins of the doors and the set-up
helpers. This file holds the cases of the resumes and the parked tickets
(T20), of the stops of the convoy (T21, T45) and of the end of the Spec
(T23, T24, T25); the first holds the starts, the ceiling, the factory
incidents, the dispatch door, the merges and the controls before them.

Since af-vqew1x the cases of the end of the Spec (T23, T24, T25) are in
tests/convoy-advance-end-of-spec-test.py."""

import importlib.machinery
import importlib.util
import hashlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: unittest collects the test classes
# named at the top of a file, and the cases of the first half run there.
first = load("convoy-advance-test.py")
TOOL = first.TOOL
STATE = first.STATE
ESCALATION = first.ESCALATION
CONVOY = first.CONVOY
OTHER = first.OTHER
PLAIN = first.PLAIN
T1 = first.T1
T2 = first.T2
T3 = first.T3
EXIT_REFUSED = first.EXIT_REFUSED
EXIT_NOT_NEW_FLOW = first.EXIT_NOT_NEW_FLOW
ticket = first.ticket
session = first.session


class ConvoyAdvanceTest(first.ConvoyAdvanceHarness):
    # --- resumes counted and bounded, parked tickets, one grouped request (T20) ---

    def earlier_resumes(self, cause, count, ticket_id=T1):
        """`count` resumes of `cause` the ticket took long before, written
        under its recorded ones, the counter with them (ADR-0030 L2: the
        bound is per cause)."""
        metadata = self.bead(ticket_id)["metadata"]
        record = json.loads(metadata.get("gc.flow.resume") or '{"entries": []}')
        earlier = [{"cause": cause, "ref": f"earlier:{n}", "session": None, "exit": None, "launches": [],
                    "at": "2000-01-01T00:00:00Z"} for n in range(count)]
        record["entries"] = earlier + record["entries"]
        metadata["gc.flow.resume"] = json.dumps(record)
        metadata["gc.flow.counter.resumes"] += count
        self.edit(ticket_id, metadata=metadata)

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

    # --- a ticket stopped without an evaluation result is resumed on itself (af-xhc0sj) ---

    NO_RESULT = "evaluation_no_result"

    @first.staged
    def evaluation_stopped(self):
        """T1, a slice, finished on the integration branch, then stopped as
        bin/ticket-evaluation stops it: its evaluation request left open
        with two launches that gave no result, the stop raised to the
        operator."""
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.env.update({
            "TICKET_EVALUATION_CANCEL_BIN": str(first.ROOT / "tests" / "fixtures" / "ticket-evaluation" / "cancel"),
            "TICKET_EVALUATION_CANCEL_LOG": str(self.tmp / "evaluation-cancel.log"),
        })
        self.advance(CONVOY)
        tip = self.finished(T1)
        bead = self.bead(T1)
        self.edit(T1, metadata={**bead["metadata"], "gc.ticket_kind": "vertical_slice",
                                "gc.flow.demonstration_line": "La page affiche 3",
                                "gc.flow.user_stories": json.dumps({"stories": ["1"]})},
                  description="## Acceptance criteria\n\n- [ ] La page affiche 3\n\n" + bead["description"])
        request = self.tmp / "evaluation-request.json"
        request.write_text(json.dumps({
            "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:9",
                             "state_file": str(self.tmp / "launches" / "gone.json")}]}))
        self.run_ok(STATE, "open-evaluation", CONVOY, T1, "--commit", tip, "--file", request)
        for launch in ("fx-e1", "fx-e2"):
            self.run_ok(STATE, "launch-evaluation", CONVOY, T1, "--bead", launch)
        self.assertEqual(2, len(self.shown_state(T1)["evaluation"]["request"]["launches"]))
        self.stop_without_result()
        self.write_log.write_text("")

    def stop_without_result(self):
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", self.NO_RESULT,
                    "--detail", "la Ticket Evaluation n'a rendu aucun état en 2 lancements")
        request = {"quoi": f"Ticket {T1} arrêté : sa Ticket Evaluation n'a rendu aucun état",
                   "pourquoi": "Une évaluation sans résultat n'est pas passée.",
                   "que_faire": [{"option": "Laisser le ticket arrêté", "consequence": "Rien ne fusionne."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)

    def test_a_ticket_stopped_without_an_evaluation_result_is_resumed_on_itself_once_per_integration_tip(self):
        self.evaluation_stopped()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, self.NO_RESULT)], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(["sling", "fx-worker", self.of(answer, "resumed")[0]["bead"], "fx-resume"],
                         self.resume_launches()[-1][:4])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, None), (shown["counters"]["resumes"], shown["stop"], shown["exit"]))
        # The stop is lifted, not erased: it is kept on the resume that lifted it.
        self.assertEqual(self.NO_RESULT, shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        # The exit taken back, the evaluation left open on it is withdrawn in the same pass.
        self.assertIsNone(shown["evaluation"].get("request"))
        # Stopped again on the same integration tip: it stays with the operator.
        self.stop_without_result()
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])
        # The integration branch moved: once more, counted.
        self.integration_moved()
        again = self.advance(CONVOY)
        self.assertEqual([(T1, self.NO_RESULT)], [(r["id"], r["cause"]) for r in self.of(again, "resumed")])
        self.assertEqual(2, self.resumes())

    def test_a_ticket_stopped_without_an_evaluation_result_at_its_third_resume_is_parked_not_restarted(self):
        self.evaluation_stopped()
        self.earlier_resumes(self.NO_RESULT, 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        self.assertEqual(([], []), (self.of(answer, "resumed"), self.resume_launches()))
        self.assertEqual((3, None), (self.resumes(), self.shown_state(T1)["stop"]))

    def test_a_stop_without_evaluation_result_the_operator_answered_is_not_resumed(self):
        self.evaluation_stopped()
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop
        self.run_ok(ESCALATION, "repondre", T1, "a")

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual(self.NO_RESULT, self.shown_state(T1)["stop"]["reason"])

    # --- a ticket stopped by a stage the flow removed is resumed on itself (ADR-0030 L3, af-pjvsgo) ---

    def stopped_by_the_test_review(self, raised=True):
        """T1 at work under an author session that is over, then stopped as
        the test review stopped it before L3 removed that stage, its
        request raised to the operator (T59, af-qjq1t6) when `raised`."""
        self.resumable()
        self.advance(CONVOY)
        self.edit(T1, status="in_progress")
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "test_review_no_result",
                    "--detail", "la relecture des tests n'a rendu aucun verdict en 2 lancements")
        self.write_log.write_text("")
        if not raised:
            return
        request = {"quoi": f"Ticket {T1} arrêté : relecture des tests sans résultat",
                   "pourquoi": "La relecture des tests n'a rendu aucun verdict.",
                   "que_faire": [{"option": "Laisser le ticket arrêté", "consequence": "Rien ne fusionne."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "stop-raised", CONVOY, T1)
        self.write_log.write_text("")

    def test_a_ticket_the_removed_test_review_stopped_is_resumed_once_and_its_request_withdrawn(self):
        self.stopped_by_the_test_review()
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "stage_removed")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, None), (shown["counters"]["resumes"], shown["stop"], shown["exit"]))
        # The stop is lifted, not erased: it is kept on the resume that lifted it.
        self.assertEqual("test_review_no_result", shown["resume"]["entries"][-1]["stop"]["reason"])
        self.assertEqual([], [line for line in self.needs() if T1 in line])
        # The next pass counts and sends nothing more.
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_stop_of_the_removed_test_review_the_operator_answered_is_not_resumed(self):
        self.stopped_by_the_test_review()
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the stop
        self.run_ok(ESCALATION, "repondre", T1, "a")

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual("test_review_no_result", self.shown_state(T1)["stop"]["reason"])

    def test_a_ticket_the_removed_test_review_stopped_without_a_resume_left_stays_stopped_and_is_raised_once(self):
        self.stopped_by_the_test_review(raised=False)
        self.earlier_resumes("stage_removed", 3)

        first_pass, second_pass = self.advance(CONVOY), self.advance(CONVOY)

        self.assertEqual([], self.of(first_pass, "resumed"))
        self.assertEqual([{"ticket": T1, "reason": "test_review_no_result"}],
                         self.of(first_pass, "tdd_stops")["escalated"])
        self.assertEqual([], self.of(second_pass, "tdd_stops"))
        self.assertEqual("test_review_no_result", self.shown_state(T1)["stop"]["reason"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    # --- a ticket stopped for an exhausted amendment reaches the operator (T45) ---

    def test_a_pass_raises_a_ticket_stopped_for_an_exhausted_amendment_naming_it_and_the_cause(self):
        self.amendment_exhausted()
        self.assertEqual([], self.needs())

        answer = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "reason": "amendment_exhausted"}], self.of(answer, "tdd_stops")["escalated"])
        needs = self.needs()
        self.assertEqual(1, len(needs), needs)
        self.assertIn(T1, needs[0])
        self.assertIn("amendement épuisé", needs[0])
        mails = self.log("mail")
        self.assertEqual(1, len(mails), mails)
        self.assertEqual("human", mails[0][1])

    def test_a_second_pass_on_the_same_exhausted_amendment_raises_nothing_more_and_the_state_shows_it_was_raised(self):
        self.amendment_exhausted()
        self.advance(CONVOY)
        self.assertIn("raised", self.shown_state(T1)["stop"])
        before = self.tickets_snapshot()
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))
        self.assertEqual([], self.log("mail"))
        self.assertEqual(before, self.tickets_snapshot())

    def test_a_ticket_stopped_for_an_exhausted_amendment_is_neither_merged_nor_resumed_and_the_others_go_on(self):
        self.amendment_exhausted(ceiling=1)
        self.assert_not_started(T2)

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([], self.resume_launches())
        self.assertNotIn("integration", next(c for c in answer["convoys"] if c["id"] == CONVOY))
        self.assertEqual("in_progress", self.bead(T1)["status"])
        self.assertEqual([T2], self.started(answer))
        self.assert_started_through_door(T2)
        self.assert_not_started(T3)

    def test_an_exhausted_amendment_the_door_could_not_raise_fails_the_pass_and_is_raised_by_the_next(self):
        self.amendment_exhausted()

        failed = self.advance(CONVOY, expect=EXIT_REFUSED, env={**self.env, "CONVOY_STATE_FAKE_MAIL_FAIL": "1"})

        self.assertIn("error", self.of(failed, "tdd_stops"))
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

        self.advance(CONVOY)

        self.assertIn("raised", self.shown_state(T1)["stop"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

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

    def test_a_finished_ticket_behind_the_integration_tip_goes_back_to_its_author_once_and_is_counted(self):
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        tip = self.finished(T1)
        self.integration_moved()

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "behind")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])
        self.assertEqual(["sling", "fx-worker", self.of(answer, "resumed")[0]["bead"], "fx-resume"],
                         self.resume_launches()[-1][:4])
        shown = self.shown_state(T1)
        self.assertEqual((1, None, f"ticket/{T1}", tip),
                         (shown["counters"]["resumes"], shown["exit"], shown["branch"], shown["tip"]))
        self.assertEqual(([], []), (self.code_review_launches(), self.evaluation_launches()))
        self.assertIsNone(shown["verdicts"].get("code_review"))
        self.assertNotIn(T1, [m["id"] for m in (self.integration_of(answer) or {}).get("merged", [])])
        self.assertEqual([], self.of(self.advance(CONVOY), "resumed"))
        self.assertEqual(1, self.resumes())

    def test_a_finished_ticket_that_holds_the_integration_tip_is_reviewed_and_not_resumed(self):
        self.integrated()
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.integration_moved()
        self.finished(T1)

        answer = self.advance(CONVOY)

        self.assertEqual(([], 0), (self.of(answer, "resumed"), self.resumes()))
        self.assertEqual(1, len(self.code_review_launches()))

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

    def test_a_ticket_parked_at_a_resume_its_red_merge_asked_for_names_that_cause_and_the_failing_tests(self):
        # af-w6xtw0: the operator read « 3 reprises » and not why the last one was.
        failing = " ; ".join(f"echo FAILED: tests/{name}-test.py" for name in ("a", "b", "c", "d"))
        self.integrated(regression=f"sh -c '{failing} ; exit 1'")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)  # the merge returns it: red tests on the merged result
        self.earlier_resumes("returned", 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        detail = self.park_of(T1)["detail"]
        self.assertIn("reprises épuisées pour la cause returned", detail)
        self.assertIn("dernière reprise enregistrée : returned", detail)
        self.assertIn("tests rouges sur le résultat fusionné", detail)
        self.assertIn("tests/a-test.py, tests/b-test.py, tests/c-test.py, …", detail)
        self.assertNotIn("tests/d-test.py", detail)

    def test_a_red_merge_whose_output_names_no_test_still_parks_with_the_merged_commit(self):
        self.integrated(regression="sh -c 'echo boom ; exit 1'")
        self.resumable()
        self.code_reviewed("favorable")
        self.evaluated()
        self.advance(CONVOY)
        self.finished(T1)
        self.advance(CONVOY)
        self.earlier_resumes("returned", 2)

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, "resumes_exhausted")], [(p["id"], p["cause"]) for p in self.of(answer, "parked")])
        detail = self.park_of(T1)["detail"]
        self.assertRegex(detail, r"tests rouges sur le résultat fusionné [0-9a-f]{7,12}\)$")

    def test_a_ticket_resumed_for_three_different_causes_is_not_parked_and_keeps_being_resumed(self):
        # ADR-0030 L2 (the af-ltchro case): an interruption, a correction
        # round and a commit after a verdict are three causes, none at its bound.
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)  # an interruption: one resume
        # A correction round, as bin/convoy-state open-correction counts it,
        # then a commit after a verdict, as invalidate-verdicts counts it.
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "parked"))
        self.assertIsNone(self.park_of(T1))
        self.assertEqual(2, self.shown_state(T1)["resumes_left"])
        # Interrupted once more, it is restarted.
        self.interrupted(T1, "auteur-2")
        again = self.advance(CONVOY)
        self.assertEqual([(T1, "interrupted")], [(r["id"], r["cause"]) for r in self.of(again, "resumed")])
        self.assertEqual(4, self.resumes())

    def test_a_ticket_at_the_last_resume_of_one_cause_is_parked_with_its_descendants_and_not_restarted(self):
        self.started_convoy()
        self.interrupted(T1, "auteur-1")
        self.advance(CONVOY)  # an interruption: one resume
        self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes", "--counter", "correction_rounds")
        for _ in range(3):  # three commits after a verdict: that cause is at its bound
            self.run_ok(STATE, "bump-counter", CONVOY, "--ticket", T1, "--counter", "resumes")
        self.write_log.write_text("")

        answer = self.advance(CONVOY)

        [parked] = self.of(answer, "parked")
        self.assertEqual((T1, "resumes_exhausted", [T1, T3]), (parked["id"], parked["cause"], parked["parked"]))
        self.assertIn("reprises épuisées pour la cause commit_after_verdict", self.park_of(T1)["detail"])
        for ticket_id in (T1, T3):
            park = self.park_of(ticket_id)
            self.assertEqual(("resumes_exhausted", T1), (park["cause"], park["origin"]), ticket_id)
        self.assertIsNone(self.park_of(T2))
        self.assertEqual([], self.slung())
        # Interrupted once more, it is not restarted.
        self.interrupted(T1, "auteur-2")
        again = self.advance(CONVOY)
        self.assertEqual(([], []), (self.of(again, "resumed"), self.slung()))
        self.assertEqual(5, self.resumes())

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

    def test_the_accepting_answer_to_a_planning_exception_naming_no_anchor_lifts_it_and_resumes_it(self):
        # ADR-0030 L5: every Planning Exception has an accept path.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        request = {"quoi": f"Planning Exception (semantic) sur {T1} : la Spec dit X, le produit fait Y",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."},
                                 {"option": "Accepter l'écart décrit", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "la Spec dit X, le produit fait Y", "--accept-option", "c")
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "planning_exception")
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking
        self.run_ok(ESCALATION, "repondre", T1, "c")

        answer = self.advance(CONVOY)

        self.assertEqual([(T1, [T1, T3])], [(entry["id"], entry["lifted"]) for entry in self.of(answer, "lifted")])
        self.assertEqual([(T1, "answered")], [(r["id"], r["cause"]) for r in self.of(answer, "resumed")])

    def already_green_excepted(self):
        """T1 stopped with all its criteria already green while its author
        session is alive; the author raises its Planning Exception, the
        request parks T1, then the session is over (ADR-0030 L5)."""
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")
        before_exception = self.advance(CONVOY)
        self.assertEqual([], self.of(before_exception, "tdd_stops"))
        request = {"quoi": f"Planning Exception (semantic) sur {T1} : critères tous déjà verts",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Accepter l'écart décrit", "consequence": "Le ticket reprend."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "critères tous déjà verts", "--accept-option", "b")
        self.run_ok(ESCALATION, "benjamin", T1, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, T1, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, T1, "--exit", "planning_exception")
        self.edit(sessions=[])
        parked = self.advance(CONVOY)
        self.assertEqual([], self.of(parked, "tdd_stops"))
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the parking

    def escalation_options(self, ticket_id):
        metadata = self.bead(ticket_id)["metadata"]
        return [entry["option"] for entry in json.loads(metadata["gc.escalation_que_faire"])]

    def test_a_ticket_whose_criteria_are_all_already_green_reaches_the_operator_once_its_exception_is_accepted(self):
        # ADR-0030 L5: « accept » lifts the parking, not the stop; the stop
        # then reaches the operator, once, instead of stalling the convoy.
        self.already_green_excepted()
        self.run_ok(ESCALATION, "repondre", T1, "b")

        answer = self.advance(CONVOY)

        self.assertEqual([T1], [entry["id"] for entry in self.of(answer, "lifted")])
        self.assertEqual([], self.of(answer, "resumed"))
        self.assertEqual([{"ticket": T1, "reason": "criterion_already_green"}], self.of(answer, "tdd_stops")["escalated"])
        needs = [line for line in self.needs() if T1 in line]
        self.assertEqual(1, len(needs), needs)
        self.assertIn("critères tous déjà verts", needs[0])
        # One decision, one request: close it as satisfied, or leave it
        # stopped; no second Planning Exception is offered (af-npz9v1.9).
        options = self.escalation_options(T1)
        self.assertTrue(any("satisfait" in option for option in options), options)
        self.assertFalse(any("Planning Exception" in option for option in options), options)

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    def test_an_already_green_ticket_whose_exception_is_answered_otherwise_stays_parked_and_its_stop_is_not_raised(self):
        self.already_green_excepted()
        self.run_ok(ESCALATION, "repondre", T1, "a")

        for _ in range(2):
            answer = self.advance(CONVOY)
            self.assertEqual(([], []), (self.of(answer, "lifted"), self.of(answer, "tdd_stops")))
        self.assertEqual("planning_exception", self.park_of(T1)["cause"])
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

    def test_an_already_green_ticket_whose_author_ended_without_an_exception_reaches_the_operator_once(self):
        # af-npz9v1.9: no silent block when the author never raises one.
        self.started_convoy()
        self.taken(T1, "auteur-1")
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")

        answer = self.advance(CONVOY)

        self.assertEqual([{"ticket": T1, "reason": "criterion_already_green"}], self.of(answer, "tdd_stops")["escalated"])
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))
        again = self.advance(CONVOY)
        self.assertEqual([], self.of(again, "tdd_stops"))
        self.assertEqual(1, len([line for line in self.needs() if T1 in line]))

    def test_an_exception_raised_before_the_already_green_stop_does_not_raise_it(self):
        # af-npz9v1.9: only an exception raised after the stop settles it.
        self.started_convoy()
        self.taken(T1, "auteur-1", alive=True)
        self.run_ok(STATE, "raise-planning-exception", CONVOY, T1, "--kind", "semantic",
                    "--summary", "une question plus ancienne", "--accept-option", "c")
        metadata = self.bead(T1)["metadata"]
        record = json.loads(metadata["gc.flow.planning_exceptions"])
        record["entries"][-1]["at"] = "2000-01-01T00:00:00Z"
        metadata["gc.flow.planning_exceptions"] = json.dumps(record)
        self.edit(T1, metadata=metadata)
        self.run_ok(STATE, "stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "tdd_stops"))
        self.assertNotIn("raised", self.shown_state(T1)["stop"])

    # --- the stops of the convoy: red integration branch, open Planning Exceptions (T21, af-cbp84n) ---

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


if __name__ == "__main__":
    unittest.main()
