#!/usr/bin/env python3
"""bin/code-review on a fake tracker state (T14, af-96cusm; Spec af-wf4w5r
§6, §8; Testing Decisions seam 2): one test per pass and per refusal, each
refusal re-reading the tracker to prove nothing was written. Only command
lines are exercised. The product is a copy of the Delivery Fixture City in a
throwaway repository with its own remote; the merge control is the real
bin/spec-integration, a stop reaches the operator through the real
bin/escalation-door, read back from its list. No agent runs:
tests/fixtures/code-review/reviewer stands in for the dispatch door and the
reviewer sessions it starts."""

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
TOOL = ROOT / "bin" / "code-review"
STATE_TOOL = ROOT / "bin" / "convoy-state"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_REVIEWER = ROOT / "tests" / "fixtures" / "code-review" / "reviewer"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, OTHER_SLICE, PREFACTORING = "fx-t1", "fx-t2", "fx-p1"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
RIG = "fx-rig"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID",
                    "DELIVERY_ROLE_READ_ONLY")

TESTS = f"{FIXTURE}/tests"
TABLE = f"{TESTS}/criteria.json"
COUNT_FILE = f"{TESTS}/test_count.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
INTERNAL_FILE = f"{TESTS}/test_render_internal.py"
RULES = "AGENTS.md"
NOTE = "docs/tranche.md"

SPEC_LINE = "As Benjamin, I want la page d'accueil afficher le nombre d'éléments, so that je voie combien il y en a."
SPEC_TEXT = f"## User Stories\n\n1. {SPEC_LINE}\n\n## Testing Decisions\n\nSeams : GET / et GET /health.\n"
RULE_LINE = "Toute fonction publique porte une docstring."
CRITERION = "Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
TICKET_TEXT = f"""## What to build

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] {CRITERION}

## Target rigs

{RIG}"""

# What the author wrote, and what a reviewer must never be given.
HANDOFF_PROSE = "PROSE-DU-HANDOFF : j'ai préféré compter côté serveur, cela me semble plus propre."
COMMIT_PROSE = "PROSE-DU-COMMIT : le relecteur peut faire confiance à ce changement"
AMENDMENT_PROSE = "PROSE-DE-L-AMENDEMENT : le test était trop strict"
SECTIONS = {"done": [HANDOFF_PROSE], "deviations": "aucun", "not_done": "aucun", "out_of_ticket": "aucun"}

CONTRADICTS = {"axis": "spec", "blocking": True, "summary": "Le diff n'affiche jamais le nombre d'éléments.",
               "citation": {"source": "spec", "quote": SPEC_LINE}}
TASTE = {"axis": "standards", "blocking": True, "summary": "Possible Feature Envy : render() lit tout de dataset."}


