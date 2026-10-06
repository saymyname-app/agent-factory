#!/usr/bin/env python3
"""bin/ticket-author on a fake tracker state (T12, af-i3q5a5; Spec af-wf4w5r
§0 rule 4, §4, §5; Testing Decisions seam 2): one test per pass and per
refusal, each refusal re-reading the tracker, the evidence store and the
repository to prove nothing was written. Only the command lines are
exercised. The product is a copy of the Delivery Fixture City, launched for
real by bin/project-launch; the red, the freeze and the green are proven by
the real bin/tdd-step, the pieces are filed by the real bin/evidence-capture
and the exits are taken by the real bin/ticket-exit."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "ticket-author"
CHECK = ROOT / "assets" / "scripts" / "checks" / "ticket-author-check.sh"
STATE_TOOL = ROOT / "bin" / "convoy-state"
TDD_TOOL = ROOT / "bin" / "tdd-step"
EXIT_TOOL = ROOT / "bin" / "ticket-exit"
CAPTURE_TOOL = ROOT / "bin" / "evidence-capture"
FIXTURE = Path("tests") / "fixtures" / "delivery-fixture-city"
DESCRIPTOR = ROOT / FIXTURE / "descriptor.json"
FAKE_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"

CONVOY, SPEC = "fx-convoy", "fx-spec"
T1, T2, P1 = "fx-t1", "fx-t2", "fx-p1"
OTHER_CONVOY, O1 = "fx-other", "fx-o1"
PLAIN_CONVOY, PLAIN_TICKET = "fx-plain", "fx-q1"
INTEGRATION = f"integration/{SPEC}"
SESSION = "delivery-author-fx-1"

EXIT_REFUSED = 1
EXIT_NOT_NEW_FLOW = 4

TESTS = f"{FIXTURE}/tests"
APP = f"{FIXTURE}/app.py"
README = "README.md"
TABLE = f"{TESTS}/criteria.json"
COUNT_FILE, HEALTH_FILE = f"{TESTS}/test_count.py", f"{TESTS}/test_health.py"
COUNT_ID = f"{COUNT_FILE}::CountTest.test_count_is_shown"
HEALTH_ID = f"{HEALTH_FILE}::HealthTest.test_dataset_is_named"

SESSION_IDENTITY = ("GC_AGENT", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE", "GC_BEAD_ID")

DESCRIPTION = """## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas
- [ ] Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent

## Target rigs

fx-rig"""

COUNT_TEST = """import os
import unittest
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        page = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/").read().decode()
        self.assertIn('<p data-anchor="fixture-count">3</p>', page)
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

HANDOFF = {
    "done": ["Critères 1 et 2 observés ; la ligne de démonstration se voit par GET / sur le jeu « content »."],
    "deviations": "aucun",
    "not_done": "aucun",
    "out_of_ticket": "aucun",
}

# Prints the page of the launched product and fails unless it shows the count.
DEMONSTRATION = ("sh", "-c", 'curl -sf "$PRODUCT_ADDRESS/" | grep -F \'data-anchor="fixture-count">3<\'')


class TicketAuthorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ticket-author-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tracker = self.tmp / "tracker.json"
        self.write_log = self.tmp / "writes.log"
        self.store = self.tmp / "store"
        self.repo = self.tmp / "product"
        self.worktrees = self.tmp / "worktrees"
        self.root = self.tmp / "root"
        (self.root / "config" / "projects").mkdir(parents=True)
        (self.root / "config" / "project-descriptors").mkdir()
        (self.root / "config" / "projects" / "fx-rig.toml").write_text(
            f'rig_dir = "{self.repo}"\nrepo = "example/fx"\nprotected_branch = "main"\nrequired_ci = "CI"\n'
            'sling_target = "fx-worker"\nformulas = "fx-start"\n')
        profile = json.loads(DESCRIPTOR.read_text())
        profile["rigs"] = ["fx-rig"]
        self.profile = self.root / "config" / "project-descriptors" / "fx.json"
        self.profile.write_text(json.dumps(profile))
        (self.tmp / "proposal-door").write_text("#!/bin/sh\necho 0\n")
        (self.tmp / "proposal-door").chmod(0o755)
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "FACTORY_ROOT": str(self.root),
            "CONVOY_STATE_FAKE_TRACKER": str(self.tracker),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "EVIDENCE_STORE_DIR": str(self.store),
            "TICKET_AUTHOR_WORKTREES_DIR": str(self.worktrees),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "essai", "GIT_AUTHOR_EMAIL": "essai@example.invalid",
            "GIT_COMMITTER_NAME": "essai", "GIT_COMMITTER_EMAIL": "essai@example.invalid",
        }
        # Never as this suite's own session: the session is what a test gives.
        for name in SESSION_IDENTITY:
            self.env.pop(name, None)
        self.seed_repo()
        self.seed_tracker()

    # --- harness ------------------------------------------------------------

    def seed_repo(self):
        """The product on `main`, and the integration branch of the Spec one
        commit ahead of it."""
        shutil.copytree(ROOT / FIXTURE, self.repo / FIXTURE)
        self.git("init", "-q", "-b", "main")
        self.main = self.commit("base")
        self.base_app = (self.repo / APP).read_text()
        self.git("checkout", "-q", "-b", INTEGRATION)
        self.integration = self.commit("un ticket déjà fusionné", {"MERGED.md": "un ticket déjà fusionné\n"})
        self.git("checkout", "-q", "main")

    def seed_tracker(self):
        def ticket(kind, scope=None):
            metadata = {"gc.ticket_kind": kind}
            if scope:
                metadata["gc.scope_paths"] = scope
            return {"title": "ticket d'essai", "status": "open", "issue_type": "task",
                    "description": DESCRIPTION, "metadata": metadata}

        beads = {
            CONVOY: {"title": "convoi d'essai", "status": "open", "issue_type": "convoy",
                     "metadata": {"gc.spec_id": SPEC}, "tracks": [T1, T2, P1]},
            # The Declared Scope of T1 leaves the README out.
            T1: ticket("vertical_slice", scope=f"{TESTS}/*,{APP}"),
            T2: ticket("vertical_slice"),
            P1: ticket("prefactoring"),
            OTHER_CONVOY: {"title": "convoi d'une autre Spec", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec-b"}, "tracks": [O1]},
            O1: ticket("vertical_slice"),
            PLAIN_CONVOY: {"title": "convoi d'avant", "status": "open", "issue_type": "convoy",
                           "metadata": {"gc.spec_id": "fx-spec2"}, "tracks": [PLAIN_TICKET]},
            PLAIN_TICKET: ticket("vertical_slice"),
        }
        self.tracker.write_text(json.dumps({"beads": beads, "sessions": []}))
        self.state("mark", CONVOY, "--demonstration-line", f"{T1}=La page d'accueil affiche 3",
                   "--demonstration-line", f"{T2}=La sonde nomme le jeu", "--user-stories", f"{T1}=1",
                   "--user-stories", f"{T2}=2")
        self.state("mark", OTHER_CONVOY, "--demonstration-line", f"{O1}=La page d'accueil affiche 3",
                   "--user-stories", f"{O1}=1")
        for convoy, tickets in ((CONVOY, (T1, T2, P1)), (OTHER_CONVOY, (O1,))):
            self.state("set-integration", convoy, "--branch", INTEGRATION, "--protected", "main", "--base", self.main)
            for ticket_id in tickets:
                self.state("record-gate", convoy, ticket_id, "--gate", "dispatch")
        self.write_log.write_text("")

    def git(self, *args, repo=None):
        return subprocess.run(
            ("git", "-C", str(repo or self.repo), *args), env=self.env, text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, message, files=None, repo=None):
        for path, content in (files or {}).items():
            target = (repo or self.repo) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("add", "-A", repo=repo)
        self.git("commit", "-q", "--allow-empty", "-m", message, repo=repo)
        return self.git("rev-parse", "HEAD", repo=repo)

    def run_cmd(self, tool, *args, session=None, env=None):
        full = {**self.env, **(env or {})}
        if session:
            full["GC_SESSION_NAME"] = session
        return subprocess.run((str(tool), *[str(a) for a in args]), env=full, text=True, capture_output=True, cwd=self.tmp)

    def state(self, *args):
        proc = self.run_cmd(STATE_TOOL, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown(self, ticket_id=T1, convoy=CONVOY):
        proc = self.run_cmd(STATE_TOOL, "show", convoy, "--repo", self.repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return next(t for t in json.loads(proc.stdout)["tickets"] if t["id"] == ticket_id)

    def edit(self, bead_id, status=None, drop=(), **metadata):
        state = json.loads(self.tracker.read_text())
        bead = state["beads"][bead_id]
        if status is not None:
            bead["status"] = status
        bead["metadata"].update(metadata)
        for key in drop:
            bead["metadata"].pop(key)
        self.tracker.write_text(json.dumps(state))

    def ok(self, *args, **kwargs):
        proc = self.run_cmd(TOOL, *args, **kwargs)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def store_files(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*") if p.is_file() and p.name != ".seal-key")

    def repo_state(self):
        return (self.git("for-each-ref", "--format=%(refname) %(objectname)"), self.git("worktree", "list", "--porcelain"))

    def refused(self, *args, mention=None, status=EXIT_REFUSED, **kwargs):
        """The call is refused, and the tracker, the evidence store, the
        branches and the work trees read again are what they were."""
        before = (self.tracker.read_bytes(), self.store_files(), self.repo_state(), self.write_log.read_text())
        proc = self.run_cmd(TOOL, *args, **kwargs)
        self.assertEqual(status, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertFalse(answer["ok"])
        self.assertNotIn("written", answer)
        self.assertEqual(before, (self.tracker.read_bytes(), self.store_files(), self.repo_state(),
                                  self.write_log.read_text()))
        text = answer.get("error") or answer.get("message")
        for part in ((mention,) if isinstance(mention, str) else mention or ()):
            self.assertIn(part, text)
        return text

    def gate(self, step, ticket=T1, convoy=CONVOY):
        return self.ok("gate", convoy, ticket, "--step", step)

    def gate_refused(self, step, mention=None, ticket=T1, convoy=CONVOY):
        return self.refused("gate", convoy, ticket, "--step", step, mention=mention)

    # --- the sequence of an author ---------------------------------------------

    def start(self, ticket=T1, session=SESSION, convoy=CONVOY):
        answer = self.ok("start", convoy, ticket, session=session)
        return answer, Path(answer["worktree"])

    def tdd(self, step, worktree, *args, ticket=T1):
        argv = [step, CONVOY, ticket, "--repo", worktree]
        if step != "freeze":
            argv += ["--profile", self.profile, "--dataset", "content"]
        proc = self.run_cmd(TDD_TOOL, *argv, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def red_step(self, worktree, base):
        table = json.dumps({"criteria": {"1": [COUNT_ID], "2": [HEALTH_ID]}})
        self.commit("tests de critère", {COUNT_FILE: COUNT_TEST, HEALTH_FILE: HEALTH_TEST, TABLE: table}, repo=worktree)
        self.tdd("red", worktree, "--base", base, "--table", TABLE)
        self.tdd("freeze", worktree)

    def code_step(self, worktree):
        """The code of the ticket, with a wiring file outside its Declared Scope."""
        app = self.base_app.replace(
            '"</body></html>"', 'f\'<p data-anchor="fixture-count">{len(items)}</p>\'\n            "</body></html>"',
        ).replace('{"status": "ok"}', '{"status": "ok", "dataset": self.dataset.get("state")}')
        head = self.commit("le nombre et le jeu", {APP: app, README: "Le produit affiche son nombre d'éléments.\n"},
                           repo=worktree)
        self.tdd("green", worktree)
        return head

    def demonstrate(self, worktree, *command, ticket=T1):
        return self.ok("demonstrate", CONVOY, ticket, "--repo", worktree, "--dataset", "content", "--",
                       *(command or DEMONSTRATION))

    def finish(self, worktree, ticket=T1):
        handoff = self.tmp / "handoff.json"
        handoff.write_text(json.dumps(HANDOFF, ensure_ascii=False))
        proc = self.run_cmd(EXIT_TOOL, "exit", CONVOY, ticket, "--exit", "finished", "--repo", worktree,
                            "--handoff", handoff)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    # --- start: a fresh session, a work tree, a branch from the integration branch

    def test_start_gives_the_ticket_its_work_tree_on_a_branch_left_from_the_integration_branch(self):
        answer, worktree = self.start()

        self.assertEqual(self.worktrees / T1, worktree)
        self.assertEqual(f"ticket/{T1}", self.git("symbolic-ref", "--short", "HEAD", repo=worktree))
        self.assertEqual(self.integration, self.git("rev-parse", "HEAD", repo=worktree))
        self.assertEqual((self.integration, INTEGRATION), (answer["base"], answer["integration_branch"]))
        self.assertEqual(str(self.profile), answer["profile"])
        ticket = self.shown()
        self.assertEqual((f"ticket/{T1}", SESSION, "in_progress"),
                         (ticket["branch"], ticket["session"]["name"], ticket["status"]))
        # Nothing was checked out in the repository of the project.
        self.assertEqual("main", self.git("symbolic-ref", "--short", "HEAD"))
        self.assertEqual("La page d'accueil affiche 3", answer["demonstration_line"])

    def test_start_is_refused_without_a_session(self):
        self.refused("start", CONVOY, T1, mention="session")

    def test_start_is_refused_to_a_session_that_already_took_another_ticket(self):
        self.start()
        self.refused("start", CONVOY, T2, session=SESSION, mention=("une session neuve par ticket", T1))
        self.refused("start", OTHER_CONVOY, O1, session=SESSION, mention=("une session neuve par ticket", T1))

    def test_start_is_refused_on_a_convoy_without_integration_branch(self):
        self.edit(CONVOY, drop=["gc.flow.integration"])
        self.refused("start", CONVOY, T1, session=SESSION, mention="branche d'intégration")

    def test_start_is_refused_on_a_ticket_the_dispatch_door_did_not_start(self):
        self.edit(T1, drop=["gc.flow.gate.dispatch"])
        self.refused("start", CONVOY, T1, session=SESSION, mention="porte de dispatch")

    def test_start_again_by_the_same_session_changes_nothing(self):
        first, _ = self.start()
        before = (self.tracker.read_bytes(), self.repo_state())

        again, _ = self.start()

        self.assertEqual(first["worktree"], again["worktree"])
        self.assertEqual(before, (self.tracker.read_bytes(), self.repo_state()))

    def test_a_convoy_without_the_mark_is_not_touched(self):
        for args in (("start", PLAIN_CONVOY, PLAIN_TICKET), ("gate", PLAIN_CONVOY, PLAIN_TICKET, "--step", "red"),
                     ("demonstrate", PLAIN_CONVOY, PLAIN_TICKET, "--repo", self.repo, "--dataset", "content", "--", "true"),
                     ("release", PLAIN_CONVOY, PLAIN_TICKET)):
            with self.subTest(command=args[0]):
                text = self.refused(*args, session=SESSION, status=EXIT_NOT_NEW_FLOW)
                self.assertIn("pas un convoi du nouveau flux", text)

    def test_locate_names_the_marked_convoy_of_a_ticket(self):
        self.assertEqual(OTHER_CONVOY, self.ok("locate", O1)["convoy"])
        proc = self.run_cmd(TOOL, "locate", PLAIN_TICKET)
        self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)

    # --- gates: each passage is a check by script -------------------------------

    def test_gate_workspace_refuses_before_start_and_passes_after(self):
        self.gate_refused("workspace", mention="session")
        self.start()
        self.assertTrue(self.gate("workspace")["passed"])

    def test_gate_workspace_refuses_a_branch_that_did_not_leave_from_the_integration_branch(self):
        self.start()
        # The same ticket branch, rebuilt from a commit the integration branch does not hold.
        worktree = self.worktrees / T1
        self.git("checkout", "-q", "--orphan", "ailleurs", repo=worktree)
        self.commit("une autre histoire", repo=worktree)
        self.git("branch", "-f", f"ticket/{T1}", "ailleurs", repo=worktree)
        self.git("checkout", "-q", f"ticket/{T1}", repo=worktree)
        self.gate_refused("workspace", mention="branche d'intégration")

    def test_gate_red_refuses_until_the_red_is_proven_and_frozen(self):
        answer, worktree = self.start()
        self.gate_refused("red", mention="étape rouge")
        # The tests are written and committed: the author's word is no proof.
        table = json.dumps({"criteria": {"1": [COUNT_ID], "2": [HEALTH_ID]}})
        self.commit("tests de critère", {COUNT_FILE: COUNT_TEST, HEALTH_FILE: HEALTH_TEST, TABLE: table}, repo=worktree)
        self.gate_refused("red", mention="étape rouge")
        self.tdd("red", worktree, "--base", answer["base"], "--table", TABLE)
        self.gate_refused("red", mention="gel")
        self.tdd("freeze", worktree)

        self.assertTrue(self.gate("red")["passed"])

    def test_gate_red_refuses_a_proof_written_by_hand_in_the_tracker(self):
        answer, worktree = self.start()
        head = self.commit("tests de critère", {COUNT_FILE: COUNT_TEST}, repo=worktree)
        for step, piece in (("red", "tdd_red"), ("freeze", "tdd_freeze")):
            self.state("add-evidence", CONVOY, T1, "--piece", piece, "--digest", "sha256:" + "ab" * 32, "--commit", head)
            self.state("set-tdd", CONVOY, T1, "--step", step, "--commit", head,
                       *(("--base", answer["base"]) if step == "red" else ()))
        self.gate_refused("red", mention="magasin de preuves")

    def test_gate_code_refuses_until_the_tests_are_green_at_the_tip(self):
        answer, worktree = self.start()
        self.red_step(worktree, answer["base"])
        self.gate_refused("code", mention="vert")
        self.code_step(worktree)
        self.assertTrue(self.gate("code")["passed"])
        head = self.commit("une retouche", {README: "Le produit affiche son nombre.\n"}, repo=worktree)
        self.gate_refused("code", mention=("pointe", head))

    def test_demonstrate_captures_the_line_on_the_product_launched_at_the_head_commit(self):
        answer, worktree = self.start()
        self.red_step(worktree, answer["base"])
        head = self.code_step(worktree)
        self.gate_refused("demonstration", mention="preuve de démonstration")

        proof = self.demonstrate(worktree)

        self.assertEqual(("demonstration", head), (proof["piece"], proof["commit"]))
        self.assertTrue(proof["address"].startswith("http://127.0.0.1:"))
        record = json.loads((self.store / SPEC / T1 / "demonstration.json").read_text())
        self.assertIn('data-anchor="fixture-count">3<', record["output"])
        self.assertEqual((head, proof["address"], 0), (record["commit"], record["address"], record["exit_code"]))
        self.assertEqual(head, self.shown()["evidence"]["demonstration"]["commit"])
        self.assertTrue(self.gate("demonstration")["passed"])
        # A commit after the capture: the proof is no longer at the head commit.
        self.commit("une retouche", {README: "Le produit affiche son nombre.\n"}, repo=worktree)
        self.gate_refused("demonstration", mention="pointe")

    def test_demonstrate_is_refused_when_the_observation_fails(self):
        answer, worktree = self.start()
        # The product of the start commit does not show the count yet.
        text = self.refused("demonstrate", CONVOY, T1, "--repo", worktree, "--dataset", "content", "--", *DEMONSTRATION)
        self.assertIn("démonstration", text)

    def test_demonstrate_is_refused_on_uncommitted_work_without_a_command_and_on_a_prefactoring(self):
        _, worktree = self.start()
        self.refused("demonstrate", CONVOY, T1, "--repo", worktree, "--dataset", "content", mention="--path")
        (worktree / APP).write_text(self.base_app + "\n# pas commité\n")
        self.refused("demonstrate", CONVOY, T1, "--repo", worktree, "--dataset", "content", "--", "true",
                     mention="diffèrent de HEAD")
        self.refused("demonstrate", CONVOY, P1, "--repo", self.repo, "--dataset", "content", "--", "true",
                     mention="prefactoring")

    def test_gate_demonstration_refuses_a_piece_not_captured_on_the_launched_product(self):
        answer, worktree = self.start()
        proc = self.run_cmd(CAPTURE_TOOL, "command", CONVOY, T1, "--piece", "demonstration", "--repo", worktree,
                            "--", "echo", "la page affiche 3")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.gate_refused("demonstration", mention="produit lancé")

    # --- the whole sequence, to the exit « terminé » -----------------------------

    def test_a_ticket_walked_through_its_gates_ends_finished_with_its_proofs(self):
        answer, worktree = self.start()
        self.assertTrue(self.gate("workspace")["passed"])
        self.red_step(worktree, answer["base"])
        self.assertTrue(self.gate("red")["passed"])
        head = self.code_step(worktree)
        self.assertTrue(self.gate("code")["passed"])
        self.demonstrate(worktree)
        self.assertTrue(self.gate("demonstration")["passed"])
        self.gate_refused("exit", mention="sortie")

        self.finish(worktree)

        self.assertTrue(self.gate("exit")["passed"])
        ticket = self.shown()
        self.assertEqual("finished", ticket["exit"]["exit"])
        records = ticket["handoff"]["records"]
        self.assertEqual((head, "tdd_red", "demonstration"),
                         (records["head"], records["red_proof"]["piece"], records["demonstration_proof"]["piece"]))
        self.assertEqual(answer["base"], records["base"])
        self.assertEqual({"tdd_red", "tdd_freeze", "tdd_green", "demonstration", "handoff_records"}, set(ticket["evidence"]))
        # The wiring outside the Declared Scope stopped nothing: it is a record.
        self.assertEqual([README], records["files_outside_declared_scope"])
        self.assertTrue(self.git("merge-base", "--is-ancestor", self.integration, head) == "")

    def test_gate_exit_refuses_a_finished_exit_left_behind_by_a_later_commit(self):
        answer, worktree = self.start()
        self.red_step(worktree, answer["base"])
        self.code_step(worktree)
        self.demonstrate(worktree)
        self.finish(worktree)
        self.commit("un commit après la sortie", {README: "Après la sortie.\n"}, repo=worktree)
        self.gate_refused("exit", mention="pointe")

    def test_an_exit_other_than_finished_closes_the_sequence_and_an_older_one_does_not(self):
        self.start()
        proc = self.run_cmd(EXIT_TOOL, "exit", CONVOY, T1, "--exit", "planning_exception", "--kind", "semantic",
                            "--summary", "La Spec fixe le libellé, la démonstration en demande un autre")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("planning_exception", self.shown()["park"]["cause"])

        for step in ("red", "code", "demonstration", "exit"):
            with self.subTest(step=step):
                answer = self.gate(step)
                self.assertTrue(answer["passed"])
                self.assertEqual("planning_exception", answer["sequence_closed_by"])
        # The branch of the ticket holds no commit: nothing of it can be merged.
        self.assertEqual(self.integration, self.git("rev-parse", f"ticket/{T1}"))

        # A session that takes the ticket later is not let through by the exit of the one before.
        session = json.loads(json.loads(self.tracker.read_text())["beads"][T1]["metadata"]["gc.flow.session"])
        self.edit(T1, **{"gc.flow.session": json.dumps({**session, "at": "2999-01-01T00:00:00Z"})})
        self.gate_refused("red", mention="étape rouge")

    def test_gates_of_a_prefactoring_ask_for_no_red_and_no_demonstration(self):
        self.start(ticket=P1)
        self.assertTrue(self.gate("red", ticket=P1)["passed"])
        self.assertTrue(self.gate("demonstration", ticket=P1)["passed"])
        self.gate_refused("code", ticket=P1, mention="régression")

    def test_gate_refuses_a_step_outside_the_closed_list_and_a_stopped_ticket(self):
        self.start()
        self.gate_refused("revue", mention="étape")
        self.state("stop-ticket", CONVOY, T1, "--reason", "criterion_already_green", "--detail", "critère 2 déjà vert")
        self.gate_refused("red", mention="arrêté")

    # --- the check Gas City runs between two steps of the formula ----------------

    def formula_step(self, step, ticket=T1):
        """The beads Gas City makes of a formula started on a ticket: the
        workflow root, its input convoy, and the bead of one step."""
        state = json.loads(self.tracker.read_text())
        state["beads"].update({
            "fx-input": {"title": f"input convoy for {ticket}", "status": "open", "issue_type": "convoy",
                         "metadata": {"gc.synthetic": "true"}, "tracks": [ticket]},
            "fx-root": {"title": "mol-ticket-author", "status": "in_progress", "issue_type": "task",
                        "metadata": {"gc.kind": "workflow", "gc.input_convoy_id": "fx-input"}},
            "fx-step": {"title": step, "status": "closed", "issue_type": "task",
                        "metadata": {"gc.step_id": step, "gc.root_bead_id": "fx-root", "gc.outcome": "pass"}},
        })
        self.tracker.write_text(json.dumps(state))
        return {"GC_BEAD_ID": "fx-step", "GC_CITY_PATH": str(ROOT)}

    def test_check_stops_a_step_the_agent_closed_without_its_proof(self):
        self.start()
        env = self.formula_step("red")
        before = self.tracker.read_bytes()

        proc = self.run_cmd(CHECK, env=env)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("refus", proc.stderr)
        self.assertIn("étape rouge", proc.stderr)
        self.assertEqual(before, self.tracker.read_bytes())

    def test_check_passes_a_step_whose_proof_is_in_the_tracker(self):
        self.start()
        proc = self.run_cmd(CHECK, env=self.formula_step("workspace"))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_check_refuses_a_bead_that_is_no_step_of_the_author_formula(self):
        self.start()
        env = self.formula_step("workspace")
        self.edit("fx-step", drop=["gc.step_id"])
        proc = self.run_cmd(CHECK, env=env)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        proc = self.run_cmd(CHECK, env={"GC_CITY_PATH": str(ROOT)})
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("GC_BEAD_ID", proc.stderr)

    # --- release ---------------------------------------------------------------

    def test_release_removes_the_work_tree_once_the_ticket_has_exited_and_keeps_the_branch(self):
        answer, worktree = self.start()
        self.refused("release", CONVOY, T1, mention="sortie")
        self.red_step(worktree, answer["base"])
        head = self.code_step(worktree)
        self.demonstrate(worktree)
        self.finish(worktree)
        (worktree / "brouillon.txt").write_text("pas commité\n")
        self.refused("release", CONVOY, T1, mention="brouillon.txt")
        (worktree / "brouillon.txt").unlink()

        self.ok("release", CONVOY, T1)

        self.assertFalse(worktree.exists())
        self.assertEqual(head, self.git("rev-parse", f"ticket/{T1}"))
        self.assertEqual({}, self.ok("release", CONVOY, T1).get("removed", {}))


if __name__ == "__main__":
    unittest.main()
