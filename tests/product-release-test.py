#!/usr/bin/env python3

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from product_release import (  # noqa: E402
    CONTRACT,
    RELEASE_STATES,
    RESERVED_CLASSES,
    ReleaseContractError,
    load_release_contract,
    project_operational_release,
    project_release,
    project_target_doc,
    project_vision,
    select_campaign_work,
    start_next_version,
    transition_release,
    validate_release_contract,
)

SCHEMA_PATH = ROOT / "config" / "product-release.schema.json"
PRODUCTION_RELEASE_PATH = ROOT / "config" / "releases" / "saymyname-v1.json"


def _evidence(status="proven"):
    return [{"kind": "document", "ref": "fixture", "status": status}]


def base_release(**overrides):
    value = {
        "$schema": "../product-release.schema.json",
        "contract": CONTRACT,
        "schema_version": 1,
        "product": "test-product",
        "version": "V1",
        "title": "Test release",
        "state": "approved",
        "next_version": "V2",
        "revision": 1,
        "objective": {
            "statement": "Ship the test product.",
            "set_by": "Benjamin",
            "set_at": "2026-09-16T00:00:00Z",
        },
        "origin": {
            "kind": "greenfield",
            "statement": "Build it from scratch.",
            "sources": [],
            "discovery": {
                "generated_at": "2026-09-16T00:00:00Z",
                "method": "deterministic_scan",
                "findings": [],
            },
        },
        "autonomy": {
            "level": "L2",
            "label": "Delegated",
            "granted_by": "Benjamin",
            "granted_at": "2026-09-16T00:00:00Z",
            "reserved_questions": sorted(RESERVED_CLASSES),
        },
        "intake": {
            "state": "complete",
            "question_budget": {
                "max_first_pass": 5, "max_per_iteration": 2, "spent": 0, "exhausted": False,
            },
            "questions": [],
            "exit_criteria": [
                {"id": "ec1", "statement": "Every criterion has an acceptance statement.", "satisfied": True},
            ],
        },
        "assumptions": [],
        "budget": {
            "max_consecutive_no_progress": 3,
            "spent": {"delivery_tokens": 0, "clarification_tokens": 0, "consecutive_no_progress": 0},
        },
        "maturity": {"level": "partial", "label": "Test", "criteria": ["c1"]},
        "capabilities": [
            {"id": "cap1", "title": "Cap 1", "description": "d", "status": "proven", "evidence": _evidence()},
        ],
        "journeys": [
            {
                "id": "j1", "title": "Journey", "description": "d", "status": "proven",
                "evidence": _evidence(), "capability_refs": ["cap1"],
            },
        ],
        "included": [],
        "excluded": [],
        "dependencies": [],
        "decisions": [],
        "criteria": [
            {
                "id": "c1", "title": "Criterion", "description": "d", "status": "proven",
                "evidence": _evidence(), "capability_refs": ["cap1"], "journey_refs": ["j1"],
                "acceptance": "A human can see it work.",
            },
        ],
        "work_graph": [
            {
                "id": "w1", "work_ref": None, "title": "Work", "kind": "product",
                "state": "delivered", "order": 1, "dedupe_key": "w1",
                "criterion_refs": ["c1"], "depends_on": [], "independence": "proven", "blocker": None,
            },
        ],
        "factory_improvements": [],
    }
    value.update(overrides)
    return value


def work_node(node_id, **overrides):
    node = {
        "id": node_id, "work_ref": None, "title": node_id, "kind": "product",
        "state": "candidate", "order": 1, "dedupe_key": node_id,
        "criterion_refs": ["c1"], "depends_on": [], "independence": "proven", "blocker": None,
    }
    node.update(overrides)
    return node


class SchemaShapeTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_module_constants_match_the_versioned_schema(self):
        self.assertEqual(self.schema["properties"]["contract"]["const"], CONTRACT)
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(set(self.schema["properties"]["state"]["enum"]), set(RELEASE_STATES))

    def test_required_top_level_fields_match_python_validation(self):
        required = set(self.schema["required"])
        value = base_release()
        for field in sorted(required):
            mutated = {key: item for key, item in value.items() if key != field}
            with self.assertRaisesRegex(ReleaseContractError, "incomplet", msg=field):
                validate_release_contract(mutated)

    def test_production_release_contract_matches_the_adr_0015_extended_shape(self):
        # af-u8id.4.2 migrated config/releases/saymyname-v1.json onto the
        # extended contract (origin/autonomy/intake/assumptions/budget +
        # per-criterion acceptance + ADR-0021 review on takeover-derived
        # blocks). It must load and validate cleanly through
        # validate_release_contract, the same pure semantic check
        # `bin/product-release validate` runs in production.
        value = load_release_contract(PRODUCTION_RELEASE_PATH)
        self.assertEqual(value["origin"]["kind"], "takeover")
        self.assertEqual(value["autonomy"]["level"], "L3")
        self.assertEqual(value["intake"]["state"], "complete")


class ValidationTest(unittest.TestCase):
    def test_accepts_a_well_formed_release(self):
        value = validate_release_contract(base_release())
        self.assertEqual("test-product", value["product"])

    def test_rejects_wrong_contract_or_schema_version(self):
        with self.assertRaisesRegex(ReleaseContractError, "non prise en charge"):
            validate_release_contract(base_release(contract="wrong/v1"))
        with self.assertRaisesRegex(ReleaseContractError, "non prise en charge"):
            validate_release_contract(base_release(schema_version=2))

    def test_rejects_malformed_product_or_version(self):
        with self.assertRaises(ReleaseContractError):
            validate_release_contract(base_release(product="Not_Slug"))
        with self.assertRaises(ReleaseContractError):
            validate_release_contract(base_release(version="1"))
        with self.assertRaises(ReleaseContractError):
            validate_release_contract(base_release(version="V0"))

    def test_next_version_must_exceed_current_version(self):
        with self.assertRaisesRegex(ReleaseContractError, "postérieure"):
            validate_release_contract(base_release(next_version="V1"))

    def test_next_version_may_be_absent(self):
        value = validate_release_contract(base_release(next_version=None))
        self.assertIsNone(value["next_version"])

    def test_rejects_unknown_release_state(self):
        with self.assertRaisesRegex(ReleaseContractError, "État de release inconnu"):
            validate_release_contract(base_release(state="shipped"))

    def test_maturity_criteria_must_reference_known_criterion(self):
        value = base_release()
        value["maturity"] = {"level": "partial", "label": "Test", "criteria": ["missing"]}
        with self.assertRaisesRegex(ReleaseContractError, "maturity.criteria"):
            validate_release_contract(value)

    def test_journeys_must_reference_at_least_one_capability(self):
        value = base_release()
        value["journeys"][0]["capability_refs"] = []
        with self.assertRaisesRegex(ReleaseContractError, "parcours doit référencer"):
            validate_release_contract(value)

    def test_dependencies_required_for_must_reference_capability_or_journey(self):
        value = base_release()
        value["dependencies"] = [{
            "id": "dep1", "title": "Dep", "description": "d", "status": "proven",
            "evidence": _evidence(), "required_for": ["missing"],
        }]
        with self.assertRaisesRegex(ReleaseContractError, "référence inconnue"):
            validate_release_contract(value)

    def test_criteria_must_reference_a_capability_or_a_journey(self):
        value = base_release()
        value["criteria"][0]["capability_refs"] = []
        value["criteria"][0]["journey_refs"] = []
        with self.assertRaisesRegex(ReleaseContractError, "critère doit être lié"):
            validate_release_contract(value)

    def test_decisions_reject_duplicate_ids_and_duplicate_options(self):
        decision = {
            "id": "d1", "title": "Decide", "source_ref": "docs/DECISIONS.md#d1",
            "status": "decision_required", "risk": "high", "revision": 1,
            "capability_refs": ["cap1"], "dependency_refs": [], "options": [],
        }
        value = base_release()
        value["decisions"] = [decision, dict(decision)]
        with self.assertRaisesRegex(ReleaseContractError, "Décision dupliquée"):
            validate_release_contract(value)

        with_options = base_release()
        with_options["decisions"] = [{
            **decision,
            "options": [{"id": "yes", "label": "Yes"}, {"id": "yes", "label": "Also yes"}],
        }]
        with self.assertRaisesRegex(ReleaseContractError, "Option dupliquée"):
            validate_release_contract(with_options)

    def test_work_graph_rejects_duplicate_ids_and_dedupe_keys(self):
        value = base_release()
        value["work_graph"] = [work_node("w1", state="delivered"), work_node("w1", state="delivered")]
        with self.assertRaisesRegex(ReleaseContractError, "double"):
            validate_release_contract(value)

        value = base_release()
        value["work_graph"] = [
            work_node("w1", state="delivered", dedupe_key="same"),
            work_node("w2", state="delivered", dedupe_key="same"),
        ]
        with self.assertRaisesRegex(ReleaseContractError, "double"):
            validate_release_contract(value)

    def test_work_graph_node_must_be_traceable_to_a_criterion(self):
        value = base_release()
        value["work_graph"] = [work_node("w1", state="delivered", criterion_refs=[])]
        with self.assertRaisesRegex(ReleaseContractError, "traçable vers au moins un critère"):
            validate_release_contract(value)

    def test_work_graph_rejects_self_dependency(self):
        value = base_release()
        value["work_graph"] = [work_node("w1", state="delivered", depends_on=["w1"])]
        with self.assertRaisesRegex(ReleaseContractError, "dépendre de lui-même"):
            validate_release_contract(value)

    def test_work_graph_rejects_a_cycle(self):
        value = base_release()
        value["work_graph"] = [
            work_node("w1", state="delivered", depends_on=["w2"]),
            work_node("w2", state="delivered", depends_on=["w1"]),
        ]
        with self.assertRaisesRegex(ReleaseContractError, "cycle"):
            validate_release_contract(value)

    def test_work_graph_blocker_kind_decision_requires_a_known_decision(self):
        value = base_release()
        value["work_graph"] = [work_node(
            "w1", state="blocked",
            blocker={"kind": "decision", "decision_id": "missing", "cause": "c", "owner": "o", "action": "a"},
        )]
        with self.assertRaisesRegex(ReleaseContractError, "blocker.decision_id est inconnu"):
            validate_release_contract(value)

    def test_work_graph_blocker_decision_id_reserved_for_decision_kind(self):
        value = base_release()
        value["work_graph"] = [work_node(
            "w1", state="blocked",
            blocker={"kind": "admin", "decision_id": "d1", "cause": "c", "owner": "o", "action": "a"},
        )]
        with self.assertRaisesRegex(ReleaseContractError, "réservé aux décisions"):
            validate_release_contract(value)

    def test_af_cm1l_can_never_be_a_v1_product_capability(self):
        value = base_release()
        value["capabilities"][0]["work_ref"] = "af-cm1l"
        with self.assertRaisesRegex(ReleaseContractError, "af-cm1l"):
            validate_release_contract(value)