def sha256_of(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def branch_of(ticket):
    return f"ticket/{ticket}"


def staged(helper):
    """A helper whose result is built once and restored afterwards (see
    CodeReviewTest.stage), when a test reaches it first: it leaves only
    files (commits and steps written by the real commands), no review sent
    and nothing read against the clock. One stage per helper and per
    arguments. A test that did anything since its setUp gets the helper
    walked for real: a restore would wipe what the test did."""
    @functools.wraps(helper)
    def reached(self, *args, **kwargs):
        if self.footprint() != self.seeded_footprint:
            return helper(self, *args, **kwargs)
        asked = json.dumps([args, kwargs], sort_keys=True, ensure_ascii=False)
        name = f"{helper.__name__}-{hashlib.sha256(asked.encode()).hexdigest()[:16]}"
        return self.stage(name, lambda: helper(self, *args, **kwargs))
    return reached


class CodeReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class (tests/spec-end-test.py): a stage
        # reached once (the seeded city, a finished ticket) is archived and
        # restored at the same paths, which the scripts, the settings, the
        # work trees and the remote of the product hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="code-review-test-"))
        cls.tmp = cls.holder / "city"
        cls.stages = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.holder, ignore_errors=True)

    def stage(self, name, build):
        """The state `build` leaves, built once and restored afterwards.
        What it returns is commits: a string, or a tuple of strings."""
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
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.root = self.tmp / "root"
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
            "CODE_REVIEW_DISPATCH_DOOR_BIN": str(FAKE_REVIEWER),
            "CODE_REVIEW_FAKE_LOG": str(self.door_log),
            "CODE_REVIEW_FAKE_PLAN": str(self.plan),
            "CODE_REVIEW_FAKE_REPO": str(self.repo),
            "CODE_REVIEW_FAKE_BRIEFS": str(self.briefs),
            "DELIVERY_ROLE_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.store),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for name in ("CONVOY_STATE_FAKE_MAIL_FAIL", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.base = self.stage("seeded", self.seed)
        self.seeded_footprint = self.footprint()

    def seed(self):
        """What every test starts from, left by real launches and holding
        only files: the Factory root, the stand-ins on the path, the marked
        convoy, the product with its remote and its integration branch.
        Returns the first commit of the product."""
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
        self.reviewer("favorable")
        self.providers(reviewer="p-codex")
        self.seed_tracker()
        self.seed_repo()
        opened = self.run_cmd(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.repo, "--protected", PROTECTED)
        self.assertEqual(0, opened.returncode, opened.stdout + opened.stderr)
        self.write_log.write_text("")
        return self.base

    # --- harness ------------------------------------------------------------

    def seed_root(self):
        """The Factory root the command reads: the settings of the review,
        the delivery roles, the provider profiles and their models, and the
        profile of the project."""
        config = self.root / "config"
        (config / "projects").mkdir(parents=True)
        (config / "project-descriptors").mkdir()
        self.settings(timeout_seconds=3600)
        shutil.copy(ROOT / "config" / "delivery-roles.json", config / "delivery-roles.json")
        (config / "model-catalog.json").write_text(json.dumps({"providers": {"p-codex": {"recommended": ["gpt-5.6-sol"]}}}))
        (self.root / "city.toml").write_text(
            '[providers.p-claude]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-codex]\nargs_append = ["-m", "gpt-5.6-sol"]\n')
        (config / "projects" / f"{RIG}.toml").write_text(f'rig_dir = "{self.repo}"\n')
        profile = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = [RIG]
        profile["stacks"] = {RIG: ["fixture-stack"]}
        self.profile.write_text(json.dumps(profile))

    def settings(self, **code_review):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "start": {"formula": "mol-ticket-author", "role": "author"},
            "code_review": {"formula": "mol-code-review", "role": "reviewer", "rig": "agent-factory", **code_review}}))

    def providers(self, reviewer, author="p-claude"):
        """What bin/provider-failover answers: the provider of each role now."""
        targets = {"delivery-author": {"effective": author}}
        if reviewer:
            targets["delivery-reviewer"] = {"effective": reviewer}
        script = self.tmp / "provider-failover"
        script.write_text(f"#!/bin/sh\ncat <<'JSON'\n{json.dumps({'targets': targets})}\nJSON\n")
        script.chmod(0o755)

    def reviewer(self, *plan):
        """What the reviewer session does at each launch, the last one repeated."""
        self.plan.write_text(json.dumps(list(plan), ensure_ascii=False))

    def seed_tracker(self):
        def ticket(kind, description=TICKET_TEXT):
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": description, "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, OTHER_SLICE, PREFACTORING]},
            SPEC: {"title": "Spec d'essai", "status": "open", "issue_type": "task", "description": SPEC_TEXT},
            SLICE: ticket("vertical_slice"), OTHER_SLICE: ticket("vertical_slice"),
            PREFACTORING: ticket("prefactoring", f"## What to build\n\nRanger le rendu.\n\n## Target rigs\n\n{RIG}"),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY, "--demonstration-line", f"{SLICE}=La page d'accueil affiche 3",
                   "--demonstration-line", f"{OTHER_SLICE}=La sonde nomme le jeu",
                   "--user-stories", f"{SLICE}=1", "--user-stories", f"{OTHER_SLICE}=1")

    def seed_repo(self):
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / RULES).write_text(f"# Règles du dépôt\n\n- {RULE_LINE}\n")
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

    def test_malformed_unfinished_ticket_is_still_refused(self):
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["metadata"]["gc.flow.code_review"] = "not-json"
        self.tracker.write_text(json.dumps(tracker))
        before = self.tracker.read_bytes()
        result = self.run_cmd(TOOL, "settle", CONVOY, "--repo", self.repo)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(SLICE, result.stdout)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([], self.launches())

    def test_unfinished_tickets_need_only_the_initial_convoy_read(self):
        calls = self.tmp / "tracker-reads"
        gc = Path(self.env["GC_BIN"])
        gc.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\n'
            f'exec "{FAKE_GC}" "$@"\n')
        before = self.tracker.read_bytes()
        result = self.run_cmd(TOOL, "settle", CONVOY, "--repo", self.repo)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        reads = [line for line in calls.read_text().splitlines()
                 if f"bd show {CONVOY} --json" in line]
        self.assertEqual(1, len(reads), reads)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([], self.launches())

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env={**self.env, **(env or {})},
                              text=True, capture_output=True, cwd=self.tmp)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def json_file(self, name, content):
        path = self.tmp / name
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

    def commit_on(self, ticket, files, message=COMMIT_PROSE):
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
        self.git("commit", "-q", "--allow-empty", "-m", message)
        self.git("push", "-q", "origin", branch)
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        return tip

    def blob(self, commit, path):
        return subprocess.run(("git", "-C", str(self.repo), "show", f"{commit}:{path}"), env=self.env,
                              capture_output=True, check=True).stdout

    def started(self, ticket):
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.edit(ticket, "in_progress")

    def finish(self, ticket, tip, amendment=None, green=True):
        """What stands for the author's Ticket Exit « terminé » at `tip`
        (bin/ticket-exit): each step of its TDD with its sealed report, the
        demonstration, the sealed records, the Handoff, the exit."""
        ticket_proofs.finish(self.env, self.repo, CONVOY, ticket, tip, self.base, branch_of(ticket), green=green, sections=SECTIONS, records={
            "files_changed": [NOTE], "commits": [{"commit": tip, "subject": COMMIT_PROSE}],
            "amendment": {"commit": amendment, "reason": AMENDMENT_PROSE} if amendment else None})

    def green(self, ticket, tip):
        self.state("set-tdd", CONVOY, ticket, "--step", "green", "--commit", tip)

    @staged
    def finished_slice(self, files=None, ticket=SLICE, green=True, test_reviewed=False, satisfied=None):
        """A slice whose criterion test was proven red and frozen (no test
        review precedes the freeze, ADR-0030 L3), whose code is green at the
        tip, and whose author has finished there. `test_reviewed` leaves on
        it the review of its tests the flow recorded before L3, as on a
        ticket in flight. Returns (red commit, tip)."""
        self.started(ticket)
        table = json.dumps({"criteria": {"1": [COUNT_ID]}})
        red = self.commit_on(ticket, {COUNT_FILE: "# le test de critère du nombre\n", TABLE: table})
        tip = self.commit_on(ticket, files or {NOTE: "le nombre est affiché\n"})
        fingerprints = {path: sha256_of(self.blob(red, path)) for path in (TABLE, COUNT_FILE)}
        self.state("set-tdd", CONVOY, ticket, "--step", "red", "--commit", red, "--base", self.base)
        if test_reviewed:
            ticket_proofs.pre_l3_test_review(self.env, ticket, red, fingerprints, {COUNT_ID: {"state": "favorable"}},
                                             "delivery-reviewer-tests")
        self.state("set-tdd", CONVOY, ticket, "--step", "freeze", "--commit", red)
        # The registry the freeze seals (bin/tdd-step freeze).
        ticket_proofs.capture(self.env, self.repo, CONVOY, ticket, "tdd_freeze", red, {
            "step": "freeze", "verdict": "frozen", "commit": red, "base": self.base, "table": TABLE,
            "criteria": {"1": [COUNT_ID]}, "files": fingerprints,
            **({"satisfied": satisfied} if satisfied is not None else {})})
        self.finish(ticket, tip, green=green)
        return red, tip

    def corrected(self, files, ticket=SLICE):
        """A new commit of the author on a finished ticket, green and
        finished again at the new tip."""
        tip = self.commit_on(ticket, files)
        self.green(ticket, tip)
        self.finish(ticket, tip)
        return tip

    def settle(self, expect=0, env=None):
        proc = self.run_cmd(TOOL, "settle", CONVOY, "--repo", self.repo, env=env)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def review(self, ticket=SLICE):
        return self.shown(ticket)["code_review"]

    def tool_show(self, ticket=SLICE):
        proc = self.run_cmd(TOOL, "show", CONVOY, ticket, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def respond(self, responses, ticket=SLICE):
        return self.run_cmd(TOOL, "respond", CONVOY, ticket, "--repo", self.repo, "--file",
                            self.json_file("responses.json", {"responses": responses}))

    def responded(self, responses):
        proc = self.respond(responses)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def refused(self, *args, mention=None, status=EXIT_REFUSED, env=None):
        """A refusal: the expected exit status, one JSON answer, and nothing
        written in the tracker, no reviewer sent."""
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
        """What the preparation command handed to the reviewer session of that launch."""
        return (self.briefs / f"brief-{number}.json").read_text()

    def escalation_list(self):
        proc = self.run_cmd(ESCALATION_TOOL, "list")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        needs = proc.stdout.split("Pending proposals")[0].splitlines()[1:]
        return [line.strip() for line in needs if line.strip() and "(none)" not in line]

    def evaluated(self, ticket, commit):
        """A favorable Ticket Evaluation of the ticket at `commit`, as an
        Evaluator session records it (bin/ticket-evaluation, T15): every
        criterion and the demonstration line observed, each with its piece."""
        shown = self.shown(ticket)
        self.state("open-evaluation", CONVOY, ticket, "--commit", commit, "--file", self.json_file(
            f"evaluation-request-{ticket}.json", {
                "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
                "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": "/launch.json"}]}))
        ticket_proofs.capture(self.env, self.repo, CONVOY, ticket, "evaluation.seen", commit)
        return self.state("record-evaluation", CONVOY, ticket, "--file", self.json_file(f"evaluation-{ticket}.json", {
            "commit": commit, "recorded_by": "delivery-evaluator-fx",
            "criteria": [{"number": number, "text": text, "state": "observed", "evidence": "evaluation.seen"}
                         for number, text in enumerate(shown["criteria"], start=1)],
            "demonstration_line": {"text": shown["demonstration_line"], "state": "observed",
                                   "evidence": "evaluation.seen"}}))

    def merge(self):
        """The merge control: one pass of the real bin/spec-integration."""
        proc = self.run_cmd(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.repo, "--profile", self.profile)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def integration_tip(self):
        return subprocess.run(("git", "--git-dir", str(self.origin), "rev-parse", f"refs/heads/{INTEGRATION}"),
                              env=self.env, text=True, capture_output=True, check=True).stdout.strip()

    def record_file(self, content):
        return self.json_file("handed.json", content)

    SESSION = {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": "delivery-reviewer-fx"}

    # --- the demonstration line of the ticket -----------------------------------

    def test_a_diff_that_contradicts_a_line_of_the_spec_gets_a_cited_blocking_finding_and_is_not_merged(self):
        _, tip = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]})
        before = self.integration_tip()

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["launched"]])
        review = self.review()
        (finding,) = review["rounds"][0]["findings"]
        self.assertEqual((True, {"source": "spec", "quote": SPEC_LINE}), (finding["blocking"], finding["citation"]))
        self.assertEqual({"verdict": "unfavorable", "commit": tip, "unsettled": ["F1.1"]}, review["state"])
        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertIn("F1.1", merged["waiting"][0]["reason"])
        self.assertEqual(before, self.integration_tip())

    def test_a_finding_of_taste_without_citation_is_recorded_without_blocking_and_the_ticket_is_merged(self):
        _, tip = self.finished_slice()
        self.reviewer({"findings": [TASTE]})

        self.settle()

        review = self.review()
        (finding,) = review["rounds"][0]["findings"]
        self.assertEqual((False, TASTE["summary"]), (finding["blocking"], finding["summary"]))
        self.assertIn("refusé comme bloquant", finding["demoted"])
        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, review["state"])
        self.evaluated(SLICE, tip)
        self.assertEqual([SLICE], [entry["id"] for entry in self.merge()["merged"]])

    def test_a_review_without_output_leaves_the_ticket_unmergeable(self):
        self.finished_slice()
        self.reviewer("silent")
        before = self.integration_tip()

        self.settle()

        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertIn("revue de code", merged["waiting"][0]["reason"])
        self.assertEqual(before, self.integration_tip())

    def test_a_ticket_no_review_was_ever_opened_on_is_not_merged(self):
        self.finished_slice()
        before = self.integration_tip()

        merged = self.merge()

        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertIn("revue de code", merged["waiting"][0]["reason"])
        self.assertEqual(before, self.integration_tip())

    # --- AC1: a reviewer session of another model than the author ----------------

    def test_the_review_is_sent_to_the_reviewer_role_through_the_dispatch_door(self):
        _, tip = self.finished_slice()

        self.settle()

        (call,) = self.launches()
        self.assertEqual(["--rig", "agent-factory", "--formula", "mol-code-review", "--role", "reviewer"], call[1:])
        bead = json.loads(self.tracker.read_text())["beads"][call[0]]
        self.assertIn(f"convoy: {CONVOY}", bead["description"])
        self.assertIn(f"ticket: {SLICE}", bead["description"])
        self.assertEqual(("favorable", tip, "delivery-reviewer-fixture-1"),
                         tuple(self.review()["rounds"][0][name] for name in ("verdict", "commit", "recorded_by")))

    def test_the_models_of_the_author_and_of_the_reviewer_are_recorded_on_the_ticket(self):
        self.finished_slice()
        self.state("set-model", CONVOY, SLICE, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", "claude-opus-5-5")

        self.settle()

        ticket = self.shown()
        self.assertEqual(("delivery-reviewer", "p-codex", "gpt-5.6-sol"),
                         tuple(ticket["models"]["reviewer"][name] for name in ("agent", "provider", "model")))
        self.assertEqual({"author": "claude-opus-5-5", "reviewer": "gpt-5.6-sol", "same_model": False},
                         ticket["code_review"]["rounds"][0]["models"])
        self.assertIsNone(self.tool_show()["independence"])

    def test_a_reviewer_of_the_same_model_as_the_author_is_said_never_left_out(self):
        self.finished_slice()
        self.providers(reviewer="p-claude")
        self.state("set-model", CONVOY, SLICE, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", "claude-opus-5-5")

        self.settle()

        self.assertIs(True, self.review()["rounds"][0]["models"]["same_model"])
        self.assertIn("même modèle que l'auteur (claude-opus-5-5)", self.tool_show()["independence"])
        self.assertIn("même modèle que l'auteur", json.loads(self.brief_given())["independence"])

    def test_a_model_that_is_not_recorded_is_said_too(self):
        self.finished_slice()
        self.providers(reviewer=None)

        self.settle()

        self.assertEqual({"author": None, "reviewer": None, "same_model": None}, self.review()["rounds"][0]["models"])
        self.assertIn("non établie", self.tool_show()["independence"])

    # --- AC2: a finding blocks only with a citation that holds --------------------

    def test_a_citation_that_is_not_a_line_of_its_source_does_not_block(self):
        self.finished_slice()
        invented = {**CONTRADICTS, "citation": {"source": "spec", "quote": "La page affiche un graphique en couleurs."}}
        absent_file = {**CONTRADICTS, "citation": {"source": "repo_rule", "quote": RULE_LINE, "path": "STYLE.md"}}
        too_short = {**CONTRADICTS, "citation": {"source": "spec", "quote": "la page"}}
        self.reviewer({"findings": [invented, absent_file, too_short]})

        self.settle()

        review = self.review()
        self.assertEqual("favorable", review["state"]["verdict"])
        findings = review["rounds"][0]["findings"]
        self.assertEqual([False, False, False], [finding["blocking"] for finding in findings])
        self.assertIn("n'est pas une ligne de la Spec", findings[0]["demoted"])
        self.assertIn("STYLE.md", findings[1]["demoted"])
        self.assertIn("trop courte", findings[2]["demoted"])

    def test_a_line_of_the_ticket_and_a_written_rule_of_the_repository_are_citations_that_block(self):
        self.finished_slice()
        of_ticket = {"axis": "spec", "blocking": True, "summary": "L'ancre fixture-count est absente du rendu.",
                     "citation": {"source": "ticket", "quote": CRITERION}}
        of_rule = {"axis": "standards", "blocking": True, "summary": "count() n'a pas de docstring.",
                   "citation": {"source": "repo_rule", "quote": RULE_LINE, "path": RULES}}
        smell = {"axis": "standards", "blocking": False, "summary": "Possible Mysterious Name : n."}
        self.reviewer({"findings": [of_ticket, of_rule, smell]})

        self.settle()

        review = self.review()
        self.assertEqual(["F1.1", "F1.2"], review["state"]["unsettled"])
        self.assertEqual([True, True, False], [finding["blocking"] for finding in review["rounds"][0]["findings"]])
        self.assertNotIn("demoted", review["rounds"][0]["findings"][2])

    def test_record_refuses_a_verdict_given_by_the_reviewer(self):
        self.finished_slice()
        self.reviewer("silent")
        self.settle()
        tip = self.shown()["tip"]

        self.refused("record", CONVOY, SLICE, "--repo", self.repo, "--file",
                     self.record_file({"commit": tip, "findings": [], "answers": {}, "verdict": "favorable"}),
                     mention="calculé par du code", env=self.SESSION)

        self.assertEqual([], self.review()["rounds"])

    # --- AC4: what the review session is given ------------------------------------

    def test_the_brief_gives_the_diff_the_spec_the_ticket_the_standards_and_the_script_records(self):
        red, tip = self.finished_slice()
        self.reviewer("silent")
        self.settle()

        proc = self.run_cmd(TOOL, "brief", CONVOY, SLICE, "--repo", self.repo)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        brief = json.loads(proc.stdout)
        self.assertEqual(("review", tip, self.base, "code-review"),
                         tuple(brief[name] for name in ("kind", "commit", "base", "skill")))
        self.assertEqual((self.base, [red, tip]), (brief["diff"]["fixed_point"], brief["diff"]["commits"]))
        self.assertIn(f"diff {self.base}...{tip}", brief["diff"]["command"])
        self.assertIn({"status": "A", "path": NOTE}, brief["diff"]["files"])
        self.assertEqual((SPEC, SPEC_TEXT), (brief["spec"]["id"], brief["spec"]["text"]))
        self.assertEqual((TICKET_TEXT, [CRITERION], "La page d'accueil affiche 3"),
                         tuple(brief["ticket_text"][name] for name in ("description", "criteria", "demonstration_line")))
        self.assertEqual([RULES], brief["standards"])
        self.assertEqual(tip, brief["records"]["tdd"]["green"]["commit"])
        self.assertEqual([tip], brief["records"]["handoff_records"]["commits"])
        self.assertEqual(["standards", "spec"], brief["axes"])
        self.assertEqual(["spec", "ticket", "repo_rule"], brief["citation_sources"])

    def test_the_brief_names_design_standards_at_the_reviewed_commit(self):
        _, tip = self.finished_slice({NOTE: "le nombre est affiché\n", "DESIGN.md": "- Le focus reste visible.\n"})
        self.reviewer("silent")
        self.settle()

        brief = json.loads(self.run_cmd(TOOL, "brief", CONVOY, SLICE, "--repo", self.repo).stdout)

        self.assertEqual(tip, brief["commit"])
        self.assertEqual([RULES, "DESIGN.md"], brief["standards"])

    def test_the_brief_holds_neither_the_handoff_nor_any_prose_of_the_author(self):
        red, _ = self.finished_slice()
        tip = self.commit_on(SLICE, {COUNT_FILE: "# le test de critère du nombre, amendé\n"})
        self.state("set-tdd", CONVOY, SLICE, "--step", "amendment", "--commit", tip, "--reason", AMENDMENT_PROSE)
        self.green(SLICE, tip)
        self.finish(SLICE, tip, amendment=tip)

        self.settle()

        given = self.brief_given()
        for prose in (HANDOFF_PROSE, COMMIT_PROSE, AMENDMENT_PROSE):
            self.assertNotIn(prose.split(" : ")[0], given)
        brief = json.loads(given)
        self.assertEqual(
            {"ok", "convoy", "ticket", "kind", "commit", "base", "repo", "diff", "spec", "ticket_text", "models",
             "independence", "skill", "axes", "citation_sources", "standards", "records", "tests", "questions",
             "answers", "review_shape", "interface", "scope"}, set(brief))
        self.assertFalse(brief["interface"])
        self.assertNotIn("sections", json.dumps(brief["records"]))

    def test_brief_exposes_an_interface_ticket_to_the_reviewer_formula(self):
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["description"] += "\n\n## Validated Prototype\n\n- branche : prototype/interface\n- commit : " + self.base + "\n- chemin : prototype.html\n- états : accueil\n"
        self.tracker.write_text(json.dumps(tracker))
        self.finished_slice()
        self.settle()
        self.assertTrue(json.loads(self.brief_given())["interface"])

    def test_brief_is_refused_when_no_review_is_open(self):
        self.finished_slice()
        self.refused("brief", CONVOY, SLICE, "--repo", self.repo, mention="aucune revue")

    # --- AC6: the closed questions on the tests ------------------------------------

    def test_a_test_file_internal_to_a_seam_that_is_not_listed_is_a_blocking_finding(self):
        self.finished_slice({NOTE: "le nombre\n", INTERNAL_FILE: "from app import render  # pas par GET /\n"})
        reason = "il importe render() du produit au lieu de passer par GET /"
        self.reviewer({"no": {INTERNAL_FILE: reason}})

        self.settle()

        review = self.review()
        (question,) = [q for q in json.loads(self.brief_given())["questions"]]
        self.assertEqual(("internal_test", INTERNAL_FILE), (question["kind"], question["subject"]))
        self.assertEqual({question["id"]: {"answer": "non", "reason": reason}}, review["rounds"][0]["answers"])
        (finding,) = review["rounds"][0]["findings"]
        self.assertEqual(("tests", True, question["id"]), (finding["axis"], finding["blocking"], finding["question"]))
        self.assertIn(reason, finding["summary"])
        self.assertEqual("unfavorable", review["state"]["verdict"])

    def test_an_amended_test_that_no_longer_observes_its_criterion_is_a_blocking_finding(self):
        self.finished_slice()
        tip = self.commit_on(SLICE, {COUNT_FILE: "# le test ne lit plus l'ancre fixture-count\n"})
        self.state("set-tdd", CONVOY, SLICE, "--step", "amendment", "--commit", tip, "--reason", "test trop strict")
        ticket_proofs.capture(self.env, self.repo, CONVOY, SLICE, "tdd_amendment", tip, {
            "step": "amend", "amendment": {"reason": "test trop strict", "files": [COUNT_FILE]}})
        self.green(SLICE, tip)
        self.finish(SLICE, tip, amendment=tip)
        reason = "le test amendé ne lit plus l'ancre fixture-count"
        self.reviewer({"no": {COUNT_FILE: reason}})

        self.settle()

        (question,) = json.loads(self.brief_given())["questions"]
        self.assertEqual(("amended_test", COUNT_FILE), (question["kind"], question["subject"]))
        review = self.review()
        self.assertEqual(("unfavorable", ["F1.1"]), (review["state"]["verdict"], review["state"]["unsettled"]))
        self.assertEqual(question["id"], review["rounds"][0]["findings"][0]["question"])

    def test_the_one_review_reads_the_criterion_tests_the_freeze_sealed_without_any_test_review(self):
        """ADR-0030 L3: no test review before the freeze; the code review is
        given the criterion tests, their table and their criteria."""
        self.finished_slice()

        self.settle()

        self.assertIsNone(self.shown()["test_review"])
        tests = json.loads(self.brief_given())["tests"]
        self.assertEqual({"1": [COUNT_ID]}, tests["criterion_tests"])
        self.assertEqual(sorted([TABLE, COUNT_FILE]), sorted(tests["frozen"]))
        self.assertEqual([], tests["amended"])

    def test_the_brief_names_the_criteria_satisfied_by_the_existing_code(self):
        """ADR-0030 L5: a satisfied criterion was never proven red; the
        reviewer is told which, to check its test really observes it."""
        self.finished_slice(satisfied=["1"])

        self.settle()

        self.assertEqual(["1"], json.loads(self.brief_given())["tests"]["satisfied"])

    def test_a_ticket_whose_tests_are_the_frozen_ones_is_asked_no_closed_question(self):
        self.finished_slice()

        self.settle()

        self.assertEqual([], json.loads(self.brief_given())["questions"])
        self.assertEqual({}, self.review()["rounds"][0]["answers"])

    # --- AC3: fixed or contested, judged by a second reviewer session -------------

    def test_every_blocking_finding_fixed_and_judged_favorably_by_a_second_session_lets_the_merge_through(self):
        _, reviewed = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]}, "favorable")
        self.settle()
        tip = self.corrected({NOTE: "le nombre est affiché : 3\n"})
        self.responded({"F1.1": {"response": "fixed", "commit": tip}})

        settled = self.settle()

        self.assertEqual([("judgement", tip)], [(entry["kind"], entry["commit"]) for entry in settled["launched"]])
        review = self.review()
        self.assertEqual(["review", "judgement"], [round_["kind"] for round_ in review["rounds"]])
        self.assertEqual(["delivery-reviewer-fixture-1", "delivery-reviewer-fixture-2"],
                         [round_["recorded_by"] for round_ in review["rounds"]])
        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, review["state"])
        judgement = json.loads(self.brief_given(2))
        self.assertEqual(("judgement", tip, reviewed, ["F1.1"]),
                         (judgement["kind"], judgement["commit"], judgement["base"],
                          [finding["id"] for finding in judgement["findings"]]))
        self.assertEqual("fixed", judgement["responses"]["F1.1"]["response"])
        self.evaluated(SLICE, tip)
        self.assertEqual([SLICE], [entry["id"] for entry in self.merge()["merged"]])

    def test_a_contested_finding_is_judged_at_the_same_commit(self):
        _, tip = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]}, "favorable")
        self.settle()
        self.responded({"F1.1": {"response": "contested", "reason": "La story parle du nombre, que GET / affiche déjà."}})

        self.settle()

        review = self.review()
        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, review["state"])
        self.assertEqual(tip, review["rounds"][1]["base"])

    def test_a_finding_judged_unfavorably_keeps_the_ticket_out_of_the_merge_and_opens_nothing_more(self):
        self.finished_slice()
        still = "le correctif n'affiche toujours pas le nombre"
        self.reviewer({"findings": [CONTRADICTS]}, {"judgements": {"F1.1": still}})
        self.settle()
        tip = self.corrected({NOTE: "toujours pas de nombre\n"})
        self.responded({"F1.1": {"response": "fixed", "commit": tip}})
        self.settle()
        self.assertEqual({"verdict": "unfavorable", "commit": tip, "unsettled": ["F1.1"]}, self.review()["state"])

        again = self.settle()

        self.assertEqual([], again["launched"])
        self.assertIn("tour de correction", again["waiting"][0]["reason"])
        self.assertEqual(2, len(self.launches()))
        self.assertEqual([], self.merge()["merged"])

    def test_a_judgement_left_unfavorable_and_overridden_is_reviewed_in_full_at_a_later_tip(self):
        # 22/10/2026, F and G1 of af-strhoy: every unsettled Blocking Finding
        # overridden, the ticket resumed and finished at a new tip; the merge
        # waited for a review of that tip which was never opened.
        self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]}, {"judgements": {"F1.1": "le nombre manque toujours"}}, "favorable")
        self.settle()
        judged = self.corrected({NOTE: "toujours pas de nombre\n"})
        self.responded({"F1.1": {"response": "fixed", "commit": judged}})
        self.settle()
        self.state("stop-ticket", CONVOY, SLICE, "--reason", "still_refused", "--detail", "revue de code (F1.1)")
        self.state("stop-raised", CONVOY, SLICE)
        self.state("override-finding", CONVOY, SLICE, "--finding", "F1.1", "--approver", "benjamin-hurand",
                   "--words", "Je passe outre F1.1.")
        self.state("open-resume", CONVOY, SLICE, "--cause", "returned", "--ref", "merge:essai")
        tip = self.corrected({NOTE: "le nombre est affiché : 3\n"})

        settled = self.settle()

        self.assertEqual([("review", tip)], [(entry["kind"], entry["commit"]) for entry in settled["launched"]])
        # ADR-0034: an override settles the finding; the review of that tip is targeted.
        scope = json.loads(self.brief_given(3))["scope"]
        self.assertEqual((judged, []), (scope["from"], scope["unsettled"]))

    def test_blocking_findings_without_an_answer_wait_and_no_judgement_is_sent(self):
        _, reviewed = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()
        self.evaluated(SLICE, reviewed)
        self.state("open-correction", CONVOY, SLICE, "--commit", reviewed)
        self.corrected({NOTE: "le nombre est affiché : 3\n"})

        settled = self.settle()

        self.assertEqual([], settled["launched"])
        self.assertIn("F1.1", settled["waiting"][0]["reason"])
        self.assertEqual(1, len(self.launches()))

    def test_an_unfavorable_review_outdated_before_any_correction_round_is_replayed_in_full_at_the_tip(self):
        # af-s31cvi (T02, 17/10): an author resumed outside the correction
        # round finished again at a new tip. Nobody answers the old
        # findings there: the review is replayed, not left waiting for them.
        _, first = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]}, "favorable")
        self.settle()
        tip = self.corrected({NOTE: "le nombre est affiché : 3\n"})

        settled = self.settle()

        self.assertEqual([("review", tip)], [(entry["kind"], entry["commit"]) for entry in settled["launched"]])
        review = self.review()
        self.assertEqual([("review", first), ("review", tip)], [(r["kind"], r["commit"]) for r in review["rounds"]])
        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, review["state"])

    # --- ADR-0034: a review after the first one is targeted ---------------------------

    def test_a_later_review_blocks_only_on_unsettled_findings_and_changed_lines_and_keeps_the_rest_for_the_end(self):
        # D (af-ten1sp, 22/10) and C1 (af-lzti7w, 21/10): a review replayed in
        # full found defects present at the first pass, and stopped them.
        _, first = self.finished_slice()
        carried = {**CONTRADICTS, "carries": "F1.1"}
        on_changed = {"axis": "spec", "blocking": True, "summary": "La note ne nomme pas l'ancre fixture-count.",
                      "citation": {"source": "ticket", "quote": CRITERION}, "location": {"path": NOTE, "line": 1}}
        missed_before = {"axis": "standards", "blocking": True, "summary": "La table des critères n'a pas de docstring.",
                         "citation": {"source": "repo_rule", "quote": RULE_LINE, "path": RULES},
                         "location": {"path": TABLE, "line": 1}}
        self.reviewer({"findings": [CONTRADICTS]}, {"findings": [carried, on_changed, missed_before]})
        self.settle()
        tip = self.corrected({NOTE: "le nombre est affiché : 3\n"})

        self.settle()

        scope = json.loads(self.brief_given(2))["scope"]
        self.assertEqual((first, ["F1.1"], {NOTE: [[1, 1]]}),
                         (scope["from"], [finding["id"] for finding in scope["unsettled"]], scope["changed"]))
        review = self.review()
        self.assertEqual({"verdict": "unfavorable", "commit": tip, "unsettled": ["F2.1", "F2.2"]}, review["state"])
        kept = review["rounds"][1]["findings"][2]
        self.assertEqual((False, True), (kept["blocking"], kept["finishing_pass"]))
        self.assertIn("passe de fin", kept["demoted"])
        self.assertEqual(["F2.3"], [finding["id"] for finding in self.tool_show()["finishing_pass"]])

    def test_the_commits_of_the_integration_taken_in_are_not_lines_of_the_ticket_for_a_targeted_review(self):
        _, first = self.finished_slice()
        self.reviewer("favorable")
        self.settle()
        other = "docs/autre-ticket.md"
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-B", "essai-integration", f"origin/{INTEGRATION}")
        (self.repo / other).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / other).write_text("le travail d'un autre ticket\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "autre ticket fusionné")
        self.git("push", "-q", "origin", f"HEAD:{INTEGRATION}")
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", branch_of(SLICE))
        self.git("merge", "-q", "--no-edit", f"origin/{INTEGRATION}")
        (self.repo / NOTE).write_text("le nombre est affiché : 3\n")
        self.git("commit", "-q", "-am", "reprise")
        self.git("push", "-q", "origin", branch_of(SLICE))
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        self.green(SLICE, tip)
        self.finish(SLICE, tip)

        self.settle()

        scope = json.loads(self.brief_given(2))["scope"]
        self.assertEqual((first, [], {NOTE: [[1, 1]]}), (scope["from"], scope["unsettled"], scope["changed"]))

    def test_the_first_review_of_a_ticket_is_complete_and_takes_no_targeted_scope(self):
        _, tip = self.finished_slice()
        self.reviewer("silent")
        self.settle()
        brief = self.run_cmd(TOOL, "brief", CONVOY, SLICE, "--repo", self.repo)
        self.assertIsNone(json.loads(brief.stdout)["scope"])
        scoped = self.json_file("scope.json", {"questions": [], "scope": {"from": tip, "unsettled": [], "changed": {}}})
        before = self.tracker.read_bytes()

        proc = self.run_cmd(STATE_TOOL, "open-code-review", CONVOY, SLICE, "--kind", "review", "--commit", tip,
                            "--base", self.base, "--file", scoped)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("premier passage est une revue complète", proc.stdout)
        self.assertEqual(before, self.tracker.read_bytes())

    def test_the_amended_test_question_leaves_the_visual_fidelity_to_the_prototype_out(self):
        # D (af-ten1sp) F3.7, 22/10, and G1 (af-wrxrmg) F1.12, 21/10: « non »
        # on an amended test for « Rendu fidèle à la référence », against ADR-0032.
        self.finished_slice()
        tip = self.commit_on(SLICE, {COUNT_FILE: "# le test ne compare plus la capture au prototype\n"})
        self.state("set-tdd", CONVOY, SLICE, "--step", "amendment", "--commit", tip, "--reason", "capture trop stricte")
        ticket_proofs.capture(self.env, self.repo, CONVOY, SLICE, "tdd_amendment", tip, {
            "step": "amend", "amendment": {"reason": "capture trop stricte", "files": [COUNT_FILE]}})
        self.green(SLICE, tip)
        self.finish(SLICE, tip, amendment=tip)

        self.settle()

        (question,) = json.loads(self.brief_given())["questions"]
        self.assertEqual("amended_test", question["kind"])
        self.assertIn("La fidélité visuelle au prototype n'est pas jugée ici (ADR-0032)", question["text"])

    def test_respond_refuses_a_correction_commit_that_does_not_follow_the_reviewed_commit(self):
        red, _ = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()
        for commit, mention in ((red, "ne suit pas"), ("0" * 40, "introuvable")):
            self.refused("respond", CONVOY, SLICE, "--repo", self.repo, "--file",
                         self.json_file("responses.json", {"responses": {"F1.1": {"response": "fixed", "commit": commit}}}),
                         mention=mention)
        self.refused("respond", CONVOY, SLICE, "--repo", self.repo, "--file",
                     self.json_file("responses.json", {"responses": {}}), mention="F1.1")

    # --- AC5: a review that crashed, timed out or gave no output -------------------

    def test_a_review_still_running_is_pending_and_is_not_launched_again(self):
        self.finished_slice()
        self.reviewer("silent")

        first = self.settle()
        second = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in first["launched"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in second["pending"]])
        self.assertEqual(1, len(self.launches()))
        self.assertIsNone(self.shown()["stop"])

    def test_a_review_without_result_is_not_passed_and_is_launched_once_more(self):
        self.finished_slice()
        self.reviewer("silent", "favorable")
        self.settle()
        self.settings(timeout_seconds=0)

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["relaunched"]])
        self.assertEqual("favorable", self.review()["state"]["verdict"])
        self.assertNotEqual(self.launches()[0][0], self.launches()[1][0])

    def test_a_review_without_result_twice_stops_the_ticket_and_raises_it_once(self):
        self.finished_slice()
        self.reviewer("silent")
        self.settings(timeout_seconds=0)
        self.settle()
        self.settle()

        stopped = self.settle()
        again = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in stopped["stopped"]])
        self.assertEqual(([], [], []), (again["stopped"], again["escalated"], again["launched"]))
        self.assertEqual("code_review_no_result", self.shown()["stop"]["reason"])
        self.assertEqual(2, len(self.launches()))
        requests = self.escalation_list()
        self.assertEqual(1, len(requests), requests)
        self.assertTrue(requests[0].startswith(f"{SLICE} — "), requests)
        self.assertIn("revue de code", requests[0])
        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))

    def test_a_reviewer_that_closes_its_bead_without_a_verdict_is_a_review_without_result(self):
        self.finished_slice()
        self.reviewer("closed", "favorable")
        self.settle()

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["relaunched"]])
        self.assertEqual("favorable", self.review()["state"]["verdict"])

    def test_a_stop_whose_request_did_not_reach_the_operator_is_raised_by_the_next_call(self):
        self.finished_slice()
        self.reviewer("silent")
        self.settings(timeout_seconds=0)
        self.settle()
        self.settle()
        failed = self.settle(expect=EXIT_REFUSED, env={"CONVOY_STATE_FAKE_MAIL_FAIL": "1"})
        self.assertIn("porte d'escalade", failed["refused"][0]["reason"])
        self.assertNotIn("raised", self.shown()["stop"])

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["escalated"]])
        self.assertEqual(1, len(self.escalation_list()))

    def test_a_dispatch_the_door_refuses_counts_no_launch(self):
        self.finished_slice()
        self.reviewer("door-refuses")

        settled = self.settle(expect=EXIT_REFUSED)

        self.assertIn("rôle relecteur", settled["refused"][0]["reason"])
        self.assertEqual([], self.review()["request"]["launches"])
        self.assertIsNone(self.shown()["stop"])
        beads = json.loads(self.tracker.read_text())["beads"]
        self.assertEqual("closed", beads[self.launches()[0][0]]["status"])

    def test_a_dispatch_the_door_defers_is_retried_by_the_next_pass_and_is_no_failure_of_it(self):
        self.finished_slice()
        self.reviewer("door-defers", "favorable")

        first = self.settle()
        second = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in first["deferred"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in second["launched"]])
        self.assertEqual("favorable", self.review()["state"]["verdict"])

    # --- when a review is due ------------------------------------------------------

    def test_no_review_is_opened_on_a_ticket_whose_author_has_not_finished_at_the_tip(self):
        self.finished_slice()
        self.commit_on(SLICE, {NOTE: "un commit de plus, sans sortie\n"})

        settled = self.settle()

        self.assertEqual([], settled["launched"])
        self.assertIn("n'est pas terminé à la pointe", settled["waiting"][0]["reason"])
        self.assertIsNone(self.review())

    def test_no_review_is_opened_on_a_ticket_that_is_not_proven_green_at_the_tip(self):
        self.finished_slice(green=False)

        settled = self.settle()

        self.assertEqual(([], []), (settled["launched"], self.launches()))
        self.assertIn("vert", settled["waiting"][0]["reason"])

    def integration_moved(self):
        """One commit more on the integration branch of the Spec, as the
        merge of another ticket leaves it; return the new tip."""
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "--detach", f"origin/{INTEGRATION}")
        (self.repo / "AUTRE.md").write_text("un autre ticket a fusionné\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "un autre ticket fusionne")
        self.git("push", "-q", "origin", f"HEAD:refs/heads/{INTEGRATION}")
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        return tip

    def test_no_review_is_launched_on_a_branch_that_has_not_taken_the_integration_tip(self):
        _, tip = self.finished_slice()
        integration = self.integration_moved()
        before = (self.tracker.read_bytes(), self.write_log.read_text())

        settled = self.settle(expect=EXIT_REFUSED)

        self.assertFalse(settled["ok"])
        self.assertEqual([(SLICE, "behind", integration, tip)],
                         [(r["ticket"], r["cause"], r["integration"], r["commit"]) for r in settled["refused"]])
        self.assertIn(integration[:12], settled["refused"][0]["reason"])
        self.assertIn(tip[:12], settled["refused"][0]["reason"])
        self.assertEqual((before, [], []),
                         ((self.tracker.read_bytes(), self.write_log.read_text()), settled["launched"], self.launches()))
        self.assertIsNone(self.review())
        self.assertIsNone(self.shown().get("verdicts", {}).get("code_review"))
        self.assertEqual({"integration": integration, "commit": tip}, self.tool_show()["behind"])

    def test_a_branch_that_took_the_integration_tip_is_reviewed_as_before(self):
        self.started(SLICE)
        integration = self.integration_moved()
        tip = self.commit_on(SLICE, {NOTE: "parti de la pointe courante\n"})
        self.finish(SLICE, tip)

        settled = self.settle()

        self.assertEqual([(SLICE, tip)], [(r["ticket"], r["commit"]) for r in settled["launched"]])
        self.assertEqual([(integration, tip, "favorable")],
                         [(r["base"], r["commit"], r["verdict"]) for r in self.review()["rounds"]])
        self.assertIsNone(self.tool_show()["behind"])

    def test_a_review_already_sent_is_awaited_when_the_integration_branch_moves(self):
        self.finished_slice()
        self.reviewer("silent")
        self.settle()
        self.integration_moved()

        settled = self.settle()

        self.assertEqual(([], [SLICE]), (settled["refused"], [r["ticket"] for r in settled["pending"]]))
        self.assertIsNone(self.tool_show()["behind"])

    def test_a_ticket_that_is_not_finished_stopped_or_parked_is_left_alone(self):
        self.started(OTHER_SLICE)
        self.commit_on(OTHER_SLICE, {NOTE: "en cours\n"})
        self.finished_slice()
        self.state("stop-ticket", CONVOY, SLICE, "--reason", "amendment_exhausted", "--detail", "second amendement")
        before = self.tracker.read_bytes()

        settled = self.settle()

        self.assertEqual({"launched": [], "waiting": [], "escalated": []},
                         {name: settled[name] for name in ("launched", "waiting", "escalated")})
        self.assertEqual((before, []), (self.tracker.read_bytes(), self.launches()))

    def test_a_prefactoring_is_reviewed_once_its_regression_is_proven_at_the_tip(self):
        self.started(PREFACTORING)
        tip = self.commit_on(PREFACTORING, {NOTE: "rendu rangé\n"})
        self.state("set-tdd", CONVOY, PREFACTORING, "--step", "prefactoring", "--commit", tip, "--base", self.base)
        self.finish(PREFACTORING, tip)

        self.settle()

        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, self.review(PREFACTORING)["state"])

    def test_a_commit_added_after_a_favorable_review_has_it_replayed_in_full_on_the_new_tip(self):
        _, first = self.finished_slice()
        self.settle()
        self.assertEqual({"launched": [], "pending": [], "waiting": []},
                         {name: self.settle()[name] for name in ("launched", "pending", "waiting")})
        tip = self.corrected({NOTE: "le nombre, après reprise de la pointe d'intégration\n"})

        settled = self.settle()

        self.assertEqual([("review", tip)], [(entry["kind"], entry["commit"]) for entry in settled["launched"]])
        review = self.review()
        self.assertEqual([("review", first), ("review", tip)], [(r["kind"], r["commit"]) for r in review["rounds"]])
        self.assertEqual(self.base, review["rounds"][1]["base"])

    def test_a_review_opened_on_a_commit_the_author_has_since_left_is_replaced_by_one_at_the_tip(self):
        self.finished_slice()
        self.reviewer("silent", "favorable")
        self.settle()
        tip = self.corrected({NOTE: "le nombre, corrigé avant le verdict\n"})

        self.settle()

        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, self.review()["state"])

    # --- what the commands refuse ----------------------------------------------------

    def test_record_is_refused_outside_a_read_only_reviewer_session(self):
        _, tip = self.finished_slice()
        self.reviewer("silent")
        self.settle()

        self.refused("record", CONVOY, SLICE, "--repo", self.repo, "--file",
                     self.record_file({"commit": tip, "findings": [], "answers": {}}), mention="lecture seule", env={})

        self.assertEqual([], self.review()["rounds"])

    def test_record_refuses_a_review_given_on_a_commit_that_is_no_longer_under_review(self):
        _, first = self.finished_slice()
        self.reviewer("silent")
        self.settle()
        self.corrected({NOTE: "le nombre, corrigé avant le verdict\n"})
        self.settle()

        self.refused("record", CONVOY, SLICE, "--repo", self.repo, "--file",
                     self.record_file({"commit": first, "findings": [], "answers": {}}), mention="commit",
                     env=self.SESSION)

    def test_a_convoy_without_the_mark_is_not_touched(self):
        for command in (("settle", PLAIN_CONVOY, "--repo", self.repo), ("brief", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo),
                        ("show", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo), ("settle", PLAIN_CONVOY)):
            text = self.refused(*command, status=EXIT_NOT_NEW_FLOW)
            self.assertIn("pas un convoi du nouveau flux", text)

    def test_settle_finds_the_repository_of_the_project_the_tickets_name(self):
        _, tip = self.finished_slice()

        proc = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual({"verdict": "favorable", "commit": tip, "unsettled": []}, self.review()["state"])

    def test_show_gives_the_rounds_the_state_and_the_verdict(self):
        _, tip = self.finished_slice()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()

        answer = self.tool_show()

        self.assertEqual((tip, None, None), (answer["tip"], answer["request"], answer["stop"]))
        self.assertEqual({"verdict": "unfavorable", "commit": tip, "unsettled": ["F1.1"]}, answer["state"])
        self.assertEqual(("unfavorable", True), (answer["verdict"]["state"], answer["verdict"]["valid"]))


    # --- T42: a fresh session per review ------------------------------------------

    def beads(self):
        """The tracker, each code review record decoded, the mark of a launch
        counted without result set apart."""
        beads = json.loads(self.tracker.read_text())["beads"]
        counted = {}
        for bead_id, bead in beads.items():
            raw = (bead.get("metadata") or {}).get("gc.flow.code_review")
            if raw is None:
                continue
            record = json.loads(raw)
            for launch in (record.get("request") or {}).get("launches") or []:
                if "refused" in launch:
                    counted.setdefault(bead_id, []).append(launch.pop("refused")["session"])
            bead["metadata"]["gc.flow.code_review"] = record
        return beads, counted

    def review_open(self):
        """The code review of SLICE launched and left without an answer:
        what a session would hand in, and the session that rendered the
        review of the tests of that ticket."""
        _, tip = self.finished_slice(test_reviewed=True)
        self.reviewer("silent")
        self.settle()
        (served,) = [round_["recorded_by"] for round_ in self.shown()["test_review"]["rounds"]]
        handed = ("record", CONVOY, SLICE, "--repo", self.repo, "--file",
                  self.record_file({"commit": tip, "findings": [], "answers": {}}))
        return handed, {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": served}

    def test_a_review_from_a_session_that_rendered_another_review_of_the_convoy_is_refused_and_counted_without_result(self):
        handed, session = self.review_open()
        before, _ = self.beads()
        sent = self.launches()

        proc = self.run_cmd(TOOL, *handed, env=session)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        text = json.loads(proc.stdout)["error"]
        self.assertIn(session["GC_SESSION_NAME"], text)
        self.assertIn("session neuve", text)
        after, counted = self.beads()
        self.assertEqual({SLICE: [session["GC_SESSION_NAME"]]}, counted)
        self.assertEqual(before, after)
        self.assertEqual(sent, self.launches())
        self.assertEqual([], self.review()["rounds"])
        self.assertNotIn("code_review", self.shown()["verdicts"])

    def test_a_review_refused_for_its_session_is_launched_once_more_to_another_session(self):
        handed, session = self.review_open()
        self.run_cmd(TOOL, *handed, env=session)
        self.reviewer("silent", "favorable")

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["relaunched"]])
        review = self.review()
        self.assertEqual("favorable", review["state"]["verdict"])
        self.assertEqual(["delivery-reviewer-fixture-2"], [round_["recorded_by"] for round_ in review["rounds"]])

    def test_a_review_refused_for_its_session_twice_stops_the_ticket(self):
        handed, session = self.review_open()
        self.run_cmd(TOOL, *handed, env=session)
        self.settle()
        again = self.run_cmd(TOOL, *handed, env=session)
        self.assertEqual(EXIT_REFUSED, again.returncode, again.stdout + again.stderr)

        stopped = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in stopped["stopped"]])
        self.assertEqual("code_review_no_result", self.shown()["stop"]["reason"])
        self.assertEqual([], self.review()["rounds"])
        self.assertEqual(2, len(self.launches()))

    def test_a_review_is_recorded_under_the_session_and_never_under_the_slot_of_the_agent(self):
        """GC_AGENT names a place in the pool of the agent: the next session
        of the role takes the same one."""
        handed, _ = self.review_open()

        self.refused(*handed, mention="session", env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_AGENT": "delivery-reviewer-1"})


if __name__ == "__main__":
    unittest.main()
