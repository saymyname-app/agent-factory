#!/usr/bin/env python3
"""bin/spec-end on a fake tracker state (T23, af-s5uysn; Spec af-wf4w5r §9,
Testing Decisions seam 2): one test per pass and per refusal, each refusal
re-reading the tracker, the evidence store and the branches to prove nothing
was written. Only command lines are exercised. The product is a copy of the
Delivery Fixture City in a throwaway repository with its own remote. The
tickets are walked to their closing by the real commands: every piece filed
and sealed by bin/evidence-capture, the merges and the takeover of the
protected branch made by bin/spec-integration, the tickets closed by
bin/ticket-end, the fidelity measured by bin/prototype-fidelity on the product
launched by bin/project-launch (with a fake browser that fetches the pages it
is given), the request of the operator raised and answered through
bin/escalation-door."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-end"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
TICKET_END_TOOL = ROOT / "bin" / "ticket-end"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = "tests/fixtures/delivery-fixture-city"
APP = f"{FIXTURE}/app.py"
PROTOTYPE = f"{FIXTURE}/prototype"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_BROWSER = ROOT / "tests" / "fixtures" / "prototype-fidelity" / "browser"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, SCREEN = "fx-t1", "fx-t2"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
VERSION = "spec-end/v2"
NAMES = ("registry", "tests", "fidelity")

EXIT_REFUSED = 1
EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4

CRITERION = "Point d'entrée : GET / — Observable : liste — Faux si : une ligne manque"
NOT_DONE = "L'export CSV de la liste n'est pas livré."
DEVIATION = "La liste est triée par nom et non par date."
SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID")
SECTIONS = {"done": ["Critère 1 observé sur GET /."], "deviations": "aucun", "not_done": "aucun",
            "out_of_ticket": "aucun"}


def branch_of(ticket):
    return f"ticket/{ticket}"


class Harness(unittest.TestCase):
    """A delivered convoy of the fixture, walked by the real commands: shared with
    tests/spec-end-review-test.py."""

    @classmethod
    def setUpClass(cls):
        # One directory for the whole class: a stage reached once (a seeded
        # city, a delivered convoy) is archived and restored at the same
        # paths, which the work trees and the remote of the product hold
        # absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="spec-end-test-"))
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
        self.root = self.tmp / "root"
        gc = self.tmp / "path" / "gc"
        self.profile = self.tmp / "descriptor.json"
        self.env = {
            **os.environ,
            "PATH": f"{self.tmp / 'path'}{os.pathsep}{os.environ['PATH']}",
            "GC_BIN": str(gc),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_WORK_DIR": str(self.work),
            "SPEC_END_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_END_WORK_DIR": str(self.tmp / "gate-work"),
            "TICKET_END_WORK_DIR": str(self.tmp / "gate-work"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "path" / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
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
        (self.root / "config").mkdir(parents=True)
        # The real `gc` finds its city from the working directory: called
        # from a merge work tree it finds none (tests/spec-integration-test.py).
        gc = self.tmp / "path" / "gc"
        gc.write_text(
            f'#!/bin/sh\ncase "$PWD/" in "{self.work}"/*) echo "gc bd: not in a city directory" >&2; exit 1;; esac\n'
            f'exec "{FAKE_GC}" "$@"\n')
        gc.chmod(0o755)
        door = self.tmp / "path" / "proposal-door"
        door.write_text("#!/bin/sh\necho 0\n")
        door.chmod(0o755)
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
        """A marked convoy of two tickets -- a slice that touches no screen
        and an interface slice, in which the publication door posed the
        reference of the Validated Prototype -- and a convoy without the mark."""
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
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, SCREEN]},
            SLICE: ticket("vertical_slice"), SCREEN: ticket("vertical_slice", interface=True),
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

    def holds(self, commit, tip):
        return subprocess.run(("git", "--git-dir", str(self.origin), "merge-base", "--is-ancestor", commit, tip),
                              env=self.env).returncode == 0

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=env or self.env, text=True, capture_output=True,
                              cwd=self.tmp)

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

    def metadata(self, bead_id):
        return json.loads(self.tracker.read_text())["beads"][bead_id].get("metadata") or {}

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

    def commit_to(self, branch, edit, message):
        """One commit pushed straight on a branch of the remote: what the
        protected branch receives from elsewhere, or a commit added to the
        integration branch after the verdicts."""
        tree = self.tmp / "elsewhere"
        self.git("fetch", "-q", "origin")
        self.git("worktree", "add", "-q", "--detach", str(tree), f"origin/{branch}")
        try:
            edit(tree)
            self.git("add", "-A", cwd=tree)
            self.git("commit", "-q", "-m", message, cwd=tree)
            self.git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=tree)
            return self.git("rev-parse", "HEAD", cwd=tree)
        finally:
            self.git("worktree", "remove", "--force", str(tree))

    def note(self, branch, name="NOTES.md"):
        return self.commit_to(branch, lambda tree: (tree / name).write_text("une note\n"), f"une note sur {branch}")

    def capture(self, ticket, piece, report=None):
        printed = json.dumps(report if report is not None else {"vu": piece}, ensure_ascii=False)
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, ticket, "--piece", piece, "--repo", self.worktree(ticket),
                            "--expect-exit", "0", "--", "printf", "%s", printed)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def finished(self, ticket, files=None):
        """A ticket walked by its author to the exit « terminé », then
        reviewed and evaluated at its tip: every step proven by a sealed
        piece, as bin/tdd-step, bin/ticket-author and bin/ticket-exit file
        them. Returns the tip."""
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.edit(ticket, status="in_progress")
        start = self.git("rev-parse", "HEAD", cwd=self.worktree(ticket))
        test = f"{FIXTURE}/tests/test_{ticket.replace('-', '_')}.py"
        red_commit = self.commit_on(ticket, {test: f"# test de critère du ticket {ticket}\n"}, "tests de critère")
        self.capture(ticket, "tdd_red", {"verdict": "red", "base": start, "seam_mode": "black_box",
                                         "tests": [{"id": f"{test}::T::test", "outcome": "failed",
                                                    "entry_points": ["GET /"]}]})
        self.state("set-tdd", CONVOY, ticket, "--step", "red", "--commit", red_commit, "--base", start)
        digests = {test: "sha256:" + hashlib.sha256((self.worktree(ticket) / test).read_bytes()).hexdigest()}
        self.state("open-test-review", CONVOY, ticket, "--commit", red_commit, "--file", self.json_file(
            f"request-{ticket}.json", {"files": digests, "criteria": {"1": [f"{test}::T::test"]}}))
        self.state("record-test-review", CONVOY, ticket, "--file", self.json_file(f"verdict-{ticket}.json", {
            "commit": red_commit, "files": digests, "tests": {f"{test}::T::test": {"state": "favorable"}},
            "recorded_by": "delivery-test-reviewer-fx"}))
        self.capture(ticket, "tdd_freeze", {"files": digests})
        self.state("set-tdd", CONVOY, ticket, "--step", "freeze", "--commit", red_commit)
        tip = self.commit_on(ticket, files or {f"docs/{ticket}.md": "la tranche\n"})
        self.capture(ticket, "tdd_green", {"verdict": "green", "k": 3, "frozen": red_commit, "seam_mode": "black_box"})
        self.state("set-tdd", CONVOY, ticket, "--step", "green", "--commit", tip)
        self.capture(ticket, "demonstration")
        self.capture(ticket, "handoff_records")
        self.state("set-handoff", CONVOY, ticket, "--file", self.json_file(f"handoff-{ticket}.json", {
            "sections": SECTIONS, "partial": False, "commit": tip, "records": {
                "exit": "finished", "branch": branch_of(ticket), "head": tip, "base": start,
                "red_proof": {"step": "red", "base": start, "commit": red_commit, "piece": "tdd_red"},
                "demonstration_proof": {"piece": "demonstration", "commit": tip, "kind": "command", "address": None},
                "deferral_markers": []}}))
        self.state("set-exit", CONVOY, ticket, "--exit", "finished")
        self.state("open-code-review", CONVOY, ticket, "--kind", "review", "--commit", tip, "--base", self.base)
        self.state("record-code-review", CONVOY, ticket, "--file", self.json_file(f"review-{ticket}.json", {
            "commit": tip, "recorded_by": "delivery-reviewer-fx", "findings": [], "answers": {}}))
        shown = self.shown(ticket)
        self.state("open-evaluation", CONVOY, ticket, "--commit", tip, "--file", self.json_file(
            f"evaluation-request-{ticket}.json", {
                "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
                "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": "/launch.json"}]}))
        self.capture(ticket, "evaluation.seen")
        self.state("record-evaluation", CONVOY, ticket, "--file", self.json_file(f"evaluation-{ticket}.json", {
            "commit": tip, "recorded_by": "delivery-evaluator-fx",
            "criteria": [{"number": number, "text": text, "state": "observed", "evidence": "evaluation.seen"}
                         for number, text in enumerate(shown["criteria"], start=1)],
            "demonstration_line": {"text": shown["demonstration_line"], "state": "observed",
                                   "evidence": "evaluation.seen"}}))
        return tip

    def closed(self, ticket, files=None):
        """A ticket finished, merged into the integration branch by the real
        merge command and closed by the real ticket-end gate."""
        self.finished(ticket, files)
        if ticket == SCREEN:
            proc = self.run_cmd(TICKET_END_TOOL, "fidelity", CONVOY, "--repo", self.repo, "--profile", self.profile)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        proc = self.run_cmd(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.repo, "--profile", self.profile)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([ticket], [entry["id"] for entry in json.loads(proc.stdout)["merged"]], proc.stdout)
        proc = self.run_cmd(TICKET_END_TOOL, "close", CONVOY, ticket, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def one_closed(self):
        """The slice is closed by its gate; the interface ticket is not started."""
        return self.stage("one-closed", lambda: self.closed(SLICE))

    def delivered(self):
        """The conforming false state: every ticket of the convoy closed by
        the ticket-end gate, the integration branch green."""
        def build():
            self.one_closed()
            self.closed(SCREEN)
        return self.stage("delivered", build)

    def verified(self):
        """The delivered convoy, the three verdicts of the gate rendered."""
        def build():
            self.delivered()
            status, answer = self.run_gate()
            self.assert_mechanical_green(status, answer)
            return answer["commit"]
        return self.stage("verified", build)

    def declare(self, ticket, **sections):
        """What the author of a closed ticket left in its Ticket Handoff."""
        handoff = json.loads(self.metadata(ticket)["gc.flow.handoff"])
        handoff["sections"].update(sections)
        self.edit(ticket, **{"gc.flow.handoff": json.dumps(handoff)})

    def gate(self, command, *args, env=None):
        proc = self.run_cmd(TOOL, command, CONVOY, "--repo", self.repo, *args, env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def run_gate(self, env=None):
        return self.gate("run", "--profile", self.profile, env=env)

    def check(self):
        return self.gate("check")

    def door(self, *args):
        proc = self.run_cmd(ESCALATION_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout

    def store_files(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*") if p.is_file() and p.name != ".seal-key")

    def snapshot(self):
        refs = subprocess.run(("git", "--git-dir", str(self.origin), "for-each-ref", "--format=%(refname) %(objectname)"),
                              env=self.env, text=True, capture_output=True).stdout
        log = self.write_log.read_text() if self.write_log.exists() else ""
        return (self.tracker.read_bytes(), self.store_files(), refs, log)

    def verdicts(self, answer):
        """The three mechanical verdicts, which the gate renders."""
        return [(entry["number"], entry["name"], entry["verdict"]) for entry in answer["conditions"][:3]]

    def review_condition(self, answer):
        """The condition the gate reads after its three verdicts: the end code review."""
        (entry,) = [entry for entry in answer["conditions"] if entry["name"] == "end_review"]
        self.assertGreater(entry["number"], len(NAMES))
        return entry

    def review_verdict(self, answer):
        return self.review_condition(answer)["verdict"]

    def assert_mechanical_green(self, status, answer):
        """The three mechanical verdicts are green and hold; the end code
        review, which no session has made on this commit, is all that is
        missing."""
        self.assertEqual((EXIT_REFUSED, False, [self.review_condition(answer)["number"]]),
                         (status, answer["ok"], answer["missing"]), answer)
        self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)], self.verdicts(answer))
        self.assertEqual("fail", self.review_verdict(answer))

    def end_reviewed(self, commit, findings=(), coverage=None, launch=True):
        """The end code review of the diff assembled at `commit`, as a
        reviewer session records it through bin/convoy-state."""
        extent = {"files": 4, "commits": 6, "insertions": 12, "deletions": 0, "digest": "sha256:" + "ab" * 32}
        self.state("open-end-review", CONVOY, "--commit", commit, "--file", self.json_file(
            "end-request.json", {"extent": extent, "reviewer": None}))
        if launch:
            self.state("launch-end-review", CONVOY, "--bead", "fx-endreview")
        return self.state("record-end-review", CONVOY, "--file", self.json_file("end-review.json", {
            "commit": commit, "recorded_by": "delivery-reviewer-fx", "findings": list(findings),
            "coverage": coverage or {"axes": ["standards", "spec"], "files": 4, "missing": []}}))

    def counters(self):
        return self.show()["convoy"]["counters"]

    def assert_refused_at_registry(self, *mentions, written=False):
        """The gate refuses on its first condition, names what it found,
        launches neither the tests nor the fidelity check, and -- unless a
        request to the operator is the one thing written -- writes nothing."""
        before = self.snapshot()
        status, answer = self.run_gate()
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertFalse(answer["ok"])
        self.assertEqual([(1, "registry", "fail"), (2, "tests", "not_run"), (3, "fidelity", "not_run")],
                         self.verdicts(answer))
        self.assertEqual("not_run", self.review_verdict(answer))
        self.assertEqual([1], answer["missing"])
        self.assertIn("condition 1", answer["error"])
        for mention in mentions:
            self.assertIn(mention, answer["error"])
        after = self.snapshot()
        # Neither a takeover of the protected branch nor a record of the gate.
        self.assertEqual(before[1:3], after[1:3])
        self.assertIsNone(self.show()["convoy"]["spec_end"])
        self.assertEqual({"end_rounds": 0}, self.counters())
        if not written:
            self.assertEqual(before, after)
        return answer


class SpecEndTest(Harness):
    # --- AC1: the three verdicts, on one commit --------------------------------

    def test_conforming_convoy_gets_three_green_verdicts_tied_to_one_integration_commit_that_holds_the_protected_tip(self):
        self.delivered()
        # The protected branch moved since the last merge: the gate takes it up.
        protected = self.note(PROTECTED)

        status, answer = self.run_gate()

        self.assert_mechanical_green(status, answer)
        self.assertEqual((VERSION, INTEGRATION), (answer["version"], answer["branch"]))
        for entry in answer["conditions"]:
            self.assertTrue(entry["detail"].strip(), entry)
        commit = answer["commit"]
        # One commit for the three: the tip of the integration branch, which
        # holds the tip of the protected branch.
        self.assertEqual(self.remote_tip(), commit)
        self.assertEqual({"branch": PROTECTED, "commit": protected}, answer["protected"])
        self.assertTrue(self.holds(protected, commit))
        record = self.show()["convoy"]["spec_end"]
        self.assertEqual((VERSION, commit, protected), (record["version"], record["commit"], record["protected"]))
        self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in record["conditions"]])
        # The fidelity verdict names what it compared; the tests their command.
        self.assertIn("regression.py", record["conditions"][1]["detail"])
        self.assertIn("accueil", record["conditions"][2]["detail"])
        self.assertEqual({"end_rounds": 0}, self.counters())
        self.assertFalse(self.show()["unruled"])

    def test_check_reads_the_recorded_verdicts_and_writes_nothing(self):
        commit = self.verified()
        before = self.snapshot()

        status, answer = self.check()

        self.assert_mechanical_green(status, answer)
        self.assertEqual((False, commit), (answer["stale"], answer["commit"]))
        self.assertEqual(before, self.snapshot())

    def test_check_before_the_first_run_says_the_verdicts_were_never_rendered(self):
        self.delivered()
        before = self.snapshot()

        status, answer = self.check()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(1, "registry", "pass"), (2, "tests", "not_run"), (3, "fidelity", "not_run")],
                         self.verdicts(answer))
        self.assertIsNone(answer["recorded"])
        self.assertEqual(before, self.snapshot())

    def test_gate_run_again_on_the_same_tip_replays_nothing_and_writes_nothing(self):
        commit = self.verified()
        before = self.snapshot()

        status, answer = self.run_gate()

        self.assert_mechanical_green(status, answer)
        self.assertEqual((commit, False), (answer["commit"], answer["replayed"]))
        self.assertEqual(before, self.snapshot())

    def test_convoy_without_interface_ticket_has_a_fidelity_verdict_that_says_so(self):
        self.delivered()
        bead = json.loads(self.tracker.read_text())["beads"][SCREEN]
        self.edit(SCREEN, description=bead["description"].split("## Validated Prototype")[0]
                  + "## Target rigs\n\nfx-rig")

        status, answer = self.run_gate()

        self.assert_mechanical_green(status, answer)
        self.assertIn("sans objet", answer["conditions"][2]["detail"])

    # --- AC6: a ticket of the convoy is still open -----------------------------

    def test_gate_called_while_a_ticket_is_still_open_refuses_and_names_it(self):
        self.one_closed()

        answer = self.assert_refused_at_registry(SCREEN, "encore ouvert")

        self.assertEqual([("open_ticket", SCREEN)], [(e["kind"], e["ticket"]) for e in answer["refused"]])

    # --- AC2: the registry refuses, the element named --------------------------

    def test_parked_ticket_is_refused_at_the_registry_and_named(self):
        self.one_closed()
        self.state("record-gate", CONVOY, SCREEN, "--gate", "dispatch")
        self.state("park", CONVOY, SCREEN, "--cause", "operator_request", "--detail", "Le secret du service manque.")

        answer = self.assert_refused_at_registry(SCREEN, "parqué", "operator_request")

        self.assertEqual([("parked", SCREEN)], [(e["kind"], e["ticket"]) for e in answer["refused"]])

    def test_open_planning_exception_is_refused_at_the_registry_and_named(self):
        self.delivered()
        self.state("raise-planning-exception", CONVOY, SLICE, "--kind", "semantic",
                   "--summary", "La Spec fixe un tri par date, le produit trie par nom.")

        answer = self.assert_refused_at_registry(SLICE, "Planning Exception ouverte", "tri par date")

        self.assertEqual([("planning_exception", SLICE)], [(e["kind"], e["ticket"]) for e in answer["refused"]])

    def test_not_done_without_final_state_is_refused_at_the_registry_named_and_raised_once_to_the_operator(self):
        self.delivered()
        self.declare(SLICE, not_done=[NOT_DONE])
        self.write_log.write_text("")

        answer = self.assert_refused_at_registry(SLICE, "non fait", NOT_DONE, "sans état final", written=True)

        self.assertEqual([("tracked_item", SLICE, "not_done.1", "ouvert")],
                         [(e["kind"], e["ticket"], e["item"], e["state"]) for e in answer["refused"]])
        # The one thing written: the request that reaches the operator, a
        # Planning Exception that names the element and the option that
        # accepts it.
        self.assertEqual([(SLICE, ["not_done.1"], True)],
                         [(r["ticket"], r["items"], r["raised"]) for r in answer["requests"]])
        raised = self.shown(SLICE)["planning_exceptions"][-1]
        self.assertEqual((["not_done.1"], "open"), (raised["items"], raised["state"]))
        listed = [line.strip() for line in self.door("list").splitlines() if line.strip().startswith(f"{SLICE} ")]
        self.assertEqual(1, len(listed), listed)
        self.assertIn(NOT_DONE, listed[0])
        mails = [json.loads(line) for line in self.write_log.read_text().splitlines() if line.startswith('["mail"')]
        self.assertEqual(1, len(mails), mails)

        # The same refusal again asks nothing more of the operator.
        before = self.snapshot()
        status, again = self.run_gate()
        self.assertEqual((EXIT_REFUSED, [1]), (status, again["missing"]), again)
        self.assertIn(NOT_DONE, again["error"])
        self.assertEqual(before, self.snapshot())

    def test_deviation_without_final_state_is_refused_at_the_registry_and_named(self):
        self.delivered()
        self.declare(SCREEN, deviations=[DEVIATION])

        answer = self.assert_refused_at_registry(SCREEN, "écart", DEVIATION, "sans état final", written=True)

        self.assertEqual([("tracked_item", SCREEN, "deviations.1")],
                         [(e["kind"], e["ticket"], e["item"]) for e in answer["refused"]])

    # --- AC3: accepted by Benjamin, through a resolved Planning Exception only ---

    def requested(self):
        """A « non fait » left without a final state, raised to the operator
        by the gate. Returns the letter of the option that accepts it."""
        self.delivered()
        self.declare(SLICE, not_done=[NOT_DONE])
        self.assertEqual(EXIT_REFUSED, self.run_gate()[0])
        return self.shown(SLICE)["planning_exceptions"][-1]["accept_option"]

    def test_not_done_becomes_accepted_by_benjamin_through_the_resolved_planning_exception_and_the_gate_passes(self):
        accept = self.requested()
        self.assertEqual("ouvert", self.shown(SLICE)["tracked_items"][0]["state"])

        self.door("repondre", SLICE, accept)

        item = self.shown(SLICE)["tracked_items"][0]
        self.assertEqual(("not_done.1", NOT_DONE, "accepté par Benjamin"), (item["id"], item["text"], item["state"]))
        status, answer = self.run_gate()
        self.assert_mechanical_green(status, answer)
        self.assertIn("accepté par Benjamin", answer["conditions"][0]["detail"])
        # The ticket the gate closed stays closed: the answer reopens nothing.
        self.assertEqual("closed", self.shown(SLICE)["status"])

    def test_planning_exception_answered_by_another_option_leaves_the_element_without_final_state(self):
        accept = self.requested()
        other = next(letter for letter in "ab" if letter != accept)

        self.door("repondre", SLICE, other)

        item = self.shown(SLICE)["tracked_items"][0]
        self.assertEqual("ouvert", item["state"])
        answer = self.assert_refused_at_registry(SLICE, NOT_DONE, "réparation demandée")
        self.assertEqual([], answer["requests"])

    def test_no_agent_command_sets_a_tracked_element_aside(self):
        self.delivered()
        self.declare(SLICE, not_done=[NOT_DONE])
        before = self.snapshot()

        # The gate itself is the Factory's: an agent session is refused.
        for identity in ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID"):
            status, answer = self.run_gate(env={**self.env, identity: "factory-worker-1"})
            self.assertEqual(EXIT_REFUSED, status, answer)
            self.assertIn("session d'agent", answer["error"])
            self.assertNotIn("conditions", answer)
        # No option of the gate accepts, waives or ignores an element.
        for option in ("--accept", "--waive", "--ignore-item", "--force"):
            proc = self.run_cmd(TOOL, "run", CONVOY, "--repo", self.repo, "--profile", self.profile, option, "not_done.1")
            self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        # A Planning Exception that is raised and not answered accepts nothing.
        self.assertEqual(before, self.snapshot())
        self.state("raise-planning-exception", CONVOY, SLICE, "--kind", "semantic", "--summary",
                   "Le non fait est sans importance.", "--item", "not_done.1", "--accept-option", "b")
        self.assertEqual("ouvert", self.shown(SLICE)["tracked_items"][0]["state"])
        # Nor does a repair named for it while the gate has not closed that repair.
        proc = self.run_cmd(STATE_TOOL, "set-item-repair", CONVOY, SLICE, "--repair", SCREEN)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertEqual("ouvert", self.shown(SLICE)["tracked_items"][0]["state"])
        self.assertEqual(EXIT_REFUSED, self.run_gate()[0])
        self.assertIsNone(self.show()["convoy"]["spec_end"])

    # --- AC4: a mechanical red creates a repair and counts a round -------------

    def break_the_tests(self):
        """The protected branch receives, from elsewhere, a commit that makes
        the regression command of the project red."""
        def edit(tree):
            app = tree / APP
            app.write_text(app.read_text().replace('<p data-anchor="fixture-generated-at">', "<p>"))
        return self.commit_to(PROTECTED, edit, "la date perd son ancre")

    def drop_the_empty_list(self, tree):
        """The empty state loses its list: the regression command, which
        reads the content state, stays green."""
        app = tree / APP
        edited = app.read_text().replace(
            """f'<ul data-anchor="fixture-items">{items_html}</ul>'""",
            """+ (f'<ul data-anchor="fixture-items">{items_html}</ul>' if items else "") +""")
        self.assertNotEqual(app.read_text(), edited)
        app.write_text(edited)

    def test_red_tests_on_the_tip_record_the_red_count_one_round_and_stop_the_gate(self):
        self.delivered()
        tip = self.remote_tip()
        protected = self.break_the_tests()

        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(1, "registry", "pass"), (2, "tests", "fail"), (3, "fidelity", "not_run")],
                         self.verdicts(answer))
        self.assertEqual([2], answer["missing"])
        self.assertIn("regression.py", answer["conditions"][1]["detail"])
        convoy = self.show()["convoy"]
        # The red is the one code repairs: recorded on the convoy with its
        # control quoted (bin/convoy-advance publishes its one repair).
        red = convoy["integration_red"]
        self.assertIn("regression.py", red["control"])
        self.assertEqual((tip, protected), (red["integration"], red["protected"]))
        self.assertEqual(red["control"], answer["red"]["control"])
        self.assertEqual({"end_rounds": 1}, convoy["counters"])
        self.assertEqual(1, answer["end_rounds"])
        # The gate does not advance: nothing is pushed, no verdict is recorded.
        self.assertEqual(tip, self.remote_tip())
        self.assertIsNone(convoy["spec_end"])

        # The same red, seen again, counts nothing more.
        before = self.snapshot()
        status, again = self.run_gate()
        self.assertEqual(EXIT_REFUSED, status, again)
        self.assertIn("branche d'intégration rouge", again["error"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual({"end_rounds": 1}, self.counters())

    def test_red_fidelity_on_the_tip_records_the_red_count_one_round_and_stop_the_gate(self):
        self.delivered()

        protected = self.commit_to(PROTECTED, self.drop_the_empty_list, "l'état vide perd sa liste")

        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(1, "registry", "pass"), (2, "tests", "pass"), (3, "fidelity", "fail")],
                         self.verdicts(answer))
        self.assertEqual([3], answer["missing"])
        detail = answer["conditions"][2]["detail"]
        self.assertIn("fixture-items", detail)
        self.assertIn("empty", detail)
        convoy = self.show()["convoy"]
        red = convoy["integration_red"]
        self.assertEqual("fidelity", red["check"])
        self.assertIn("fidélité", red["control"])
        self.assertIn("fixture-items", red["detail"])
        # Measured on the one tip the tests ran on: the protected branch taken up.
        tip = self.remote_tip()
        self.assertEqual((tip, tip, protected), (red["commit"], red["integration"], red["protected"]))
        self.assertTrue(self.holds(protected, tip))
        self.assertEqual({"end_rounds": 1}, convoy["counters"])
        self.assertIsNone(convoy["spec_end"])

    def test_deviation_on_an_anchor_benjamin_accepted_is_not_a_red_fidelity(self):
        self.delivered()
        # Accepted on the ticket, by a resolved Planning Exception that names the anchor.
        self.state("raise-planning-exception", CONVOY, SCREEN, "--kind", "semantic", "--summary",
                   "L'état vide est livré sans sa liste.", "--anchor", "fixture-items", "--accept-option", "c")
        self.edit(SCREEN, **{"gc.needs_benjamin": "none", "gc.escalation_response_option": "c",
                             "gc.escalation_response_at": "2999-01-01T00:00:00Z"})

        self.commit_to(PROTECTED, self.drop_the_empty_list, "l'état vide perd sa liste")

        status, answer = self.run_gate()

        self.assert_mechanical_green(status, answer)
        self.assertIn("accepté par Benjamin", answer["conditions"][2]["detail"])

    # --- AC5: one more commit outdates every verdict ----------------------------

    def test_commit_added_to_the_integration_branch_after_the_verdicts_makes_them_stale(self):
        commit = self.verified()
        added = self.note(INTEGRATION)
        before = self.snapshot()

        status, answer = self.check()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual((False, True, added), (answer["ok"], answer["stale"], answer["commit"]))
        self.assertEqual(commit, answer["recorded"]["commit"])
        self.assertEqual([(1, "registry", "stale"), (2, "tests", "stale"), (3, "fidelity", "stale")],
                         self.verdicts(answer))
        self.assertEqual("stale", self.review_verdict(answer))
        self.assertEqual([entry["number"] for entry in answer["conditions"]], answer["missing"])
        self.assertIn("périmé", answer["error"])
        self.assertIn("tout est à rejouer", answer["error"])
        self.assertIn(commit[:12], answer["error"])
        self.assertIn(added[:12], answer["error"])
        self.assertEqual(before, self.snapshot())

        # Replayed in full on the new tip: three fresh verdicts, on that commit.
        status, replayed = self.run_gate()
        self.assert_mechanical_green(status, replayed)
        self.assertEqual((added, True), (replayed["commit"], replayed["replayed"]))
        self.assertEqual(added, self.show()["convoy"]["spec_end"]["commit"])
        self.assertEqual((EXIT_REFUSED, False), (lambda s, a: (s, a["stale"]))(*self.check()))

    def test_protected_branch_moved_after_the_verdicts_makes_them_stale(self):
        commit = self.verified()
        moved = self.note(PROTECTED)

        status, answer = self.check()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertTrue(answer["stale"])
        self.assertIn("branche protégée", answer["error"])
        self.assertIn(moved[:12], answer["error"])
        status, replayed = self.run_gate()
        self.assert_mechanical_green(status, replayed)
        self.assertNotEqual(commit, replayed["commit"])
        self.assertTrue(self.holds(moved, replayed["commit"]))

    # --- T25: the end code review, read on the commit of the gate ------------------

    SPEC_LINE = "As Benjamin, I want la page d'accueil afficher la liste des éléments."
    BLOCKING = {"axis": "spec", "blocking": True, "summary": "Deux tickets se contredisent sur la liste affichée.",
                "citation": {"source": "spec", "quote": SPEC_LINE},
                "repair": {"title": "Afficher la liste sur la page d'accueil",
                           "what_it_delivers": "La page d'accueil affiche de nouveau la liste des éléments.",
                           "restores": {"kind": "spec_line", "ref": SPEC_LINE},
                           "demonstration_line": "Sur le produit lancé, la page d'accueil affiche la liste.",
                           "acceptance_criteria": [{"entry_point": "GET /", "observable": "la liste des éléments",
                                                    "false_if": "une ligne manque"}]}}

    def assert_refused_at_the_end_review(self, *mentions):
        """Neither `run` nor `check` passes the gate, both name the end
        review, and nothing is written."""
        before = self.snapshot()
        for status, answer in (self.run_gate(), self.check()):
            self.assert_mechanical_green(status, answer)
            self.assertIn(f"condition {self.review_condition(answer)['number']}", answer["error"])
            for mention in mentions:
                self.assertIn(mention, answer["error"])
        self.assertEqual(before, self.snapshot())

    def test_a_favorable_end_review_on_the_commit_of_the_gate_passes_its_four_conditions(self):
        commit = self.verified()
        self.end_reviewed(commit)
        before = self.snapshot()

        for status, answer in (self.run_gate(), self.check()):
            self.assertEqual((0, True, []), (status, answer["ok"], answer["missing"]), answer)
            self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)],
                             self.verdicts(answer))
            self.assertEqual("pass", self.review_verdict(answer))
            self.assertIn(commit[:12], self.review_condition(answer)["detail"])
            self.assertNotIn("error", answer)
        # The gate reads the review: it writes nothing more.
        self.assertEqual(before, self.snapshot())

    def test_gate_without_an_end_review_is_refused(self):
        self.verified()

        self.assert_refused_at_the_end_review("revue de fin absente")

    def test_gate_with_an_end_review_still_open_is_refused(self):
        commit = self.verified()
        self.state("open-end-review", CONVOY, "--commit", commit, "--file", self.json_file("end-request.json", {
            "extent": {"files": 4, "commits": 6, "insertions": 12, "deletions": 0, "digest": "sha256:" + "ab" * 32},
            "reviewer": None}))
        self.state("launch-end-review", CONVOY, "--bead", "fx-endreview")

        self.assert_refused_at_the_end_review("revue de fin en cours", "pas de verdict")

    def test_gate_with_an_end_review_that_crashed_without_result_is_refused(self):
        commit = self.verified()
        self.state("open-end-review", CONVOY, "--commit", commit, "--file", self.json_file("end-request.json", {
            "extent": {"files": 4, "commits": 6, "insertions": 12, "deletions": 0, "digest": "sha256:" + "ab" * 32},
            "reviewer": None}))
        self.state("launch-end-review", CONVOY, "--bead", "fx-endreview")
        self.state("launch-end-review", CONVOY, "--bead", "fx-endreview2")
        self.state("stop-end-review", CONVOY, "--reason", "end_review_no_result",
                   "--detail", "aucun résultat complet en 2 lancements")

        self.assert_refused_at_the_end_review("arrêtée sans verdict", "end_review_no_result")

    def test_gate_with_an_incomplete_end_review_is_refused(self):
        commit = self.verified()
        self.end_reviewed(commit, coverage={"axes": ["standards", "spec"], "files": 3, "missing": ["README.md"]})

        self.assert_refused_at_the_end_review("revue de fin en cours", "incomplète")

    def test_gate_with_an_end_review_tied_to_another_commit_is_refused_and_no_earlier_verdict_is_reused(self):
        commit = self.verified()
        self.end_reviewed(commit)
        self.assertEqual(0, self.run_gate()[0])
        # One commit more: everything is replayed, the review included.
        added = self.note(INTEGRATION)

        status, replayed = self.run_gate()

        self.assert_mechanical_green(status, replayed)
        self.assertEqual((added, True), (replayed["commit"], replayed["replayed"]))
        self.assertIn("liée à un autre commit", replayed["error"])
        self.assertIn(commit[:12], replayed["error"])
        self.assertIn("jamais réutilisé", replayed["error"])
        # Replayed in full on the new tip, it passes the gate there.
        self.end_reviewed(added)
        self.assertEqual((0, "pass"), (lambda s, a: (s, self.review_verdict(a)))(*self.run_gate()))

    def test_gate_with_a_blocking_finding_of_the_end_review_is_refused_and_names_it(self):
        commit = self.verified()
        recorded = self.end_reviewed(commit, [self.BLOCKING])
        self.assertEqual(("unfavorable", ["F1.1"]), (recorded["outcome"], recorded["blocking"]))

        self.assert_refused_at_the_end_review("Blocking Finding", "F1.1", "sans verdict favorable",
                                              "Deux tickets se contredisent", "pas encore publié")

        self.assertEqual({"end_rounds": 1}, self.counters())

    # --- what the gate is not called on ----------------------------------------

    def test_convoy_without_the_mark_is_not_touched(self):
        self.delivered()
        before = self.snapshot()

        for command in (("run", PLAIN_CONVOY, "--repo", self.repo, "--profile", self.profile),
                        ("check", PLAIN_CONVOY, "--repo", self.repo)):
            proc = self.run_cmd(TOOL, *command)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.snapshot())

    def test_convoy_in_a_state_without_rule_gets_no_verdict(self):
        self.delivered()
        # Closed outside its gate: the record of the gate is gone.
        self.edit(SLICE, unset=("gc.flow.gate.ticket_end",))
        before = self.snapshot()

        status, answer = self.run_gate()

        self.assertEqual(EXIT_UNRULED, status, answer)
        self.assertEqual([SLICE], [anomaly["ticket"] for anomaly in answer["unruled"]])
        self.assertEqual(before, self.snapshot())

    def test_run_without_profile_or_repository_is_refused(self):
        self.delivered()
        before = self.snapshot()

        proc = self.run_cmd(TOOL, "run", CONVOY, "--repo", self.repo)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertIn("--profile", json.loads(proc.stdout)["error"])
        proc = self.run_cmd(TOOL, "run", CONVOY, "--profile", self.profile)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertIn("--repo", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
