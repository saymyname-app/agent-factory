#!/usr/bin/env python3
# ci: over-ceiling — 119 s then 122 s in two CI runs of the same file (2026-10-11): at the ceiling, not above it by its cases; to cut with the next long files (af-vqew1x)
"""bin/ticket-end on a fake tracker state (T19, af-iefuud; Spec af-wf4w5r §9,
Testing Decisions seam 2): one test per pass and per refusal, each refusal
re-reading the tracker, the evidence store and the branches to prove nothing
was written. Only command lines are exercised. The product is a copy of the
Delivery Fixture City in a throwaway repository with its own remote. Every
piece of evidence is filed and sealed by the real bin/evidence-capture, the
merge is the real bin/spec-integration, the fidelity check is the real
bin/prototype-fidelity on the product launched by the real
bin/project-launch, with a fake browser that fetches the pages it is given."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "ticket-end"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
FIXTURE = "tests/fixtures/delivery-fixture-city"
PROTOTYPE = f"{FIXTURE}/prototype"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_BROWSER = ROOT / "tests" / "fixtures" / "prototype-fidelity" / "browser"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, SCREEN, PREFACTORING = "fx-t1", "fx-t2", "fx-p1"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
VERSION = "ticket-end/v1"
APPROVER = "benjamin-hurand"

EXIT_REFUSED = 1
EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4

CRITERION = "Point d'entrée : GET / — Observable : liste — Faux si : une ligne manque"
SPEC_LINE = "La page d'accueil affiche le nombre d'éléments."
SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID")
SECTIONS = {"done": ["Critère 1 observé sur GET /."], "deviations": "aucun", "not_done": "aucun",
            "out_of_ticket": "aucun"}
NAMES = ("criteria", "handoff", "evaluation", "fidelity", "deferral", "merge", "evidence", "tdd", "review")


def branch_of(ticket):
    return f"ticket/{ticket}"


class TicketEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class: a stage reached once (a seeded
        # city, a merged ticket) is archived and restored at the same paths,
        # which the work trees and the remote of the product hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="ticket-end-test-"))
        cls.tmp = cls.holder / "city"
        cls.stages = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.holder, ignore_errors=True)

    def stage(self, name, build):
        """The state `build` leaves, built once and restored afterwards."""
        archive = self.holder / f"{name}.tar"
        if name in self.stages:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp.mkdir()
            subprocess.run(("tar", "-C", str(self.tmp), "-xf", str(archive)), check=True)
        else:
            self.stages[name] = build()
            subprocess.run(("tar", "-C", str(self.tmp), "-cf", str(archive), "."), check=True)
        return self.stages[name]

    def setUp(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir()
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        gc = self.tmp / "path" / "gc"
        self.profile = self.tmp / "descriptor.json"
        self.env = {
            **os.environ,
            "PATH": f"{self.tmp / 'path'}{os.pathsep}{os.environ['PATH']}",
            "GC_BIN": str(gc),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_WORK_DIR": str(self.work),
            "TICKET_END_WORK_DIR": str(self.tmp / "gate-work"),
            "EVIDENCE_STORE_DIR": str(self.store),
            "EVIDENCE_CAPTURE_BROWSER": str(FAKE_BROWSER),
            "EVIDENCE_FAKE_BROWSER_LOG": str(self.tmp / "browser.log"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for name in ("FIDELITY_FAKE_BROWSER_MODE", "EVIDENCE_FAKE_BROWSER_MODE", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.base = self.stage("seeded", self.seed)

    def seed(self):
        (self.tmp / "path").mkdir()
        # The real `gc` finds its city from the working directory: called
        # from a merge work tree it finds none (tests/spec-integration-test.py).
        gc = self.tmp / "path" / "gc"
        gc.write_text(
            f'#!/bin/sh\ncase "$PWD/" in "{self.work}"/*) echo "gc bd: not in a city directory" >&2; exit 1;; esac\n'
            f'exec "{FAKE_GC}" "$@"\n')
        gc.chmod(0o755)
        shutil.copy(ROOT / FIXTURE / "descriptor.json", self.profile)
        self.seed_repo()
        self.seed_tracker()
        proc = self.run_cmd(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.repo, "--protected", PROTECTED)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return self.base

    # --- harness ------------------------------------------------------------

    def seed_repo(self):
        """The product and its remote, the protected branch pushed. The
        Validated Prototype is the one of the fixture, at the first commit."""
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / "README.md").write_text("Le produit de la fixture.\n")
        self.git("init", "-q", "-b", PROTECTED)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        subprocess.run(("git", "init", "-q", "--bare", "-b", PROTECTED, str(self.origin)), env=self.env, check=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", PROTECTED)
        self.base = self.git("rev-parse", "HEAD")

    def seed_tracker(self):
        """A marked convoy: a slice that touches no screen, an interface
        slice (the publication door posed the reference of the Validated
        Prototype in it) and a prefactoring; and a convoy without the mark."""
        def ticket(kind, interface=False):
            sections = [f"## Acceptance criteria\n\n- [ ] {CRITERION}"]
            if interface:
                sections.append(
                    "## Validated Prototype\n\n- branche : main\n"
                    f"- commit : {self.base}\n- chemin : {PROTOTYPE}\n- états : empty, content\n"
                    "- Prototype Fold : ce ticket")
            sections.append("## Target rigs\n\nfx-rig")
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": "\n\n".join(sections), "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, SCREEN, PREFACTORING]},
            SLICE: ticket("vertical_slice"), SCREEN: ticket("vertical_slice", interface=True),
            PREFACTORING: ticket("prefactoring"),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY,
                   "--demonstration-line", f"{SLICE}=La page d'accueil affiche les trois éléments",
                   "--demonstration-line", f"{SCREEN}=La page d'accueil porte les ancres du prototype",
                   "--user-stories", f"{SLICE}=1", "--user-stories", f"{SCREEN}=2", "--prototype-fold", SCREEN)

    def git(self, *args, cwd=None, check=True):
        proc = subprocess.run(
            ("git", "-C", str(cwd or self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True)
        if check:
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def remote_tip(self, branch=INTEGRATION):
        proc = subprocess.run(("git", "--git-dir", str(self.origin), "rev-parse", "--verify", "--quiet",
                               f"refs/heads/{branch}"), env=self.env, text=True, capture_output=True)
        return proc.stdout.strip() or None

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=env or self.env, text=True, capture_output=True)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def show(self, expect=0):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket, expect=0):
        return next(t for t in self.show(expect)["tickets"] if t["id"] == ticket)

    def json_file(self, name, content):
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def metadata(self, ticket):
        return json.loads(self.tracker.read_text())["beads"][ticket].get("metadata") or {}

    def edit(self, bead_id, status=None, description=None, unset=(), **metadata):
        """A tracker state written outside every command: what a gate must
        not take for granted."""
        state = json.loads(self.tracker.read_text())
        bead = state["beads"][bead_id]
        if status is not None:
            bead["status"] = status
        if description is not None:
            bead["description"] = description
        bead.setdefault("metadata", {}).update(metadata)
        for key in unset:
            bead["metadata"].pop(key, None)
        self.tracker.write_text(json.dumps(state))

    def worktree(self, ticket):
        """The work tree of the author of a ticket, on its branch."""
        path = self.tmp / "wt" / ticket
        if not path.is_dir():
            self.git("fetch", "-q", "origin")
            self.git("worktree", "add", "-q", "-b", branch_of(ticket), str(path), f"origin/{INTEGRATION}")
        return path

    def commit_on(self, ticket, files, message="travail du ticket"):
        tree = self.worktree(ticket)
        for path, content in files.items():
            target = tree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A", cwd=tree)
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=tree)
        self.git("push", "-q", "origin", branch_of(ticket), cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def capture(self, ticket, piece, report=None):
        """One piece of evidence filed by the real capture tool, at the HEAD
        of the ticket's work tree: the report is what the captured command
        prints, as the script of a step prints its own."""
        printed = json.dumps(report if report is not None else {"vu": piece}, ensure_ascii=False)
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, ticket, "--piece", piece, "--repo", self.worktree(ticket),
                            "--expect-exit", "0", "--", "printf", "%s", printed)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def reviewed(self, ticket, commit, findings=()):
        self.state("open-code-review", CONVOY, ticket, "--kind", "review", "--commit", commit, "--base", self.base)
        return self.state("record-code-review", CONVOY, ticket, "--file", self.json_file(f"review-{ticket}.json", {
            "commit": commit, "recorded_by": f"delivery-reviewer-{ticket}-{commit[:6]}", "findings": list(findings), "answers": {}}))

    def evaluated(self, ticket, commit, legacy=False):
        """The demonstration line observed at `commit` (ADR-0030 L4); with
        `legacy`, also one state per criterion, as a round recorded before."""
        shown = self.shown(ticket)
        self.state("open-evaluation", CONVOY, ticket, "--commit", commit, "--file", self.json_file(
            f"evaluation-request-{ticket}.json", {
                "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
                "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": "/launch.json"}]}))
        self.capture(ticket, "evaluation.seen")
        handed = {"commit": commit, "recorded_by": f"delivery-evaluator-{ticket}-{commit[:6]}",
                  "demonstration_line": {"text": shown["demonstration_line"], "state": "observed",
                                         "evidence": "evaluation.seen"}}
        if legacy:
            handed["criteria"] = [{"number": number, "text": text, "state": "observed", "evidence": "evaluation.seen"}
                                  for number, text in enumerate(shown["criteria"], start=1)]
        return self.state("record-evaluation", CONVOY, ticket, "--file", self.json_file(f"evaluation-{ticket}.json", handed))

    def finished(self, ticket, findings=(), markers=(), legacy=False):
        """A ticket walked by its author to the exit « terminé », then
        reviewed and evaluated at its tip: every step proven by a sealed
        piece, as bin/tdd-step, bin/ticket-author and bin/ticket-exit file
        them. Returns the tip."""
        prefactoring = ticket == PREFACTORING
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.edit(ticket, status="in_progress")
        start = self.git("rev-parse", "HEAD", cwd=self.worktree(ticket))
        if prefactoring:
            tip = self.commit_on(ticket, {f"docs/{ticket}.md": "même comportement, autre forme\n"})
            self.capture(ticket, "tdd_prefactoring", {"verdict": "unchanged", "regression": [
                {"commit": start, "exit_code": 0}, {"commit": tip, "exit_code": 0}]})
            self.state("set-tdd", CONVOY, ticket, "--step", "prefactoring", "--commit", tip, "--base", start)
            red = {"step": "prefactoring", "base": start, "commit": tip, "piece": "tdd_prefactoring"}
            demonstration = None
        else:
            test = f"{FIXTURE}/tests/test_{ticket.replace('-', '_')}.py"
            red_commit = self.commit_on(ticket, {test: f"# test de critère du ticket {ticket}\n"}, "tests de critère")
            self.capture(ticket, "tdd_red", {"verdict": "red", "base": start, "seam_mode": "black_box",
                                             "tests": [{"id": f"{test}::T::test", "outcome": "failed",
                                                        "entry_points": ["GET /"]}]})
            self.state("set-tdd", CONVOY, ticket, "--step", "red", "--commit", red_commit, "--base", start)
            files = {test: "sha256:" + hashlib.sha256((self.worktree(ticket) / test).read_bytes()).hexdigest()}
            self.capture(ticket, "tdd_freeze", {"files": files})
            self.state("set-tdd", CONVOY, ticket, "--step", "freeze", "--commit", red_commit)
            tip = self.commit_on(ticket, {f"docs/{ticket}.md": "la tranche\n"})
            self.capture(ticket, "tdd_green", {"verdict": "green", "k": 3, "frozen": red_commit, "seam_mode": "black_box"})
            self.state("set-tdd", CONVOY, ticket, "--step", "green", "--commit", tip)
            self.capture(ticket, "demonstration")
            red = {"step": "red", "base": start, "commit": red_commit, "piece": "tdd_red"}
            demonstration = {"piece": "demonstration", "commit": tip, "kind": "command", "address": None}
        self.capture(ticket, "handoff_records")
        self.state("set-handoff", CONVOY, ticket, "--file", self.json_file(f"handoff-{ticket}.json", {
            "sections": SECTIONS, "partial": False, "commit": tip, "records": {
                "exit": "finished", "branch": branch_of(ticket), "head": tip, "base": start, "red_proof": red,
                "demonstration_proof": demonstration, "deferral_markers": list(markers)}}))
        self.state("set-exit", CONVOY, ticket, "--exit", "finished")
        self.reviewed(ticket, tip, findings)
        if prefactoring:
            self.capture(ticket, "evaluation.startup")
            self.state("record-startup", CONVOY, ticket, "--commit", tip, "--piece", "evaluation.startup", "--file",
                       self.json_file("startup.json", {"environment": [{"dataset": "content",
                                                                         "address": "http://127.0.0.1:1"}]}))
        else:
            self.evaluated(ticket, tip, legacy)
        return tip

    def gate(self, command, *args, env=None):
        return self.run_cmd(TOOL, command, CONVOY, *args, "--repo", self.repo, env=env)

    def check(self, ticket, *extra):
        proc = self.gate("check", ticket, *extra)
        return proc.returncode, json.loads(proc.stdout)

    def fidelity(self, *extra):
        proc = self.gate("fidelity", "--profile", self.profile, *extra)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def merge(self):
        proc = self.run_cmd(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.repo, "--profile", self.profile)
        return proc.returncode, json.loads(proc.stdout)

    def merged(self, ticket):
        """A finished ticket merged into the integration branch by the real
        merge command. Returns the tip of the ticket."""
        def build():
            tip = self.finished(ticket)
            status, answer = self.merge()
            self.assertEqual((0, [ticket]), (status, [entry["id"] for entry in answer["merged"]]), answer)
            return tip
        # Only from the seeded city: a second ticket is built on what is there.
        untouched = not (self.tmp / "wt").exists()
        return self.stage(f"merged-{ticket}", build) if untouched else build()

    def measured(self):
        """The interface ticket finished, its fidelity measured at its tip."""
        def build():
            tip = self.finished(SCREEN)
            self.fidelity()
            return tip
        return self.stage("measured", build)

    def close(self, ticket):
        proc = self.gate("close", ticket)
        return proc.returncode, json.loads(proc.stdout)

    def store_files(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*") if p.is_file() and p.name != ".seal-key")

    def snapshot(self):
        refs = subprocess.run(("git", "--git-dir", str(self.origin), "for-each-ref", "--format=%(refname) %(objectname)"),
                              env=self.env, text=True, capture_output=True).stdout
        log = self.write_log.read_text() if self.write_log.exists() else ""
        return (self.tracker.read_bytes(), self.store_files(), refs, log)

    def assert_left_open(self, ticket, missing, *mentions):
        """The gate refuses to close the ticket, names the missing condition
        and nothing else, and what is read again is what it was."""
        before = self.snapshot()
        status, answer = self.close(ticket)
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertFalse(answer["ok"])
        self.assertEqual([missing], answer["missing"], answer)
        self.assertIn(f"condition {missing}", answer["error"])
        for mention in mentions:
            self.assertIn(mention, answer["error"])
        verdicts = {entry["number"]: entry["verdict"] for entry in answer["conditions"]}
        self.assertEqual({number: "fail" if number == missing else "pass" for number in range(1, 10)}, verdicts)
        self.assertEqual(before, self.snapshot())
        self.assertNotEqual("closed", self.shown(ticket)["status"])
        self.assertNotIn("ticket_end", self.shown(ticket)["gates"])
        return answer

    # --- AC1: the nine conditions are met -----------------------------------

    def test_ticket_whose_nine_conditions_hold_is_closed_with_the_nine_verdicts_and_the_list_version(self):
        tip = self.merged(SLICE)

        status, answer = self.close(SLICE)

        self.assertEqual(0, status, answer)
        self.assertEqual((True, True, SLICE, tip, VERSION),
                         tuple(answer[name] for name in ("ok", "closed", "ticket", "commit", "version")))
        shown = self.shown(SLICE)
        self.assertEqual("closed", shown["status"])
        record = shown["gates"]["ticket_end"]
        self.assertEqual((VERSION, tip), (record["version"], record["commit"]))
        self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in record["conditions"]])
        for entry in record["conditions"]:
            self.assertTrue(entry["detail"].strip(), entry)
        # Closed through its gate: the convoy is in a state the code has a rule for.
        self.assertEqual([], shown["unruled"])
        self.assertFalse(self.show()["unruled"])

    def test_a_round_on_the_demonstration_line_alone_passes_the_nine_conditions(self):
        self.merged(SLICE)
        self.assertEqual([], self.shown(SLICE)["evaluation"]["rounds"][-1]["criteria"])

        status, answer = self.check(SLICE)

        self.assertEqual((0, []), (status, answer["missing"]), answer)

    def test_a_round_recorded_with_a_state_per_criterion_before_adr_0030_l4_still_closes_the_ticket(self):
        self.finished(SLICE, legacy=True)
        self.assertEqual(0, self.merge()[0])
        self.assertEqual(["observed"], [item["state"] for item in
                                        self.shown(SLICE)["evaluation"]["rounds"][-1]["criteria"]])

        status, answer = self.close(SLICE)

        self.assertEqual(0, status, answer)

    def test_closing_is_one_tracker_write_that_carries_the_record_and_the_status(self):
        self.merged(SLICE)
        self.write_log.write_text("")

        self.assertEqual(0, self.close(SLICE)[0])

        writes = [json.loads(line) for line in self.write_log.read_text().splitlines()]
        self.assertEqual(1, len(writes), writes)
        self.assertIn("gc.flow.gate.ticket_end", json.dumps(writes[0]))
        self.assertIn("closed", json.dumps(writes[0]))

    def test_prefactoring_is_closed_on_the_proof_that_its_product_starts_and_its_regression_is_unchanged(self):
        tip = self.merged(PREFACTORING)

        status, answer = self.close(PREFACTORING)

        self.assertEqual(0, status, answer)
        record = self.shown(PREFACTORING)["gates"]["ticket_end"]
        self.assertEqual(tip, record["commit"])
        details = {entry["number"]: entry["detail"] for entry in record["conditions"]}
        self.assertIn("démarre", details[3])
        self.assertIn("prefactoring", details[8])

    def test_closed_ticket_is_not_closed_twice(self):
        self.merged(SLICE)
        self.assertEqual(0, self.close(SLICE)[0])
        before = self.snapshot()

        status, answer = self.close(SLICE)

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertIn("déjà fermé", answer["error"])
        self.assertEqual(before, self.snapshot())

    def test_check_lists_the_nine_verdicts_and_writes_nothing(self):
        self.merged(SLICE)
        before = self.snapshot()

        status, answer = self.check(SLICE)

        self.assertEqual(0, status, answer)
        self.assertEqual((True, VERSION, [], list(range(1, 10))),
                         (answer["ok"], answer["version"], answer["missing"],
                          [entry["number"] for entry in answer["conditions"]]))
        self.assertEqual(before, self.snapshot())

    # --- AC2: one condition withdrawn at a time ------------------------------

    def test_condition_1_criteria_changed_since_the_approved_digest_leaves_the_ticket_open(self):
        self.merged(SLICE)
        bead = json.loads(self.tracker.read_text())["beads"][SLICE]
        self.edit(SLICE, description=bead["description"].replace("une ligne manque", "la page répond 200"))

        self.assert_left_open(SLICE, 1, "Critères évalués identiques au digest approuvé")

    def test_condition_1_demonstration_line_changed_since_its_evaluation_leaves_the_ticket_open(self):
        self.merged(SLICE)
        self.edit(SLICE, **{"gc.flow.demonstration_line": "La page d'accueil affiche autre chose"})

        self.assert_left_open(SLICE, 1, "ligne de démonstration")

    def test_condition_2_handoff_without_demonstration_proof_leaves_the_ticket_open(self):
        self.merged(SLICE)
        self.edit(SLICE, unset=("gc.flow.evidence.demonstration",))
        (self.store / SPEC / SLICE / "demonstration.json").unlink()

        self.assert_left_open(SLICE, 2, "Ticket Handoff valide", "démonstration")

    def test_condition_3_without_ticket_evaluation_leaves_the_ticket_open(self):
        self.merged(SLICE)
        self.edit(SLICE, unset=("gc.flow.evaluation", "gc.flow.verdict.evaluation"))

        self.assert_left_open(SLICE, 3, "Ticket Evaluation")

    def test_condition_4_interface_ticket_without_fidelity_result_leaves_the_ticket_open(self):
        self.measured()
        self.assertEqual([SCREEN], [entry["id"] for entry in self.merge()[1]["merged"]])
        self.edit(SCREEN, unset=("gc.flow.fidelity", "gc.flow.verdict.fidelity"))

        self.assert_left_open(SCREEN, 4, "fidélité")

    def test_condition_5_undeclared_deferral_marker_leaves_the_ticket_open(self):
        self.merged(SLICE)
        handoff = json.loads(self.metadata(SLICE)["gc.flow.handoff"])
        handoff["records"]["deferral_markers"] = [
            {"path": "docs/fx-t1.md", "line": 1, "marker": "TODO", "text": "TODO brancher", "declared": False}]
        self.edit(SLICE, **{"gc.flow.handoff": json.dumps(handoff)})

        self.assert_left_open(SLICE, 5, "Détecteur de report", "docs/fx-t1.md:1")

    def test_condition_6_ticket_not_merged_leaves_the_ticket_open(self):
        self.finished(SLICE)

        self.assert_left_open(SLICE, 6, "Fusionné dans la branche d'intégration")

    def test_condition_6_red_tests_on_the_merged_result_leave_the_ticket_open(self):
        self.merged(SLICE)
        piece = self.store / SPEC / SLICE / "merged_tests.json"
        merged_at = json.loads(piece.read_text())["commit"]
        # The same piece, filed again by the capture tool at the merged
        # result, with a command that fails: a red run is a piece too.
        tree = self.tmp / "merged"
        self.git("worktree", "add", "-q", "--detach", str(tree), merged_at)
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, SLICE, "--piece", "merged_tests", "--repo", tree, "--", "false")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        self.assert_left_open(SLICE, 6, "tests rouges")

    def test_condition_7_fingerprint_of_a_piece_the_capture_tool_never_filed_leaves_the_ticket_open(self):
        tip = self.merged(SLICE)
        self.state("add-evidence", CONVOY, SLICE, "--piece", "evaluation.redigee", "--digest", "sha256:" + "ab" * 32,
                   "--commit", tip)

        self.assert_left_open(SLICE, 7, "Preuves recevables", "evaluation.redigee")

    def test_condition_8_without_recorded_green_leaves_the_ticket_open(self):
        self.merged(SLICE)
        self.edit(SLICE, unset=("gc.flow.tdd.green",))

        self.assert_left_open(SLICE, 8, "Preuve TDD", "vert")

    def test_condition_9_without_review_verdict_leaves_the_ticket_open(self):
        self.merged(SLICE)
        self.edit(SLICE, unset=("gc.flow.code_review", "gc.flow.verdict.code_review"))

        self.assert_left_open(SLICE, 9, "Verdict de revue")

    def test_merged_pull_request_and_green_ci_do_not_close_a_ticket(self):
        """ADR-0026's closing proof -- a merged PR and a green CI -- on a
        ticket that met none of the nine conditions."""
        self.state("record-gate", CONVOY, SLICE, "--gate", "dispatch")
        self.edit(SLICE, status="in_progress", **{
            "gc.delivery_status": "merged", "gc.work_outcome": "shipped", "gc.pr_number": 12,
            "gc.pr_head": "a" * 40, "gc.merge_commit": "b" * 40, "gc.ci_conclusion": "success"})
        before = self.snapshot()

        status, answer = self.close(SLICE)

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual(list(range(1, 10)), answer["missing"])
        self.assertEqual(before, self.snapshot())

    # --- condition 9: the recorded override of the operator -----------------

    def refused_then_overridden(self, override=True):
        """A ticket whose review left a Blocking Finding without a favorable
        verdict, stopped after its round, and that the declared approver
        overrode (Spec §8, « passer outre »)."""
        finding = {"axis": "spec", "blocking": True, "summary": "Le nombre d'éléments n'est pas affiché.",
                   "citation": {"source": "spec", "quote": SPEC_LINE}}
        tip = self.finished(SLICE, findings=[finding])
        self.state("stop-ticket", CONVOY, SLICE, "--reason", "still_refused", "--detail", "revue : F1.1")
        if override:
            self.state("override-finding", CONVOY, SLICE, "--finding", "F1.1", "--approver", APPROVER,
                       "--words", "Je passe outre : le nombre viendra avec la tranche suivante.")
        return tip

    def test_blocking_finding_overridden_by_the_operator_passes_condition_9_as_a_recorded_override(self):
        tip = self.refused_then_overridden()

        status, answer = self.merge()
        self.assertEqual((0, [SLICE]), (status, [entry["id"] for entry in answer["merged"]]), answer)
        status, answer = self.close(SLICE)

        self.assertEqual(0, status, answer)
        review = self.shown(SLICE)["gates"]["ticket_end"]["conditions"][8]
        self.assertEqual((9, "pass"), (review["number"], review["verdict"]))
        self.assertIn("dérogation enregistrée", review["detail"])
        self.assertIn("F1.1", review["detail"])
        self.assertIn(APPROVER, review["detail"])
        self.assertEqual(tip, self.shown(SLICE)["gates"]["ticket_end"]["commit"])

    def test_blocking_finding_without_override_is_not_merged_and_fails_condition_9(self):
        self.refused_then_overridden(override=False)
        before = self.remote_tip()

        status, answer = self.merge()

        self.assertEqual(([], before), (answer["merged"], self.remote_tip()), answer)
        status, answer = self.check(SLICE, "--before-merge")
        self.assertEqual((EXIT_REFUSED, [9]), (status, answer["missing"]), answer)
        self.assertIn("F1.1", answer["conditions"][8]["detail"])

    # --- AC3: the fidelity of an interface ticket, run by code before the merge ---

    def test_interface_ticket_is_measured_by_code_before_its_merge_and_condition_4_reads_that_result(self):
        tip = self.finished(SCREEN)
        status, answer = self.check(SCREEN, "--before-merge")
        self.assertEqual((EXIT_REFUSED, [4]), (status, answer["missing"]), answer)
        status, answer = self.merge()
        self.assertEqual([], answer["merged"], answer)
        self.assertEqual([SCREEN], [entry["id"] for entry in answer["waiting"]])
        self.assertIn("condition 4", answer["waiting"][0]["reason"])

        answer = self.fidelity()

        self.assertEqual([(SCREEN, tip, "vert")], [(e["id"], e["commit"], e["result"]) for e in answer["checked"]])
        shown = self.shown(SCREEN)
        self.assertEqual((tip, "vert"), (shown["fidelity"]["commit"], shown["fidelity"]["state"]))
        self.assertEqual(["accueil"], shown["fidelity"]["screens"])
        self.assertEqual(["content", "empty"], sorted(shown["fidelity"]["states"]))
        self.assertEqual(tip, shown["evidence"]["fidelity"]["commit"])
        self.assertEqual((0, []), (lambda s, a: (s, a["missing"]))(*self.check(SCREEN, "--before-merge")))

        status, answer = self.merge()
        self.assertEqual([SCREEN], [entry["id"] for entry in answer["merged"]], answer)
        status, answer = self.close(SCREEN)
        self.assertEqual(0, status, answer)
        fidelity = self.shown(SCREEN)["gates"]["ticket_end"]["conditions"][3]
        self.assertEqual((4, "pass"), (fidelity["number"], fidelity["verdict"]))
        self.assertIn(tip[:12], fidelity["detail"])

    def test_fidelity_is_not_measured_twice_at_the_same_tip(self):
        self.measured()
        before = self.snapshot()

        answer = self.fidelity()

        self.assertEqual([], answer["checked"])
        self.assertEqual(before, self.snapshot())

    def test_fidelity_measures_only_the_states_of_its_reference_the_ticket_names(self):
        """Faux si un ticket qui nomme dans ses critères une partie des états
        de sa référence est mesuré sur tous : les autres sont livrés par un
        autre ticket (T02R, af-lvhakk). Un ticket qui n'en nomme aucun reste
        mesuré sur tous (test ci-dessus)."""
        tip = self.finished(SCREEN)
        description = json.loads(self.tracker.read_text())["beads"][SCREEN]["description"]
        self.edit(SCREEN, description=description.replace("GET /", "GET /, datasets : content", 1))

        answer = self.fidelity()

        self.assertEqual([(SCREEN, tip)], [(e["id"], e["commit"]) for e in answer["checked"]], answer)
        self.assertEqual(["content"], sorted(self.shown(SCREEN)["fidelity"]["states"]))

    def test_condition_4_is_not_green_on_a_fidelity_result_of_another_commit(self):
        """Faux si la condition 4 peut être verte sans que la commande ait
        tourné sur le commit fusionné."""
        first = self.measured()
        tip = self.commit_on(SCREEN, {"docs/suite.md": "un commit de plus\n"})

        status, answer = self.check(SCREEN, "--before-merge")

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertIn(4, answer["missing"])
        detail = answer["conditions"][3]["detail"]
        self.assertIn(first[:12], detail)
        self.assertIn(tip[:12], detail)

    def test_ticket_that_touches_no_screen_passes_condition_4_without_any_measure(self):
        self.finished(SLICE)

        answer = self.fidelity()
        status, checked = self.check(SLICE, "--before-merge")

        self.assertEqual([], answer["checked"])
        self.assertEqual((0, "pass"), (status, checked["conditions"][3]["verdict"]))
        self.assertIn("sans objet", checked["conditions"][3]["detail"])
        self.assertIsNone(self.shown(SLICE)["fidelity"])

    # --- AC4: the merge command refuses while a condition before the merge is missing ---

    def test_merge_command_refuses_to_merge_while_a_condition_before_the_merge_is_missing(self):
        tip = self.measured()
        complete = self.tracker.read_bytes()
        handoff = json.loads(self.metadata(SCREEN)["gc.flow.handoff"])
        handoff["records"]["deferral_markers"] = [
            {"path": "docs/a.md", "line": 3, "marker": "FIXME", "text": "FIXME", "declared": False}]
        description = json.loads(complete)["beads"][SCREEN]["description"]
        withdrawals = {
            1: lambda: self.edit(SCREEN, description=description.replace("une ligne manque", "autre chose")),
            2: lambda: self.edit(SCREEN, unset=("gc.flow.evidence.handoff_records",)),
            3: lambda: self.edit(SCREEN, unset=("gc.flow.evaluation", "gc.flow.verdict.evaluation")),
            4: lambda: self.edit(SCREEN, unset=("gc.flow.fidelity", "gc.flow.verdict.fidelity")),
            5: lambda: self.edit(SCREEN, **{"gc.flow.handoff": json.dumps(handoff)}),
            7: lambda: self.state("add-evidence", CONVOY, SCREEN, "--piece", "piece.redigee",
                                  "--digest", "sha256:" + "cd" * 32, "--commit", tip),
            8: lambda: self.edit(SCREEN, unset=("gc.flow.tdd.red",)),
            9: lambda: self.edit(SCREEN, unset=("gc.flow.code_review", "gc.flow.verdict.code_review")),
        }
        integration = self.remote_tip()
        for number, withdraw in withdrawals.items():
            with self.subTest(condition=number):
                self.tracker.write_bytes(complete)
                withdraw()
                before = self.snapshot()

                status, answer = self.merge()

                self.assertEqual([], answer["merged"], answer)
                self.assertEqual([SCREEN], [entry["id"] for entry in answer["waiting"]], answer)
                # The evaluation and the review are first refused by the
                # merge command's own controls (T15, T14).
                named = {3: "Ticket Evaluation", 9: "revue de code"}.get(number, f"condition {number} (")
                self.assertIn(named, answer["waiting"][0]["reason"])
                self.assertEqual(integration, self.remote_tip())
                self.assertEqual(before, self.snapshot())

        self.tracker.write_bytes(complete)
        status, answer = self.merge()
        self.assertEqual((0, [SCREEN]), (status, [entry["id"] for entry in answer["merged"]]), answer)

    def test_before_the_merge_condition_6_is_not_asked(self):
        self.finished(SLICE)

        status, answer = self.check(SLICE, "--before-merge")

        self.assertEqual((0, True, []), (status, answer["ok"], answer["missing"]), answer)
        self.assertEqual("after_merge", answer["conditions"][5]["verdict"])

    # --- the convoy's settlement ---------------------------------------------

    def test_settle_closes_each_merged_ticket_whose_conditions_hold_and_names_what_keeps_the_others_open(self):
        self.merged(SLICE)
        self.merged(PREFACTORING)
        self.edit(PREFACTORING, unset=("gc.flow.code_review", "gc.flow.verdict.code_review"))
        self.finished(SCREEN)

        proc = self.gate("settle")

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertEqual([SLICE], [entry["id"] for entry in answer["closed"]])
        self.assertEqual([(PREFACTORING, [9])], [(entry["id"], entry["missing"]) for entry in answer["open"]])
        statuses = {ticket["id"]: ticket["status"] for ticket in self.show()["tickets"]}
        self.assertEqual({SLICE: "closed", PREFACTORING: "in_progress", SCREEN: "in_progress"}, statuses)

    # --- who may close ---------------------------------------------------------

    def test_agent_session_never_closes_a_ticket(self):
        """L'auteur ne ferme jamais son ticket: the gate is run by the
        order of the Factory, never from an agent session."""
        self.merged(SLICE)
        for name in ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID"):
            with self.subTest(identity=name):
                before = self.snapshot()
                for command, args in (("close", (SLICE,)), ("settle", ())):
                    proc = self.gate(command, *args, env={**self.env, name: "delivery-author-1"})
                    self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
                    self.assertIn("session d'agent", json.loads(proc.stdout)["error"])
                self.assertEqual(before, self.snapshot())

    def test_state_command_refuses_a_ticket_end_record_without_the_nine_passing_verdicts(self):
        tip = self.merged(SLICE)
        report = {"version": VERSION, "conditions": [
            {"number": number, "name": name, "verdict": "pass", "detail": "vu"} for number, name in enumerate(NAMES, start=1)]}
        failing = json.loads(json.dumps(report))
        failing["conditions"][4]["verdict"] = "fail"
        for content, mention in (
            ({**report, "conditions": report["conditions"][:8]}, "neuf"),
            (failing, "condition 5"),
            ({**report, "version": "ticket-end/v0"}, "version"),
        ):
            with self.subTest(mention=mention):
                before = self.snapshot()
                proc = self.run_cmd(STATE_TOOL, "close-ticket", CONVOY, SLICE, "--commit", tip, "--file",
                                    self.json_file("report.json", content))
                self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn(mention, json.loads(proc.stdout)["error"])
                self.assertEqual(before, self.snapshot())
        before = self.snapshot()
        proc = self.run_cmd(STATE_TOOL, "record-gate", CONVOY, SLICE, "--gate", "ticket_end", "--commit", tip)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("close-ticket", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.snapshot())

    # --- AC5: closed without the gate's record --------------------------------

    def test_ticket_closed_without_the_record_of_the_gate_is_an_etat_sans_regle(self):
        tip = self.merged(SLICE)
        self.edit(SLICE, status="closed")

        shown = self.shown(SLICE, expect=EXIT_UNRULED)
        self.assertIn("fermé hors porte", " ".join(anomaly["reason"] for anomaly in shown["unruled"]))

        # A record without the nine verdicts is not the record of the gate.
        self.edit(SLICE, **{"gc.flow.gate.ticket_end": json.dumps({"at": "2026-10-07T10:00:00Z", "commit": tip})})
        shown = self.shown(SLICE, expect=EXIT_UNRULED)
        self.assertIn("gc.flow.gate.ticket_end", " ".join(anomaly["field"] for anomaly in shown["unruled"]))
        proc = self.gate("settle")
        self.assertEqual(EXIT_UNRULED, proc.returncode, proc.stdout + proc.stderr)

    # --- AC6: a convoy without the mark ----------------------------------------

    def test_convoy_without_the_mark_is_not_touched(self):
        before = self.snapshot()
        for command, args in (("check", (PLAIN_TICKET,)), ("close", (PLAIN_TICKET,)), ("settle", ()),
                              ("fidelity", ("--profile", self.profile))):
            with self.subTest(command=command):
                proc = self.run_cmd(TOOL, command, PLAIN_CONVOY, *args, "--repo", self.repo)
                self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
