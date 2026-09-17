#!/usr/bin/env python3
"""Unit tests for lib/factory_continuity.py (docs/FACTORY_CONTINUITY.md sec5).

Fixtures reuse the real `project_human_state`/`project_candidate` contract
builders from factory_state.py, and mirror shapes already recorded on the
live system where possible -- e.g. the `af-oihx` "Gate: human" bead from the
2026-09-16 incident (docs/INCIDENT_2026-09-16-silent-campaign-stall.md) --
rather than inventing synthetic shapes the real contract could never emit.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_continuity import (  # noqa: E402
    CONTINUITY_STATES,
    ContinuityContractError,
    project_continuity_state,
    record_transition,
)
from factory_state import (  # noqa: E402
    project_candidate,
    project_human_state,
)


BASE = {
    "infrastructure": {"running": True, "usable": True, "degraded": False},
    "sources_consistent": True, "current": None, "needs_benjamin": None,
    "blockers": [], "queue": [], "resume_policy": {"mode": "manual"},
}


def _campaign_only_queue_item():
    return project_candidate({
        "id": "af-campaign", "title": "Nettoyage interne", "status": "deferred",
        "state": "queued", "urgency": "normal", "goal": "none",
    })


class ProjectContinuityStateTest(unittest.TestCase):
    def test_rejects_a_non_human_state_contract(self):
        with self.assertRaises(ContinuityContractError):
            project_continuity_state({"contract": "something-else"})

    def test_blocked_external_for_a_dead_controller_with_no_recorded_window(self):
        dead = project_human_state({
            **BASE,
            "infrastructure": {"running": False, "usable": False, "degraded": False},
        })
        result = project_continuity_state(dead)
        self.assertEqual("BLOCKED_EXTERNAL", result["state"])
        self.assertEqual(0, result["model_calls"])
        self.assertEqual(list(CONTINUITY_STATES), result["states"])

    def test_stopped_human_for_a_recorded_admin_maintenance_window(self):
        """A deliberate stop (docs/FACTORY_CONTINUITY.md class A/B) must never

        read the same as a crash (class C) -- this is the exact ambiguity
        the 2026-09-16 incident report calls out as still open at the
        section-1 taxonomy level, but factory_state.py already resolves it
        for the one concrete signal that exists: a persisted `admin` block.
        """
        window = project_human_state({
            **BASE,
            "infrastructure": {"running": False, "usable": False, "degraded": False},
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "blocked",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Benjamin", "gc.campaign_action": "Aucune action pendant la fenêtre.",
                "gc.campaign_block_kind": "admin", "gc.campaign_cause": "Fenêtre de maintenance planifiée.",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("STOPPED_HUMAN", project_continuity_state(window)["state"])

    def test_stopped_human_when_the_release_target_is_proven(self):
        completed = project_human_state({
            **BASE, "queue": [_campaign_only_queue_item()],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "active",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("completed", completed["campaign"]["state"])
        self.assertEqual("STOPPED_HUMAN", project_continuity_state(completed)["state"])

    def test_awaiting_gate_for_a_real_recorded_human_decision(self):
        """Mirrors af-oihx, the actual 'Gate: human' bead from the incident:

        `gc bd show af-oihx --json` (still queryable, closed) recorded a
        Mayor/Benjamin decision blocking af-u8id.4 for ~2h with no
        escalation. docs/FACTORY_CONTINUITY.md sec5 defines AWAITING_GATE as
        "a 'Gate: human' OR reserved decision is open" -- the reserved-
        decision half is what `needs_benjamin` already encodes end to end.
        """
        needs_benjamin = (
            "Blocked on mayor decision re af-wisp-ds03ds: (1) mol-polecat-commit "
            "direct-to-main routing conflicts with this bead's own independent-"
            "review requirement, (2) required-vs-backward-compatible schema scope "
            "conflict, (3) ADR-0021 has no written ADR yet, (4) intake protocol v2 "
            "needs an independent Verify pass a single writer can't supply."
        )
        gated = project_human_state({**BASE, "needs_benjamin": needs_benjamin})
        self.assertEqual("blocking_decision", gated["resume"]["mode"])
        self.assertEqual("AWAITING_GATE", project_continuity_state(gated)["state"])

    def test_blocked_stalled_for_a_non_admin_campaign_block(self):
        blocked = project_human_state({
            **BASE, "queue": [project_candidate({
                "id": "af-next", "title": "Prochain résultat", "status": "deferred",
                "state": "queued", "urgency": "normal", "goal": "af-goal",
            })],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "blocked",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Mayor", "gc.campaign_action": "Réparer le store en panne.",
                "gc.campaign_block_kind": "durable_failure", "gc.campaign_cause": "Store Dolt en quarantaine.",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("campaign_blocked", blocked["resume"]["mode"])
        self.assertEqual("BLOCKED_STALLED", project_continuity_state(blocked)["state"])

    def test_blocked_stalled_for_a_bounded_result_blocker(self):
        stuck = project_human_state({
            **BASE,
            "current": {
                "id": "af-work", "title": "Corriger l'import CSV", "state": "blocked",
                "cause": "Dépendance externe indisponible.",
            },
        })
        self.assertEqual("blocked", stuck["resume"]["mode"])
        self.assertEqual("BLOCKED_STALLED", project_continuity_state(stuck)["state"])

    def test_materializing_when_the_sentinel_has_woken_the_mayor(self):
        materializing = project_human_state({
            **BASE, "queue": [project_candidate({
                "id": "af-next", "title": "Prochain résultat", "status": "deferred",
                "state": "queued", "urgency": "normal", "goal": "af-goal",
            })],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "active",
                "gc.campaign_candidate": "af-next", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
                "gc.campaign_wake_state": "pending", "gc.campaign_wake_key": "af-next:1",
                "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("awaiting_mayor", materializing["campaign"]["state"])
        self.assertEqual("MATERIALIZING", project_continuity_state(materializing)["state"])

    def test_dispatching_when_an_agent_is_actively_working(self):
        active = project_human_state({
            **BASE,
            "current": {
                "id": "af-work", "title": "Implémenter la vue", "state": "active",
                "agent": "claude-4", "phase": "Écriture des tests",
            },
        })
        self.assertEqual("active_delivery", active["resume"]["mode"])
        self.assertEqual("DISPATCHING", project_continuity_state(active)["state"])

    def test_idle_release_queue_when_a_candidate_is_eligible_but_not_woken(self):
        idle_queue = project_human_state({
            **BASE, "queue": [_campaign_only_queue_item(), project_candidate({
                "id": "af-next", "title": "Prochain résultat", "status": "deferred",
                "state": "queued", "urgency": "normal", "goal": "af-goal",
            })],
            "resume_policy": {"mode": "automatic_campaign", "condition": "Fenêtre autorisée"},
            "campaign_metadata": {
                "gc.campaign_mode": "automatic", "gc.campaign_state": "active",
                "gc.campaign_candidate": "af-cm1l", "gc.campaign_condition": "Fenêtre autorisée",
                "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
                "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
            },
        })
        self.assertEqual("active", idle_queue["campaign"]["state"])
        self.assertEqual("IDLE_RELEASE_QUEUE", project_continuity_state(idle_queue)["state"])

    def test_idle_ladder_when_nothing_is_queued_and_no_campaign_runs(self):
        empty = project_human_state({**BASE, "queue": [_campaign_only_queue_item()]})
        self.assertEqual("no_candidate", empty["resume"]["mode"])
        self.assertFalse(empty["campaign"]["enabled"])
        self.assertEqual("IDLE_LADDER", project_continuity_state(empty)["state"])


class RecordTransitionTest(unittest.TestCase):
    def test_first_transition_is_recorded(self):
        history = record_transition([], "DISPATCHING", "2026-09-17T21:00:00Z")
        self.assertEqual([{"state": "DISPATCHING", "since": "2026-09-17T21:00:00Z"}], history)

    def test_repeating_the_same_state_does_not_append(self):
        history = [{"state": "DISPATCHING", "since": "2026-09-17T21:00:00Z"}]
        unchanged = record_transition(history, "DISPATCHING", "2026-09-17T21:05:00Z")
        self.assertEqual(history, unchanged)
        self.assertIsNot(history, unchanged)  # still a fresh list, never the caller's own

    def test_a_real_change_appends_a_new_entry(self):
        history = [{"state": "DISPATCHING", "since": "2026-09-17T21:00:00Z"}]
        updated = record_transition(history, "AWAITING_GATE", "2026-09-17T21:24:00Z")
        self.assertEqual([
            {"state": "DISPATCHING", "since": "2026-09-17T21:00:00Z"},
            {"state": "AWAITING_GATE", "since": "2026-09-17T21:24:00Z"},
        ], updated)

    def test_history_is_capped_to_the_limit(self):
        history = [{"state": s, "since": f"t{i}"} for i, s in enumerate(
            ["DISPATCHING", "AWAITING_GATE", "DISPATCHING"]
        )]
        updated = record_transition(history, "IDLE_LADDER", "t3", limit=2)
        self.assertEqual([
            {"state": "DISPATCHING", "since": "t2"},
            {"state": "IDLE_LADDER", "since": "t3"},
        ], updated)

    def test_rejects_an_unknown_state(self):
        with self.assertRaises(ContinuityContractError):
            record_transition([], "NOT_A_REAL_STATE", "2026-09-17T21:00:00Z")

    def test_rejects_a_blank_timestamp(self):
        with self.assertRaises(ContinuityContractError):
            record_transition([], "IDLE_LADDER", "  ")


if __name__ == "__main__":
    unittest.main()