class ExtendedIntakeFieldsTest(unittest.TestCase):
    def test_criteria_require_a_human_observable_acceptance(self):
        value = base_release()
        del value["criteria"][0]["acceptance"]
        with self.assertRaises(ReleaseContractError):
            validate_release_contract(value)

    def test_autonomy_reserved_questions_must_contain_the_full_reserved_set(self):
        value = base_release()
        value["autonomy"]["reserved_questions"] = sorted(RESERVED_CLASSES - {"legal"})
        with self.assertRaisesRegex(ReleaseContractError, "ensemble complet"):
            validate_release_contract(value)

    def test_autonomy_version_transition_requires_human_cannot_be_false(self):
        value = base_release()
        value["autonomy"]["version_transition_requires_human"] = False
        with self.assertRaisesRegex(ReleaseContractError, "doit rester vrai"):
            validate_release_contract(value)

    def test_origin_conflict_mix_resolution_requires_a_detail(self):
        value = base_release()
        value["decisions"] = [{
            "id": "d1", "title": "Decide", "source_ref": "docs/DECISIONS.md#d1",
            "status": "decision_required", "risk": "high", "revision": 1,
            "reserved_class": "outcome", "capability_refs": ["cap1"], "dependency_refs": [], "options": [],
        }]
        value["origin"]["conflicts"] = [{
            "id": "conflict1", "summary": "Code disagrees.", "code_evidence": _evidence(),
            "intent_ref": "criteria/c1", "decision_id": "d1", "resolution": "mix",
        }]
        with self.assertRaisesRegex(ReleaseContractError, "resolution_detail"):
            validate_release_contract(value)

    def test_origin_conflict_decision_id_must_reference_a_known_decision(self):
        value = base_release()
        value["origin"]["conflicts"] = [{
            "id": "conflict1", "summary": "Code disagrees.", "code_evidence": _evidence(),
            "intent_ref": "criteria/c1", "decision_id": "missing", "resolution": "pending",
        }]
        with self.assertRaisesRegex(ReleaseContractError, "conflicts\\[0\\].decision_id"):
            validate_release_contract(value)

    def test_leverage_admitted_question_requires_leverage_refs(self):
        value = base_release()
        value["intake"]["questions"] = [{
            "id": "q1", "kind": "outcome", "prompt": "What does done mean?",
            "admitted_by": "leverage", "status": "pending",
        }]
        with self.assertRaisesRegex(ReleaseContractError, "leverage_refs"):
            validate_release_contract(value)

    def test_leverage_refs_must_reference_a_known_criterion_or_work_node(self):
        value = base_release()
        value["intake"]["questions"] = [{
            "id": "q1", "kind": "outcome", "prompt": "What does done mean?",
            "admitted_by": "leverage", "status": "pending", "leverage_refs": ["missing"],
        }]
        with self.assertRaisesRegex(ReleaseContractError, "leverage_refs"):
            validate_release_contract(value)

    def test_assumption_scope_refs_must_reference_a_known_id(self):
        value = base_release()
        value["assumptions"] = [{
            "id": "a1", "title": "Assume", "statement": "s", "rationale": "r",
            "confidence": "low", "status": "standing", "scope_refs": ["missing"], "invalidated_by": [],
        }]
        with self.assertRaisesRegex(ReleaseContractError, "scope_refs"):
            validate_release_contract(value)


