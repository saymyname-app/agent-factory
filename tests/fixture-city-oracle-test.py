#!/usr/bin/env python3
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
planning run of the reference protocol, then the delivery of the tickets of
a marked convoy, walked through the whole delivery flow by the reference
delivery driver.

The cases are in two files of about the same duration (Spec CI01,
af-q9urgr: this file was the longest of the battery, and alone set the
duration of a CI run): this one holds the harness (FixtureCityOracleHarness:
the launches of the oracle and the drivers made to go wrong) and the cases
of the planning run, of the delivery of one ticket on each project (T19,
T35) and of the story repaired then Delivered (T26);
tests/fixture-city-oracle-parked-answer-author-gates-test.py loads the
harness from here and holds the others."""

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
# The gates of the author's step, as the oracle names the commands it saw run (T37).
AUTHOR_GATES = ["tdd-step freeze", "tdd-step green", "tdd-step red", "test-review review",
                "ticket-author demonstrate", "ticket-author start", "ticket-exit exit"]


class FixtureCityOracleHarness(unittest.TestCase):
    """The launches of the oracle, for the cases of the two files: no case here."""

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

    # --- the delivery of one ticket of a marked convoy (T19, af-iefuud) ---------

    def deliver(self, scenario, *adapters):
        return subprocess.run(
            (str(ORACLE), "run", str(FIXTURES / scenario), *(adapters or ("--delivery-driver", str(DELIVERY_DRIVER)))),
            cwd=ROOT, text=True, capture_output=True, check=False)

    def assert_walked_through_the_gates_of_the_author(self, result, tickets):
        """T37: the commands of the flow the oracle saw run during the walk
        name each gate of the author's step, and each closed ticket had its
        red, frozen, reviewed and finished states written by its gate."""
        for gate in AUTHOR_GATES:
            self.assertIn(gate, result["interfaces"]["flow"])
        self.assertEqual(sorted(result["interfaces"]["flow"]), result["interfaces"]["flow"])
        for direct in ("set-tdd", "record-test-review", "set-exit", "set-handoff"):
            self.assertNotIn(f"convoy-state {direct}", result["interfaces"]["flow"])
        self.assertEqual({"tickets": tickets, "commands": AUTHOR_GATES}, result["author_gates"])

    # --- the walk of a scenario with what it expects changed (T26, af-vwcflt) ---

    def deliver_expecting(self, scenario, **expect):
        """The walk of `scenario` with what it expects changed."""
        given = json.loads((FIXTURES / scenario).read_text())
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "scenario.json"
            changed.write_text(json.dumps({**given, "expect": {**given["expect"], **expect}}))
            return subprocess.run((str(ORACLE), "run", str(changed), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)

    # --- the reference driver made to go wrong in one way (T30, af-vlzc6v) ---

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

    # --- a gate of the author's step replaced by a direct write (T37, af-fg8lhx) ---

    DIRECT_WRITER_DRIVER = '''#!/usr/bin/env python3
"""The reference delivery driver, with one gate of the author's step replaced
by a direct write of its state through bin/convoy-state."""
import os
import subprocess
import sys
from pathlib import Path

REAL, FAULT, GATE = {real!r}, {fault!r}, {gate!r}
workspace = Path(sys.argv[2])
flow, doctored = Path(os.environ["FIXTURE_CITY_FLOW_BIN"]), workspace / "doctored-bin"
if not doctored.is_dir():
    doctored.mkdir()
    for tool in flow.iterdir():
        (doctored / tool.name).symlink_to(tool)
    (doctored / GATE).rename(doctored / (GATE + ".real"))
    (doctored / GATE).write_text({writer!r})
    (doctored / GATE).chmod(0o755)
raise SystemExit(subprocess.run((REAL, *sys.argv[1:]), env={{**os.environ, "FIXTURE_CITY_FLOW_BIN": str(doctored)}}).returncode)
'''

    DIRECT_WRITER = '''#!/usr/bin/env python3
"""A gate of the author's step that writes its state itself."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FAULT, STATE = {fault!r}, {state!r}
name, arguments = Path(sys.argv[0]).name, sys.argv[1:]
step = "tdd-step " + arguments[0] if name == "tdd-step" else name
if step != {{"red": "tdd-step red", "freeze": "tdd-step freeze", "review": "test-review", "exit": "ticket-exit"}}[FAULT]:
    real = sys.argv[0] + ".real"
    os.execv(real, [real, *arguments])
convoy, ticket = arguments[1:3]


def option(flag):
    return arguments[arguments.index(flag) + 1]


def write(command, *more, **record):
    with tempfile.TemporaryDirectory() as holder:
        if record:
            Path(holder, "record.json").write_text(json.dumps(record))
            more = (*more, "--file", str(Path(holder, "record.json")))
        subprocess.run((STATE, command, convoy, ticket, *more), check=True, stdout=subprocess.DEVNULL)


head = subprocess.run(("git", "-C", option("--repo"), "rev-parse", "HEAD"), text=True, capture_output=True).stdout.strip()
files, test = {{"tests/test_critere.py": "sha256:" + "ab" * 32}}, "tests/test_critere.py::Critere::test_observable"
if FAULT == "red":
    write("set-tdd", "--step", "red", "--commit", head, "--base", option("--base"))
elif FAULT == "freeze":
    write("set-tdd", "--step", "freeze", "--commit", head)
elif FAULT == "review":
    write("open-test-review", "--commit", head, files=files, criteria={{"1": [test]}})
    write("record-test-review", commit=head, files=files, tests={{test: {{"state": "favorable"}}}}, recorded_by="relecteur-" + ticket)
else:
    write("set-exit", "--exit", "finished")
print(json.dumps({{"ok": True}}))
'''

    def deliver_with_a_direct_writer(self, scenario, fault):
        """The walk of `scenario` by the reference driver, where the state
        `fault` names is written by bin/convoy-state and not by its gate."""
        gate = {"red": "tdd-step", "freeze": "tdd-step", "review": "test-review", "exit": "ticket-exit"}[fault]
        with tempfile.TemporaryDirectory() as temporary:
            driver = Path(temporary) / "delivery-driver"
            driver.write_text(self.DIRECT_WRITER_DRIVER.format(
                real=str(DELIVERY_DRIVER), fault=fault, gate=gate,
                writer=self.DIRECT_WRITER.format(fault=fault, state=str(ROOT / "bin" / "convoy-state"))))
            driver.chmod(0o755)
            return self.deliver(scenario, "--delivery-driver", str(driver))


class FixtureCityOracleTest(FixtureCityOracleHarness):
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

    def test_one_ticket_walks_the_whole_flow_and_is_closed_by_the_ticket_end_gate(self):
        proc = self.deliver("one-ticket-end-to-end.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=1)

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
        self.assert_walked_through_the_gates_of_the_author(result, tickets=1)

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

    # --- a story not observed at the end: one repair, the gate replayed, Delivered (T26, af-vwcflt) ---

    def test_a_story_not_observed_at_the_end_is_repaired_by_one_ticket_and_the_convoy_is_delivered_on_the_new_tip(self):
        proc = self.deliver("story-repaired-delivered.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=2)

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


if __name__ == "__main__":
    unittest.main()
