#!/usr/bin/env python3
"""Rules of lib/ntfy_notify.py: what Benjamin's phone says, and when.

Contract set by Benjamin on 2026-09-18: every push states the real state in
one sentence, then exactly one of: nothing to do (and what to follow), an
easy action, or a delegation with a sentence he can type word for word. Never
a bead id.
"""
import calendar
import json
import re
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import provider_failover as pf  # noqa: E402
from ntfy_notify import (  # noqa: E402
    DELEGATE, EASY, NOTHING, PERSIST_ALERT_SECONDS, PROMPTS, PROVIDER_ALERT_CAP, PROVIDER_MAX_REMINDERS,
    PROVIDER_REMIND_SECONDS, STRIKES_ALERT_THRESHOLD, apply_provider_budget, cold_start_alert, compute_alerts,
    compute_digest, diff_alerts, diff_provider_alerts, digest_due, provider_problem_alerts, provider_trouble_keys,
    providers_exhausted_until,
)

NOW = 1_800_000_000.0
CLEAR_SNAPSHOT = {
    "human_state": {
        "needs_benjamin": None,
        "resume": {"required": False, "mode": "mayor_finalization"},
        "campaign": {"blocked": False},
        "activity": {"label": "Active · campagne en cours"},
        "result": {"id": None, "title": None},
    },
    "needs_benjamin": None,
    "warnings": [],
    "last_delivery": {"title": "Apply ADR-0021 review tiers (af-j41c2)"},
    "queue": [
        {"goal": "none", "state": "eligible"},
        {"goal": "af-u8id", "state": "paused"},
        {"goal": "af-u8id", "state": "eligible"},
    ],
}
BEAD = re.compile(r"\b(?:af|smb|smf)-[a-z0-9]{3,}", re.I)
# Minimal stand-in for config/provider-policy.json's providers -> pool map.
PROVIDER_POLICY = {"providers": {
    "codex": {"pool": "openai"},
    "claude": {"pool": "anthropic"},
    "claude-standard": {"pool": "anthropic"},
    "claude-cheap": {"pool": "anthropic"},
}}


def snap(**human):
    return {**CLEAR_SNAPSHOT, "human_state": {**CLEAR_SNAPSHOT["human_state"], **human}}