class TakeoverReviewTest(unittest.TestCase):
    def _review(self, state, tier="static"):
        return {
            "state": state, "tier": tier, "reviewed_at": "2026-09-16T00:00:00Z",
            "reviewed_by": "factory:static", "ref": _evidence(), "notes": "Looks fine.",
        }

    def _unreviewed(self):
        return {
            "state": "unreviewed", "tier": None, "reviewed_at": None,
            "reviewed_by": None, "ref": [], "notes": "",
        }

    def test_takeover_derived_block_cannot_be_proven_while_unreviewed(self):
        value = base_release()
        value["capabilities"][0]["review"] = self._unreviewed()
        with self.assertRaisesRegex(ReleaseContractError, "unreviewed"):
            validate_release_contract(value)

    def test_takeover_derived_block_can_be_proven_once_reviewed_ok(self):
        value = base_release()
        value["capabilities"][0]["review"] = self._review("reviewed_ok")
        result = validate_release_contract(value)
        self.assertEqual("reviewed_ok", result["capabilities"][0]["review"]["state"])

    def test_takeover_derived_block_may_stay_assumed_while_unreviewed(self):
        value = base_release()
        value["capabilities"][0]["status"] = "assumed"
        value["capabilities"][0]["review"] = self._unreviewed()
        result = validate_release_contract(value)
        self.assertEqual("unreviewed", result["capabilities"][0]["review"]["state"])

    def test_review_object_rejects_an_unknown_state(self):
        value = base_release()
        review = self._unreviewed()
        review["state"] = "bogus"
        value["capabilities"][0]["review"] = review
        with self.assertRaises(ReleaseContractError):
            validate_release_contract(value)

    def test_takeover_derived_proven_block_with_no_review_key_is_rejected(self):
        # ADR-0021's exact fail-closed gap: a takeover-origin release with a
        # discovery-sourced (scan) evidence item on a proven block, and no
        # "review" key at all -- must not validate cleanly.
        value = base_release()
        value["origin"]["kind"] = "takeover"
        value["capabilities"][0]["evidence"] = [{"kind": "scan", "ref": "discovery-scan", "status": "proven"}]
        self.assertNotIn("review", value["capabilities"][0])
        with self.assertRaisesRegex(ReleaseContractError, "review"):
            validate_release_contract(value)

    def test_takeover_derived_block_without_discovery_evidence_does_not_require_review(self):
        value = base_release()
        value["origin"]["kind"] = "takeover"
        result = validate_release_contract(value)
        self.assertNotIn("review", result["capabilities"][0])


