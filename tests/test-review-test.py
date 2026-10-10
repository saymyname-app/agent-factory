#!/usr/bin/env python3
"""bin/test-review on a fake tracker state (T13, af-nkpjpr; Spec af-wf4w5r
§5 « Relecture avant gel », §8; Testing Decisions seam 2): one test per pass
and per refusal, each refusal re-reading the tracker to prove nothing was
written. Only command lines are exercised. The product is a copy of the
Delivery Fixture City in a throwaway repository; the red and the freeze are
proven by the real bin/tdd-step, a stop reaches the operator through the real
bin/escalation-door, read back from its list. No agent runs:
tests/fixtures/test-review/reviewer stands in for the dispatch door and the
reviewer session it starts."""

import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "test-review"
TDD_TOOL = ROOT / "bin" / "tdd-step"
STATE_TOOL = ROOT / "bin" / "convoy-state"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
DESCRIPTOR = ROOT / FIXTURE / "descriptor.json"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_REVIEWER = ROOT / "tests" / "fixtures" / "test-review" / "reviewer"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, OTHER_SLICE, PREFACTORING = "fx-t1", "fx-t2", "fx-p1"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"

EXIT_REFUSED = 1
EXIT_RETURNED = 2
EXIT_NOT_NEW_FLOW = 4
EXIT_STOPPED = 5
EXIT_PENDING = 6

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID",
                    "DELIVERY_ROLE_READ_ONLY")

TESTS = f"{FIXTURE}/tests"
TABLE = f"{TESTS}/criteria.json"
HARNESS = (f"{TESTS}/conftest.py", f"{TESTS}/harness.py")
COUNT_FILE, HEALTH_FILE = f"{TESTS}/test_count.py", f"{TESTS}/test_health.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
HEALTH_ID = f"{HEALTH_FILE}::HealthTest.test_dataset_is_named"

CRITERION_COUNT = "Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
CRITERION_HEALTH = "Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent"
CRITERIA = f"""## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] {CRITERION_COUNT}
- [ ] {CRITERION_HEALTH}

## Target rigs

delivery-fixture-city"""

# Criterion 1 as a test that observes it: the count is on the home page.
COUNT_TEST = """import os
import unittest
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        page = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/").read().decode()
        self.assertIn('<p data-anchor="fixture-count">3</p>', page)
"""

# Criterion 1 as a test that only checks a status 200: red at the start
# commit, and green on a product that never shows the count.
COUNT_TEST_STATUS_ONLY = """import os
import unittest
import urllib.error
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        try:
            status = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/?count=1").status
        except urllib.error.HTTPError as error:
            status = error.code
        self.assertEqual(200, status)
"""

HEALTH_TEST = """import json
import os
import unittest
import urllib.request


class HealthTest(unittest.TestCase):
    def test_dataset_is_named(self):
        body = json.loads(urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/health").read())
        self.assertEqual("content", body.get("dataset"))
"""

STATUS_ONLY = "le test ne vérifie qu'un statut 200 : il passerait sur une page qui n'affiche pas le nombre d'éléments"
STILL_STATUS_ONLY = "le test compare encore un statut, jamais l'ancre fixture-count"


