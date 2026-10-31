#!/usr/bin/env python3
"""Criterion test of the request contract at the doors that write a request
(T59, af-qjq1t6; Spec af-2zseit, user story 78).

Each door is driven through its public command -- `bin/escalation-door
benjamin`, `bin/proposal-door create`, `bin/ticket-graph-publish bd-patch
--reslice` -- with a complete request, then with an incomplete one, and the
source is read after each command: one fake tracker store, the JSON file
the fake `bd` of the publication tests serves, which a fake `gc` written
here serves too, so the three doors write to the same place.

An incomplete request is one the operator cannot act on: an option without
its consequence, or a consequence or an option that says nothing (spaces
only). The publication door composes its options and their consequences
itself; what its producer gives is the reason of the recommended option,
so its incomplete request is a reslice with no reason.

A refusal is explicit when the command exits non-zero and says, on its
error output, which field is missing; a refused request is absent when the
store holds no field of it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lib"))
from bounded_process import run as bounded_run  # noqa: E402

FAKE_BD = ROOT / "tests" / "fixtures" / "ticket-graph-publish" / "bd-bead-mode"
PROJECTS = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"
ESCALATION_DOOR = "bin/escalation-door"
PROPOSAL_DOOR = "bin/proposal-door"
GRAPH_PUBLISH = "bin/ticket-graph-publish"

FAKE_GC = textwrap.dedent(f"""\
    #!{sys.executable}
    import os, sys
    args = sys.argv[1:]
    if args[:1] == ["bd"]:
        os.execv({sys.executable!r}, [{sys.executable!r}, {str(FAKE_BD)!r}, *args[1:]])
    if args[:2] == ["mail", "send"]:
        raise SystemExit(0)
    sys.stderr.write("fake gc: no canned response for gc " + " ".join(args) + "\\n")
    raise SystemExit(1)
    """)

FAKE_OPERATOR_CONFIG = "#!/bin/sh\n[ \"$1\" = language ] && echo fr\n"

REQUEST_KEYS = ("gc.needs_benjamin", "gc.escalation_que_faire", "gc.escalation_pourquoi")


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class RequestDoors(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="request-doors-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = self.tmp / "beads.json"
        tools = self.tmp / "tools"
        tools.mkdir()
        for name, body in (("gc", FAKE_GC), ("operator-config", FAKE_OPERATOR_CONFIG)):
            (tools / name).write_text(body, encoding="utf-8")
            (tools / name).chmod(0o755)
        (self.tmp / "repo").mkdir()
        self.env = {
            **os.environ,
            "GC_BIN": str(tools / "gc"),
            "BD_BIN": str(FAKE_BD),
            "OPERATOR_CONFIG_BIN": str(tools / "operator-config"),
            "TICKET_GRAPH_BD_STATE": str(self.store),
            "TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY": "1",
            # The doors' locks belong to this test, never the host's default
            # (bin/ci-run-tests refuses a test that reaches it).
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_LOCK_FILE": str(self.tmp / "proposal-door.lock"),
        }
        self.seed()

    def seed(self) -> None:
        """A request bead for the escalation door, and a graph whose ticket
        T1 a reslice draft would give other acceptance criteria."""
        old = "sha256:" + "1" * 64
        draft = (
            "global_execution_contract:\n  models: none\n\n"
            "tickets:\n"
            "  - id: T1\n"
            "    title: One ticket\n"
            "    blocked_by: []\n"
            "    target_rigs: [fixture_city]\n"
            "    what_it_delivers: does a thing\n"
            "    acceptance_criteria: [does a different thing]\n"
        )
        beads = {
            "af-req": {"id": "af-req", "title": "", "description": "", "status": "open", "labels": [], "metadata": {}},
            "draft-1": {
                "id": "draft-1", "title": "Draft", "description": draft, "status": "open", "labels": [],
                "metadata": {
                    "spec_id": "spec-1", "approved_by": "benjamin", "approved_digest": digest(draft),
                    "approved_evidence": "Benjamin's exact words", "display_title": "Effort d'exemple",
                    "language": "fr", "revises_digest": old,
                },
            },
            "spec-1": {
                "id": "spec-1", "title": "Spec", "description": "prose", "status": "open", "labels": [],
                "metadata": {"planning_run_target": "A6b", "spec_state": "APPROVED_SPEC",
                             "approved_digest": digest("prose"), "gc.project_id": "acme"},
            },
            "af-conv": {"id": "af-conv", "title": "", "description": "", "status": "open", "labels": [],
                        "metadata": {"gc.graph_digest": old}},
            "af-t1": {"id": "af-t1", "title": "", "status": "open", "labels": [],
                      "description": "## Acceptance criteria\n\n- [ ] does the thing\n",
                      "metadata": {"gc.graph_digest": old, "gc.ticket_id": "T1", "gc.blocked_by": ""}},
        }
        self.store.write_text(json.dumps({"beads": beads, "next_id": 1}), encoding="utf-8")

    def run_door(self, *argv: str) -> subprocess.CompletedProcess:
        return bounded_run([str(ROOT / argv[0]), *argv[1:]], cwd=ROOT, env=self.env,
                           text=True, capture_output=True, timeout=120)

    def source(self) -> dict:
        return json.loads(self.store.read_text(encoding="utf-8"))["beads"]

    def metadata(self, bead_id: str) -> dict:
        return self.source()[bead_id].get("metadata") or {}

    def assert_refused(self, proc: subprocess.CompletedProcess, field: str, door: str) -> None:
        self.assertNotEqual(0, proc.returncode, f"{door} accepted an incomplete request: {proc.stdout}")
        self.assertIn(field, proc.stderr, f"{door} refused without naming the missing field « {field} »")

    @staticmethod
    def request(options: list[dict]) -> str:
        return json.dumps({
            "quoi": "La sauvegarde de cette nuit a échoué",
            "pourquoi": "Sans sauvegarde, une panne du disque ferait perdre la journée",
            "que_faire": options, "langue": "fr", "classe": "decision",
        }, ensure_ascii=False)

    COMPLETE = [
        {"option": "Relancer la sauvegarde", "consequence": "Elle reprend dans la minute",
         "recommande": True, "raison": "La cause la plus fréquente est passagère"},
        {"option": "Attendre la prochaine nuit", "consequence": "La journée reste sans sauvegarde"},
    ]
    INCOMPLETE = {
        "conséquence de l'option 1": [{"option": "Relancer la sauvegarde"}],
        "option 1": [{"option": "   ", "consequence": "Elle reprend dans la minute"}],
        "conséquence de l'option 2": [
            {"option": "Relancer la sauvegarde", "consequence": "Elle reprend dans la minute"},
            {"option": "Attendre la prochaine nuit", "consequence": "  "},
        ],
    }

    def test_each_door_records_a_complete_request_and_refuses_an_incomplete_one_explicitly(self) -> None:
        # escalation-door: an incomplete request first, so the bead holds no
        # request field before the complete one is written.
        for field, options in self.INCOMPLETE.items():
            proc = self.run_door(ESCALATION_DOOR, "benjamin", "af-req", self.request(options))
            self.assert_refused(proc, field, ESCALATION_DOOR)
            written = {k: v for k, v in self.metadata("af-req").items() if k in REQUEST_KEYS}
            self.assertEqual({}, written, f"{ESCALATION_DOOR} wrote an incomplete request ({field})")
        proc = self.run_door(ESCALATION_DOOR, "benjamin", "af-req", self.request(self.COMPLETE))
        self.assertEqual(0, proc.returncode, proc.stderr)
        recorded = self.metadata("af-req")
        self.assertEqual("La sauvegarde de cette nuit a échoué", recorded["gc.needs_benjamin"])
        self.assertEqual("Sans sauvegarde, une panne du disque ferait perdre la journée",
                         recorded["gc.escalation_pourquoi"])
        self.assertEqual(
            [("a", "Relancer la sauvegarde", "Elle reprend dans la minute"),
             ("b", "Attendre la prochaine nuit", "La journée reste sans sauvegarde")],
            [(o["lettre"], o["option"], o["consequence"]) for o in json.loads(recorded["gc.escalation_que_faire"])],
        )

        # proposal-door: a refused proposal creates no bead at all.
        before = set(self.source())
        for field, options in self.INCOMPLETE.items():
            proc = self.run_door(PROPOSAL_DOOR, "create", self.request(options))
            self.assert_refused(proc, field, PROPOSAL_DOOR)
            self.assertEqual(before, set(self.source()), f"{PROPOSAL_DOOR} wrote an incomplete proposal ({field})")
        proc = self.run_door(PROPOSAL_DOOR, "create", self.request(self.COMPLETE))
        self.assertEqual(0, proc.returncode, proc.stderr)
        created = [bead_id for bead_id in self.source() if bead_id not in before]
        self.assertEqual(1, len(created), self.source())
        proposal = self.metadata(created[0])
        self.assertEqual("La sauvegarde de cette nuit a échoué", proposal["gc.proposal_quoi"])
        self.assertEqual(
            [("a", "Relancer la sauvegarde", "Elle reprend dans la minute"),
             ("b", "Attendre la prochaine nuit", "La journée reste sans sauvegarde")],
            [(o["lettre"], o["option"], o["consequence"]) for o in json.loads(proposal["gc.proposal_que_faire"])],
        )

        # ticket-graph-publish: the request a refused reslice raises.
        reslice = (GRAPH_PUBLISH, "bd-patch", "draft-1", "--author", "Mayor", "--project", "acme",
                   "--repo-root", str(self.tmp / "repo"), "--config-dir", str(PROJECTS), "--reslice")
        proc = self.run_door(*reslice, "--reason", "  ")
        self.assert_refused(proc, "--reason", GRAPH_PUBLISH)
        written = {k: v for k, v in self.metadata("af-conv").items() if k in REQUEST_KEYS}
        self.assertEqual({}, written, f"{GRAPH_PUBLISH} wrote a request without the reason of its recommendation")
        proc = self.run_door(*reslice, "--reason", "Le découpage débloque la livraison")
        self.assertNotEqual(0, proc.returncode, "the reslice changes acceptance criteria: it is refused")
        recorded = self.metadata("af-conv")
        self.assertTrue(recorded.get("gc.needs_benjamin"), f"{GRAPH_PUBLISH} recorded no request: {proc.stderr}")
        self.assertTrue(recorded.get("gc.escalation_pourquoi"))
        options = json.loads(recorded["gc.escalation_que_faire"])
        self.assertGreaterEqual(len(options), 1)
        self.assertTrue(all(o["option"].strip() and o["consequence"].strip() for o in options), options)
        self.assertEqual(["Le découpage débloque la livraison"],
                         [o["raison"] for o in options if o.get("recommande")])


if __name__ == "__main__":
    unittest.main()