class IntakeStateTransitionTest(unittest.TestCase):
    def test_intake_to_draft_requires_intake_state_complete(self):
        value = base_release(state="intake", next_version="V2")
        value["intake"]["state"] = "awaiting_human"
        with self.assertRaisesRegex(ReleaseContractError, "intake.state doit être complete"):
            transition_release(value, "draft")

    def test_intake_to_draft_succeeds_once_intake_is_complete(self):
        value = base_release(state="intake", next_version="V2")
        value["intake"]["state"] = "complete"
        result = transition_release(value, "draft")
        self.assertEqual("draft", result["state"])

    def test_intake_release_is_not_executable(self):
        value = base_release(state="intake", next_version="V2")
        value["intake"]["state"] = "complete"
        result = select_campaign_work(value)
        self.assertEqual("release_not_executable", result["reason"])

    def test_enabled_campaign_cannot_execute_an_intake_release(self):
        value = base_release(state="intake", next_version="V2")
        value["intake"]["state"] = "complete"
        release = project_release(value)
        with self.assertRaisesRegex(ReleaseContractError, "intake"):
            project_operational_release(release, {"enabled": True})


class TransitionTest(unittest.TestCase):
    def test_same_state_transition_is_idempotent(self):
        value = base_release(state="approved")
        result = transition_release(value, "approved")
        self.assertEqual(value, result)
        self.assertIsNot(value, result)

    def test_forward_transitions_follow_the_state_machine(self):
        draft = base_release(state="draft")
        approved = transition_release(draft, "approved")
        self.assertEqual("approved", approved["state"])
        executing = transition_release(approved, "executing")
        self.assertEqual("executing", executing["state"])
        frozen = transition_release(executing, "frozen")
        self.assertEqual("frozen", frozen["state"])

    def test_frozen_release_is_immutable(self):
        frozen = base_release(state="frozen", next_version=None)
        with self.assertRaisesRegex(ReleaseContractError, "immuable"):
            transition_release(frozen, "draft")

    def test_rejects_skipping_a_state(self):
        with self.assertRaisesRegex(ReleaseContractError, "Transition interdite"):
            transition_release(base_release(state="draft"), "executing")

    def test_rejects_an_unknown_target_state(self):
        with self.assertRaisesRegex(ReleaseContractError, "état inconnu"):
            transition_release(base_release(state="draft"), "shipped")


class StartNextVersionTest(unittest.TestCase):
    def test_requires_the_exact_approved_next_version(self):
        value = base_release(state="executing", next_version="V2")
        with self.assertRaisesRegex(ReleaseContractError, "ne correspond pas"):
            start_next_version(value, "V3")

    def test_requires_executing_or_frozen_state(self):
        value = base_release(state="approved", next_version="V2")
        with self.assertRaisesRegex(ReleaseContractError, "executing ou frozen"):
            start_next_version(value, "V2")

    def test_freezes_an_executing_release_before_starting_next(self):
        value = base_release(state="executing", next_version="V2")
        result = start_next_version(value, "V2")
        self.assertEqual("frozen", result["frozen_release"]["state"])
        self.assertEqual("V2", result["next_version"])
        self.assertEqual("executing", value["state"])  # caller's value is untouched

    def test_an_already_frozen_release_stays_frozen(self):
        value = base_release(state="frozen", next_version="V2")
        result = start_next_version(value, "V2")
        self.assertEqual("frozen", result["frozen_release"]["state"])