class Shape(unittest.TestCase):
    def assert_shape(self, alert, kind):
        self.assertEqual(kind, alert["kind"])
        state, todo = alert["message"].split("\n", 1)
        self.assertTrue(state.startswith("ÉTAT : "), state)
        self.assertTrue(todo.startswith("À FAIRE"), todo)
        self.assertIsNone(BEAD.search(alert["message"]), alert["message"])
        self.assertIsNone(BEAD.search(alert["title"]), alert["title"])
        if kind == DELEGATE:
            self.assertIn("Écris-moi : «", todo)

    def test_a_clear_snapshot_pages_nobody(self):
        self.assertEqual([], compute_alerts(CLEAR_SNAPSHOT))

    def test_a_durable_failure_is_a_delegation_with_the_typed_sentence(self):
        alerts = compute_alerts(snap(campaign={
            "blocked": True, "blocker_kind": "durable_failure",
            "cause": "Le sentinelle a échoué 8 fois : jq error on af-ogg8z",
        }))
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], DELEGATE)
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertIn(PROMPTS["blocked"], alerts[0]["message"])
        self.assertEqual("campaign_blocked:durable_failure", alerts[0]["key"])

    def test_an_admin_pause_is_an_easy_action_from_the_campaign_text(self):
        alerts = compute_alerts(snap(campaign={
            "blocked": True, "blocker_kind": "admin", "cause": "Fenêtre de maintenance",
            "action": "Relancer la campagne depuis le cockpit quand la fenêtre est finie",
        }))
        self.assert_shape(alerts[0], EASY)
        self.assertEqual("default", alerts[0]["priority"])
        self.assertIn("Relancer la campagne", alerts[0]["message"])

    def test_a_quota_limit_is_nothing_to_do(self):
        alerts = compute_alerts(snap(campaign={"blocked": True, "blocker_kind": "limit", "cause": "quota Codex"}))
        self.assert_shape(alerts[0], NOTHING)
        self.assertEqual("low", alerts[0]["priority"])

    def test_all_product_candidates_paused_is_not_an_alarm(self):
        alerts = compute_alerts(snap(campaign={"blocked": True, "blocker_kind": "all_paused",
                                               "cause": "Tous les candidats produit sont en pause"}))
        self.assert_shape(alerts[0], NOTHING)
        self.assertEqual("low", alerts[0]["priority"])
        self.assertIn("usine avance", alerts[0]["message"])

    def test_a_transient_failure_is_nothing_and_a_result_blocker_is_a_delegation(self):
        transient = compute_alerts(snap(campaign={"blocked": True, "blocker_kind": "transient_failure", "cause": "timeout"}))
        self.assert_shape(transient[0], NOTHING)
        blocked = compute_alerts(snap(campaign={"blocked": True, "blocker_kind": "result_blocker", "cause": "preuve manquante"}))
        self.assert_shape(blocked[0], DELEGATE)
        self.assertIn(PROMPTS["result"], blocked[0]["message"])

    def test_every_pool_exhausted_overrides_everything_with_nothing_to_do(self):
        snapshot = snap(campaign={"blocked": True, "blocker_kind": "all_paused", "cause": "x"})
        snapshot["provider_policy"] = PROVIDER_POLICY
        snapshot["provider_state"] = {
            "effective": {"workspace": "codex", "mayor": "claude"},
            "pools": {
                "openai": {"status": "exhausted", "until": "2033-01-15T10:00:00Z"},
                "anthropic": {"status": "exhausted", "until": "2033-01-15T08:00:00Z"},
            },
        }
        alerts = compute_alerts(snapshot, {}, NOW)
        self.assertEqual(["quota_exhausted"], [a["key"] for a in alerts])
        self.assert_shape(alerts[0], NOTHING)
        self.assertIn("quota", alerts[0]["message"])
        expected = time.localtime(calendar.timegm((2033, 1, 15, 8, 0, 0, 0, 0, 0)))
        self.assertIn(f"{expected.tm_hour:02d}h00", alerts[0]["message"])

    def test_one_pool_available_is_not_a_quota_stop(self):
        snapshot = snap()
        snapshot["provider_policy"] = PROVIDER_POLICY
        snapshot["provider_state"] = {
            "effective": {"workspace": "codex", "mayor": "claude"},
            "pools": {
                "openai": {"status": "exhausted", "until": "2033-01-15T10:00:00Z"},
                "anthropic": {"status": "available"},
            },
        }
        self.assertEqual([], compute_alerts(snapshot, {}, NOW))

    def test_a_provider_with_no_pool_entry_at_all_is_not_a_quota_stop(self):
        # af-d1jfc, 2026-09-18: replay of the exact live state that made the
        # phone say "tous les fournisseurs" -- openai has a recorded
        # exhaustion, claude-standard (what the Mayor actually runs on) has
        # never had one, so it has no entry in 'pools' at all.
        snapshot = snap()
        snapshot["provider_policy"] = PROVIDER_POLICY
        snapshot["provider_state"] = {
            "effective": {
                "workspace": "claude-standard", "mayor": "claude-standard",
                "claude-reviewer": "claude", "ux-reviewer": "claude",
            },
            "pools": {
                "openai": {"status": "exhausted", "until": "2026-09-21T05:22:00Z"},
            },
        }
        self.assertIsNone(providers_exhausted_until(
            snapshot["provider_state"], snapshot["provider_policy"], NOW))
        self.assertEqual([], compute_alerts(snapshot, {}, NOW))

    def test_a_decision_block_is_one_delegation_not_two(self):
        alerts = compute_alerts(snap(
            needs_benjamin="Choisir le périmètre de af-hc2mx",
            campaign={"blocked": True, "blocker_kind": "decision", "cause": "attend Benjamin"},
        ))
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], DELEGATE)
        self.assertIn(PROMPTS["decision"], alerts[0]["message"])

    def test_a_pending_decision_alone_is_a_delegation(self):
        alerts = compute_alerts(snap(needs_benjamin="Choisir le contrat"))
        self.assertEqual("needs_benjamin", alerts[0]["key"])
        self.assert_shape(alerts[0], DELEGATE)

    def test_a_mayor_resume_is_nothing_then_a_delegation_after_an_hour(self):
        human = dict(resume={"required": True, "mode": "mayor_finalization", "owner": "Mayor",
                             "condition": "finaliser af-7700"})
        fresh = compute_alerts(snap(**human), {}, NOW)
        self.assert_shape(fresh[0], NOTHING)
        stale = compute_alerts(snap(**human), {"resume:mayor_finalization": NOW - 3601}, NOW)
        self.assert_shape(stale[0], DELEGATE)
        self.assertIn(PROMPTS["mayor_silent"], stale[0]["message"])
        self.assertEqual(fresh[0]["key"], stale[0]["key"])

    def test_a_benjamin_resume_is_an_easy_action(self):
        alerts = compute_alerts(snap(resume={"required": True, "mode": "blocking_decision", "owner": "Benjamin",
                                             "condition": "valider", "action": "Valider le périmètre dans le cockpit"}))
        self.assert_shape(alerts[0], EASY)
        self.assertIn("Valider le périmètre", alerts[0]["message"])

    def test_warnings_are_follow_only_then_delegate_after_a_day(self):
        snapshot = {**CLEAR_SNAPSHOT, "warnings": ["worktree stale af-x", {"message": "delivery-proof af-y"}]}
        fresh = compute_alerts(snapshot, {}, NOW)
        self.assertEqual(1, len(fresh))
        self.assert_shape(fresh[0], NOTHING)
        self.assertIn("2 avertissement", fresh[0]["message"])
        self.assertNotIn("af-x", fresh[0]["message"])
        self.assertNotIn("worktree", fresh[0]["message"])
        old = compute_alerts(snapshot, {"warnings": NOW - 86_401}, NOW)
        self.assert_shape(old[0], DELEGATE)


