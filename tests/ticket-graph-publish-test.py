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
PUBLISHER = ROOT / "bin" / "ticket-graph-publish"
FAKE_GC = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "gc"
FAKE_BD_BEAD_MODE = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "bd-bead-mode"
FAKE_ESCALATION_DOOR = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "escalation-door"
PROJECTS_CONFIG_DIR = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"

SKIP_MAYOR_NOTIFY_ENV = "TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY"


class TicketGraphPublishBeadModeTest(unittest.TestCase):
    """W05: bd-publish/bd-patch read the Ticket Graph Draft from a
    planning-plane bead bound to the approved Spec bead, against the live
    Beads/reservation/profile tools."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ticket-graph-publish-bd-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()

    def invoke(self, *args, env=None, check=False):
        full_env = {
            **os.environ,
            SKIP_MAYOR_NOTIFY_ENV: "1",
            "BD_BIN": str(FAKE_BD_BEAD_MODE),
            "TICKET_GRAPH_BD_STATE": str(self.state_path),
            **(env or {}),
        }
        return subprocess.run(
            (str(PUBLISHER), *args), env=full_env, text=True, capture_output=True, check=check,
        )

    def seed(self, beads, next_id=1):
        self.state_path.write_text(json.dumps({"beads": beads, "next_id": next_id}))

    def current_state(self):
        return json.loads(self.state_path.read_text())

    def digest(self, description):
        return "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()

    def draft_description(self, tickets_yaml, contract="  models: none\n"):
        return (
            "global_execution_contract:\n" + contract + "\n"
            "tickets:\n" + tickets_yaml
        )

    ONE_TICKET_YAML = (
        "  - id: T1\n"
        "    title: One ticket\n"
        "    blocked_by: []\n"
        "    target_rigs: [fixture_city]\n"
        "    what_it_delivers: does a thing\n"
        "    acceptance_criteria: [does the thing]\n"
        "    scope:\n"
        "      paths: [bin/foo.py]\n"
    )

    def draft_bead(self, tickets_yaml=ONE_TICKET_YAML, spec_id="spec-1", approved_by="benjamin",
                   approved_evidence="Benjamin's exact words, 2026-09-30 Paris", digest_override=None,
                   revises_digest=None, display_title="Effort d'exemple", language="fr"):
        description = self.draft_description(tickets_yaml)
        metadata = {
            "spec_id": spec_id,
            "approved_by": approved_by,
            "approved_evidence": approved_evidence,
            "approved_digest": digest_override if digest_override is not None else self.digest(description),
        }
        if display_title is not None:
            metadata["display_title"] = display_title
        if language is not None:
            metadata["language"] = language
        if revises_digest:
            metadata["revises_digest"] = revises_digest
        return {
            "id": "draft-1", "title": "Draft", "description": description,
            "status": "open", "labels": [], "metadata": metadata,
        }

    def spec_bead(self, description="prose spec body", target="A6b", approved=True, digest_override=None,
                  project_id="acme"):
        metadata = {"planning_run_target": target}
        if approved:
            metadata["spec_state"] = "APPROVED_SPEC"
            metadata["approved_digest"] = digest_override if digest_override is not None else self.digest(description)
        if project_id is not None:
            metadata["gc.project_id"] = project_id
        return {
            "id": "spec-1", "title": "Spec", "description": description,
            "status": "open", "labels": [], "metadata": metadata,
        }

    def bd_publish(self, draft_id="draft-1", project="acme", check=False, env=None):
        return self.invoke(
            "bd-publish", draft_id, "--project", project, "--repo-root", str(self.repo_root),
            "--config-dir", str(PROJECTS_CONFIG_DIR), check=check, env=env,
        )

    def bd_patch(self, draft_id="draft-1", project="acme", author="Test", reason="test patch", check=False, env=None):
        return self.invoke(
            "bd-patch", draft_id, "--author", author, "--reason", reason, "--project", project,
            "--repo-root", str(self.repo_root), "--config-dir", str(PROJECTS_CONFIG_DIR), check=check, env=env,
        )

    def write_reservation(self, reserved_for):
        runtime_path = self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json"
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(json.dumps({
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "cleared_at": None,
        }))

    # --- refusals: nothing created -------------------------------------------

    def test_bd_publish_refuses_when_spec_is_not_approved(self):
        self.seed({"draft-1": self.draft_bead(), "spec-1": self.spec_bead(approved=False)})

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("not approved", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_an_empty_bd_bin_is_not_an_override(self):
        # Gas City 1.5 gives an order BD_BIN set and empty (af-d130xt), and
        # the order convoy-advance reaches this door to publish a repair.
        self.seed({"draft-1": self.draft_bead(), "spec-1": self.spec_bead(approved=False)})
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "bd").symlink_to(FAKE_BD_BEAD_MODE)

        proc = self.bd_patch(env={"BD_BIN": "", "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("not approved", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_bd_publish_refuses_when_spec_digest_differs_from_approved(self):
        spec = self.spec_bead()
        self.seed({"draft-1": self.draft_bead(), "spec-1": spec})
        state = self.current_state()
        state["beads"]["spec-1"]["description"] = "edited after approval"
        self.state_path.write_text(json.dumps(state))

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("digest differs from its approved digest", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_bd_publish_refuses_when_approver_is_not_declared_human_approver(self):
        self.seed({
            "draft-1": self.draft_bead(approved_by="someone-else"), "spec-1": self.spec_bead(),
        })

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("declared", proc.stderr)
        self.assertIn("human approver", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_bd_publish_refuses_when_approval_evidence_is_empty(self):
        self.seed({
            "draft-1": self.draft_bead(approved_evidence=""), "spec-1": self.spec_bead(),
        })

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("no approval evidence", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_bd_publish_refuses_when_tickets_changed_after_approval(self):
        draft = self.draft_bead()
        self.seed({"draft-1": draft, "spec-1": self.spec_bead()})
        state = self.current_state()
        state["beads"]["draft-1"]["description"] += "\n# edited after approval\n"
        self.state_path.write_text(json.dumps(state))

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("changed after approval", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    def test_bd_publish_refuses_when_a_ticket_has_no_target_rig(self):
        no_rig_ticket = (
            "  - id: T1\n"
            "    title: One ticket\n"
            "    blocked_by: []\n"
            "    target_rigs: []\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does the thing]\n"
        )
        self.seed({
            "draft-1": self.draft_bead(tickets_yaml=no_rig_ticket), "spec-1": self.spec_bead(),
        })

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("no target rigs", proc.stderr)
        self.assertEqual({"draft-1", "spec-1"}, set(self.current_state()["beads"]))

    PROTOTYPE_TICKET_YAML = (
        "  - id: T1\n"
        "    kind: prototype\n"
        "    title: Try two layouts\n"
        "    blocked_by: []\n"
        "    target_rigs: [fixture_city]\n"
        "    what_it_delivers: a throwaway prototype\n"
        "    acceptance_criteria: [Benjamin picks a variant]\n"
    )

    def test_bd_publish_refuses_a_prototype_ticket_before_any_write(self):
        # Benjamin, 2026-09-30: a prototype is planning work, done by the
        # Planning Run (wayfinder:prototype map ticket), never by a worker.
        prototype_t2 = self.PROTOTYPE_TICKET_YAML.replace("T1", "T2")
        self.seed({
            "draft-1": self.draft_bead(tickets_yaml=self.ONE_TICKET_YAML + prototype_t2),
            "spec-1": self.spec_bead(),
        })
        before = self.current_state()

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("T2 declare kind: prototype", proc.stderr)
        self.assertIn("wayfinder:prototype", proc.stderr)
        self.assertEqual(before, self.current_state())

    # --- T05: display title, language, project key -----------------------

    def test_bd_publish_refuses_a_draft_with_no_display_title(self):
        self.seed({
            "draft-1": self.draft_bead(display_title=""), "spec-1": self.spec_bead(),
        })
        before = self.current_state()

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("display_title", proc.stderr)
        self.assertEqual(before, self.current_state())

    def test_bd_publish_refuses_a_draft_whose_declared_language_is_not_the_operator_language(self):
        self.seed({
            "draft-1": self.draft_bead(language="en"), "spec-1": self.spec_bead(),
        })
        before = self.current_state()

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("language", proc.stderr)
        self.assertEqual(before, self.current_state())

    def test_bd_publish_refuses_a_draft_whose_spec_has_no_project_key(self):
        self.seed({
            "draft-1": self.draft_bead(), "spec-1": self.spec_bead(project_id=None),
        })
        before = self.current_state()

        proc = self.bd_publish()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("project key", proc.stderr)
        self.assertEqual(before, self.current_state())

    def test_bd_publish_convoy_carries_the_project_key_and_display_title(self):
        self.seed({
            "draft-1": self.draft_bead(display_title="Effort d'exemple"),
            "spec-1": self.spec_bead(project_id="acme-project"),
        })

        result = json.loads(self.bd_publish(check=True).stdout)
        self.assertTrue(result["ok"])

        state = self.current_state()
        convoy = next(
            b for b in state["beads"].values()
            if b["metadata"].get("gc.plane") == "delivery" and "gc.ticket_id" not in b["metadata"]
        )
        self.assertEqual("acme-project", convoy["metadata"]["gc.project_id"])
        self.assertEqual("Effort d'exemple", convoy["title"])

    # --- nominal --------------------------------------------------------------

    def test_derived_authority_is_transmitted_and_publication_stays_idempotent(self):
        # The lower door proves the source/fidelity refusals. Here prove
        # transmission through the real publication command only.
        spec, draft = self.spec_bead(), self.draft_bead(approved_by="author")
        for bead in (spec, draft):
            bead["metadata"].update(approval_mode="derived/v1", derived_authorization="seal", **{"gc.project_id": "acme"})
        self.seed({"draft-1": draft, "spec-1": spec})
        helper = self.tmp / "derivation"
        helper.write_text("#!/usr/bin/env python3\nimport json,os,sys,hashlib\n"
            "artifact=sys.argv[sys.argv.index('--artifact')+1]\n"
            "state=json.load(open(os.environ['TICKET_GRAPH_BD_STATE']))\n"
            "body=state['beads'][artifact]['description']\n"
            "print(json.dumps({'ok':True,'kind':'spec' if artifact=='spec-1' else 'graph',"
            "'digest':'sha256:'+hashlib.sha256(body.encode()).hexdigest(),'project':'acme',"
            "'authorization':'seal','delegated_by':'benjamin','derived_by':'author'}))\n")
        helper.chmod(0o755)
        env = {"PLANNING_DELEGATION_BIN": str(helper)}
        first = json.loads(self.bd_publish(env=env, check=True).stdout)
        second = json.loads(self.bd_publish(env=env, check=True).stdout)
        self.assertEqual(first["ids"], second["ids"])
        self.assertEqual(4, len(self.current_state()["beads"]))

    def test_derived_source_refusal_stops_publication_before_writes(self):
        spec = self.spec_bead()
        spec["metadata"].update(approval_mode="derived/v1", derived_authorization="seal")
        self.seed({"draft-1": self.draft_bead(), "spec-1": spec})
        before = self.current_state()
        helper = self.tmp / "derivation"
        helper.write_text('#!/usr/bin/env python3\nprint(\'{"ok":false,"error":"source changed"}\')\nraise SystemExit(1)\n')
        helper.chmod(0o755)
        proc = self.bd_publish(env={"PLANNING_DELEGATION_BIN": str(helper)})
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("source changed", proc.stderr)
        self.assertEqual(before, self.current_state())

    def test_bd_publish_creates_delivery_beads_and_convoy_advances_reservation_and_wakes_mayor(self):
        two_tickets = (
            "  - id: T1\n"
            "    title: First\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does the thing]\n"
            "    scope:\n"
            "      paths: [bin/foo.py]\n"
            "  - id: T2\n"
            "    title: Second\n"
            "    blocked_by: [T1]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does another thing\n"
            "    acceptance_criteria: [does the other thing]\n"
        )
        self.seed({
            "draft-1": self.draft_bead(tickets_yaml=two_tickets), "spec-1": self.spec_bead(target="A6b"),
        })
        self.write_reservation(reserved_for="A6b")

        gc_log = self.tmp / "gc.log"
        result = json.loads(self.bd_publish(check=True, env={
            SKIP_MAYOR_NOTIFY_ENV: "",
            "GC_BIN": str(FAKE_GC),
            "TICKET_GRAPH_GC_LOG": str(gc_log),
        }).stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(3, len(result["ids"]))  # _convoy, T1, T2
        self.assertIs(True, result["mayor_notified"])
        self.assertEqual("cleared", result["reservation_advanced"]["result"])

        state = self.current_state()
        delivery = [b for b in state["beads"].values() if b["id"] not in ("draft-1", "spec-1")]
        self.assertEqual(3, len(delivery))
        convoy = next(b for b in delivery if b["metadata"].get("gc.plane") == "delivery" and "gc.ticket_id" not in b["metadata"])
        tickets_created = [b for b in delivery if b is not convoy]
        self.assertEqual(2, len(tickets_created))
        t2 = next(b for b in tickets_created if b["metadata"]["gc.ticket_id"] == "T2")
        self.assertEqual("T1", t2["metadata"]["gc.blocked_by"])
        t1 = next(b for b in tickets_created if b["metadata"]["gc.ticket_id"] == "T1")
        self.assertEqual("bin/foo.py", t1["metadata"]["gc.scope_paths"])

        reservation_after = json.loads(
            (self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json").read_text()
        )
        self.assertIsNotNone(reservation_after["cleared_at"])

    def test_bd_publish_accepts_a_spec_claimed_by_a_to_tickets_session(self):
        # Spec handoff (docs/agents/issue-tracker.md): the Spec offered for
        # /to-tickets stays claimed -- in_progress, assigned, maybe still
        # carrying wayfinder.offered_by -- when its draft is published.
        spec = self.spec_bead(target="A6b")
        spec["status"] = "in_progress"
        spec["assignee"] = "po-agent/zz-fixture-session"
        spec["metadata"]["wayfinder.offered_by"] = "po-agent/zz-fixture-offerer"
        self.seed({"draft-1": self.draft_bead(), "spec-1": spec})
        self.write_reservation(reserved_for="A6b")

        result = json.loads(self.bd_publish(check=True).stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(result["ids"]))  # _convoy, T1
        state = self.current_state()
        self.assertEqual("in_progress", state["beads"]["spec-1"]["status"])
        self.assertEqual("po-agent/zz-fixture-session", state["beads"]["spec-1"]["assignee"])

    def test_bd_publish_does_not_advance_a_reservation_for_a_different_target(self):
        self.seed({"draft-1": self.draft_bead(), "spec-1": self.spec_bead(target="A6b")})
        self.write_reservation(reserved_for="C01")

        result = json.loads(self.bd_publish(check=True).stdout)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["reservation_advanced"])

        reservation_after = json.loads(
            (self.repo_root / ".gc" / "runtime" / "planning-run-reservation.json").read_text()
        )
        self.assertIsNone(reservation_after["cleared_at"])
        self.assertEqual("C01", reservation_after["reserved_for"])

    # --- patch: reads its draft from the bead, keeps current rules ------------

    def test_bd_patch_reads_its_draft_from_the_bead_and_keeps_its_current_rules(self):
        old_digest = "sha256:" + "1" * 64
        self.seed({
            "draft-1": self.draft_bead(revises_digest=old_digest),
            "spec-1": self.spec_bead(),
            "af-conv": {
                "id": "af-conv", "status": "open", "labels": [], "title": "", "description": "",
                "metadata": {"gc.graph_digest": old_digest},
            },
            "af-t1": {
                "id": "af-t1", "status": "open", "labels": [], "title": "", "description": "",
                "metadata": {"gc.graph_digest": old_digest, "gc.ticket_id": "T1", "gc.blocked_by": ""},
            },
        })

        result = json.loads(self.bd_patch(check=True).stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(["T1"], result["patched"])
        self.assertEqual("af-t1", result["ids"]["T1"])
        self.assertEqual("af-conv", result["ids"]["_convoy"])

        state = self.current_state()
        self.assertIn("does a thing", state["beads"]["af-t1"]["description"])

    def test_bd_patch_added_ticket_waits_for_its_blocker(self):
        # T48: on the tracker, the ticket a patch adds waits for the ticket
        # that blocks it -- never the other way round.
        self.seed_patch(self.ONE_TICKET_YAML + (
            "  - id: T2\n"
            "    title: A ticket added behind the first\n"
            "    blocked_by: [T1]\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does another thing\n"
            "    acceptance_criteria: [does the other thing]\n"
            "    scope:\n"
            "      paths: [bin/bar.py]\n"
        ))

        result = json.loads(self.bd_patch(check=True).stdout)
        self.assertEqual(["T2"], result["created"])
        added = result["ids"]["T2"]
        self.assertEqual("T1", self.current_state()["beads"][added]["metadata"]["gc.blocked_by"])
        self.assertEqual(["af-t1"], self.waits_for(added))
        self.assertEqual([], self.waits_for("af-t1"))

    def waits_for(self, bead_id):
        """The beads this one waits for, as the tracker shows them."""
        proc = subprocess.run(
            (str(FAKE_BD_BEAD_MODE), "show", bead_id, "--json"),
            env={**os.environ, "TICKET_GRAPH_BD_STATE": str(self.state_path)}, text=True, capture_output=True, check=True,
        )
        return sorted(dep["id"] for dep in json.loads(proc.stdout)[0].get("dependencies", [])
                      if dep["dependency_type"] == "blocks")

    def seed_patch(self, tickets_yaml):
        old_digest = "sha256:" + "1" * 64
        self.seed({
            "draft-1": self.draft_bead(tickets_yaml=tickets_yaml, revises_digest=old_digest),
            "spec-1": self.spec_bead(),
            "af-conv": {
                "id": "af-conv", "status": "open", "labels": [], "title": "", "description": "",
                "metadata": {"gc.graph_digest": old_digest},
            },
            "af-t1": {
                "id": "af-t1", "status": "open", "labels": [], "title": "", "description": "",
                "metadata": {"gc.graph_digest": old_digest, "gc.ticket_id": "T1", "gc.blocked_by": ""},
            },
        })

    def test_bd_patch_refuses_a_new_prototype_ticket_before_any_write(self):
        self.seed_patch(self.ONE_TICKET_YAML + self.PROTOTYPE_TICKET_YAML.replace("T1", "T2"))
        before = self.current_state()

        proc = self.bd_patch()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("T2 declare kind: prototype", proc.stderr)
        self.assertEqual(before, self.current_state())

    def test_bd_patch_keeps_a_prototype_ticket_already_published(self):
        # A graph published before the rule (C01's T21) stays patchable.
        self.seed_patch(self.PROTOTYPE_TICKET_YAML)

        result = json.loads(self.bd_patch(check=True).stdout)
        self.assertEqual(["T1"], result["patched"])
        self.assertEqual([], result["created"])

    def test_bd_patch_reslice_refusal_escalates_with_quoi_pourquoi_and_consequential_options(self):
        # T05: escalation-door benjamin now refuses anything but a JSON
        # object carrying quoi/pourquoi/que_faire (options with
        # consequence) and langue -- a reslice refusal must speak that
        # contract, not a bare reason string.
        old_digest = "sha256:" + "1" * 64
        changed_ac = (
            "  - id: T1\n"
            "    title: One ticket\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does a different thing]\n"
        )
        self.seed({
            "draft-1": self.draft_bead(tickets_yaml=changed_ac, revises_digest=old_digest),
            "spec-1": self.spec_bead(),
            "af-conv": {
                "id": "af-conv", "status": "open", "labels": [], "title": "", "description": "",
                "metadata": {"gc.graph_digest": old_digest},
            },
            "af-t1": {
                "id": "af-t1", "status": "open", "labels": [], "title": "",
                "description": "## Acceptance criteria\n\n- [ ] does the thing\n",
                "metadata": {"gc.graph_digest": old_digest, "gc.ticket_id": "T1", "gc.blocked_by": ""},
            },
        })
        escalation_log = self.tmp / "escalation.json"

        proc = self.invoke(
            "bd-patch", "draft-1", "--author", "Mayor", "--reason", "reslice to unblock delivery",
            "--project", "acme", "--repo-root", str(self.repo_root),
            "--config-dir", str(PROJECTS_CONFIG_DIR), "--reslice",
            env={"ESCALATION_DOOR_BIN": str(FAKE_ESCALATION_DOOR), "ESCALATION_DOOR_LOG": str(escalation_log)},
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("refused and escalated", proc.stderr)

        entries = json.loads(escalation_log.read_text())
        self.assertEqual(1, len(entries))
        self.assertEqual("af-conv", entries[0]["bead"])
        payload = entries[0]["payload"]
        self.assertTrue(payload["quoi"])
        self.assertTrue(payload["pourquoi"])
        self.assertEqual("fr", payload["langue"])
        self.assertGreaterEqual(len(payload["que_faire"]), 1)
        for option in payload["que_faire"]:
            self.assertTrue(option["option"])
            self.assertTrue(option["consequence"])

    def test_bd_patch_refuses_without_revises_digest(self):
        self.seed({
            "draft-1": self.draft_bead(revises_digest=None), "spec-1": self.spec_bead(),
        })

        proc = self.bd_patch()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("revises_digest", proc.stderr)


if __name__ == "__main__":
    unittest.main()