class CampaignSelectionTest(unittest.TestCase):
    def test_release_not_executable_when_draft_or_frozen(self):
        for state in ("draft", "frozen"):
            value = base_release(state=state, next_version=None if state == "frozen" else "V2")
            result = select_campaign_work(value)
            self.assertEqual("release_not_executable", result["reason"])
            self.assertIsNone(result["selected"])
            self.assertEqual("PO", result["owner"])

    def test_release_target_proven_when_nothing_left_to_select(self):
        value = base_release()  # default work_graph is fully delivered; criteria proven
        result = select_campaign_work(value)
        self.assertEqual("release_target_proven", result["reason"])
        self.assertIsNone(result["selected"])
        self.assertEqual("none", result["owner"])

    def test_no_proven_independent_work_when_criteria_are_not_all_proven(self):
        value = base_release()
        value["criteria"][0]["status"] = "partial"
        result = select_campaign_work(value)
        self.assertEqual("no_proven_independent_work", result["reason"])
        self.assertIsNone(result["selected"])

    def test_selects_the_lowest_order_proven_independent_candidate(self):
        value = base_release()
        value["work_graph"] = [
            work_node("w2", order=2),
            work_node("w1", order=1),
        ]
        result = select_campaign_work(value)
        self.assertEqual("proven_independent_work", result["reason"])
        self.assertEqual("w1", result["selected"]["id"])
        self.assertEqual("Mayor", result["owner"])

    def test_unknown_independence_does_not_block_a_later_proven_candidate(self):
        value = base_release()
        value["work_graph"] = [
            work_node("unknown-first", order=1, independence="unknown"),
            work_node("proven-second", order=2, independence="proven"),
        ]
        result = select_campaign_work(value)
        self.assertEqual("proven_independent_work", result["reason"])
        self.assertEqual("proven-second", result["selected"]["id"])

    def test_independence_unknown_reason_when_no_proven_candidate_exists(self):
        value = base_release()
        value["work_graph"] = [work_node("w1", independence="unknown")]
        result = select_campaign_work(value)
        self.assertEqual("independence_unknown", result["reason"])
        self.assertIsNone(result["selected"])

    def test_a_candidate_waits_for_its_dependency_to_be_delivered(self):
        value = base_release()
        value["work_graph"] = [
            work_node("dep", order=1, state="active"),
            work_node("w1", order=2, depends_on=["dep"]),
        ]
        result = select_campaign_work(value)
        self.assertIsNone(result["selected"])

        value["work_graph"][0]["state"] = "delivered"
        result = select_campaign_work(value)
        self.assertEqual("w1", result["selected"]["id"])

    def test_blocked_reason_reports_kind_cause_owner_action_and_decision_id(self):
        value = base_release()
        value["decisions"] = [{
            "id": "d1", "title": "Decide", "source_ref": "docs/DECISIONS.md#d1",
            "status": "decision_required", "risk": "high", "revision": 1,
            "capability_refs": ["cap1"], "dependency_refs": [], "options": [],
        }]
        value["work_graph"] = [work_node(
            "w1", state="blocked",
            blocker={"kind": "decision", "decision_id": "d1", "cause": "Attente", "owner": "Benjamin", "action": "Décider"},
        )]
        result = select_campaign_work(value)
        self.assertEqual("blocked_decision", result["reason"])
        self.assertEqual("Benjamin", result["owner"])
        self.assertEqual("Décider", result["action"])
        self.assertEqual("Attente", result["cause"])
        self.assertEqual("d1", result["decision_id"])

    def test_blocked_tie_break_is_by_blocker_kind_then_cause_not_by_node_order(self):
        value = base_release()
        value["work_graph"] = [
            work_node(
                "later-in-list-first-alphabetically", order=1, state="blocked",
                blocker={"kind": "admin", "cause": "z-cause", "owner": "Benjamin", "action": "Autoriser"},
            ),
            work_node(
                "earlier-in-list-second-alphabetically", order=2, state="blocked",
                blocker={"kind": "limit", "cause": "a-cause", "owner": "Benjamin", "action": "Attendre"},
            ),
        ]
        result = select_campaign_work(value)
        self.assertEqual("blocked_admin", result["reason"])
        self.assertIsNone(result["decision_id"])


