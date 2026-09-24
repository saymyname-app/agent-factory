#!/usr/bin/env python3

import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "wayfinding-run"
FIXTURES = ROOT / "tests" / "fixtures" / "wayfinding-run"


class WayfindingRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wayfinding-run-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_tool(self, *args, check=False):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), text=True, capture_output=True, check=check
        )

    def promote(self, request=FIXTURES / "request.json", out=None, check=True):
        out = out or (self.tmp / "map.json")
        proc = self.run_tool("promote", request, "--out", out, check=check)
        return out, proc

    def load(self, map_path):
        return json.loads(map_path.read_text())

    # --- AC1: plane=planning metadata, never delivery-routable -------------

    def test_promote_creates_plane_planning_never_delivery_routable(self):
        map_path, proc = self.promote()
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])

        state = self.load(map_path)
        self.assertEqual("planning", state["plane"])
        self.assertFalse(state["delivery_routable"])
        for decision in state["decisions"].values():
            self.assertEqual("planning", decision["plane"])
            self.assertFalse(decision["delivery_routable"])

        route = json.loads(self.run_tool("route-check", map_path, check=True).stdout)
        self.assertFalse(route["any_delivery_routable"])
        for eligible in route["delivery_routable"].values():
            self.assertFalse(eligible)

    def test_promote_rejects_work_that_fits_one_session(self):
        proc = self.run_tool(
            "promote", FIXTURES / "invalid-single-session-request.json", "--out", self.tmp / "map.json"
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("exceeds_one_session", error["error"])
        self.assertFalse((self.tmp / "map.json").exists())

    # --- AC2: one disposable session claims, resolves, records evidence ----

    def test_claim_resolve_records_evidence_updates_map_and_closes(self):
        map_path, _ = self.promote()

        claim = json.loads(
            self.run_tool(
                "claim", map_path, "--decision", "staffing-model", "--claimant", "session-a", "--session", "s-a",
                check=True,
            ).stdout
        )
        self.assertTrue(claim["ok"])

        resolve = json.loads(
            self.run_tool(
                "resolve", map_path, "--decision", "staffing-model", "--session", "s-a",
                "--resolution", "embedded staffing", "--evidence", "af-example-evidence",
                check=True,
            ).stdout
        )
        self.assertTrue(resolve["ok"])
        self.assertFalse(resolve["to_spec_ready"])  # rig-topology still open

        state = self.load(map_path)
        decision = state["decisions"]["staffing-model"]
        self.assertEqual("resolved", decision["status"])
        self.assertEqual("embedded staffing", decision["resolution"])
        self.assertEqual("af-example-evidence", decision["evidence"])

        # A second, unrelated session cannot resolve the same decision again.
        second = self.run_tool(
            "resolve", map_path, "--decision", "staffing-model", "--session", "s-b",
            "--resolution", "x", "--evidence", "y",
        )
        self.assertNotEqual(0, second.returncode)

    def test_resolve_rejects_session_that_did_not_claim(self):
        map_path, _ = self.promote()
        self.run_tool(
            "claim", map_path, "--decision", "staffing-model", "--claimant", "session-a", "--session", "s-a",
            check=True,
        )
        proc = self.run_tool(
            "resolve", map_path, "--decision", "staffing-model", "--session", "wrong-session",
            "--resolution", "x", "--evidence", "y",
        )
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertIn("did not claim", error["error"])

    # --- AC3: independent children progress concurrently -------------------

    def test_independent_decisions_progress_concurrently(self):
        map_path, _ = self.promote()

        results = {}

        def claim_and_resolve(decision_id, session_id):
            claim = self.run_tool(
                "claim", map_path, "--decision", decision_id, "--claimant", session_id, "--session", session_id
            )
            resolve = self.run_tool(
                "resolve", map_path, "--decision", decision_id, "--session", session_id,
                "--resolution", f"resolved by {session_id}", "--evidence", f"evidence-{session_id}",
            )
            results[decision_id] = (claim.returncode, resolve.returncode)

        threads = [
            threading.Thread(target=claim_and_resolve, args=("staffing-model", "s-a")),
            threading.Thread(target=claim_and_resolve, args=("rig-topology", "s-b")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual((0, 0), results["staffing-model"])
        self.assertEqual((0, 0), results["rig-topology"])

        state = self.load(map_path)
        self.assertEqual("resolved", state["decisions"]["staffing-model"]["status"])
        self.assertEqual("resolved", state["decisions"]["rig-topology"]["status"])
        # both independently resolved -> route is clear with no lost update
        self.assertEqual("to_spec_ready", state["status"])

    def test_racing_claims_on_the_same_decision_produce_exactly_one_winner(self):
        map_path, _ = self.promote()

        outcomes = []
        lock = threading.Lock()
        barrier = threading.Barrier(5)

        def race(session_id):
            barrier.wait()
            proc = self.run_tool(
                "claim", map_path, "--decision", "staffing-model", "--claimant", session_id, "--session", session_id
            )
            with lock:
                outcomes.append(proc.returncode)

        threads = [threading.Thread(target=race, args=(f"s-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(1, outcomes.count(0))
        self.assertEqual(4, outcomes.count(1))

        state = self.load(map_path)
        self.assertEqual("claimed", state["decisions"]["staffing-model"]["status"])
        # the untouched decision remains open -- no cross-decision interference
        self.assertEqual("open", state["decisions"]["rig-topology"]["status"])

    # --- AC4: pause releases sessions and retains evidence; resume refreshes
    # only time-sensitive facts; abandon publishes nothing ------------------

    def test_pause_releases_sessions_but_retains_map_resolutions_and_evidence(self):
        map_path, _ = self.promote()
        self.run_tool(
            "claim", map_path, "--decision", "staffing-model", "--claimant", "session-a", "--session", "s-a",
            check=True,
        )
        self.run_tool(
            "resolve", map_path, "--decision", "staffing-model", "--session", "s-a",
            "--resolution", "embedded staffing", "--evidence", "af-example-evidence", check=True,
        )
        self.run_tool(
            "claim", map_path, "--decision", "rig-topology", "--claimant", "session-b", "--session", "s-b",
            check=True,
        )

        pause = json.loads(self.run_tool("pause", map_path, "--reason", "benjamin unavailable", check=True).stdout)
        self.assertTrue(pause["ok"])
        self.assertEqual(["rig-topology"], pause["released_decisions"])

        state = self.load(map_path)
        self.assertEqual("paused", state["status"])
        released = state["decisions"]["rig-topology"]
        self.assertEqual("open", released["status"])
        self.assertIsNone(released["claimed_by"])
        self.assertIsNone(released["session_id"])

        resolved = state["decisions"]["staffing-model"]
        self.assertEqual("resolved", resolved["status"])
        self.assertEqual("embedded staffing", resolved["resolution"])
        self.assertEqual("af-example-evidence", resolved["evidence"])

        # cannot claim or resolve while paused
        proc = self.run_tool(
            "claim", map_path, "--decision", "rig-topology", "--claimant", "session-c", "--session", "s-c"
        )
        self.assertNotEqual(0, proc.returncode)

    def test_resume_refreshes_only_declared_time_sensitive_facts(self):
        map_path, _ = self.promote()
        self.run_tool("pause", map_path, "--reason", "interruption", check=True)

        resume = json.loads(
            self.run_tool("resume", map_path, "--refresh", FIXTURES / "refresh-valid.json", check=True).stdout
        )
        self.assertTrue(resume["ok"])
        self.assertEqual("active", resume["status"])

        state = self.load(map_path)
        self.assertEqual(
            "factory_workspace, fixture_city both green as of resume",
            state["time_sensitive_facts"]["rig_availability"],
        )

    def test_resume_rejects_refresh_of_non_time_sensitive_fields(self):
        map_path, _ = self.promote()
        self.run_tool("pause", map_path, "--reason", "interruption", check=True)

        proc = self.run_tool("resume", map_path, "--refresh", FIXTURES / "refresh-out-of-scope.json")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertIn("not declared time-sensitive", error["error"])

        # rejection leaves the run paused, untouched
        state = self.load(map_path)
        self.assertEqual("paused", state["status"])

    def test_abandon_publishes_nothing(self):
        map_path, _ = self.promote()
        self.run_tool(
            "claim", map_path, "--decision", "staffing-model", "--claimant", "session-a", "--session", "s-a",
            check=True,
        )

        before = set(self.tmp.iterdir())
        abandon = json.loads(self.run_tool("abandon", map_path, "--reason", "superseded", check=True).stdout)
        after = set(self.tmp.iterdir())

        self.assertTrue(abandon["ok"])
        self.assertEqual("abandoned", abandon["status"])
        self.assertEqual(before, after)  # no other artifact was created

        state = self.load(map_path)
        self.assertEqual("abandoned", state["status"])

        proc = self.run_tool("abandon", map_path, "--reason", "again")
        self.assertNotEqual(0, proc.returncode)

    # --- AC5: to-spec starts without a second fog audit ---------------------

    def test_route_clear_flips_to_spec_ready_inside_the_closing_resolve(self):
        map_path, _ = self.promote()
        self.run_tool(
            "claim", map_path, "--decision", "staffing-model", "--claimant", "session-a", "--session", "s-a",
            check=True,
        )
        self.run_tool(
            "resolve", map_path, "--decision", "staffing-model", "--session", "s-a",
            "--resolution", "a", "--evidence", "e-a", check=True,
        )
        self.run_tool(
            "claim", map_path, "--decision", "rig-topology", "--claimant", "session-b", "--session", "s-b",
            check=True,
        )
        closing = json.loads(
            self.run_tool(
                "resolve", map_path, "--decision", "rig-topology", "--session", "s-b",
                "--resolution", "b", "--evidence", "e-b", check=True,
            ).stdout
        )
        self.assertTrue(closing["to_spec_ready"])

        status = json.loads(self.run_tool("status", map_path, check=True).stdout)
        self.assertTrue(status["route_clear"])
        self.assertTrue(status["to_spec_eligible"])

    def test_tool_exposes_no_separate_fog_audit_subcommand(self):
        proc = self.run_tool("--help", check=True)
        for token in ("audit", "fog-audit", "fog_audit"):
            self.assertNotIn(token, proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()
