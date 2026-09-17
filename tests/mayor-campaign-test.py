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
        # with no Factory bead ready, it walks the generative rungs, once each...
        first = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW)}).stdout
        self.assertIn("ladder:tests:", first)
        second = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW + 60)}).stdout
        self.assertIn("ladder:docs:", second)
        # ...and only then rests, without mailing anyone.
        third = self.invoke("sentinel", extra_env={"CAMPAIGN_NOW": str(NOW + 120)}).stdout
        self.assertIn("ladder_rested", third)
        self.assertEqual(2, self.mail_count())


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

    def test_a_bead_in_progress_for_hours_is_not_progress(self):
        tracked = bead("af-hi", status="in_progress", updated_at="2026-09-16T01:00:00Z")
        plan = plan_idle_ladder([], NOW, tracked=tracked)
        self.assertEqual("ladder_stalled", plan["reason"])

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

    def test_empty_product_queue_dispatches_a_factory_bead(self):
        self.write_status(status(next_id=None))  # automatic campaign, nothing eligible
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — ladder:factory:af-fix", out)
        meta = self.current_metadata()
        self.assertEqual("af-fix", meta["gc.campaign_ladder_bead"])
        self.assertEqual("2026-09-16T10:40:00Z", meta["gc.campaign_progress_at"])
        self.assertEqual("2026-09-16T10:40:00Z", meta["gc.campaign_sentinel_at"])
        # Same bead, same key: announced once.
        self.assertIn("already notified", self.sentinel(NOW + 60).stdout)
        self.assertEqual(1, self.mail_count())

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
        self.write_status(status(next_id="af-next"))
        out = self.sentinel(NOW).stdout
        self.assertIn("NOTIFIED: mayor — materialize:af-next", out)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("af-fix", log)

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
        self.stalled_resume(**{"gc.campaign_wake_resends": "3",
                               "gc.campaign_wake_sent_at": "2026-09-16T08:00:00Z"})
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
