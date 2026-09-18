#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = 1789555200.0  # 2026-09-16T10:40:00Z, fixed so throttling is deterministic
sys.path.insert(0, str(ROOT / "lib"))

from factory_campaign import is_ladder_bead, plan_idle_ladder, plan_transition  # noqa: E402


def metadata(state="active"):
    value = {
        "gc.current_jit": "none", "gc.needs_benjamin": "none",
        "gc.campaign_mode": "automatic", "gc.campaign_state": state,
        "gc.campaign_candidate": "af-cm1l",
        "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
        "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
        "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
        "gc.resume_mode": "automatic_campaign",
        "gc.resume_condition": "Le Mayor enchaîne le premier candidat éligible",
    }
    return value


def status(next_id="af-next", result=None, mode="automatic_campaign"):
    campaign = {
        "enabled": True, "state": "active", "blocked": False,
        "wake_key": None, "wake_state": "none",
    }
    return {
        "contract": "agent-factory-human-state/v1", "campaign": campaign,
        "resume": {"mode": mode},
        "result": result or {"id": None, "state": "none"},
        "next_candidate": ({"id": next_id} if next_id else None),
    }


def status_with_release_mismatch(node_id="af-node9", other_id="af-other"):
    return {
        "contract": "agent-factory-human-state/v1",
        "campaign": {"enabled": True, "state": "active", "blocked": False, "wake_key": None, "wake_state": "none"},
        "resume": {"mode": "automatic_campaign"},
        "result": {"id": None, "state": "none"},
        "next_candidate": {"id": node_id},
        "release": {
            "contract": "agent-factory-product-release/v1",
            "state": "approved",
            "campaign": {"selected": {"work_ref": other_id, "criterion_refs": []}},
        },
    }


class CampaignFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state_file = self.root / "coordination.json"
        self.status_file = self.root / "status.json"
        self.log_file = self.root / "calls.log"
        self.lock_file = self.root / "campaign.lock"
        self.node_dir = self.root / "nodes"
        self.node_dir.mkdir()
        self.fixture = ROOT / "tests" / "fixtures" / "mayor-campaign"
        self.env = {
            **os.environ,
            "GC_BIN": str(self.fixture / "gc"),
            "SAYMYNAME_STATUS_BIN": str(self.fixture / "status"),
            "SAYMYNAME_PRODUCT_QUEUE_BIN": str(self.fixture / "product-queue"),
            "CAMPAIGN_STATE_FILE": str(self.state_file),
            "CAMPAIGN_STATUS_FILE": str(self.status_file),
            "CAMPAIGN_CALL_LOG": str(self.log_file),
            "CAMPAIGN_LOCK_FILE": str(self.lock_file),
            "CAMPAIGN_NODE_DIR": str(self.node_dir),
            # The breaker tests below assert the count logic alone; the
            # wall-clock span has its own test.
            "CAMPAIGN_FAILURE_MIN_SPAN_SECONDS": "0",
        }
        self.write_state(metadata())
        self.write_status(status())

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, value):
        self.state_file.write_text(json.dumps({"id": "af-1vr4", "metadata": value}), encoding="utf-8")

    def write_status(self, value):
        self.status_file.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, *args, check=True, extra_env=None):
        return subprocess.run(
            (str(ROOT / "bin" / "mayor-campaign"), *args), cwd=ROOT,
            env={**self.env, **(extra_env or {})}, text=True, capture_output=True, check=check,
        )

    def current_metadata(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))["metadata"]

    def node_metadata(self, node_id):
        return json.loads((self.node_dir / f"{node_id}.json").read_text(encoding="utf-8"))["metadata"]

    def mail_count(self):
        if not self.log_file.exists():
            return 0
        return sum("mail send mayor" in line for line in self.log_file.read_text(encoding="utf-8").splitlines())


