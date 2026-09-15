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
    ReleaseContractError,
    load_release_contract,
    project_operational_release,
    project_release,
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

    def test_production_release_contract_validates_against_python_semantics(self):
        value = load_release_contract(PRODUCTION_RELEASE_PATH)
        self.assertEqual(CONTRACT, value["contract"])
        self.assertEqual("saymyname", value["product"])
        self.assertEqual("V1", value["version"])
        projected = project_release(value)
        self.assertEqual(0, projected["model_calls"])
        self.assertNotIn("$schema", projected)


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