class Digest(unittest.TestCase):
    def test_the_digest_states_the_real_state_and_counts_the_queue(self):
        digest = compute_digest(CLEAR_SNAPSHOT, [])
        self.assertIn("ÉTAT : Active · campagne en cours.", digest["message"])
        self.assertIn("Dernière livraison : Apply ADR-0021 review tiers ().", digest["message"].replace("( )", "()"))
        self.assertIn("1 tâche(s) usine prête(s), 1 produit prête(s), 1 produit en pause", digest["message"])
        self.assertIn("À FAIRE : rien.", digest["message"])
        self.assertIsNone(BEAD.search(digest["message"]))

    def test_the_digest_carries_the_first_actionable_todo(self):
        alerts = compute_alerts(snap(campaign={"blocked": True, "blocker_kind": "durable_failure", "cause": "x"}))
        digest = compute_digest(CLEAR_SNAPSHOT, alerts)
        self.assertIn(PROMPTS["blocked"], digest["message"])

    def test_digest_is_due_once_per_slot_hour(self):
        eight = lambda now: time.struct_time((2026, 9, 18, 8, 5, 0, 4, 261, 0))
        nine = lambda now: time.struct_time((2026, 9, 18, 9, 5, 0, 4, 261, 0))
        self.assertEqual("digest:2026-09-18:08", digest_due({}, NOW, (8, 20), eight))
        self.assertIsNone(digest_due({"digest:2026-09-18:08": NOW}, NOW, (8, 20), eight))
        self.assertIsNone(digest_due({}, NOW, (8, 20), nine))