class ProjectionTest(unittest.TestCase):
    def test_project_release_applies_status_labels_and_strips_schema(self):
        value = base_release()
        projected = project_release(value)
        self.assertEqual("Prouvé", projected["capabilities"][0]["status_label"])
        self.assertEqual("Approuvée", projected["state_label"])
        self.assertNotIn("$schema", projected)
        self.assertEqual(0, projected["model_calls"])

    def test_project_release_exposes_the_first_decision_required_intervention(self):
        value = base_release()
        value["decisions"] = [
            {
                "id": "d1", "title": "Decide", "source_ref": "docs/DECISIONS.md#d1",
                "status": "decision_required", "risk": "high", "revision": 1,
                "capability_refs": ["cap1"], "dependency_refs": [], "options": [],
            },
        ]
        projected = project_release(value)
        self.assertEqual("d1", projected["intervention"]["decision_id"])
        self.assertEqual("#view=project&releaseDecision=d1", projected["intervention"]["deep_link"])

    def test_project_release_intervention_is_none_without_a_pending_decision(self):
        projected = project_release(base_release())
        self.assertIsNone(projected["intervention"])

    def test_project_release_embeds_the_campaign_selection(self):
        projected = project_release(base_release())
        self.assertEqual("release_target_proven", projected["campaign"]["reason"])


class TargetDocProjectionTest(unittest.TestCase):
    def test_chain_projects_journey_to_capability_to_criterion_to_work(self):
        doc = project_target_doc(base_release())
        self.assertIn(
            {"kind": "journey_to_capability", "from": "j1", "to": "cap1"}, doc["chain"]["edges"],
        )
        self.assertIn(
            {"kind": "capability_to_criterion", "from": "cap1", "to": "c1"}, doc["chain"]["edges"],
        )
        self.assertIn(
            {"kind": "criterion_to_work", "from": "c1", "to": "w1"}, doc["chain"]["edges"],
        )

    def test_work_graph_carries_dependency_edges(self):
        value = base_release()
        value["work_graph"] = [
            work_node("w1", state="delivered"),
            work_node("w2", depends_on=["w1"]),
        ]
        doc = project_target_doc(value)
        self.assertIn({"from": "w1", "to": "w2"}, doc["work_graph"]["edges"])
        self.assertEqual(2, len(doc["work_graph"]["nodes"]))

    def test_assumption_overlay_lists_scope_and_confidence_not_a_separate_graph(self):
        value = base_release()
        value["assumptions"] = [
            {
                "id": "a1", "title": "Assumed", "statement": "s", "rationale": "r",
                "confidence": "medium", "status": "standing", "scope_refs": ["w1"],
                "invalidated_by": [],
            },
        ]
        doc = project_target_doc(value)
        self.assertEqual(1, len(doc["assumption_overlay"]))
        self.assertEqual(["w1"], doc["assumption_overlay"][0]["scope_refs"])
        self.assertEqual("medium", doc["assumption_overlay"][0]["confidence"])

    def test_blocker_subgraph_is_filtered_from_the_same_work_graph(self):
        value = base_release()
        value["work_graph"] = [
            work_node("w1", state="delivered"),
            work_node(
                "w2", depends_on=["w1"], state="blocked",
                blocker={
                    "kind": "decision", "decision_id": "d1", "cause": "needs a call",
                    "owner": "Benjamin", "action": "decide",
                },
            ),
        ]
        value["decisions"] = [
            {
                "id": "d1", "title": "Decide", "source_ref": "docs/DECISIONS.md#d1",
                "status": "decision_required", "risk": "high", "revision": 1,
                "capability_refs": [], "dependency_refs": [], "options": [],
            },
        ]
        doc = project_target_doc(value)
        self.assertEqual(["w2"], [node["id"] for node in doc["blocker_subgraph"]["nodes"]])
        self.assertIn({"from": "w1", "to": "w2"}, doc["blocker_subgraph"]["edges"])

    def test_work_ref_index_joins_work_graph_nodes_to_their_ticket(self):
        value = base_release()
        value["work_graph"] = [work_node("w1", work_ref="af-abcde", state="delivered")]
        doc = project_target_doc(value)
        self.assertEqual({"w1": "af-abcde"}, doc["work_ref_index"])

    def test_is_zero_token_and_leaves_the_source_value_unmutated(self):
        value = base_release()
        before = copy.deepcopy(value)
        doc = project_target_doc(value)
        self.assertEqual(0, doc["model_calls"])
        self.assertEqual(before, value)