def sha256_of(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def staged(helper):
    """A helper whose result is built once and restored afterwards (see
    TestReviewTest.stage), when a test reaches it first: it leaves only files
    (a commit, the red proof written by the real bin/tdd-step), no launched
    product, no review request and nothing read against the clock. One stage
    per helper and per arguments. A test that did anything since its setUp
    gets the helper walked for real: a restore would wipe what the test did."""
    @functools.wraps(helper)
    def reached(self, *args, **kwargs):
        if self.footprint() != self.seeded_footprint:
            return helper(self, *args, **kwargs)
        asked = json.dumps([args, kwargs], sort_keys=True, ensure_ascii=False)
        name = f"{helper.__name__}-{hashlib.sha256(asked.encode()).hexdigest()[:16]}"
        return self.stage(name, lambda: helper(self, *args, **kwargs))
    return reached


class TestReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class (tests/spec-end-test.py): a stage
        # reached once (the seeded tracker and product, a proven red) is
        # archived and restored at the same paths, which the settings, the
        # stand-ins and the recorded steps hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="test-review-test-"))
        cls.tmp = cls.holder / "city"
        cls.stages = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.holder, ignore_errors=True)

    def stage(self, name, build):
        """The state `build` leaves, built once and restored afterwards.
        What it returns is a commit: a string."""
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
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.root = self.tmp / "root"
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "TEST_REVIEW_DISPATCH_DOOR_BIN": str(FAKE_REVIEWER),
            "TEST_REVIEW_POLL_SECONDS": "0",
            "TEST_REVIEW_FAKE_LOG": str(self.door_log),
            "TEST_REVIEW_FAKE_PLAN": str(self.plan),
            "TEST_REVIEW_FAKE_REPO": str(self.repo),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.store),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        # As an author's tool call would run, but never as this suite's own session.
        for name in ("CONVOY_STATE_FAKE_MAIL_FAIL", *SESSION_IDENTITY):
            self.env.pop(name, None)
        self.base = self.stage("seeded", self.seed)
        self.seeded_footprint = self.footprint()

    def seed(self):
        """What every test starts from, left by real launches and holding
        only files: the Factory root and its settings, the stand-in of the
        proposal door, the plan of the reviewer, the marked convoy, the
        product at its first commit. Returns that commit."""
        (self.root / "config").mkdir(parents=True)
        self.settings(timeout_seconds=3600)
        (self.tmp / "proposal-door").write_text("#!/bin/sh\necho 0\n")
        (self.tmp / "proposal-door").chmod(0o755)
        self.reviewer("favorable")
        self.seed_tracker()
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE)
        self.git("init", "-q", "-b", "main")
        return self.commit("base")

    # --- harness ------------------------------------------------------------

    def settings(self, **test_review):
        """config/delivery-flow.json of the Factory root the command reads."""
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "start": {"formula": "mol-ticket-author", "role": "author"},
            "test_review": {"formula": "mol-test-review", "role": "reviewer", "rig": "agent-factory", **test_review}}))

    def reviewer(self, *plan):
        """What the reviewer session does at each launch, the last one repeated."""
        self.plan.write_text(json.dumps(list(plan), ensure_ascii=False))

    def seed_tracker(self):
        def ticket(kind, description=CRITERIA):
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": description, "metadata": {"gc.ticket_kind": kind}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, OTHER_SLICE, PREFACTORING]},
            SLICE: ticket("vertical_slice"), OTHER_SLICE: ticket("vertical_slice"),
            PREFACTORING: ticket("prefactoring", "## What to build\n\nRanger le rendu."),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads}))
        self.state("mark", CONVOY, "--demonstration-line", f"{SLICE}=La page d'accueil affiche 3",
                   "--demonstration-line", f"{OTHER_SLICE}=La sonde nomme le jeu",
                   "--user-stories", f"{SLICE}=1", "--user-stories", f"{OTHER_SLICE}=2")
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

    def run_cmd(self, tool, *args, env=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env={**self.env, **(env or {})},
                              text=True, capture_output=True, cwd=self.tmp)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket=SLICE):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket)

    def tdd(self, step, *args, ticket=SLICE):
        argv = [step, CONVOY, ticket, "--repo", self.repo]
        if step != "freeze":
            argv += ["--profile", DESCRIPTOR, "--dataset", "content"]
        return self.run_cmd(TDD_TOOL, *argv, *args)

    @staged
    def red(self, count_test=COUNT_TEST, ticket=SLICE):
        """The red step of the author: the criterion tests, their table, and
        the proof that they fail at the start commit."""
        table = json.dumps({"criteria": {"1": [COUNT_ID], "2": [HEALTH_ID]}})
        head = self.commit("tests de critère", {COUNT_FILE: count_test, HEALTH_FILE: HEALTH_TEST, TABLE: table})
        proc = self.tdd("red", "--base", self.base, "--table", TABLE, ticket=ticket)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return head

    def review(self, *args, ticket=SLICE, convoy=CONVOY, expect=0, env=None):
        proc = self.run_cmd(TOOL, "review", convoy, ticket, "--repo", self.repo, "--wait", "0", *args, env=env)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
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

    def escalation_list(self):
        proc = self.run_cmd(ESCALATION_TOOL, "list")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        needs = proc.stdout.split("Pending proposals")[0].splitlines()[1:]
        return [line.strip() for line in needs if line.strip() and "(none)" not in line]

    def mails(self):
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [entry for entry in lines if entry[0] == "mail"]

    def brief(self, *args, env=None):
        return self.run_cmd(TOOL, "brief", CONVOY, SLICE, "--repo", self.repo, *args, env=env)

    def record(self, verdict, env=None, ticket=SLICE):
        path = self.tmp / "verdict.json"
        path.write_text(json.dumps(verdict, ensure_ascii=False))
        session = {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": "delivery-reviewer-fx"} if env is None else env
        return ("record", CONVOY, ticket, "--verdict-file", path), session

    # --- AC1: a refusal per test, with its reason; no freeze --------------------

    def test_a_test_that_only_checks_a_status_is_refused_with_its_reason_and_the_freeze_does_not_happen(self):
        # Demonstration line of the ticket, first part.
        head = self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY})

        answer = self.review(expect=EXIT_RETURNED)

        self.assertEqual(("unfavorable", True, 1), (answer["verdict"], answer["returned"], answer["refusals"]))
        self.assertEqual([{"test": COUNT_ID, "criteria": ["1"], "reason": STATUS_ONLY}], answer["refused"])
        (round_,) = self.shown()["test_review"]["rounds"]
        self.assertEqual(("unfavorable", head, "delivery-reviewer-fixture-tests-1"),
                         (round_["verdict"], round_["commit"], round_["recorded_by"]))
        self.assertEqual({COUNT_ID: {"state": "unfavorable", "reason": STATUS_ONLY}, HEALTH_ID: {"state": "favorable"}},
                         round_["tests"])
        frozen = self.tdd("freeze")
        self.assertEqual(EXIT_REFUSED, frozen.returncode, frozen.stdout)
        self.assertIn("relecture", json.loads(frozen.stdout)["error"])
        self.assertNotIn("freeze", self.shown()["tdd"])
        self.assertIsNone(self.shown()["stop"])
        self.assertEqual([], self.escalation_list())

    def test_the_review_is_sent_to_the_reviewer_role_through_the_dispatch_door(self):
        self.red()

        answer = self.review()

        self.assertEqual("favorable", answer["verdict"])
        (call,) = self.launches()
        self.assertEqual(["--rig", "agent-factory", "--formula", "mol-test-review", "--role", "reviewer"], call[1:])
        bead = json.loads(self.tracker.read_text())["beads"][call[0]]
        self.assertIn(f"convoy: {CONVOY}", bead["description"])
        self.assertIn(f"ticket: {SLICE}", bead["description"])

    def test_the_verdict_is_bound_to_the_fingerprints_of_the_tests_the_freeze_seals(self):
        head = self.red()

        self.review()

        (round_,) = self.shown()["test_review"]["rounds"]
        expected = {path: sha256_of((self.repo / path).read_text()) for path in (TABLE, COUNT_FILE, HEALTH_FILE, *HARNESS)}
        self.assertEqual((head, expected), (round_["commit"], round_["files"]))

    def test_corrected_tests_pass_the_review_and_are_frozen(self):
        # Demonstration line of the ticket, second part.
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, "favorable")
        self.review(expect=EXIT_RETURNED)
        head = self.red(COUNT_TEST)

        answer = self.review()

        self.assertEqual(("favorable", 1), (answer["verdict"], answer["refusals"]))
        self.assertEqual(["unfavorable", "favorable"], [r["verdict"] for r in self.shown()["test_review"]["rounds"]])
        frozen = self.tdd("freeze")
        self.assertEqual(0, frozen.returncode, frozen.stdout + frozen.stderr)
        self.assertEqual(head, self.shown()["tdd"]["freeze"]["commit"])
        self.assertEqual(2, len(self.launches()))

    def test_a_verdict_already_given_on_these_tests_is_read_again_without_a_new_reviewer(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)
        before = self.tracker.read_bytes()

        answer = self.review(expect=EXIT_RETURNED)

        self.assertEqual(STATUS_ONLY, answer["refused"][0]["reason"])
        self.assertEqual((before, 1), (self.tracker.read_bytes(), len(self.launches())))

    # --- AC3: a second refusal stops the ticket, one element on the list --------

    def test_a_second_refusal_stops_the_ticket_and_raises_it_once_to_the_operator(self):
        # Demonstration line of the ticket, third part.
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, {COUNT_ID: STILL_STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)
        self.red(COUNT_TEST_STATUS_ONLY.replace("?count=1", "?count=2"))

        answer = self.review(expect=EXIT_STOPPED)

        self.assertEqual((True, "test_review_refused", True), (answer["stopped"], answer["stop"], answer["escalated"]))
        self.assertIn(STILL_STATUS_ONLY, answer["error"])
        stop = self.shown()["stop"]
        self.assertEqual("test_review_refused", stop["reason"])
        requests = self.escalation_list()
        self.assertEqual(1, len(requests), requests)
        self.assertTrue(requests[0].startswith(f"{SLICE} — "), requests)
        self.assertIn("relecture", requests[0])
        self.assertEqual(1, len(self.mails()))
        frozen = self.tdd("freeze")
        self.assertEqual(EXIT_REFUSED, frozen.returncode, frozen.stdout)
        self.assertNotIn("freeze", self.shown()["tdd"])

    def test_a_stopped_ticket_asked_again_stays_one_element_and_is_not_raised_twice(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, {COUNT_ID: STILL_STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)
        self.red(COUNT_TEST_STATUS_ONLY.replace("?count=1", "?count=2"))
        self.review(expect=EXIT_STOPPED)

        again = self.review(expect=EXIT_STOPPED)
        settled = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual("test_review_refused", again["stop"])
        self.assertEqual(0, settled.returncode, settled.stdout + settled.stderr)
        self.assertEqual((1, 1, 2), (len(self.escalation_list()), len(self.mails()), len(self.launches())))

    def test_a_stop_whose_request_did_not_reach_the_operator_is_raised_by_the_next_call(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, {COUNT_ID: STILL_STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)
        self.red(COUNT_TEST_STATUS_ONLY.replace("?count=1", "?count=2"))
        failed = self.review(expect=EXIT_REFUSED, env={"CONVOY_STATE_FAKE_MAIL_FAIL": "1"})
        self.assertIn("porte d'escalade", failed["error"])
        self.assertEqual("test_review_refused", self.shown()["stop"]["reason"])

        settled = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual(0, settled.returncode, settled.stdout + settled.stderr)
        self.assertEqual([SLICE], [entry["ticket"] for entry in json.loads(settled.stdout)["escalated"]])
        self.assertEqual((1, 1), (len(self.escalation_list()), len(self.mails())))

    def test_an_answer_of_the_operator_is_not_followed_by_a_second_request(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, {COUNT_ID: STILL_STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)
        self.red(COUNT_TEST_STATUS_ONLY.replace("?count=1", "?count=2"))
        self.review(expect=EXIT_STOPPED)
        answered = self.run_cmd(ESCALATION_TOOL, "repondre", SLICE, "b")
        self.assertEqual(0, answered.returncode, answered.stdout + answered.stderr)

        settled = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual(0, settled.returncode, settled.stdout + settled.stderr)
        self.assertEqual([], json.loads(settled.stdout)["escalated"])
        self.assertEqual([], self.escalation_list())

    # --- AC4: a review that crashed or gave no result ---------------------------

    def test_a_review_without_result_is_not_passed_and_is_launched_once_more(self):
        self.settings(timeout_seconds=0)
        self.red()
        self.reviewer("silent", "favorable")

        answer = self.review()

        self.assertEqual(("favorable", 2), (answer["verdict"], answer["launches"]))
        self.assertEqual(2, len(self.launches()))
        self.assertNotEqual(self.launches()[0][0], self.launches()[1][0])

    def test_a_review_without_result_twice_stops_the_ticket_and_raises_it(self):
        self.settings(timeout_seconds=0)
        self.red()
        self.reviewer("silent")

        answer = self.review(expect=EXIT_STOPPED)

        self.assertEqual((True, "test_review_no_result", True), (answer["stopped"], answer["stop"], answer["escalated"]))
        self.assertEqual(2, len(self.launches()))
        self.assertEqual("test_review_no_result", self.shown()["stop"]["reason"])
        requests = self.escalation_list()
        self.assertEqual(1, len(requests), requests)
        self.assertTrue(requests[0].startswith(f"{SLICE} — "), requests)
        frozen = self.tdd("freeze")
        self.assertEqual(EXIT_REFUSED, frozen.returncode, frozen.stdout)

    def test_a_reviewer_that_closes_its_bead_without_a_verdict_is_a_review_without_result(self):
        self.red()
        self.reviewer("closed", "favorable")

        answer = self.review()

        self.assertEqual(("favorable", 2), (answer["verdict"], answer["launches"]))

    def test_a_review_still_running_is_pending_and_is_not_launched_again(self):
        self.red()
        self.reviewer("silent")

        first = self.review(expect=EXIT_PENDING)
        second = self.review(expect=EXIT_PENDING)

        self.assertTrue(first["pending"] and second["pending"])
        self.assertEqual(1, len(self.launches()))
        self.assertEqual(1, len(self.shown()["test_review"]["request"]["launches"]))
        self.assertIsNone(self.shown()["stop"])
        frozen = self.tdd("freeze")
        self.assertEqual(EXIT_REFUSED, frozen.returncode, frozen.stdout)
        self.assertIn("relecture", json.loads(frozen.stdout)["error"])

    def test_the_advance_pass_settles_a_review_left_without_result(self):
        """What bin/convoy-advance runs: no author session is needed for the
        relaunch, the stop and the request to the operator."""
        self.red()
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)
        self.settings(timeout_seconds=0)

        first = self.run_cmd(TOOL, "settle", CONVOY)
        second = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual((0, 0), (first.returncode, second.returncode), first.stdout + second.stdout + second.stderr)
        self.assertEqual([SLICE], [entry["ticket"] for entry in json.loads(first.stdout)["relaunched"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in json.loads(second.stdout)["stopped"]])
        self.assertEqual(2, len(self.launches()))
        self.assertEqual("test_review_no_result", self.shown()["stop"]["reason"])
        self.assertEqual(1, len(self.escalation_list()))

    def test_a_dispatch_the_door_refuses_counts_no_launch(self):
        self.red()
        self.reviewer("door-refuses")

        proc = self.run_cmd(TOOL, "review", CONVOY, SLICE, "--repo", self.repo, "--wait", "0")

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("rôle relecteur", json.loads(proc.stdout)["error"])
        review = self.shown()["test_review"]
        self.assertEqual([], review["request"]["launches"])
        self.assertIsNone(self.shown()["stop"])
        beads = json.loads(self.tracker.read_text())["beads"]
        self.assertEqual("closed", beads[self.launches()[0][0]]["status"])

    def test_a_dispatch_the_door_defers_is_retried_by_the_next_pass_and_is_no_failure_of_it(self):
        self.red()
        self.reviewer("door-defers", "favorable")
        deferred = self.run_cmd(TOOL, "review", CONVOY, SLICE, "--repo", self.repo, "--wait", "0")
        self.assertEqual(EXIT_REFUSED, deferred.returncode, deferred.stdout + deferred.stderr)
        self.assertIn("différé", json.loads(deferred.stdout)["error"])
        self.reviewer("door-defers", "door-defers", "favorable")

        first = self.run_cmd(TOOL, "settle", CONVOY)
        second = self.run_cmd(TOOL, "settle", CONVOY)

        self.assertEqual((0, 0), (first.returncode, second.returncode), first.stdout + second.stdout)
        self.assertEqual([SLICE], [entry["ticket"] for entry in json.loads(first.stdout)["deferred"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in json.loads(second.stdout)["launched"]])
        self.assertEqual("favorable", self.shown()["test_review"]["rounds"][0]["verdict"])

    # --- what `review` refuses --------------------------------------------------

    def test_review_is_refused_without_a_red_proof_at_the_head_commit(self):
        self.commit("tests de critère", {COUNT_FILE: COUNT_TEST})
        self.refused("review", CONVOY, SLICE, "--repo", self.repo, mention="rouge")
        self.red()
        self.commit("un commit de plus", {f"{TESTS}/note.txt": "x\n"})
        self.refused("review", CONVOY, SLICE, "--repo", self.repo, mention="rouge")

    def test_review_is_refused_on_a_prefactoring_on_frozen_tests_and_without_a_work_tree(self):
        self.refused("review", CONVOY, PREFACTORING, "--repo", self.repo, mention="prefactoring")
        self.refused("review", CONVOY, SLICE, mention="--repo")
        self.red()
        self.review()
        self.assertEqual(0, self.tdd("freeze").returncode)
        self.refused("review", CONVOY, SLICE, "--repo", self.repo, mention="gelés")

    def test_review_is_refused_on_a_ticket_stopped_for_another_reason(self):
        self.red()
        self.state("stop-ticket", CONVOY, SLICE, "--reason", "criterion_already_green", "--detail", "critère 2 déjà vert")

        self.refused("review", CONVOY, SLICE, "--repo", self.repo, mention="arrêté")

        self.assertEqual([], self.escalation_list())

    def test_a_convoy_without_the_mark_is_not_touched(self):
        for command in (("review", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo), ("settle", PLAIN_CONVOY),
                        ("brief", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo)):
            text = self.refused(*command, status=EXIT_NOT_NEW_FLOW)
            self.assertIn("pas un convoi du nouveau flux", text)

    # --- the reviewer session: what it is given and what it hands in ------------

    def test_the_brief_gives_the_criteria_their_tests_and_the_one_question(self):
        head = self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)

        proc = self.brief()

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        brief = json.loads(proc.stdout)
        self.assertEqual((head, ["favorable", "unfavorable"]), (brief["commit"], brief["states"]))
        self.assertIn("observe", brief["question"])
        self.assertEqual([{"number": "1", "text": CRITERION_COUNT, "tests": [COUNT_ID]},
                          {"number": "2", "text": CRITERION_HEALTH, "tests": [HEALTH_ID]}], brief["criteria"])
        self.assertEqual([{"id": COUNT_ID, "file": COUNT_FILE, "criteria": ["1"]},
                          {"id": HEALTH_ID, "file": HEALTH_FILE, "criteria": ["2"]}], brief["tests"])
        self.assertEqual(COUNT_TEST_STATUS_ONLY, brief["files"][COUNT_FILE])
        self.assertEqual(sha256_of(COUNT_TEST_STATUS_ONLY), brief["fingerprints"][COUNT_FILE])
        self.assertEqual(set(brief["fingerprints"]), set(brief["files"]))

    def test_the_brief_gives_nothing_of_the_author_but_the_tests(self):
        """The reviewer judges the tests against the criteria: no Handoff, no
        note of the author, no session."""
        self.red()
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)

        brief = json.loads(self.brief().stdout)

        self.assertEqual(
            {"ok", "convoy", "ticket", "commit", "repo", "question", "states", "criteria", "tests", "files",
             "fingerprints", "verdict_shape"}, set(brief))

    def test_brief_is_refused_when_no_review_is_open(self):
        self.red()
        self.refused("brief", CONVOY, SLICE, "--repo", self.repo, mention="aucune relecture")

    def test_record_is_refused_outside_a_read_only_reviewer_session(self):
        head = self.red()
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)
        brief = json.loads(self.brief().stdout)
        verdict = {"commit": head, "files": brief["fingerprints"],
                   "tests": {COUNT_ID: {"state": "favorable"}, HEALTH_ID: {"state": "favorable"}}}

        command, _ = self.record(verdict)
        self.refused(*command, mention="lecture seule", env={})

        self.assertEqual([], self.shown()["test_review"]["rounds"])

    def test_record_refuses_a_verdict_that_leaves_a_test_out_or_gives_no_reason(self):
        head = self.red()
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)
        fingerprints = json.loads(self.brief().stdout)["fingerprints"]
        for tests, mention in (
            ({COUNT_ID: {"state": "favorable"}}, HEALTH_ID),
            ({COUNT_ID: {"state": "unfavorable"}, HEALTH_ID: {"state": "favorable"}}, "sans raison"),
            ({COUNT_ID: {"state": "peut-être"}, HEALTH_ID: {"state": "favorable"}}, "liste fermée"),
        ):
            command, session = self.record({"commit": head, "files": fingerprints, "tests": tests})
            self.refused(*command, mention=mention, env=session)
        command, session = self.record({"commit": self.base, "files": fingerprints,
                                        "tests": {COUNT_ID: {"state": "favorable"}, HEALTH_ID: {"state": "favorable"}}})
        self.refused(*command, mention="commit", env=session)

    def test_record_refuses_a_verdict_given_on_tests_that_changed_since(self):
        """The author replaced the tests while the reviewer was reading the
        first ones: its verdict answers a request that is no longer open."""
        head = self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer("silent")
        self.review(expect=EXIT_PENDING)
        stale = json.loads(self.brief().stdout)["fingerprints"]
        self.red(COUNT_TEST)
        self.review(expect=EXIT_PENDING)

        command, session = self.record({"commit": head, "files": stale,
                                        "tests": {COUNT_ID: {"state": "favorable"}, HEALTH_ID: {"state": "favorable"}}})
        self.refused(*command, mention="commit", env=session)

    def test_show_gives_the_rounds_and_the_open_request(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY})
        self.review(expect=EXIT_RETURNED)

        proc = self.run_cmd(TOOL, "show", CONVOY, SLICE)

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertEqual((1, None, None), (answer["refusals"], answer["request"], answer["stop"]))
        self.assertEqual(["unfavorable"], [r["verdict"] for r in answer["rounds"]])


    # --- T42: a fresh session per review ------------------------------------------

    def other_review_open(self):
        """The review of SLICE rendered by one session, then the review of
        OTHER_SLICE launched and left without an answer: the verdict a
        session would hand in on it, and the session that served SLICE."""
        self.red()
        self.review()
        (served,) = [round_["recorded_by"] for round_ in self.shown()["test_review"]["rounds"]]
        head = self.red(ticket=OTHER_SLICE)
        self.reviewer("favorable", "silent")
        self.review(ticket=OTHER_SLICE, expect=EXIT_PENDING)
        fingerprints = self.shown(OTHER_SLICE)["test_review"]["request"]["files"]
        verdict = {"commit": head, "files": fingerprints,
                   "tests": {COUNT_ID: {"state": "favorable"}, HEALTH_ID: {"state": "favorable"}}}
        return verdict, served

    def beads(self):
        """The tracker, each review record decoded, the mark of a launch
        counted without result set apart."""
        beads = json.loads(self.tracker.read_text())["beads"]
        counted = {}
        for bead_id, bead in beads.items():
            raw = (bead.get("metadata") or {}).get("gc.flow.test_review")
            if raw is None:
                continue
            record = json.loads(raw)
            for launch in (record.get("request") or {}).get("launches") or []:
                if "refused" in launch:
                    counted.setdefault(bead_id, []).append(launch.pop("refused")["session"])
            bead["metadata"]["gc.flow.test_review"] = record
        return beads, counted

    def test_show_names_the_session_that_rendered_each_review(self):
        head = self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, "favorable")
        self.review(expect=EXIT_RETURNED)
        self.red(COUNT_TEST)
        self.review()

        rounds = self.shown()["test_review"]["rounds"]

        self.assertEqual(["delivery-reviewer-fixture-tests-1", "delivery-reviewer-fixture-tests-2"],
                         [round_["recorded_by"] for round_ in rounds])
        self.assertEqual(head, rounds[0]["commit"])

    def test_a_review_is_recorded_under_the_session_and_never_under_the_slot_of_the_agent(self):
        """GC_AGENT names a place in the pool of the agent: the next session
        of the role takes the same one."""
        verdict, _ = self.other_review_open()
        command, _ = self.record(verdict, ticket=OTHER_SLICE)

        self.refused(*command, mention="session", env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_AGENT": "delivery-reviewer-1"})
        proc = self.run_cmd(TOOL, *command, env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_AGENT": "delivery-reviewer-1",
                                                 "GC_SESSION_ID": "fx-s9"})

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(["fx-s9"], [round_["recorded_by"] for round_ in self.shown(OTHER_SLICE)["test_review"]["rounds"]])

    def test_a_verdict_from_a_session_that_rendered_another_review_of_the_convoy_is_refused_and_counted_without_result(self):
        # Demonstration line of the ticket, last part.
        verdict, served = self.other_review_open()
        before, _ = self.beads()
        writes = self.launches()
        command, _ = self.record(verdict, ticket=OTHER_SLICE)

        proc = self.run_cmd(TOOL, *command, env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": served})

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        text = json.loads(proc.stdout)["error"]
        self.assertIn(served, text)
        self.assertIn("session neuve", text)
        self.assertIn(SLICE, text)
        after, counted = self.beads()
        self.assertEqual({OTHER_SLICE: [served]}, counted)
        self.assertEqual(before, after)
        self.assertEqual(writes, self.launches())
        self.assertEqual([], self.shown(OTHER_SLICE)["test_review"]["rounds"])
        self.assertNotIn("freeze", self.shown(OTHER_SLICE)["tdd"])

    def test_a_review_refused_for_its_session_is_launched_once_more_to_another_session(self):
        verdict, served = self.other_review_open()
        command, _ = self.record(verdict, ticket=OTHER_SLICE)
        self.run_cmd(TOOL, *command, env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": served})
        self.reviewer("favorable")

        answer = self.review(ticket=OTHER_SLICE)

        self.assertEqual(("favorable", 2), (answer["verdict"], answer["launches"]))
        self.assertNotEqual(served, answer["recorded_by"])
        self.assertEqual(3, len(self.launches()))

    def test_a_review_refused_for_its_session_twice_stops_the_ticket(self):
        verdict, served = self.other_review_open()
        command, _ = self.record(verdict, ticket=OTHER_SLICE)
        session = {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": served}
        self.run_cmd(TOOL, *command, env=session)
        self.review(ticket=OTHER_SLICE, expect=EXIT_PENDING)
        again = self.run_cmd(TOOL, *command, env=session)
        self.assertEqual(EXIT_REFUSED, again.returncode, again.stdout + again.stderr)

        answer = self.review(ticket=OTHER_SLICE, expect=EXIT_STOPPED)

        self.assertEqual((True, "test_review_no_result"), (answer["stopped"], answer["stop"]))
        self.assertEqual([], self.shown(OTHER_SLICE)["test_review"]["rounds"])
        self.assertEqual(3, len(self.launches()))
        requests = self.escalation_list()
        self.assertEqual(1, len(requests), requests)
        self.assertTrue(requests[0].startswith(f"{OTHER_SLICE} — "), requests)

    def test_the_session_that_refused_the_tests_of_a_ticket_does_not_review_them_again(self):
        self.red(COUNT_TEST_STATUS_ONLY)
        self.reviewer({COUNT_ID: STATUS_ONLY}, "silent")
        self.review(expect=EXIT_RETURNED)
        (served,) = [round_["recorded_by"] for round_ in self.shown()["test_review"]["rounds"]]
        head = self.red(COUNT_TEST)
        self.review(expect=EXIT_PENDING)
        fingerprints = self.shown()["test_review"]["request"]["files"]
        command, _ = self.record({"commit": head, "files": fingerprints,
                                  "tests": {COUNT_ID: {"state": "favorable"}, HEALTH_ID: {"state": "favorable"}}})

        proc = self.run_cmd(TOOL, *command, env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": served})

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("session neuve", json.loads(proc.stdout)["error"])
        self.assertEqual(["unfavorable"], [round_["verdict"] for round_ in self.shown()["test_review"]["rounds"]])


if __name__ == "__main__":
    unittest.main()
