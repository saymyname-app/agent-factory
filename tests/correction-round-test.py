#!/usr/bin/env python3
"""bin/correction-round on a fake tracker state (T17, af-rx0ocp; Spec
af-wf4w5r §8, user stories 43 to 45; Testing Decisions seam 2): one test per
pass and per refusal, each refusal re-reading the tracker to prove nothing
was written. Only command lines are exercised. The product is a copy of the
Delivery Fixture City in a throwaway repository with its own remote; the
merge control is the real bin/spec-integration, a stop reaches the operator
through the real bin/escalation-door, read back from its list, and the
declared human approver is read by the real bin/project-planning-profile. No
agent runs: tests/fixtures/correction-round/author stands in for the dispatch
door and the author session it starts; the verdicts of the reviewer and of
the Evaluator are written as their sessions write them, through
bin/convoy-state."""

import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import ticket_proofs  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "correction-round"
STATE_TOOL = ROOT / "bin" / "convoy-state"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_AUTHOR = ROOT / "tests" / "fixtures" / "correction-round" / "author"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, OTHER_SLICE = "fx-t1", "fx-t2"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
RIG = "fx-rig"
APPROVER = "benjamin-hurand"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4
DIGEST = "sha256:" + "ab" * 32

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID",
                    "DELIVERY_ROLE_READ_ONLY")

TESTS = f"{FIXTURE}/tests"
TABLE = f"{TESTS}/criteria.json"
COUNT_FILE = f"{TESTS}/test_count.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
NOTE = "docs/tranche.md"

SPEC_LINE = "As Benjamin, I want la page d'accueil afficher le nombre d'éléments, so that je voie combien il y en a."
SPEC_TEXT = f"## User Stories\n\n1. {SPEC_LINE}\n\n## Testing Decisions\n\nSeams : GET / et GET /health.\n"
CRITERION = "Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
LINE = "La page d'accueil affiche 3"
TICKET_TEXT = f"""## What to build

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] {CRITERION}

## Target rigs

{RIG}"""

SECTIONS = {"done": ["Le nombre est compté côté serveur."], "deviations": "aucun", "not_done": "aucun",
            "out_of_ticket": "aucun"}
CONTRADICTS = {"axis": "spec", "blocking": True, "summary": "Le diff n'affiche jamais le nombre d'éléments.",
               "citation": {"source": "spec", "quote": SPEC_LINE}}
TASTE = {"axis": "standards", "blocking": False, "summary": "Possible Feature Envy : render() lit tout de dataset."}
NOT_SEEN = "l'ancre fixture-count est absente de la page"
WORDS = "Je passe outre : le nombre est affiché, la citation ne dit pas le contraire."


def branch_of(ticket):
    return f"ticket/{ticket}"


def staged(helper):
    """A helper whose result is built once and restored afterwards (see
    CorrectionRoundTest.stage), when a test reaches it first: it leaves only
    files (commits, steps, pieces, verdicts and, for a stopped ticket, the
    round and the stop the real settlement wrote, its author session ended),
    no process and nothing read against the clock. One stage per helper and
    per arguments. A test that did anything since its setUp gets the helper
    walked for real: a restore would wipe what the test did. The number of
    the files given so far (json_file) comes back with the stage."""
    @functools.wraps(helper)
    def reached(self, *args, **kwargs):
        if self.footprint() != self.seeded_footprint:
            return helper(self, *args, **kwargs)
        asked = json.dumps([args, kwargs], sort_keys=True, ensure_ascii=False)
        name = f"{helper.__name__}-{hashlib.sha256(asked.encode()).hexdigest()[:16]}"
        tip, self.files = self.stage(name, lambda: (helper(self, *args, **kwargs), self.files))
        return tip
    return reached


class CorrectionRoundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class (tests/spec-end-test.py): a stage
        # reached once (the seeded city, a finished slice, a slice refused by
        # both) is archived and restored at the same paths, which the
        # scripts, the settings, the work trees and the remote of the product
        # hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="correction-round-test-"))
        cls.tmp = cls.holder / "city"
        cls.stages = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.holder, ignore_errors=True)

    def stage(self, name, build):
        """The state `build` leaves, built once and restored afterwards.
        What it returns is plain and never changed: a commit, or a commit
        and a number."""
        archive = self.holder / f"{name}.tar"
        if name in self.stages:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp.mkdir()
            subprocess.run(("tar", "-C", str(self.tmp), "-xf", str(archive)), check=True)
        else:
            built = build()
            subprocess.run(("tar", "-C", str(self.tmp), "-cf", str(archive), "."), check=True)
            # Known only once its archive is whole.
            self.stages[name] = built
        return self.stages[name]

    def footprint(self):
        """Every file and folder of the test's directory with its mode, and
        for a file its size and the time it was last written: the same as
        after setUp only while the test did nothing there."""
        found = []
        for folder, folders, names in os.walk(self.tmp):
            for name in folders:
                found.append((os.path.join(folder, name), os.lstat(os.path.join(folder, name)).st_mode, 0, 0))
            for name in names:
                entry = os.lstat(os.path.join(folder, name))
                found.append((os.path.join(folder, name), entry.st_mode, entry.st_size, entry.st_mtime_ns))
        return sorted(found)

    def setUp(self):
        # No test sees what another left: an empty directory, then the stage.
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir()
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.door_log = self.tmp / "door.log"
        self.plan = self.tmp / "plan.json"
        self.briefs = self.tmp / "briefs"
        self.repo = self.tmp / "product"
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.root = self.tmp / "root"
        self.files = 0
        self.profile = self.root / "config" / "project-descriptors" / "fx.json"
        gc = self.tmp / "path" / "gc"
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
            "CORRECTION_ROUND_DISPATCH_DOOR_BIN": str(FAKE_AUTHOR),
            "CORRECTION_ROUND_FAKE_LOG": str(self.door_log),
            "CORRECTION_ROUND_FAKE_PLAN": str(self.plan),
            "CORRECTION_ROUND_FAKE_REPO": str(self.repo),
            "CORRECTION_ROUND_FAKE_BRIEFS": str(self.briefs),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.tmp / "store"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for name in ("CONVOY_STATE_FAKE_MAIL_FAIL", "PROJECT_PLANNING_PROFILE_BIN", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.base = self.stage("seeded", self.seed)
        self.seeded_footprint = self.footprint()

    def seed(self):
        """What every test starts from, left by real launches and holding
        only files: the Factory root, the stand-ins on the path, the plan of
        the author session, the marked convoy, the product with its remote
        and its integration branch. Returns the first commit of the product."""
        self.seed_root()
        (self.tmp / "path").mkdir()
        # The real `gc` finds its city from the working directory: called
        # from a merge work tree it finds none (tests/spec-integration-test.py).
        gc = self.tmp / "path" / "gc"
        gc.write_text(
            f'#!/bin/sh\ncase "$PWD/" in "{self.work}"/*) echo "gc bd: not in a city directory" >&2; exit 1;; esac\n'
            f'exec "{FAKE_GC}" "$@"\n')
        gc.chmod(0o755)
        (self.tmp / "proposal-door").write_text("#!/bin/sh\necho 0\n")
        (self.tmp / "proposal-door").chmod(0o755)
        self.author("works")
        self.seed_tracker()
        self.seed_repo()
        opened = self.run_cmd(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.repo, "--protected", PROTECTED)
        self.assertEqual(0, opened.returncode, opened.stdout + opened.stderr)
        self.write_log.write_text("")
        return self.base

    # --- harness ------------------------------------------------------------

    def seed_root(self):
        """The Factory root the command reads: the settings of the
        correction round, and the project with its declared human approver
        and its profile."""
        config = self.root / "config"
        (config / "projects").mkdir(parents=True)
        (config / "project-descriptors").mkdir()
        (config / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "start": {"formula": "mol-ticket-author", "role": "author"},
            "correction": {"formula": "mol-ticket-correction", "role": "author", "rig": "agent-factory"}}))
        (config / "projects" / f"{RIG}.toml").write_text(f'rig_dir = "{self.repo}"\nhuman_approver = "{APPROVER}"\n')
        profile = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = [RIG]
        self.profile.write_text(json.dumps(profile))

    def author(self, *plan):
        """What the author session does at each launch, the last one repeated."""
        self.plan.write_text(json.dumps(list(plan)))

    def seed_tracker(self):
        def ticket(kind="vertical_slice"):
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": TICKET_TEXT, "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, OTHER_SLICE]},
            SPEC: {"title": "Spec d'essai", "status": "open", "issue_type": "task", "description": SPEC_TEXT},
            SLICE: ticket(), OTHER_SLICE: ticket(),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket(),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY, "--demonstration-line", f"{SLICE}={LINE}",
                   "--demonstration-line", f"{OTHER_SLICE}=La sonde nomme le jeu",
                   "--user-stories", f"{SLICE}=1", "--user-stories", f"{OTHER_SLICE}=1")

    def seed_repo(self):
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        self.git("init", "-q", "-b", PROTECTED)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        subprocess.run(("git", "init", "-q", "--bare", "-b", PROTECTED, str(self.origin)), env=self.env, check=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", PROTECTED)
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *args, check=True):
        proc = subprocess.run(
            ("git", "-C", str(self.repo), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env=self.env, text=True, capture_output=True)
        if check:
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env={**self.env, **(env or {})},
                              text=True, capture_output=True, cwd=self.tmp)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def json_file(self, content):
        self.files += 1
        path = self.tmp / f"given-{self.files}.json"
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def shown(self, ticket=SLICE):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket)

    def edit(self, bead_id, status):
        state = json.loads(self.tracker.read_text())
        state["beads"][bead_id]["status"] = status
        self.tracker.write_text(json.dumps(state))

    def commit_on(self, ticket, files):
        """Add one commit to the branch of a ticket (created from the
        integration branch if new) and push it; return its SHA."""
        branch = branch_of(ticket)
        if self.git("rev-parse", "-q", "--verify", f"refs/heads/{branch}", check=False):
            self.git("checkout", "-q", branch)
        else:
            self.git("fetch", "-q", "origin")
            self.git("checkout", "-q", "-b", branch, f"origin/{INTEGRATION}")
        for path, content in files.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "travail du ticket")
        self.git("push", "-q", "origin", branch)
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        return tip

    def finish(self, ticket, tip):
        """What stands for the author's Ticket Exit « terminé » at `tip`
        (bin/ticket-exit), on a ticket green there (bin/tdd-step): each step
        with its sealed report, the demonstration, the sealed records."""
        ticket_proofs.finish(self.env, self.repo, CONVOY, ticket, tip, self.base, branch_of(ticket), sections=SECTIONS, records={
            "files_changed": [NOTE], "commits": [{"commit": tip, "subject": "travail du ticket"}], "amendment": None})

    @staged
    def finished_slice(self, ticket=SLICE):
        """A slice started through the dispatch door, whose criterion test
        is frozen, whose code is green at the tip, and whose author has
        finished there. Returns the tip."""
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.edit(ticket, "in_progress")
        table = json.dumps({"criteria": {"1": [COUNT_ID]}})
        red = self.commit_on(ticket, {COUNT_FILE: "# le test de critère du nombre\n", TABLE: table})
        tip = self.commit_on(ticket, {NOTE: "le nombre est affiché\n"})
        fingerprints = {path: DIGEST for path in (TABLE, COUNT_FILE)}
        self.state("set-tdd", CONVOY, ticket, "--step", "red", "--commit", red, "--base", self.base)
        self.state("open-test-review", CONVOY, ticket, "--commit", red, "--file",
                   self.json_file({"files": fingerprints, "criteria": {"1": [COUNT_ID]}}))
        self.state("record-test-review", CONVOY, ticket, "--file", self.json_file({
            "commit": red, "files": fingerprints, "tests": {COUNT_ID: {"state": "favorable"}},
            "recorded_by": f"delivery-reviewer-tests-{ticket}"}))
        self.state("set-tdd", CONVOY, ticket, "--step", "freeze", "--commit", red)
        self.finish(ticket, tip)
        return tip

    def reviewed(self, tip, *findings, ticket=SLICE):
        """A code review recorded at `tip`, as a reviewer session records it
        (bin/code-review, T14): unfavorable as soon as one finding blocks."""
        self.state("open-code-review", CONVOY, ticket, "--kind", "review", "--commit", tip, "--base", self.base)
        return self.state("record-code-review", CONVOY, ticket, "--file", self.json_file(
            {"commit": tip, "recorded_by": f"delivery-reviewer-{tip[:6]}", "findings": list(findings), "answers": {}}))

    def judged(self, tip, reviewed_commit, refused=(), ticket=SLICE):
        """The judgement, by a second reviewer session, of the answers given
        to the Blocking Findings of the review made at `reviewed_commit`."""
        self.state("open-code-review", CONVOY, ticket, "--kind", "judgement", "--commit", tip, "--base", reviewed_commit)
        findings = self.shown(ticket)["code_review"]["rounds"][-1]
        judgements = {finding["id"]: ({"state": "unfavorable", "reason": "le nombre n'est toujours pas rendu"}
                                      if finding["id"] in refused else {"state": "favorable"})
                      for finding in findings["findings"] if finding["blocking"]}
        return self.state("record-code-review", CONVOY, ticket, "--file", self.json_file(
            {"commit": tip, "recorded_by": f"delivery-reviewer-second-{ticket}-{tip[:6]}", "judgements": judgements}))

    def open_evaluation(self, tip, ticket=SLICE):
        self.state("open-evaluation", CONVOY, ticket, "--commit", tip, "--file", self.json_file({
            "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": "/launch.json"}]}))

    def evaluated(self, tip, observed=True, ticket=SLICE):
        """A Ticket Evaluation recorded at `tip`, as an Evaluator session
        records it (bin/ticket-evaluation, T15): the criterion observed, or
        not, each state with its piece."""
        self.open_evaluation(tip, ticket)
        ticket_proofs.capture(self.env, self.repo, CONVOY, ticket, "evaluation.seen", tip)
        criterion = {"number": 1, "text": CRITERION, "state": "observed", "evidence": "evaluation.seen"}
        if not observed:
            criterion.update(state="not_observed", reason=NOT_SEEN)
        return self.state("record-evaluation", CONVOY, ticket, "--file", self.json_file({
            "commit": tip, "recorded_by": f"delivery-evaluator-{ticket}-{tip[:6]}", "criteria": [criterion],
            "demonstration_line": {"text": LINE, "state": "observed", "evidence": "evaluation.seen"}}))

    @staged
    def refused_by_both(self):
        """A finished slice the code review refused (Blocking Finding F1.1)
        and the Ticket Evaluation refused (criterion 1 not observed), both
        at its tip. Returns the tip."""
        tip = self.finished_slice()
        self.reviewed(tip, CONTRADICTS, TASTE)
        self.evaluated(tip, observed=False)
        return tip

    def corrected(self, tip, response=None, ticket=SLICE):
        """What the author session of the correction round does: a new
        commit, an answer to the Blocking Finding, green and finished again
        at the new tip. Returns that tip."""
        new_tip = self.commit_on(ticket, {NOTE: f"le nombre est affiché, corrigé depuis {tip[:8]}\n"})
        if response is not False:
            self.state("respond-code-review", CONVOY, ticket, "--file", self.json_file(
                {"responses": {"F1.1": response or {"response": "fixed", "commit": new_tip}}}))
        self.finish(ticket, new_tip)
        return new_tip

    def settle(self, expect=0, env=None):
        proc = self.run_cmd(TOOL, "settle", CONVOY, "--repo", self.repo, env=env)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def tickets(self, entries):
        return [entry["ticket"] for entry in entries]

    @staged
    def stopped_ticket(self):
        """A ticket refused by both, whose correction session ended without
        correcting anything, and that the settlement stopped. Returns the tip."""
        tip = self.refused_by_both()
        self.author("leaves")
        self.settle()
        self.assertEqual([SLICE], self.tickets(self.settle()["stopped"]))
        return tip

    def override(self, *args, ticket=SLICE, convoy=CONVOY, env=None):
        return self.run_cmd(TOOL, "override", convoy, ticket, "--repo", self.repo, *args, env=env)

    def refused(self, *args, mention=None, status=EXIT_REFUSED, env=None):
        """A refusal: the expected exit status, one JSON answer, and nothing
        written in the tracker, no author session sent."""
        before = (self.tracker.read_bytes(), self.write_log.read_text(), self.launches())
        proc = self.run_cmd(TOOL, *args, env=env)
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertEqual(before, (self.tracker.read_bytes(), self.write_log.read_text(), self.launches()))
        text = answer.get("error") or answer.get("message")
        for part in ((mention,) if isinstance(mention, str) else mention or ()):
            self.assertIn(part, text)
        return text

    def launches(self):
        """What the dispatch door was asked, call by call."""
        if not self.door_log.exists():
            return []
        return [json.loads(line) for line in self.door_log.read_text().splitlines()]

    def brief_given(self, number=1):
        """What the preparation command handed to the author session of that launch."""
        return json.loads((self.briefs / f"brief-{number}.json").read_text())

    def escalation_list(self):
        proc = self.run_cmd(ESCALATION_TOOL, "list")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        needs = proc.stdout.split("Pending proposals")[0].splitlines()[1:]
        return [line.strip() for line in needs if line.strip() and "(none)" not in line]

    def merge(self):
        """The merge control: one pass of the real bin/spec-integration."""
        proc = self.run_cmd(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.repo, "--profile", self.profile)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def integration_tip(self):
        return subprocess.run(("git", "--git-dir", str(self.origin), "rev-parse", f"refs/heads/{INTEGRATION}"),
                              env=self.env, text=True, capture_output=True, check=True).stdout.strip()

    def tool_show(self, ticket=SLICE):
        proc = self.run_cmd(TOOL, "show", CONVOY, ticket, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    # --- the demonstration line of the ticket -----------------------------------

    def test_a_ticket_refused_by_both_gets_one_round_then_stops_as_one_item_and_takes_an_override_of_the_review_only(self):
        tip = self.refused_by_both()
        before = self.integration_tip()

        # One correction session receives the two lists.
        self.assertEqual([SLICE], self.tickets(self.settle()["launched"]))
        self.assertEqual(1, len(self.launches()))
        brief = self.brief_given()
        self.assertEqual(["F1.1"], [finding["id"] for finding in brief["code_review"]["blocking_findings"]])
        self.assertEqual(["critère 1"], [entry["what"] for entry in brief["evaluation"]["not_observed"]])

        # Still refused by both after that round: no second round, no merge,
        # one item on the list of the escalation door.
        new_tip = self.corrected(tip)
        self.judged(new_tip, tip, refused=("F1.1",))
        self.evaluated(new_tip, observed=False)
        self.assertEqual([SLICE], self.tickets(self.settle()["stopped"]))
        self.settle()
        self.assertEqual(1, len(self.launches()))
        self.assertEqual(before, self.integration_tip())
        (line,) = self.escalation_list()
        self.assertIn(SLICE, line)

        # The override of the review finding is recorded, the one of the
        # criterion that was not observed is refused.
        accepted = self.override("--finding", "F1.1", "--approved-by", APPROVER, "--words", WORDS)
        self.assertEqual(0, accepted.returncode, accepted.stdout + accepted.stderr)
        (override,) = self.tool_show()["overrides"]
        self.assertEqual(("F1.1", "dérogation enregistrée", WORDS),
                         (override["finding"], override["state"], override["words"]))
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--criterion", "1", "--approved-by", APPROVER,
                     "--words", WORDS, mention="Planning Exception")

    # --- AC1: one fresh author session receives the findings of both ---------------

    def test_the_round_is_sent_to_one_author_session_through_the_dispatch_door(self):
        tip = self.refused_by_both()

        settled = self.settle()

        (call,) = self.launches()
        self.assertEqual(["--rig", "agent-factory", "--formula", "mol-ticket-correction", "--role", "author"], call[1:])
        bead = json.loads(self.tracker.read_text())["beads"][call[0]]
        self.assertIn(f"convoy: {CONVOY}\nticket: {SLICE}", bead["description"])
        self.assertEqual([{"ticket": SLICE, "commit": tip, "bead": call[0]}], settled["launched"])
        correction = self.shown()["correction"]
        self.assertEqual((tip, [call[0]]), (correction["commit"], [launch["bead"] for launch in correction["launches"]]))

    def test_the_author_session_is_given_the_findings_of_the_review_and_what_the_evaluation_did_not_observe(self):
        tip = self.refused_by_both()

        self.settle()

        brief = self.brief_given()
        self.assertEqual((CONVOY, SLICE, tip, branch_of(SLICE)),
                         tuple(brief[name] for name in ("convoy", "ticket", "commit", "branch")))
        (finding,) = brief["code_review"]["blocking_findings"]
        self.assertEqual(("F1.1", "spec", CONTRADICTS["summary"], CONTRADICTS["citation"]),
                         tuple(finding[name] for name in ("id", "axis", "summary", "citation")))
        self.assertEqual([TASTE["summary"]],
                         [entry["summary"] for entry in brief["code_review"]["non_blocking_findings"]])
        self.assertEqual([{"what": "critère 1", "text": CRITERION, "reason": NOT_SEEN, "evidence": "evaluation.seen"}],
                         brief["evaluation"]["not_observed"])
        self.assertEqual(tip, brief["code_review"]["commit"])
        self.assertEqual(tip, brief["evaluation"]["commit"])

    def test_no_author_session_starts_while_the_evaluation_has_not_answered(self):
        tip = self.finished_slice()
        self.reviewed(tip, CONTRADICTS)
        self.open_evaluation(tip)
        writes = self.write_log.read_text()

        settled = self.settle()

        self.assertEqual([SLICE], self.tickets(settled["waiting"]))
        self.assertIn("Ticket Evaluation", settled["waiting"][0]["reason"])
        self.assertEqual(([], writes), (self.launches(), self.write_log.read_text()))
        self.assertIsNone(self.shown()["correction"])

    def test_no_author_session_starts_while_the_code_review_has_not_answered(self):
        tip = self.finished_slice()
        self.evaluated(tip, observed=False)
        writes = self.write_log.read_text()

        settled = self.settle()

        self.assertEqual([SLICE], self.tickets(settled["waiting"]))
        self.assertIn("revue de code", settled["waiting"][0]["reason"])
        self.assertEqual(([], writes), (self.launches(), self.write_log.read_text()))

    def test_a_ticket_refused_by_the_review_alone_gets_its_round_with_nothing_from_the_evaluation(self):
        tip = self.finished_slice()
        self.reviewed(tip, CONTRADICTS)
        self.evaluated(tip)

        self.assertEqual([SLICE], self.tickets(self.settle()["launched"]))

        brief = self.brief_given()
        self.assertEqual(["F1.1"], [finding["id"] for finding in brief["code_review"]["blocking_findings"]])
        self.assertEqual([], brief["evaluation"]["not_observed"])

    def test_a_ticket_refused_by_the_evaluation_alone_gets_its_round_with_nothing_from_the_review(self):
        tip = self.finished_slice()
        self.reviewed(tip, TASTE)
        self.evaluated(tip, observed=False)

        self.assertEqual([SLICE], self.tickets(self.settle()["launched"]))

        brief = self.brief_given()
        self.assertEqual([], brief["code_review"]["blocking_findings"])
        self.assertEqual(["critère 1"], [entry["what"] for entry in brief["evaluation"]["not_observed"]])

    def test_a_ticket_both_accepted_gets_no_round(self):
        tip = self.finished_slice()
        self.reviewed(tip, TASTE)
        self.evaluated(tip)
        writes = self.write_log.read_text()

        settled = self.settle()

        self.assertEqual(([], []), (settled["launched"], settled["waiting"]))
        self.assertEqual(([], writes), (self.launches(), self.write_log.read_text()))

    def test_a_second_settlement_starts_no_second_session(self):
        self.refused_by_both()
        self.settle()
        before = (self.tracker.read_bytes(), self.write_log.read_text())

        again = self.settle()

        self.assertEqual([SLICE], self.tickets(again["pending"]))
        self.assertEqual(1, len(self.launches()))
        self.assertEqual(before, (self.tracker.read_bytes(), self.write_log.read_text()))

    def test_a_launch_the_door_defers_is_tried_again_by_the_next_settlement(self):
        self.refused_by_both()
        self.author("door-defers", "works")

        deferred = self.settle()

        self.assertEqual([SLICE], self.tickets(deferred["deferred"]))
        self.assertEqual([], self.shown()["correction"]["launches"])
        self.assertEqual([SLICE], self.tickets(self.settle()["launched"]))
        self.assertEqual(1, len(self.shown()["correction"]["launches"]))
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown()["counters"])

    def test_a_launch_the_door_refuses_fails_the_settlement_and_counts_no_session(self):
        self.refused_by_both()
        self.author("door-refuses")

        refused = self.settle(expect=EXIT_REFUSED)

        self.assertEqual([SLICE], self.tickets(refused["refused"]))
        self.assertIn("rôle auteur", refused["refused"][0]["reason"])
        self.assertEqual([], self.shown()["correction"]["launches"])
        (call,) = self.launches()
        self.assertEqual("closed", json.loads(self.tracker.read_text())["beads"][call[0]]["status"])

    # --- AC5: the round counts among the resumes ---------------------------------

    def test_the_correction_round_counts_among_the_resumes_of_the_ticket(self):
        self.refused_by_both()
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, self.shown()["counters"])

        self.settle()
        self.settle()

        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown()["counters"])
        metadata = json.loads(self.tracker.read_text())["beads"][SLICE]["metadata"]
        self.assertEqual((1, 1), (metadata["gc.flow.counter.resumes"], metadata["gc.flow.counter.correction_rounds"]))
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, self.shown(OTHER_SLICE)["counters"])

    def test_the_commit_of_the_correction_is_not_counted_as_a_second_resume_by_the_merge_command(self):
        tip = self.refused_by_both()
        self.settle()
        self.corrected(tip)

        proc = self.run_cmd(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.repo, "--profile", self.profile)

        merged = json.loads(proc.stdout)
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["refused"]]))
        self.assertEqual(["code_review", "evaluation"], merged["refused"][0]["invalidated"])
        self.assertIn("aucune reprise de plus", merged["refused"][0]["reason"])
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown()["counters"])

    # --- AC2: still refused after its round, the ticket stops as one item ---------

    def test_while_the_author_corrects_nothing_is_stopped(self):
        tip = self.refused_by_both()
        self.settle()
        self.commit_on(SLICE, {NOTE: "correction en cours\n"})

        settled = self.settle()

        self.assertEqual(([SLICE], []), (self.tickets(settled["pending"]), settled["stopped"]))
        self.assertIsNone(self.shown()["stop"])
        self.assertEqual([], self.escalation_list())
        self.assertNotEqual(tip, self.shown()["tip"])

    def test_while_the_corrected_ticket_is_judged_and_evaluated_again_nothing_is_stopped(self):
        tip = self.refused_by_both()
        self.settle()
        new_tip = self.corrected(tip)
        self.open_evaluation(new_tip)

        settled = self.settle()

        self.assertEqual(([SLICE], []), (self.tickets(settled["pending"]), settled["stopped"]))
        self.assertIsNone(self.shown()["stop"])

    def test_a_ticket_corrected_and_accepted_by_both_is_merged_and_never_stopped(self):
        tip = self.refused_by_both()
        self.settle()
        new_tip = self.corrected(tip)
        self.judged(new_tip, tip)
        self.evaluated(new_tip)

        settled = self.settle()

        self.assertEqual(([], []), (settled["stopped"], settled["pending"]))
        self.assertIsNone(self.shown()["stop"])
        self.assertEqual([SLICE], [entry["id"] for entry in self.merge()["merged"]])
        self.assertEqual([], self.escalation_list())

    def test_a_ticket_whose_answers_are_judged_unfavorably_stops_without_second_round_or_merge(self):
        tip = self.refused_by_both()
        self.settle()
        new_tip = self.corrected(tip)
        self.judged(new_tip, tip, refused=("F1.1",))
        self.evaluated(new_tip)
        before = self.integration_tip()

        stopped = self.settle()

        self.assertEqual([{"ticket": SLICE, "stop": "still_refused"}], stopped["stopped"])
        stop = self.shown()["stop"]
        self.assertEqual("still_refused", stop["reason"])
        self.assertIn("F1.1", stop["detail"])
        self.assertIn("raised", stop)
        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertEqual(before, self.integration_tip())
        self.assertEqual(1, len(self.launches()))
        self.assertEqual({"resumes": 1, "correction_rounds": 1}, self.shown()["counters"])

    def test_a_ticket_still_not_observed_after_its_round_stops(self):
        tip = self.refused_by_both()
        self.settle()
        new_tip = self.corrected(tip)
        self.judged(new_tip, tip)
        self.evaluated(new_tip, observed=False)

        stopped = self.settle()

        self.assertEqual([SLICE], self.tickets(stopped["stopped"]))
        self.assertIn("critère 1", self.shown()["stop"]["detail"])
        self.assertEqual(1, len(self.launches()))

    def test_a_ticket_refused_again_by_a_review_replayed_in_full_stops(self):
        tip = self.finished_slice()
        self.reviewed(tip, TASTE)
        self.evaluated(tip, observed=False)
        self.settle()
        new_tip = self.corrected(tip, response=False)
        self.reviewed(new_tip, CONTRADICTS)
        self.evaluated(new_tip)

        stopped = self.settle()

        self.assertEqual([SLICE], self.tickets(stopped["stopped"]))
        self.assertIn("F2.1", self.shown()["stop"]["detail"])
        self.assertEqual(1, len(self.launches()))

    def test_a_stopped_ticket_is_one_item_on_the_list_of_the_escalation_door_whatever_the_number_of_settlements(self):
        tip = self.refused_by_both()
        self.settle()
        new_tip = self.corrected(tip)
        self.judged(new_tip, tip, refused=("F1.1",))
        self.evaluated(new_tip, observed=False)

        self.settle()
        before = (self.tracker.read_bytes(), self.write_log.read_text())
        again = self.settle()
        self.settle()

        (line,) = self.escalation_list()
        self.assertIn(SLICE, line)
        self.assertIn("encore refusé après son tour de correction", line)
        self.assertEqual(([], []), (again["stopped"], again["escalated"]))
        self.assertEqual(before, (self.tracker.read_bytes(), self.write_log.read_text()))
        mails = [json.loads(entry) for entry in self.write_log.read_text().splitlines() if entry.startswith('["mail"')]
        self.assertEqual(1, len(mails))

    def test_a_correction_session_that_ends_without_correcting_stops_the_ticket(self):
        self.refused_by_both()
        self.author("leaves")
        self.settle()

        stopped = self.settle()

        self.assertEqual([SLICE], self.tickets(stopped["stopped"]))
        detail = self.shown()["stop"]["detail"]
        self.assertIn("F1.1", detail)
        self.assertIn("critère 1", detail)
        self.assertEqual(1, len(self.launches()))

    def test_a_stop_the_escalation_door_could_not_take_is_raised_once_by_the_next_settlement(self):
        self.refused_by_both()
        self.author("leaves")
        self.settle()

        failed = self.settle(expect=EXIT_REFUSED, env={"CONVOY_STATE_FAKE_MAIL_FAIL": "1"})

        self.assertEqual([SLICE], self.tickets(failed["refused"]))
        self.assertNotIn("raised", self.shown()["stop"])
        self.assertEqual([SLICE], self.tickets(self.settle()["escalated"]))
        self.assertIn("raised", self.shown()["stop"])
        self.assertEqual(1, len(self.escalation_list()))
        self.assertEqual([], self.settle()["escalated"])

    def test_a_ticket_parked_or_stopped_by_another_control_gets_no_round(self):
        self.refused_by_both()
        self.state("park", CONVOY, SLICE, "--cause", "operator_request", "--detail", "un secret manque")
        writes = self.write_log.read_text()

        settled = self.settle()

        self.assertEqual(([], []), (settled["launched"], settled["waiting"]))
        self.assertEqual(([], writes), (self.launches(), self.write_log.read_text()))

    # --- brief ----------------------------------------------------------------------

    def test_brief_is_refused_on_a_ticket_without_a_correction_round(self):
        self.finished_slice()
        self.refused("brief", CONVOY, SLICE, "--repo", self.repo, mention="aucun tour de correction")

    # --- AC3: the override of a Blocking Finding of a stopped ticket ----------------

    def test_an_override_by_the_declared_human_approver_is_read_back_as_a_recorded_override(self):
        tip = self.stopped_ticket()

        proc = self.override("--finding", "F1.1", "--approved-by", APPROVER, "--words", WORDS)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertEqual(("F1.1", "dérogation enregistrée"), (answer["finding"], answer["state"]))
        for overrides in (self.tool_show()["overrides"], self.shown()["overrides"]):
            (override,) = overrides
            self.assertEqual(("F1.1", APPROVER, WORDS, tip, "dérogation enregistrée"),
                             tuple(override[name] for name in ("finding", "approver", "words", "commit", "state")))
        # Nothing is merged for all that: the ticket is still stopped.
        self.assertEqual("still_refused", self.shown()["stop"]["reason"])

    def test_an_override_is_refused_from_anyone_but_the_declared_human_approver(self):
        self.stopped_ticket()
        for other in ("mayor", "delivery-author", ""):
            self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--approved-by", other,
                         "--words", WORDS, mention="approbateur humain déclaré")
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--words", WORDS,
                     mention="approbateur humain déclaré")
        self.assertEqual([], self.shown()["overrides"])

    def test_an_override_is_refused_without_words(self):
        self.stopped_ticket()
        for words in ("", "   "):
            self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--approved-by", APPROVER,
                         "--words", words, mention="mots")
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--approved-by", APPROVER,
                     mention="mots")

    def test_an_override_is_refused_on_a_ticket_that_is_not_stopped(self):
        self.refused_by_both()
        self.settle()
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--approved-by", APPROVER,
                     "--words", WORDS, mention="n'est pas arrêté")

    def test_an_override_is_refused_for_a_finding_the_review_does_not_hold_against_the_ticket(self):
        self.stopped_ticket()
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.2", "--approved-by", APPROVER,
                     "--words", WORDS, mention="Blocking Finding")
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--approved-by", APPROVER, "--words", WORDS,
                     mention="--finding")

    def test_an_override_is_refused_when_the_approver_of_the_project_cannot_be_read(self):
        self.stopped_ticket()
        (self.root / "config" / "projects" / f"{RIG}.toml").write_text(f'rig_dir = "{self.repo}"\n')
        self.refused("override", CONVOY, SLICE, "--repo", self.repo, "--finding", "F1.1", "--approved-by", APPROVER,
                     "--words", WORDS, mention="approbateur humain")

    # --- AC4: a criterion that was not observed is never waived ---------------------

    def test_an_override_of_a_criterion_that_was_not_observed_is_refused_and_points_to_the_planning_exception(self):
        self.stopped_ticket()
        for named in (("--criterion", "1"), ("--criterion", "ligne de démonstration"), ("--finding", "critère 1")):
            text = self.refused("override", CONVOY, SLICE, "--repo", self.repo, *named, "--approved-by", APPROVER,
                                "--words", WORDS, mention="Planning Exception")
            self.assertIn("ne se dispense jamais", text)
        self.assertEqual([], self.shown()["overrides"])

    # --- a convoy without the mark ---------------------------------------------------

    def test_a_convoy_without_the_mark_is_not_touched(self):
        for args in (("settle", PLAIN_CONVOY, "--repo", self.repo),
                     ("brief", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo),
                     ("show", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo),
                     ("override", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo, "--finding", "F1.1",
                      "--approved-by", APPROVER, "--words", WORDS)):
            text = self.refused(*args, status=EXIT_NOT_NEW_FLOW)
            self.assertIn("pas un convoi du nouveau flux", text)


if __name__ == "__main__":
    unittest.main()
