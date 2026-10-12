#!/usr/bin/env python3
"""bin/ticket-evaluation on a fake tracker state (T15, af-higj9z; Spec
af-wf4w5r §7, §8; Testing Decisions seam 2): one test per pass and per
refusal, each refusal re-reading the tracker to prove nothing was written.
Only command lines are exercised. The product is a copy of the Delivery
Fixture City in a throwaway repository with its own remote, launched by the
real bin/project-launch; every piece of evidence is captured by the real
bin/evidence-capture; the merge control is the real bin/spec-integration, a
stop or a Planning Exception reaches the operator through the real
bin/escalation-door, read back from its list. No agent runs:
tests/fixtures/ticket-evaluation/evaluator stands in for the dispatch door
and the Evaluator sessions it starts."""

import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import sys
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import ticket_proofs  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "ticket-evaluation"
STATE_TOOL = ROOT / "bin" / "convoy-state"
LAUNCH_TOOL = ROOT / "bin" / "project-launch"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
ESCALATION_TOOL = ROOT / "bin" / "escalation-door"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
FAKE_EVALUATOR = ROOT / "tests" / "fixtures" / "ticket-evaluation" / "evaluator"

CONVOY, SPEC = "fx-convoy", "fx-spec"
SLICE, OTHER_SLICE, PREFACTORING, WAITING_SLICE = "fx-t1", "fx-t2", "fx-p1", "fx-t3"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
RIG = "fx-rig"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4
DIGEST = "sha256:" + "ab" * 32

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID",
                    "DELIVERY_ROLE_READ_ONLY")

APP = f"{FIXTURE}/app.py"
TESTS = f"{FIXTURE}/tests"
TABLE = f"{TESTS}/criteria.json"
COUNT_FILE = f"{TESTS}/test_count.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
NOTE = "docs/tranche.md"

CRITERION = "Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
SECOND_CRITERION = "Point d'entrée : GET /health — Observable : statut ok — Faux si : la sonde ne répond pas"
DEMONSTRATION = "Sur le jeu content, la page d'accueil affiche 3 éléments"
TICKET_TEXT = f"""## What to build

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] {CRITERION}
- [ ] {SECOND_CRITERION}

## Target rigs

{RIG}"""
# What the realized ticket makes the launched product show.
COUNT_SHOWN = 'data-anchor="fixture-count">3<'

# What the author wrote, and what an Evaluator must never be given.
HANDOFF_PROSE = "PROSE-DU-HANDOFF : le nombre est calculé côté serveur, tout est observable."
COMMIT_PROSE = "PROSE-DU-COMMIT : la page affiche le nombre"
SECTIONS = {"done": [HANDOFF_PROSE], "deviations": "aucun", "not_done": "aucun", "out_of_ticket": "aucun"}