class VisionProjectionTest(unittest.TestCase):
    def test_jtbd_is_deduced_from_the_objective_statement(self):
        vision = project_vision(base_release())
        self.assertEqual("deduit", vision["jtbd"]["label"])
        self.assertEqual("Ship the test product.", vision["jtbd"]["text"])
        self.assertIn("Benjamin", vision["jtbd"]["source"])

    def test_primary_user_is_marked_a_trancher_when_no_field_carries_it(self):
        vision = project_vision(base_release())
        self.assertEqual("a_trancher", vision["primary_user"]["label"])
        self.assertIsNone(vision["primary_user"]["text"])

    def test_non_goals_are_deduced_from_out_of_version_excluded_items(self):
        value = base_release()
        value["excluded"] = [
            {
                "id": "payment", "title": "Payment", "description": "Later.",
                "kind": "product", "status": "out_of_version",
                "evidence": [{"kind": "document", "ref": "docs/DECISIONS.md#payment", "status": "out_of_version"}],
            },
            {
                "id": "in-scope", "title": "In scope after all", "description": "d",
                "kind": "product", "status": "proven", "evidence": _evidence(),
            },
        ]
        vision = project_vision(value)
        self.assertEqual("deduit", vision["non_goals"]["label"])
        self.assertEqual(["payment"], [item["id"] for item in vision["non_goals"]["items"]])
        self.assertEqual(["docs/DECISIONS.md#payment"], vision["non_goals"]["items"][0]["source"])

    def test_is_zero_token_and_leaves_the_source_value_unmutated(self):
        value = base_release()
        before = copy.deepcopy(value)
        vision = project_vision(value)
        self.assertEqual(0, vision["model_calls"])
        self.assertEqual(before, value)


class OperationalProjectionTest(unittest.TestCase):
    def test_rejects_a_release_without_the_release_contract(self):
        with self.assertRaisesRegex(ReleaseContractError, "Projection de release invalide"):
            project_operational_release({"contract": "wrong"}, {"enabled": False})

    def test_rejects_a_campaign_projection_without_an_enabled_flag(self):
        release = project_release(base_release())
        with self.assertRaisesRegex(ReleaseContractError, "Projection de campagne invalide"):
            project_operational_release(release, {})

    def test_disabled_campaign_keeps_the_git_truth_state(self):
        release = project_release(base_release(state="approved"))
        result = project_operational_release(release, {"enabled": False})
        self.assertEqual("approved", result["truth_state"])
        self.assertEqual("approved", result["operational_state"])
        self.assertEqual("Approuvée · campagne non activée", result["operational_state_label"])

    def test_enabled_campaign_cannot_execute_a_draft_release(self):
        release = project_release(base_release(state="draft"))
        with self.assertRaisesRegex(ReleaseContractError, "draft"):
            project_operational_release(release, {"enabled": True})

    def test_enabled_campaign_reports_executing_for_approved_or_executing_truth(self):
        for state in ("approved", "executing"):
            release = project_release(base_release(state=state))
            result = project_operational_release(release, {"enabled": True})
            self.assertEqual("executing", result["operational_state"])
            self.assertEqual("En exécution par la campagne", result["operational_state_label"])

    def test_enabled_campaign_leaves_a_frozen_release_frozen(self):
        release = project_release(base_release(state="frozen", next_version=None))
        result = project_operational_release(release, {"enabled": True})
        self.assertEqual("frozen", result["operational_state"])


class LoadReleaseContractTest(unittest.TestCase):
    def test_missing_file_raises_a_release_contract_error(self):
        with self.assertRaisesRegex(ReleaseContractError, "illisible"):
            load_release_contract(ROOT / "config" / "releases" / "does-not-exist.json")

    def test_malformed_json_raises_a_release_contract_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(ReleaseContractError, "illisible"):
                load_release_contract(path)


if __name__ == "__main__":
    unittest.main()
