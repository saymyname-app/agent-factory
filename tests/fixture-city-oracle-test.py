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

    # --- the same walk on the second project of the fixture (T35, af-f62cxt) ------

    def test_one_ticket_of_the_second_project_walks_the_same_flow_and_is_closed_by_the_ticket_end_gate(self):
        proc = self.deliver("one-ticket-second-project.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("delivery-fixture-city-api", result["project"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        self.assertEqual(DELIVERY_STATES, [state for seen in result["observations"] for state in seen])
        self.assertTrue(result["closed"])
        gate = result["ticket_end"]
        self.assertEqual("ticket-end/v1", gate["version"])
        self.assertEqual([(number, name, "pass") for number, name in enumerate(GATE_CONDITIONS, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertTrue(result["evidence"]["verified"])
        for piece in ("tdd_red", "tdd_freeze", "tdd_green", "demonstration", "handoff_records", "merged_tests",
                      "evaluation.c1", "evaluation.demo"):
            self.assertIn(piece, result["evidence"]["pieces"])
        # Its interface is not a web page: no screen was compared to a prototype.
        self.assertNotIn("fidelity", result["evidence"]["pieces"])
        # The same flow as the first project: same states, observed at the
        # same events, and the same list of conditions with the same verdicts.
        first = json.loads(self.deliver("one-ticket-end-to-end.json").stdout)
        self.assertNotIn("project", first)
        for same in ("lifecycle", "observations", "closed", "ticket_end", "interfaces"):
            self.assertEqual(first[same], result[same], same)

    def test_a_delivery_scenario_naming_a_project_the_driver_does_not_know_fails_the_oracle(self):
        scenario = json.loads((FIXTURES / "one-ticket-second-project.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for project, named in (("projet-inconnu", "projet-inconnu"), ("../ailleurs", "project"), (3, "project")):
                broken = Path(tmp) / "scenario.json"
                broken.write_text(json.dumps({**scenario, "project": project}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, project)
                self.assertEqual("", proc.stdout)
                self.assertIn(named, proc.stderr)

    # --- a ticket out of resumes is parked, the others go on, one grouped request (T20, af-y9pw9z) ---

    def test_a_ticket_that_fails_three_times_is_parked_with_its_descendant_while_the_other_goes_on_then_one_request(self):
        proc = self.deliver("three-failures-parked.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        # The ticket that waits for no parked ticket walked the whole flow.
        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        parking = result["parking"]
        [sick] = [entry for entry in parking["parked"] if entry["origin"] == entry["id"]]
        [behind] = [entry for entry in parking["parked"] if entry["origin"] != entry["id"]]
        self.assertEqual(("resumes_exhausted", 3), (sick["cause"], sick["resumes"]))
        self.assertEqual((sick["id"], "resumes_exhausted"), (behind["origin"], behind["cause"]))
        # It went on after the parking, and was closed with the others still parked.
        self.assertIn("coded", parking["reached_after"])
        self.assertIn("closed", parking["reached_after"])
        # No request while a ticket could still advance; then exactly one, which names every parked ticket.
        self.assertEqual(0, parking["requests_before_only_parked_left"])
        self.assertEqual(1, parking["requests"])
        self.assertEqual(sorted([sick["id"], behind["id"]]), parking["named_by_the_request"])
        self.assertIn("escalation-door list", result["interfaces"]["read"])
        self.assertEqual(proc.stdout, self.deliver("three-failures-parked.json").stdout)

    def test_a_delivery_scenario_that_expects_parked_tickets_without_a_closed_one_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken.json"
            for expect in ({"closed": False, "missing": [1], "parked": 2}, {"closed": True, "parked": 0},
                           {"closed": True, "parked": "deux"}):
                broken.write_text(json.dumps({"contract": "agent-factory-fixture-delivery-scenario/v1",
                                              "scenario_id": "broken", "expect": expect}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("expect.parked", proc.stderr)

    # --- a story not observed at the end: one repair, the gate replayed, Delivered (T26, af-vwcflt) ---

    def deliver_expecting(self, scenario, **expect):
        """The walk of `scenario` with what it expects changed."""
        given = json.loads((FIXTURES / scenario).read_text())
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "scenario.json"
            changed.write_text(json.dumps({**given, "expect": {**given["expect"], **expect}}))
            return subprocess.run((str(ORACLE), "run", str(changed), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)

    def test_a_story_not_observed_at_the_end_is_repaired_by_one_ticket_and_the_convoy_is_delivered_on_the_new_tip(self):
        proc = self.deliver("story-repaired-delivered.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        # The walked ticket went through its nine states before the end of the Spec was tried.
        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        outcome = result["outcome"]
        self.assertEqual("delivered", outcome["state"])
        # The first gate refused on the Outcome Evaluation, and on nothing before it.
        refused = outcome["refused"]
        self.assertEqual(["outcome_evaluation"], [entry["name"] for entry in refused["conditions"] if entry["verdict"] == "fail"])
        self.assertEqual({"pass"}, {entry["verdict"] for entry in refused["conditions"][:3]})
        # One round, one repair, published by the flow and delivered like any ticket.
        self.assertEqual((1, None), (outcome["end_rounds"], outcome["end_stop"]))
        [repair] = outcome["repairs"]
        self.assertEqual(("repair", DELIVERY_STATES, True), (repair["kind"], repair["lifecycle"], repair["closed_by_the_gate"]))
        self.assertNotIn(repair["id"], outcome["published"])
        # The whole gate replayed on the tip the repair left: its seven conditions, there.
        gate = outcome["spec_end"]
        self.assertEqual((True, True, True), (gate["at_the_tip"], gate["holds_every_repair"], gate["delivered"]))
        self.assertEqual([(number, "pass") for number in range(1, 8)],
                         [(entry["number"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertEqual([], gate["missing"])
        self.assertTrue(outcome["delivered"]["at_the_tip"])
        # Never Delivered before the repair was closed, nor while the gate named a condition.
        self.assertEqual(1, outcome["delivered"]["repairs_closed_when_first_seen"])
        self.assertGreater(outcome["delivered"]["checked"], 0)
        # The one request of the operator's list is the Acceptance Request of the Delivered Outcome (T28).
        self.assertEqual(1, outcome["requests"])
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        for read in ("spec-end check", "escalation-door list", "git rev-parse", "evidence-pack check",
                     "acceptance-session open", "acceptance-session close"):
            self.assertIn(read, result["interfaces"]["read"])
        # Nothing of the agents: the only session named is the command of the Acceptance Session.
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower().replace("acceptance-session", ""))
        # No path, commit or time in the result.
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T")

    def test_a_delivered_outcome_with_another_number_of_repairs_than_expected_fails_the_oracle(self):
        # No story is left unobserved on the walk where nothing goes wrong: no repair is published.
        proc = self.deliver_expecting("one-ticket-end-to-end.json", outcome="delivered", repairs=1)

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("0 repair", proc.stderr)
        self.assertIn("expects 1", proc.stderr)

    def test_a_repaired_story_expected_without_a_repair_fails_the_oracle(self):
        proc = self.deliver_expecting("story-repaired-delivered.json", repairs=0)

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("1 repair", proc.stderr)
        self.assertIn("expects 0", proc.stderr)

    def test_the_walk_where_nothing_goes_wrong_is_delivered_without_a_repair_and_without_a_round(self):
        proc = self.deliver_expecting("one-ticket-end-to-end.json", outcome="delivered")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        outcome = json.loads(proc.stdout)["outcome"]

        self.assertEqual(("delivered", [], 0, None), tuple(outcome[name] for name in ("state", "repairs", "end_rounds", "end_stop")))
        self.assertNotIn("refused", outcome)
        self.assertTrue(outcome["spec_end"]["delivered"])
        # After the Delivered Outcome the operator's list shows the Acceptance Request with the link of
        # the dossier; the session opens the product at the commit of the dossier, and closing it stops it (T28).
        self.assertEqual(1, outcome["requests"])
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")
        # The scenario that asks for no outcome keeps the result it had: nothing of the end in it.
        plain = json.loads(self.deliver("one-ticket-end-to-end.json").stdout)
        self.assertNotIn("outcome", plain)
        self.assertNotIn("spec-end check", plain["interfaces"]["read"])
        self.assertNotIn("acceptance-session open", plain["interfaces"]["read"])

    def test_a_delivery_scenario_with_a_malformed_expected_outcome_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken.json"
            for expect, named in (({"closed": True, "outcome": "rejected"}, "expect.outcome"),
                                  ({"closed": False, "missing": [1], "outcome": "delivered"}, "expect.outcome"),
                                  ({"closed": True, "outcome": "delivered", "parked": 1}, "expect.outcome"),
                                  ({"closed": True, "repairs": 1}, "expect.repairs"),
                                  ({"closed": True, "outcome": "delivered", "repairs": -1}, "expect.repairs"),
                                  ({"closed": True, "outcome": "delivered", "repairs": True}, "expect.repairs")):
                broken.write_text(json.dumps({"contract": "agent-factory-fixture-delivery-scenario/v1",
                                              "scenario_id": "broken", "expect": expect}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, expect)
                self.assertIn(named, proc.stderr, expect)

    # --- after Benjamin's answer: Delivered, then Accepted or abandoned (T30, af-vlzc6v) ---

    FAULTY_DRIVER = '''#!/usr/bin/env python3
"""The reference delivery driver, going wrong in one named way."""
import json
import subprocess
import sys
from pathlib import Path

REAL, FAULT = {real!r}, {fault!r}
workspace, command, options = Path(sys.argv[2]), sys.argv[3], sys.argv[4:]


def real(*arguments):
    proc = subprocess.run((REAL, "--workspace", str(workspace), *arguments), text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def git(*arguments):
    return subprocess.run(("git", "-C", str(workspace / "city"), *arguments), text=True, capture_output=True).stdout.strip()


if command == "prepare" and FAULT == "nobody-answers":
    options = [option for option in options if option not in ("--answer", "accepted", "abandoned")]
answer = real(command, *options)
if command == "advance" and FAULT == "answers-in-the-event-of-delivered":
    # Everything up to the pass that follows the answer, as one event.
    while not answer["idle"] and not answer["event"].startswith("owner:"):
        answer = real("advance")
    answer = real("advance")
if command == "advance" and FAULT == "protected-branch-moved":
    integration = git("for-each-ref", "--format=%(objectname)", "refs/heads/integration")
    if integration and integration != git("rev-parse", "refs/heads/main"):
        git("update-ref", "refs/heads/main", integration)
print(json.dumps(answer))
'''

    def deliver_with_a_faulty_driver(self, scenario, fault):
        """The walk of `scenario` by the reference driver made to go wrong in one way."""
        with tempfile.TemporaryDirectory() as temporary:
            driver = Path(temporary) / "delivery-driver"
            driver.write_text(self.FAULTY_DRIVER.format(real=str(DELIVERY_DRIVER), fault=fault))
            driver.chmod(0o755)
            return self.deliver(scenario, "--delivery-driver", str(driver))

    def test_the_complete_scenario_is_observed_delivered_then_accepted_and_the_protected_branch_receives_one_merge(self):
        proc = self.deliver("outcome-accepted.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        outcome = result["outcome"]
        # Two states, observed one after the other on the public state.
        self.assertEqual(("accepted", ["delivered", "accepted"]), (outcome["state"], outcome["states"]))
        # While it was Delivered: the whole end-of-Spec gate at the tip, after the one repair, and the
        # Acceptance Request with its dossier; the evidence of the walked ticket was read then.
        self.assertEqual((1, None), (outcome["end_rounds"], outcome["end_stop"]))
        [repair] = outcome["repairs"]
        self.assertEqual(("repair", DELIVERY_STATES, True), (repair["kind"], repair["lifecycle"], repair["closed_by_the_gate"]))
        self.assertEqual((True, True, []), (outcome["spec_end"]["at_the_tip"], outcome["spec_end"]["delivered"],
                                            outcome["spec_end"]["missing"]))
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        self.assertTrue(result["evidence"]["verified"])
        # Before « accepté » was recorded the protected branch held no commit of the convoy; after it,
        # one merge: its first parent is the tip it had, its second the tip of the integration branch.
        self.assertEqual({"moved_before_the_answer": False, "convoy_commits_before_the_answer": 0, "merges": 1,
                          "first_parent_is_the_previous_tip": True, "second_parent_is_the_integration_tip": True},
                         outcome["protected_branch"])
        self.assertEqual({"kept": True, "at_the_judged_commit": True}, outcome["integration_branch"])
        # The convoy is closed on the words of its approver, and nothing is left on the operator's list.
        closed = outcome["closed"]
        self.assertEqual(("accepted", "benjamin"), (closed["how"], closed["approver"]))
        self.assertTrue(closed["said"].strip())
        self.assertEqual((1, 0), (outcome["requests"], outcome["requests_once_closed"]))
        self.assertIn("git rev-list", result["interfaces"]["read"])
        self.assertEqual(["prepare", "publish", "advance", "stop"], result["interfaces"]["driver"])
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower().replace("acceptance-session", ""))
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")

    def test_an_abandoned_convoy_is_closed_with_its_reason_and_the_protected_branch_does_not_move(self):
        proc = self.deliver("outcome-abandoned.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        outcome = json.loads(proc.stdout)["outcome"]

        self.assertEqual(("abandoned", ["delivered", "abandoned"]), (outcome["state"], outcome["states"]))
        closed = outcome["closed"]
        self.assertEqual(("abandoned", "benjamin"), (closed["how"], closed["approver"]))
        self.assertTrue(closed["said"].strip())
        # Nothing is merged, and the integration branch stays where the Outcome was Delivered.
        self.assertEqual({"moved_before_the_answer": False, "convoy_commits_before_the_answer": 0, "merges": 0,
                          "unchanged": True}, outcome["protected_branch"])
        self.assertEqual({"kept": True, "at_the_judged_commit": True}, outcome["integration_branch"])
        self.assertEqual(0, outcome["requests_once_closed"])
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")

    def test_a_convoy_closed_accepted_without_having_been_observed_delivered_first_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-accepted.json", "answers-in-the-event-of-delivered")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("without having been observed Delivered first", proc.stderr)

    def test_a_protected_branch_that_moves_before_the_answer_is_recorded_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-accepted.json", "protected-branch-moved")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("the protected branch moved before « accepté » was recorded", proc.stderr)
        self.assertIn("commit(s) of the convoy", proc.stderr)

    def test_an_expected_answer_that_nobody_gives_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-abandoned.json", "nobody-answers")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("observed delivered", proc.stderr)
        self.assertIn("expects delivered, then abandoned", proc.stderr)

    def test_the_answer_of_the_owner_is_one_the_driver_plays_only_when_asked(self):
        proc = subprocess.run((str(DELIVERY_DRIVER), "--workspace", "/nonexistent", "prepare", "--help"),
                              text=True, capture_output=True, check=False)
        self.assertIn("--answer {none,accepted,abandoned}", proc.stdout)

    def test_the_injection_of_a_story_not_observed_is_one_the_oracle_and_its_driver_both_know(self):
        proc = subprocess.run((str(DELIVERY_DRIVER), "--workspace", "/nonexistent", "prepare", "--help"),
                              text=True, capture_output=True, check=False)
        self.assertIn("story-not-observed", proc.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken.json"
            broken.write_text(json.dumps({"contract": "agent-factory-fixture-delivery-scenario/v1", "scenario_id": "broken",
                                          "inject": {"delivery": "inconnue"}, "expect": {"closed": True}}))
            proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(1, proc.returncode)
            self.assertIn("story-not-observed", proc.stderr)
            # The second project already serves the story the injection leaves unserved: the driver refuses it.
            given = json.loads((FIXTURES / "story-repaired-delivered.json").read_text())
            broken.write_text(json.dumps({**given, "project": "delivery-fixture-city-api"}))
            proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("delivery-fixture-city only", proc.stderr)

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
