#!/usr/bin/env python3
"""One test proves the whole Planning Run path (A6b, W07, af-scwme1).

Drives the wired Planning Run lifecycle end-to-end through the doors' real
command lines against a fake `bd` (and a fake `gc` for the Mayor wake-up):
a finished Planning Map Bead with its Planning Decision Bead children, a
Spec bead naming it, `spec-approve bd-approve` (bin/spec-approve), then
`ticket-graph-publish bd-publish` (bin/ticket-graph-publish) publishing a
Ticket Graph Draft bead into a delivery convoy. Covers every refusal named
in af-3s8prq: an unfinished map, a Spec whose target is not the active
Planning Run Reservation, a wrong approver, a Spec edited after approval
(approval void, publication refused), and an unmapped Spec with no No-fog
exit evidence -- plus the positive unmapped path with valid evidence.

This is the proof of the whole wired path; it replaced
tests/planning-run-router-test.py in that role, which W10 (A6b) later
deleted along with the router itself. Every assertion is against the
doors' stdout/stderr/exit code and the beads the fake `bd` store is left
holding -- never against the doors' internal Python functions.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_APPROVE = ROOT / "bin" / "spec-approve"
TICKET_GRAPH_PUBLISH = ROOT / "bin" / "ticket-graph-publish"
DISPATCH_DOOR = ROOT / "bin" / "dispatch-door"

FIXTURES = ROOT / "tests" / "fixtures" / "planning-run-lifecycle"
FAKE_BD = FIXTURES / "bd"
FAKE_GC = FIXTURES / "gc"
FAKE_DISPATCH_GC = FIXTURES / "dispatch-gc"
FAKE_PROVIDER_FAILOVER = FIXTURES / "provider-failover"

PROJECTS_CONFIG_DIR = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"
HUMAN_APPROVER = "benjamin"
PROJECT = "acme"

EVIDENCE = "Benjamin's exact words, 2026-09-30 Paris"
NO_FOG_EVIDENCE = "« pas de brouillard » (Benjamin, 2026-09-30 Paris)"


def digest(description: str) -> str:
    """The one canonical Spec/draft bead digest formula both doors share
    (sha256 of the raw description text) -- see canonical_bead_digest in
    bin/spec-approve and bin/ticket-graph-publish."""
    return "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()


ONE_TICKET_YAML = (
    "  - id: T1\n"
    "    title: Ship the thing\n"
    "    blocked_by: []\n"
    "    target_rigs: [fixture_city]\n"
    "    what_it_delivers: does a thing\n"
    "    acceptance_criteria: [does the thing]\n"
    "    scope:\n"
    "      paths: [bin/foo.py]\n"
)


def draft_description(tickets_yaml: str = ONE_TICKET_YAML) -> str:
    return (
        "global_execution_contract:\n"
        "  models: none\n"
        "\n"
        "tickets:\n" + tickets_yaml
    )


class PlanningRunLifecycleTest(unittest.TestCase):
    """Base fixture: one fake `bd` state file and one repo-root scratch
    directory (for the reservation's runtime file) per test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="planning-run-lifecycle-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()
        self.gc_log = self.tmp / "gc.log"

    # --- bd state -------------------------------------------------------

    def seed(self, beads: dict, next_id: int = 1):
        self.state_path.write_text(json.dumps({"beads": beads, "next_id": next_id}))

    def current_state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def bead(self, **kwargs) -> dict:
        base = {
            "labels": [], "metadata": {}, "parent": None, "status": "open",
            "title": "", "description": "",
        }
        base.update(kwargs)
        return base

    def write_reservation(self, reserved_for: str | None, next_target: str | None = None):
        runtime_path = self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "cleared_at": None,
        }
        if next_target:
            record["next"] = {"reserved_for": next_target}
        runtime_path.write_text(json.dumps(record))

    def reservation_state(self) -> dict:
        return json.loads(
            (self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json").read_text()
        )

    # --- Planning Map + Planning Decision Bead builders -------------------

    def finished_map_beads(self, map_id: str = "map-1") -> dict:
        """A finished map: labelled wayfinder:map, one closed
        wayfinder:-labelled planning-plane child -- exactly what
        `bin/planning-map check` reports `finished: true` for."""
        return {
            map_id: self.bead(id=map_id, labels=["wayfinder:map"], metadata={"gc.plane": "planning"}),
            f"{map_id}.1": self.bead(
                id=f"{map_id}.1", parent=map_id, status="closed",
                labels=["wayfinder:grilling"], metadata={"gc.plane": "planning"},
            ),
        }

    def unfinished_map_beads(self, map_id: str = "map-1") -> dict:
        beads = self.finished_map_beads(map_id)
        beads[f"{map_id}.1"]["status"] = "open"
        return beads

    def spec_bead(
        self, spec_id="spec-1", target="A6b", map_id="map-1", description="prose spec body\n\n## User Stories\n\n1. As an operator, I want a probe, so that I know it runs.\n",
        no_fog_evidence=None, project_id=PROJECT,
    ) -> dict:
        metadata = {"planning_run_target": target, "planning_map": map_id or "none", "gc.plane": "planning"}
        if no_fog_evidence is not None:
            metadata["no_fog_evidence"] = no_fog_evidence
        if project_id is not None:
            metadata["gc.project_id"] = project_id
        return self.bead(id=spec_id, description=description, metadata=metadata)

    def draft_bead(
        self, draft_id="draft-1", spec_id="spec-1", tickets_yaml=ONE_TICKET_YAML,
        approved_by=HUMAN_APPROVER, approved_evidence=EVIDENCE, digest_override=None,
        display_title="Effort d'exemple", language="fr",
    ) -> dict:
        description = draft_description(tickets_yaml)
        metadata = {
            "spec_id": spec_id,
            "approved_by": approved_by,
            "approved_evidence": approved_evidence,
            "approved_digest": digest_override if digest_override is not None else digest(description),
            "gc.plane": "planning",
        }
        if display_title is not None:
            metadata["display_title"] = display_title
        if language is not None:
            metadata["language"] = language
        return self.bead(id=draft_id, title="Ticket Graph Draft", description=description, metadata=metadata)

    # --- door invocations --------------------------------------------------

    def spec_approve_env(self, **overrides) -> dict:
        env = {**os.environ, "BD_BIN": str(FAKE_BD), "PLANNING_RUN_LIFECYCLE_BD_STATE": str(self.state_path)}
        env.update(overrides)
        return env

    def bd_approve(self, spec_id="spec-1", approved_by=HUMAN_APPROVER, evidence=EVIDENCE, check=False):
        return subprocess.run(
            (str(SPEC_APPROVE), "bd-approve", "--spec", spec_id, "--approved-by", approved_by,
             "--evidence", evidence, "--project", PROJECT, "--repo-root", str(self.repo_root),
             "--config-dir", str(PROJECTS_CONFIG_DIR)),
            env=self.spec_approve_env(), text=True, capture_output=True, check=check,
        )

    def bd_status(self, spec_id="spec-1", check=True):
        return subprocess.run(
            (str(SPEC_APPROVE), "bd-status", "--spec", spec_id),
            env=self.spec_approve_env(), text=True, capture_output=True, check=check,
        )

    def bd_publish(self, draft_id="draft-1", check=False, env_overrides=None, wake_mayor=False):
        env = self.spec_approve_env(
            TICKET_GRAPH_BD_STATE=str(self.state_path),
            GC_BIN=str(FAKE_GC),
            PLANNING_RUN_LIFECYCLE_GC_LOG=str(self.gc_log),
            TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY=("" if wake_mayor else "1"),
        )
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            (str(TICKET_GRAPH_PUBLISH), "bd-publish", draft_id, "--project", PROJECT,
             "--repo-root", str(self.repo_root), "--config-dir", str(PROJECTS_CONFIG_DIR)),
            env=env, text=True, capture_output=True, check=check,
        )

    def gc_log_lines(self) -> list[str]:
        if not self.gc_log.exists():
            return []
        return [line for line in self.gc_log.read_text().splitlines() if line.strip()]

    def dispatch_door(self, bead_id: str, dispatch_log: Path):
        env = {
            **os.environ,
            "GC_BIN": str(FAKE_DISPATCH_GC),
            "PLANNING_RUN_LIFECYCLE_BD_STATE": str(self.state_path),
            "PLANNING_RUN_LIFECYCLE_DISPATCH_LOG": str(dispatch_log),
            "DISPATCH_DOOR_PROVIDER_FAILOVER_BIN": str(FAKE_PROVIDER_FAILOVER),
        }
        return subprocess.run(
            (str(DISPATCH_DOOR), bead_id, "--rig", "agent-factory", "--formula", "mol-do-work"),
            env=env, text=True, capture_output=True,
        )

    # =====================================================================
    # 1. Nominal mapped path: approve then publish reach a published convoy
    # =====================================================================

    def test_nominal_mapped_run_publishes_a_convoy_closes_map_advances_reservation_wakes_mayor(self):
        self.seed({**self.finished_map_beads(), "spec-1": self.spec_bead()})
        self.write_reservation(reserved_for="A6b")

        approve = self.bd_approve(check=True)
        approved = json.loads(approve.stdout)
        self.assertTrue(approved["ok"])
        self.assertTrue(approved["map_closed"])
        self.assertEqual("APPROVED_SPEC", approved["state"])

        state = self.current_state()
        self.assertEqual("closed", state["beads"]["map-1"]["status"])
        self.assertEqual("APPROVED_SPEC", state["beads"]["spec-1"]["metadata"]["spec_state"])

        # status confirms the approval is not void immediately after approval
        status = json.loads(self.bd_status().stdout)
        self.assertFalse(status["void"])

        state = self.current_state()
        state["beads"]["draft-1"] = self.draft_bead()
        self.state_path.write_text(json.dumps(state))

        publish = self.bd_publish(check=True, wake_mayor=True)
        result = json.loads(publish.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(result["ids"]))  # _convoy, T1
        self.assertIs(True, result["mayor_notified"])
        self.assertEqual("cleared", result["reservation_advanced"]["result"])

        state = self.current_state()
        delivery = [
            b for b in state["beads"].values()
            if b["metadata"].get("gc.plane") == "delivery"
        ]
        self.assertEqual(2, len(delivery))  # convoy + T1
        convoy = next(b for b in delivery if "gc.ticket_id" not in b["metadata"])
        self.assertEqual("open", convoy["status"])

        self.assertIsNotNone(self.reservation_state()["cleared_at"])

    # =====================================================================
    # 2. Refusal: map not finished
    # =====================================================================

    def test_refuses_unfinished_map(self):
        self.seed({**self.unfinished_map_beads(), "spec-1": self.spec_bead()})

        proc = self.bd_approve()
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("not finished", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    # =====================================================================
    # 3. Refusal: wrong target while a different target is reserved
    # =====================================================================

    def test_refuses_wrong_target_while_reserved(self):
        self.seed({**self.finished_map_beads(), "spec-1": self.spec_bead(target="A6b")})
        self.write_reservation(reserved_for="C01")

        proc = self.bd_approve()
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("C01", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])
        self.assertEqual("open", state["beads"]["map-1"]["status"])

    # =====================================================================
    # 4. Refusal: wrong approver
    # =====================================================================

    def test_refuses_wrong_approver(self):
        self.seed({**self.finished_map_beads(), "spec-1": self.spec_bead()})

        proc = self.bd_approve(approved_by="someone-else")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("declared human approver", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    # =====================================================================
    # 5. Refusal: Spec edited after approval -- approval void, publish refused
    # =====================================================================

    def test_spec_edited_after_approval_voids_approval_and_publish_refuses(self):
        self.seed({**self.finished_map_beads(), "spec-1": self.spec_bead()})
        self.write_reservation(reserved_for="A6b")

        self.assertTrue(json.loads(self.bd_approve(check=True).stdout)["ok"])

        state = self.current_state()
        state["beads"]["spec-1"]["description"] = "edited after approval"
        state["beads"]["draft-1"] = self.draft_bead()
        self.state_path.write_text(json.dumps(state))

        status = json.loads(self.bd_status().stdout)
        self.assertTrue(status["void"])

        publish = self.bd_publish()
        self.assertNotEqual(0, publish.returncode)
        self.assertIn("digest differs from its approved digest", publish.stderr)

        state = self.current_state()
        self.assertEqual({"map-1", "map-1.1", "spec-1", "draft-1"}, set(state["beads"]))

    # =====================================================================
    # 6. Refusal: unmapped Spec without No-fog evidence
    # =====================================================================

    def test_refuses_unmapped_spec_without_no_fog_evidence(self):
        self.seed({"spec-1": self.spec_bead(map_id="none", no_fog_evidence=None)})

        proc = self.bd_approve()
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("No-fog", error["error"])

        state = self.current_state()
        self.assertNotIn("spec_state", state["beads"]["spec-1"]["metadata"])

    # =====================================================================
    # 7. Positive: unmapped Spec WITH valid No-fog evidence is approved and
    #    published
    # =====================================================================

    def test_valid_unmapped_run_is_approved_and_published(self):
        self.seed({"spec-1": self.spec_bead(map_id="none", no_fog_evidence=NO_FOG_EVIDENCE)})
        self.write_reservation(reserved_for="A6b")

        approve = self.bd_approve(check=True)
        result = json.loads(approve.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["map_closed"])
        self.assertIsNone(result["map"])

        state = self.current_state()
        state["beads"]["draft-1"] = self.draft_bead()
        self.state_path.write_text(json.dumps(state))

        publish = self.bd_publish(check=True)
        result = json.loads(publish.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(result["ids"]))

        state = self.current_state()
        convoy = next(
            b for b in state["beads"].values()
            if b["metadata"].get("gc.plane") == "delivery" and "gc.ticket_id" not in b["metadata"]
        )
        self.assertEqual("open", convoy["status"])

    # =====================================================================
    # 8. No planning bead is ever dispatched, woken for, or counted as
    #    delivery
    # =====================================================================

    def test_no_planning_bead_is_ever_dispatched_woken_for_or_counted_as_delivery(self):
        self.seed({**self.finished_map_beads(), "spec-1": self.spec_bead()})
        self.write_reservation(reserved_for="A6b")
        self.assertTrue(json.loads(self.bd_approve(check=True).stdout)["ok"])

        state = self.current_state()
        state["beads"]["draft-1"] = self.draft_bead()
        self.state_path.write_text(json.dumps(state))

        result = json.loads(self.bd_publish(check=True, wake_mayor=True).stdout)
        self.assertTrue(result["ok"])
        self.assertIs(True, result["mayor_notified"])
        convoy_id = result["ids"]["_convoy"]

        state = self.current_state()
        planning_bead_ids = {"map-1", "map-1.1", "spec-1", "draft-1"}
        delivery_bead_ids = set(state["beads"]) - planning_bead_ids

        # (a) never counted as delivery: every planning-plane bead keeps
        # gc.plane=planning; only the beads the publish created carry
        # gc.plane=delivery.
        for bead_id in planning_bead_ids:
            self.assertEqual(
                "planning", state["beads"][bead_id]["metadata"].get("gc.plane"),
                f"{bead_id} must stay on the planning plane",
            )
        for bead_id in delivery_bead_ids:
            self.assertEqual("delivery", state["beads"][bead_id]["metadata"].get("gc.plane"))

        # (b) never woken for: the Mayor wake-up mail only ever names the
        # convoy/graph digest, never a planning bead id.
        gc_log_text = "\n".join(self.gc_log_lines())
        self.assertIn(convoy_id, gc_log_text)
        for bead_id in planning_bead_ids:
            self.assertNotIn(bead_id, gc_log_text)

        # (c) never dispatched: bin/dispatch-door -- the actual dispatch
        # gate, not a bespoke check -- refuses each planning-plane bead
        # before any sling or stamp call, the same way
        # tests/dispatch-door-test.sh proves for a hand-built fixture bead.
        for bead_id in planning_bead_ids:
            dispatch_log = self.tmp / f"dispatch-{bead_id.replace('.', '_')}.log"
            proc = self.dispatch_door(bead_id, dispatch_log)
            self.assertEqual(2, proc.returncode, f"{bead_id}: {proc.stderr}")
            self.assertIn("planning-plane bead", proc.stderr)
            calls = [line for line in dispatch_log.read_text().splitlines() if line.strip()]
            self.assertEqual(1, len(calls), f"{bead_id}: dispatch-door called gc after refusing: {calls}")
            self.assertIn("bd show", calls[0])


if __name__ == "__main__":
    unittest.main()
