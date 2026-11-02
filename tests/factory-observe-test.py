#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "factory-observe"
POLICY = ROOT / "config" / "factory-observe-policy.json"

sys.path.insert(0, str(ROOT / "lib"))
import factory_observe as fo  # noqa: E402
import factory_measures as fm  # noqa: E402


class ToolMixin:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="factory-observe-test-"))
        cleanup = lambda: subprocess.run(["rm", "-rf", str(self.tmp)])  # noqa: E731
        if hasattr(self, "addCleanup"):
            self.addCleanup(cleanup)
        else:
            self._cleanup = cleanup
        self.state_file = self.tmp / "state.json"

    def env(self, extra=None):
        base = {
            **os.environ,
            "FACTORY_OBSERVE_STATE_FILE": str(self.state_file),
            "FACTORY_OBSERVE_POLICY_FILE": str(POLICY),
        }
        base.update(extra or {})
        return base

    def write_json(self, name, payload):
        path = self.tmp / name
        path.write_text(json.dumps(payload))
        return path

    def run_tool(self, *args, env=None, check=False):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), text=True, capture_output=True, check=check,
            env=self.env(env),
        )


# --- AC1: repeated observation of unchanged state makes zero wakes ----------


class ZeroIdleCallTest(unittest.TestCase):
    def test_diff_of_identical_snapshots_is_empty(self):
        snap = {"delivery": {"af-x": {"status": "in_progress"}}}
        self.assertEqual(fo.diff_snapshot(snap, snap), [])
        self.assertEqual(fo.diff_snapshot(snap, dict(snap)), [])

    def test_observe_called_twice_with_unchanged_input_wakes_zero_both_times(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        evidence = {}

        first = fo.observe(state, policy, areas, evidence, "2026-01-01T00:00:00Z")
        # First call against an empty prior snapshot IS a new fact -- it must wake.
        self.assertEqual(first["action"], "wake")
        self.assertEqual(len(first["wakes"]), 1)

        second = fo.observe(state, policy, areas, evidence, "2026-01-01T00:05:00Z")
        third = fo.observe(state, policy, areas, evidence, "2026-01-01T00:10:00Z")
        for result in (second, third):
            self.assertEqual(result["action"], "none")
            self.assertEqual(result["wakes"], [])
            self.assertEqual(result["exemption_transitions"], [])

    def test_cli_observe_twice_with_identical_snapshot_wakes_zero_the_second_time(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {"areas": {"delivery": {"af-x": {"status": "open"}}}})
            first = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(first["action"], "wake")
            second = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(second["action"], "none")
            self.assertEqual(second["wakes"], [])


class ToolCase(ToolMixin):
    """Reusable outside unittest.TestCase via context-manager protocol."""

    def __enter__(self):
        self.setUp()
        return self

    def __exit__(self, *exc):
        getattr(self, "_cleanup", lambda: None)()


# --- AC2: a new actionable fact wakes the smallest qualified role once, with evidence -----


class WakeQualificationTest(unittest.TestCase, ToolMixin):
    def setUp(self):
        ToolMixin.setUp(self)

    def test_new_delivery_fact_wakes_the_smaller_delivery_worker_role_not_the_mayor(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        result = fo.observe(state, policy, areas, {}, "2026-01-01T00:00:00Z")
        self.assertEqual(result["action"], "wake")
        wake = result["wakes"][0]
        self.assertEqual(wake["role"], "delivery-worker")  # rank 1, not mayor (rank 2)
        self.assertEqual(wake["evidence"]["after"], {"status": "in_progress"})
        self.assertIsNone(wake["evidence"]["before"])

    def test_planning_run_fact_has_no_dedicated_worker_and_wakes_mayor(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"planning_runs": {"run-1": {"status": "open"}}}
        result = fo.observe(state, policy, areas, {}, "t")
        self.assertEqual(result["wakes"][0]["role"], "mayor")

    def test_unqualified_area_wakes_with_role_none_not_a_silent_fallback(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": []}
        facts = fo.diff_snapshot({}, {"unmapped_area": {"x": {"a": 1}}})
        wakes = fo.plan_wakes(facts, policy)
        self.assertIsNone(wakes[0]["role"])

    def test_a_second_identical_fact_does_not_wake_again(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        fo.observe(state, policy, areas, {}, "t1")
        repeat = fo.observe(state, policy, areas, {}, "t2")
        self.assertEqual(repeat["wakes"], [])

    def test_evidence_pointer_is_preserved_verbatim_across_state_persistence(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {
                "areas": {"delivery": {"af-x": {"status": "open", "detail": "spec drift"}}}
            })
            result = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(
                result["wakes"][0]["evidence"]["after"],
                {"status": "open", "detail": "spec drift"},
            )


class LiveToolCase(ToolCase):
    """Public-CLI fixture with the minimal shapes of the R2/A2 live incident."""

    def setUp(self):
        super().setUp()
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        self.calls = self.tmp / "calls.jsonl"
        self.mail_state = self.tmp / "mail-state.json"
        self.mail_rc = self.tmp / "mail-rc"
        self.mail_rc.write_text("0")
        self.active = self.tmp / "active.json"
        self.requests = self.tmp / "requests.json"
        self.prs = self.tmp / "prs.json"
        self.sessions = self.tmp / "sessions.json"
        self.git_head = self.tmp / "git-head"
        self.git_main = self.tmp / "git-main"
        self.git_head.write_text("1" * 40)
        self.git_main.write_text("1" * 40)
        self.prs.write_text(json.dumps([{
            "number": 765,
            "state": "MERGED",
            "isDraft": False,
            "mergeStateStatus": "CLEAN",
            "headRefName": "do-work/af-npz9v1.48",
            "headRefOid": "d1505a17434e98d438332c45333876af16074ef9",
            "baseRefName": "main",
            "statusCheckRollup": [{"name": "Tests", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            "closedAt": "2026-10-29T14:19:00Z",
            "mergedAt": "2026-10-29T14:19:00Z",
        }]))
        self.sessions.write_text(json.dumps({
            "sessions": [{"name": "factory-worker-af-fixture", "state": "active"}],
        }))
        self.write_incident(resumed=False, request_active=True)
        self._write_fakes()

    def write_incident(self, *, resumed, request_active):
        resumes = [{
            "cause": "unblocked",
            "ref": "repair:af-npz9v1.48",
            "at": "2026-10-29T14:20:00Z",
        }] if resumed else []
        technical = {
            "id": "af-cifk1e",
            "status": "in_progress",
            "issue_type": "task",
            "metadata": {
                "gc.session_name": "factory-worker-af-fixture",
                "gc.flow.exit": json.dumps({"exit": "operator_request", "at": "2026-10-29T14:00:00Z"}),
                "gc.flow.park": json.dumps({"cause": "operator_request", "at": "2026-10-29T14:00:01Z"}),
                "gc.flow.technical_repairs": json.dumps({
                    "exit_at": "2026-10-29T14:00:00Z",
                    "entries": [{"id": "af-npz9v1.48", "at": "2026-10-29T14:01:00Z"}],
                }),
                "gc.flow.resume": json.dumps({"entries": resumes}),
            },
        }
        human = {
            "id": "af-ocz64w",
            "status": "blocked",
            "issue_type": "task",
            "metadata": {
                "gc.plane": "planning",
                "gc.needs_benjamin": (
                    "A2 doit rendre Essai et Avis utilisables jusqu'à A2"
                    if request_active else "none"
                ),
                **({} if request_active else {
                    "gc.escalation_quoi": "A2 doit rendre Essai et Avis utilisables jusqu'à A2",
                    "gc.escalation_response_option": "a",
                    "gc.escalation_response_actor": "Benjamin",
                    "gc.escalation_response_at": "2026-10-29T16:00:00Z",
                }),
            },
        }
        self.active.write_text(json.dumps([technical, human]))
        self.requests.write_text(json.dumps([human]))

    def _write_fakes(self):
        gc = self.bin_dir / "gc"
        gc.write_text(f"""#!/usr/bin/env python3
import json, pathlib, sys
args = sys.argv[1:]
with pathlib.Path({str(self.calls)!r}).open('a') as handle:
    handle.write(json.dumps(args) + '\\n')
if args[:2] == ['bd', 'list']:
    source = {str(self.requests)!r} if 'gc.needs_benjamin' in args else {str(self.active)!r}
    print(pathlib.Path(source).read_text())
elif args[:2] == ['session', 'list']:
    print(pathlib.Path({str(self.sessions)!r}).read_text())
elif args[:2] == ['mail', 'send']:
    pathlib.Path({str(self.mail_state)!r}).write_text(pathlib.Path({str(self.state_file)!r}).read_text())
    active = {{
        session['name']
        for session in json.loads(pathlib.Path({str(self.sessions)!r}).read_text())['sessions']
        if session.get('state') == 'active'
    }}
    if args[2] != 'mayor' and args[2] not in active:
        raise SystemExit(1)
    raise SystemExit(int(pathlib.Path({str(self.mail_rc)!r}).read_text()))
else:
    raise SystemExit(2)
""")
        gh = self.bin_dir / "gh"
        gh.write_text(f"""#!/usr/bin/env python3
import pathlib, sys
if sys.argv[1:3] != ['pr', 'list']:
    raise SystemExit(2)
print(pathlib.Path({str(self.prs)!r}).read_text())
""")
        git = self.bin_dir / "git"
        git.write_text(f"""#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
if args[-3:] == ['config', '--get', 'remote.origin.url']:
    print('git@github.com:acme/factory.git')
elif args[-2:] == ['rev-parse', 'HEAD']:
    print(pathlib.Path({str(self.git_head)!r}).read_text())
elif args[-2:] == ['rev-parse', 'refs/remotes/origin/main']:
    print(pathlib.Path({str(self.git_main)!r}).read_text())
elif args[-3:] == ['rev-parse', '--abbrev-ref', 'HEAD']:
    print('main')
else:
    raise SystemExit(2)
""")
        for executable in (gc, gh, git):
            executable.chmod(0o755)

    def live_env(self, now):
        return {
            "FACTORY_ROOT": str(self.tmp),
            "FACTORY_OBSERVE_NOW": str(now),
            "FACTORY_OBSERVE_REPO": "acme/factory",
            "FACTORY_OBSERVE_GC_BIN": str(self.bin_dir / "gc"),
            "FACTORY_OBSERVE_GH_BIN": str(self.bin_dir / "gh"),
            "FACTORY_OBSERVE_GIT_BIN": str(self.bin_dir / "git"),
        }

    def run_live(self, now, check=True):
        return self.run_tool("live", env=self.live_env(now), check=check)

    def calls_matching(self, prefix):
        if not self.calls.exists():
            return []
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return [call for call in calls if call[:len(prefix)] == prefix]


class LiveObservationTest(unittest.TestCase):
    def test_identical_live_reads_create_a_baseline_then_wake_nobody(self):
        with LiveToolCase() as case:
            first = json.loads(case.run_live(1000).stdout)
            second = json.loads(case.run_live(1300).stdout)
            self.assertEqual((first["action"], second["action"]), ("none", "none"))
            self.assertEqual([], case.calls_matching(["mail", "send"]))
            status = json.loads(case.run_tool("status", "--json", env=case.live_env(1300), check=True).stdout)
            self.assertEqual(
                {"delivery", "planning_runs", "human_requests"},
                set(status["live"]["areas_observed"]),
            )
            self.assertEqual("1970-01-01T02:16:40Z", status["live"]["window"]["due_at"])

    def test_a_new_unblocked_resume_routes_once_to_the_holding_worker(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            case.write_incident(resumed=True, request_active=True)
            changed = json.loads(case.run_live(1300).stdout)
            repeat = json.loads(case.run_live(1600).stdout)
            self.assertEqual("wake", changed["action"])
            self.assertEqual("none", repeat["action"])
            resume = next(event for event in changed["events"] if event["id"] == "af-cifk1e")
            stored_ref = resume["evidence"]["after"]["signals"]["gc.flow.resume"]["entries"][0]["ref"]
            self.assertEqual({"fingerprint"}, set(stored_ref))
            self.assertNotIn("repair:af-npz9v1.48", json.dumps(resume))
            mails = case.calls_matching(["mail", "send"])
            self.assertEqual(1, len(mails))
            self.assertEqual("factory-worker-af-fixture", mails[0][2])

    def test_a_transition_is_durable_before_its_deduplicated_alert(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            case.write_incident(resumed=True, request_active=True)
            changed = json.loads(case.run_live(1300).stdout)

            event_id = changed["events"][0]["event_id"]
            state_at_send = json.loads(case.mail_state.read_text())
            live = state_at_send["live"]
            self.assertIn(event_id, [event["event_id"] for event in live["events"]])
            route = next(route for route in live["pending"] if event_id in route["event_ids"])
            mail = case.calls_matching(["mail", "send"])[0]
            self.assertEqual(route["route_id"], mail[mail.index("--dedup") + 1])

    def test_answering_a2_is_preserved_and_wakes_the_mayor_once(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            case.write_incident(resumed=False, request_active=False)
            changed = json.loads(case.run_live(1300).stdout)
            self.assertEqual("wake", changed["action"])
            mails = case.calls_matching(["mail", "send"])
            self.assertEqual(1, len(mails))
            self.assertEqual("mayor", mails[0][2])
            status = json.loads(case.run_tool("status", "--json", env=case.live_env(1300), check=True).stdout)
            request_events = [
                event for event in status["live"]["events"]
                if event.get("area") == "human_requests" and event.get("id") == "af-ocz64w"
            ]
            self.assertEqual(1, len(request_events))
            self.assertTrue(request_events[0]["evidence"]["before"]["active"])
            self.assertFalse(request_events[0]["evidence"]["after"]["active"])
            self.assertEqual("a", request_events[0]["evidence"]["after"]["response"]["option"])

    def test_the_two_hour_final_read_wakes_the_mayor_once(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            final = json.loads(case.run_live(8201).stdout)
            repeat = json.loads(case.run_live(8202).stdout)
            self.assertEqual("wake", final["action"])
            self.assertEqual("1970-01-01T02:16:41Z", final["window"]["final_at"])
            self.assertEqual("none", repeat["action"])
            mails = case.calls_matching(["mail", "send"])
            self.assertEqual(1, len(mails))
            self.assertEqual("mayor", mails[0][2])

    def test_a_failed_route_is_retried_without_rediscovering_the_transition(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            case.write_incident(resumed=True, request_active=True)
            case.mail_rc.write_text("1")
            failed = json.loads(case.run_live(1300, check=False).stdout)
            self.assertFalse(failed["ok"])
            case.mail_rc.write_text("0")
            retried = json.loads(case.run_live(1600).stdout)
            quiet = json.loads(case.run_live(1900).stdout)
            self.assertEqual((retried["action"], quiet["action"]), ("none", "none"))
            self.assertEqual(2, len(case.calls_matching(["mail", "send"])))

    def test_a_failed_route_falls_back_to_mayor_when_its_worker_disappears(self):
        with LiveToolCase() as case:
            case.run_live(1000)
            case.write_incident(resumed=True, request_active=True)
            case.mail_rc.write_text("1")
            failed = json.loads(case.run_live(1300, check=False).stdout)
            self.assertFalse(failed["ok"])

            case.sessions.write_text(json.dumps({"sessions": []}))
            case.mail_rc.write_text("0")
            reassignment = case.run_live(1600, check=False)
            reassigned = json.loads(reassignment.stdout)
            quiet = json.loads(case.run_live(1900).stdout)

            self.assertEqual(0, reassignment.returncode)
            self.assertTrue(reassigned["ok"])
            self.assertEqual([], reassigned["route_failures"])
            self.assertEqual((reassigned["action"], quiet["action"]), ("wake", "none"))
            mails = case.calls_matching(["mail", "send"])
            self.assertEqual(2, len(mails))
            self.assertEqual("mayor", mails[1][2])
            status = json.loads(case.run_tool(
                "status", "--json", env=case.live_env(1900), check=True,
            ).stdout)
            route = status["live"]["routes"][0]
            self.assertEqual("mayor", route["recipient"])
            self.assertEqual(len(route["event_ids"]), len(set(route["event_ids"])))
            self.assertEqual(1, route["event_ids"].count(failed["events"][0]["event_id"]))


# --- AC3: measures separate by comparable work class ------------------------


class MeasuresTest(unittest.TestCase, ToolMixin):
    def setUp(self):
        ToolMixin.setUp(self)

    def measures_doc(self):
        return {
            "contract": fm.MEASURES_CONTRACT,
            "work_classes": {
                "simple": {
                    "lost_decisions": 0, "escaped_defects": 1, "human_rework": 2,
                    "maintainability": 0.9, "elapsed_seconds": 120, "tokens": 4000,
                },
                "wayfinding": {
                    "lost_decisions": 3, "escaped_defects": 0, "human_rework": 5,
                    "maintainability": 0.4, "elapsed_seconds": 900, "tokens": 40000,
                },
            },
        }

    def test_validate_accepts_a_complete_document(self):
        fm.validate_measures(self.measures_doc())  # no raise

    def test_validate_rejects_a_missing_key(self):
        doc = self.measures_doc()
        del doc["work_classes"]["simple"]["tokens"]
        with self.assertRaises(fm.MeasuresError):
            fm.validate_measures(doc)

    def test_two_work_classes_keep_distinct_values_no_cross_contamination(self):
        by_class = fm.aggregate_by_class(self.measures_doc())
        self.assertEqual(by_class["simple"]["escaped_defects"], 1)
        self.assertEqual(by_class["wayfinding"]["escaped_defects"], 0)
        self.assertNotEqual(by_class["simple"], by_class["wayfinding"])
        # mutating one class's returned dict must not touch the other
        by_class["simple"]["tokens"] = 999999
        self.assertEqual(by_class["wayfinding"]["tokens"], 40000)

    def test_compare_classes_reports_a_per_metric_delta_not_a_blended_total(self):
        delta = fm.compare_classes(self.measures_doc(), "wayfinding", "simple")
        self.assertEqual(delta["lost_decisions"], 3)
        self.assertEqual(delta["human_rework"], 3)

    def test_cli_measures_validate_and_show(self):
        measures = self.write_json("measures.json", self.measures_doc())
        ok = json.loads(self.run_tool("measures-validate", "--measures", measures, check=True).stdout)
        self.assertTrue(ok["ok"])
        shown = json.loads(self.run_tool("measures-show", "--measures", measures, check=True).stdout)
        self.assertEqual(set(shown["work_classes"]), {"simple", "wayfinding"})


# --- AC4: adaptation register entry exists and matches the field contract ---


class AdaptationRegisterTest(unittest.TestCase):
    def test_register_has_an_entry_for_this_adaptation(self):
        text = (ROOT / "docs" / "ADAPTATION_REGISTER.md").read_text(encoding="utf-8")
        self.assertIn("AR-004", text)
        for field in (
            "Statut", "Baseline", "But", "Adaptation sélectionnée",
            "Alternative maintenue viable", "Preuves", "Coût observé",
            "Réversibilité bornée", "Point de revue",
            "Règle conserver / remplacer / supprimer",
        ):
            self.assertIn(field, text)


# --- AC5: exemption/handoff activates only on evidence, restores on regression --


class ExemptionTest(unittest.TestCase):
    def entry(self):
        return {"name": "auto-x", "requires": ["signal_a", "signal_b"]}

    def test_no_activation_without_evidence(self):
        result = fo.evaluate_exemption(self.entry(), {})
        self.assertFalse(result["active"])
        self.assertEqual(sorted(result["missing"]), ["signal_a", "signal_b"])

    def test_no_activation_with_partial_evidence(self):
        result = fo.evaluate_exemption(self.entry(), {"signal_a": True})
        self.assertFalse(result["active"])
        self.assertEqual(result["missing"], ["signal_b"])

    def test_activates_when_all_required_evidence_holds(self):
        result = fo.evaluate_exemption(self.entry(), {"signal_a": True, "signal_b": True})
        self.assertTrue(result["active"])
        self.assertEqual(result["missing"], [])

    def test_apply_exemptions_records_one_activation_transition_then_none(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": [self.entry()]}
        state = fo.empty_state()
        evidence = {"auto-x": {"signal_a": True, "signal_b": True}}

        first = fo.apply_exemptions(state, policy, evidence, "t1")
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["event"], "activated")
        self.assertTrue(state["exemptions"]["auto-x"])

        second = fo.apply_exemptions(state, policy, evidence, "t2")
        self.assertEqual(second, [])  # still active, no repeated transition

    def test_apply_exemptions_restores_the_instant_evidence_regresses(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": [self.entry()]}
        state = fo.empty_state()
        fo.apply_exemptions(state, policy, {"auto-x": {"signal_a": True, "signal_b": True}}, "t1")
        self.assertTrue(state["exemptions"]["auto-x"])

        regressed = fo.apply_exemptions(state, policy, {"auto-x": {"signal_a": True, "signal_b": False}}, "t2")
        self.assertEqual(len(regressed), 1)
        self.assertEqual(regressed[0]["event"], "restored")
        self.assertFalse(state["exemptions"]["auto-x"])

    def test_cli_end_to_end_activation_and_restore_via_observe(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {"areas": {}})
            active_evidence = case.write_json("evidence-on.json", {
                "tactical-resolve-auto-handoff": {
                    "decision_kind_tactical": True, "patch_not_required": True,
                },
            })
            result = json.loads(
                case.run_tool("observe", "--snapshot", snapshot, "--evidence", active_evidence, check=True).stdout
            )
            self.assertTrue(result["exemptions"]["tactical-resolve-auto-handoff"])
            self.assertEqual(result["exemption_transitions"][0]["event"], "activated")

            regressed_evidence = case.write_json("evidence-off.json", {
                "tactical-resolve-auto-handoff": {
                    "decision_kind_tactical": True, "patch_not_required": False,
                },
            })
            result2 = json.loads(
                case.run_tool(
                    "observe", "--snapshot", snapshot, "--evidence", regressed_evidence, check=True
                ).stdout
            )
            self.assertFalse(result2["exemptions"]["tactical-resolve-auto-handoff"])
            self.assertEqual(result2["exemption_transitions"][0]["event"], "restored")


# --- policy validation guards ------------------------------------------------


class PolicyValidationTest(unittest.TestCase):
    def test_default_policy_file_is_valid(self):
        fo.validate_policy(json.loads(POLICY.read_text()))  # no raise

    def test_rejects_forbidden_model_token(self):
        bad = json.loads(POLICY.read_text())
        bad["roles"][0]["model"] = "astra-1"
        with self.assertRaises(fo.ObservePolicyError):
            fo.validate_policy(bad)

    def test_rejects_effort_above_medium(self):
        bad = json.loads(POLICY.read_text())
        bad["roles"][0]["effort"] = "high"
        with self.assertRaises(fo.ObservePolicyError):
            fo.validate_policy(bad)

    def test_cli_policy_validate(self):
        proc = subprocess.run(
            [str(TOOL), "policy-validate"], text=True, capture_output=True, check=True,
            env={**os.environ, "FACTORY_OBSERVE_POLICY_FILE": str(POLICY)},
        )
        self.assertTrue(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
