#!/usr/bin/env python3
"""Criterion tests of R2 (af-cifk1e; Spec af-fgcw0d, user stories 129, 130
and 131, Testing Decisions 1, 7 and 8): the frise of a run read from a
tracker as the commands of the flow write it, once the sessions that worked
on it have ended.

Each case declares a dataset that holds a tracker -- the convoy of a D01
delivery, its tickets, the workflow mol-ticket-author run on each, its
steps and the attempts the sessions claimed, and the session beads the
supervisor leaves once a session ended -- and no session the supervisor
still lists, as in service when the sessions are over. It launches the
real cockpit on it with the launcher of the profile, bin/project-launch,
and reads the page GET /runs/run of that run as a headless Chromium
renders it.

Criterion 1: one lane per logical agent -- the agent the supervisor named
the session after (`agent_name`) --, its successive sessions in the same
lane with « Contexte · dernière session » and the role and model it ran
with (user story 130: the model its session was started with); two agents
of the same role at
work at the same time on two lanes. False if a new session of an agent
opens a lane of its own (the 84 lanes of the convoy af-strhoy, one per
session, seen on 22/10/2026), or if two agents at work at once share one.

Criterion 2: a stop of a ticket, an unfavourable verdict, a refused check
and a question to Benjamin without an answer each say their state --
arrêté, refusé, en attente -- and name the ticket they are about; only a
step that succeeded carries the mark of a success (✓). False if one of
them carries that mark, or if a job does not name its ticket -- the one it
serves, not another ticket of the run --, on the run of a D01 delivery as on
the run of a ticket of the old flow.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import launch_declared  # noqa: E402
from runs_destination import LaunchTree, lanes, observe, seconds  # noqa: E402

# The run of every case: a D01 delivery published on 22/10/2026 at 12:00
# Paris (10:00 UTC), whose tickets each had a workflow mol-ticket-author.
START = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
CONVOY, DIGEST = "af-r2conv", "sha256:r2-graph"
SUCCESS = "✓"


def at(minutes: float) -> str:
    """The instant `minutes` after the publication of the graph, as the
    tracker writes it."""
    return (START + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


class Tracker:
    """The beads the commands of the flow write for one D01 delivery, by
    their id: the convoy, then what each call adds to it."""

    def __init__(self) -> None:
        self.beads: dict[str, dict] = {CONVOY: {
            "title": "Notes partagées", "issue_type": "convoy", "status": "open", "created_at": at(0),
            "created_by": "benjamin",
            "metadata": {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": DIGEST, "gc.project_id": "agent-factory",
                         "gc.spec_id": "af-r2spec"},
        }}

    def ticket(self, bead_id: str, label: str, title: str, dispatched: float, **metadata) -> None:
        """A ticket of the graph, open, labelled `label` (gc.ticket_id),
        dispatched at `dispatched` to an author, with what else the flow
        wrote on it."""
        models = {"author": {"agent": "delivery-author", "at": at(dispatched), "model": "claude-opus-5-5",
                             "provider": "claude-standard"}}
        self.beads[bead_id] = {
            "title": f"{label} — {title}", "issue_type": "task", "status": "open", "created_at": at(0),
            "metadata": {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": DIGEST, "gc.ticket_id": label,
                         "gc.flow.gate.dispatch": json.dumps({"at": at(dispatched)}),
                         "gc.flow.models": json.dumps(models), **metadata},
        }

    def session(self, bead_id: str, agent: str, begin: float, end: float, model: str) -> None:
        """A session of the pool delivery-author, named by the supervisor
        after the agent `agent` (delivery-author-<slot>) and started with
        `model`, ended: the session bead the supervisor leaves."""
        self.beads[bead_id] = {
            "title": agent, "issue_type": "session", "status": "closed", "created_at": at(begin),
            "closed_at": at(end), "close_reason": "session drained: pool slot retired by reconciler",
            "labels": [f"agent:{agent}", "gc:session"],
            "metadata": {"agent_name": agent, "template": "delivery-author", "provider": "claude-standard",
                         "command": f"/home/benja/.local/bin/claude --strict-mcp-config --model {model} --effort medium",
                         "session_name": f"delivery-author-{bead_id}", "pool_slot": agent.rsplit("-", 1)[-1]},
        }

    def workflow(self, root: str, ticket: str, begin: float) -> None:
        """The workflow mol-ticket-author run on an input convoy that
        tracks `ticket`."""
        wrapper = f"{root}-input"
        self.beads[wrapper] = {
            "title": f"input convoy for {ticket}", "issue_type": "convoy", "status": "open", "created_at": at(begin),
            "metadata": {"gc.synthetic": "true"},
            "dependencies": [{"issue_id": wrapper, "depends_on_id": ticket, "type": "tracks"}],
        }
        self.beads[root] = {
            "title": "mol-ticket-author", "issue_type": "task", "status": "in_progress", "created_at": at(begin),
            "metadata": {"gc.kind": "workflow", "gc.formula_name": "mol-ticket-author", "gc.input_convoy_id": wrapper,
                         "gc.routed_to": "delivery-author", "gc.step_id": "mol-ticket-author"},
        }

    def step(self, root: str, step: str, session: str, begin: float, end: float, outcome: str = "pass") -> None:
        """The step `step` of the workflow `root`, claimed by `session`
        at `begin` and closed at `end` with `outcome`: the ralph step and
        its attempt."""
        logical = f"{root}-{step}"
        self.beads[logical] = {
            "title": step, "issue_type": "task", "status": "closed", "created_at": at(begin), "closed_at": at(end),
            "metadata": {"gc.kind": "ralph", "gc.check_mode": "exec", "gc.root_bead_id": root, "gc.step_id": step,
                         "gc.routed_to": "core.control-dispatcher", "gc.outcome": outcome},
        }
        self.beads[f"{logical}-attempt-1"] = {
            "title": step, "issue_type": "task", "status": "closed", "created_at": at(begin), "closed_at": at(end),
            "assignee": session,
            "metadata": {"gc.logical_bead_id": logical, "gc.root_bead_id": root, "gc.attempt": "1",
                         "gc.step_id": step, "gc.ralph_step_id": step, "gc.control_for": step,
                         "gc.routed_to": "delivery-author", "gc.session_id": session,
                         "gc.session_name": f"delivery-author-{session}", "gc.claimed_at": at(begin),
                         "gc.outcome": outcome},
        }

    def check(self, root: str, bead_id: str, title: str, begin: float, end: float, outcome: str) -> None:
        """A check of the workflow `root`, run from `begin` to `end`, that
        ended in `outcome`."""
        self.beads[bead_id] = {
            "title": title, "issue_type": "task", "status": "closed", "created_at": at(begin), "closed_at": at(end),
            "metadata": {"gc.kind": "check", "gc.root_bead_id": root, "gc.outcome": outcome},
        }

    def dataset(self, name: str) -> dict:
        return {"generated_at": "2026-10-22T12:00:00+02:00", "synthetic": True, "ui": {"id": name},
                "tracker": {"beads": json.loads(json.dumps(self.beads))}}


def names_ticket(job: str, label: str, title: str) -> bool:
    """Whether the text of a job names the ticket labelled `label` and
    titled `title`: by its label, or by its title."""
    return bool(re.search(rf"(?<![\w-]){re.escape(label)}(?![\w-])", job)) or title in job


class RunsDestinationTracker(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def frise(self, tracker: Tracker, name: str, run: str = CONVOY, title: str = "Notes partagées") -> list[dict]:
        """The lanes of the frise of the run `run`, titled `title`, as the
        cockpit launched on the dataset of `tracker` draws them, 1440 px
        wide."""
        address = launch_declared(self.tree, name, tracker.dataset(name))
        reading = observe(address, f"/runs/run?id={run}")[0][0]
        self.assertEqual(title, next((a["text"] for a in reading["anchors"] if a["name"] == "h1"), ""),
                         f"the page is not the frise of the run {run}")
        return lanes(reading)

    def agent_lanes(self, served: list[dict]) -> list[dict]:
        """The lanes of the frise after Humain and Code, which come first."""
        self.assertEqual(["Benjamin", "Code"], [lane["name"].split()[0] if lane["name"] else "" for lane in served[:2]],
                         "the frise does not begin with the lanes Humain and Code")
        return served[2:]

    def test_the_successive_sessions_of_an_agent_are_one_lane_with_the_context_of_the_last(self):
        tracker = Tracker()
        tracker.ticket("af-r2t1", "N1", "Recherche dans les notes", 1)
        tracker.ticket("af-r2t3", "N3", "Partage des notes", 20)
        # delivery-author-1 worked on N1 in a session, then on N3 in another,
        # both started with claude-opus-5-5.
        tracker.session("af-wisp-r2s1", "delivery-author-1", 1, 12, "claude-opus-5-5")
        tracker.session("af-wisp-r2s3", "delivery-author-1", 20, 35, "claude-opus-5-5")
        tracker.workflow("af-r2w1", "af-r2t1", 1)
        tracker.step("af-r2w1", "workspace", "af-wisp-r2s1", 1, 3)
        tracker.step("af-r2w1", "red", "af-wisp-r2s1", 3, 11)
        tracker.workflow("af-r2w3", "af-r2t3", 20)
        tracker.step("af-r2w3", "workspace", "af-wisp-r2s3", 20, 23)
        tracker.step("af-r2w3", "red", "af-wisp-r2s3", 23, 34)
        agents = self.agent_lanes(self.frise(tracker, "r2-successive-sessions"))
        self.assertEqual(1, len(agents),
                         f"two sessions of delivery-author-1 are not one lane: {[lane['name'] for lane in agents]}")
        lane = agents[0]
        self.assertTrue(lane["name"].startswith("delivery-author-1"),
                        f"the lane does not say which agent it is: « {lane['name']} »")
        self.assertIn("Auteur", lane["name"], f"the lane does not say the role of its agent: « {lane['name']} »")
        self.assertIn("claude-opus-5-5", lane["name"],
                      f"the lane does not say the model its agent ran with: « {lane['name']} »")
        self.assertIn("Contexte · dernière session", lane["name"],
                      f"the lane does not hold the context of the last session: « {lane['name']} »")
        # Its jobs, those of both sessions: 2 min and 8 min on N1, 3 min and
        # 11 min on N3.
        self.assertEqual(sorted([120, 480, 180, 660]), sorted(seconds(job) or 0 for job in lane["jobs"]),
                         f"the lane does not hold the jobs of both sessions: {lane['jobs']}")

    def test_two_authors_at_work_at_the_same_time_keep_a_lane_each(self):
        tracker = Tracker()
        tracker.ticket("af-r2t1", "N1", "Recherche dans les notes", 1)
        tracker.ticket("af-r2t2", "N2", "Export des notes", 2)
        # delivery-author-1 on N1 with claude-opus-5-5 and delivery-author-2
        # on N2 with claude-sonnet-5-5, at once.
        tracker.session("af-wisp-r2s1", "delivery-author-1", 1, 12, "claude-opus-5-5")
        tracker.session("af-wisp-r2s2", "delivery-author-2", 2, 14, "claude-sonnet-5-5")
        tracker.workflow("af-r2w1", "af-r2t1", 1)
        tracker.step("af-r2w1", "workspace", "af-wisp-r2s1", 1, 3)
        tracker.step("af-r2w1", "red", "af-wisp-r2s1", 3, 11)
        tracker.workflow("af-r2w2", "af-r2t2", 2)
        tracker.step("af-r2w2", "workspace", "af-wisp-r2s2", 2, 6)
        tracker.step("af-r2w2", "red", "af-wisp-r2s2", 6, 13)
        agents = self.agent_lanes(self.frise(tracker, "r2-two-authors"))
        self.assertEqual(2, len(agents),
                         f"two authors at work at once are not two lanes: {[lane['name'] for lane in agents]}")
        first, second = agents
        self.assertTrue(first["name"].startswith("delivery-author-1"), f"« {first['name']} »")
        self.assertTrue(second["name"].startswith("delivery-author-2"), f"« {second['name']} »")
        self.assertIn("claude-opus-5-5", first["name"], f"« {first['name']} »")
        self.assertIn("claude-sonnet-5-5", second["name"], f"« {second['name']} »")
        for lane in agents:
            self.assertIn("Auteur", lane["name"], f"the lane does not say the role of its agent: « {lane['name']} »")
            self.assertIn("Contexte · dernière session", lane["name"])
        # 2 min and 8 min for delivery-author-1; 4 min and 7 min for
        # delivery-author-2.
        self.assertEqual([120, 480], sorted(seconds(job) or 0 for job in first["jobs"]), first["jobs"])
        self.assertEqual([240, 420], sorted(seconds(job) or 0 for job in second["jobs"]), second["jobs"])

    def test_a_stop_a_refusal_and_a_question_waiting_say_their_state_and_only_a_success_is_ticked(self):
        tracker = Tracker()
        # N1 stopped at 15 min, N2 under an unfavourable fidelity verdict at
        # 18 min, N3 with a refused check and a question to Benjamin he has
        # not answered; the start of N1 and a check of N2 succeeded.
        tracker.ticket("af-r2t1", "N1", "Recherche dans les notes", 1, **{
            "gc.flow.stop": json.dumps({"at": at(15), "reason": "technically_blocked",
                                        "detail": "Le produit ne démarre pas au commit de départ"})})
        tracker.ticket("af-r2t2", "N2", "Export des notes", 2, **{
            "gc.flow.verdict.fidelity": json.dumps({"at": at(18), "commit": "5b2b3bd", "state": "unfavorable"})})
        tracker.ticket("af-r2t3", "N3", "Partage des notes", 20, **{
            "gc.escalation_horodatage": at(25), "gc.escalation_pourquoi": "Quel format de lien garder ?"})
        tracker.session("af-wisp-r2s1", "delivery-author-1", 1, 15, "claude-opus-5-5")
        tracker.workflow("af-r2w1", "af-r2t1", 1)
        tracker.step("af-r2w1", "workspace", "af-wisp-r2s1", 1, 3)
        tracker.workflow("af-r2w2", "af-r2t2", 2)
        tracker.check("af-r2w2", "af-r2w2-scope", "Contrôle du périmètre", 4, 5, "pass")
        tracker.workflow("af-r2w3", "af-r2t3", 20)
        tracker.check("af-r2w3", "af-r2w3-demo", "Contrôle de la démonstration", 21, 22, "fail")
        served = self.frise(tracker, "r2-job-states")
        jobs = [job for lane in served for job in lane["jobs"]]

        def the(pattern: str) -> str:
            found = [job for job in jobs if re.search(pattern, job)]
            self.assertEqual(1, len(found), f"not one job of the frise matches {pattern}: {jobs}")
            return found[0]

        # (the job, the state it says, the ticket it is about)
        expected = [
            (the(r"(?i)arr[êe]t"), "arrêté", ("N1", "Recherche dans les notes")),
            (the(r"Fidélité"), "refusé", ("N2", "Export des notes")),
            (the(r"Contrôle de la démonstration"), "refusé", ("N3", "Partage des notes")),
            (the(r"Question"), "en attente", ("N3", "Partage des notes")),
        ]
        for job, state, (label, title) in expected:
            self.assertIn(state, job.lower(), f"the job does not say it is {state}: « {job} »")
            self.assertNotIn(SUCCESS, job, f"a job {state} carries the mark of a success: « {job} »")
            self.assertTrue(names_ticket(job, label, title), f"the job does not name its ticket {label}: « {job} »")
        for job in (the(r"Prendre le ticket"), the(r"Contrôle du périmètre")):
            self.assertIn(SUCCESS, job, f"a step that succeeded does not carry the mark of a success: « {job} »")

    def test_each_job_of_the_frise_names_the_ticket_it_serves(self):
        tracker = Tracker()
        # Three tickets, each launched, with the jobs of its own: N1 started
        # by delivery-author-1 then stopped; N2 a check of its scope and a
        # fidelity verdict; N3 a check of its demonstration and a question.
        tracker.ticket("af-r2t1", "N1", "Recherche dans les notes", 1, **{
            "gc.flow.stop": json.dumps({"at": at(15), "reason": "technically_blocked",
                                        "detail": "Le produit ne démarre pas au commit de départ"})})
        tracker.ticket("af-r2t2", "N2", "Export des notes", 2, **{
            "gc.flow.verdict.fidelity": json.dumps({"at": at(18), "commit": "5b2b3bd", "state": "unfavorable"})})
        tracker.ticket("af-r2t3", "N3", "Partage des notes", 20, **{
            "gc.escalation_horodatage": at(25), "gc.escalation_pourquoi": "Quel format de lien garder ?"})
        tracker.session("af-wisp-r2s1", "delivery-author-1", 1, 15, "claude-opus-5-5")
        tracker.workflow("af-r2w1", "af-r2t1", 1)
        tracker.step("af-r2w1", "workspace", "af-wisp-r2s1", 1, 3)
        tracker.workflow("af-r2w2", "af-r2t2", 2)
        tracker.check("af-r2w2", "af-r2w2-scope", "Contrôle du périmètre", 4, 5, "pass")
        tracker.workflow("af-r2w3", "af-r2t3", 20)
        tracker.check("af-r2w3", "af-r2w3-demo", "Contrôle de la démonstration", 21, 22, "fail")
        served = self.frise(tracker, "r2-job-tickets")
        jobs = [job for lane in served for job in lane["jobs"]]
        tickets = {"N1": "Recherche dans les notes", "N2": "Export des notes", "N3": "Partage des notes"}

        def named(job: str) -> list[str]:
            return [label for label, title in tickets.items() if names_ticket(job, label, title)]

        # Each job of a ticket, by what it says, and the one ticket it names.
        expected = [(r"Prendre le ticket", "N1"), (r"(?i)arr[êe]t", "N1"),
                    (r"Contrôle du périmètre", "N2"), (r"Fidélité", "N2"),
                    (r"Contrôle de la démonstration", "N3"), (r"Question", "N3")]
        for pattern, label in expected:
            found = [job for job in jobs if re.search(pattern, job)]
            self.assertEqual(1, len(found), f"not one job of the frise matches {pattern}: {jobs}")
            self.assertEqual([label], named(found[0]),
                             f"the job does not name the ticket it serves, {label}, and it alone: « {found[0]} »")
        # The launch of each ticket names that ticket.
        launched = [job for job in jobs if "Ticket lancé" in job]
        self.assertEqual([["N1"], ["N2"], ["N3"]], sorted(named(job) for job in launched),
                         f"the launches do not each name their own ticket: {launched}")
        self.assertEqual(9, len(jobs), f"the frise has not the nine jobs of the run: {jobs}")

    def test_each_job_of_a_run_of_the_old_flow_names_its_ticket(self):
        tracker = Tracker()
        # A ticket of the old flow: no convoy carries its graph; an author
        # launched on it at 1 min, its tests proven red at 5 min, stopped at
        # 10 min.
        old = {"author": {"agent": "delivery-author", "at": at(1), "model": "claude-opus-5-5",
                          "provider": "claude-standard"}}
        tracker.beads["af-r2old"] = {
            "title": "N4 — Archivage des notes", "issue_type": "task", "status": "open", "created_at": at(0),
            "metadata": {"gc.ticket_id": "N4", "gc.flow.gate.dispatch": json.dumps({"at": at(1)}),
                         "gc.flow.models": json.dumps(old), "gc.flow.tdd.red": json.dumps({"at": at(5)}),
                         "gc.flow.stop": json.dumps({"at": at(10), "reason": "technically_blocked",
                                                     "detail": "Le produit ne démarre pas"})},
        }
        served = self.frise(tracker, "r2-old-flow", run="af-r2old", title="Archivage des notes")
        jobs = [job for lane in served for job in lane["jobs"]]
        self.assertGreaterEqual(len(jobs), 4, f"the frise has not the jobs of the run: {jobs}")
        self.assertEqual([], [job for job in jobs if not names_ticket(job, "N4", "Archivage des notes")],
                         "a job of the run of the old flow does not name its ticket N4")
        stop = next((job for job in jobs if re.search(r"(?i)arr[êe]t", job)), "")
        self.assertIn("arrêté", stop.lower(), f"the stop of N4 does not say it is stopped: « {stop} »")
        self.assertNotIn(SUCCESS, stop, f"the stop of N4 carries the mark of a success: « {stop} »")


if __name__ == "__main__":
    unittest.main()
