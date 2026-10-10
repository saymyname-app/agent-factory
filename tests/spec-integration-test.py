#!/usr/bin/env python3
"""bin/spec-integration on a fake tracker state (T18, af-gmz9s1; Spec
af-wf4w5r §4 and §8, Testing Decisions seam 2): one test per refusal and per
pass, each refusal re-reading the tracker, the evidence store and the
branches to prove nothing was written. Only command lines are exercised. The
product is a copy of the Delivery Fixture City in a throwaway repository
with its own remote; the tests on a merged result are the regression command
of its profile, run and sealed for real by bin/evidence-capture."""

import functools
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import ticket_proofs  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-integration"
STATE_TOOL = ROOT / "bin" / "convoy-state"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY, SPEC = "fx-convoy", "fx-spec"
T1, T2 = "fx-t1", "fx-t2"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
PROTECTED = "main"
INTEGRATION = f"integration/{SPEC}"
TESTS_PIECE = "merged_tests"

EXIT_REFUSED = 1
EXIT_UNRULED = 3
EXIT_NOT_NEW_FLOW = 4

README = "README.md"
DATASET = f"{FIXTURE}/datasets/content.json"
SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE")


def branch_of(ticket):
    return f"ticket/{ticket}"


def staged(helper):
    """A helper whose result is built once and restored afterwards (see
    SpecIntegrationTest.stage), when a test reaches it first: it leaves only
    files (commits, steps and pieces written by the real commands), no
    running process and nothing read against the clock. One stage per helper
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


class SpecIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One directory for the whole class (tests/spec-end-test.py): a stage
        # reached once (the seeded product, two finished tickets) is archived
        # and restored at the same paths, which the stand-ins on the path, the
        # remote of the product and the evidence store hold absolute.
        cls.holder = Path(tempfile.mkdtemp(prefix="spec-integration-test-"))
        cls.tmp = cls.holder / "city"
        cls.stages = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.holder, ignore_errors=True)

    def stage(self, name, build):
        """The state `build` leaves, built once and restored afterwards.
        What it returns is a commit or a tuple of commits: strings."""
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
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.gh_log = self.tmp / "gh.log"
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
            "EVIDENCE_STORE_DIR": str(self.store),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for name in SESSION_IDENTITY:
            self.env.pop(name, None)
        self.base = self.stage("seeded", self.seed)
        self.seeded_footprint = self.footprint()

    def seed(self):
        """What every test starts from, left by real launches and holding
        only files: the stand-ins on the path, the profile, the marked
        convoy, the product with its remote. Returns the first commit of the
        product."""
        # No pull request is ever opened: any call of `gh` is recorded.
        (self.tmp / "path").mkdir()
        gh = self.tmp / "path" / "gh"
        gh.write_text(f'#!/bin/sh\necho "$@" >> "{self.gh_log}"\n')
        gh.chmod(0o755)
        # The real `gc` finds its city from the working directory: called
        # from a merge work tree it finds none (seen on gc/bd 1.2.2,
        # tests/spec-integration-demonstration-test.sh).
        gc = self.tmp / "path" / "gc"
        gc.write_text(
            f'#!/bin/sh\ncase "$PWD/" in "{self.work}"/*) echo "gc bd: not in a city directory" >&2; exit 1;; esac\n'
            f'exec "{FAKE_GC}" "$@"\n')
        gc.chmod(0o755)
        shutil.copy(ROOT / FIXTURE / "descriptor.json", self.profile)
        self.seed_tracker()
        self.seed_repo()
        return self.base

    # --- harness ------------------------------------------------------------

    def seed_tracker(self):
        """A marked convoy of two slices that wait for nothing, and a convoy
        without the mark."""
        def ticket():
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": "## Acceptance criteria\n\n- [ ] Point d'entrée : GET / — Observable : liste — "
                                   "Faux si : une ligne manque\n\n## Target rigs\n\nfx-rig",
                    "metadata": {"gc.ticket_kind": "vertical_slice"}}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [T1, T2]},
            T1: ticket(), T2: ticket(),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket(),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY,
                   "--demonstration-line", f"{T1}=La page d'accueil affiche les trois éléments",
                   "--demonstration-line", f"{T2}=GET /health répond 200",
                   "--user-stories", f"{T1}=1", "--user-stories", f"{T2}=2")

    def seed_repo(self):
        """The product and its remote, the protected branch pushed."""
        # An earlier test of the same run may have imported the fixture: its
        # bytecode cache, once committed, is rewritten by the merged tests and
        # the work tree no longer matches any commit.
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE, ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / README).write_text("Le produit de la fixture.\n")
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

    def remote(self, *args):
        proc = subprocess.run(("git", "--git-dir", str(self.origin), *args), env=self.env, text=True, capture_output=True)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def remote_tip(self, branch=INTEGRATION):
        return self.remote("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")

    def remote_branches(self):
        return sorted((self.remote("for-each-ref", "--format=%(refname:short)", "refs/heads") or "").split())

    def parents(self, commit):
        return self.remote("rev-list", "--parents", "-n", "1", commit).split()[1:]

    def contains(self, tip, commit):
        return subprocess.run(("git", "--git-dir", str(self.origin), "merge-base", "--is-ancestor", commit, tip),
                              env=self.env).returncode == 0

    def run_cmd(self, tool, *args, cwd=None):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=self.env, text=True, capture_output=True, cwd=cwd)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def show(self, expect=0):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket_id):
        return next(t for t in self.show()["tickets"] if t["id"] == ticket_id)

    def edit(self, bead_id, status=None, **metadata):
        state = json.loads(self.tracker.read_text())
        if status is not None:
            state["beads"][bead_id]["status"] = status
        state["beads"][bead_id].setdefault("metadata", {}).update(metadata)
        self.tracker.write_text(json.dumps(state))

    def open(self, *extra, convoy=CONVOY):
        return self.run_cmd(TOOL, "open", convoy, "--repo", self.repo, "--protected", PROTECTED, *extra)

    def opened(self):
        proc = self.open()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def merge(self, *extra, convoy=CONVOY):
        return self.run_cmd(TOOL, "merge", convoy, "--repo", self.repo, "--profile", self.profile, *extra)

    def merged(self, *extra, expect=0):
        proc = self.merge(*extra)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def commit_on(self, ticket, files, message="travail du ticket", start=None):
        """Add one commit to the branch of a ticket (created from the
        integration branch if new) and push it; return its SHA."""
        branch = branch_of(ticket)
        if self.git("rev-parse", "-q", "--verify", f"refs/heads/{branch}", check=False):
            self.git("checkout", "-q", branch)
        else:
            self.git("fetch", "-q", "origin")
            self.git("checkout", "-q", "-b", branch, start or f"origin/{INTEGRATION}")
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

    def finish(self, ticket, commit, reviewed=True):
        """What stands for the author's Ticket Exit « terminé » at `commit`
        (bin/ticket-exit, T11): its TDD proven and its demonstration
        captured there, the sealed records, the Handoff, the exit;
        and, unless `reviewed` is false, for the favorable code review
        (bin/code-review, T14) and the favorable Ticket Evaluation
        (bin/ticket-evaluation, T15) that follow it at that commit."""
        ticket_proofs.finish(self.env, self.repo, CONVOY, ticket, commit, self.base, branch_of(ticket))
        if reviewed:
            self.reviewed(ticket, commit)
            self.evaluated(ticket, commit)

    def json_file(self, name, content):
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def reviewed(self, ticket, commit, findings=(), session=None):
        """A round of the code review of the ticket at `commit`, as a
        reviewer session records it: favorable unless a finding blocks."""
        self.state("open-code-review", CONVOY, ticket, "--kind", "review", "--commit", commit, "--base", self.base)
        return self.state("record-code-review", CONVOY, ticket, "--file", self.json_file(f"review-{ticket}.json", {
            "commit": commit, "recorded_by": session or f"delivery-reviewer-{ticket}-{commit[:6]}", "findings": list(findings), "answers": {}}))

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
            "commit": commit, "recorded_by": f"delivery-evaluator-{ticket}-{commit[:6]}",
            "criteria": [{"number": number, "text": text, "state": "observed", "evidence": "evaluation.seen"}
                         for number, text in enumerate(shown["criteria"], start=1)],
            "demonstration_line": {"text": shown["demonstration_line"], "state": "observed",
                                   "evidence": "evaluation.seen"}}))

    def finished(self, ticket, files, start=None, reviewed=True):
        """A ticket started through the dispatch door, with one commit on its
        branch, that its author has finished; returns that commit."""
        self.state("record-gate", CONVOY, ticket, "--gate", "dispatch")
        self.state("set-branch", CONVOY, ticket, "--branch", branch_of(ticket))
        self.edit(ticket, status="in_progress")
        tip = self.commit_on(ticket, files, start=start)
        self.finish(ticket, tip, reviewed=reviewed)
        return tip

    def judged(self, ticket, commit, state="favorable", kinds=("code_review", "evaluation")):
        """The verdicts of a ticket at `commit`: a favorable one as the
        round of the code review or of the Ticket Evaluation it comes from,
        an unfavorable one as its verdict alone."""
        rounds = {"code_review": self.reviewed, "evaluation": self.evaluated}
        for kind in kinds:
            if state != "favorable":
                self.state("set-verdict", CONVOY, ticket, "--kind", kind, "--state", state, "--commit", commit)
            elif ((self.shown(ticket)[kind] or {}).get("state") or {}).get("commit") != commit:
                rounds[kind](ticket, commit)

    @staged
    def two_finished_tickets(self):
        self.opened()
        return (self.finished(T1, {"docs/t1.md": "tranche 1\n"}), self.finished(T2, {"docs/t2.md": "tranche 2\n"}))

    def store_files(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*") if p.is_file() and p.name != ".seal-key")

    def piece(self, ticket, name=TESTS_PIECE):
        return json.loads((self.store / SPEC / ticket / f"{name}.json").read_text())

    def worktrees(self):
        return [line for line in self.git("worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]

    def snapshot(self):
        proc = self.run_cmd(STATE_TOOL, "show", CONVOY, "--repo", self.repo)
        refs = self.remote("for-each-ref", "--format=%(refname) %(objectname)")
        log = self.write_log.read_text() if self.write_log.exists() else ""
        return (self.tracker.read_bytes(), proc.stdout, self.store_files(), refs, log)

    def assert_refused_and_nothing_written(self, proc_factory, *mentions, status=EXIT_REFUSED):
        """The call is refused, and what is read again is what it was: the
        tracker, the evidence store and every branch of the remote."""
        before = self.snapshot()
        proc = proc_factory()
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        for mention in mentions:
            self.assertIn(mention, answer.get("error") or answer.get("message"))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, len(self.worktrees()))
        return answer

    # --- AC5: the integration branch of the Spec, at publication ---------------

    def test_open_creates_the_integration_branch_at_the_tip_of_the_protected_branch(self):
        self.assertIsNone(self.remote_tip())

        answer = self.opened()
        self.assertEqual(
            {"branch": INTEGRATION, "protected": PROTECTED, "base": self.base, "created": True},
            {key: answer[key] for key in ("branch", "protected", "base", "created")})
        self.assertEqual(self.base, self.remote_tip())
        self.assertEqual(self.base, self.remote_tip(PROTECTED))
        integration = self.show()["convoy"]["integration"]
        self.assertEqual((INTEGRATION, PROTECTED, self.base),
                         (integration["branch"], integration["protected"], integration["base"]))

    def test_open_starts_from_the_tip_of_the_remote_even_when_the_local_branch_is_behind(self):
        other = self.tmp / "other"
        subprocess.run(("git", "clone", "-q", str(self.origin), str(other)), env=self.env, check=True)
        subprocess.run(("git", "-C", str(other), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "ailleurs"), env=self.env, check=True)
        subprocess.run(("git", "-C", str(other), "push", "-q", "origin", PROTECTED), env=self.env, check=True)
        ahead = self.remote_tip(PROTECTED)
        self.assertNotEqual(self.base, ahead)

        self.assertEqual(ahead, self.opened()["base"])
        self.assertEqual(ahead, self.remote_tip())

    def test_open_again_changes_nothing(self):
        self.opened()
        before = self.snapshot()

        answer = self.opened()
        self.assertFalse(answer["created"])
        self.assertEqual(before, self.snapshot())

    def test_open_completes_a_branch_created_but_not_recorded(self):
        self.git("push", "-q", "origin", f"{self.base}:refs/heads/{INTEGRATION}")

        answer = self.opened()
        self.assertFalse(answer["created"])
        self.assertEqual(self.base, self.show()["convoy"]["integration"]["base"])

    def test_open_refuses_a_branch_of_that_name_that_already_carries_commits(self):
        self.git("checkout", "-q", "-b", INTEGRATION)
        self.git("commit", "-q", "--allow-empty", "-m", "d'où vient ce commit ?")
        self.git("push", "-q", "origin", INTEGRATION)
        self.git("checkout", "-q", "--detach", self.base)
        self.git("branch", "-q", "-D", INTEGRATION)

        self.assert_refused_and_nothing_written(self.open, INTEGRATION, "existe déjà")

    def test_open_on_a_convoy_without_the_mark_creates_no_branch(self):
        before = self.snapshot()

        proc = self.open(convoy=PLAIN_CONVOY)
        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual([PROTECTED], self.remote_branches())

    def test_open_refuses_a_protected_branch_that_does_not_exist(self):
        self.assert_refused_and_nothing_written(
            lambda: self.run_cmd(TOOL, "open", CONVOY, "--repo", self.repo, "--protected", "trunk"), "trunk")
        self.assertEqual([PROTECTED], self.remote_branches())

    def test_open_refuses_a_directory_that_is_not_a_repository(self):
        self.assert_refused_and_nothing_written(
            lambda: self.run_cmd(TOOL, "open", CONVOY, "--repo", self.tmp / "locks", "--protected", PROTECTED),
            "dépôt Git")

    def test_open_refuses_a_convoy_that_names_no_spec(self):
        state = json.loads(self.tracker.read_text())
        del state["beads"][CONVOY]["metadata"]["gc.spec_id"]
        self.tracker.write_text(json.dumps(state))

        self.assert_refused_and_nothing_written(self.open, "Spec")

    # --- AC1: two tickets finished at once, merged one after the other ---------

    def test_two_finished_tickets_are_merged_one_after_the_other_each_with_its_test_record(self):
        tip1, tip2 = self.two_finished_tickets()

        answer = self.merged()
        self.assertEqual([T1, T2], [entry["id"] for entry in answer["merged"]])
        first, second = (entry["commit"] for entry in answer["merged"])
        # Two successive merges: the second is made on the result of the first.
        self.assertEqual([self.base, tip1], self.parents(first))
        self.assertEqual([first, tip2], self.parents(second))
        self.assertEqual(second, self.remote_tip())
        for ticket, tip, commit in ((T1, tip1, first), (T2, tip2, second)):
            shown = self.shown(ticket)
            self.assertEqual(("merged", tip, commit),
                             (shown["merge"]["outcome"], shown["merge"]["ticket_commit"], shown["merge"]["commit"]))
            # The test record carries the commit of the merged result.
            self.assertEqual(commit, shown["evidence"][TESTS_PIECE]["commit"])
            record = self.piece(ticket)
            self.assertEqual((commit, 0), (record["commit"], record["exit_code"]))
            self.assertIn("regression.py", " ".join(record["command"]))
            verified = self.run_cmd(CAPTURE_TOOL, "verify", CONVOY, ticket, "--piece", TESTS_PIECE)
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)

    def test_the_protected_branch_receives_no_commit_and_no_pull_request_is_opened(self):
        self.two_finished_tickets()

        self.merged()
        self.assertEqual(self.base, self.remote_tip(PROTECTED))
        self.assertEqual([INTEGRATION, PROTECTED, branch_of(T1), branch_of(T2)], self.remote_branches())
        self.assertFalse(self.gh_log.exists(), "gh was called")
        self.assertEqual(1, len(self.worktrees()))

    def test_a_second_pass_merges_nothing_more(self):
        self.two_finished_tickets()
        self.merged()
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual([], answer["merged"])
        self.assertEqual(before, self.snapshot())

    def test_two_merge_commands_at_once_never_merge_at_the_same_time(self):
        tip1, tip2 = self.two_finished_tickets()

        with ThreadPoolExecutor(max_workers=2) as pool:
            procs = list(pool.map(lambda _: self.merge(), range(2)))
        for proc in procs:
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        merged = [entry["id"] for proc in procs for entry in json.loads(proc.stdout)["merged"]]
        self.assertEqual([T1, T2], sorted(merged))
        # One line of merges: tip -> merge of T2 -> merge of T1 -> base.
        second = self.remote_tip()
        first = self.parents(second)[0]
        self.assertEqual(tip2, self.parents(second)[1])
        self.assertEqual([self.base, tip1], self.parents(first))

    def test_limit_merges_that_many_tickets_and_leaves_the_others_for_the_next_pass(self):
        self.two_finished_tickets()

        answer = self.merged("--limit", "1")
        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        self.assertIsNone(self.shown(T2)["merge"])
        self.assertEqual([T2], [entry["id"] for entry in self.merged("--limit", "1")["merged"]])

    def test_a_ticket_that_is_not_finished_is_not_merged(self):
        self.opened()
        self.state("record-gate", CONVOY, T1, "--gate", "dispatch")
        self.state("set-branch", CONVOY, T1, "--branch", branch_of(T1))
        self.edit(T1, status="in_progress")
        self.commit_on(T1, {"docs/t1.md": "en cours\n"})
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual([], answer["merged"])
        self.assertEqual(before, self.snapshot())

    def test_a_ticket_finished_at_an_older_commit_than_its_tip_is_not_merged(self):
        self.opened()
        self.finished(T1, {"docs/t1.md": "tranche 1\n"}, reviewed=False)
        self.commit_on(T1, {"docs/t1.md": "repris par une session neuve\n"})
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual([], answer["merged"])
        self.assertEqual([T1], [entry["id"] for entry in answer["waiting"]])
        self.assertIn("terminé", answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())

    def test_a_ticket_with_an_unfavorable_verdict_is_not_merged(self):
        self.opened()
        tip = self.finished(T1, {"docs/t1.md": "tranche 1\n"})
        self.judged(T1, tip, kinds=("code_review",))
        self.judged(T1, tip, state="unfavorable", kinds=("evaluation",))
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual([], answer["merged"])
        self.assertIn("défavorable", answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())

    def test_tickets_judged_favorably_at_their_tip_are_merged(self):
        tip1, tip2 = self.two_finished_tickets()
        self.judged(T1, tip1)
        self.judged(T2, tip2)

        answer = self.merged()
        self.assertEqual([T1, T2], [entry["id"] for entry in answer["merged"]])
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, self.shown(T2)["counters"])

    # --- the code review of a ticket (T14): no merge without a favorable verdict ---

    CITED = {"axis": "spec", "blocking": True, "summary": "La liste n'affiche que deux éléments.",
             "citation": {"source": "ticket", "quote": "Point d'entrée : GET / — Observable : liste"}}

    @staged
    def unreviewed_ticket(self):
        """A ticket whose author has finished, and that no reviewer has read."""
        self.opened()
        return self.finished(T1, {"docs/t1.md": "tranche 1\n"}, reviewed=False)

    def assert_not_merged(self, mention):
        before = self.snapshot()
        answer = self.merged()
        self.assertEqual(([], [], [T1]), (answer["merged"], answer["refused"], [e["id"] for e in answer["waiting"]]))
        self.assertIn(mention, answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.base, self.remote_tip())

    def test_a_finished_ticket_without_a_code_review_is_not_merged(self):
        self.unreviewed_ticket()

        self.assert_not_merged("aucune revue de code")

    def test_a_code_review_that_gave_no_verdict_yet_is_not_an_agreement(self):
        tip = self.unreviewed_ticket()
        self.state("open-code-review", CONVOY, T1, "--kind", "review", "--commit", tip, "--base", self.base)
        self.state("launch-code-review", CONVOY, T1, "--bead", "fx-r1")

        self.assert_not_merged("revue de code en cours")

    def test_a_ticket_with_a_blocking_finding_without_a_favorable_verdict_is_not_merged(self):
        # AC3, first half.
        tip = self.unreviewed_ticket()
        self.reviewed(T1, tip, findings=[self.CITED])

        self.assert_not_merged("F1.1")

    def test_a_blocking_finding_answered_but_not_judged_yet_is_not_merged(self):
        tip = self.unreviewed_ticket()
        self.reviewed(T1, tip, findings=[self.CITED])
        self.state("respond-code-review", CONVOY, T1, "--file", self.json_file("responses.json", {
            "responses": {"F1.1": {"response": "contested", "reason": "La liste affiche bien trois éléments."}}}))

        self.assert_not_merged("F1.1")

    def judged_findings(self, state):
        """Two Blocking Findings, one fixed and one contested, judged by a
        second reviewer session at the tip the author finished at again."""
        reviewed = self.unreviewed_ticket()
        self.reviewed(T1, reviewed, findings=[self.CITED, {**self.CITED, "summary": "Le troisième élément manque."}])
        tip = self.commit_on(T1, {"docs/t1.md": "tranche 1, corrigée\n"})
        self.finish(T1, tip, reviewed=False)
        self.state("respond-code-review", CONVOY, T1, "--file", self.json_file("responses.json", {"responses": {
            "F1.1": {"response": "fixed", "commit": tip},
            "F1.2": {"response": "contested", "reason": "Les trois éléments sont rendus."}}}))
        self.state("open-code-review", CONVOY, T1, "--kind", "judgement", "--commit", tip, "--base", reviewed)
        self.state("record-code-review", CONVOY, T1, "--file", self.json_file("judgement.json", {
            "commit": tip, "recorded_by": "delivery-reviewer-fx2",
            "judgements": {"F1.1": {"state": "favorable"}, "F1.2": state}}))
        return tip

    def test_every_blocking_finding_fixed_or_contested_and_judged_favorably_lets_the_ticket_merge(self):
        # AC3, second half.
        tip = self.judged_findings({"state": "favorable"})
        self.evaluated(T1, tip)

        answer = self.merged()

        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        self.assertTrue(self.contains(self.remote_tip(), tip))

    # --- the Ticket Evaluation of a ticket (T15): no merge without a favorable one ---

    @staged
    def reviewed_ticket(self):
        """A finished ticket whose code review is favorable, and that no
        Evaluator has evaluated."""
        tip = self.unreviewed_ticket()
        self.reviewed(T1, tip)
        return tip

    def not_merged(self, mention):
        before = self.snapshot()
        answer = self.merged()
        self.assertEqual(([], [T1]), (answer["merged"], [entry["id"] for entry in answer["waiting"]]))
        self.assertIn(mention, answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())

    def test_a_reviewed_ticket_without_a_ticket_evaluation_is_not_merged(self):
        self.reviewed_ticket()

        self.not_merged("aucune Ticket Evaluation rendue")

    def test_a_ticket_evaluation_that_gave_no_state_yet_is_not_an_agreement(self):
        tip = self.reviewed_ticket()
        self.state("open-evaluation", CONVOY, T1, "--commit", tip, "--file", self.json_file("request.json", {
            "roles": {"author": None, "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": "/launch.json"}]}))

        self.not_merged("Ticket Evaluation en cours")

    def test_a_favorable_evaluation_verdict_written_without_its_evaluation_is_not_an_agreement(self):
        tip = self.reviewed_ticket()
        self.state("set-verdict", CONVOY, T1, "--kind", "evaluation", "--state", "favorable", "--commit", tip)

        self.not_merged("aucune Ticket Evaluation rendue")

    def test_a_ticket_evaluated_favorably_at_its_tip_is_merged(self):
        tip = self.reviewed_ticket()
        self.evaluated(T1, tip)

        self.assertEqual([T1], [entry["id"] for entry in self.merged()["merged"]])

    def test_one_blocking_finding_judged_unfavorably_keeps_the_ticket_out_of_the_merge(self):
        self.judged_findings({"state": "unfavorable", "reason": "La liste n'a toujours que deux éléments."})

        self.assert_not_merged("F1.2")

    def test_a_favorable_verdict_written_without_its_review_does_not_let_the_ticket_merge(self):
        tip = self.unreviewed_ticket()
        self.state("set-verdict", CONVOY, T1, "--kind", "code_review", "--state", "favorable", "--commit", tip)

        self.assert_not_merged("aucune revue de code")

    # --- AC2: a commit added after a verdict -----------------------------------

    def test_a_commit_newer_than_the_judged_commit_refuses_the_merge_and_invalidates_the_verdicts(self):
        tip1, judged = self.two_finished_tickets()
        self.judged(T2, judged)
        newer = self.commit_on(T2, {"docs/t2.md": "retouche après le verdict\n"})
        self.finish(T2, newer, reviewed=False)

        answer = self.merged(expect=EXIT_REFUSED)
        self.assertFalse(answer["ok"])
        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        refused = answer["refused"]
        self.assertEqual([T2], [entry["id"] for entry in refused])
        self.assertEqual(["code_review", "evaluation"], refused[0]["invalidated"])
        self.assertIn("verdict", refused[0]["reason"])
        self.assertIn(newer[:12], refused[0]["reason"])
        # Nothing of the second ticket reached the integration branch.
        self.assertFalse(self.contains(self.remote_tip(), judged))
        shown = self.shown(T2)
        self.assertIsNone(shown["merge"])
        for kind in ("code_review", "evaluation"):
            verdict = shown["verdicts"][kind]
            self.assertIs(False, verdict["valid"])
            self.assertEqual(newer, verdict["invalidated"]["tip"])
            self.assertEqual(judged, verdict["commit"])
        self.assertEqual(1, shown["counters"]["resumes"])
        self.assertEqual(0, shown["counters"]["correction_rounds"])

    def test_an_invalidated_verdict_counts_one_resume_whatever_the_number_of_passes(self):
        _, judged = self.two_finished_tickets()
        self.judged(T2, judged)
        self.finish(T2, self.commit_on(T2, {"docs/t2.md": "retouche après le verdict\n"}), reviewed=False)
        self.merged(expect=EXIT_REFUSED)
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual([], answer["merged"])
        self.assertEqual([], answer["refused"])
        self.assertIn("rejouer", answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, self.shown(T2)["counters"]["resumes"])

    def test_verdicts_replayed_on_the_new_tip_let_the_ticket_merge(self):
        _, judged = self.two_finished_tickets()
        self.judged(T2, judged)
        newer = self.commit_on(T2, {"docs/t2.md": "retouche après le verdict\n"})
        self.finish(T2, newer, reviewed=False)
        self.merged(expect=EXIT_REFUSED)

        self.judged(T2, newer)
        answer = self.merged()
        self.assertEqual([T2], [entry["id"] for entry in answer["merged"]])
        shown = self.shown(T2)
        self.assertIs(True, shown["verdicts"]["evaluation"]["valid"])
        self.assertNotIn("invalidated", shown["verdicts"]["evaluation"])
        self.assertEqual(1, shown["counters"]["resumes"])

    def test_one_stale_verdict_is_enough_to_refuse_and_only_that_one_is_invalidated(self):
        self.opened()
        judged = self.finished(T1, {"docs/t1.md": "tranche 1\n"})
        self.judged(T1, judged, kinds=("code_review",))
        newer = self.commit_on(T1, {"docs/t1.md": "retouche\n"})
        self.finish(T1, newer, reviewed=False)
        self.judged(T1, newer, kinds=("evaluation",))

        answer = self.merged(expect=EXIT_REFUSED)
        self.assertEqual(["code_review"], answer["refused"][0]["invalidated"])
        shown = self.shown(T1)
        self.assertIs(True, shown["verdicts"]["evaluation"]["valid"])
        self.assertEqual(1, shown["counters"]["resumes"])
        self.assertEqual(self.base, self.remote_tip())

    # --- AC3: a conflict goes back to the author -------------------------------

    @staged
    def conflicting_tickets(self):
        self.opened()
        return (self.finished(T1, {README: "Le produit, vu par la tranche 1.\n"}),
                self.finished(T2, {README: "Le produit, vu par la tranche 2.\n"}))

    def test_a_conflict_merges_nothing_and_returns_the_ticket_to_its_author(self):
        tip1, tip2 = self.conflicting_tickets()

        answer = self.merged()
        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        first = answer["merged"][0]["commit"]
        returned = answer["returned"]
        self.assertEqual([(T2, "conflict")], [(entry["id"], entry["cause"]) for entry in returned])
        self.assertEqual([README], returned[0]["files"])
        self.assertIn("auteur", returned[0]["reason"])
        # Nothing of the second ticket was merged, and nobody resolved it.
        self.assertEqual(first, self.remote_tip())
        self.assertEqual(tip2, self.remote_tip(branch_of(T2)))
        self.assertFalse(self.contains(first, tip2))
        shown = self.shown(T2)
        self.assertEqual(("conflict", tip2, first),
                         (shown["merge"]["outcome"], shown["merge"]["ticket_commit"], shown["merge"]["integration"]))
        self.assertNotIn("commit", shown["merge"])
        self.assertNotIn(TESTS_PIECE, shown["evidence"])
        self.assertEqual(1, len(self.worktrees()))
        self.assertNotIn("sling", self.write_log.read_text())

    def test_a_returned_ticket_is_not_tried_again_until_its_author_adds_a_commit(self):
        self.conflicting_tickets()
        self.merged()
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual(([], []), (answer["merged"], answer["returned"]))
        self.assertIn("auteur", answer["waiting"][0]["reason"])
        self.assertEqual(before, self.snapshot())

    def test_the_author_takes_up_the_integration_tip_and_the_ticket_merges(self):
        self.conflicting_tickets()
        first = self.merged()["merged"][0]["commit"]

        # A fresh session of the author takes up the integration tip.
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", branch_of(T2))
        self.git("merge", "-q", "--no-edit", f"origin/{INTEGRATION}", check=False)
        (self.repo / README).write_text("Le produit, vu par les tranches 1 et 2.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "conflit résolu")
        self.git("push", "-q", "origin", branch_of(T2))
        resolved = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        self.finish(T2, resolved)

        answer = self.merged()
        self.assertEqual([T2], [entry["id"] for entry in answer["merged"]])
        second = answer["merged"][0]["commit"]
        self.assertEqual([first, resolved], self.parents(second))
        self.assertEqual("merged", self.shown(T2)["merge"]["outcome"])

    # --- AC4: red tests on the merged result ------------------------------------

    @staged
    def red_ticket(self):
        """T2 alone breaks the regression command of the profile."""
        self.opened()
        broken = json.dumps({"state": "content", "generated_at": "2026-01-01T00:00:00Z", "items": ["alpha"]})
        return (self.finished(T1, {"docs/t1.md": "tranche 1\n"}), self.finished(T2, {DATASET: broken}))

    def test_red_tests_on_the_merged_result_are_not_pushed_and_belong_to_the_ticket_being_merged(self):
        _, tip2 = self.red_ticket()

        answer = self.merged()
        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        first = answer["merged"][0]["commit"]
        returned = answer["returned"]
        self.assertEqual([(T2, "red")], [(entry["id"], entry["cause"]) for entry in returned])
        self.assertNotEqual(0, returned[0]["tests"]["exit_code"])
        # The merge was not pushed: the integration branch is where the first merge left it.
        self.assertEqual(first, self.remote_tip())
        self.assertFalse(self.contains(first, tip2))
        # The red is attributed to the ticket being merged, with its record.
        shown = self.shown(T2)
        self.assertEqual(("red", tip2, first),
                         (shown["merge"]["outcome"], shown["merge"]["ticket_commit"], shown["merge"]["integration"]))
        record = self.piece(T2)
        self.assertEqual(shown["merge"]["commit"], record["commit"])
        self.assertNotEqual(0, record["exit_code"])
        self.assertIn("absent from the home page", record["output"])
        self.assertEqual("merged", self.shown(T1)["merge"]["outcome"])

    def test_the_integration_branch_stays_green_after_a_red_merge(self):
        self.red_ticket()
        self.merged()

        checkout = self.tmp / "checkout"
        subprocess.run(("git", "clone", "-q", "-b", INTEGRATION, str(self.origin), str(checkout)), env=self.env, check=True)
        proc = subprocess.run(("python3", f"{FIXTURE}/tests/regression.py"), cwd=checkout, env=self.env)
        self.assertEqual(0, proc.returncode)

    def test_a_red_ticket_is_not_tried_again_until_its_author_adds_a_commit(self):
        self.red_ticket()
        self.merged()
        before = self.snapshot()

        answer = self.merged()
        self.assertEqual(([], []), (answer["merged"], answer["returned"]))
        self.assertEqual(before, self.snapshot())

    # --- AC6: the integration branch takes up the protected branch first -------

    def advance_protected(self, files, message="avance de la branche protégée"):
        self.git("checkout", "-q", PROTECTED)
        for path, content in files.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.git("push", "-q", "origin", PROTECTED)
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        self.git("branch", "-q", "-f", PROTECTED, self.base)
        return tip

    def test_the_integration_branch_contains_the_tip_of_the_protected_branch_before_a_ticket_is_merged(self):
        tip1, _ = self.two_finished_tickets()
        ahead = self.advance_protected({"docs/ailleurs.md": "fusionné ailleurs\n"})

        answer = self.merged()
        first = answer["merged"][0]["commit"]
        takeover = answer["takeover"]["commit"]
        # Read on the branches: the merge of the ticket sits on a commit that holds the protected tip.
        self.assertEqual([takeover, tip1], self.parents(first))
        self.assertEqual([self.base, ahead], self.parents(takeover))
        self.assertTrue(self.contains(self.remote_tip(), ahead))
        self.assertEqual(ahead, self.remote_tip(PROTECTED))

    def test_no_takeover_when_the_integration_branch_already_holds_the_protected_tip(self):
        self.two_finished_tickets()

        self.assertIsNone(self.merged()["takeover"])

    def test_a_takeover_in_conflict_merges_no_ticket(self):
        self.opened()
        self.finished(T1, {README: "Le produit, vu par la tranche 1.\n"})
        self.merged()
        self.finished(T2, {"docs/t2.md": "tranche 2\n"})
        self.advance_protected({README: "Le produit, vu d'ailleurs.\n"})

        answer = self.assert_refused_and_nothing_written(self.merge, "branche protégée", "conflit")
        self.assertNotIn("returned", answer)

    def test_a_red_takeover_is_not_pushed_and_no_ticket_is_blamed(self):
        self.two_finished_tickets()
        self.advance_protected({DATASET: json.dumps({"state": "content", "items": []})})
        refs = self.remote("for-each-ref", "--format=%(refname) %(objectname)")

        proc = self.merge()

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout)["error"]
        self.assertIn("branche protégée", error)
        self.assertIn("rouge", error)
        # Nothing is pushed and no ticket is blamed: the red belongs to the branch (T21).
        self.assertEqual(refs, self.remote("for-each-ref", "--format=%(refname) %(objectname)"))
        self.assertEqual(self.base, self.remote_tip())
        self.assertEqual((None, None), (self.shown(T1)["merge"], self.shown(T2)["merge"]))
        self.assertEqual(1, len(self.worktrees()))

    # --- T21: a red integration branch stops the merges, its repair restores it ---

    REPAIR = "fx-r1"
    BROKEN = json.dumps({"state": "content", "items": []})

    def red(self):
        return self.show()["convoy"]["integration_red"]

    @staged
    def red_takeover(self):
        """Two finished tickets, and a protected branch whose tip turns the
        regression command red once the integration branch takes it up; the
        merge command has seen it. Returns that tip."""
        self.two_finished_tickets()
        ahead = self.advance_protected({DATASET: self.BROKEN})
        self.assertEqual(EXIT_REFUSED, self.merge().returncode)
        return ahead

    def advance_protected_again(self, files, message):
        """One more commit on the protected branch, on top of its remote tip."""
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-B", PROTECTED, f"origin/{PROTECTED}")
        for path, content in files.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.git("push", "-q", "origin", PROTECTED)
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        self.git("branch", "-q", "-f", PROTECTED, self.base)
        return tip

    def repair_ticket(self):
        """The repair of the red, tracked by the convoy as the patch door
        leaves it, and named on the red as the advance command does."""
        state = json.loads(self.tracker.read_text())
        state["beads"][self.REPAIR] = {
            "title": "Rétablir le contrôle rouge", "status": "open", "issue_type": "task",
            "description": "## Acceptance criteria\n\n- [ ] Point d'entrée : la commande de régression — Observable : "
                           "code 0 — Faux si : code non nul\n\n## Target rigs\n\nfx-rig",
            "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append(self.REPAIR)
        self.tracker.write_text(json.dumps(state))
        self.state("mark", CONVOY, "--demonstration-line", f"{self.REPAIR}=La commande de régression se termine avec le code 0")
        self.state("set-integration-repair", CONVOY, "--ticket", self.REPAIR)

    def repaired(self, dataset=None):
        """The author of the repair takes up the integration tip and the
        protected branch, restores the data set, and finishes."""
        self.state("record-gate", CONVOY, self.REPAIR, "--gate", "dispatch")
        self.state("set-branch", CONVOY, self.REPAIR, "--branch", branch_of(self.REPAIR))
        self.edit(self.REPAIR, status="in_progress")
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", branch_of(self.REPAIR), f"origin/{INTEGRATION}")
        self.git("merge", "-q", "--no-edit", f"origin/{PROTECTED}")
        (self.repo / DATASET).write_text(dataset if dataset is not None else (ROOT / DATASET).read_text())
        (self.repo / "docs").mkdir(exist_ok=True)
        (self.repo / "docs" / "repair.md").write_text("le contrôle rétabli\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "repair du contrôle rouge")
        self.git("push", "-q", "origin", branch_of(self.REPAIR))
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", self.base)
        self.finish(self.REPAIR, tip)
        return tip

    def test_a_red_takeover_records_the_red_of_the_integration_branch_and_quotes_its_control(self):
        self.two_finished_tickets()
        ahead = self.advance_protected({DATASET: self.BROKEN})

        answer = self.merged(expect=EXIT_REFUSED)

        red = self.red()
        self.assertEqual((self.base, ahead), (red["integration"], red["protected"]))
        self.assertIn("regression.py", red["control"])
        self.assertIn(INTEGRATION, red["control"])
        self.assertIn("absent from the home page", red["detail"])
        self.assertNotIn("repair", red)
        self.assertEqual(red["control"], answer["red"]["control"])
        self.assertIn(red["control"], answer["error"])

    def test_merge_refuses_while_the_integration_branch_is_red_and_writes_nothing(self):
        self.red_takeover()
        self.repair_ticket()

        answer = self.assert_refused_and_nothing_written(self.merge, "branche d'intégration rouge", self.red()["control"])

        self.assertEqual(self.REPAIR, answer["red"]["repair"])
        self.assertEqual([], answer.get("merged", []))
        self.assertEqual(self.base, self.remote_tip())

    def test_merge_refuses_on_tests_recorded_red_at_the_tip_of_the_integration_branch(self):
        # The false state of the ticket: the red is on the tip itself, and two tickets are ready.
        self.two_finished_tickets()
        self.state("record-integration-red", CONVOY, "--commit", self.base, "--integration", self.base,
                   "--protected", self.base, "--control", "commande de régression : code 1")
        self.repair_ticket()

        self.assert_refused_and_nothing_written(self.merge, "branche d'intégration rouge", "commande de régression : code 1")
        self.assertEqual((None, None), (self.shown(T1)["merge"], self.shown(T2)["merge"]))

    def test_the_repair_of_the_red_is_the_one_ticket_merged_and_the_branch_is_green_again(self):
        ahead = self.red_takeover()
        self.repair_ticket()
        tip = self.repaired()

        answer = self.merged()

        self.assertEqual([self.REPAIR], [entry["id"] for entry in answer["merged"]])
        self.assertEqual(0, answer["merged"][0]["tests"]["exit_code"])
        self.assertEqual(sorted([T1, T2]), sorted(entry["id"] for entry in answer["waiting"]))
        # Read on the branches: the integration branch holds the protected tip and the repair, and nothing else.
        self.assertTrue(self.contains(self.remote_tip(), ahead))
        self.assertTrue(self.contains(self.remote_tip(), tip))
        self.assertEqual("merged", self.shown(self.REPAIR)["merge"]["outcome"])
        self.assertEqual((None, None), (self.shown(T1)["merge"], self.shown(T2)["merge"]))
        # The condition is gone: the red is withdrawn by the command that saw the green.
        self.assertIsNone(self.red())

    def test_the_merges_resume_by_themselves_once_the_repair_is_merged(self):
        self.red_takeover()
        self.repair_ticket()
        self.repaired()
        self.merged()

        answer = self.merged()

        self.assertEqual(sorted([T1, T2]), sorted(entry["id"] for entry in answer["merged"]))

    def test_a_repair_that_leaves_the_branch_red_is_returned_and_the_red_stays(self):
        self.red_takeover()
        self.repair_ticket()
        self.repaired(dataset=self.BROKEN)
        control = self.red()["control"]

        answer = self.merged()

        self.assertEqual([(self.REPAIR, "red")], [(entry["id"], entry["cause"]) for entry in answer["returned"]])
        self.assertEqual([], answer["merged"])
        self.assertEqual(self.base, self.remote_tip())
        self.assertEqual((control, self.REPAIR), (self.red()["control"], self.red()["repair"]))

    def test_the_merges_resume_by_themselves_once_the_protected_branch_is_green_again(self):
        self.red_takeover()
        self.repair_ticket()
        mended = self.advance_protected_again(
            {DATASET: (ROOT / DATASET).read_text()}, "la branche protégée réparée ailleurs")

        answer = self.merged()

        self.assertIsNone(self.red())
        self.assertEqual(mended, answer["takeover"]["protected"])
        self.assertEqual(sorted([T1, T2]), sorted(entry["id"] for entry in answer["merged"]))
        self.assertTrue(self.contains(self.remote_tip(), mended))

    def test_a_branch_checked_again_and_still_red_stays_red_under_its_new_tips(self):
        first = self.red_takeover()
        self.repair_ticket()
        second = self.advance_protected_again(
            {"docs/ailleurs.md": "autre chose, le jeu de données toujours cassé\n"}, "avance, toujours cassée")

        answer = self.merged(expect=EXIT_REFUSED)

        red = self.red()
        self.assertNotEqual(first, second)
        self.assertEqual((self.base, second), (red["integration"], red["protected"]))
        self.assertEqual(self.REPAIR, red["repair"])
        self.assertIn("branche d'intégration rouge", answer["error"])
        self.assertEqual(self.base, self.remote_tip())
        self.assertEqual((None, None), (self.shown(T1)["merge"], self.shown(T2)["merge"]))

    # --- what the command refuses outright ------------------------------------

    def test_merge_on_a_convoy_without_the_mark_does_nothing(self):
        before = self.snapshot()

        proc = self.merge(convoy=PLAIN_CONVOY)
        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.snapshot())

    def test_merge_refuses_a_convoy_without_an_integration_branch(self):
        self.assert_refused_and_nothing_written(self.merge, "branche d'intégration")

    def test_merge_refuses_an_integration_branch_that_is_gone(self):
        self.two_finished_tickets()
        self.git("push", "-q", "origin", f":refs/heads/{INTEGRATION}")

        self.assert_refused_and_nothing_written(self.merge, INTEGRATION, "introuvable")

    def test_merge_refuses_a_profile_without_a_regression_command(self):
        self.two_finished_tickets()
        descriptor = json.loads(self.profile.read_text())
        del descriptor["launch"]["regression_command"]
        self.profile.write_text(json.dumps(descriptor))

        self.assert_refused_and_nothing_written(self.merge, "regression_command")

    def test_merge_without_a_ready_ticket_asks_nothing_of_the_profile(self):
        self.opened()
        self.profile.unlink()

        self.assertEqual([], self.merged()["merged"])

    def test_merge_stops_on_a_state_without_rule(self):
        self.two_finished_tickets()
        self.edit(T2, status="closed")

        answer = self.assert_refused_and_nothing_written(self.merge, "état sans règle", status=EXIT_UNRULED)
        self.assertNotIn("merged", answer)

    def test_a_parked_ticket_is_not_merged(self):
        self.two_finished_tickets()
        self.state("park", CONVOY, T2, "--cause", "operator_request", "--detail", "Un accès manque")

        answer = self.merged()
        self.assertEqual([T1], [entry["id"] for entry in answer["merged"]])
        self.assertIn("parqué", answer["waiting"][0]["reason"])
        self.assertIsNone(self.shown(T2)["merge"])

    # --- T23: the one tip of the end-of-Spec gate (take-up) ---------------------

    def take_up(self, *extra, convoy=CONVOY):
        return self.run_cmd(TOOL, "take-up", convoy, "--repo", self.repo, "--profile", self.profile, *extra)

    def taken_up(self, *extra, expect=0):
        proc = self.take_up(*extra)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def counters(self):
        return self.show()["convoy"]["counters"]

    def test_take_up_runs_the_regression_command_on_the_tip_even_with_nothing_to_take_up(self):
        self.opened()
        before = self.snapshot()

        answer = self.taken_up()

        self.assertEqual((True, INTEGRATION, PROTECTED), (answer["ok"], answer["branch"], answer["protected"]))
        self.assertEqual((self.base, self.base, None), (answer["integration"], answer["protected_tip"], answer["takeover"]))
        tests = answer["tests"]
        self.assertIn("regression.py", tests["command"])
        self.assertEqual((0, self.base), (tests["exit_code"], tests["commit"]))
        # Nothing to push, nothing to record.
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, len(self.worktrees()))

    def test_take_up_pushes_the_takeover_of_the_protected_branch_once_its_tests_are_green(self):
        self.opened()
        ahead = self.advance_protected({"docs/ailleurs.md": "fusionné ailleurs\n"})

        answer = self.taken_up()

        tip = answer["integration"]
        self.assertEqual(tip, self.remote_tip())
        self.assertEqual([self.base, ahead], self.parents(tip))
        self.assertEqual((ahead, tip), (answer["protected_tip"], answer["takeover"]["commit"]))
        self.assertEqual(tip, answer["tests"]["commit"])
        self.assertEqual(ahead, self.remote_tip(PROTECTED))
        self.assertIsNone(self.red())
        self.assertEqual({"end_rounds": 0}, self.counters())

    def test_a_red_take_up_is_not_pushed_and_records_the_red_of_the_integration_branch(self):
        self.opened()
        ahead = self.advance_protected({DATASET: self.BROKEN})
        refs = self.remote("for-each-ref", "--format=%(refname) %(objectname)")

        answer = self.taken_up(expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        red = self.red()
        self.assertEqual((self.base, ahead), (red["integration"], red["protected"]))
        self.assertIn("regression.py", red["control"])
        self.assertEqual(red["control"], answer["red"]["control"])
        self.assertIn(red["control"], answer["error"])
        self.assertEqual(refs, self.remote("for-each-ref", "--format=%(refname) %(objectname)"))
        # Asked without --end-round: the red counts no round of the end of the Spec.
        self.assertEqual({"end_rounds": 0}, self.counters())
        self.assertEqual(1, len(self.worktrees()))

    def test_a_red_take_up_of_the_end_of_the_spec_counts_one_round_once(self):
        self.opened()
        self.advance_protected({DATASET: self.BROKEN})

        self.taken_up("--end-round", expect=EXIT_REFUSED)

        self.assertEqual({"end_rounds": 1}, self.counters())
        self.assertIn("regression.py", self.red()["control"])

        # Asked again under that red: refused before any control, nothing counted.
        answer = self.assert_refused_and_nothing_written(
            lambda: self.take_up("--end-round"), "branche d'intégration rouge", self.red()["control"])
        self.assertEqual(self.red()["control"], answer["red"]["control"])
        self.assertEqual({"end_rounds": 1}, self.counters())

    def test_a_take_up_in_conflict_pushes_and_records_nothing(self):
        self.opened()
        self.finished(T1, {README: "Le produit, vu par la tranche 1.\n"})
        self.merged()
        self.advance_protected({README: "Le produit, vu d'ailleurs.\n"})

        self.assert_refused_and_nothing_written(lambda: self.take_up("--end-round"), "branche protégée", "conflit")

        self.assertIsNone(self.red())
        self.assertEqual({"end_rounds": 0}, self.counters())

    def test_take_up_refuses_outright_what_merge_refuses(self):
        # No integration branch yet.
        self.assert_refused_and_nothing_written(self.take_up, "branche d'intégration")
        self.opened()
        self.assert_refused_and_nothing_written(lambda: self.take_up("--timeout", "bientôt"), "--timeout")
        self.assert_refused_and_nothing_written(lambda: self.take_up("--timeout", "0"), "--timeout")
        descriptor = json.loads(self.profile.read_text())
        del descriptor["launch"]["regression_command"]
        self.profile.write_text(json.dumps(descriptor))
        self.assert_refused_and_nothing_written(self.take_up, "regression_command")

    def test_take_up_stops_on_a_state_without_rule_and_leaves_an_unmarked_convoy_alone(self):
        self.opened()
        self.edit(T2, status="closed")
        self.assert_refused_and_nothing_written(self.take_up, "état sans règle", status=EXIT_UNRULED)

        before = self.snapshot()
        proc = self.take_up(convoy=PLAIN_CONVOY)
        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
