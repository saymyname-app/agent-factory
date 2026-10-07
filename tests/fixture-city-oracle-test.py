#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "fixture-city-oracle"
FIXTURES = ROOT / "tests" / "fixtures" / "fixture-city"
OPERATOR = FIXTURES / "operator"
DELIVERY_DRIVER = FIXTURES / "delivery-driver"
DELIVERY_STATES = ["published", "started", "red", "frozen", "coded", "reviewed", "evaluated", "merged", "closed"]
GATE_CONDITIONS = ["criteria", "handoff", "evaluation", "fidelity", "deferral", "merge", "evidence", "tdd", "review"]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BWRAP_PROFILE = ROOT / "config" / "fixture-city-bwrap.apparmor"


class FixtureCityOracleTest(unittest.TestCase):
    def invoke(self, scenario, *, check=True):
        return subprocess.run(
            (
                str(ORACLE),
                "run",
                str(FIXTURES / scenario),
                "--operator",
                str(OPERATOR),
                "--publication-door",
                str(OPERATOR),
            ),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_single_rig_run_observes_the_public_lifecycle_deterministically(self):
        first = self.invoke("single-rig.json")
        second = self.invoke("single-rig.json")
        self.assertEqual(first.stdout, second.stdout)

        result = json.loads(first.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("single-rig", result["scenario_id"])
        self.assertEqual(
            [
                "REQUESTED",
                "SPEC_AWAITING_APPROVAL",
                "APPROVED_SPEC",
                "DELIVERY_GRAPH_PUBLISHED",
                "DELIVERING",
                "DELIVERED_OUTCOME",
                "ACCEPTED_OUTCOME",
            ],
            result["planning_states"],
        )
        self.assertEqual("published", result["publication"]["state"])
        self.assertTrue(result["publication"]["convoy_id"].startswith("convoy-"))
        self.assertEqual("single-rig", result["integration"]["mode"])
        self.assertEqual(
            [{
                "rig": "fixture-app",
                "revision": "7a9e5aeffb4f73c649a22fd666208a22a80d9f46",
                "verified": True,
            }],
            [
                {key: evidence[key] for key in ("rig", "revision", "verified")}
                for evidence in result["integration"]["evidence"]
            ],
        )
        self.assertRegex(result["integration"]["evidence"][0]["tree"], r"^[0-9a-f]{40}$")
        self.assertTrue(result["integration"]["assembly_check"]["passed"])
        self.assertEqual(
            {"delivered": True, "accepted": True}, result["outcome"]
        )
        self.assertEqual([], result["effects"])
        self.assertEqual(["publish"], result["interfaces"]["write_doors"])
        self.assertNotIn("cockpit", json.dumps(result).lower())

    def test_multi_rig_run_requires_the_exact_participating_revisions(self):
        result = json.loads(self.invoke("multi-rig.json").stdout)
        self.assertEqual("exact-revision-multi-rig", result["integration"]["mode"])
        self.assertEqual(
            [
                {
                    "rig": "fixture-api",
                    "revision": "73ac3a0db24ecb1d522b83a454526b75c4a83668",
                    "verified": True,
                },
                {
                    "rig": "fixture-web",
                    "revision": "97e20dbabc2ae1c7874c5ae9be50fee49d3ac654",
                    "verified": True,
                },
            ],
            [
                {key: evidence[key] for key in ("rig", "revision", "verified")}
                for evidence in result["integration"]["evidence"]
            ],
        )
        self.assertTrue(result["integration"]["assembly_check"]["passed"])
        self.assertEqual(2, len(result["integration"]["assembly_check"]["participants"]))
        self.assertEqual(
            {"delivered": True, "accepted": True}, result["outcome"]
        )

    def test_injected_publication_failure_leaves_no_graph_or_convoy(self):
        result = json.loads(self.invoke("publication-failure.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("failed_atomically", result["publication"]["state"])
        self.assertIsNone(result["publication"]["graph_digest"])
        self.assertIsNone(result["publication"]["convoy_id"])
        self.assertEqual(
            {"delivered": False, "accepted": False}, result["outcome"]
        )
        self.assertEqual([], result["integration"]["evidence"])
        self.assertIsNone(result["integration"]["assembly_check"])
        self.assertEqual([], result["effects"])

    def test_oracle_rejects_a_failed_door_that_leaks_a_partial_graph(self):
        result = self.invoke("partial-publication-bug.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("failed publication left a partial delivery graph", result.stderr)

    def test_oracle_rejects_an_arbitrary_revision_string(self):
        result = self.invoke("wrong-revision.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not pinned revision", result.stderr)

    def test_exact_revisions_still_fail_when_their_public_interfaces_are_incompatible(self):
        advertised = json.loads(
            (FIXTURES / "rigs" / "fixture-web-incompatible" / "fixture-interface.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual({"fixture-status/v1": "ready"}, advertised["requires"])
        result = self.invoke("incompatible-assembly.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("assembled public behavior failed", result.stderr)

    def test_oracle_rejects_a_publication_with_a_duplicate_slice_key(self):
        result = self.invoke("duplicate-graph-node.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("exact approved slice keys", result.stderr)

    def test_adapter_runs_without_host_identity_files_network_or_system_writes(self):
        result = json.loads(self.invoke("containment.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual([], result["effects"])

    def test_adapter_cannot_replace_bytes_in_an_exact_revision_checkout(self):
        result = self.invoke("dirty-assembly-attempt.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("assembly checkout is read-only", result.stderr)

    def test_ci_preserves_the_global_user_namespace_restriction(self):
        workflow = CI_WORKFLOW.read_text()
        profile = BWRAP_PROFILE.read_text()

        self.assertIn("apparmor_restrict_unprivileged_userns", workflow)
        self.assertIn("config/fixture-city-bwrap.apparmor", workflow)
        self.assertNotIn("sysctl -w", workflow)
        self.assertIn(
            "profile fixture-city-bwrap /usr/bin/bwrap flags=(unconfined)",
            profile,
        )
        self.assertIn("userns,", profile)

    def test_reference_protocol_does_not_overclaim_three_rig_coverage(self):
        result = self.invoke("unsupported-three-rig.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("support one or two exact-revision rigs", result.stderr)

    def test_new_planning_run_selecting_legacy_planning_base_fails_closed(self):
        result = json.loads(self.invoke("legacy-planning-base.json").stdout)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["planning_run_id"])
        self.assertEqual([], result["planning_states"])
        self.assertEqual({"delivered": False, "accepted": False}, result["outcome"])
        self.assertEqual("not_attempted", result["publication"]["state"])
        rejection = result["legacy_path_rejection"]
        self.assertEqual("planning-base", rejection["selection"])
        self.assertIn("legacy planning-base methodology is quarantined", rejection["reason"])
        self.assertEqual(["start"], result["interfaces"]["operator"])
        self.assertEqual([], result["interfaces"]["write_doors"])

    def test_matt_path_cannot_create_or_consume_a_duplicated_release_contract(self):
        result = json.loads(self.invoke("legacy-release-contract.json").stdout)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["planning_run_id"])
        rejection = result["legacy_path_rejection"]
        self.assertEqual("release-contract", rejection["selection"])
        self.assertIn("agent-factory-product-release/v1", rejection["reason"])
        self.assertIn("Matt-path-forbidden", rejection["reason"])

    def test_cockpit_v1_export_of_routes_screens_or_state_model_fails_closed(self):
        result = json.loads(self.invoke("legacy-cockpit-v1-export.json").stdout)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["planning_run_id"])
        rejection = result["legacy_path_rejection"]
        self.assertEqual("cockpit-v1-export", rejection["selection"])
        self.assertIn("read-only evidence", rejection["reason"])

    def test_multi_slice_outcome_receives_one_independent_assembled_diff_review(self):
        result = json.loads(self.invoke("multi-rig.json").stdout)
        self.assertEqual({"required": True, "performed": True}, result["review"])
        self.assertIn("review-assembly", result["interfaces"]["operator"])

    def test_single_slice_outcome_receives_no_duplicate_final_review(self):
        result = json.loads(self.invoke("containment.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual({"required": False, "performed": False}, result["review"])

    def test_rejection_routes_a_spec_mismatch_to_targeted_repair(self):
        result = json.loads(self.invoke("reject-spec-mismatch.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(
            {"reason": "spec_mismatch", "routing": "targeted_repair"}, result["rejection"]
        )
        self.assertEqual({"delivered": True, "accepted": False}, result["outcome"])
        self.assertEqual("published", result["publication"]["state"])
        self.assertIsNotNone(result["publication"]["graph_digest"])
        self.assertTrue(result["integration"]["evidence"])
        self.assertEqual([], result["effects"])

    def test_rejection_routes_changed_desired_behavior_to_planning(self):
        result = json.loads(self.invoke("reject-changed-behavior.json").stdout)
        self.assertEqual(
            {"reason": "changed_behavior", "routing": "planning"}, result["rejection"]
        )

    def test_rejection_routes_active_danger_to_safe_neutralization(self):
        result = json.loads(self.invoke("reject-active-danger.json").stdout)
        self.assertEqual(
            {"reason": "active_danger", "routing": "safe_neutralization"}, result["rejection"]
        )

    def test_rejection_does_not_perform_a_default_whole_outcome_rollback(self):
        result = json.loads(self.invoke("reject-spec-mismatch.json").stdout)
        # The already-verified per-rig integration evidence and the published
        # delivery graph survive a rejection: only the Delivered/Accepted
        # boundary is affected, never a blanket rollback of prior work.
        self.assertTrue(result["integration"]["assembly_check"]["passed"])
        self.assertIsNotNone(result["publication"]["convoy_id"])

    def test_sensitive_effects_stay_blocked_regardless_of_integration_state(self):
        for scenario in ("single-rig.json", "reject-spec-mismatch.json"):
            result = json.loads(self.invoke(scenario).stdout)
            self.assertEqual([], result["effects"])
            self.assertIn("attempt-effect", result["interfaces"]["operator"])

    def test_default_planning_path_is_unaffected_by_the_legacy_fence(self):
        # Existing convoy-attached delivery (e.g. single-rig/multi-rig) must
        # keep working unchanged: the fence only engages when a request
        # explicitly selects a legacy_path.
        result = json.loads(self.invoke("single-rig.json").stdout)
        self.assertTrue(result["ok"])
        self.assertNotIn("legacy_path_rejection", result)
        self.assertIsNotNone(result["planning_run_id"])


    # --- the delivery of one ticket of a marked convoy (T19, af-iefuud) ---------

    def deliver(self, scenario, *adapters):
        return subprocess.run(
            (str(ORACLE), "run", str(FIXTURES / scenario), *(adapters or ("--delivery-driver", str(DELIVERY_DRIVER)))),
            cwd=ROOT, text=True, capture_output=True, check=False)

    def test_one_ticket_walks_the_whole_flow_and_is_closed_by_the_ticket_end_gate(self):
        proc = self.deliver("one-ticket-end-to-end.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        # Each state is observed once, in the order of the flow, on the
        # public state read after an event; none is skipped.
        self.assertEqual(DELIVERY_STATES, [state for seen in result["observations"] for state in seen])
        for alone in DELIVERY_STATES[:6]:
            self.assertIn([alone], result["observations"])
        self.assertTrue(result["closed"])
        gate = result["ticket_end"]
        self.assertEqual("ticket-end/v1", gate["version"])
        self.assertEqual([(number, name, "pass") for number, name in enumerate(GATE_CONDITIONS, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertTrue(result["evidence"]["verified"])
        for piece in ("tdd_red", "tdd_freeze", "tdd_green", "demonstration", "handoff_records", "fidelity", "merged_tests"):
            self.assertIn(piece, result["evidence"]["pieces"])
        # What the oracle reads is the public state, and nothing of the agents.
        self.assertEqual(["convoy-state show", "git merge-base", "ticket-end check", "evidence-capture verify"],
                         result["interfaces"]["read"])
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower())
        # Equal public behavior gives an equal result: no path, commit or time in it.
        self.assertEqual(proc.stdout, self.deliver("one-ticket-end-to-end.json").stdout)

    def test_the_same_walk_with_a_condition_missing_leaves_the_ticket_open_and_the_gate_names_it(self):
        proc = self.deliver("one-ticket-missing-condition.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        self.assertFalse(result["closed"])
        self.assertEqual(DELIVERY_STATES[:7], result["lifecycle"])
        self.assertEqual([1, 6], result["ticket_end"]["missing"])
        verdicts = {entry["name"]: entry["verdict"] for entry in result["ticket_end"]["conditions"]}
        self.assertEqual(("fail", "fail"), (verdicts["criteria"], verdicts["merge"]))
        self.assertEqual({"pass"}, {verdict for name, verdict in verdicts.items() if name not in ("criteria", "merge")})
        self.assertNotIn("merged_tests", result["evidence"]["pieces"])

    def test_a_ticket_closed_outside_the_ticket_end_gate_fails_the_oracle(self):
        proc = self.deliver("one-ticket-closed-by-hand.json")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("closed outside the gate", proc.stderr)

    def test_a_scenario_is_walked_only_with_the_adapters_of_its_contract(self):
        planning = ("--operator", str(OPERATOR), "--publication-door", str(OPERATOR))
        proc = self.deliver("one-ticket-end-to-end.json", *planning)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("--delivery-driver", proc.stderr)
        proc = self.deliver("single-rig.json")
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("--operator", proc.stderr)

    def test_a_delivery_scenario_that_expects_a_closed_ticket_with_a_missing_condition_is_rejected(self):
        scenario = FIXTURES / "one-ticket-end-to-end.json"
        with tempfile.TemporaryDirectory() as tmp:
            for expect in ({"closed": True, "missing": [1]}, {"closed": False}, {"closed": False, "missing": [10]}):
                broken = Path(tmp) / "scenario.json"
                broken.write_text(json.dumps({**json.loads(scenario.read_text()), "expect": expect}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, expect)
                self.assertIn("expect", proc.stderr)

if __name__ == "__main__":
    unittest.main()