class Throttle(unittest.TestCase):
    def alert(self, key):
        return {"key": key, "title": "t", "message": "m", "priority": "default", "kind": NOTHING}

    def test_a_brand_new_alert_is_due_immediately(self):
        due, resolved = diff_alerts([self.alert("a")], {}, NOW)
        self.assertEqual(["a"], [a["key"] for a in due]); self.assertEqual([], resolved)

    def test_a_recently_sent_alert_is_not_due_again(self):
        due, _ = diff_alerts([self.alert("a")], {"a": NOW - 100}, NOW)
        self.assertEqual([], due)

    def test_a_stuck_alert_pages_again_after_the_reminder_window(self):
        due, _ = diff_alerts([self.alert("a")], {"a": NOW - 3601}, NOW)
        self.assertEqual(["a"], [a["key"] for a in due])

    def test_bookkeeping_keys_are_never_reported_resolved(self):
        _, resolved = diff_alerts([], {"a": NOW, "first:a": NOW, "digest:2026-09-18:08": NOW}, NOW)
        self.assertEqual(["a"], resolved)


FULL_POLICY = {
    "pools": {
        "anthropic": {"label": "Anthropic · Claude (compte partagé)"},
        "openai": {"label": "OpenAI · Codex"},
    },
    "providers": {
        "claude": {"pool": "anthropic", "label": "Claude"},
        "claude-standard": {"pool": "anthropic", "label": "Claude (standard)"},
        "codex": {"pool": "openai", "label": "Codex"},
    },
    "targets": {
        "workspace": {"label": "Ouvriers des rigs", "chain": ["claude-standard", "codex"]},
        "mayor": {"label": "Mayor", "chain": ["claude-standard", "codex"]},
    },
}


def full_state(pools):
    return {"pools": pools, "disabled": {}, "forced": {}, "chains": {}, "effective": {}}


class ProviderAlerts(unittest.TestCase):
    """R1/R2/R4: alert on impact, classified by who must act, plain French."""

    def assert_shape(self, alert, kind):
        state, todo = alert["message"].split("\n", 1)
        self.assertTrue(state.startswith("ÉTAT : "), state)
        self.assertTrue(todo.startswith("À FAIRE"), todo)
        self.assertIsNone(BEAD.search(alert["message"]), alert["message"])
        self.assertNotIn("anthropic", alert["message"])  # internal pool id, never the phone
        self.assertEqual(kind, alert["kind"])

    def test_an_auth_error_alerts_immediately_with_the_exact_fix(self):
        state = full_state({"anthropic": {
            "status": "error", "category": "auth", "strikes": 7, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "please run /login",
        }})
        alerts = provider_problem_alerts(state, FULL_POLICY, NOW, {})
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], EASY)
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertIn("/login", alerts[0]["message"])
        self.assertIn("Ouvriers des rigs", alerts[0]["message"])
        self.assertIn("Mayor", alerts[0]["message"])

    def test_a_young_transient_network_error_stays_silent(self):
        state = full_state({"openai": {
            "status": "error", "category": "network", "strikes": 1, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "connection refused",
        }})
        self.assertEqual([], provider_problem_alerts(state, FULL_POLICY, NOW, {}))

    def test_a_network_error_alerts_once_it_persists(self):
        state = full_state({"openai": {
            "status": "error", "category": "network", "strikes": 1, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "connection refused",
        }})
        keys = provider_trouble_keys(state, FULL_POLICY, NOW)
        self.assertEqual(1, len(keys))
        first_seen = {next(iter(keys)): NOW - PERSIST_ALERT_SECONDS - 1}
        alerts = provider_problem_alerts(state, FULL_POLICY, NOW, first_seen)
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], DELEGATE)
        self.assertIn(PROMPTS["provider_error"], alerts[0]["message"])
        self.assertIn("default", alerts[0]["priority"])

    def test_strikes_crossing_the_threshold_alerts_even_while_young(self):
        state = full_state({"openai": {
            "status": "error", "category": "server", "strikes": STRIKES_ALERT_THRESHOLD,
            "until": "2057-01-01T00:00:00Z", "source": "detected", "evidence": "503",
        }})
        alerts = provider_problem_alerts(state, FULL_POLICY, NOW, {})
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], DELEGATE)

    def test_a_known_reset_quota_wall_stays_silent(self):
        state = full_state({"anthropic": {
            "status": "exhausted", "reset_known": True, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "resets 6:50pm",
        }})
        self.assertEqual([], provider_problem_alerts(state, FULL_POLICY, NOW, {}))

    def test_an_unknown_reset_quota_wall_alerts_once_it_persists(self):
        state = full_state({"anthropic": {
            "status": "exhausted", "reset_known": False, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "unknown reset", "strikes": 1,
        }})
        keys = provider_trouble_keys(state, FULL_POLICY, NOW)
        first_seen = {next(iter(keys)): NOW - PERSIST_ALERT_SECONDS - 1}
        alerts = provider_problem_alerts(state, FULL_POLICY, NOW, first_seen)
        self.assertEqual(1, len(alerts))
        self.assert_shape(alerts[0], NOTHING)
        self.assertIn("quota", alerts[0]["message"])

    def test_a_manual_mark_is_a_decision_benjamin_already_made_never_an_alert(self):
        state = full_state({"anthropic": {
            "status": "exhausted", "source": "manual", "until": "2057-01-01T00:00:00Z",
            "evidence": "marqué à la main",
        }})
        self.assertEqual([], provider_problem_alerts(state, FULL_POLICY, NOW, {}))

    def test_an_expired_marking_stays_silent(self):
        state = full_state({"anthropic": {
            "status": "error", "category": "network", "until": "2000-01-01T00:00:00Z",
            "source": "detected", "evidence": "old",
        }})
        self.assertEqual([], provider_problem_alerts(state, FULL_POLICY, NOW, {}))

    def test_the_fingerprint_changes_when_a_new_target_becomes_affected(self):
        one_target = {"anthropic": {
            "status": "error", "category": "auth", "strikes": 1, "until": "2057-01-01T00:00:00Z",
            "source": "detected", "evidence": "please run /login",
        }}
        before = provider_trouble_keys(full_state(one_target), FULL_POLICY, NOW)
        forced_state = full_state(one_target)
        forced_state["forced"] = {"mayor": "codex"}  # mayor no longer depends on the broken pool
        after = provider_trouble_keys(forced_state, FULL_POLICY, NOW)
        self.assertNotEqual(before, after)