SESSION = {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": "delivery-evaluator-fx"}


def sha256_of(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def branch_of(ticket):
    return f"ticket/{ticket}"


def staged(helper):
    """A helper whose result is built once and restored afterwards (see
    TicketEvaluationTest.stage), when a test reaches it first: it leaves only
    files (commits, steps and pieces written by the real commands), no
    launched product and nothing read against the clock. One stage per helper
    and per arguments. A test that did anything since its setUp gets the
    helper walked for real: a restore would wipe what the test did."""
    @functools.wraps(helper)
    def reached(self, *args, **kwargs):
        if self.footprint() != self.seeded_footprint:
            return helper(self, *args, **kwargs)
        asked = json.dumps([args, kwargs], sort_keys=True, ensure_ascii=False)
        name = f"{helper.__name__}-{hashlib.sha256(asked.encode()).hexdigest()[:16]}"
        return self.stage(name, lambda: helper(self, *args, **kwargs))
    return reached


class TicketEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class (tests/spec-end-test.py): a stage
        # reached once (the seeded city, a finished ticket) is archived and
        # restored at the same paths, which the scripts, the settings, the
        # work trees and the remote of the product hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="ticket-evaluation-test-"))
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
        self.briefs = self.tmp / "briefs"
        self.store = self.tmp / "store"
        self.launches_dir = self.tmp / "launches"
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
            "TICKET_EVALUATION_DISPATCH_DOOR_BIN": str(FAKE_EVALUATOR),
            "TICKET_EVALUATION_STATE_DIR": str(self.launches_dir),
            "OUTCOME_EVALUATION_STATE_DIR": str(self.tmp / "outcome-launches"),
            "EVALUATION_CAPACITY_STATE_DIR": str(self.tmp / "capacity"),
            "TICKET_EVALUATION_FAKE_LOG": str(self.door_log),
            "TICKET_EVALUATION_FAKE_PLAN": str(self.plan),
            "TICKET_EVALUATION_FAKE_BRIEFS": str(self.briefs),
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
        # No product a test launched outlives it: stopped before the next
        # test empties the directory.
        self.addCleanup(self.stop_every_product)
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
        self.evaluator({"look_for": COUNT_SHOWN, "dataset": "content"})
        self.providers(evaluator=["p-codex"])
        self.seed_tracker()
        self.seed_repo()
        opened = self.run_cmd(INTEGRATION_TOOL, "open", CONVOY, "--repo", self.repo, "--protected", PROTECTED)
        self.assertEqual(0, opened.returncode, opened.stdout + opened.stderr)
        self.write_log.write_text("")
        return self.base

    # --- harness ------------------------------------------------------------

    def seed_root(self):
        """The Factory root the command reads: the settings of the
        evaluation, the delivery roles, the provider profiles, their models
        and who supplies them, and the profile of the project."""
        config = self.root / "config"
        (config / "projects").mkdir(parents=True)
        (config / "project-descriptors").mkdir()
        self.settings(timeout_seconds=3600)
        shutil.copy(ROOT / "config" / "delivery-roles.json", config / "delivery-roles.json")
        (config / "model-catalog.json").write_text(json.dumps({"providers": {"p-codex": {"recommended": ["gpt-5.6-sol"]}}}))
        (config / "provider-policy.json").write_text(json.dumps({"providers": {
            "p-claude": {"pool": "anthropic"}, "p-claude-ro": {"pool": "anthropic"}, "p-codex": {"pool": "openai"}}}))
        (self.root / "city.toml").write_text(
            '[providers.p-claude]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-claude-ro]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-codex]\nargs_append = ["-m", "gpt-5.6-sol"]\n')
        (config / "projects" / f"{RIG}.toml").write_text(f'rig_dir = "{self.repo}"\n')
        profile = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = [RIG]
        profile["launch"]["datasets"] = {"content": profile["launch"]["datasets"]["content"]}
        for screen in profile["launch"]["screens"]:
            screen["states"] = ["content"]
        self.profile.write_text(json.dumps(profile))

    def settings(self, **evaluation):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "start": {"formula": "mol-ticket-author", "role": "author"},
            "evaluation": {"formula": "mol-ticket-evaluation", "role": "evaluator", "rig": "agent-factory",
                           "start_timeout_seconds": 15, **evaluation}}))

    def providers(self, evaluator, unavailable=()):
        """What bin/provider-failover answers: the chain of the Evaluator
        role, its first available provider being the one it runs on."""
        pools = {"p-claude": "anthropic", "p-claude-ro": "anthropic", "p-codex": "openai"}
        chain = [{"provider": name, "pool": pools[name], "state": "held" if name in unavailable else "available"}
                 for name in evaluator]
        targets = {"delivery-author": {"effective": "p-claude"}}
        running = [entry["provider"] for entry in chain if entry["state"] == "available"]
        if running:
            targets["delivery-evaluator"] = {"effective": running[0], "chain": chain}
        script = self.tmp / "provider-failover"
        script.write_text(f"#!/bin/sh\ncat <<'JSON'\n{json.dumps({'targets': targets})}\nJSON\n")
        script.chmod(0o755)

    def evaluator(self, *plan):
        """What the Evaluator session does at each launch, the last one repeated."""
        self.plan.write_text(json.dumps(list(plan), ensure_ascii=False))

    def seed_tracker(self):
        def ticket(kind, description=TICKET_TEXT, **more):
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": description, "metadata": {"gc.ticket_kind": kind}, **more}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [SLICE, OTHER_SLICE, PREFACTORING, WAITING_SLICE]},
            SPEC: {"title": "Spec d'essai", "status": "open", "issue_type": "task", "description": "## User Stories\n"},
            SLICE: ticket("vertical_slice"), OTHER_SLICE: ticket("vertical_slice"),
            WAITING_SLICE: ticket("vertical_slice", blocks=[SLICE]),
            PREFACTORING: ticket("prefactoring", f"## What to build\n\nRanger le rendu.\n\n## Target rigs\n\n{RIG}"),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        mark = ["mark", CONVOY]
        for slice_ in (SLICE, OTHER_SLICE, WAITING_SLICE):
            mark += ["--demonstration-line", f"{slice_}={DEMONSTRATION}", "--user-stories", f"{slice_}=1"]
        self.state(*mark)

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

    def json_file(self, name, content):
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def shown(self, ticket=SLICE):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket)

    def edit(self, bead_id, **fields):
        state = json.loads(self.tracker.read_text())
        state["beads"][bead_id].update(fields)
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

    def realized(self):
        """The product of the fixture, with the number of items on its home page."""
        app = (ROOT / APP).read_text()
        shown = "f'<ul data-anchor=\"fixture-items\">{items_html}</ul>'"
        self.assertIn(shown, app)
        return {APP: app.replace(shown, shown + "\n            f'<p data-anchor=\"fixture-count\">{len(items)}</p>'")}

    def started(self, ticket):
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.state("set-model", CONVOY, ticket, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", "claude-opus-5-5")
        self.edit(ticket, status="in_progress")

    def finish(self, ticket, tip):
        """What stands for the author's Ticket Exit « terminé » at `tip`
        (bin/ticket-exit): each step of its TDD with its sealed report, the
        demonstration, the sealed records, the Handoff, the exit."""
        ticket_proofs.finish(self.env, self.repo, CONVOY, ticket, tip, self.base, branch_of(ticket), sections=SECTIONS,
                             records={"files_changed": [NOTE], "commits": [{"commit": tip, "subject": COMMIT_PROSE}],
                                      "amendment": None})

    @staged
    def finished_slice(self, files=None, ticket=SLICE):
        """A slice whose criterion test was proven red, read by the test
        reviewer and frozen, whose code is green at the tip, and whose
        author has finished there. Without `files` the criterion is not
        realized: the commit changes nothing of the product. Returns the tip."""
        self.started(ticket)
        table = json.dumps({"criteria": {"1": [COUNT_ID]}})
        red = self.commit_on(ticket, {COUNT_FILE: "# le test de critère du nombre\n", TABLE: table})
        tip = self.commit_on(ticket, files or {NOTE: "le nombre sera affiché plus tard\n"})
        fingerprints = {path: sha256_of(self.blob(red, path)) for path in (TABLE, COUNT_FILE)}
        self.state("set-tdd", CONVOY, ticket, "--step", "red", "--commit", red, "--base", self.base)
        self.state("open-test-review", CONVOY, ticket, "--commit", red, "--file",
                   self.json_file("test-request.json", {"files": fingerprints, "criteria": {"1": [COUNT_ID]}}))
        self.state("record-test-review", CONVOY, ticket, "--file", self.json_file("test-verdict.json", {
            "commit": red, "files": fingerprints, "tests": {COUNT_ID: {"state": "favorable"}},
            "recorded_by": "delivery-reviewer-tests"}))
        self.state("set-tdd", CONVOY, ticket, "--step", "freeze", "--commit", red)
        self.state("set-tdd", CONVOY, ticket, "--step", "green", "--commit", tip)
        self.finish(ticket, tip)
        return tip

    def corrected(self, files, ticket=SLICE):
        """A new commit of the author on a finished ticket, green and
        finished again at the new tip."""
        tip = self.commit_on(ticket, files)
        self.state("set-tdd", CONVOY, ticket, "--step", "green", "--commit", tip)
        self.finish(ticket, tip)
        return tip

    @staged
    def finished_prefactoring(self, files=None):
        self.started(PREFACTORING)
        tip = self.commit_on(PREFACTORING, files or {NOTE: "le rendu est rangé\n"})
        self.state("set-tdd", CONVOY, PREFACTORING, "--step", "prefactoring", "--commit", tip, "--base", self.base)
        self.finish(PREFACTORING, tip)
        return tip

    def code_reviewed(self, tip, ticket=SLICE):
        """A favorable code review at `tip` (bin/code-review): the other
        verdict the merge control asks for."""
        self.state("open-code-review", CONVOY, ticket, "--kind", "review", "--commit", tip, "--base", self.base)
        self.state("record-code-review", CONVOY, ticket, "--file", self.json_file("code-review.json", {
            "commit": tip, "findings": [], "answers": {}, "recorded_by": "delivery-reviewer-fx"}))

    def settle(self, expect=0, env=None):
        proc = self.run_cmd(TOOL, "settle", CONVOY, "--repo", self.repo, env=env)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def evaluation(self, ticket=SLICE):
        return self.shown(ticket)["evaluation"]

    def tool(self, command, ticket=SLICE, *args, env=None):
        proc = self.run_cmd(TOOL, command, CONVOY, ticket, "--repo", self.repo, *args, env=env)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def refused(self, *args, mention=None, status=EXIT_REFUSED, env=None):
        """A refusal: the expected exit status, one JSON answer, and nothing
        written in the tracker, no Evaluator sent."""
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
        """What the preparation command handed to the Evaluator session of that launch."""
        return (self.briefs / f"brief-{number}.json").read_text()

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

    def launch_records(self):
        return sorted(self.launches_dir.rglob("*.json")) if self.launches_dir.exists() else []

    def stop_every_product(self):
        for record in self.launch_records():
            subprocess.run((str(LAUNCH_TOOL), "stop", "--state-file", str(record)), env=self.env, capture_output=True)

    def piece(self, name, ticket=SLICE):
        """An Evidence Record of the ticket, as the store holds it."""
        return json.loads((self.store / SPEC / ticket / f"{name}.json").read_text())

    # --- an evaluation left open, for what a session hands in ---------------------

    def open_evaluation(self, files=None):
        """A finished slice whose evaluation is open: its products run, and
        the Evaluator session did not answer. Returns (tip, request)."""
        tip = self.finished_slice(files or self.realized())
        self.evaluator("silent")
        self.settle()
        return tip, self.evaluation()["request"]

    def capture(self, piece, product, path="/", ticket=SLICE):
        """What an Evaluator does: a page of a launched product, captured
        by bin/evidence-capture."""
        fetch = "import sys, urllib.request; sys.stdout.write(urllib.request.urlopen(sys.argv[1]).read().decode())"
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, ticket, "--piece", piece, "--launch-state",
                            product["state_file"], "--", "python3", "-c", fetch, product["address"] + path, env=SESSION)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return piece

    def handed(self, tip, request, **changes):
        """Every state « observed », each on a captured page of the first product."""
        product = request["environment"][0]
        result = {
            "commit": tip,
            "criteria": [{"number": 1, "text": CRITERION, "state": "observed",
                          "evidence": self.capture("evaluation.c1", product)},
                         {"number": 2, "text": SECOND_CRITERION, "state": "observed",
                          "evidence": self.capture("evaluation.c2", product, "/health")}],
            "demonstration_line": {"text": DEMONSTRATION, "state": "observed",
                                   "evidence": self.capture("evaluation.demo", product)},
            "coverage": [{"dataset": product["dataset"], "evidence": "evaluation.c1"}],
        }
        result.update(changes)
        return result

    def record(self, content, ticket=SLICE, env=SESSION):
        return self.run_cmd(TOOL, "record", CONVOY, ticket, "--repo", self.repo, "--file",
                            self.json_file("handed.json", content), env=env)

    def recorded(self, content):
        proc = self.record(content)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def record_refused(self, content, mention, env=SESSION):
        return self.refused("record", CONVOY, SLICE, "--repo", self.repo, "--file",
                            self.json_file("handed.json", content), mention=mention, env=env)

    def test_recipe_establishing_ticket_uses_its_committed_recipe_not_live_or_dirty_profile(self):
        candidate = self.profile.read_text()
        files = self.realized()
        files["config/project-descriptors/fx.json"] = candidate
        tip = self.finished_slice(files)
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["metadata"]["gc.flow.establishes_launch_recipe"] = True
        tracker["beads"][OTHER_SLICE]["description"] += (
            "\n\n## Validated Prototype\n\n- branche : main\n"
            f"- commit : {self.base}\n- chemin : {FIXTURE}/prototype\n- états : empty, content\n")
        self.tracker.write_text(json.dumps(tracker))
        live = json.loads(candidate)
        live["launch"] = None
        self.profile.write_text(json.dumps(live))
        # The author's checkout and the live profile cannot provide the recipe.
        (self.repo / "config/project-descriptors").mkdir(parents=True, exist_ok=True)
        (self.repo / "config/project-descriptors/fx.json").write_text("invalid dirty profile")
        self.evaluator("silent")
        settled = self.settle()
        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["launched"]])
        brief = self.tool("brief")
        self.assertEqual(tip, brief["commit"])
        self.assertEqual(json.loads(candidate)["launch"]["entry_points"], brief["entry_points"])
        self.assertIsNone(json.loads(self.profile.read_text())["launch"])
        observation = brief["controller_observation"]
        lifecycle = observation["observation"]["lifecycle"]
        self.assertEqual(0, lifecycle["start"]["exit_code"])
        self.assertEqual(0, lifecycle["stop"]["exit_code"])
        self.assertTrue(lifecycle["port_open_before_stop"])
        self.assertFalse(lifecycle["port_open_after_stop"])
        self.assertFalse(lifecycle["process_alive_after_stop"])
        self.assertEqual([], lifecycle["processes_after_stop"])
        self.assertIn(int(brief["environments"][0]["address"].rsplit(":", 1)[1]), lifecycle["existing_ports_after"])
        reference, = observation["observation"]["references"]
        self.assertEqual(0, reference["anchors"]["exit_code"])
        self.assertEqual(1, len(reference["datasets"]))
        self.assertTrue(all(d["identical"] for d in reference["datasets"]))
        self.assertEqual(observation, self.tool("brief", env=SESSION)["controller_observation"])
        request = self.evaluation()["request"]
        self.refused("observe", CONVOY, SLICE, "--repo", self.repo, "--commit", tip,
                     "--launch-state", request["environment"][0]["state_file"],
                     env=SESSION, mention="réservées au contrôleur")
        verdict = self.tool("verdict")
        self.assertFalse(verdict["favorable"])
        request = self.evaluation()["request"]
        handed = self.handed(tip, request)
        handed["criteria"][1]["evidence"] = observation["piece"]
        path = Path(observation["path"])
        saved = path.read_bytes()
        path.write_text('{}')
        self.record_refused(handed, "ne correspond plus à l'empreinte")
        path.write_bytes(saved)
        self.recorded(handed)
        self.assertTrue(self.tool("verdict")["favorable"])

    def test_inaccessible_reference_is_captured_as_failure_never_as_a_pass(self):
        files = self.realized()
        files["config/project-descriptors/fx.json"] = self.profile.read_text()
        tip = self.finished_slice(files)
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["metadata"]["gc.flow.establishes_launch_recipe"] = True
        tracker["beads"][OTHER_SLICE]["description"] += (
            "\n\n## Validated Prototype\n\n- branche : main\n"
            f"- commit : {'a' * 40}\n- chemin : absent\n- états : content\n")
        self.tracker.write_text(json.dumps(tracker))
        self.evaluator("silent")
        self.settle()
        report = self.tool("brief")["controller_observation"]
        ref, = report["observation"]["references"]
        self.assertNotEqual(0, ref["anchors"]["exit_code"])
        self.assertIn("error", ref)
        handed = self.handed(tip, self.evaluation()["request"])
        handed["criteria"][1].update(state="not_observed", evidence=report["piece"], reason="référence inaccessible")
        self.assertEqual("return_to_author", self.recorded(handed)["outcome"])
        self.assertFalse(self.tool("verdict")["favorable"])

    def test_recipe_establishing_ticket_refuses_missing_committed_profile(self):
        self.finished_slice(self.realized())
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["metadata"]["gc.flow.establishes_launch_recipe"] = True
        self.tracker.write_text(json.dumps(tracker))
        settled = self.settle(expect=1)
        self.assertIn("profil absent au commit évalué", settled["refused"][0]["reason"])
        self.assertEqual([], self.launches())

    def test_interrupted_preparation_reuses_exact_live_products_before_opening_evaluation(self):
        tip = self.finished_slice(self.realized())
        folder = self.launches_dir / CONVOY / SLICE
        folder.mkdir(parents=True)
        record = folder / "interrupted-content.json"
        started = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", self.profile,
                               "--commit", tip, "--dataset", "content", "--state-file", record)
        self.assertEqual(0, started.returncode, started.stdout + started.stderr)
        original = json.loads(record.read_text())
        self.assertIsNone((self.evaluation() or {}).get("request"))
        self.evaluator("silent")
        settled = self.settle()
        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["launched"]])
        request = self.evaluation()["request"]
        content = next(e for e in request["environment"] if e["dataset"] == "content")
        self.assertEqual(str(record), content["state_file"])
        self.assertEqual(original["address"], content["address"])
        self.assertEqual(len(json.loads(self.profile.read_text())["launch"]["datasets"]),
                         len(request["environment"]))
        self.assertEqual(original["pid"], json.loads(record.read_text())["pid"])
        self.assertFalse(self.tool("verdict")["favorable"])

    def test_prepared_products_are_stopped_when_the_ticket_is_no_longer_due(self):
        tip = self.finished_slice(self.realized())
        folder = self.launches_dir / CONVOY / SLICE
        folder.mkdir(parents=True)
        record = folder / "interrupted-content.json"
        started = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", self.profile,
                               "--commit", tip, "--dataset", "content", "--state-file", record)
        self.assertEqual(0, started.returncode, started.stdout + started.stderr)
        original = json.loads(record.read_text())
        trial = record.with_suffix(".trial")
        started = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", self.profile,
                               "--commit", tip, "--dataset", "content", "--state-file", trial)
        self.assertEqual(0, started.returncode, started.stdout + started.stderr)
        self.addCleanup(self.run_cmd, LAUNCH_TOOL, "stop", "--state-file", trial)
        interrupted_trial = json.loads(trial.read_text())
        tracker = json.loads(self.tracker.read_text())
        tracker["beads"][SLICE]["status"] = "closed"
        self.tracker.write_text(json.dumps(tracker))
        self.settle()
        self.assertEqual([], self.launches())
        self.assertFalse(trial.exists())
        with self.assertRaises(Exception):
            urllib.request.urlopen(interrupted_trial["address"], timeout=1)
        with self.assertRaises(Exception):
            urllib.request.urlopen(original["address"], timeout=1)

    # --- the demonstration line of the ticket -----------------------------------

    def test_an_unrealized_criterion_is_recorded_not_observed_with_its_evidence_and_the_verdict_is_unfavorable(self):
        tip = self.finished_slice()
        self.code_reviewed(tip)

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["launched"]])
        (round_,) = self.evaluation()["rounds"]
        first = round_["criteria"][0]
        self.assertEqual(("not_observed", CRITERION), (first["state"], first["text"]))
        evidence = self.piece(first["evidence"])
        self.assertEqual((tip, 0), (evidence["commit"], evidence["exit_code"]))
        self.assertNotIn("fixture-count", evidence["output"])
        self.assertEqual(("return_to_author", "unfavorable"), (round_["outcome"], round_["verdict"]))
        verdict = self.tool("verdict")
        self.assertEqual((False, "unfavorable"), (verdict["favorable"], verdict["verdict"]))
        self.assertIn("retour à l'auteur", verdict["consequence"])
        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))

    def test_the_corrected_ticket_has_every_state_observed_with_evidence_and_a_favorable_verdict(self):
        self.finished_slice()
        self.settle()

        tip = self.corrected(self.realized())
        self.code_reviewed(tip)
        self.settle()

        last = self.evaluation()["rounds"][-1]
        states = [item["state"] for item in last["criteria"]] + [last["demonstration_line"]["state"]]
        self.assertEqual(["observed"] * 3, states)
        for item in (*last["criteria"], last["demonstration_line"]):
            self.assertEqual(tip, self.piece(item["evidence"])["commit"])
        self.assertIn(COUNT_SHOWN, self.piece(last["criteria"][0]["evidence"])["output"])
        self.assertEqual(("favorable", "favorable", tip), (last["outcome"], last["verdict"], last["commit"]))
        verdict = self.tool("verdict")
        self.assertEqual((True, "favorable", []), (verdict["favorable"], verdict["verdict"], verdict["reasons"]))
        self.assertEqual([SLICE], [entry["id"] for entry in self.merge()["merged"]])

    # --- the product that is evaluated ---------------------------------------------

    def test_the_evaluator_works_on_a_product_launched_from_a_clean_copy_of_the_branch(self):
        tip = self.finished_slice(self.realized())
        # The work tree of the author holds something its branch does not.
        self.git("checkout", "-q", branch_of(SLICE))
        (self.repo / APP).write_text((self.repo / APP).read_text().replace("fixture-count", "fixture-uncommitted"))
        self.evaluator("silent")

        settled = self.settle()

        request = self.evaluation()["request"]
        self.assertEqual(["content"], [entry["dataset"] for entry in request["environment"]])
        self.assertEqual(request["environment"][0]["address"], settled["launched"][0]["environment"][0]["address"])
        for product in request["environment"]:
            launch = json.loads(Path(product["state_file"]).read_text())
            self.assertEqual((tip, product["address"]), (launch["commit"], launch["address"]))
            self.assertNotEqual(self.repo.resolve(), Path(launch["worktree"]).resolve())
            page = urllib.request.urlopen(product["address"] + "/").read().decode()
            self.assertIn("fixture-count", page)
            self.assertNotIn("fixture-uncommitted", page)
        captured = self.piece(self.capture("evaluation.c1", request["environment"][0]))
        self.assertEqual((request["environment"][0]["address"], tip), (captured["address"], captured["commit"]))

    def test_datasets_open_on_demand_with_one_live_product_and_separate_proofs(self):
        profile = json.loads(self.profile.read_text())
        original = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["launch"]["datasets"]["empty"] = original["launch"]["datasets"]["empty"]
        profile["launch"]["screens"][0]["states"] = ["content", "empty"]
        self.profile.write_text(json.dumps(profile))
        tip = self.finished_slice(self.realized())
        self.evaluator("silent")
        self.settle()
        request = self.evaluation()["request"]
        self.assertEqual(["content"], [entry["dataset"] for entry in request["environment"]])
        first = request["environment"][0]
        handed = self.handed(tip, request)
        asked = self.tool("product", SLICE, "--dataset", "empty", env=SESSION)
        self.assertFalse(asked["ready"])
        settled = self.settle()
        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["product_ready"]])
        request = self.evaluation()["request"]
        self.assertEqual(["content", "empty"], [entry["dataset"] for entry in request["environment"]])
        self.assertFalse(Path(first["state_file"]).exists())
        second = request["environment"][-1]
        self.assertEqual([second["state_file"]], self.evaluation()["live"])
        self.assertEqual(tip, json.loads(Path(second["state_file"]).read_text())["commit"])
        self.assertTrue(self.tool("product", SLICE, "--dataset", "empty", env=SESSION)["ready"])
        handed["coverage"].append({"dataset": "empty", "evidence": self.capture("evaluation.empty", second)})
        self.recorded(handed)
        self.assertTrue(self.tool("verdict")["favorable"])

    def test_open_legacy_multi_game_request_cannot_record_without_coverage(self):
        profile = json.loads(self.profile.read_text())
        original = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["launch"]["datasets"]["empty"] = original["launch"]["datasets"]["empty"]
        profile["launch"]["screens"][0]["states"] = ["content", "empty"]
        self.profile.write_text(json.dumps(profile))
        tip = self.finished_slice(self.realized())
        self.evaluator("silent")
        self.settle()
        request = self.evaluation()["request"]
        handed = self.handed(tip, request)
        self.tool("product", SLICE, "--dataset", "empty", env=SESSION)
        self.settle()
        tracker = json.loads(self.tracker.read_text())
        metadata = tracker["beads"][SLICE]["metadata"]
        legacy = json.loads(metadata["gc.flow.evaluation"])
        self.assertEqual(2, len(legacy["request"]["environment"]))
        legacy["request"].pop("datasets")
        metadata["gc.flow.evaluation"] = json.dumps(legacy)
        self.tracker.write_text(json.dumps(tracker))
        handed.pop("coverage")

        self.record_refused(handed, "couverture")

    def test_settle_on_a_project_without_a_named_dataset_is_refused_and_launches_no_product(self):
        """T38 (af-8o4jcp): no dataset declared, so nothing is launched and
        nothing is recorded, although the recipe would start."""
        self.finished_slice(self.realized())
        profile = json.loads(self.profile.read_text())
        launch = profile["launch"]
        content = launch["datasets"]["content"]
        launch["recipe"] = [content if token == "{dataset}" else token for token in launch["recipe"]]
        launch["datasets"] = {}
        launch.pop("screens", None)
        self.profile.write_text(json.dumps(profile))
        self.evaluator("silent")

        before = (self.tracker.read_bytes(), self.write_log.read_text(), self.launches())

        answer = self.settle(expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertEqual([SLICE], [entry["ticket"] for entry in answer["refused"]])
        self.assertIn("aucun jeu de données", answer["refused"][0]["reason"])
        self.assertEqual([], self.launch_records(), "un produit a été lancé sans jeu de données")
        self.assertEqual(before, (self.tracker.read_bytes(), self.write_log.read_text(), self.launches()))

    def test_the_address_and_the_commit_of_the_launched_product_are_in_the_evidence_of_each_state(self):
        tip = self.finished_slice(self.realized())

        self.settle()

        (round_,) = self.evaluation()["rounds"]
        addresses = [entry["address"] for entry in round_["environment"]]
        for item in (*round_["criteria"], round_["demonstration_line"]):
            evidence = self.piece(item["evidence"])
            self.assertEqual(tip, evidence["commit"])
            self.assertIn(evidence["address"], addresses)

    def test_a_piece_captured_on_the_authors_own_launch_is_refused(self):
        tip, request = self.open_evaluation()
        own = self.tmp / "author-launch.json"
        launched = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", self.profile, "--commit", tip,
                                "--dataset", "content", "--state-file", own)
        self.assertEqual(0, launched.returncode, launched.stdout + launched.stderr)
        self.addCleanup(subprocess.run, (str(LAUNCH_TOOL), "stop", "--state-file", str(own)), env=self.env,
                        capture_output=True)
        author = json.loads(own.read_text())
        handed = self.handed(tip, request)
        handed["criteria"][0]["evidence"] = self.capture(
            "evaluation.own", {"state_file": str(own), "address": author["address"]})

        self.record_refused(handed, ("évaluation", "n'est jamais celui qui est évalué", author["address"]))

    def test_the_launched_products_are_stopped_by_code_once_the_states_are_recorded(self):
        tip, request = self.open_evaluation()
        addresses = [entry["address"] for entry in request["environment"]]
        self.recorded(self.handed(tip, request))
        self.assertEqual(sorted(entry["state_file"] for entry in request["environment"]),
                         sorted(self.evaluation()["live"]))

        self.settle()

        self.assertNotIn("live", self.evaluation())
        self.assertEqual([], self.launch_records())
        for address in addresses:
            with self.assertRaises(OSError):
                urllib.request.urlopen(address + "/health", timeout=2)

    # --- record: what is accepted from the Evaluator --------------------------------

    def test_a_state_without_a_piece_of_evidence_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        del handed["criteria"][1]["evidence"]

        self.record_refused(handed, ("critère 2", "état sans Evidence Record valide"))

    def test_a_state_whose_evidence_was_not_captured_by_the_tool_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        # A fingerprint written by hand, for a piece no capture filed.
        self.state("add-evidence", CONVOY, SLICE, "--piece", "evaluation.written", "--digest", DIGEST, "--commit", tip)
        handed["demonstration_line"]["evidence"] = "evaluation.written"

        self.record_refused(handed, ("état sans Evidence Record valide", "evaluation.written"))

    def test_a_state_whose_evidence_was_captured_at_another_commit_is_refused(self):
        self.finished_slice()
        self.settle()
        tip, request = self.corrected(self.realized()), None
        self.evaluator("silent")
        self.settle()
        request = self.evaluation()["request"]
        handed = self.handed(tip, request)
        # What the first evaluation captured, at the commit before the correction.
        self.capture("evaluation.c2", request["environment"][0], "/health")
        stale = self.evaluation()["rounds"][0]["criteria"][0]["evidence"]
        self.assertEqual("evaluation.c1", stale)
        old = self.tmp / "old-launch.json"
        launched = self.run_cmd(LAUNCH_TOOL, "--repo-root", self.repo, "start", self.profile, "--commit",
                                self.evaluation()["rounds"][0]["commit"], "--dataset", "content", "--state-file", old)
        self.assertEqual(0, launched.returncode, launched.stdout + launched.stderr)
        self.addCleanup(subprocess.run, (str(LAUNCH_TOOL), "stop", "--state-file", str(old)), env=self.env,
                        capture_output=True)
        handed["criteria"][0]["evidence"] = self.capture(
            "evaluation.old", {"state_file": str(old), "address": json.loads(old.read_text())["address"]})

        self.record_refused(handed, ("évaluation.old".replace("é", "e"), "non au commit évalué"))

    def test_an_overall_verdict_given_by_the_evaluator_is_refused(self):
        tip, request = self.open_evaluation()

        self.record_refused(self.handed(tip, request, verdict="favorable"),
                            "le verdict est calculé par du code, jamais donné par l'Evaluator")

    def test_a_state_outside_the_three_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0]["state"] = "partially_observed"

        self.record_refused(handed, ("critère 1", "hors de la liste fermée", "observed, not_observed, unobservable"))

    def test_a_state_that_is_not_observed_without_a_reason_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0]["state"] = "not_observed"

        self.record_refused(handed, ("critère 1", "sans raison"))

    def test_an_unobservable_without_its_cause_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0].update(state="unobservable", reason="rien à voir")

        self.record_refused(handed, ("critère 1", "sans cause", "criterion, environment"))

    def test_a_reworded_criterion_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0]["text"] = "La page d'accueil répond"

        self.record_refused(handed, ("critère 1 reformulé", CRITERION))

    def test_a_removed_criterion_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        del handed["criteria"][1]

        self.record_refused(handed, ("critère 2 retiré", SECOND_CRITERION))

    def test_a_criterion_the_approved_ticket_does_not_have_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"].append({"number": 3, "text": "La page est jolie", "state": "observed",
                                   "evidence": "evaluation.c1"})

        self.record_refused(handed, "un critère que le ticket approuvé n'a pas : 3")

    def test_a_reworded_demonstration_line_is_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["demonstration_line"]["text"] = "La page d'accueil affiche quelque chose"

        self.record_refused(handed, ("ligne de démonstration reformulé", DEMONSTRATION))

    def test_criteria_changed_on_the_ticket_since_the_request_are_refused(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        self.edit(SLICE, description=TICKET_TEXT.replace(SECOND_CRITERION, "La sonde répond vite"))
        handed["criteria"][1]["text"] = "La sonde répond vite"

        self.record_refused(handed, "ne sont plus ceux de la demande d'évaluation")

    def test_states_handed_in_from_outside_a_read_only_role_session_are_refused(self):
        tip, request = self.open_evaluation()

        self.record_refused(self.handed(tip, request), "session du rôle Evaluator, en lecture seule", env={})

    def test_states_for_another_commit_than_the_evaluated_one_are_refused(self):
        tip, request = self.open_evaluation()

        self.record_refused(self.handed(tip, request, commit=self.base), ("porte sur le commit", tip))

    def test_states_without_an_open_evaluation_are_refused(self):
        tip = self.finished_slice(self.realized())

        self.record_refused({"commit": tip, "criteria": [], "demonstration_line": {}}, "aucune évaluation n'est demandée")

    # --- the verdict, computed from the tracker ---------------------------------------

    def test_the_verdict_is_favorable_only_when_everything_is_observed_with_evidence_at_the_head_commit(self):
        tip, request = self.open_evaluation()

        recorded = self.recorded(self.handed(tip, request))

        self.assertEqual(("favorable", "favorable"), (recorded["outcome"], recorded["verdict"]))
        verdict = self.tool("verdict")
        self.assertEqual((True, "favorable", tip, tip), tuple(verdict[name] for name in ("favorable", "verdict", "commit", "tip")))
        stored = self.shown()["verdicts"]["evaluation"]
        self.assertEqual(("favorable", tip, True), (stored["state"], stored["commit"], stored["valid"]))

    def test_a_favorable_evaluation_is_not_favorable_once_a_commit_is_added_to_the_branch(self):
        tip, request = self.open_evaluation()
        self.recorded(self.handed(tip, request))

        newer = self.commit_on(SLICE, {NOTE: "un commit de plus\n"})

        verdict = self.tool("verdict")
        self.assertEqual((False, None, tip, newer), tuple(verdict[name] for name in ("favorable", "verdict", "commit", "tip")))
        self.assertIn("à rejouer sur la pointe", " ".join(verdict["reasons"]))

    def test_a_favorable_evaluation_is_not_favorable_once_a_piece_of_its_evidence_is_gone(self):
        tip, request = self.open_evaluation()
        self.recorded(self.handed(tip, request))

        (self.store / SPEC / SLICE / "evaluation.c2.json").unlink()

        verdict = self.tool("verdict")
        self.assertFalse(verdict["favorable"])
        self.assertIn("preuve non recevable", " ".join(verdict["reasons"]))
        self.assertIn("evaluation.c2", " ".join(verdict["reasons"]))

    def test_no_evaluation_is_not_a_favorable_verdict(self):
        self.finished_slice(self.realized())

        verdict = self.tool("verdict")

        self.assertEqual((False, None), (verdict["favorable"], verdict["verdict"]))
        self.assertIn("l'absence d'évaluation ne vaut pas accord", " ".join(verdict["reasons"]))

    def test_a_not_observed_gives_an_unfavorable_verdict_that_returns_to_the_author(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["demonstration_line"].update(state="not_observed", reason="la page n'affiche pas 3 éléments")

        recorded = self.recorded(handed)

        self.assertEqual(("return_to_author", "unfavorable"), (recorded["outcome"], recorded["verdict"]))
        self.assertEqual(["ligne de démonstration"], recorded["state"]["not_observed"])
        self.assertEqual("unfavorable", self.shown()["verdicts"]["evaluation"]["state"])
        waiting = self.settle()["waiting"]
        self.assertEqual([SLICE], [entry["ticket"] for entry in waiting])
        self.assertIn("retour à l'auteur", waiting[0]["reason"])
        self.assertEqual([], self.escalation_list())
        self.assertIsNone(self.shown()["park"])

    def test_an_unobservable_by_the_criterion_is_a_planning_exception_and_parks_the_ticket(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0].update(state="unobservable", cause="criterion",
                                     reason="le critère nomme une ancre qu'aucun point d'entrée ne sert")
        recorded = self.recorded(handed)
        self.assertEqual(("planning_exception", "unfavorable"), (recorded["outcome"], recorded["verdict"]))
        self.assertIn("Planning Exception", self.tool("verdict")["consequence"])

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["planning_exception"]])
        self.assertEqual(sorted([SLICE, WAITING_SLICE]), sorted(settled["planning_exception"][0]["parked"]))
        park = self.shown()["park"]
        self.assertEqual(("planning_exception", SLICE), (park["cause"], park["origin"]))
        (request_line,) = self.escalation_list()
        self.assertIn(SLICE, request_line)
        self.assertIn("Planning Exception", request_line)
        # Said once: a second pass has nothing more to do.
        again = self.settle()
        self.assertEqual([], again["planning_exception"])
        self.assertEqual(1, len(self.escalation_list()))

    def test_resolved_evaluation_exception_replays_once_without_erasing_its_refusal(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][0].update(state="unobservable", cause="criterion", reason="commande inaccessible")
        self.recorded(handed)
        self.settle()
        previous = self.evaluation()["rounds"]
        time.sleep(1.1)  # Distinct event timestamps, as in the durable parking contract.
        self.state("lift-park", CONVOY, SLICE, "--request", SLICE, "--option", "a")
        self.evaluator("silent")
        self.assertEqual([SLICE], [e["ticket"] for e in self.settle()["launched"]])
        self.assertEqual(previous, self.evaluation()["rounds"])
        self.assertFalse(self.tool("verdict")["favorable"])
        request = self.evaluation()["request"]
        handed = self.handed(tip, request)
        handed["criteria"][0].update(state="unobservable", cause="criterion", reason="toujours inaccessible")
        self.tool("record", SLICE, "--file", self.json_file("replay.json", handed),
                  env={**SESSION, "GC_SESSION_NAME": "delivery-evaluator-fx-replay"})
        self.assertEqual(2, len(self.evaluation()["rounds"]))
        self.assertEqual([SLICE], [e["ticket"] for e in self.settle()["planning_exception"]])
        self.assertFalse(self.tool("verdict")["favorable"])
        self.assertEqual([], self.settle()["launched"])

    def test_an_unobservable_by_the_environment_is_an_outage_that_is_not_counted_as_a_refusal(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        handed["criteria"][1].update(state="unobservable", cause="environment", reason="le produit lancé ne répond plus")

        recorded = self.recorded(handed)

        self.assertEqual(("environment_outage", None), (recorded["outcome"], recorded["verdict"]))
        self.assertNotIn("evaluation", self.shown()["verdicts"])
        verdict = self.tool("verdict")
        self.assertEqual((False, None), (verdict["favorable"], verdict["verdict"]))
        self.assertIn("non comptée comme refus", verdict["consequence"])
        # Not a refusal: the evaluation is made again, on products launched again.
        self.evaluator({"look_for": COUNT_SHOWN, "dataset": "content"})
        settled = self.settle()
        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["launched"]])
        self.assertEqual(["environment_outage", "favorable"], [r["outcome"] for r in self.evaluation()["rounds"]])
        self.assertEqual(0, self.shown()["counters"]["correction_rounds"])

    def test_a_second_outage_at_the_same_commit_stops_the_ticket_as_a_breakdown_raised_once(self):
        self.finished_slice(self.realized())
        self.evaluator({"states": {"2": {"state": "unobservable", "cause": "environment", "reason": "plus de réponse"}}})
        self.settle()
        self.settle()
        self.assertEqual(["environment_outage"] * 2, [r["outcome"] for r in self.evaluation()["rounds"]])

        stopped = self.settle()

        self.assertEqual([{"ticket": SLICE, "stop": "evaluation_outage"}], stopped["stopped"])
        self.assertEqual("evaluation_outage", self.shown()["stop"]["reason"])
        (request_line,) = self.escalation_list()
        self.assertIn("en panne", request_line)
        self.assertNotIn("evaluation", self.shown()["verdicts"])
        self.settle()
        self.assertEqual(1, len(self.escalation_list()))
        self.assertEqual(2, len(self.launches()))

    # --- a prefactoring: no Evaluator session ------------------------------------------

    def test_a_prefactoring_gets_no_evaluator_session_and_the_control_records_that_the_product_starts(self):
        tip = self.finished_prefactoring()

        settled = self.settle()

        self.assertEqual([PREFACTORING], [entry["ticket"] for entry in settled["started"]])
        self.assertEqual([], self.launches())
        (round_,) = self.evaluation(PREFACTORING)["rounds"]
        self.assertEqual(("startup", True, "favorable", tip),
                         tuple(round_[name] for name in ("kind", "started", "verdict", "commit")))
        probe = self.piece(round_["evidence"], PREFACTORING)
        self.assertEqual((tip, 0), (probe["commit"], probe["exit_code"]))
        self.assertIn(probe["address"], [entry["address"] for entry in round_["environment"]])
        self.assertIn('"status": "ok"', probe["output"])
        self.assertTrue(probe["command"][-2].endswith("/health"))
        self.assertTrue(self.tool("verdict", PREFACTORING)["favorable"])
        self.assertEqual([], self.launch_records())
        # A second pass does nothing more.
        self.assertEqual([], self.settle()["started"])

    def test_prefactoring_probes_each_game_sequentially_with_separate_evidence(self):
        profile = json.loads(self.profile.read_text())
        original = json.loads((ROOT / FIXTURE / "descriptor.json").read_text())
        profile["launch"]["datasets"]["empty"] = original["launch"]["datasets"]["empty"]
        profile["launch"]["screens"][0]["states"] = ["content", "empty"]
        self.profile.write_text(json.dumps(profile))
        tip = self.finished_prefactoring()

        settled = self.settle()

        self.assertEqual([PREFACTORING], [entry["ticket"] for entry in settled["started"]])
        (round_,) = self.evaluation(PREFACTORING)["rounds"]
        self.assertEqual(["content", "empty"], [entry["dataset"] for entry in round_["environment"]])
        self.assertEqual(["content", "empty"], [entry["dataset"] for entry in round_["coverage"]])
        for entry, coverage in zip(round_["environment"], round_["coverage"]):
            piece = self.piece(coverage["evidence"], PREFACTORING)
            self.assertEqual((tip, entry["address"], 0),
                             (piece["commit"], piece["address"], piece["exit_code"]))
        self.assertTrue(self.tool("verdict", PREFACTORING)["favorable"])
        self.assertEqual([], self.launch_records())

    def test_a_prefactoring_whose_product_does_not_start_gets_an_unfavorable_verdict(self):
        tip = self.finished_prefactoring({APP: "raise SystemExit('le produit ne démarre plus')\n"})
        self.settings(timeout_seconds=3600, start_timeout_seconds=2)

        settled = self.settle()

        self.assertEqual([PREFACTORING], [entry["ticket"] for entry in settled["refused_startup"]])
        (round_,) = self.evaluation(PREFACTORING)["rounds"]
        self.assertEqual(("startup", False, "unfavorable", tip),
                         tuple(round_[name] for name in ("kind", "started", "verdict", "commit")))
        self.assertIn("ne démarre pas depuis une copie propre", round_["detail"])
        self.assertFalse(self.tool("verdict", PREFACTORING)["favorable"])
        self.assertEqual([], self.launches())

    def test_states_of_an_evaluator_are_refused_on_a_prefactoring(self):
        tip = self.finished_prefactoring()

        self.refused("record", CONVOY, PREFACTORING, "--repo", self.repo, "--file",
                     self.json_file("handed.json", {"commit": tip, "criteria": [], "demonstration_line": {}}),
                     mention="aucune évaluation n'est demandée", env=SESSION)
        refused = self.run_cmd(STATE_TOOL, "open-evaluation", CONVOY, PREFACTORING, "--commit", tip, "--file",
                               self.json_file("request.json", {}))
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout)
        self.assertIn("aucune session d'Evaluator", refused.stdout)

    def test_a_slice_whose_clean_copy_does_not_start_is_refused_without_an_evaluator_session(self):
        tip = self.finished_slice({APP: "raise SystemExit('le produit ne démarre plus')\n"})
        self.settings(timeout_seconds=3600, start_timeout_seconds=2)

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["refused_startup"]])
        (round_,) = self.evaluation()["rounds"]
        self.assertEqual(("startup", False, "unfavorable", tip),
                         tuple(round_[name] for name in ("kind", "started", "verdict", "commit")))
        self.assertEqual([], self.launches())

    # --- what the Evaluator is given ----------------------------------------------------

    def test_what_the_evaluator_is_given_holds_neither_the_handoff_nor_the_diff(self):
        tip = self.finished_slice(self.realized())

        self.settle()

        given = self.brief_given()
        brief = json.loads(given)
        self.assertEqual(DEMONSTRATION, brief["demonstration_line"])
        self.assertEqual([{"number": 1, "text": CRITERION}, {"number": 2, "text": SECOND_CRITERION}], brief["criteria"])
        self.assertEqual(tip, brief["commit"])
        self.assertEqual(["content"], [entry["dataset"] for entry in brief["environments"]])
        for forbidden in (HANDOFF_PROSE, "PROSE-DU-HANDOFF", COMMIT_PROSE, "handoff", "diff", str(self.repo),
                          branch_of(SLICE), NOTE, self.base, "files_changed"):
            self.assertNotIn(forbidden, given)
        self.assertNotIn("repo", brief)

    def test_a_brief_is_refused_when_no_evaluation_is_open(self):
        self.finished_slice(self.realized())

        self.refused("brief", CONVOY, SLICE, "--repo", self.repo, mention="aucune évaluation n'est demandée")

    # --- the roles: who evaluates, on whose supplier --------------------------------------

    def test_an_evaluator_of_another_supplier_than_the_author_is_recorded_without_a_mention(self):
        self.finished_slice(self.realized())

        self.settle()

        (round_,) = self.evaluation()["rounds"]
        self.assertEqual({"author": {"provider": "p-claude", "supplier": "anthropic"},
                          "evaluator": {"provider": "p-codex", "supplier": "openai"},
                          "same_provider": False, "other_declared": ["openai"]}, round_["roles"])
        shown = self.tool("show")
        self.assertIsNone(shown["independence"])
        self.assertEqual("p-codex", shown["models"]["evaluator"]["provider"])
        self.assertIsNone(json.loads(self.brief_given())["independence"])

    def test_an_evaluator_of_the_authors_supplier_is_recorded_with_the_mention_when_no_other_is_declared(self):
        self.finished_slice(self.realized())
        self.providers(evaluator=["p-claude-ro"])

        self.settle()

        (round_,) = self.evaluation()["rounds"]
        self.assertEqual((True, []), (round_["roles"]["same_provider"], round_["roles"]["other_declared"]))
        self.assertEqual("même fournisseur que l'auteur (anthropic)", self.tool("show")["independence"])
        self.assertEqual("même fournisseur que l'auteur (anthropic)", json.loads(self.brief_given())["independence"])
        self.assertEqual("favorable", round_["verdict"])

    def test_an_evaluation_does_not_start_on_the_authors_supplier_while_another_declared_one_is_available(self):
        self.finished_slice(self.realized())
        self.providers(evaluator=["p-claude-ro", "p-codex"])

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["deferred"]])
        self.assertIn("autre fournisseur déclaré est disponible (openai)", settled["deferred"][0]["reason"])
        self.assertEqual(([], []), (self.launches(), self.launch_records()))
        self.assertIsNone(self.evaluation())

    def test_the_mention_names_the_other_declared_supplier_when_it_is_not_available(self):
        self.finished_slice(self.realized())
        self.providers(evaluator=["p-codex", "p-claude-ro"], unavailable=["p-codex"])

        self.settle()

        (round_,) = self.evaluation()["rounds"]
        self.assertEqual((True, ["openai"]), (round_["roles"]["same_provider"], round_["roles"]["other_declared"]))
        self.assertEqual("même fournisseur que l'auteur (anthropic) ; autre fournisseur déclaré mais indisponible : openai",
                         self.tool("show")["independence"])

    def test_an_unknown_supplier_is_said_and_never_left_out(self):
        self.finished_slice(self.realized())
        self.providers(evaluator=[])

        self.settle()

        (round_,) = self.evaluation()["rounds"]
        self.assertEqual((None, None), (round_["roles"]["evaluator"], round_["roles"]["same_provider"]))
        self.assertIn("indépendance de fournisseur non établie", self.tool("show")["independence"])

    # --- when an evaluation is due ---------------------------------------------------------

    def test_a_ticket_that_is_not_finished_or_not_green_at_its_tip_is_not_evaluated(self):
        self.started(SLICE)
        self.commit_on(SLICE, self.realized())
        self.assertEqual([], self.settle()["launched"])

        self.finished_slice(self.realized(), ticket=OTHER_SLICE)
        self.commit_on(OTHER_SLICE, {NOTE: "un commit après la sortie\n"})

        settled = self.settle()

        self.assertEqual([OTHER_SLICE], [entry["ticket"] for entry in settled["waiting"]])
        self.assertIn("son auteur y travaille", settled["waiting"][0]["reason"])
        self.assertEqual([], self.launches())

    def test_a_second_pass_on_the_same_state_does_nothing(self):
        self.finished_slice(self.realized())
        self.settle()
        # The pass after the states are in stops the products they were observed on.
        self.settle()
        before = (self.tracker.read_bytes(), self.launches())

        settled = self.settle()

        self.assertEqual(([], [], []), (settled["launched"], settled["pending"], settled["waiting"]))
        self.assertEqual(before, (self.tracker.read_bytes(), self.launches()))

    def test_a_commit_added_after_a_favorable_evaluation_has_it_replayed_on_the_new_tip(self):
        self.finished_slice(self.realized())
        self.settle()

        tip = self.corrected({NOTE: "une précision\n"})
        settled = self.settle()

        self.assertEqual([tip], [entry["commit"] for entry in settled["launched"]])
        self.assertEqual(["favorable", "favorable"], [r["verdict"] for r in self.evaluation()["rounds"]])
        self.assertEqual(tip, self.evaluation()["state"]["commit"])

    def test_an_evaluation_left_open_on_a_tip_the_author_left_is_withdrawn_and_its_products_stopped(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        addresses = [entry["address"] for entry in request["environment"]]

        self.commit_on(SLICE, {NOTE: "l'auteur reprend son ticket\n"})
        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["waiting"]])
        evaluation = self.evaluation()
        self.assertEqual(([], False, False), (evaluation["rounds"], "request" in evaluation, "live" in evaluation))
        self.assertEqual([], self.launch_records())
        for address in addresses:
            with self.assertRaises(OSError):
                urllib.request.urlopen(address + "/health", timeout=2)
        # What the session of the withdrawn evaluation hands in later is refused.
        self.record_refused(handed, "aucune évaluation n'est demandée")

    def test_an_evaluation_left_open_on_a_parked_ticket_is_withdrawn_and_its_products_stopped(self):
        self.open_evaluation()
        self.state("park", CONVOY, SLICE, "--cause", "operator_request", "--detail", "une question pour l'opérateur")

        settled = self.settle()

        self.assertTrue(settled["ok"])
        self.assertEqual(("request" in self.evaluation(), self.launch_records()), (False, []))

    # --- an evaluation that gives no result ---------------------------------------------------

    def test_an_evaluation_without_a_result_is_pending_and_merges_nothing(self):
        tip = self.finished_slice(self.realized())
        self.code_reviewed(tip)
        self.evaluator("silent")

        first, second = self.settle(), self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in first["launched"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in second["pending"]])
        self.assertEqual(1, len(self.launches()))
        merged = self.merge()
        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertIn("Ticket Evaluation en cours", merged["waiting"][0]["reason"])

    def test_an_evaluation_without_a_result_is_launched_once_more_then_the_ticket_is_stopped_and_raised_once(self):
        self.finished_slice(self.realized())
        self.settings(timeout_seconds=0)
        self.evaluator("silent")

        launched, relaunched, stopped, after = self.settle(), self.settle(), self.settle(), self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in launched["launched"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in relaunched["relaunched"]])
        self.assertEqual([{"ticket": SLICE, "stop": "evaluation_no_result"}], stopped["stopped"])
        self.assertEqual(([], []), (after["stopped"], after["escalated"]))
        self.assertEqual(2, len(self.launches()))
        stop = self.shown()["stop"]
        self.assertEqual("evaluation_no_result", stop["reason"])
        self.assertIn("raised", stop)
        (request_line,) = self.escalation_list()
        self.assertIn(SLICE, request_line)
        self.assertNotIn("evaluation", self.shown()["verdicts"])
        self.assertEqual([], self.launch_records())

    def test_a_session_that_closes_its_bead_without_states_counts_as_no_result(self):
        self.finished_slice(self.realized())
        self.evaluator("closed", {"look_for": COUNT_SHOWN, "dataset": "content"})

        first, second = self.settle(), self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in first["launched"]])
        self.assertEqual([SLICE], [entry["ticket"] for entry in second["relaunched"]])
        self.assertEqual("favorable", self.evaluation()["state"]["verdict"])

    def test_a_dispatch_the_door_defers_counts_no_launch_and_is_tried_again(self):
        self.finished_slice(self.realized())
        self.evaluator("door-defers", {"look_for": COUNT_SHOWN, "dataset": "content"})

        deferred = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in deferred["deferred"]])
        self.assertEqual([], self.evaluation()["request"]["launches"])
        self.assertEqual([SLICE], [entry["ticket"] for entry in self.settle()["launched"]])
        self.assertEqual("favorable", self.evaluation()["state"]["verdict"])

    def test_a_dispatch_the_door_refuses_counts_no_launch_and_fails_the_pass(self):
        self.finished_slice(self.realized())
        self.evaluator("door-refuses")

        refused = self.settle(expect=EXIT_REFUSED)

        self.assertEqual([SLICE], [entry["ticket"] for entry in refused["refused"]])
        self.assertIn("n'a pas été routée vers le rôle Evaluator", refused["refused"][0]["reason"])
        self.assertEqual([], self.evaluation()["request"]["launches"])

    def test_the_evaluator_is_sent_through_the_dispatch_door_on_its_role_and_formula(self):
        self.finished_slice(self.realized())

        self.settle()

        (call,) = self.launches()
        self.assertEqual(["--rig", "agent-factory", "--formula", "mol-ticket-evaluation", "--role", "evaluator"], call[1:])

    # --- the merge control ------------------------------------------------------------------

    def test_a_ticket_without_an_evaluation_is_not_merged(self):
        tip = self.finished_slice(self.realized())
        self.code_reviewed(tip)

        merged = self.merge()

        self.assertEqual(([], [SLICE]), (merged["merged"], [entry["id"] for entry in merged["waiting"]]))
        self.assertIn("aucune Ticket Evaluation rendue", merged["waiting"][0]["reason"])

    def test_a_favorable_verdict_written_without_its_evaluation_does_not_pass_the_merge_control(self):
        tip = self.finished_slice(self.realized())
        self.code_reviewed(tip)
        self.state("set-verdict", CONVOY, SLICE, "--kind", "evaluation", "--state", "favorable", "--commit", tip)

        merged = self.merge()

        self.assertEqual([], merged["merged"])
        self.assertIn("aucune Ticket Evaluation rendue", merged["waiting"][0]["reason"])

    def test_a_prefactoring_is_merged_once_its_product_starts(self):
        tip = self.finished_prefactoring()
        self.code_reviewed(tip, PREFACTORING)
        self.assertEqual([], self.merge()["merged"])

        self.settle()

        self.assertEqual([PREFACTORING], [entry["id"] for entry in self.merge()["merged"]])

    # --- a convoy without the mark -------------------------------------------------------------

    def test_a_convoy_without_the_mark_is_not_touched(self):
        for command in (("settle", PLAIN_CONVOY), ("show", PLAIN_CONVOY, PLAIN_TICKET),
                        ("verdict", PLAIN_CONVOY, PLAIN_TICKET), ("brief", PLAIN_CONVOY, PLAIN_TICKET)):
            with self.subTest(command=command[0]):
                self.refused(*command, "--repo", self.repo, mention="pas un convoi du nouveau flux",
                             status=EXIT_NOT_NEW_FLOW)
        self.assertEqual([], self.launch_records())

    def test_a_ticket_of_another_convoy_is_refused(self):
        self.refused("show", CONVOY, PLAIN_TICKET, "--repo", self.repo, mention="n'appartient pas au convoi")

    def test_settings_without_an_evaluation_block_refuse_the_pass(self):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({"max_sessions": 2}))

        self.refused("settle", CONVOY, "--repo", self.repo, mention="la Ticket Evaluation n'est pas réglée")


    # --- T42: a fresh session per evaluation -----------------------------------------

    def beads(self):
        """The tracker, each Ticket Evaluation record decoded, the mark of a launch
        counted without result set apart."""
        beads = json.loads(self.tracker.read_text())["beads"]
        counted = {}
        for bead_id, bead in beads.items():
            raw = (bead.get("metadata") or {}).get("gc.flow.evaluation")
            if raw is None:
                continue
            record = json.loads(raw)
            for launch in (record.get("request") or {}).get("launches") or []:
                if "refused" in launch:
                    counted.setdefault(bead_id, []).append(launch.pop("refused")["session"])
            bead["metadata"]["gc.flow.evaluation"] = record
        return beads, counted

    def served_session(self):
        """The session that rendered the review of the tests of SLICE."""
        (served,) = [round_["recorded_by"] for round_ in self.shown()["test_review"]["rounds"]]
        return {**SESSION, "GC_SESSION_NAME": served}

    def test_show_names_the_session_that_rendered_the_evaluation(self):
        tip, request = self.open_evaluation()

        self.recorded(self.handed(tip, request))

        self.assertEqual([SESSION["GC_SESSION_NAME"]], [round_["recorded_by"] for round_ in self.evaluation()["rounds"]])

    def test_states_from_a_session_that_rendered_another_review_of_the_convoy_are_refused_and_counted_without_result(self):
        tip, request = self.open_evaluation()
        handed = self.handed(tip, request)
        session = self.served_session()
        before, _ = self.beads()
        sent, products = self.launches(), self.launch_records()

        proc = self.record(handed, env=session)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        text = json.loads(proc.stdout)["error"]
        self.assertIn(session["GC_SESSION_NAME"], text)
        self.assertIn("session neuve", text)
        after, counted = self.beads()
        self.assertEqual({SLICE: [session["GC_SESSION_NAME"]]}, counted)
        self.assertEqual(before, after)
        self.assertEqual((sent, products), (self.launches(), self.launch_records()))
        self.assertEqual([], self.evaluation()["rounds"])
        self.assertNotIn("evaluation", self.shown()["verdicts"])

    def test_an_evaluation_refused_for_its_session_is_launched_once_more_to_another_session(self):
        tip, request = self.open_evaluation()
        self.record(self.handed(tip, request), env=self.served_session())
        self.evaluator("silent", {"look_for": COUNT_SHOWN, "dataset": "content"})

        settled = self.settle()

        self.assertEqual([SLICE], [entry["ticket"] for entry in settled["relaunched"]])
        evaluation = self.evaluation()
        self.assertEqual("favorable", evaluation["state"]["verdict"])
        self.assertEqual(["delivery-evaluator-fixture-2"], [round_["recorded_by"] for round_ in evaluation["rounds"]])

    def test_an_evaluation_refused_for_its_session_twice_stops_the_ticket(self):
        tip, request = self.open_evaluation()
        session = self.served_session()
        self.record(self.handed(tip, request), env=session)
        self.settle()
        again = self.record(self.handed(tip, self.evaluation()["request"]), env=session)
        self.assertEqual(EXIT_REFUSED, again.returncode, again.stdout + again.stderr)

        stopped = self.settle()

        self.assertEqual([{"ticket": SLICE, "stop": "evaluation_no_result"}], stopped["stopped"])
        self.assertEqual([], self.evaluation()["rounds"])
        self.assertEqual(2, len(self.launches()))

    def test_states_are_recorded_under_the_session_and_never_under_the_slot_of_the_agent(self):
        """GC_AGENT names a place in the pool of the agent: the next session
        of the role takes the same one."""
        tip, request = self.open_evaluation()

        self.record_refused(self.handed(tip, request), "session",
                            env={"DELIVERY_ROLE_READ_ONLY": "1", "GC_AGENT": "delivery-evaluator-1"})


if __name__ == "__main__":
    unittest.main()