class MayorCampaignTest(CampaignFixture, unittest.TestCase):
    def test_plans_only_one_authorized_transition(self):
        planned = plan_transition(status())
        self.assertEqual(("wake_mayor", "materialize:af-next"), (planned["action"], planned["wake_key"]))
        active = status(result={"id": "af-exec", "state": "active"}, mode="active_delivery")
        self.assertEqual("none", plan_transition(active)["action"])
        finalizing = status(result={"id": "af-exec", "state": "active"}, mode="mayor_finalization")
        finalize = plan_transition(finalizing)
        self.assertEqual("finalize:af-exec", finalize["wake_key"])
        # It says what finalizing means, so an already-closed result is not
        # mistaken for finished work (af-7700, 2026-09-16).
        self.assertIn("./bin/deliver-close af-exec", finalize["message"])
        self.assertIn("jamais `gc bd close`", finalize["message"])
        self.assertIn("gc.last_delivered", finalize["message"])
        materialized = status(result={"id": "af-exec", "state": "materialized"}, mode="materialized_without_agent")
        self.assertEqual("resume:af-exec", plan_transition(materialized)["wake_key"])

    def test_activation_is_guarded_and_requires_materialized_campaign(self):
        self.write_state({"gc.current_jit": "none", "gc.needs_benjamin": "none"})
        denied = self.invoke("activate", "af-cm1l", "af-hho5", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.invoke("activate", "af-cm1l", "af-hho5", "--mayor")
        value = self.current_metadata()
        self.assertEqual(("automatic", "active", "af-cm1l"), (
            value["gc.campaign_mode"], value["gc.campaign_state"], value["gc.campaign_candidate"],
        ))
        again = self.invoke("activate", "af-cm1l", "af-hho5", "--mayor")
        self.assertIn("ALREADY ACTIVE", again.stdout)

    def test_activation_never_overwrites_blocked_or_human_resume_state(self):
        blocked = metadata("blocked")
        blocked.update({
            "gc.campaign_block_kind": "admin", "gc.campaign_cause": "ADMIN requise",
            "gc.campaign_owner": "Benjamin", "gc.campaign_action": "Autoriser l'action exacte",
        })
        self.write_state(blocked)
        denied = self.invoke("activate", "af-cm1l", "af-hho5", "--mayor", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.assertEqual(("blocked", "ADMIN requise"), (
            self.current_metadata()["gc.campaign_state"], self.current_metadata()["gc.campaign_cause"],
        ))

        completed = metadata("completed")
        completed.update({
            "gc.campaign_owner": "none",
            "gc.campaign_action": "Aucune action immédiate",
        })
        self.write_state(completed)
        denied = self.invoke("activate", "af-cm1l", "af-hho5", "--mayor", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.assertEqual("completed", self.current_metadata()["gc.campaign_state"])

        inactive = {"gc.current_jit": "none", "gc.needs_benjamin": "Choisir le contrat"}
        self.write_state(inactive)
        denied = self.invoke("activate", "af-cm1l", "af-hho5", "--mayor", check=False)
        self.assertIn("NEEDS BENJAMIN", denied.stderr)
        self.assertNotIn("gc.campaign_mode", self.current_metadata())

        dependency = {
            "gc.current_jit": "none", "gc.needs_benjamin": "none",
            "gc.resume_mode": "automatic_dependency",
        }
        self.write_state(dependency)
        denied = self.invoke("activate", "af-cm1l", "af-hho5", "--mayor", check=False)
        self.assertIn("automatic_dependency", denied.stderr)
        self.assertNotIn("gc.campaign_mode", self.current_metadata())

    def test_shared_lock_serializes_concurrent_activation(self):
        self.write_state({"gc.current_jit": "none", "gc.needs_benjamin": "none"})
        if self.log_file.exists():
            self.log_file.unlink()
        command = (str(ROOT / "bin" / "mayor-campaign"), "activate", "af-cm1l", "af-hho5", "--mayor")
        env = {**self.env, "CAMPAIGN_UPDATE_DELAY": "0.2"}
        first = subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first_output = first.communicate(timeout=10)
        second_output = second.communicate(timeout=10)
        self.assertEqual((0, 0), (first.returncode, second.returncode), (first_output, second_output))
        outputs = first_output[0] + second_output[0]
        self.assertIn("ACTIVATED", outputs)
        self.assertIn("ALREADY ACTIVE", outputs)
        updates = [
            line for line in self.log_file.read_text(encoding="utf-8").splitlines()
            if "bd update af-1vr4" in line
        ]
        self.assertEqual(1, len(updates))

    def test_restart_idempotency_and_pending_recovery(self):
        self.invoke("sentinel")
        self.invoke("sentinel")
        self.assertEqual(1, self.mail_count())
        value = self.current_metadata()
        self.assertEqual(("materialize:af-next", "sent"), (
            value["gc.campaign_wake_key"], value["gc.campaign_wake_state"],
        ))

        value["gc.campaign_wake_state"] = "pending"
        self.write_state(value)
        self.invoke("sentinel")
        self.assertEqual(2, self.mail_count())
        self.assertEqual("sent", self.current_metadata()["gc.campaign_wake_state"])
        calls = self.log_file.read_text(encoding="utf-8")
        for forbidden in ("bd create", "product-queue materialize", "sling", "gh pr", "bd close"):
            self.assertNotIn(forbidden, calls)

    def test_notification_uses_the_configured_mayor_sender(self):
        self.invoke("sentinel")

        calls = self.log_file.read_text(encoding="utf-8")
        self.assertIn("mail send mayor --from mayor", calls)
        self.assertNotIn("mayor-campaign-sentinel", calls)
        self.assertEqual("sent", self.current_metadata()["gc.campaign_wake_state"])

    def test_a_killed_tick_is_recorded_distinctly_not_as_a_command_failure(self):
        # C8: the sentinel order kills the whole tick at 50s with no trace at
        # all (31 kills in 24h, live). A tick that runs past its own 40s
        # internal budget must record that fact and must NOT count toward
        # FAILURE_THRESHOLD -- it is a duration problem, not a bad command.
        result = self.invoke("sentinel", check=False, extra_env={"CAMPAIGN_TICK_DEADLINE_SECONDS": "0"})
        self.assertEqual(1, result.returncode)
        self.assertIn("TICK_TIMEOUT", result.stderr)
        meta = self.current_metadata()
        self.assertIn("gc.campaign_last_tick_timeout", meta)
        self.assertEqual("0", meta.get("gc.campaign_failure_count", "0"))
        self.assertEqual(0, self.mail_count())

    def test_three_failures_persist_durable_block_with_exact_recovery(self):
        for expected in (1, 2, 3):
            result = self.invoke("sentinel", check=False, extra_env={"CAMPAIGN_STATUS_FAIL": "1"})
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(str(expected), self.current_metadata()["gc.campaign_failure_count"])
        value = self.current_metadata()
        self.assertEqual(("blocked", "durable_failure", "Mayor"), (
            value["gc.campaign_state"], value["gc.campaign_block_kind"], value["gc.campaign_owner"],
        ))
        self.assertIn("mayor-campaign resume --mayor", value["gc.campaign_action"])
        noop = self.invoke("sentinel")
        self.assertIn("campaign blocked", noop.stdout)

    def test_a_short_failure_burst_is_not_durable_until_it_spans_wall_clock_time(self):
        # 2026-09-17: three 1-minute ticks failing while the Mayor was mid-turn
        # (then under load) paged a false durable failure within ~3 minutes.
        span = {"CAMPAIGN_STATUS_FAIL": "1", "CAMPAIGN_FAILURE_MIN_SPAN_SECONDS": "600"}
        for offset in (0, 60, 120, 180):
            result = self.invoke("sentinel", check=False,
                                 extra_env={**span, "CAMPAIGN_NOW": str(NOW + offset)})
            self.assertNotEqual(0, result.returncode)
            self.assertIn("automatic retry", result.stderr)
        value = self.current_metadata()
        self.assertEqual("4", value["gc.campaign_failure_count"])
        self.assertEqual("active", value["gc.campaign_state"])
        result = self.invoke("sentinel", check=False,
                             extra_env={**span, "CAMPAIGN_NOW": str(NOW + 600)})
        self.assertIn("durable failure", result.stderr)
        value = self.current_metadata()
        self.assertEqual(("blocked", "durable_failure"), (
            value["gc.campaign_state"], value["gc.campaign_block_kind"],
        ))

    def test_durable_failure_tied_to_one_node_quarantines_only_that_node(self):
        self.write_status(status_with_release_mismatch())
        for expected in (1, 2, 3):
            result = self.invoke("sentinel", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("af-node9", result.stderr)

        # The failing node alone is quarantined, with a repair item opened for it.
        node = self.node_metadata("af-node9")
        self.assertEqual("blocked_durable_failure", node["gc.queue_state"])
        calls = self.log_file.read_text(encoding="utf-8")
        self.assertIn("bd create", calls)
        self.assertIn("af-node9", calls)

        # The campaign itself was never blocked -- only the local node was.
        coordination = self.current_metadata()
        self.assertEqual("active", coordination["gc.campaign_state"])
        self.assertEqual("0", coordination.get("gc.campaign_failure_count", "0"))

        # The rest of the campaign keeps going: a different candidate wakes the Mayor normally.
        self.write_status(status(next_id="af-next2"))
        resumed = self.invoke("sentinel")
        self.assertIn("materialize:af-next2", resumed.stdout)

    def test_malformed_coordination_is_counted_and_store_outage_is_explicit(self):
        malformed = metadata()
        malformed["gc.campaign_state"] = "unknown"
        self.write_state(malformed)
        for expected in (1, 2, 3):
            result = self.invoke("sentinel", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(str(expected), self.current_metadata()["gc.campaign_failure_count"])
        value = self.current_metadata()
        self.assertEqual(("blocked", "durable_failure"), (
            value["gc.campaign_state"], value["gc.campaign_block_kind"],
        ))

        before = json.dumps(value, sort_keys=True)
        unavailable = self.invoke(
            "sentinel", check=False, extra_env={"CAMPAIGN_COORDINATION_FAIL": "1"},
        )
        self.assertIn("fail-closed", unavailable.stderr)
        self.assertIn("non persistable", unavailable.stderr)
        self.assertEqual(before, json.dumps(self.current_metadata(), sort_keys=True))

    def test_block_resume_and_complete_lifecycle_are_mayor_guarded(self):
        self.invoke(
            "block", "--kind", "admin", "--cause", "Rotation ADMIN requise",
            "--owner", "Benjamin", "--action", "Autoriser précisément la rotation", "--mayor",
        )
        self.assertEqual("blocked", self.current_metadata()["gc.campaign_state"])
        self.invoke("resume", "--mayor")
        self.assertEqual("active", self.current_metadata()["gc.campaign_state"])
        self.write_status(status(next_id=None, mode="no_candidate"))
        self.invoke("complete", "--mayor")
        self.assertEqual("completed", self.current_metadata()["gc.campaign_state"])
        completed = status(next_id=None, mode="no_candidate")
        completed["campaign"]["state"] = "completed"
        self.write_status(completed)
        # A completed product campaign is not an idle factory (ADR-0016 s.7):
        # with no Factory bead ready, it walks the generative rungs, once
        # each, then the default-enabled improvement axis (sec4)...
        first = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW)}).stdout
        self.assertIn("ladder:tests:", first)
        second = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW + 60)}).stdout
        self.assertIn("ladder:docs:", second)
        third = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW + 120)}).stdout
        self.assertIn("ladder:axis:code-review", third)
        # ...and only then rests, without mailing anyone.
        fourth = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW + 180)}).stdout
        self.assertIn("ladder_rested", fourth)
        self.assertEqual(3, self.mail_count())

    def test_activate_and_resume_record_the_last_valid_candidate_and_condition(self):
        # ADR-0023 / af-hihkg: repair --mayor can only restore what activate
        # and resume have been recording all along.
        self.write_state({"gc.current_jit": "none", "gc.needs_benjamin": "none"})
        self.invoke("activate", "af-cm1l", "af-hho5", "--mayor")
        value = self.current_metadata()
        self.assertEqual("af-cm1l", value["gc.campaign_candidate_last"])
        self.assertEqual(value["gc.campaign_condition"], value["gc.campaign_condition_last"])

        self.invoke(
            "block", "--kind", "admin", "--cause", "Rotation ADMIN requise",
            "--owner", "Benjamin", "--action", "Autoriser précisément la rotation", "--mayor",
        )
        self.invoke("resume", "--mayor")
        value = self.current_metadata()
        self.assertEqual(value["gc.campaign_candidate"], value["gc.campaign_candidate_last"])
        self.assertEqual(value["gc.campaign_condition"], value["gc.campaign_condition_last"])

    def test_repair_restores_missing_candidate_and_normalises_empty_pointers(self):
        # Replays the 2026-09-18 08:43Z incident: gc.campaign_candidate went
        # missing by a hand-write while the campaign stayed marked active, and
        # gc.current held an empty string instead of "none". No door could
        # repair it before this one -- activate refuses an already-active
        # campaign.
        broken = metadata()
        broken["gc.campaign_candidate_last"] = broken["gc.campaign_candidate"]
        broken["gc.campaign_condition_last"] = broken["gc.campaign_condition"]
        del broken["gc.campaign_candidate"]
        broken["gc.current"] = ""
        self.write_state(broken)

        result = self.invoke("repair", "--mayor")
        self.assertIn("FIXED: gc.campaign_candidate -> af-cm1l", result.stdout)
        self.assertIn("FIXED: gc.current -> none", result.stdout)
        value = self.current_metadata()
        self.assertEqual("af-cm1l", value["gc.campaign_candidate"])
        self.assertEqual("none", value["gc.current"])

        # Healthy again with no further hand-write: one guard run (repair,
        # then the ordinary sentinel tick) and the campaign is back to normal.
        healthy = self.invoke("sentinel")
        self.assertEqual(0, healthy.returncode)

    def test_repair_requires_the_mayor_guard(self):
        broken = metadata()
        del broken["gc.campaign_candidate"]
        self.write_state(broken)
        denied = self.invoke("repair", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.assertNotIn("gc.campaign_candidate", self.current_metadata())

    def test_repair_is_a_noop_on_a_healthy_campaign(self):
        result = self.invoke("repair", "--mayor")
        self.assertIn("NOOP", result.stdout)

    def test_repair_blocks_with_admin_cause_when_no_last_valid_pair_exists(self):
        # The genuinely unrecoverable shape: no candidate/condition, and no
        # history to restore from either (repair predates this campaign, or
        # both were wiped together). Repair must not guess a candidate.
        broken = metadata()
        del broken["gc.campaign_candidate"]
        del broken["gc.campaign_condition"]
        self.write_state(broken)

        result = self.invoke("repair", "--mayor")
        self.assertIn("FIXED: gc.campaign_state -> blocked", result.stdout)
        value = self.current_metadata()
        self.assertEqual("blocked", value["gc.campaign_state"])
        self.assertEqual("admin", value["gc.campaign_block_kind"])
        self.assertEqual("none", value["gc.campaign_candidate"])
        self.assertEqual("none", value["gc.campaign_condition"])

        # The sentinel reads it as a plain, coherent block -- never a crash.
        healthy = self.invoke("sentinel")
        self.assertEqual(0, healthy.returncode)
        self.assertIn("campaign blocked", healthy.stdout)

        # And resume refuses rather than reactivating with nothing to run.
        denied = self.invoke("resume", "--mayor", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.assertEqual("blocked", self.current_metadata()["gc.campaign_state"])


def bead(bead_id, **extra):
    value = {"id": bead_id, "title": f"Titre {bead_id}", "status": "open",
             "issue_type": "task", "priority": 2, "labels": None, "metadata": {},
             "assignee": "", "created_at": "2026-09-16T08:00:00Z"}
    value.update(extra)
    return value


class IdleLadderPlanTest(unittest.TestCase):
    """ADR-0016 s.7: 'no eligible product candidate' is not inactivity."""

    def test_only_ready_factory_work_is_eligible(self):
        self.assertTrue(is_ladder_bead(bead("af-ok")))
        self.assertTrue(is_ladder_bead(bead("af-bug", issue_type="bug")))
        self.assertTrue(is_ladder_bead(bead("af-mine", assignee="mayor")))
        rejected = {
            "session": bead("af-s", issue_type="session"),
            "convoy": bead("af-c", issue_type="convoy"),
            "nudge": bead("af-n", issue_type="chore", labels=["gc:nudge"]),
            "product": bead("af-p", issue_type="feature", labels=["product-goal", "saymyname"]),
            "upstream": bead("af-u", issue_type="bug", labels=["upstream"]),
            "workflow step": bead("af-w", metadata={"gc.step_ref": "x", "gc.root_bead_id": "af-r"}),
            "waiting": bead("af-wait", metadata={"gc.waiting_on": "po"}),
            "needs benjamin": bead("af-nb", metadata={"gc.needs_benjamin": "choix de périmètre"}),
            "someone else's": bead("af-o", assignee="po-techlead"),
            "not open": bead("af-ip", status="in_progress"),
        }
        for why, item in rejected.items():
            with self.subTest(why):
                self.assertFalse(is_ladder_bead(item))
        # "none" is how the store says nobody is needed.
        self.assertTrue(is_ladder_bead(bead("af-none", metadata={"gc.needs_benjamin": "none"})))

    def test_highest_priority_factory_bead_first(self):
        plan = plan_idle_ladder(
            [bead("af-low", priority=3), bead("af-hi", priority=1),
             bead("af-sess", issue_type="session", priority=0)],
            NOW,
        )
        self.assertEqual(("wake_mayor", "ladder:factory:af-hi", "af-hi"),
                         (plan["action"], plan["wake_key"], plan["ladder_bead"]))
        self.assertIn("gc.waiting_on", plan["message"])

    def test_one_factory_bead_at_a_time(self):
        tracked = bead("af-hi", status="in_progress", updated_at="2026-09-16T10:00:00Z")
        plan = plan_idle_ladder([bead("af-next")], NOW, tracked=tracked)
        self.assertEqual(("none", "ladder_active"), (plan["action"], plan["reason"]))

    def test_a_stalled_bead_is_unstuck_and_the_next_candidate_is_taken(self):
        # C6: this used to return a terminal "ladder_stalled" NOOP forever,
        # so one stuck bead (af-6eqc, live) permanently starved rung 2. It
        # must instead mark the stalled bead for the caller to unstick and
        # move on, in the same tick, to whatever rung is next in line.
        tracked = bead("af-hi", status="in_progress", updated_at="2026-09-16T01:00:00Z")
        no_candidate = plan_idle_ladder([], NOW, tracked=tracked)
        self.assertEqual("af-hi", no_candidate["unstick_bead"])
        self.assertEqual("ladder_tests", no_candidate["reason"])  # falls to the next rung
        with_candidate = plan_idle_ladder([bead("af-next")], NOW, tracked=tracked)
        self.assertEqual(
            ("af-hi", "ladder_factory", "ladder:factory:af-next"),
            (with_candidate["unstick_bead"], with_candidate["reason"], with_candidate["wake_key"]),
        )

    def test_a_closed_tracked_bead_releases_the_next_one(self):
        plan = plan_idle_ladder([bead("af-next")], NOW, tracked=bead("af-hi", status="closed"))
        self.assertEqual("ladder:factory:af-next", plan["wake_key"])

    def test_generative_rungs_are_throttled_then_rest(self):
        first = plan_idle_ladder([], NOW)
        self.assertEqual("ladder_tests", first["reason"])
        just_ran = "2026-09-16T10:30:00Z"
        second = plan_idle_ladder([], NOW, {"tests": just_ran})
        self.assertEqual("ladder_docs", second["reason"])
        rested = plan_idle_ladder([], NOW, {"tests": just_ran, "docs": just_ran})
        self.assertEqual(("none", "ladder_rested"), (rested["action"], rested["reason"]))
        later = plan_idle_ladder([], NOW + 13 * 3600, {"tests": just_ran, "docs": just_ran})
        self.assertEqual("ladder_tests", later["reason"])
        # Factory beads always outrank generative audits.
        self.assertEqual("ladder_factory", plan_idle_ladder([bead("af-x")], NOW)["reason"])

    def test_factory_queue_candidate_is_rung_2b(self):
        # C3: the goal=none lane in `saymyname-product-queue list --json` was
        # read by nobody. It sits between a ready Factory bead (rung 2) and
        # the generative rungs (3-4).
        candidate = {"id": "af-q1", "kind": "factory_campaign", "state": "eligible",
                     "title": "Nettoyer les beads de tracking d'ordres"}
        plan = plan_idle_ladder([], NOW, queue_candidates=[candidate])
        self.assertEqual(
            ("wake_mayor", "ladder_factory_queue", "materialize:af-q1"),
            (plan["action"], plan["reason"], plan["wake_key"]),
        )
        self.assertIn("af-q1", plan["message"])
        self.assertIn("materialize af-q1", plan["message"])

    def test_a_ready_factory_bead_outranks_a_queue_candidate(self):
        candidate = {"id": "af-q1", "kind": "factory_campaign", "state": "eligible", "title": "x"}
        plan = plan_idle_ladder([bead("af-hi")], NOW, queue_candidates=[candidate])
        self.assertEqual("ladder_factory", plan["reason"])

    def test_a_queue_candidate_outranks_generative_rungs(self):
        candidate = {"id": "af-q1", "kind": "factory_campaign", "state": "eligible", "title": "x"}
        plan = plan_idle_ladder([], NOW, queue_candidates=[candidate])
        self.assertEqual("ladder_factory_queue", plan["reason"])

    def test_maintain_alive_off_gates_the_whole_ladder(self):
        # sec1: OFF must read as an explicit, cockpit-visible idle-by-switch
        # reason, never silence and never indistinguishable from a stall.
        plan = plan_idle_ladder([bead("af-hi")], NOW, maintain_alive=False)
        self.assertEqual(("none", "maintain_alive_off"), (plan["action"], plan["reason"]))
        rested = plan_idle_ladder(
            [], NOW, {"tests": "2026-09-16T10:30:00Z", "docs": "2026-09-16T10:30:00Z"},
            maintain_alive=False,
            axis={"name": "code-review", "action": "dispatch",
                  "scope_boundary": "x", "mechanism": {"status": "wired", "ref": "skill:code-review"}},
        )
        self.assertEqual("maintain_alive_off", rested["reason"])

    def test_maintain_alive_off_still_lets_a_tracked_bead_finish(self):
        tracked = bead("af-hi", status="in_progress", updated_at="2026-09-16T10:00:00Z")
        plan = plan_idle_ladder([], NOW, tracked=tracked, maintain_alive=False)
        self.assertEqual(("none", "ladder_active"), (plan["action"], plan["reason"]))

    def test_axis_rung_fires_after_generative_rungs_when_maintain_alive_is_on(self):
        axis = {"name": "code-review", "action": "dispatch", "scope_boundary": "Périmètre x.",
                "mechanism": {"status": "wired", "ref": "skill:code-review"}}
        just_ran = "2026-09-16T10:30:00Z"
        plan = plan_idle_ladder(
            [], NOW, {"tests": just_ran, "docs": just_ran}, axis=axis,
        )
        self.assertEqual(
            ("wake_mayor", "ladder_axis_code-review", "ladder:axis:code-review"),
            (plan["action"], plan["reason"], plan["wake_key"]),
        )
        self.assertIn("Périmètre x.", plan["message"])
        self.assertIn("skill:code-review", plan["message"])

    def test_axis_rung_is_throttled_then_rests(self):
        axis = {"name": "code-review", "action": "dispatch", "scope_boundary": "x",
                "mechanism": {"status": "wired", "ref": "skill:code-review"}}
        just_ran = "2026-09-16T10:30:00Z"
        soon = plan_idle_ladder(
            [], NOW, {"tests": just_ran, "docs": just_ran}, axis=axis, last_axis=just_ran,
        )
        self.assertEqual(("none", "ladder_rested"), (soon["action"], soon["reason"]))
        later = plan_idle_ladder(
            [], NOW + 7 * 3600, {"tests": just_ran, "docs": just_ran}, axis=axis, last_axis=just_ran,
        )
        self.assertEqual("ladder_axis_code-review", later["reason"])

    def test_a_draft_only_axis_only_ever_proposes(self):
        axis = {"name": "auth-providers", "action": "propose", "scope_boundary": "réservée",
                "mechanism": {"status": "not_implemented"}}
        just_ran = "2026-09-16T10:30:00Z"
        plan = plan_idle_ladder([], NOW, {"tests": just_ran, "docs": just_ran}, axis=axis)
        self.assertEqual("wake_mayor", plan["action"])
        self.assertIn("proposition", plan["message"])
        self.assertIn("AUCUN", plan["message"])
        self.assertNotIn("Mécanisme", plan["message"])

    def test_no_axis_selected_still_rests(self):
        just_ran = "2026-09-16T10:30:00Z"
        plan = plan_idle_ladder([], NOW, {"tests": just_ran, "docs": just_ran}, axis=None)
        self.assertEqual(("none", "ladder_rested"), (plan["action"], plan["reason"]))

    def test_a_paused_or_product_candidate_is_not_rung_2b(self):
        paused = {"id": "af-q1", "kind": "factory_campaign", "state": "paused", "title": "x"}
        product = {"id": "af-q2", "kind": "product_candidate", "state": "eligible", "title": "x"}
        plan = plan_idle_ladder([], NOW, queue_candidates=[paused, product])
        self.assertNotEqual("ladder_factory_queue", plan["reason"])


class IdleLadderSentinelTest(CampaignFixture, unittest.TestCase):
    """The acceptance scenario of af-gxt1, end to end through the sentinel."""

    def setUp(self):
        super().setUp()
        self.ready_file = self.root / "ready.json"
        self.env["CAMPAIGN_READY_FILE"] = str(self.ready_file)
        self.ready_file.write_text(json.dumps([
            bead("af-sess", issue_type="session", priority=0),
            bead("af-fix", issue_type="bug", priority=1, title="Réparer le test"),
        ]), encoding="utf-8")

    def sentinel(self, at, **env):
        return self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(at), **env})

    def test_factory_lane_wins_over_an_eligible_product_candidate_by_default(self):
        # ADR-0023 amendment 2: factory-first is a priority order with
        # automatic fallthrough, not an exclusive product pause. Default
        # priority (no gc.campaign_priority_lane set) is factory, so af-fix
        # (ready Factory bead) must win over af-next (eligible product
        # candidate) even though the product lane is not empty.
        self.write_status(status(next_id="af-next"))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — ladder:factory:af-fix", out)

    def test_product_priority_lane_still_wins_when_set(self):
        self.write_state({**metadata(), "gc.campaign_priority_lane": "product"})
        self.write_status(status(next_id="af-next"))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — materialize:af-next", out)

    def test_factory_priority_falls_through_automatically_when_factory_lane_is_empty(self):
        # WHEN the priority lane has no eligible candidate, THE mayor-campaign
        # SHALL materialize the next eligible candidate from the other lane
        # automatically -- no manual resume/unpause step required.
        self.ready_file.write_text(json.dumps([
            bead("af-sess", issue_type="session", priority=0),
        ]), encoding="utf-8")
        self.write_status(status(next_id="af-next"))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — materialize:af-next", out)

    def test_empty_product_queue_dispatches_a_factory_bead(self):
        self.write_status(status(next_id=None))  # automatic campaign, nothing eligible
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — ladder:factory:af-fix", out)
        meta = self.current_metadata()
        self.assertEqual("af-fix", meta["gc.campaign_ladder_bead"])
        # C5: dispatching a new wake is not progress by itself -- only a real
        # event (here, af-fix actually being claimed) is. See
        # test_the_claimed_factory_bead_counts_as_progress below.
        self.assertNotIn("gc.campaign_progress_at", meta)
        self.assertEqual("2026-09-16T10:40:00Z", meta["gc.campaign_sentinel_at"])
        # Same bead, same key: announced once.
        self.assertIn("already notified", self.sentinel(NOW + 60).stdout)
        self.assertEqual(1, self.mail_count())

    def test_a_factory_candidate_closed_between_read_and_notify_is_not_announced(self):
        # af-mqphq (2026-09-18): an order-dispatch tracking bead was open in
        # the `ready` snapshot plan_factory_lane picked it from, but had
        # already closed (order dispatch completed) by the time the sentinel
        # was about to notify the Mayor about it. Replay that exact race:
        # af-fix is "open" in the ready snapshot, but a live re-check right
        # before sending finds it closed.
        (self.node_dir / "af-fix.json").write_text(json.dumps({
            "id": "af-fix", "status": "closed", "metadata": {},
        }), encoding="utf-8")
        self.write_status(status(next_id=None))  # automatic campaign, nothing eligible
        out = self.sentinel(NOW).stdout
        self.assertNotIn("NOTIFIED", out)
        self.assertIn("NOOP: factory_candidate_closed", out)
        self.assertEqual(0, self.mail_count())

    def test_a_factory_queue_candidate_closed_between_read_and_notify_is_not_announced(self):
        # Same race, rung 2b (a materialized queue candidate) instead of a
        # ready Factory bead.
        self.ready_file.write_text("[]", encoding="utf-8")
        queue_file = self.root / "queue.json"
        queue_file.write_text(json.dumps([
            {"id": "af-q1", "kind": "factory_campaign", "state": "eligible", "title": "x"},
        ]), encoding="utf-8")
        (self.node_dir / "af-q1.json").write_text(json.dumps({
            "id": "af-q1", "status": "closed", "metadata": {},
        }), encoding="utf-8")
        self.write_status(status(next_id=None))
        out = self.sentinel(NOW, CAMPAIGN_QUEUE_FILE=str(queue_file)).stdout
        self.assertNotIn("NOTIFIED", out)
        self.assertIn("NOOP: factory_candidate_closed", out)
        self.assertEqual(0, self.mail_count())

    def test_a_stale_product_reminder_bundles_a_factory_wake(self):
        # C4: a product wake stale enough to be reminded (>=30 min) must not
        # starve the Factory of the same 30 minutes; bundle a ladder wake into
        # the same mail without changing the tracked wake_key.
        self.write_state({**metadata(), "gc.campaign_wake_key": "resume:af-exec",
                          "gc.campaign_wake_state": "sent",
                          "gc.campaign_wake_sent_at": "2026-09-16T10:00:00Z"})
        self.write_status(status(result={"id": "af-exec", "state": "materialized"},
                                 mode="materialized_without_agent"))
        out = self.sentinel(NOW).stdout
        self.assertIn("REMINDED: mayor — resume:af-exec (1/3)", out)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("af-fix", log)  # the bundled Factory ladder pointer
        # The tracked wake is still the product one, not the bundled ladder's.
        self.assertEqual("resume:af-exec", self.current_metadata()["gc.campaign_wake_key"])

    def test_a_fresh_product_wake_does_not_bundle_the_ladder(self):
        # Only a stale (reminder) wake bundles the ladder -- the first send
        # must not spend a second call on Factory work that is not starving.
        # Priority is pinned to product: af-fix (ready Factory bead) is
        # present in this fixture and would otherwise win under the default
        # factory-priority lane (ADR-0023 amendment 2) -- unrelated to what
        # this test actually verifies.
        self.write_state({**metadata(), "gc.campaign_priority_lane": "product"})
        self.write_status(status(next_id="af-next"))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — materialize:af-next", out)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("af-fix", log)

    def test_a_stalled_ladder_bead_is_unstuck_end_to_end(self):
        # C6: af-stuck has been in_progress since before LADDER_STALE_SECONDS;
        # the sentinel must mark it, stop tracking it, and dispatch af-fix in
        # the very same tick instead of reporting ladder_stalled forever.
        self.write_state({**metadata(), "gc.campaign_ladder_bead": "af-stuck"})
        (self.node_dir / "af-stuck.json").write_text(json.dumps({
            "id": "af-stuck", "status": "in_progress", "metadata": {},
            "updated_at": "2026-09-16T01:00:00Z",
        }), encoding="utf-8")
        self.write_status(status(next_id=None))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — ladder:factory:af-fix", out)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("bd update af-stuck --set-metadata gc.waiting_on=stalled", log)
        self.assertEqual("af-fix", self.current_metadata()["gc.campaign_ladder_bead"])

    def test_no_ready_bead_falls_through_to_the_factory_queue_candidate(self):
        # C3: with no product work and no ready Factory bead, rung 2b reads
        # `saymyname-product-queue list --json` end to end through the sentinel.
        self.ready_file.write_text("[]", encoding="utf-8")
        queue_file = self.root / "queue.json"
        queue_file.write_text(json.dumps([
            {"id": "af-q1", "kind": "factory_campaign", "state": "eligible", "title": "Purger les logs"},
        ]), encoding="utf-8")
        self.write_status(status(next_id=None))
        out = self.sentinel(NOW, CAMPAIGN_QUEUE_FILE=str(queue_file)).stdout
        self.assertIn("NOTIFIED: mayor — materialize:af-q1", out)

    def test_the_claimed_factory_bead_counts_as_progress(self):
        self.write_status(status(next_id=None))
        self.sentinel(NOW)
        (self.node_dir / "af-fix.json").write_text(json.dumps({
            "id": "af-fix", "status": "in_progress", "metadata": {},
            "updated_at": "2026-09-16T10:41:00Z",
        }), encoding="utf-8")
        later = NOW + 600
        self.assertIn("ladder_active", self.sentinel(later).stdout)
        self.assertEqual("2026-09-16T10:50:00Z", self.current_metadata()["gc.campaign_progress_at"])
        self.assertEqual(1, self.mail_count())

    def test_a_stale_finalize_wake_clears_once_its_target_closes_even_under_ladder_active(self):
        # af-hnm7l: a wake sent for a product finalize/resume target used to
        # survive that target's closure whenever the *next* tick's reason
        # was anything outside {active_delivery, automatic_dependency} --
        # observed live as 'ladder_active' -- leaving the cockpit reporting
        # awaiting_mayor forever even though the named wake was long resolved.
        self.write_state({**metadata(), "gc.campaign_wake_key": "finalize:af-target",
                          "gc.campaign_wake_state": "sent",
                          "gc.campaign_ladder_bead": "af-fix"})
        (self.node_dir / "af-target.json").write_text(json.dumps({
            "id": "af-target", "status": "closed", "metadata": {},
        }), encoding="utf-8")
        (self.node_dir / "af-fix.json").write_text(json.dumps({
            "id": "af-fix", "status": "in_progress", "metadata": {},
            "updated_at": "2026-09-16T10:40:00Z",
        }), encoding="utf-8")
        self.write_status(status(next_id=None))  # automatic campaign, nothing eligible
        out = self.sentinel(NOW).stdout
        self.assertIn("NOOP: ladder_active", out)
        meta = self.current_metadata()
        self.assertEqual("", meta["gc.campaign_wake_key"])
        self.assertEqual("none", meta["gc.campaign_wake_state"])

    def test_product_work_in_flight_never_triggers_the_ladder(self):
        self.write_status(status(result={"id": "af-exec", "state": "active"}, mode="active_delivery"))
        self.assertIn("NOOP: active_delivery", self.sentinel(NOW).stdout)
        self.assertEqual(0, self.mail_count())
        self.assertIn("gc.campaign_progress_at", self.current_metadata())

    def test_an_admin_window_stays_quiet_but_the_loop_still_proves_it_lives(self):
        self.invoke("block", "--kind", "admin", "--cause", "Fenêtre de maintenance",
                    "--owner", "Benjamin", "--action", "Rien pendant la fenêtre", "--mayor")
        self.assertIn("campaign blocked", self.sentinel(NOW).stdout)
        self.assertEqual(0, self.mail_count())
        meta = self.current_metadata()
        self.assertEqual("2026-09-16T10:40:00Z", meta["gc.campaign_sentinel_at"])
        self.assertNotIn("gc.campaign_progress_at", meta)

    def test_a_product_decision_parks_product_work_not_the_factory(self):
        # The block command itself refuses a decision block with nothing pending.
        self.write_state({**metadata(), "gc.needs_benjamin": "Choix de périmètre du résultat"})
        self.invoke("block", "--kind", "decision", "--cause", "Choix de périmètre",
                    "--owner", "Benjamin", "--action", "Répondre à la décision", "--mayor")
        out = self.sentinel(NOW, CAMPAIGN_STATUS_FAIL="1").stdout
        # The product status is not even consulted, and Factory work goes on.
        self.assertIn("ladder:factory:af-fix", out)
        self.assertEqual(1, self.mail_count())

    def test_an_unreadable_ready_queue_is_reported_not_counted_as_a_failure(self):
        self.write_status(status(next_id=None))
        out = self.sentinel(NOW, CAMPAIGN_READY_FAIL="1").stdout
        self.assertIn("ladder_unavailable", out)
        self.assertEqual("0", self.current_metadata()["gc.campaign_failure_count"])
        self.assertEqual(0, self.mail_count())

    def test_watching_starts_once_and_only_without_progress(self):
        # Exactly the live state on 2026-09-16: a resume wake already sent and
        # never acted on. Re-announcing it is not progress, so only the watch
        # reference can make this stall measurable.
        self.write_state({**metadata(), "gc.campaign_wake_key": "resume:af-exec",
                          "gc.campaign_wake_state": "sent",
                          "gc.campaign_wake_sent_at": "2026-09-16T10:39:00Z"})
        self.write_status(status(result={"id": "af-exec", "state": "materialized"},
                                 mode="materialized_without_agent"))
        self.assertIn("already notified", self.sentinel(NOW).stdout)
        meta = self.current_metadata()
        self.assertEqual("2026-09-16T10:40:00Z", meta["gc.campaign_watch_since"])
        self.assertNotIn("gc.campaign_progress_at", meta)
        self.sentinel(NOW + 900)
        self.assertEqual("2026-09-16T10:40:00Z", self.current_metadata()["gc.campaign_watch_since"])
        self.assertEqual(0, self.mail_count())

    def stalled_resume(self, **extra):
        self.write_state({**metadata(), "gc.campaign_wake_key": "resume:af-exec",
                          "gc.campaign_wake_state": "sent", **extra})
        self.write_status(status(result={"id": "af-exec", "state": "materialized"},
                                 mode="materialized_without_agent"))

    def test_a_wake_that_predates_the_rule_is_reminded_at_once(self):
        """The live case: a sent wake with no send time, forgotten by a restart."""
        self.stalled_resume()
        out = self.sentinel(NOW).stdout
        self.assertIn("REMINDED: mayor — resume:af-exec (1/3)", out)
        self.assertEqual(1, self.mail_count())
        meta = self.current_metadata()
        self.assertEqual("1", meta["gc.campaign_wake_resends"])
        # A reminder is not progress: liveness can still see the stall.
        self.assertNotIn("gc.campaign_progress_at", meta)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("RAPPEL", log)

    def test_reminders_are_spaced_and_capped(self):
        self.stalled_resume(**{"gc.campaign_wake_sent_at": "2026-09-16T10:30:00Z"})
        self.assertIn("already notified", self.sentinel(NOW).stdout)  # 10 min: too soon
        at = NOW + 20 * 60
        self.assertIn("REMINDED", self.sentinel(at).stdout)            # 30 min
        self.assertIn("already notified", self.sentinel(at + 60).stdout)
        at += 30 * 60
        self.assertIn("(2/3)", self.sentinel(at).stdout)
        at += 30 * 60
        self.assertIn("(3/3)", self.sentinel(at).stdout)
        at += 30 * 60
        self.assertIn("already notified", self.sentinel(at).stdout)    # capped
        self.assertEqual(3, self.mail_count())

    def test_progress_after_the_wake_cancels_the_reminder(self):
        self.stalled_resume(**{"gc.campaign_wake_sent_at": "2026-09-16T09:00:00Z",
                               "gc.campaign_progress_at": "2026-09-16T09:10:00Z"})
        self.assertIn("already notified", self.sentinel(NOW).stdout)
        self.assertEqual(0, self.mail_count())

    def test_optional_generative_rungs_are_never_chased(self):
        key = "ladder:tests:" + str(int(NOW // (12 * 3600)))
        self.write_state({**metadata(), "gc.campaign_wake_key": key,
                          "gc.campaign_wake_state": "sent",
                          "gc.campaign_ladder_docs_at": "2026-09-16T10:00:00Z"})
        self.ready_file.write_text("[]", encoding="utf-8")
        self.write_status(status(next_id=None))
        self.assertIn("already notified", self.sentinel(NOW).stdout)
        self.assertEqual(0, self.mail_count())

    def test_a_new_wake_resets_the_reminder_count(self):
        # Priority pinned to product for the same reason as
        # test_a_fresh_product_wake_does_not_bundle_the_ladder above.
        self.stalled_resume(**{"gc.campaign_wake_resends": "3",
                               "gc.campaign_wake_sent_at": "2026-09-16T08:00:00Z",
                               "gc.campaign_priority_lane": "product"})
        self.write_status(status())  # a different transition is now due
        self.assertIn("NOTIFIED: mayor — materialize:af-next", self.sentinel(NOW).stdout)
        meta = self.current_metadata()
        self.assertEqual(("0", "2026-09-16T10:40:00Z"),
                         (meta["gc.campaign_wake_resends"], meta["gc.campaign_wake_sent_at"]))

    def test_no_action_on_a_status_masked_by_a_transient_failure(self):
        """Seen live: the masked status let the ladder run over a result awaiting finalization."""
        self.write_state({**metadata(), "gc.campaign_failure_count": "1",
                          "gc.campaign_last_error": "product queue lock"})
        masked = status(next_id=None)
        masked["campaign"]["blocker_kind"] = "transient_failure"
        self.write_status(masked)
        out = self.sentinel(NOW).stdout
        self.assertIn("recovered from a transient failure", out)
        self.assertEqual(0, self.mail_count())
        self.assertEqual("0", self.current_metadata()["gc.campaign_failure_count"])
        # Next tick, with the real state, acts normally.
        self.write_status(status(result={"id": "af-7700", "state": "active"}, mode="mayor_finalization"))
        self.assertIn("NOTIFIED: mayor — finalize:af-7700", self.sentinel(NOW + 60).stdout)

    def test_heartbeats_are_throttled(self):
        self.write_status(status(result={"id": "af-exec", "state": "active"}, mode="active_delivery"))
        self.sentinel(NOW)
        self.sentinel(NOW + 120)  # within five minutes: no rewrite
        self.assertEqual("2026-09-16T10:40:00Z", self.current_metadata()["gc.campaign_progress_at"])
        self.sentinel(NOW + 301)
        self.assertEqual("2026-09-16T10:45:01Z", self.current_metadata()["gc.campaign_progress_at"])


if __name__ == "__main__":
    unittest.main()