class ColdStartBackstop(unittest.TestCase):
    """R6: alert on the symptom even when no error text was recognised."""

    def test_below_threshold_is_silent(self):
        self.assertIsNone(cold_start_alert(9))
        self.assertIsNone(cold_start_alert(None))

    def test_at_threshold_is_a_delegation(self):
        alert = cold_start_alert(10)
        self.assertEqual(DELEGATE, alert["kind"])
        self.assertEqual("urgent", alert["priority"])
        self.assertIn(PROMPTS["cold_start"], alert["message"])
        self.assertIsNone(BEAD.search(alert["message"]))


class ProviderThrottleAndCap(unittest.TestCase):
    """R3 (one alert per incident, capped reminders) and R7 (24h budget)."""

    def alert(self, key="provider:openai:network:workspace"):
        return {"key": key, "title": "t", "message": "m", "priority": "default", "kind": DELEGATE}

    def test_a_new_incident_is_due_immediately(self):
        due, resolved = diff_provider_alerts([self.alert()], {}, NOW)
        self.assertEqual(1, len(due)); self.assertEqual([], resolved)

    def test_no_reminder_before_the_six_hour_window(self):
        sent = {"provider:openai:network:workspace": {"at": NOW - 60, "reminders": 0}}
        due, _ = diff_provider_alerts([self.alert()], sent, NOW)
        self.assertEqual([], due)

    def test_a_reminder_fires_after_six_hours(self):
        sent = {"provider:openai:network:workspace": {"at": NOW - PROVIDER_REMIND_SECONDS - 1, "reminders": 0}}
        due, _ = diff_provider_alerts([self.alert()], sent, NOW)
        self.assertEqual(1, len(due))

    def test_reminders_stop_after_the_cap(self):
        sent = {"provider:openai:network:workspace": {
            "at": NOW - PROVIDER_REMIND_SECONDS - 1, "reminders": PROVIDER_MAX_REMINDERS}}
        due, _ = diff_provider_alerts([self.alert()], sent, NOW)
        self.assertEqual([], due, "still open, but silent past the reminder cap -- never fully unbounded")

    def test_worsening_realerts_immediately_even_mid_cooldown(self):
        sent = {"provider:openai:network:workspace": {"at": NOW - 60, "reminders": 0}}
        worse = self.alert(key="provider:openai:network:workspace,mayor")
        due, _ = diff_provider_alerts([worse], sent, NOW)
        self.assertEqual([worse], due)

    def test_a_resolved_incident_is_reported_once(self):
        sent = {"provider:openai:network:workspace": {"at": NOW, "reminders": 0}}
        due, resolved = diff_provider_alerts([], sent, NOW)
        self.assertEqual([], due)
        self.assertEqual(["provider:openai:network:workspace"], resolved)

    def test_the_cap_collapses_overflow_into_one_alert(self):
        due = [self.alert(key=f"provider:pool{i}:network:workspace") for i in range(PROVIDER_ALERT_CAP + 4)]
        allowed, history, cap_alert = apply_provider_budget(due, [], NOW)
        self.assertEqual(PROVIDER_ALERT_CAP, len(allowed))
        self.assertIsNotNone(cap_alert)
        self.assertIn("4", cap_alert["message"])
        # Nothing is recorded as sent until the caller actually pushes it --
        # apply_provider_budget only decides, it never assumes success.
        self.assertEqual([], history)

    def test_the_cap_holds_across_many_ticks_in_the_same_24h(self):
        history = []
        pushed = 0
        for tick in range(30):
            due = [self.alert(key=f"provider:pool{tick}:network:workspace")]
            allowed, history, _ = apply_provider_budget(due, history, NOW + tick * 60)
            pushed += len(allowed)
            history.extend([NOW + tick * 60] * len(allowed))
        self.assertLessEqual(pushed, PROVIDER_ALERT_CAP)

    def test_under_the_cap_nothing_is_collapsed(self):
        due = [self.alert(key=f"provider:pool{i}:network:workspace") for i in range(PROVIDER_ALERT_CAP - 1)]
        allowed, _, cap_alert = apply_provider_budget(due, [], NOW)
        self.assertEqual(len(due), len(allowed))
        self.assertIsNone(cap_alert)


