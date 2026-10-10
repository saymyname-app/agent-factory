#!/usr/bin/env python3
"""bin/ticket-exit on a fake tracker state (T11, af-egkabn; Spec af-wf4w5r
§5, Testing Decisions seam 2): one test per refusal and per pass, each
refusal re-reading the tracker and the evidence store to prove nothing was
written. Only command lines are exercised. The ticket branch lives in a
throwaway repository that holds a copy of the Delivery Fixture City; the
records of a Handoff are sealed for real by bin/evidence-capture, the
requests go through the real bin/escalation-door, and the `repair` of a
ticket blocked technically is published by the real patch door
(bin/ticket-graph-publish) on the graph of the Fixture City."""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "ticket-exit"
STATE_TOOL = ROOT / "bin" / "convoy-state"
ADVANCE_TOOL = ROOT / "bin" / "convoy-advance"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
LAUNCH_TOOL = ROOT / "bin" / "project-launch"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"

CONVOY, SPEC = "fx-convoy", "fx-spec"
# The graph of the Fixture City: T2 waits for T1, T3 for T2; T4 waits for nothing.
T1, T2, T3, T4 = "fx-t1", "fx-t2", "fx-t3", "fx-t4"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
BRANCH = "ticket/fx-t2"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4

APP = f"{FIXTURE}/app.py"
TEST_FILE = f"{FIXTURE}/tests/test_list.py"
README = "README.md"
RED_DIGEST = "sha256:" + "ab" * 32

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE")

COMPLETE = {
    "done": ["Critère 1 : la région « liste » affiche Alpha, Bêta, Gamma ; voir GET / sur le jeu « contenu »."],
    "deviations": "aucun",
    "not_done": "aucun",
    "out_of_ticket": ["Le chargeur relit le fichier à chaque requête."],
}


def description(rig="fx-rig"):
    return (
        "## What to build\n\nLa liste des éléments.\n\n## Acceptance criteria\n\n"
        "- [ ] Point d'entrée : GET / — Observable : région liste — Faux si : une ligne manque\n\n"
        f"## Target rigs\n\n{rig}"
    )


class TicketExitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ticket-exit-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.origin = self.tmp / "origin.git"
        self.root = self.tmp / "root"
        (self.root / "config" / "projects").mkdir(parents=True)
        (self.root / "config" / "projects" / "fx-rig.toml").write_text(
            'rig_dir = "."\nrepo = "example/fx"\nprotected_branch = "main"\nrequired_ci = "CI"\n'
            'sling_target = "fx-worker"\nformulas = "fx-start"\n')
        shutil.copy(ROOT / "config" / "delivery-roles.json", self.root / "config" / "delivery-roles.json")
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 5,
            "start": {"formula": "fx-start", "role": None}}))
        stubs = {"provider-failover": "printf '{}\\n'", "proposal-door": "echo 0"}
        for name, body in stubs.items():
            (self.tmp / name).write_text(f"#!/bin/sh\n{body}\n")
            (self.tmp / name).chmod(0o755)
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "CONVOY_ADVANCE_LOCK_DIR": str(self.tmp / "locks"),
            "DISPATCH_DOOR_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
            "DISPATCH_DOOR_MEMINFO_FILE": str(self.tmp / "no-meminfo"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.store),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        # As an author's tool call would run, but never as this suite's own session.
        for name in ("CONVOY_STATE_FAKE_SLING_FAIL", "CONVOY_STATE_FAKE_MAIL_FAIL", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.seed_tracker()
        self.seed_repo()

    # --- harness ------------------------------------------------------------

    def seed_tracker(self):
        """The graph of the Fixture City in a marked convoy, T2 started
        through the dispatch door on its branch; and a convoy without the
        mark."""
        def ticket(kind, blocks=(), scope=None):
            metadata = {"gc.ticket_kind": kind}
            if scope:
                metadata["gc.scope_paths"] = scope
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": description(), "metadata": metadata, "blocks": list(blocks)}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [T1, T2, T3, T4]},
            T1: ticket("prefactoring"),
            T2: ticket("vertical_slice", blocks=[T1], scope=f"{FIXTURE}/tests/*,{APP}"),
            T3: ticket("repair", blocks=[T2]),
            T4: ticket("vertical_slice"),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state(
            "mark", CONVOY,
            "--demonstration-line", f"{T2}=La page d'accueil affiche les trois éléments",
            "--demonstration-line", f"{T3}=L'API rend de nouveau le champ label",
            "--demonstration-line", f"{T4}=GET /health répond 200",
            "--user-stories", f"{T2}=1,2", "--user-stories", f"{T4}=3")
        self.close_through_gate(T1)
        self.state("record-gate", CONVOY, T2, "--gate", "dispatch")
        self.state("set-branch", CONVOY, T2, "--branch", BRANCH)
        self.edit(T2, status="in_progress")

    def seed_repo(self):
        """The product, its remote, and the branch of T2 with the red step
        proven at its first commit (the criterion tests)."""
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE)
        self.git("init", "-q", "-b", "main")
        self.base = self.commit("base")
        subprocess.run(("git", "init", "-q", "--bare", str(self.origin)), env=self.env, check=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("checkout", "-q", "-b", BRANCH)
        self.red = self.commit("tests de critère", {TEST_FILE: "# les tests de critère\n"})
        self.state("add-evidence", CONVOY, T2, "--piece", "tdd_red", "--digest", RED_DIGEST, "--commit", self.red)
        self.state("set-tdd", CONVOY, T2, "--step", "red", "--commit", self.red, "--base", self.base)
        self.write_log.write_text("")

    def git(self, *args):
        return subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, message, files=None):
        for path, content in (files or {}).items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def code(self, extra="", demonstrated=True, ticket=T2):
        """The code of T2: the product, and a file outside its Declared
        Scope; then, as its author does before leaving, the proof of the
        demonstration line on the product launched at that commit."""
        app = (self.repo / APP).read_text()
        head = self.commit("la liste des éléments", {APP: app + "\n# la liste des éléments\n" + extra,
                                                     README: "Le produit de la fixture.\n"})
        if demonstrated:
            self.demonstrate(ticket)
        return head

    def demonstrate(self, ticket=T2):
        """The piece `demonstration`, captured for real on the product
        launched for real at HEAD."""
        launch = self.tmp / "launch.json"
        proc = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", ROOT / FIXTURE / "descriptor.json",
                            "--commit", self.git("rev-parse", "HEAD"), "--dataset", "content", "--state-file", launch)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        try:
            address = json.loads(launch.read_text())["address"]
            proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, ticket, "--piece", "demonstration",
                                "--launch-state", launch, "--", "curl", "-sf", address + "/")
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        finally:
            self.run_cmd(LAUNCH_TOOL, "stop", "--state-file", launch)
        self.write_log.write_text("")

    def run_cmd(self, tool, *args):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket_id=T2, expect=0):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket_id)

    def edit(self, bead_id=None, status=None, sessions=None, **fields):
        state = json.loads(self.tracker.read_text())
        if bead_id is not None:
            if status is not None:
                state["beads"][bead_id]["status"] = status
            state["beads"][bead_id].update(fields)
        if sessions is not None:
            state["sessions"] = list(sessions)
        self.tracker.write_text(json.dumps(state))

    def close_through_gate(self, ticket_id):
        """What stands for the flow's own ticket end (T19, bin/ticket-end):
        the record of the gate, written with the closing."""
        self.state("close-ticket", CONVOY, ticket_id, "--commit", "0" * 40, "--file", GATE_REPORT)

    def file(self, name, content):
        path = self.tmp / name
        path.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
        return path

    def handoff(self, **changes):
        """The Handoff of the author: the complete one, with some sections
        changed, or left out (None)."""
        sections = {**COMPLETE, **changes}
        return self.file("handoff.json", {name: value for name, value in sections.items() if value is not None})

    def exit(self, *args, ticket=T2, convoy=CONVOY):
        return self.run_cmd(TOOL, "exit", convoy, ticket, *args)

    def exited(self, *args, ticket=T2):
        proc = self.exit(*args, ticket=ticket)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def raise_exception(self, *args, **changes):
        """The exit « Planning Exception », with the Handoff it comes after:
        the complete one, with some sections changed."""
        return self.exited("--exit", "planning_exception", "--repo", self.repo, "--handoff", self.handoff(**changes),
                           *args)

    def finish(self, handoff=None):
        return self.exit("--exit", "finished", "--repo", self.repo, *(("--handoff", handoff) if handoff else ()))

    def store_files(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*") if p.is_file() and p.name != ".seal-key")

    def remote_tip(self):
        proc = subprocess.run(("git", "--git-dir", str(self.origin), "rev-parse", "--verify", "--quiet", BRANCH),
                              env=self.env, text=True, capture_output=True)
        return proc.stdout.strip() or None

    def assert_refused_and_nothing_written(self, proc_factory, *mentions, status=EXIT_REFUSED):
        """The call is refused, and the state of the ticket read again is
        what it was: the tracker, the evidence store and the remote."""
        before = (self.tracker.read_bytes(), self.shown(), self.store_files(), self.remote_tip(),
                  self.write_log.read_text())
        proc = proc_factory()
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        if status == EXIT_REFUSED:
            answer = json.loads(proc.stdout)
            self.assertFalse(answer["ok"])
            self.assertNotIn("written", answer)
            for mention in mentions:
                self.assertIn(mention, answer["error"])
        self.assertEqual(before, (self.tracker.read_bytes(), self.shown(), self.store_files(), self.remote_tip(),
                                  self.write_log.read_text()))
        return proc

    def escalation_list(self):
        proc = self.run_cmd(ESCALATION_TOOL, "list")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        needs = proc.stdout.split("Pending proposals")[0].splitlines()[1:]
        return [line.strip() for line in needs if line.strip() and "(none)" not in line]

    def advance(self):
        proc = self.run_cmd(ADVANCE_TOOL, CONVOY)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(c for c in json.loads(proc.stdout)["convoys"] if c["id"] == CONVOY)

    def started_by_code(self):
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [entry[2] for entry in lines if entry[0] == "sling"]

    # --- AC1: « terminé » needs a valid Ticket Handoff ------------------------

    def test_finished_is_refused_without_a_handoff(self):
        # Demonstration line of the ticket, first part.
        self.code()
        self.assert_refused_and_nothing_written(self.finish, "sans Ticket Handoff")
        self.assertIsNone(self.shown()["exit"])

    def test_finished_is_refused_when_a_section_is_left_out(self):
        self.code()
        for name, label in (("done", "Fait"), ("deviations", "Écarts"), ("not_done", "Non fait"),
                            ("out_of_ticket", "Constats hors ticket")):
            with self.subTest(section=name):
                self.assert_refused_and_nothing_written(
                    lambda: self.finish(self.handoff(**{name: None})), label, "ni contenu ni « aucun »")

    def test_finished_is_refused_when_a_section_is_empty(self):
        self.code()
        for empty in ([], "", [""], ["deux\nlignes"]):
            with self.subTest(value=empty):
                self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff(deviations=empty)), "Écarts")

    def test_finished_is_refused_when_the_handoff_is_not_readable(self):
        self.code()
        self.assert_refused_and_nothing_written(lambda: self.finish(self.file("handoff.json", "pas du JSON")), "illisible")
        self.assert_refused_and_nothing_written(lambda: self.finish(self.tmp / "absent.json"), "illisible")

    def test_finished_with_a_valid_handoff_is_recorded_in_the_tracker(self):
        head = self.code()

        answer = self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())

        ticket = self.shown()
        self.assertEqual("finished", ticket["exit"]["exit"])
        handoff = ticket["handoff"]
        self.assertEqual(handoff, {**answer["handoff"], "at": handoff["at"]})
        self.assertFalse(handoff["partial"])
        self.assertEqual(head, handoff["commit"])
        self.assertEqual(COMPLETE, handoff["sections"])
        self.assertEqual("aucun", handoff["sections"]["deviations"])

    def test_finished_is_refused_on_a_stopped_ticket(self):
        self.code()
        self.state("stop-ticket", CONVOY, T2, "--reason", "criterion_already_green", "--detail", "critère 1 déjà vert")
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "arrêté")

    def test_finished_is_refused_while_work_is_not_committed(self):
        self.code()
        (self.repo / APP).write_text("# en cours\n")
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "diffèrent de HEAD")

    def test_finished_is_refused_on_another_branch_than_the_ticket_s(self):
        self.code()
        self.git("checkout", "-q", "-b", "ailleurs")
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "n'est pas celle du ticket")

    # --- AC5: the records are written by code ---------------------------------

    def test_records_list_commits_files_outside_scope_and_the_red_proof(self):
        head = self.code()

        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())

        records = self.shown()["handoff"]["records"]
        self.assertEqual([self.red, head], [entry["commit"] for entry in records["commits"]])
        self.assertEqual(["tests de critère", "la liste des éléments"], [entry["subject"] for entry in records["commits"]])
        self.assertEqual(sorted([README, APP, TEST_FILE]), sorted(records["files_changed"]))
        # README.md is outside the Declared Scope; touching it stops nothing.
        self.assertEqual([README], records["files_outside_declared_scope"])
        self.assertEqual({"step": "red", "piece": "tdd_red", "digest": RED_DIGEST, "commit": self.red,
                          "base": self.base}, records["red_proof"])
        self.assertEqual([], records["deferral_markers"])
        self.assertEqual((self.base, head, BRANCH), (records["base"], records["head"], records["branch"]))

    def test_records_are_a_sealed_piece_of_the_evidence_store(self):
        head = self.code()
        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())

        ticket = self.shown()
        self.assertEqual(head, ticket["evidence"]["handoff_records"]["commit"])
        proc = self.run_cmd(CAPTURE_TOOL, "verify", CONVOY, T2, "--piece", "handoff_records")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        piece = json.loads((self.store / SPEC / T2 / "handoff_records.json").read_text())
        self.assertEqual(ticket["handoff"]["records"], json.loads(piece["output"]))

    def test_the_author_cannot_give_the_records(self):
        self.code()
        forged = {"commits": [], "files_outside_declared_scope": [], "deferral_markers": []}
        for field in ("records", "relevés", "commits"):
            with self.subTest(field=field):
                given = self.file("handoff.json", {**COMPLETE, field: forged})
                self.assert_refused_and_nothing_written(
                    lambda: self.finish(given), field, "l'auteur ne les fournit pas")

    def test_no_option_carries_the_records(self):
        self.code()
        records = self.file("records.json", {"commits": []})
        for option in ("--records", "--commits", "--red-proof"):
            with self.subTest(option=option):
                self.assert_refused_and_nothing_written(
                    lambda: self.exit("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff(),
                                      option, records), status=2)

    def test_a_handoff_written_past_the_tool_needs_the_sealed_records(self):
        # The state command takes the records only with the piece the tool sealed.
        head = self.code()
        forged = self.file("forged.json", {"sections": COMPLETE, "partial": False, "commit": head,
                                           "records": {"commits": []}})
        self.assert_refused_and_nothing_written(
            lambda: self.run_cmd(STATE_TOOL, "set-handoff", CONVOY, T2, "--file", forged), "handoff_records")

    def test_finished_is_refused_without_a_proven_red(self):
        self.edit(T4, status="in_progress")
        self.state("record-gate", CONVOY, T4, "--gate", "dispatch")
        self.code()
        proc = self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff(), ticket=T4))
        self.assertIn("preuve du rouge", json.loads(proc.stdout)["error"])

    # --- T12: « terminé » needs the proof of the demonstration line at HEAD ----

    def test_finished_is_refused_without_a_demonstration_proof(self):
        self.code(demonstrated=False)
        self.assert_refused_and_nothing_written(
            lambda: self.finish(self.handoff()), "aucune preuve de démonstration", "ticket-author demonstrate")

    def test_finished_is_refused_when_the_demonstration_was_captured_before_the_head_commit(self):
        self.code()
        head = self.commit("un dernier commit", {README: "Le produit de la fixture, relu.\n"})
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "commit de tête", head)

    def test_finished_is_refused_when_the_demonstration_was_not_captured_on_the_launched_product(self):
        self.code(demonstrated=False)
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, T2, "--piece", "demonstration", "--repo", self.repo,
                            "--", "echo", "la page affiche les trois éléments")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "produit lancé")

    def test_finished_is_refused_when_the_demonstration_fingerprint_was_written_by_hand(self):
        head = self.code(demonstrated=False)
        self.state("add-evidence", CONVOY, T2, "--piece", "demonstration", "--digest", RED_DIGEST, "--commit", head)
        self.assert_refused_and_nothing_written(lambda: self.finish(self.handoff()), "magasin de preuves")

    def test_records_carry_the_demonstration_proof(self):
        head = self.code()

        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())

        ticket = self.shown()
        proof = ticket["handoff"]["records"]["demonstration_proof"]
        self.assertEqual(("demonstration", head, ticket["evidence"]["demonstration"]["digest"]),
                         (proof["piece"], proof["commit"], proof["digest"]))
        self.assertTrue(proof["address"].startswith("http://127.0.0.1:"))

    # --- AC4: the deferral detector -------------------------------------------

    MARKED_LINES = {
        "TODO": "# TODO brancher la liste sur la page",
        "FIXME": "# FIXME: la liste est vide",
        "not wired": "# The list is not wired to the home page yet.",
        "à brancher": "# Reste à brancher sur la page d'accueil.",
    }

    def test_finished_is_refused_on_a_deferral_marker_no_not_done_covers(self):
        # Demonstration line of the ticket, second part: a TODO in the diff, no « non fait ».
        for marker, line in self.MARKED_LINES.items():
            with self.subTest(marker=marker):
                self.git("reset", "-q", "--hard", self.red)
                self.code(line + "\n")
                proc = self.assert_refused_and_nothing_written(
                    lambda: self.finish(self.handoff()), "marqueur de report", APP, f"({marker})")
                self.assertIsNone(self.shown()["exit"])
                self.assertIn("Non fait", json.loads(proc.stdout)["error"])

    def test_a_not_done_about_another_file_does_not_cover_the_marker(self):
        self.code(self.MARKED_LINES["TODO"] + "\n")
        declared = [{"what": "Le README n'est pas écrit.", "paths": [README]}, "La page n'est pas branchée."]
        self.assert_refused_and_nothing_written(
            lambda: self.finish(self.handoff(not_done=declared)), "marqueur de report", APP)

    def test_finished_passes_when_each_marker_is_declared_and_records_list_them(self):
        for marker, line in self.MARKED_LINES.items():
            with self.subTest(marker=marker):
                self.git("reset", "-q", "--hard", self.red)
                self.code(line + "\n")
                declared = [{"what": "La liste n'est pas branchée sur la page d'accueil.", "paths": [APP]}]

                self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff(not_done=declared))

                handoff = self.shown()["handoff"]
                self.assertEqual(declared, handoff["sections"]["not_done"])
                found = handoff["records"]["deferral_markers"]
                self.assertEqual([(APP, marker, True)], [(m["path"], m["marker"], m["declared"]) for m in found])
                self.assertIn(line, found[0]["text"])
                self.assertGreater(found[0]["line"], 0)

    def test_a_marker_the_ticket_did_not_add_is_not_its_deferral(self):
        # Only the lines the ticket added are read: a line removed, or already there, is not one.
        self.git("checkout", "-q", "main")
        self.commit("avant le ticket", {README: "TODO d'avant le ticket\n"})
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-B", BRANCH)
        red = self.commit("tests de critère", {TEST_FILE: "# les tests de critère\n"})
        self.state("add-evidence", CONVOY, T2, "--piece", "tdd_red", "--digest", RED_DIGEST, "--commit", red)
        self.edit(T2, metadata={k: v for k, v in json.loads(self.tracker.read_text())["beads"][T2]["metadata"].items()
                                if k != "gc.flow.tdd.red"})
        self.state("set-tdd", CONVOY, T2, "--step", "red", "--commit", red, "--base", base)
        self.commit("le README est écrit", {README: "Le produit de la fixture.\n"})
        self.demonstrate()

        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())
        self.assertEqual([], self.shown()["handoff"]["records"]["deferral_markers"])

    def test_the_detector_alone_refuses_and_passes_and_writes_nothing(self):
        self.code(self.MARKED_LINES["TODO"] + "\n", demonstrated=False)
        proc = self.assert_refused_and_nothing_written(
            lambda: self.run_cmd(TOOL, "deferral", CONVOY, T2, "--repo", self.repo), status=EXIT_REFUSED)
        answer = json.loads(proc.stdout)
        self.assertEqual(["TODO"], [m["marker"] for m in answer["markers"]])
        declared = self.handoff(not_done=[{"what": "La liste n'est pas branchée.", "paths": [APP]}])
        before = self.tracker.read_bytes()
        proc = self.run_cmd(TOOL, "deferral", CONVOY, T2, "--repo", self.repo, "--handoff", declared)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["markers"][0]["declared"])
        self.assertEqual((before, []), (self.tracker.read_bytes(), self.store_files()))

    # --- AC2: Planning Exception and operator request park the ticket ----------

    REQUEST = {
        "quoi": "Le ticket a besoin d'un accès au service d'horloge",
        "pourquoi": "L'accès n'était pas déclaré dans le graphe ; lui seul peut le donner",
        "que_faire": [
            {"option": "Donner l'accès", "consequence": "Le ticket reprend."},
            {"option": "Retirer le besoin", "consequence": "La question retourne au Planning Run."},
        ],
    }

    def assert_parked_with_descendants(self, cause):
        for ticket_id in (T2, T3):
            park = self.shown(ticket_id)["park"]
            self.assertEqual((cause, T2), (park["cause"], park["origin"]), ticket_id)
        for ticket_id in (T1, T4):
            self.assertIsNone(self.shown(ticket_id)["park"], ticket_id)

    def test_planning_exception_parks_the_ticket_and_its_descendants(self):
        # Demonstration line of the ticket, last part.
        answer = self.raise_exception(
            "--kind", "semantic",
            "--summary", "La Spec fixe l'ordre alphabétique, la démonstration demande l'ordre de saisie")

        self.assertEqual(sorted([T2, T3]), answer["parked"])
        self.assert_parked_with_descendants("planning_exception")
        self.assertEqual("planning_exception", self.shown()["exit"]["exit"])
        requests = self.escalation_list()
        self.assertEqual(1, len(requests))
        self.assertIn(T2, requests[0])
        self.assertIn("Planning Exception (semantic)", requests[0])

    # --- T41 (af-rqgtpi): the Ticket Handoff first, then the Planning Exception --

    EXCEPTION = ("--exit", "planning_exception", "--kind", "semantic", "--summary", "La liste est livrée sans sa région")
    DEVIATION = "La région de l'ancre fixture-items n'est pas livrée : la liste est rendue à plat."

    def writes_of(self, key):
        """The positions, in the order the tracker received them, of the
        writes that set this field of the ticket."""
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [i for i, entry in enumerate(lines) if any(str(part).startswith(key + "=") for part in entry)]

    def test_planning_exception_is_refused_without_a_handoff(self):
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION), "Ticket Handoff", "Fait", "Écarts", "Non fait", "Constats hors ticket")
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION, "--repo", self.repo), "Ticket Handoff", "Écarts")
        self.assertEqual([], self.shown()["planning_exceptions"])
        self.assertEqual([], self.escalation_list())

    def test_planning_exception_is_refused_when_a_section_of_the_handoff_is_missing(self):
        for name, label in (("done", "Fait"), ("deviations", "Écarts"), ("not_done", "Non fait"),
                            ("out_of_ticket", "Constats hors ticket")):
            with self.subTest(section=name):
                self.assert_refused_and_nothing_written(
                    lambda: self.exit(*self.EXCEPTION, "--repo", self.repo, "--handoff", self.handoff(**{name: None})),
                    label)
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION, "--repo", self.repo, "--handoff", self.handoff(deviations=[])), "Écarts")
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION, "--handoff", self.handoff()), "--repo")
        self.assertEqual([], self.shown()["planning_exceptions"])
        self.assertEqual([], self.escalation_list())

    def test_planning_exception_records_the_handoff_first_then_parks(self):
        # Demonstration line of T41: « aucun » stands for an empty section.
        head = self.code()

        answer = self.raise_exception("--kind", "semantic", "--summary", "Question sur l'ordre",
                                      done="aucun", out_of_ticket="aucun")

        ticket = self.shown()
        self.assertEqual({name: "aucun" for name in COMPLETE}, ticket["handoff"]["sections"])
        self.assertEqual(head, ticket["handoff"]["records"]["head"])
        self.assertEqual(["Question sur l'ordre"], [e["summary"] for e in ticket["planning_exceptions"]])
        handoff, raised = self.writes_of("gc.flow.handoff"), self.writes_of("gc.flow.planning_exceptions")
        self.assertEqual((1, 1), (len(handoff), len(raised)))
        self.assertLess(handoff[0], raised[0])
        self.assertLessEqual(ticket["handoff"]["at"], ticket["planning_exceptions"][0]["at"])
        self.assertEqual(sorted([T2, T3]), answer["parked"])
        self.assert_parked_with_descendants("planning_exception")
        self.assertEqual("planning_exception", ticket["exit"]["exit"])
        self.assertEqual(1, len(self.escalation_list()))

    def test_planning_exception_is_refused_when_the_deviations_do_not_name_its_anchor(self):
        for deviations in ("aucun", ["La liste est rendue à plat."], ["L'ancre fixture-items-bis n'est pas livrée."]):
            with self.subTest(deviations=deviations):
                self.assert_refused_and_nothing_written(
                    lambda: self.exit(*self.EXCEPTION, "--anchor", "fixture-items", "--repo", self.repo,
                                      "--handoff", self.handoff(deviations=deviations)),
                    "fixture-items", "Écarts")
        # Each anchor named is looked for: one of two is not enough.
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION, "--anchor", "fixture-items", "--anchor", "fixture-title",
                              "--repo", self.repo, "--handoff", self.handoff(deviations=[self.DEVIATION])),
            "fixture-title", "Écarts")
        self.assertEqual([], self.shown()["planning_exceptions"])
        self.assertEqual([], self.escalation_list())

    def test_planning_exception_is_refused_when_the_deviations_name_only_an_anchor_that_contains_its_own(self):
        """The name is compared whole, whatever separates it from what follows
        (T51): `fixture` is not named by `fixture.items` nor by `fixture:items`."""
        for other in ("fixture-items", "fixture.items", "fixture:items", "fixture_items", "page.fixture", "page:fixture"):
            with self.subTest(other=other):
                self.assert_refused_and_nothing_written(
                    lambda: self.exit(*self.EXCEPTION, "--anchor", "fixture", "--repo", self.repo, "--handoff",
                                      self.handoff(deviations=[f"La région de l'ancre {other} n'est pas livrée."])),
                    "fixture", "Écarts")
        self.assertEqual([], self.shown()["planning_exceptions"])
        self.assertEqual([], self.escalation_list())

    def test_planning_exception_reads_its_anchor_before_the_punctuation_of_a_sentence(self):
        for deviation in ("La liste est rendue à plat, sans la région de l'ancre fixture.",
                          "Écart sur l'ancre fixture, rendue à plat.",
                          "fixture : la liste est rendue à plat.",
                          "fixture: la liste est rendue à plat.",
                          "L'ancre `fixture` (et non fixture.items) est rendue à plat."):
            with self.subTest(deviation=deviation):
                self.setUp()
                self.raise_exception("--kind", "semantic", "--summary", "La liste est livrée sans sa région",
                                     "--anchor", "fixture", deviations=[deviation])
                self.assertEqual([["fixture"]], [e["anchors"] for e in self.shown()["planning_exceptions"]])

    def test_planning_exception_names_under_deviations_the_anchor_it_raises(self):
        self.raise_exception("--kind", "semantic", "--summary", "La liste est livrée sans sa région",
                             "--anchor", "fixture-items", deviations=[self.DEVIATION])

        ticket = self.shown()
        self.assertEqual([self.DEVIATION], ticket["handoff"]["sections"]["deviations"])
        self.assertEqual([["fixture-items"]], [e["anchors"] for e in ticket["planning_exceptions"]])

    def test_planning_exception_naming_an_anchor_offers_its_acceptance_to_the_operator(self):
        """T16: a deviation from the Validated Prototype is never decided by
        the author; the request names the anchor and one of its options
        accepts the deviation. Only the operator's answer accepts it."""
        self.raise_exception("--kind", "semantic", "--summary", "La liste est livrée sans sa région",
                             "--anchor", "fixture-items", deviations=[self.DEVIATION])

        raised = self.shown()["planning_exceptions"]
        self.assertEqual([("semantic", ["fixture-items"], "open", False)],
                         [(e["kind"], e["anchors"], e["state"], e["accepted"]) for e in raised])
        self.assertEqual([], self.shown()["accepted_anchors"])
        options = json.loads(json.loads(self.tracker.read_text())["beads"][T2]["metadata"]["gc.escalation_que_faire"])
        accepting = [o for o in options if o["lettre"] == raised[0]["accept_option"]]
        self.assertEqual(1, len(accepting))
        self.assertIn("fixture-items", accepting[0]["option"])

        proc = self.run_cmd(ESCALATION_TOOL, "repondre", T2, raised[0]["accept_option"])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        self.assertEqual(["fixture-items"], self.shown()["accepted_anchors"])

    def test_planning_exception_without_anchor_offers_no_acceptance(self):
        self.raise_exception("--kind", "semantic", "--summary", "Question sur l'ordre")

        raised = self.shown()["planning_exceptions"]
        self.assertEqual([([], None)], [(e["anchors"], e["accept_option"]) for e in raised])
        proc = self.run_cmd(ESCALATION_TOOL, "repondre", T2, "a")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([], self.shown()["accepted_anchors"])

    def test_planning_exception_is_refused_with_a_malformed_anchor(self):
        self.assert_refused_and_nothing_written(
            lambda: self.exit(*self.EXCEPTION, "--repo", self.repo, "--handoff", self.handoff(),
                              "--anchor", "une ancre"), "ancre")
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "operator_request", "--request", self.file("r.json", {}), "--anchor", "liste"),
            "--anchor")

    def test_tickets_unrelated_to_a_parked_ticket_keep_starting(self):
        self.raise_exception("--kind", "topology", "--summary", "Le ticket recouvre T4")
        # The parked ticket is given back to the pool, as a resumed one would be.
        self.edit(T2, status="open")

        result = self.advance()

        self.assertEqual([T4], result["started"])
        self.assertEqual([T4], self.started_by_code())
        waiting = {entry["id"]: entry["reason"] for entry in result["waiting"]}
        self.assertIn("parqué", waiting[T3])
        self.assertIn(T2, waiting[T3])

    def test_planning_exception_is_refused_for_a_technical_repair_or_without_summary(self):
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "planning_exception", "--kind", "repair", "--summary", "le harnais est cassé",
                              "--repo", self.repo, "--handoff", self.handoff()),
            "bloqué technique")
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "planning_exception", "--kind", "semantic",
                              "--repo", self.repo, "--handoff", self.handoff()), "--summary")
        self.assertEqual([], self.escalation_list())

    def test_operator_request_parks_and_appears_on_the_escalation_door_list(self):
        answer = self.exited("--exit", "operator_request", "--request", self.file("request.json", self.REQUEST))

        self.assertEqual(sorted([T2, T3]), answer["parked"])
        self.assert_parked_with_descendants("operator_request")
        self.assertEqual("operator_request", self.shown()["exit"]["exit"])
        self.assertEqual([f"{T2} — {self.REQUEST['quoi']}"], self.escalation_list())
        mails = [json.loads(line) for line in self.write_log.read_text().splitlines() if line.startswith('["mail"')]
        self.assertEqual([["mail", "human", f"NEEDS BENJAMIN: {T2}"]], mails)

    def test_operator_request_is_refused_when_the_request_is_incomplete(self):
        for change, mention in (({"quoi": None}, "quoi"), ({"que_faire": []}, "que_faire"),
                                ({"pourquoi": "x" * 141}, "140"), ({"quoi": "deux\nlignes"}, "quoi"),
                                ({"que_faire": [{"option": "Donner l'accès"}]}, "conséquence"),
                                ({"langue": "en"}, "mal formée")):
            with self.subTest(change=change):
                request = {key: value for key, value in {**self.REQUEST, **change}.items() if value is not None}
                self.assert_refused_and_nothing_written(
                    lambda: self.exit("--exit", "operator_request", "--request", self.file("request.json", request)),
                    mention)
        self.assert_refused_and_nothing_written(lambda: self.exit("--exit", "operator_request"), "--request")
        self.assertEqual([], self.escalation_list())

    def test_a_parking_exit_may_carry_a_partial_handoff(self):
        head = self.code()
        partial = self.file("handoff.json", {"done": ["Le chargeur est écrit."]})

        self.exited("--exit", "operator_request", "--request", self.file("request.json", self.REQUEST),
                    "--repo", self.repo, "--handoff", partial)

        handoff = self.shown()["handoff"]
        self.assertTrue(handoff["partial"])
        self.assertEqual({"done": ["Le chargeur est écrit."]}, handoff["sections"])
        self.assertEqual(head, handoff["records"]["head"])

    # --- AC3: interrupted -----------------------------------------------------

    def test_interrupted_pushes_the_work_and_records_a_partial_handoff(self):
        head = self.code(self.MARKED_LINES["TODO"] + "\n")
        partial = self.file("handoff.json", {"done": ["Le chargeur est écrit."], "not_done": ["La page n'est pas branchée."]})
        self.assertIsNone(self.remote_tip())

        self.exited("--exit", "interrupted", "--repo", self.repo, "--handoff", partial)

        self.assertEqual(head, self.remote_tip())
        ticket = self.shown()
        self.assertEqual("interrupted", ticket["exit"]["exit"])
        handoff = ticket["handoff"]
        self.assertTrue(handoff["partial"])
        self.assertEqual(head, handoff["commit"])
        self.assertEqual({"remote": "origin", "branch": BRANCH, "commit": head}, handoff["records"]["pushed"])
        # An interruption is not refused for a marker: it is recorded.
        self.assertEqual([False], [m["declared"] for m in handoff["records"]["deferral_markers"]])
        self.assertIsNone(ticket["park"])

    def test_interrupted_without_any_section_still_records_the_pushed_work(self):
        head = self.code()
        self.exited("--exit", "interrupted", "--repo", self.repo)
        handoff = self.shown()["handoff"]
        self.assertEqual(({}, True, head), (handoff["sections"], handoff["partial"], handoff["records"]["pushed"]["commit"]))

    def test_interrupted_is_refused_when_the_work_cannot_be_pushed(self):
        self.code()
        self.git("remote", "remove", "origin")
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "interrupted", "--repo", self.repo), "poussée")

    def read(self, ticket_id=T2):
        proc = self.run_cmd(TOOL, "read", CONVOY, ticket_id)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_a_session_ended_without_an_exit_is_read_as_interrupted(self):
        session = {"id": "fx-s1", "session_name": "delivery-author-fx-s1", "template": "delivery-author",
                   "state": "active", "closed": False}
        self.edit(T2, assignee="delivery-author-fx-s1")
        self.edit(sessions=[session])
        before = self.tracker.read_bytes()
        self.assertIsNone(self.read()["exit"])

        for ended in ([{**session, "closed": True, "state": "closed"}], []):
            with self.subTest(sessions=ended):
                self.edit(sessions=ended)
                before = self.tracker.read_bytes()
                read = self.read()["exit"]
                self.assertEqual(("interrupted", False), (read["exit"], read["declared"]))
                self.assertIn("delivery-author-fx-s1", read["reason"])
                self.assertEqual(before, self.tracker.read_bytes())

    def test_a_ticket_no_session_took_or_that_declared_its_exit_is_not_read_as_interrupted(self):
        self.edit(T2, status="open")
        self.assertIsNone(self.read()["exit"])
        self.edit(T2, status="in_progress", assignee="delivery-author-fx-s1")
        self.raise_exception("--kind", "semantic", "--summary", "Question sur l'ordre")
        read = self.read()["exit"]
        self.assertEqual(("planning_exception", True), (read["exit"], read["declared"]))

    # --- AC6: a ticket receives the Handoff of its closed direct blockers ------

    def test_reading_a_ticket_joins_the_handoff_of_its_closed_blocker(self):
        head = self.code()
        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff(
            deviations=["Le champ s'appelle label et non name."]))
        self.close_through_gate(T2)

        read = self.read(T3)

        self.assertEqual(description(), read["ticket"]["description"])
        self.assertEqual([T2], [entry["ticket"] for entry in read["blocker_handoffs"]])
        joined = read["blocker_handoffs"][0]["handoff"]
        self.assertEqual(["Le champ s'appelle label et non name."], joined["sections"]["deviations"])
        self.assertEqual(COMPLETE["out_of_ticket"], joined["sections"]["out_of_ticket"])
        self.assertEqual(head, joined["records"]["head"])
        self.assertEqual([README], joined["records"]["files_outside_declared_scope"])

    def test_reading_a_ticket_joins_nothing_of_a_blocker_still_open(self):
        self.code()
        self.exited("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff())
        self.assertEqual([], self.read(T3)["blocker_handoffs"])
        # T1 is closed and wrote no Handoff: it is named, with none.
        self.assertEqual([{"ticket": T1, "title": "ticket d'essai", "handoff": None}], self.read(T2)["blocker_handoffs"])

    # --- what any exit refuses ------------------------------------------------

    def test_an_exit_outside_the_closed_list_is_refused(self):
        self.assert_refused_and_nothing_written(lambda: self.exit("--exit", "done"), "liste fermée")
        self.assert_refused_and_nothing_written(lambda: self.exit(), "liste fermée")

    def test_a_ticket_not_started_or_closed_has_no_exit(self):
        self.code()
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "finished", "--repo", self.repo, "--handoff", self.handoff(), ticket=T4),
            "porte de dispatch")
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "interrupted", "--repo", self.repo, ticket=T1), "fermé")
        self.assert_refused_and_nothing_written(
            lambda: self.exit("--exit", "interrupted", "--repo", self.repo, ticket="fx-absent"), "n'appartient pas")

    def test_a_convoy_without_the_mark_is_not_touched(self):
        before = self.tracker.read_bytes()
        for command in (("exit", PLAIN_CONVOY, PLAIN_TICKET, "--exit", "finished", "--repo", self.repo,
                         "--handoff", self.handoff()),
                        ("read", PLAIN_CONVOY, PLAIN_TICKET),
                        ("deferral", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo)):
            with self.subTest(command=command[0]):
                proc = self.run_cmd(TOOL, *command)
                self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
                self.assertEqual((before, []), (self.tracker.read_bytes(), self.store_files()))


