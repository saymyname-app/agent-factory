#!/usr/bin/env python3
"""Rules of lib/ntfy_notify.py: what Benjamin's phone says, and when.

Contract set by Benjamin on 2026-09-18: every push states the real state in
one sentence, then exactly one of: nothing to do (and what to follow), an
easy action, or a delegation with a sentence he can type word for word. Never
a bead id.
"""
import re
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from ntfy_notify import (  # noqa: E402
    DELEGATE, EASY, NOTHING, PROMPTS, compute_alerts, compute_digest, diff_alerts, digest_due,
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


if __name__ == "__main__":
    unittest.main()