class IncidentReplay(unittest.TestCase):
    """Acceptance criteria: replay 2026-09-20 (auth) and a noisy week (no alert)."""

    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((ROOT / "config" / "provider-policy.json").read_text(encoding="utf-8"))

    def test_2026_09_20_incident_alerts_within_one_cycle(self):
        # The exact shape provider_failover.record_detection would have
        # written the first tick it saw "please run /login": strikes=1,
        # source=detected, status=error/auth.
        state = full_state({"anthropic": {
            "status": "error", "category": "auth", "strikes": 1, "until": pf.iso(NOW + 600),
            "source": "detected", "evidence": "Invalid API key · Please run /login",
        }})
        state["effective"] = {"workspace": "claude-standard", "mayor": "claude-standard"}
        alerts = provider_problem_alerts(state, self.policy, NOW, {})
        self.assertEqual(1, len(alerts), "auth alerts on the very first detection, no threshold wait")
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertEqual(EASY, alerts[0]["kind"])

    def test_a_noisy_week_of_transient_errors_never_alerts(self):
        # Each blip is detected on one tick (strikes=1, fresh first_seen) and
        # is gone by the next -- exactly what bin/ntfy-notify's own per-tick
        # prune of `provider_trouble_keys` produces for a transient error
        # that clears rather than persisting. Two hundred of these span far
        # more than a week at provider-failover's real 2-minute tick.
        seen_alert = False
        for blip in range(200):
            now = NOW + blip * 3600
            state = full_state({"openai": {
                "status": "error", "category": "network", "strikes": 1, "until": pf.iso(now + 600),
                "source": "detected", "evidence": "connection refused",
            }})
            first_seen = {key: now for key in provider_trouble_keys(state, self.policy, now)}
            alerts = provider_problem_alerts(state, self.policy, now, first_seen)
            seen_alert = seen_alert or bool(alerts)
        self.assertFalse(seen_alert)


if __name__ == "__main__":
    unittest.main()