def load(name):
    """A sibling test file, as a module: its harness is reused, not its tests."""
    path = str(ROOT / "tests" / name)
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


publication = load("ticket-graph-publish-coverage-test.py")
PROJECT = publication.PROJECT


class TechnicallyBlockedTest(publication.Harness):
    """`technically_blocked` on the graph of the Fixture City, published by
    the real publication door: T2 (blocked by T1, delivered) is at work, T3
    waits for it, T4 waits for nothing."""

    REPAIR = {
        "title": "Le harnais de test relit le jeu de données",
        "what_it_delivers": "Le harnais de test du produit charge de nouveau le jeu de données « contenu ».",
        "restores": {"kind": "red_check", "ref": "le harnais échoue au chargement du jeu de données « contenu »"},
        "demonstration_line": "Sur le produit lancé avec le jeu de données « contenu », GET /api/items rend trois éléments.",
        "acceptance_criteria": [{
            "entry_point": "GET /api/items sur le produit lancé avec le jeu de données « contenu »",
            "observable": "la réponse JSON liste trois éléments",
            "false_if": "la réponse est vide ou en erreur",
        }],
    }

    def setUp(self):
        super().setUp()
        self.seed(publication.CONFORMANT_DRAFT.read_text(encoding="utf-8"))
        self.ids = self.published()["ids"]
        self.convoy = self.ids["_convoy"]
        # The Factory root the exit tool hands to the patch door.
        factory = self.tmp / "exit-root"
        (factory / "config" / "projects").mkdir(parents=True)
        shutil.copy(publication.PROJECTS_CONFIG_DIR / f"{PROJECT}.toml", factory / "config" / "projects")
        shutil.copytree(self.descriptors, factory / "config" / "project-descriptors")
        self.env = {**self.env, "FACTORY_ROOT": str(factory), "TICKET_GRAPH_BD_WORKSPACE": str(self.tmp)}
        for name in SESSION_IDENTITY:
            self.env.pop(name, None)
        # T1 is delivered, T2 is at work.
        self.state_tool("close-ticket", self.convoy, self.ids["T1"], "--commit", "0" * 40, "--file", str(GATE_REPORT))
        self.state_tool("record-gate", self.convoy, self.ids["T2"], "--gate", "dispatch")
        self.edit_bead(self.ids["T2"], status="in_progress")

    def exit(self, repair, *extra):
        path = self.tmp / "repair.json"
        path.write_text(json.dumps(repair, ensure_ascii=False))
        return subprocess.run(
            (str(TOOL), "exit", self.convoy, self.ids["T2"], "--exit", "technically_blocked", "--repair", str(path), *extra),
            env=self.env, text=True, capture_output=True)

    def test_technically_blocked_publishes_a_repair_that_blocks_the_ticket(self):
        before = self.beads()

        proc = self.exit(self.REPAIR)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        repair = json.loads(proc.stdout)["repair"]
        self.assertEqual(("R1", self.ids["T2"]), (repair["key"], repair["blocks"]))
        beads = self.beads()
        # Created by code, published by the patch door: marked, tracked, a repair.
        self.assertFalse(self.convoy_state(self.convoy)["unruled"])
        ticket = self.shown_ticket(self.convoy, repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        self.assertEqual(self.REPAIR["demonstration_line"], ticket["demonstration_line"])
        self.assertEqual({}, ticket["gates"])
        self.assertIn("red_check : le harnais échoue", beads[repair["id"]]["description"])
        self.assertNotIn("approved_by", beads[repair["draft"]]["metadata"])
        # It blocks the ticket, which keeps the blocker it already had.
        self.assertEqual("R1,T1", beads[self.ids["T2"]]["metadata"]["gc.blocked_by"])
        self.assertEqual("technically_blocked", self.shown_ticket(self.convoy, self.ids["T2"])["exit"]["exit"])
        # The rest of the convoy goes on: nothing is parked, T3 and T4 are as they were.
        for key in ("T3", "T4"):
            shown = self.shown_ticket(self.convoy, self.ids[key])
            self.assertEqual((None, None, "open"), (shown["park"], shown["exit"], shown["status"]), key)
            self.assertEqual(before[self.ids[key]]["metadata"]["gc.blocked_by"],
                             beads[self.ids[key]]["metadata"]["gc.blocked_by"], key)
        self.assertIsNone(self.shown_ticket(self.convoy, self.ids["T2"])["park"])

    def test_the_red_control_a_technical_block_names_is_recorded_on_the_convoy(self):
        # T40: the patch door publishes a repair of a red control only if the
        # convoy carries a record of it; the exit records the one it names.
        self.assertEqual([], self.convoy_state(self.convoy)["convoy"]["red_checks"])

        self.assertEqual(0, self.exit(self.REPAIR).returncode)

        self.assertEqual(
            [{"name": self.REPAIR["restores"]["ref"], "source": "technically_blocked", "ticket": self.ids["T2"]}],
            self.convoy_state(self.convoy)["convoy"]["red_checks"])

    def test_a_refused_technical_block_leaves_no_red_control_on_the_convoy(self):
        repair = {**self.REPAIR, "acceptance_criteria": ["La réponse liste trois éléments."]}
        before = self.beads()

        proc = self.exit(repair)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        beads = self.beads()
        self.assertEqual(before, {bead_id: beads[bead_id] for bead_id in before})
        self.assertEqual([], self.convoy_state(self.convoy)["convoy"]["red_checks"])

    def test_a_second_technical_block_adds_a_second_repair(self):
        self.assertEqual(0, self.exit(self.REPAIR).returncode)
        proc = self.exit({**self.REPAIR, "title": "Le harnais retrouve son port"})
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("R2", json.loads(proc.stdout)["repair"]["key"])
        self.assertEqual("R1,R2,T1", self.beads()[self.ids["T2"]]["metadata"]["gc.blocked_by"])

    def test_technically_blocked_is_refused_when_the_repair_breaks_the_entry_contract(self):
        repair = {**self.REPAIR, "restores": {"kind": "user_story", "ref": "user story 99"}}
        before = self.beads()

        proc = self.exit(repair)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("la porte de patch a refusé", json.loads(proc.stdout)["error"])
        beads = self.beads()
        # Nothing of the graph changed; the refused revision is closed.
        self.assertEqual(before, {bead_id: beads[bead_id] for bead_id in before})
        drafts = [bead for bead_id, bead in beads.items() if bead_id not in before]
        self.assertEqual(["closed"], [bead["status"] for bead in drafts])
        self.assertIsNone(self.shown_ticket(self.convoy, self.ids["T2"])["exit"])

    def test_technically_blocked_is_refused_when_the_author_sets_more_than_a_repair(self):
        before = self.state_path.read_bytes()
        for repair in ({**self.REPAIR, "kind": "vertical_slice"}, {**self.REPAIR, "blocked_by": []},
                       {key: value for key, value in self.REPAIR.items() if key != "restores"}):
            with self.subTest(fields=sorted(repair)):
                proc = self.exit(repair)
                self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("ticket repair mal formé", json.loads(proc.stdout)["error"])
                self.assertEqual(before, self.state_path.read_bytes())
        proc = subprocess.run((str(TOOL), "exit", self.convoy, self.ids["T2"], "--exit", "technically_blocked"),
                              env=self.env, text=True, capture_output=True)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.state_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
