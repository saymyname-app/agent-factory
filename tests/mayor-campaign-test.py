#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_campaign import plan_transition  # noqa: E402


def metadata(state="active"):
    value = {
        "gc.current_jit": "none", "gc.needs_benjamin": "none",
        "gc.campaign_mode": "automatic", "gc.campaign_state": state,
        "gc.campaign_candidate": "af-cm1l",
        "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
        "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
        "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0",
        "gc.resume_mode": "automatic_campaign",
        "gc.resume_condition": "Le Mayor enchaîne le premier candidat éligible",
    }
    return value


def status(next_id="af-next", result=None, mode="automatic_campaign"):
    campaign = {
        "enabled": True, "state": "active", "blocked": False,
        "wake_key": None, "wake_state": "none",
    }
    return {
        "contract": "agent-factory-human-state/v1", "campaign": campaign,
        "resume": {"mode": mode},
        "result": result or {"id": None, "state": "none"},
        "next_candidate": ({"id": next_id} if next_id else None),
    }


class MayorCampaignTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state_file = self.root / "coordination.json"
        self.status_file = self.root / "status.json"
        self.log_file = self.root / "calls.log"
        self.lock_file = self.root / "campaign.lock"
        self.fixture = ROOT / "tests" / "fixtures" / "mayor-campaign"
        self.env = {
            **os.environ,
            "GC_BIN": str(self.fixture / "gc"),
            "SAYMYNAME_STATUS_BIN": str(self.fixture / "status"),
            "CAMPAIGN_STATE_FILE": str(self.state_file),
            "CAMPAIGN_STATUS_FILE": str(self.status_file),
            "CAMPAIGN_CALL_LOG": str(self.log_file),
            "CAMPAIGN_LOCK_FILE": str(self.lock_file),
        }
        self.write_state(metadata())
        self.write_status(status())

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, value):
        self.state_file.write_text(json.dumps({"id": "af-1vr4", "metadata": value}), encoding="utf-8")

    def write_status(self, value):
        self.status_file.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, *args, check=True, extra_env=None):
        return subprocess.run(
            (str(ROOT / "bin" / "mayor-campaign"), *args), cwd=ROOT,
            env={**self.env, **(extra_env or {})}, text=True, capture_output=True, check=check,
        )

    def current_metadata(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))["metadata"]

    def mail_count(self):
        if not self.log_file.exists():
            return 0
        return sum("mail send mayor" in line for line in self.log_file.read_text(encoding="utf-8").splitlines())

    def test_plans_only_one_authorized_transition(self):
        planned = plan_transition(status())
        self.assertEqual(("wake_mayor", "materialize:af-next"), (planned["action"], planned["wake_key"]))
        active = status(result={"id": "af-exec", "state": "active"}, mode="active_delivery")
        self.assertEqual("none", plan_transition(active)["action"])
        finalizing = status(result={"id": "af-exec", "state": "active"}, mode="mayor_finalization")
        self.assertEqual("finalize:af-exec", plan_transition(finalizing)["wake_key"])
        materialized = status(result={"id": "af-exec", "state": "materialized"}, mode="materialized_without_agent")
        self.assertEqual("resume:af-exec", plan_transition(materialized)["wake_key"])

    def test_activation_is_guarded_and_requires_materialized_campaign(self):
        self.write_state({"gc.current_jit": "none", "gc.needs_benjamin": "none"})
        denied = self.invoke("activate", "af-cm1l", "af-hho5", check=False)
        self.assertNotEqual(0, denied.returncode)
        self.invoke("activate", "af-cm1l", "af-hho5", "--mayor")
        value = self.current_metadata()
        self.assertEqual(("automatic", "active", "af-cm1l"), (
            value["gc.campaign_mode"], value["gc.campaign_state"], value["gc.campaign_candidate"],
        ))

    def test_restart_idempotency_and_pending_recovery(self):
        self.invoke("sentinel")
        self.invoke("sentinel")
        self.assertEqual(1, self.mail_count())
        value = self.current_metadata()
        self.assertEqual(("materialize:af-next", "sent"), (
            value["gc.campaign_wake_key"], value["gc.campaign_wake_state"],
        ))

        value["gc.campaign_wake_state"] = "pending"
        self.write_state(value)
        self.invoke("sentinel")
        self.assertEqual(2, self.mail_count())
        self.assertEqual("sent", self.current_metadata()["gc.campaign_wake_state"])
        calls = self.log_file.read_text(encoding="utf-8")
        for forbidden in ("bd create", "product-queue materialize", "sling", "gh pr", "bd close"):
            self.assertNotIn(forbidden, calls)

    def test_three_failures_persist_durable_block_with_exact_recovery(self):
        for expected in (1, 2, 3):
            result = self.invoke("sentinel", check=False, extra_env={"CAMPAIGN_STATUS_FAIL": "1"})
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(str(expected), self.current_metadata()["gc.campaign_failure_count"])
        value = self.current_metadata()
        self.assertEqual(("blocked", "durable_failure", "Mayor"), (
            value["gc.campaign_state"], value["gc.campaign_block_kind"], value["gc.campaign_owner"],
        ))
        self.assertIn("mayor-campaign resume --mayor", value["gc.campaign_action"])
        noop = self.invoke("sentinel")
        self.assertIn("campaign blocked", noop.stdout)

    def test_block_resume_and_complete_lifecycle_are_mayor_guarded(self):
        self.invoke(
            "block", "--kind", "admin", "--cause", "Rotation ADMIN requise",
            "--owner", "Benjamin", "--action", "Autoriser précisément la rotation", "--mayor",
        )
        self.assertEqual("blocked", self.current_metadata()["gc.campaign_state"])
        self.invoke("resume", "--mayor")
        self.assertEqual("active", self.current_metadata()["gc.campaign_state"])
        self.write_status(status(next_id=None, mode="no_candidate"))
        self.invoke("complete", "--mayor")
        self.assertEqual("completed", self.current_metadata()["gc.campaign_state"])
        completed = status(next_id=None, mode="no_candidate")
        completed["campaign"]["state"] = "completed"
        self.write_status(completed)
        self.assertIn("campaign_complete", self.invoke("sentinel").stdout)
        self.assertEqual(0, self.mail_count())


if __name__ == "__main__":
    unittest.main()
