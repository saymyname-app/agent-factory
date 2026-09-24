#!/usr/bin/env python3

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "planning-run-router"
FIXTURES = ROOT / "tests" / "fixtures" / "planning-run-router"
FAKE_BD = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "bd"

CITY_REGISTRY = FIXTURES / "city-registry.json"
SIMPLE_SESSION = FIXTURES / "sessions" / "simple.json"
MISSING_TOPIC_SESSION = FIXTURES / "sessions" / "missing-topic.json"
WAYFINDING_SESSION = FIXTURES / "sessions" / "wayfinding.json"
WAYFINDING_REQUEST = FIXTURES / "wayfinding" / "request.json"

REQUEST_CONTRACT = "agent-factory-planning-run-router-request/v1"


def scoped_digest(raw: bytes) -> str:
    marker = b"\nlegacy_boundary:"
    start = raw.index(marker) + 1
    return "sha256:" + hashlib.sha256(raw[start:]).hexdigest()


def build_draft(spec_id: str) -> tuple[bytes, str]:
    """A minimal, already-approved Ticket Graph Draft naming `spec_id` as its
    source Spec. `ticket-graph-publish` only checks the source Spec digest is
    a well-formed sha256 string (it does not cross-check it against a real
    Spec file), so a fixed placeholder digest is legitimate here -- the
    router never re-slices a Spec, it only sequences the existing publish
    door against a caller-supplied, already-approved draft."""
    body = (
        "legacy_boundary:\n"
        "  note: planning-run-router fixture\n"
        "\n"
        "global_execution_contract:\n"
        "  models: no Astra or Fable\n"
        "\n"
        "tickets:\n"
        "  - id: R01\n"
        "    kind: vertical_slice\n"
        "    title: Router fixture ticket\n"
        "    blocked_by: []\n"
        "    target_rigs: [fixture_city]\n"
        "    what_it_delivers: proves the router publishes through the existing door\n"
        "    acceptance_criteria: [router fixture ticket exists]\n"
    ).encode("utf-8")
    digest = scoped_digest(b"\n" + body)
    header = (
        "artifact:\n"
        "  id: router-fixture-graph\n"
        "  state: APPROVED_TICKET_GRAPH_DRAFT\n"
        "  approved_by: Test\n"
        "  approved_at: 2026-09-24\n"
        f"  content_digest: {digest}\n"
        "  digest_scope: UTF-8 bytes from the legacy_boundary key through end of file, with LF line endings\n"
        "  source_spec:\n"
        f"    id: {spec_id}\n"
        "    state: APPROVED_SPEC\n"
        f"    digest: sha256:{'0' * 64}\n"
        "  publication_authorized: true\n"
        "\n"
    ).encode("utf-8")
    return header + body, digest


class PlanningRunRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="planning-run-router-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bd_log = self.tmp / "bd.log"
        self.bd_capture = self.tmp / "bd-graph.json"

    def bd_env(self):
        return {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "TICKET_GRAPH_BD_LOG": str(self.bd_log),
            "TICKET_GRAPH_CAPTURE": str(self.bd_capture),
            "TICKET_GRAPH_EXISTING": "[]",
        }

    def write_request(self, request, name="request.json"):
        path = self.tmp / name
        path.write_text(json.dumps(request), encoding="utf-8")
        return path

    def run_router(self, request_path, env=None, check=False, repo_root=None):
        # Default repo_root to this test's own scratch directory, not the
        # real repo root -- every fixture path the tests pass is already
        # absolute (resolve_path only joins repo_root onto a relative path),
        # so this only changes where the router looks for
        # config/planning-run-reservation.json: an empty scratch dir has none,
        # keeping these tests isolated from the shipped C01 reservation.
        return subprocess.run(
            (str(TOOL), "--repo-root", str(repo_root or self.tmp), "run", str(request_path)),
            cwd=ROOT, env=env or {**os.environ}, text=True, capture_output=True, check=check,
        )

    def base_request(self, session, spec_out=None, approval=None, publish=None, wayfinding=None):
        request = {
            "contract": REQUEST_CONTRACT,
            "legacy_path": "none",
            "session": str(session),
            "city_registry": str(CITY_REGISTRY),
            "spec_out": str(spec_out or (self.tmp / "specs")),
        }
        if wayfinding is not None:
            request["wayfinding"] = wayfinding
        if approval is not None:
            request["approval"] = approval
        if publish is not None:
            request["publish"] = publish
        return request

    # --- legacy_path is translated before any Planning Run identity -------

    def test_legacy_path_selectors_are_rejected_before_any_identity_is_created(self):
        expectations = {
            "planning-base": "planning-base methodology",
            "release-contract": "agent-factory-product-release/v1",
            "cockpit-v1-export": "Cockpit V1",
        }
        for legacy_path, expected_fragment in expectations.items():
            with self.subTest(legacy_path=legacy_path):
                request_path = self.write_request(
                    {"contract": REQUEST_CONTRACT, "legacy_path": legacy_path},
                    name=f"legacy-{legacy_path}.json",
                )
                proc = self.run_router(request_path, check=True)
                result = json.loads(proc.stdout)
                self.assertTrue(result["ok"])
                self.assertEqual("legacy_path_rejected", result["result"])
                self.assertEqual(legacy_path, result["legacy_path"])
                self.assertIn(expected_fragment, result["reason"])
                self.assertFalse((self.tmp / "specs").exists())

    def test_unrecognized_legacy_path_selector_is_rejected(self):
        request_path = self.write_request({"contract": REQUEST_CONTRACT, "legacy_path": "something-else"})
        proc = self.run_router(request_path)
        self.assertNotEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertFalse(result["ok"])

    # --- a simple request completes session -> Spec -> approval ->
    #     publication -> convoy through the router alone -------------------

    def test_simple_request_completes_end_to_end_through_the_router_alone(self):
        spec_out = self.tmp / "specs"
        draft_bytes, _ = build_draft("router-simple-2026-09-24")
        draft_path = self.tmp / "draft.yaml"
        draft_path.write_bytes(draft_bytes)

        request = self.base_request(
            SIMPLE_SESSION,
            spec_out=spec_out,
            approval={"approved_by": "benjamin", "evidence": "af-fixture-evidence"},
            publish={"draft": str(draft_path)},
        )
        request_path = self.write_request(request)

        proc = self.run_router(request_path, env=self.bd_env(), check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("published", result["result"])
        self.assertIn("_convoy", result["ids"])

        spec_path = spec_out / "spec-router-simple-2026-09-24.json"
        spec = json.loads(spec_path.read_text())
        self.assertEqual("APPROVED_SPEC", spec["state"])
        self.assertEqual("benjamin", spec["approved_by"])

    def test_rerunning_the_same_simple_request_from_scratch_is_safe(self):
        spec_out = self.tmp / "specs"
        draft_bytes, _ = build_draft("router-simple-2026-09-24")
        draft_path = self.tmp / "draft.yaml"
        draft_path.write_bytes(draft_bytes)

        request = self.base_request(
            SIMPLE_SESSION,
            spec_out=spec_out,
            approval={"approved_by": "benjamin", "evidence": "af-fixture-evidence"},
            publish={"draft": str(draft_path)},
        )
        request_path = self.write_request(request)

        env = self.bd_env()
        first = json.loads(self.run_router(request_path, env=env, check=True).stdout)

        # The fake `bd` has no memory of its own between invocations, so the
        # second run's `bd list` is told what the first run actually
        # published -- exactly what a real Beads store would report back.
        graph_digest = first["graph_digest"]
        existing = [
            {"id": bead_id, "status": "open", "metadata": {
                "gc.graph_digest": graph_digest,
                **({"gc.ticket_id": key} if key != "_convoy" else {}),
            }}
            for key, bead_id in first["ids"].items()
        ]
        env = {**env, "TICKET_GRAPH_EXISTING": json.dumps(existing)}
        second = json.loads(self.run_router(request_path, env=env, check=True).stdout)

        self.assertEqual("published", first["result"])
        self.assertEqual("published", second["result"])
        self.assertEqual(first["ids"], second["ids"])
        calls = [json.loads(line) for line in self.bd_log.read_text(encoding="utf-8").splitlines()]
        # The underlying publish door dedups by graph digest -- a second full
        # rerun that finds its own prior publication never issues a second
        # `create --graph` transaction.
        self.assertEqual(1, sum(1 for call in calls if call[:2] == ["create", "--graph"]))

    # --- a Wayfinding request completes session -> Spec -> approval ->
    #     publication -> convoy through the router alone -------------------

    def test_wayfinding_request_completes_end_to_end_through_the_router_alone(self):
        spec_out = self.tmp / "specs"
        draft_bytes, _ = build_draft("router-wayfinding-2026-09-24")
        draft_path = self.tmp / "draft.yaml"
        draft_path.write_bytes(draft_bytes)

        wayfinding = {
            "request": str(WAYFINDING_REQUEST),
            "map": str(self.tmp / "map.json"),
            "decisions": [
                {
                    "decision": "staffing-model",
                    "claimant": "session-a",
                    "session": "s-a",
                    "resolution": "embedded staffing",
                    "evidence": "af-fixture-evidence",
                },
                {
                    "decision": "rig-topology",
                    "claimant": "session-a",
                    "session": "s-a",
                    "resolution": "hub-and-spoke",
                    "evidence": "af-fixture-evidence",
                },
            ],
        }
        request = self.base_request(
            WAYFINDING_SESSION,
            spec_out=spec_out,
            approval={"approved_by": "benjamin", "evidence": "af-fixture-evidence"},
            publish={"draft": str(draft_path)},
            wayfinding=wayfinding,
        )
        request_path = self.write_request(request)

        proc = self.run_router(request_path, env=self.bd_env(), check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("published", result["result"])
        self.assertIn("_convoy", result["ids"])

        map_state = json.loads((self.tmp / "map.json").read_text())
        self.assertEqual("closed", map_state["status"])

        spec_path = spec_out / "spec-router-wayfinding-2026-09-24.json"
        spec = json.loads(spec_path.read_text())
        self.assertEqual("APPROVED_SPEC", spec["state"])

    def test_wayfinding_request_with_decisions_still_open_stays_pending(self):
        wayfinding = {
            "request": str(WAYFINDING_REQUEST),
            "map": str(self.tmp / "map.json"),
            "decisions": [
                {
                    "decision": "staffing-model",
                    "claimant": "session-a",
                    "session": "s-a",
                    "resolution": "embedded staffing",
                    "evidence": "af-fixture-evidence",
                },
            ],
        }
        request = self.base_request(WAYFINDING_SESSION, wayfinding=wayfinding)
        request_path = self.write_request(request)

        proc = self.run_router(request_path, check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("wayfinding_pending", result["result"])
        self.assertFalse((self.tmp / "specs").exists())

    # --- a real contradiction/missing trace returns to planning instead of
    #     inventing a Spec, and creates no Spec, approval or convoy --------

    def test_missing_trace_returns_to_planning_and_creates_no_spec_or_convoy(self):
        request = self.base_request(MISSING_TOPIC_SESSION)
        request_path = self.write_request(request)

        proc = self.run_router(request_path, check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("missing_trace", result["signal"])
        self.assertFalse((self.tmp / "specs").exists())

    # --- approval is never fabricated; publication is never re-sliced -----

    def test_missing_approval_stops_after_spec_synthesis_without_publishing(self):
        spec_out = self.tmp / "specs"
        request = self.base_request(SIMPLE_SESSION, spec_out=spec_out)
        request_path = self.write_request(request)

        proc = self.run_router(request_path, check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("awaiting_approval", result["result"])
        spec = json.loads((spec_out / "spec-router-simple-2026-09-24.json").read_text())
        self.assertEqual("DRAFT_SPEC", spec["state"])

    def test_approved_spec_without_a_draft_stops_before_publication(self):
        spec_out = self.tmp / "specs"
        request = self.base_request(
            SIMPLE_SESSION, spec_out=spec_out,
            approval={"approved_by": "benjamin", "evidence": "af-fixture-evidence"},
        )
        request_path = self.write_request(request)

        proc = self.run_router(request_path, check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("approved_awaiting_publication", result["result"])
        spec = json.loads((spec_out / "spec-router-simple-2026-09-24.json").read_text())
        self.assertEqual("APPROVED_SPEC", spec["state"])

    # --- a reservation blocks every request except the one it names, and is
    #     cleared once that reserved request publishes (B12 AC#5) -----------

    def write_reservation(self, reserved_for="C01", cleared_at=None):
        config_dir = self.tmp / "config"
        config_dir.mkdir(exist_ok=True)
        path = config_dir / "planning-run-reservation.json"
        path.write_text(json.dumps({
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "note": "test reservation",
            "reserved_at": "2026-09-24",
            "reserved_by": "planning-run-router-test",
            "cleared_at": cleared_at,
        }), encoding="utf-8")
        return path

    def test_reservation_blocks_a_request_that_does_not_declare_the_reserved_target(self):
        self.write_reservation(reserved_for="C01")
        request = self.base_request(SIMPLE_SESSION)
        request_path = self.write_request(request)

        proc = self.run_router(request_path, check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("reservation_blocked", result["result"])
        self.assertEqual("C01", result["reserved_for"])
        self.assertIn("C01", result["reason"])
        self.assertFalse((self.tmp / "specs").exists())

    def test_reservation_lets_the_declared_target_through_and_then_clears(self):
        reservation_path = self.write_reservation(reserved_for="C01")
        spec_out = self.tmp / "specs"
        draft_bytes, _ = build_draft("router-simple-2026-09-24")
        draft_path = self.tmp / "draft.yaml"
        draft_path.write_bytes(draft_bytes)

        request = self.base_request(
            SIMPLE_SESSION,
            spec_out=spec_out,
            approval={"approved_by": "benjamin", "evidence": "af-fixture-evidence"},
            publish={"draft": str(draft_path)},
        )
        request["planning_run_target"] = "C01"
        request_path = self.write_request(request)

        proc = self.run_router(request_path, env=self.bd_env(), check=True)
        result = json.loads(proc.stdout)

        self.assertTrue(result["ok"])
        self.assertEqual("published", result["result"])

        reservation_after = json.loads(reservation_path.read_text())
        self.assertIsNotNone(reservation_after["cleared_at"])

        # Once cleared, a later request that names no target is unblocked.
        second_request = self.base_request(SIMPLE_SESSION, spec_out=self.tmp / "specs-2")
        second_request_path = self.write_request(second_request, name="second-request.json")
        second = json.loads(
            self.run_router(second_request_path, check=True).stdout
        )
        self.assertNotEqual("reservation_blocked", second["result"])


if __name__ == "__main__":
    unittest.main()
