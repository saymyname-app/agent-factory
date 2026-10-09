#!/usr/bin/env python3
"""The stops of a convoy on the graph of the Fixture City (T21, af-cbp84n;
Spec af-wf4w5r §8, user story 53): the demonstration line of the ticket.

The graph is the one of tests/fixtures/ticket-graph-publish/
fixture-city-new-flow-draft.yaml, published by the real publication door
(bin/ticket-graph-publish) in a throwaway repository, which opens the
integration branch of its Spec. Only command lines are exercised:
bin/convoy-advance (one pass of the Factory's order), bin/spec-integration
merge, bin/convoy-state, bin/escalation-door. The `repair` of a red
integration branch is published by the real patch door, and the control
that is red is a real command of the project's profile, run on the real
branches. One tracker file serves the two fake trackers of the suites: the
publication door writes it through tests/fixtures/ticket-graph-publish/
bd-bead-mode, the commands of the flow read and write it through
tests/fixtures/convoy-state/gc.

The end of the Spec on the same graph (T23, af-s5uysn; Spec §9, points 1 to
3): once every ticket is closed, the pass runs the real bin/spec-end; red
tests count one round and their one `repair` is published by code, as is the
`repair` the operator asks for a « non fait » left without a final state.

The end code review on the same graph (T25, af-ji2ruy; Spec §6 « Fin de
Spec »): the three mechanical verdicts green, the pass has the assembled diff
reviewed; the `repair` its reviewer drafted for a cited Blocking Finding is
published by the real patch door and starts like any ticket, and the gate
refuses until a review made in full on the new tip is favorable
(tests/fixtures/spec-end-review/reviewer stands in for the reviewer session).
The Outcome Evaluation on the same graph (T24, af-oy7v3i; Spec §7, §9,
points 4 and 5): what the Evaluator of the end drafted -- the `repair` of a
user story it did not observe, the one of a finding « hors ticket » it
classified « repaired » -- is published by the pass through the real patch
door, once, and named where it was drafted.

The acceptance of the Outcome (T28, af-3x6zkb; Spec §11), on the convoy the
reference driver of the Fixture City Oracle walks to the end of its Spec
(tests/fixtures/fixture-city/delivery-driver: each pass is the real
bin/convoy-advance, the Evidence Pack is the generated one, the product is
really launched on loopback): the Acceptance Request sent once at the
Delivered Outcome, the delay that accepts nothing, the outage of a session,
which gets one `repair`, and the session of a « non conforme » request.

No agent runs here: what an author session leaves (a Planning Exception, a
closed repair, a Ticket Handoff) and what the Evaluator of the end hands in
are written the way their tools write them."""

import html
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVANCE = ROOT / "bin" / "convoy-advance"
STATE = ROOT / "bin" / "convoy-state"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
ESCALATION = ROOT / "bin" / "escalation-door"
SESSION = ROOT / "bin" / "acceptance-session"
OWNER = ROOT / "bin" / "owner-answer"
DRIVER = ROOT / "tests" / "fixtures" / "fixture-city" / "delivery-driver"
FLOW_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"

RIG = "fixture_city"
RED = "branche d'intégration rouge"
# The regression command of the profile: red while the product holds this file.
RED_FILE = "rouge"
REGRESSION = f"sh -c 'test ! -e {RED_FILE}'"
SESSION_IDENTITY = ("GC_AGENT", "GC_ALIAS", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE")

EXIT_REFUSED = 1
THIRTY_DAYS = 30 * 24 * 3600
# The clocks the tools of the flow read, each simulated by its own variable.
CLOCKS = ("ESCALATION_DOOR_NOW", "PROPOSAL_DOOR_NOW", "PR_AUTOPILOT_NOW_EPOCH")


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def answers(address):
    """Whether something serves HTTP at `address`."""
    try:
        with urllib.request.urlopen(address, timeout=5):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


publication = load("ticket-graph-publish-coverage-test.py")
PROJECT = publication.PROJECT


class ConvoyStopsOnTheFixtureCity(publication.Harness):
    def setUp(self):
        super().setUp()
        # The product holds what turns its regression command red, from its
        # protected branch on: the integration branch opens red.
        (self.repo_root / RED_FILE).write_text("le contrôle est rouge tant que ce fichier existe\n")
        self.git("add", RED_FILE)
        self.git("commit", "-q", "-m", "le produit, rouge")
        # A fifth ticket, so that a ticket is still ready once two authors
        # have left by a Planning Exception: T1, T4 and T5 wait for nothing.
        draft = self.conformant()
        draft["tickets"].append({
            "id": "T5", "kind": "vertical_slice", "title": "La sonde de santé nomme le jeu de données",
            "blocked_by": [], "target_rigs": [RIG],
            "what_it_delivers": "La sonde de santé du produit nomme le jeu de données servi.",
            "demonstration_line": "Sur le produit lancé, GET /health nomme le jeu de données servi.",
            "user_stories": [3],
            "acceptance_criteria": [{
                "entry_point": "GET /health sur le produit lancé avec le jeu de données « contenu »",
                "observable": "la réponse nomme le jeu de données « contenu »",
                "false_if": "la réponse ne nomme aucun jeu de données",
            }],
        })
        self.seed(draft)
        self.ids = self.published()["ids"]
        self.convoy = self.ids["_convoy"]
        self.tickets = {key: bead_id for key, bead_id in self.ids.items() if key != "_convoy"}
        # The edges the real tracker holds between the tickets (`blocks`).
        state = self.state()
        for bead_id in self.tickets.values():
            blockers = [key for key in str(state["beads"][bead_id]["metadata"].get("gc.blocked_by") or "").split(",") if key]
            state["beads"][bead_id]["blocks"] = [self.ids[key] for key in blockers]
        self.state_path.write_text(json.dumps(state))
        self.factory_root()
        self.write_log = self.tmp / "writes.log"
        self.write_log.write_text("")
        for name, body in (("provider-failover", "#!/bin/sh\nprintf '{}\\n'\n"), ("proposal-door", "#!/bin/sh\necho 0\n")):
            (self.tmp / name).write_text(body)
            (self.tmp / name).chmod(0o755)
        self.env = {
            **self.env,
            "GC_BIN": str(FLOW_GC),
            "CONVOY_STATE_FAKE_TRACKER": str(self.state_path),
            "CONVOY_STATE_FAKE_WRITE_LOG": str(self.write_log),
            "FACTORY_ROOT": str(self.repo_root),
            "TICKET_GRAPH_BD_WORKSPACE": str(self.tmp),
            "CONVOY_ADVANCE_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_LOCK_DIR": str(self.tmp / "locks"),
            "SPEC_INTEGRATION_WORK_DIR": str(self.tmp / "work"),
            "EVIDENCE_STORE_DIR": str(self.tmp / "store"),
            "EVIDENCE_PACK_DIR": str(self.tmp / "packs"),
            "DISPATCH_DOOR_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
            "DISPATCH_DOOR_MEMINFO_FILE": str(self.tmp / "no-meminfo"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            # The reviewer of the end is its stand-in: it finds nothing to block, unless a test plans otherwise.
            "SPEC_END_REVIEW_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "spec-end-review" / "reviewer"),
            "SPEC_END_REVIEW_FAKE_LOG": str(self.tmp / "end-review-door.log"),
            "SPEC_END_REVIEW_FAKE_PLAN": str(self.tmp / "end-review-plan.json"),
            "SPEC_END_REVIEW_FAKE_REPO": str(self.repo_root),
        }
        (self.tmp / "end-review-plan.json").write_text(json.dumps(["favorable"]))
        for name in SESSION_IDENTITY:
            self.env.pop(name, None)
        self.integration = self.shown()["convoy"]["integration"]["branch"]
        self.base = self.git("rev-parse", self.integration)

    # --- harness ------------------------------------------------------------

    def factory_root(self, ceiling=5, bounds=None):
        """The settings of the Factory, beside the product: the project of
        the Spec, the rig its tickets target, its profile, the flow."""
        config = self.repo_root / "config"
        (config / "projects").mkdir(parents=True, exist_ok=True)
        # The project of the Spec declares its human approver (the patch door
        # reads it); the rig its tickets target is what the dispatch door reads.
        project = ('repo = "example/fx"\nprotected_branch = "main"\nrequired_ci = "CI"\n'
                   'sling_target = "fx-worker"\nformulas = "fx-start"\n')
        (config / "projects" / f"{PROJECT}.toml").write_text(
            'human_approver = "benjamin"\nrig_dir = "rigs/' + PROJECT + '"\n' + project)
        (config / "projects" / f"{RIG}.toml").write_text('rig_dir = "."\n' + project)
        (config / "project-descriptors").mkdir(exist_ok=True)
        descriptor = json.loads((self.descriptors / f"{PROJECT}.json").read_text())
        descriptor["rigs"] = [RIG]
        descriptor["launch"]["regression_command"] = REGRESSION
        (config / "project-descriptors" / f"{PROJECT}.json").write_text(json.dumps(descriptor))
        shutil.copy(ROOT / "config" / "delivery-roles.json", config / "delivery-roles.json")
        settings = {"contract": "agent-factory-delivery-flow/v1", "max_sessions": ceiling,
                    "start": {"formula": "fx-start", "role": None},
                    "outcome_evaluation": {"formula": "mol-outcome-evaluation", "role": "evaluator", "rig": RIG,
                                           "timeout_seconds": 3600, "start_timeout_seconds": 15},
                    "end_review": {"formula": "mol-end-review", "role": "reviewer", "rig": RIG, "timeout_seconds": 3600}}
        if bounds is not None:
            settings["bounds"] = bounds
        (config / "delivery-flow.json").write_text(json.dumps(settings))

    def git(self, *args, check=True):
        proc = subprocess.run(
            ("git", "-C", str(self.repo_root), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", *args),
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
            text=True, capture_output=True)
        if check:
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def run_cmd(self, tool, *args):
        return subprocess.run((str(tool), *[str(a) for a in args]), env=self.env, text=True, capture_output=True)

    def run_ok(self, tool, *args):
        proc = self.run_cmd(tool, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def shown(self):
        proc = self.run_cmd(STATE, "show", self.convoy, "--repo", self.repo_root)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def shown_ticket(self, bead_id):
        return next(ticket for ticket in self.shown()["tickets"] if ticket["id"] == bead_id)

    def one_pass(self, expect=0):
        """One pass of the Factory's order on the convoy."""
        proc = self.run_cmd(ADVANCE, self.convoy)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return next(convoy for convoy in json.loads(proc.stdout)["convoys"] if convoy["id"] == self.convoy)

    def slung(self):
        lines = [json.loads(line) for line in self.write_log.read_text().splitlines() if line]
        return [entry[2] for entry in lines if entry[0] == "sling"]

    def tracked(self):
        return [ticket["id"] for ticket in self.shown()["tickets"]]

    def red_at_the_tip(self):
        """The false state of the ticket: tests red at the tip of the
        integration branch, as the merge command records them. The control
        it names is the regression command of the profile, red there for real."""
        self.assertNotEqual(0, subprocess.run(REGRESSION, shell=True, cwd=self.repo_root).returncode)
        control = f"commande de régression ({REGRESSION}) : code 1, sur {self.integration}"
        self.run_ok(STATE, "record-integration-red", self.convoy, "--commit", self.base, "--integration", self.base,
                    "--protected", self.base, "--control", control)
        return control

    def merge(self):
        profile = self.repo_root / "config" / "project-descriptors" / f"{PROJECT}.json"
        return self.run_cmd(INTEGRATION_TOOL, "merge", self.convoy, "--repo", self.repo_root, "--profile", profile)

    def planning_exception(self, bead_id):
        """The author of the ticket left by the Ticket Exit « Planning
        Exception » (bin/ticket-exit): the exception, the request, the parking."""
        request = {"quoi": f"Planning Exception (semantic) sur {bead_id} : la Spec dit X, le produit fait Y",
                   "pourquoi": "L'auteur ne tranche pas une question d'intention.",
                   "que_faire": [{"option": "Trancher dans le Planning Run", "consequence": "Le ticket reste parqué."},
                                 {"option": "Retirer le ticket du graphe", "consequence": "La couverture est recalculée."}],
                   "langue": "fr", "bloquant": True}
        self.run_ok(STATE, "set-session", self.convoy, bead_id, "--session", f"auteur-{bead_id}")
        self.run_ok(STATE, "raise-planning-exception", self.convoy, bead_id, "--kind", "semantic",
                    "--summary", "la Spec dit X, le produit fait Y")
        self.run_ok(ESCALATION, "benjamin", bead_id, json.dumps(request))
        self.run_ok(STATE, "park", self.convoy, bead_id, "--cause", "planning_exception", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", self.convoy, bead_id, "--exit", "planning_exception")

    # --- a red integration branch -------------------------------------------

    def test_a_red_integration_branch_stops_starts_and_merges_and_one_repair_appears_in_the_convoy(self):
        control = self.red_at_the_tip()
        before = {key: self.beads()[bead_id] for key, bead_id in self.tickets.items()}

        first = self.one_pass()

        # A repair is added to the convoy, by the patch door, and it names the red control.
        repair = first["repair"]
        self.assertEqual(("R1", True), (repair["key"], repair["published"]))
        self.assertEqual(sorted([*self.tickets.values(), repair["id"]]), sorted(self.tracked()))
        ticket = self.shown_ticket(repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        beads = self.beads()
        self.assertIn(f"red_check : {control}", beads[repair["id"]]["description"])
        self.assertEqual("R1", beads[repair["id"]]["metadata"]["gc.ticket_id"])
        self.assertNotIn("approved_by", beads[repair["draft"]]["metadata"])
        self.assertEqual(repair["id"], self.shown()["convoy"]["integration_red"]["repair"])
        self.assertFalse(self.shown()["unruled"])
        # T1, T4 and T5 are ready and places are free: none starts. Only the repair does.
        self.assertEqual([repair["id"]], first["started"])
        self.assertEqual([repair["id"]], self.slung())
        waiting = {entry["id"]: entry["reason"] for entry in first["waiting"]}
        for key in ("T1", "T4", "T5"):
            self.assertIn(RED, waiting[self.ids[key]], key)
            self.assertIn(control, waiting[self.ids[key]], key)
        for key, bead_id in self.tickets.items():
            self.assertEqual(before[key]["status"], beads[bead_id]["status"], key)
            self.assertNotIn("gc.flow.gate.dispatch", beads[bead_id]["metadata"], key)
        self.assertEqual(("integration_red", control, repair["id"]),
                         tuple(first["stop"][name] for name in ("reason", "control", "repair")))
        # The merge command refuses, and names the control too.
        proc = self.merge()
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn(RED, json.loads(proc.stdout)["error"])
        self.assertIn(control, json.loads(proc.stdout)["error"])
        self.assertEqual(self.base, self.git("rev-parse", self.integration))

    def test_one_repair_per_red_whatever_the_number_of_passes(self):
        self.red_at_the_tip()
        repair = self.one_pass()["repair"]["id"]
        tracked, drafts = sorted(self.tracked()), len(self.beads())
        self.write_log.write_text("")

        for _ in range(3):
            again = self.one_pass()
            self.assertNotIn("repair", again)
            self.assertEqual([], again["started"])

        self.assertEqual(tracked, sorted(self.tracked()))
        self.assertEqual(drafts, len(self.beads()))
        self.assertEqual([], self.slung())
        self.assertEqual(repair, self.shown()["convoy"]["integration_red"]["repair"])

    def test_the_repair_closed_and_the_branch_green_again_the_convoy_goes_on_by_itself(self):
        self.red_at_the_tip()
        repair = self.one_pass()["repair"]["id"]
        self.write_log.write_text("")
        # What the delivery of the repair leaves: the control green again where the
        # integration branch takes it up, and the repair closed by its gate.
        self.git("rm", "-q", RED_FILE)
        self.git("commit", "-q", "-m", "le contrôle rétabli")
        mended = self.git("rev-parse", "main")
        self.run_ok(STATE, "close-ticket", self.convoy, repair, "--commit", mended, "--file", GATE_REPORT)

        seen = self.one_pass()

        # The pass that sees the green: the merge command ran the control again, withdrew the red.
        self.assertEqual(mended, seen["integration"]["takeover"]["protected"])
        self.assertNotIn("red", seen["integration"])
        self.assertIsNone(self.shown()["convoy"]["integration_red"])
        self.assertNotIn(RED_FILE, self.git("ls-tree", "--name-only", self.integration).splitlines())
        # The next one starts the ready tickets, with no hand on the convoy.
        after = self.one_pass()
        self.assertNotIn("stop", after)
        self.assertEqual([self.ids[key] for key in ("T1", "T4", "T5")], after["started"])
        self.assertEqual(0, self.merge().returncode)

    # --- two open Planning Exceptions -----------------------------------------

    def two_at_work(self):
        """T1 and T4 started; T5, ready too, still waits for a place."""
        self.factory_root(ceiling=2)
        self.assertEqual([self.ids["T1"], self.ids["T4"]], self.one_pass()["started"])
        self.factory_root(ceiling=5)
        self.write_log.write_text("")

    def test_two_open_planning_exceptions_start_no_ready_ticket(self):
        self.two_at_work()
        self.planning_exception(self.ids["T1"])
        self.planning_exception(self.ids["T4"])
        before = self.beads()[self.ids["T5"]]

        stopped = self.one_pass()

        # T5 is ready and places are free: it does not start.
        self.assertEqual([], stopped["started"])
        self.assertEqual([], self.slung())
        self.assertEqual(before, self.beads()[self.ids["T5"]])
        self.assertEqual(("planning_exceptions", [self.ids["T1"], self.ids["T4"]], 2),
                         tuple(stopped["stop"][name] for name in ("reason", "open", "bound")))
        waiting = {entry["id"]: entry["reason"] for entry in stopped["waiting"]}
        self.assertIn("2 Planning Exceptions ouvertes", waiting[self.ids["T5"]])

    def test_one_open_planning_exception_lets_the_ready_ticket_start(self):
        self.two_at_work()
        self.planning_exception(self.ids["T1"])
        self.run_ok(STATE, "set-session", self.convoy, self.ids["T4"], "--session", "auteur-t4")
        state = self.state()
        state["sessions"] = [{"id": "s-t4", "name": "auteur-t4", "template": "fx-worker", "state": "active", "closed": False}]
        self.state_path.write_text(json.dumps(state))

        answer = self.one_pass()

        # T5 starts; T2 and T3, parked behind T1, do not.
        self.assertEqual([self.ids["T5"]], answer["started"])
        self.assertNotIn("stop", answer)
        waiting = {entry["id"]: entry["reason"] for entry in answer["waiting"]}
        for key in ("T2", "T3"):
            self.assertIn("parqué", waiting[self.ids[key]], key)

    def test_the_bound_of_the_open_planning_exceptions_is_read_in_the_settings_of_the_flow(self):
        self.two_at_work()
        self.planning_exception(self.ids["T1"])
        self.planning_exception(self.ids["T4"])
        self.factory_root(bounds={"resumes": 3, "open_planning_exceptions": 3})

        answer = self.one_pass()

        self.assertEqual([self.ids["T5"]], answer["started"])
        self.assertNotIn("stop", answer)

    def test_the_starts_resume_by_themselves_once_one_planning_exception_is_answered(self):
        self.two_at_work()
        self.planning_exception(self.ids["T1"])
        self.planning_exception(self.ids["T4"])
        self.assertEqual([], self.one_pass()["started"])
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the exception
        self.run_ok(ESCALATION, "repondre", self.ids["T4"], "a")

        answer = self.one_pass()

        self.assertEqual([self.ids["T5"]], answer["started"])
        self.assertNotIn("stop", answer)

    # --- the end of the Spec: what a pass does once every ticket is closed (T23, af-s5uysn) ---

    NOT_DONE = "L'export CSV de la liste n'est pas livré."

    def delivered(self, not_done=None, out_of_ticket=None):
        """Every ticket of the convoy closed by the ticket-end gate; with
        `not_done` or `out_of_ticket`, T4 left it in its Ticket Handoff. The
        product is still red from its protected branch on."""
        self.env["SPEC_END_LOCK_DIR"] = str(self.tmp / "locks")
        self.env["SPEC_END_WORK_DIR"] = str(self.tmp / "gate-work")
        self.env["OUTCOME_EVALUATION_STATE_DIR"] = str(self.tmp / "launches")
        if not_done or out_of_ticket:
            self.run_ok(STATE, "add-evidence", self.convoy, self.ids["T4"], "--piece", "handoff_records",
                        "--digest", "sha256:" + "ab" * 32, "--commit", self.base)
            handoff = self.tmp / "handoff.json"
            handoff.write_text(json.dumps({
                "sections": {"done": ["Critère 1 observé sur GET /health."], "deviations": "aucun",
                             "not_done": [not_done] if not_done else "aucun",
                             "out_of_ticket": [out_of_ticket] if out_of_ticket else "aucun"},
                "partial": False, "commit": self.base, "records": {"commits": [], "deferral_markers": []}}))
            self.run_ok(STATE, "set-handoff", self.convoy, self.ids["T4"], "--file", handoff)
        for bead_id in self.tickets.values():
            self.run_ok(STATE, "close-ticket", self.convoy, bead_id, "--commit", self.base, "--file", GATE_REPORT)
        self.write_log.write_text("")

    def end_rounds(self):
        return self.shown()["convoy"]["counters"]["end_rounds"]

    def answer(self, bead_id, option):
        self.env["ESCALATION_DOOR_NOW"] = "4102444800"  # the answer comes after the request
        self.run_ok(ESCALATION, "repondre", bead_id, option)

    def item(self):
        return self.shown_ticket(self.ids["T4"])["tracked_items"][0]

    def test_red_tests_at_the_end_of_the_spec_count_one_round_and_code_publishes_the_one_repair(self):
        self.delivered()

        first = self.one_pass()

        # The gate of the end of the Spec, run by the pass: the tests are red on the tip.
        ending = first["spec_end"]
        self.assertEqual({"registry": "pass", "tests": "fail", "fidelity": "not_run", "outcome_evaluation": "not_run", "findings": "not_run", "end_review": "not_run", "evidence_pack": "not_run"}, ending["verdicts"])
        self.assertEqual(1, ending["end_rounds"])
        control = self.shown()["convoy"]["integration_red"]["control"]
        self.assertIn(REGRESSION, control)
        self.assertIsNone(self.shown()["convoy"]["spec_end"])

        second = self.one_pass()

        # The next pass: the repair of that red, written by code, added by the patch door, started.
        repair = second["repair"]
        self.assertEqual(("R1", True), (repair["key"], repair["published"]))
        ticket = self.shown_ticket(repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        self.assertIn(f"red_check : {control}", self.beads()[repair["id"]]["description"])
        self.assertNotIn("approved_by", self.beads()[repair["draft"]]["metadata"])
        self.assertEqual(repair["id"], self.shown()["convoy"]["integration_red"]["repair"])
        self.assertEqual([repair["id"]], second["started"])
        # The gate does not advance while the branch is red, and the red is counted once.
        self.assertNotIn("spec_end", second)
        tracked = sorted(self.tracked())
        third = self.one_pass()
        self.assertNotIn("repair", third)
        self.assertNotIn("spec_end", third)
        self.assertEqual(tracked, sorted(self.tracked()))
        self.assertEqual(1, self.end_rounds())
        self.assertFalse(self.shown()["unruled"])

    def test_a_red_fidelity_at_the_end_of_the_spec_gets_its_repair_through_the_patch_door(self):
        self.delivered()
        # What bin/spec-end records when the fidelity of the tip is red.
        control = f"fidélité mécanique au Validated Prototype : écart(s) ouvert(s) sur {self.integration} à {self.base[:12]}"
        detail = "1 écart(s) ouvert(s) : empty/fixture-items/presence (missing)"
        self.run_ok(STATE, "record-integration-red", self.convoy, "--commit", self.base, "--integration", self.base,
                    "--protected", self.base, "--control", control, "--detail", detail, "--check", "fidelity", "--end-round")

        answer = self.one_pass()

        repair = answer["repair"]
        self.assertTrue(repair["published"])
        ticket = self.shown_ticket(repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        description = self.beads()[repair["id"]]["description"]
        # It cites the red control the convoy records (T40), and is an
        # interface ticket: the door posed the reference of the prototype.
        self.assertIn(f"red_check : {control}", description)
        self.assertIn(detail, description)
        self.assertIn("\n## Validated Prototype\n", description)
        self.assertEqual(repair["id"], self.shown()["convoy"]["integration_red"]["repair"])
        self.assertEqual([repair["id"]], answer["started"])
        self.assertEqual(1, self.end_rounds())
        self.assertFalse(self.shown()["unruled"])

    def test_a_not_done_without_final_state_is_asked_once_and_repaired_by_a_ticket_code_publishes(self):
        t4 = self.ids["T4"]
        self.delivered(not_done=self.NOT_DONE)

        first = self.one_pass()

        # The registry refuses and names the element: an outcome of the pass, asked of the operator.
        ending = first["spec_end"]
        self.assertEqual({"registry": "fail", "tests": "not_run", "fidelity": "not_run", "outcome_evaluation": "not_run", "findings": "not_run", "end_review": "not_run", "evidence_pack": "not_run"}, ending["verdicts"])
        self.assertIn(self.NOT_DONE, ending["reason"])
        self.assertEqual([(t4, ["not_done.1"])], [(entry["ticket"], entry["items"]) for entry in ending["requests"]])
        listed = [line for line in self.run_ok(ESCALATION, "list").stdout.splitlines() if line.strip().startswith(f"{t4} ")]
        self.assertEqual(1, len(listed), listed)
        self.assertIn(self.NOT_DONE, listed[0])
        self.assertNotIn("item_repairs", first)

        # Seen again: nothing more is asked, nothing is written.
        before = self.state_path.read_bytes()
        again = self.one_pass()
        self.assertEqual([], again["spec_end"]["requests"])
        self.assertEqual(before, self.state_path.read_bytes())

        # The operator asks for the repair: code publishes it, names it on the element, starts it.
        self.answer(t4, "a")
        asked = self.one_pass()
        self.assertEqual(1, len(asked["item_repairs"]), asked)
        repair = asked["item_repairs"][0]
        self.assertEqual((t4, ["not_done.1"], "R1", True),
                         tuple(repair[name] for name in ("ticket", "items", "key", "published")))
        ticket = self.shown_ticket(repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        description = self.beads()[repair["id"]]["description"]
        self.assertIn(self.NOT_DONE, description)
        self.assertIn("red_check : registre de la porte de fin de Spec", description)
        self.assertNotIn("approved_by", self.beads()[repair["draft"]]["metadata"])
        self.assertEqual(("ouvert", repair["id"]), (self.item()["state"], self.item()["repair"]))
        self.assertEqual([repair["id"]], asked["started"])
        # The gate waits for that repair, and a repair the operator asked for counts no round.
        self.assertNotIn("spec_end", asked)
        self.assertEqual(0, self.end_rounds())

        # One repair per request, whatever the number of passes.
        tracked = sorted(self.tracked())
        self.assertNotIn("item_repairs", self.one_pass())
        self.assertEqual(tracked, sorted(self.tracked()))

        # Closed by the ticket-end gate, the repair leaves the element « réparé »: the registry passes.
        self.run_ok(STATE, "close-ticket", self.convoy, repair["id"], "--commit", self.base, "--file", GATE_REPORT)
        self.assertEqual("réparé", self.item()["state"])
        self.assertEqual("pass", self.one_pass()["spec_end"]["verdicts"]["registry"])
        self.assertFalse(self.shown()["unruled"])

    def test_a_not_done_the_operator_accepts_passes_the_registry_and_no_repair_is_published(self):
        t4 = self.ids["T4"]
        self.delivered(not_done=self.NOT_DONE)
        self.assertEqual("fail", self.one_pass()["spec_end"]["verdicts"]["registry"])
        tracked = sorted(self.tracked())

        self.answer(t4, "b")
        answer = self.one_pass()

        self.assertEqual("accepté par Benjamin", self.item()["state"])
        self.assertNotIn("item_repairs", answer)
        self.assertEqual("pass", answer["spec_end"]["verdicts"]["registry"])
        self.assertEqual(tracked, sorted(self.tracked()))
        self.assertEqual("closed", self.shown_ticket(t4)["status"])

    # --- the Outcome Evaluation: what the Evaluator of the end drafted is published by code (T24, af-oy7v3i) ---

    FINDING = "La sonde de santé ne dit pas la version servie."
    EVALUATOR = "delivery-evaluator-fx"

    def drafted(self, what, restores):
        return {"title": f"Rétablir {what}", "what_it_delivers": f"Le produit assemblé sert {what}.",
                "restores": restores, "demonstration_line": f"Sur le produit lancé, {what} est servi.",
                "acceptance_criteria": [{"entry_point": "GET / sur le produit lancé", "observable": f"{what} y est servi",
                                         "false_if": f"{what} n'y est pas servi"}]}

    def json_file(self, name, content):
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False))
        return path

    def outcome(self):
        return self.shown()["convoy"]["outcome_evaluation"]

    def evaluation_open(self):
        """What bin/spec-end and bin/outcome-evaluation settle leave once the
        mechanical verdicts are green: their record, and the Outcome
        Evaluation open at their commit on a launched product, sent to an
        Evaluator session. A process that does nothing stands for the product."""
        product = subprocess.Popen(("sleep", "600"))
        self.addCleanup(product.wait)
        self.addCleanup(product.kill)
        (self.tmp / "launches").mkdir()
        (self.tmp / "launches" / "produit.json").write_text(json.dumps({"pid": product.pid}))
        names = ("registry", "tests", "fidelity")
        report = self.json_file("spec-end.json", {
            "version": "spec-end/v4",
            "conditions": [{"number": number, "name": name, "verdict": "pass", "detail": "vert"}
                           for number, name in enumerate(names, start=1)]})
        self.run_ok(STATE, "record-spec-end", self.convoy, "--commit", self.base, "--protected", self.base, "--file", report)
        request = self.json_file("outcome-request.json", {
            "roles": {"authors": [], "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:1",
                             "state_file": str(self.tmp / "launches" / "produit.json")}]})
        self.run_ok(STATE, "open-outcome-evaluation", self.convoy, "--commit", self.base, "--file", request)
        self.run_ok(STATE, "launch-outcome-evaluation", self.convoy, "--bead", self.convoy)
        return self.outcome()["request"]["stories"]

    def evaluated(self, stories, not_observed):
        """The Evaluator of the end hands in its states: every story observed
        with its piece, but `not_observed`, for which it drafts a repair."""
        self.run_ok(STATE, "add-evidence", self.convoy, self.convoy, "--piece", "outcome.produit",
                    "--digest", "sha256:" + "cd" * 32, "--commit", self.base)
        states = [{"number": story["number"], "text": story["text"], "evidence": "outcome.produit",
                   **({"state": "not_observed", "reason": "le produit lancé ne la sert pas"}
                      if story["number"] == not_observed else {"state": "observed"})} for story in stories]
        handed = self.json_file("outcome.json", {
            "commit": self.base, "stories": states, "exploration": "aucun", "fidelity_deviations": "aucun",
            "repairs": [{"story": not_observed, **self.drafted(
                f"la user story {not_observed}", {"kind": "user_story", "ref": f"user story {not_observed}"})}],
            "recorded_by": self.EVALUATOR})
        self.run_ok(STATE, "record-outcome-evaluation", self.convoy, "--file", handed)

    def test_what_the_evaluator_of_the_end_drafted_is_published_once_by_the_patch_door_and_named(self):
        t4 = self.ids["T4"]
        self.delivered(out_of_ticket=self.FINDING)
        stories = self.evaluation_open()
        story = stories[-1]["number"]
        draft = self.json_file("finding-repair.json", self.drafted(
            "la version servie par la sonde de santé", {"kind": "user_story", "ref": f"user story {story}"}))
        self.run_ok(STATE, "classify-finding", self.convoy, t4, "--item", "out_of_ticket.1", "--as", "repaired",
                    "--file", draft, "--recorded-by", self.EVALUATOR)

        # While the evaluation is open, a classification may still change: nothing is published.
        tracked = sorted(self.tracked())
        waiting = self.one_pass()
        self.assertEqual("pending", waiting["outcome_evaluation"]["action"])
        self.assertNotIn("outcome_repairs", waiting)
        self.assertEqual(tracked, sorted(self.tracked()))

        self.evaluated(stories, not_observed=story)
        answer = self.one_pass()

        # Its states are in: one repair per story not observed, one per finding « réparé », written by
        # the Evaluator, added by the patch door without approval, each named where it was drafted.
        published = answer["outcome_repairs"]
        self.assertEqual([{"story": story}, {"finding": f"{t4}:out_of_ticket.1"}],
                         [{name: entry[name] for name in ("story", "finding") if name in entry} for entry in published])
        self.assertEqual([("R1", True), ("R2", True)], [(entry["key"], entry["published"]) for entry in published])
        for entry in published:
            ticket = self.shown_ticket(entry["id"])
            self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
            self.assertIn(f"user_story : user story {story}", self.beads()[entry["id"]]["description"])
            self.assertNotIn("approved_by", self.beads()[entry["draft"]]["metadata"])
        self.assertIn(f"Rétablir la user story {story}", self.beads()[published[0]["id"]]["title"])
        self.assertEqual([{"story": story, "repair": published[0]["id"]}], self.outcome()["state"]["repairs"])
        finding = self.shown_ticket(t4)["findings"][0]
        self.assertEqual(("à réparer", published[1]["id"]), (finding["state"], finding["repair"]))
        self.assertEqual(sorted(entry["id"] for entry in published), sorted(answer["started"]))
        # The gate waits for those repairs.
        self.assertNotIn("spec_end", answer)

        # One repair per element, whatever the number of passes.
        tracked = sorted(self.tracked())
        self.assertNotIn("outcome_repairs", self.one_pass())
        self.assertEqual(tracked, sorted(self.tracked()))

        # Closed by the ticket-end gate, the repair leaves the finding « réparé ».
        self.run_ok(STATE, "close-ticket", self.convoy, published[1]["id"], "--commit", self.base, "--file", GATE_REPORT)
        self.assertEqual("réparé", self.shown_ticket(t4)["findings"][0]["state"])
        self.assertFalse(self.shown()["unruled"])


    # --- the end code review of the assembled diff (T25, af-ji2ruy) --------------------

    STORY_LINE = "As an exploitant, I want une sonde de santé, so that je sache que le produit répond."
    END_FINDING = {
        "axis": "spec", "blocking": True,
        "summary": "T4 et T5, corrects chacun, se contredisent : la sonde ne répond plus dès qu'elle nomme le jeu de données.",
        "citation": {"source": "spec", "quote": STORY_LINE},
        "repair": {
            "title": "La sonde de santé répond quel que soit le jeu de données servi",
            "what_it_delivers": "La sonde de santé du produit répond, qu'elle nomme ou non le jeu de données servi.",
            "restores": {"kind": "spec_line", "ref": STORY_LINE},
            "demonstration_line": "Sur le produit lancé, GET /health répond 200 avec chaque jeu de données.",
            "acceptance_criteria": [{
                "entry_point": "GET /health sur le produit lancé avec le jeu de données « vide »",
                "observable": "la réponse a le statut 200",
                "false_if": "la réponse a un autre statut",
            }],
        },
    }

    def verified(self, *plan):
        """Every ticket closed by the ticket-end gate and the three
        mechanical verdicts of the end green on the tip of the integration
        branch; `plan` is what the reviewer session does at each launch."""
        self.delivered()
        descriptor = self.repo_root / "config" / "project-descriptors" / f"{PROJECT}.json"
        profile = json.loads(descriptor.read_text())
        profile["launch"]["regression_command"] = "true"
        descriptor.write_text(json.dumps(profile))
        report = self.tmp / "spec-end.json"
        report.write_text(json.dumps({
            "version": "spec-end/v4",
            "conditions": [{"number": number, "name": name, "verdict": "pass", "detail": "réunie (relevé d'essai)"}
                           for number, name in enumerate(("registry", "tests", "fidelity"), start=1)]}))
        self.run_ok(STATE, "record-spec-end", self.convoy, "--commit", self.base, "--protected",
                    self.git("rev-parse", "main"), "--file", report)
        (self.tmp / "end-review-plan.json").write_text(json.dumps(list(plan), ensure_ascii=False))
        self.write_log.write_text("")

    def end_review(self):
        return self.shown()["convoy"]["end_review"]

    def test_a_cited_blocking_finding_of_the_end_review_gets_its_drafted_repair_through_the_patch_door(self):
        self.verified({"findings": [self.END_FINDING]}, "favorable")

        first = self.one_pass()

        # The pass that reads the three green verdicts launches the review on their commit.
        verdicts = first["spec_end"]["verdicts"]
        self.assertEqual(("pass", "pass", "pass", "fail"),
                         tuple(verdicts[name] for name in ("registry", "tests", "fidelity", "end_review")))
        self.assertEqual(("launched", self.base), (first["end_review"]["action"], first["end_review"]["commit"]))
        review = self.end_review()
        self.assertEqual({"commit": self.base, "outcome": "unfavorable", "unsettled": ["F1.1"]}, review["state"])
        self.assertEqual(self.STORY_LINE, review["rounds"][0]["findings"][0]["citation"]["quote"])
        self.assertEqual(1, self.end_rounds())

        second = self.one_pass()

        # The gate refuses on that finding, named; the repair its reviewer drafted is published by the patch door.
        self.assertIn("F1.1", second["spec_end"]["reason"])
        self.assertIn("sans verdict favorable", second["spec_end"]["reason"])
        repairs = second["end_review"]["repairs"]
        self.assertEqual([("F1.1", "R1", True)], [(entry["finding"], entry["key"], entry["published"]) for entry in repairs])
        repair = repairs[0]
        ticket = self.shown_ticket(repair["id"])
        self.assertEqual(("repair", publication.MARK, "open"), (ticket["kind"], ticket["mark"], ticket["status"]))
        self.assertEqual(self.END_FINDING["repair"]["demonstration_line"], ticket["demonstration_line"])
        description = self.beads()[repair["id"]]["description"]
        # The drafted repair cites the finding and the line of the Spec it restores.
        for mention in ("F1.1", self.base[:12], self.END_FINDING["summary"], f"spec_line : {self.STORY_LINE}"):
            self.assertIn(mention, description)
        # Inside the approved intent: no approval of the operator is asked for it.
        self.assertNotIn("approved_by", self.beads()[repair["draft"]]["metadata"])
        self.assertEqual(repair["id"], self.end_review()["rounds"][0]["findings"][0]["repair"])

        third = self.one_pass()

        # It follows the flow of an ordinary ticket: started by the next pass, through the dispatch door.
        self.assertEqual([repair["id"]], third["started"])
        self.assertIn(repair["id"], self.slung())
        # One repair per finding, whatever the number of passes; no end verification while it is open.
        tracked = sorted(self.tracked())
        fourth = self.one_pass()
        self.assertNotIn("spec_end", fourth)
        self.assertNotIn("end_review", fourth)
        self.assertEqual(tracked, sorted(self.tracked()))
        self.assertEqual(1, self.end_rounds())
        self.assertFalse(self.shown()["unruled"])

    def test_the_gate_refuses_after_the_repair_until_the_review_is_replayed_in_full_on_the_new_tip(self):
        self.verified({"findings": [self.END_FINDING]}, "favorable")
        self.one_pass()
        repair = self.one_pass()["end_review"]["repairs"][0]["id"]
        # What the flow of that ticket leaves once it is merged and closed by
        # its gate: one commit more on the integration branch.
        self.git("checkout", "-q", self.integration)
        (self.repo_root / "sonde.md").write_text("la sonde répond avec chaque jeu de données\n")
        self.git("add", "sonde.md")
        self.git("commit", "-q", "-m", "repair fusionné")
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", "main")
        self.run_ok(STATE, "close-ticket", self.convoy, repair, "--commit", tip, "--file", GATE_REPORT)
        # The mechanical verdicts, replayed on the new tip.
        self.run_ok(STATE, "record-spec-end", self.convoy, "--commit", tip, "--protected",
                    self.git("rev-parse", "main"), "--file", self.tmp / "spec-end.json")

        answer = self.one_pass()

        # The round of the earlier tip stands for nothing: the gate refuses,
        # and the same pass launches the review again, on the whole diff.
        self.assertEqual("fail", answer["spec_end"]["verdicts"]["end_review"])
        self.assertIn("jamais réutilisé", answer["spec_end"]["reason"])
        self.assertEqual(("launched", tip), (answer["end_review"]["action"], answer["end_review"]["commit"]))
        review = self.end_review()
        self.assertEqual([(self.base, "unfavorable"), (tip, "favorable")],
                         [(entry["commit"], entry["outcome"]) for entry in review["rounds"]])
        self.assertEqual(1, review["rounds"][1]["extent"]["files"])
        final = self.one_pass()
        self.assertEqual(("pass", "pass", "pass", "pass"), tuple(
            final["spec_end"]["verdicts"][name] for name in ("registry", "tests", "fidelity", "end_review")))
        self.assertEqual(1, self.end_rounds())

    # --- the repair rounds of the end are bounded, then a « non conforme » request (T26, af-vwcflt) ---

    def verdicts_at(self, commit):
        """What bin/spec-end leaves once its three mechanical verdicts are green at `commit`."""
        report = self.json_file("spec-end.json", {
            "version": "spec-end/v4",
            "conditions": [{"number": number, "name": name, "verdict": "pass", "detail": "réunie (relevé d'essai)"}
                           for number, name in enumerate(("registry", "tests", "fidelity"), start=1)]})
        self.run_ok(STATE, "record-spec-end", self.convoy, "--commit", commit, "--protected", self.git("rev-parse", "main"),
                    "--file", report)

    def evaluation_at(self, commit, not_observed=()):
        """What the end of the Spec leaves at `commit` once its mechanical
        verdicts are green there and the Evaluator of the end has handed in
        its states: every story observed with its piece, but those of
        `not_observed`, each with its drafted repair. A process that does
        nothing stands for the launched product."""
        self.verdicts_at(commit)
        product = subprocess.Popen(("sleep", "600"))
        self.addCleanup(product.wait)
        self.addCleanup(product.kill)
        (self.tmp / "launches").mkdir(exist_ok=True)
        launch = self.tmp / "launches" / f"produit-{commit[:12]}.json"
        launch.write_text(json.dumps({"pid": product.pid}))
        request = self.json_file("outcome-request.json", {
            "roles": {"authors": [], "evaluator": None, "same_provider": None, "other_declared": []},
            "environment": [{"dataset": None, "address": "http://127.0.0.1:1", "state_file": str(launch)}]})
        self.run_ok(STATE, "open-outcome-evaluation", self.convoy, "--commit", commit, "--file", request)
        self.run_ok(STATE, "launch-outcome-evaluation", self.convoy, "--bead", self.convoy)
        self.run_ok(STATE, "add-evidence", self.convoy, self.convoy, "--piece", "outcome.produit",
                    "--digest", "sha256:" + "cd" * 32, "--commit", commit)
        states = [{"number": story["number"], "text": story["text"], "evidence": "outcome.produit",
                   **({"state": "not_observed", "reason": "le produit lancé ne la sert pas"}
                      if story["number"] in not_observed else {"state": "observed"})}
                  for story in self.outcome()["request"]["stories"]]
        handed = self.json_file("outcome.json", {
            "commit": commit, "stories": states, "exploration": "aucun", "fidelity_deviations": "aucun",
            "repairs": [{"story": number, **self.drafted(
                f"la user story {number}", {"kind": "user_story", "ref": f"user story {number}"})} for number in not_observed],
            "recorded_by": self.EVALUATOR})
        self.run_ok(STATE, "record-outcome-evaluation", self.convoy, "--file", handed)

    def repair_delivered(self, repair):
        """What the flow of a repair leaves once it is merged and closed by
        its gate: one commit more on the integration branch. Returns that tip."""
        self.git("checkout", "-q", self.integration)
        (self.repo_root / f"{repair}.md").write_text(f"ce que le repair {repair} rétablit\n")
        self.git("add", f"{repair}.md")
        self.git("commit", "-q", "-m", f"repair {repair} fusionné")
        tip = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", "main")
        self.run_ok(STATE, "close-ticket", self.convoy, repair, "--commit", tip, "--file", GATE_REPORT)
        return tip

    def repairs(self):
        return [ticket["id"] for ticket in self.shown()["tickets"] if ticket["kind"] == "repair" and ticket["id"]
                not in self.tickets.values()]

    def requests(self):
        """The lines of the convoy on the operator's list, as bin/escalation-door prints it."""
        return [line.strip() for line in self.run_ok(ESCALATION, "list").stdout.splitlines()
                if line.strip().startswith(f"{self.convoy} ")]

    def stop(self):
        return self.shown()["convoy"]["end_stop"]

    def assert_non_conforme_request(self, answer, reason):
        """The pass raised the « non conforme » request of the convoy: one
        line on the operator's list, which carries the link of an Evidence
        Pack whose header says « non conforme »."""
        raised = answer["non_conforme"]
        self.assertEqual(("raised", reason), (raised["action"], raised["reason"]), raised)
        listed = self.requests()
        self.assertEqual(1, len(listed), listed)
        self.assertIn("« non conforme »", listed[0])
        self.assertIn(raised["page"], listed[0])
        page = Path(raised["page"])
        self.assertEqual("index.html", page.name)
        header = page.read_text(encoding="utf-8").split('<section id="rubrique-2">')[0]
        self.assertIn("Dossier non conforme", header)
        self.assertIn(self.git("rev-parse", self.integration), header)
        # Recorded on the convoy with the pack it carries; « accepté » is not one of its issues.
        stop = self.stop()
        pack = self.shown()["convoy"]["evidence_pack"]
        self.assertEqual((self.convoy, str(page), pack["digest"], False),
                         (stop["request"]["bead"], stop["request"]["page"], stop["request"]["digest"], pack["conforming"]))
        options = json.loads(self.beads()[self.convoy]["metadata"]["gc.escalation_que_faire"])
        self.assertEqual(3, len(options))
        self.assertNotIn("accept", " ".join(option["option"] for option in options).lower())
        return raised

    def test_two_rounds_consumed_and_a_condition_still_red_no_more_repair_and_a_non_conforme_request(self):
        self.delivered()
        story = 3
        # The false state: two rounds of the end consumed, and the Outcome Evaluation refuses the tip once more.
        self.run_ok(STATE, "set-counter", self.convoy, "--counter", "end_rounds", "--value", "2")
        self.evaluation_at(self.base, not_observed=[story])
        tracked = sorted(self.tracked())

        answer = self.one_pass()

        # The repair the Evaluator drafted is not published: no third round starts.
        self.assertNotIn("outcome_repairs", answer)
        self.assertEqual(([], tracked, []), (answer["started"], sorted(self.tracked()), self.slung()))
        self.assertEqual(2, self.end_rounds())
        self.assertEqual("fail", answer["spec_end"]["verdicts"]["outcome_evaluation"])
        stop = self.stop()
        self.assertEqual(("end_rounds_exhausted", self.base, "outcome_evaluation", 2),
                         tuple(stop[name] for name in ("reason", "commit", "source", "rounds")))
        self.assert_non_conforme_request(answer, "end_rounds_exhausted")
        self.assertIsNone(self.shown()["convoy"]["delivered"])
        self.assertFalse(self.shown()["unruled"])

        # Whatever the number of passes: one request, no repair, nothing written.
        before = self.state_path.read_bytes()
        for _ in range(2):
            again = self.one_pass()
            self.assertNotIn("non_conforme", again)
            self.assertNotIn("outcome_repairs", again)
            self.assertEqual([], again["started"])
        self.assertEqual(before, self.state_path.read_bytes())
        self.assertEqual(1, len(self.requests()))

    def one_round_for(self, not_observed):
        """One round of the end, for the stories the first Outcome Evaluation
        did not observe: counted, their repairs published by the pass,
        delivered. Returns the tip their merge leaves."""
        self.delivered()
        self.evaluation_at(self.base, not_observed=not_observed)
        self.assertEqual((1, None), (self.end_rounds(), self.stop()))
        published = self.one_pass()["outcome_repairs"]
        self.assertEqual(sorted(not_observed), sorted(entry["story"] for entry in published))
        for entry in published:
            tip = self.repair_delivered(entry["id"])
        self.write_log.write_text("")
        return tip

    def test_a_round_that_does_not_reduce_the_stories_not_observed_stops_before_the_second_round(self):
        tip = self.one_round_for([1])
        tracked = sorted(self.tracked())

        # Replayed on the new tip: another story is not observed, as many as before the round.
        self.evaluation_at(tip, not_observed=[2])
        answer = self.one_pass()

        stop = self.stop()
        self.assertEqual(("stories_not_reduced", tip, "outcome_evaluation", 1),
                         tuple(stop[name] for name in ("reason", "commit", "source", "rounds")))
        self.assertEqual(1, self.end_rounds())
        self.assertNotIn("outcome_repairs", answer)
        self.assertEqual(([], tracked, []), (answer["started"], sorted(self.tracked()), self.slung()))
        raised = self.assert_non_conforme_request(answer, "stories_not_reduced")
        self.assertIn(tip, Path(raised["page"]).read_text(encoding="utf-8"))
        self.assertNotIn("non_conforme", self.one_pass())
        self.assertEqual(tracked, sorted(self.tracked()))

    def test_the_same_story_refused_twice_stops_before_the_second_round(self):
        tip = self.one_round_for([1, 3])
        tracked = sorted(self.tracked())

        # Fewer stories are refused, but one of them for the second time.
        self.evaluation_at(tip, not_observed=[3])
        answer = self.one_pass()

        stop = self.stop()
        self.assertEqual(("story_refused_twice", tip, 1), tuple(stop[name] for name in ("reason", "commit", "rounds")))
        self.assertIn("user story 3", stop["detail"])
        self.assertEqual(1, self.end_rounds())
        self.assertNotIn("outcome_repairs", answer)
        self.assertEqual(([], tracked), (answer["started"], sorted(self.tracked())))
        self.assert_non_conforme_request(answer, "story_refused_twice")

    def test_a_round_that_reduces_the_stories_not_observed_leaves_the_second_round_start(self):
        tip = self.one_round_for([1, 3])

        # Fewer stories refused, none for the second time: the second round is counted and its repair published.
        self.evaluation_at(tip, not_observed=[2])
        answer = self.one_pass()

        self.assertEqual((2, None), (self.end_rounds(), self.stop()))
        self.assertEqual([2], [entry["story"] for entry in answer["outcome_repairs"]])
        self.assertNotIn("non_conforme", answer)
        self.assertEqual([], self.requests())

    def test_a_mechanical_red_and_a_finding_of_the_end_review_share_the_two_rounds_of_the_end(self):
        self.delivered()
        (self.tmp / "end-review-plan.json").write_text(json.dumps([{"findings": [self.END_FINDING]}] * 2, ensure_ascii=False))

        # Round 1: the tests are red on the tip, found by the gate of the pass.
        self.assertEqual("fail", self.one_pass()["spec_end"]["verdicts"]["tests"])
        self.assertEqual(1, self.end_rounds())
        first = self.one_pass()["repair"]["id"]
        self.git("rm", "-q", RED_FILE)
        self.git("commit", "-q", "-m", "le contrôle rétabli")
        self.run_ok(STATE, "close-ticket", self.convoy, first, "--commit", self.git("rev-parse", "main"), "--file", GATE_REPORT)
        self.assertNotIn("red", self.one_pass()["integration"])
        self.assertIsNone(self.shown()["convoy"]["integration_red"])

        # Round 2: on the new tip, mechanical verdicts and Outcome Evaluation green, the end review finds a Blocking Finding.
        tip = self.git("rev-parse", self.integration)
        self.evaluation_at(tip)
        launched = self.one_pass()["end_review"]
        self.assertEqual(("launched", tip), (launched["action"], launched["commit"]))
        self.assertEqual("unfavorable", self.end_review()["state"]["outcome"])
        counted = self.shown()["convoy"]
        self.assertEqual((2, tip, "end_review", None),
                         (counted["counters"]["end_rounds"], counted["end_round"]["commit"], counted["end_round"]["source"],
                          counted["end_stop"]))
        second = self.one_pass()["end_review"]["repairs"][0]["id"]
        self.assertEqual(sorted([first, second]), sorted(self.repairs()))

        # Replayed in full on the tip of that repair, the review refuses again: the rounds are consumed.
        last = self.repair_delivered(second)
        self.evaluation_at(last)
        tracked = sorted(self.tracked())
        self.write_log.write_text("")
        answer = self.one_pass()

        # One counter read in the tracker: the red and the review did not have two rounds each.
        self.assertEqual(2, self.end_rounds())
        stop = self.stop()
        self.assertEqual(("end_rounds_exhausted", last, "end_review", 2),
                         tuple(stop[name] for name in ("reason", "commit", "source", "rounds")))
        self.assertNotIn("repairs", answer["end_review"])
        self.assertEqual(([], tracked, []), (answer["started"], sorted(self.tracked()), self.slung()))
        self.assert_non_conforme_request(answer, "end_rounds_exhausted")
        again = self.one_pass()
        self.assertNotIn("repairs", again.get("end_review", {}))
        self.assertEqual(tracked, sorted(self.tracked()))


    def test_a_mechanical_red_once_the_rounds_are_consumed_gets_no_repair_and_the_request_is_raised_under_the_red(self):
        self.delivered()
        self.run_ok(STATE, "set-counter", self.convoy, "--counter", "end_rounds", "--value", "2")
        tracked = sorted(self.tracked())

        # The gate of the pass finds the tests red on the tip: a third round would start.
        answer = self.one_pass()

        self.assertEqual("fail", answer["spec_end"]["verdicts"]["tests"])
        shown = self.shown()["convoy"]
        self.assertEqual(("end_rounds_exhausted", self.base, "regression", 2),
                         tuple(shown["end_stop"][name] for name in ("reason", "commit", "source", "rounds")))
        # The red stands, and stops the convoy; it gets no repair, in this pass or a later one.
        self.assertEqual(self.base, shown["integration_red"]["commit"])
        self.assertNotIn("repair", shown["integration_red"])
        self.assert_non_conforme_request(answer, "end_rounds_exhausted")
        for _ in range(2):
            again = self.one_pass()
            self.assertNotIn("repair", again)
            self.assertNotIn("non_conforme", again)
            self.assertEqual(([], tracked, []), (again["started"], sorted(self.tracked()), self.slung()))
        self.assertEqual((2, 1), (self.end_rounds(), len(self.requests())))


class FixtureCityWalk(unittest.TestCase):
    """The convoy the reference driver walks to the end of its Spec: every
    pass is the real bin/convoy-advance, the Evidence Pack is the generated
    one and the product is really launched. The harness of the suites below."""

    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="acceptance-fixture-city-")).resolve()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        self.clock = {}

    # --- harness ------------------------------------------------------------

    def driver(self, command, *args):
        proc = subprocess.run((str(DRIVER), "--workspace", str(self.workspace), command, *args),
                              env={"PATH": os.environ["PATH"], **self.clock}, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def tool(self, tool, *args):
        return subprocess.run((str(tool), *[str(arg) for arg in args]), env={**self.env, **self.clock},
                              text=True, capture_output=True)

    def tool_ok(self, tool, *args):
        proc = self.tool(tool, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def shown(self):
        return json.loads(self.tool_ok(STATE, "show", self.convoy, "--repo", self.repo).stdout)

    def requests(self):
        return [line.strip() for line in self.tool_ok(ESCALATION, "list").stdout.splitlines()
                if line.strip().startswith(f"{self.convoy} ")]

    def tip(self, branch):
        return subprocess.run(("git", "-C", str(self.repo), "rev-parse", f"refs/heads/{branch}"), text=True,
                              capture_output=True, check=True).stdout.strip()

    def order_pass(self):
        """One more pass of the Factory's order on the convoy."""
        event = self.driver("advance")
        self.assertEqual("order-pass", event["event"])
        return event

    def walk_to_delivered(self, inject="none"):
        """The walk of the fixture, up to the pass that records the Delivered
        Outcome and not one event further. Returns the record."""
        return self.walk(inject, lambda convoy: convoy["delivered"])

    def walk(self, inject, reached, rounds_consumed=None):
        """The walk of the fixture, up to the pass after which `reached`
        answers something of the convoy, and not one event further; with
        `rounds_consumed`, the rounds of the end the convoy already counts."""
        prepared = self.driver("prepare", "--inject", inject)
        self.addCleanup(self.driver, "stop")
        self.repo, self.profile = Path(prepared["repo"]), Path(prepared["profile"])
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.workspace / "home"), **prepared["environment"],
                    "ESCALATION_DOOR_LOCK_FILE": str(self.workspace / "escalation-door.lock"),
                    "GC_ESCALATION_RECIPIENT": "human"}
        self.tracker = Path(self.env["CONVOY_STATE_FAKE_TRACKER"])
        self.write_log = self.workspace / "writes.log"
        self.convoy = self.driver("publish").get("convoy", prepared.get("convoy"))
        if rounds_consumed is not None:
            self.tool_ok(STATE, "set-counter", self.convoy, "--counter", "end_rounds", "--value", rounds_consumed)
        for _ in range(48):
            self.assertEqual([], self.requests())
            event = self.driver("advance")
            found = reached(self.shown()["convoy"])
            if found:
                self.assertEqual("order-pass", event["event"])
                return found
            self.assertFalse(event["idle"], "the walk settled before the end of the Spec")
        self.fail("the end of the Spec is not reached after 48 events")

    def assert_one_acceptance_request(self, delivered):
        """One line on the operator's list, with the link of the Evidence
        Pack of the Delivered Outcome; recorded on the convoy. Returns the line."""
        pack = json.loads(self.tool_ok(ROOT / "bin" / "evidence-pack", "check", self.convoy, "--repo", self.repo).stdout)
        self.assertEqual(("à jour", delivered["commit"], delivered["pack"]), (pack["state"], pack["commit"], pack["digest"]))
        listed = self.requests()
        self.assertEqual(1, len(listed), listed)
        self.assertIn("Acceptance Request", listed[0])
        self.assertTrue(listed[0].endswith(f" — dossier : {pack['page']}"), listed[0])
        self.assertTrue(Path(pack["page"]).is_file())
        acceptance = self.shown()["convoy"]["acceptance"]
        self.assertEqual((delivered["commit"], delivered["pack"], self.convoy, pack["page"]),
                         (acceptance["commit"], acceptance["pack"], acceptance["request"]["bead"], acceptance["request"]["page"]))
        self.assertNotIn("panne", acceptance)
        return listed[0]

    def written(self):
        return [json.loads(line) for line in self.write_log.read_text().splitlines() if line]


class AcceptanceOnTheFixtureCity(FixtureCityWalk):
    """T28 (af-3x6zkb; Spec §11) on the convoy the reference driver walks to
    the end of its Spec."""

    # --- the Acceptance Request ---------------------------------------------

    def test_the_pass_that_reaches_delivered_sends_one_acceptance_request_with_the_dossier_and_never_again(self):
        delivered = self.walk_to_delivered()

        request = self.assert_one_acceptance_request(delivered)
        mails = [entry for entry in self.written() if entry[0] == "mail"]
        self.assertEqual([["mail", "human", f"NEEDS BENJAMIN: {self.convoy}"]], mails)

        # Whatever the number of passes: nothing more is sent, nothing is written.
        before, log = self.tracker.read_bytes(), self.write_log.read_bytes()
        for _ in range(2):
            self.assertTrue(self.order_pass()["idle"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(log, self.write_log.read_bytes())
        self.assertEqual([request], self.requests())
        self.assertEqual(delivered, self.shown()["convoy"]["delivered"])

    def test_thirty_days_without_an_answer_the_outcome_is_still_delivered_nothing_merged_nothing_closed(self):
        delivered = self.walk_to_delivered()
        request = self.assert_one_acceptance_request(delivered)
        integration = self.shown()["convoy"]["integration"]["branch"]
        tips = (self.tip("main"), self.tip(integration))
        self.assertEqual(delivered["commit"], tips[1])
        self.assertNotEqual(*tips)
        before, log = self.tracker.read_bytes(), self.write_log.read_bytes()
        acceptance = self.shown()["convoy"]["acceptance"]

        # Every clock a tool of the flow reads is thirty days later; the request got no answer.
        later = str(int(time.time()) + THIRTY_DAYS)
        self.clock = {name: later for name in CLOCKS}
        self.assertIn("nothing due", self.tool_ok(ESCALATION, "sweep").stdout)
        for _ in range(3):
            self.order_pass()
        self.tool_ok(ESCALATION, "sweep")

        shown = self.shown()
        # Still Delivered, at the same commit, and not accepted: the request still waits, alone.
        self.assertEqual((delivered, acceptance), (shown["convoy"]["delivered"], shown["convoy"]["acceptance"]))
        self.assertEqual([request], self.requests())
        gate = json.loads(self.tool_ok(ROOT / "bin" / "spec-end", "check", self.convoy, "--repo", self.repo).stdout)
        self.assertEqual((True, delivered["commit"]), (gate["delivered"], gate["commit"]))
        # Nothing merged: the protected branch and the integration branch are where they were.
        self.assertEqual(tips, (self.tip("main"), self.tip(integration)))
        # Nothing closed, nothing cleared, nothing written at all.
        bead = json.loads(self.tracker.read_text())["beads"][self.convoy]
        self.assertNotEqual("closed", bead["status"])
        self.assertIn("Acceptance Request", bead["metadata"]["gc.needs_benjamin"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(log, self.write_log.read_bytes())
        self.assertFalse(shown["unruled"])

    # --- the outage of an Acceptance Session ----------------------------------

    def test_a_product_that_does_not_start_is_an_outage_and_the_next_pass_publishes_its_one_repair(self):
        delivered = self.walk_to_delivered(inject="story-not-observed")
        request = self.assert_one_acceptance_request(delivered)
        tracked = [ticket["id"] for ticket in self.shown()["tickets"]]
        broken = json.loads(self.profile.read_text())
        broken["launch"]["recipe"] = ["{python}", "-c", "import sys; sys.exit(3)"]
        profile = self.workspace / "broken-descriptor.json"
        profile.write_text(json.dumps(broken))

        proc = self.tool(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", profile)

        # An outage, not a judgment: said, no session, no address; noted on the convoy and nowhere else.
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        answer = json.loads(proc.stdout)
        self.assertEqual((False, True), (answer["ok"], answer["outage"]))
        self.assertIn("panne", answer["error"])
        self.assertNotIn("address", answer)
        self.assertNotEqual(0, self.tool(SESSION, "close", self.convoy).returncode)
        outage = self.shown()["convoy"]["acceptance"]["panne"]
        self.assertTrue(outage["detail"])
        self.assertNotIn("ticket", outage)
        self.assertEqual(tracked, [ticket["id"] for ticket in self.shown()["tickets"]])
        self.assertEqual([request], self.requests())

        self.order_pass()

        # One `repair` more in the convoy, published by code, and the outage names it.
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual(("repair", "open"), (repair["kind"], repair["status"]))
        self.assertEqual(repair["id"], shown["convoy"]["acceptance"]["panne"]["ticket"])
        self.assertEqual(outage, {key: value for key, value in shown["convoy"]["acceptance"]["panne"].items() if key != "ticket"})
        self.assertFalse(shown["unruled"])

        # Whatever the number of passes: no second repair. The session stays refused meanwhile.
        self.order_pass()
        after = self.shown()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in after["tickets"]])
        self.assertEqual(repair["id"], after["convoy"]["acceptance"]["panne"]["ticket"])
        before = self.tracker.read_bytes()
        refused = self.tool(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", self.profile)
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout + refused.stderr)
        self.assertFalse(json.loads(refused.stdout)["ok"])
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([request], self.requests())

    # --- the Acceptance Session of a « non conforme » request ------------------

    def test_the_session_of_a_non_conforme_request_launches_the_product_with_three_issues_and_never_accepted(self):
        # The false state of the stopped rounds: two rounds of the end consumed, and the Outcome
        # Evaluation refuses the tip once more (the second user story is not served).
        stop = self.walk("story-not-observed", lambda convoy: (convoy["end_stop"] or {}).get("request") and convoy["end_stop"],
                         rounds_consumed=2)
        self.assertEqual("end_rounds_exhausted", stop["reason"])
        [request] = self.requests()
        self.assertIn("« non conforme »", request)
        self.assertTrue(request.endswith(f" — dossier : {stop['request']['page']}"), request)
        self.assertIsNone(self.shown()["convoy"]["delivered"])
        integration = self.shown()["convoy"]["integration"]["branch"]

        opened = json.loads(self.tool_ok(SESSION, "open", self.convoy, "--repo", self.repo, "--profile", self.profile).stdout)

        # Same door, same session: the product at the commit of the dossier, the three issues, no « accepté ».
        self.assertEqual(("non_conforme", self.tip(integration), stop["request"]["page"]),
                         (opened["kind"], opened["commit"], opened["page"]))
        self.assertEqual(["relancer", "planification", "abandon"], [issue["response"] for issue in opened["issues"]])
        self.assertNotIn("accept", json.dumps(opened["issues"], ensure_ascii=False).lower())
        addresses = [product["address"] for product in opened["products"]]
        self.assertIn(opened["address"], addresses)
        for address in addresses:
            self.assertTrue(answers(address), address)

        # « accepté » is not an answer to a « non conforme » request: refused, nothing written.
        before = self.tracker.read_bytes()
        for word in ("accepte", "accepté"):
            proc = self.tool(SESSION, "record", self.convoy, "--repo", self.repo, "--response", word)
            self.assertNotEqual(0, proc.returncode, proc.stdout)
            self.assertNotIn('"ok": true', proc.stdout)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual([request], self.requests())
        self.assertIsNone(self.shown()["convoy"]["delivered"])

        closed = json.loads(self.tool_ok(SESSION, "close", self.convoy).stdout)
        self.assertTrue(closed["closed"])
        self.assertEqual([True] * len(addresses), [product["free"] for product in closed["stopped"]])
        for address in addresses:
            self.assertFalse(answers(address), address)
        self.assertEqual(before, self.tracker.read_bytes())


class OwnerAnswerOnTheFixtureCity(FixtureCityWalk):
    """T29 (af-mcd7pw; Spec §11) on the convoy the reference driver walks to
    the end of its Spec: Benjamin's answer is recorded by the real
    bin/owner-answer, and the repair of the finding he returns is published,
    delivered and judged again by the real passes of the order."""

    APPROVER = "benjamin"
    FINDING = "La liste des éléments ne se relit pas en JSON à l'adresse /items."
    LATER = "Un export CSV de la liste serait utile."
    REPAIR = {
        "title": "Servir la liste des éléments en JSON",
        "what_it_delivers": "Le produit sert la liste des éléments du jeu de données en JSON à l'adresse /items.",
        "demonstration_line": "Sur le produit lancé avec le jeu de données « content », GET /items rend les trois éléments.",
        "acceptance_criteria": [{
            "entry_point": "GET /items sur le produit lancé avec le jeu de données « content »",
            "observable": "le champ items contient « alpha », « beta », « gamma »",
            "false_if": "un élément manque, ou /items ne répond pas"}]}

    def owner(self, command, *args):
        return self.tool(OWNER, command, self.convoy, "--repo", self.repo, "--approved-by", self.APPROVER, *args)

    def owner_ok(self, command, *args):
        proc = self.owner(command, *args)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def pack(self):
        """The Evidence Pack of the convoy as bin/evidence-pack holds it, and its page."""
        pack = json.loads(self.tool_ok(ROOT / "bin" / "evidence-pack", "check", self.convoy, "--repo", self.repo).stdout)
        return pack, Path(pack["page"]).read_text(encoding="utf-8")

    def last_pass(self):
        """What the last pass of the order answered about the convoy."""
        answer = json.loads((self.workspace / "order-pass.json").read_text(encoding="utf-8"))
        return next(result for result in answer["convoys"] if result["id"] == self.convoy)

    def test_accepted_waits_for_the_verdicts_a_returned_finding_is_repaired_and_judged_again_then_accepted(self):
        first = self.walk_to_delivered(inject="proposition")
        self.assert_one_acceptance_request(first)
        first_pack, first_page = self.pack()
        self.assertNotIn("Depuis ton dernier jugement", first_page)
        self.assertNotIn('<section id="rubrique-0">', first_page)
        shown = self.shown()
        integration = shown["convoy"]["integration"]["branch"]
        tracked = [ticket["id"] for ticket in shown["tickets"]]
        # The dossier carries one « proposition »: what the author found « hors ticket ».
        [proposition] = [finding for ticket in shown["tickets"] for finding in ticket.get("findings") or []
                         if finding["classification"] == "proposal"]
        main = self.tip("main")

        # « accepté » while the proposition has no verdict: refused, nothing written.
        before = self.tracker.read_bytes()
        refused = self.owner("record", "--response", "accepté", "--words", "C'est bon pour moi.",
                             "--commit", first["commit"], "--pack-digest", first["pack"])
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout + refused.stderr)
        error = json.loads(refused.stdout)["error"]
        self.assertTrue(error.startswith("refus : "), error)
        self.assertIn("verdict", error)
        self.assertIn(proposition["id"], error)
        self.assertEqual(before, self.tracker.read_bytes())
        self.assertEqual(shown, self.shown())

        # His verdict on it, then one finding that cites the second user story of the Spec.
        self.owner_ok("verdict", "--proposition", proposition["id"], "--verdict", "sans suite", "--words", "Pas utile.")
        findings = self.workspace / "owner-findings.json"
        findings.write_text(json.dumps({"findings": [
            {"text": self.FINDING, "cites": {"kind": "user_story", "ref": "user story 2"}, "repair": self.REPAIR},
            {"text": self.LATER, "later": True}]}, ensure_ascii=False), encoding="utf-8")
        returned = self.owner_ok("record", "--response", "constats rendus", "--words", "Il manque le JSON.",
                                 "--commit", first["commit"], "--pack-digest", first["pack"], "--findings", findings)
        self.assertEqual(["repair", "later"], [finding["route"] for finding in returned["findings"]])
        # The proposition door of the fixture creates nothing: his answer is recorded all the same.
        self.assertEqual([2], [pending["finding"] for pending in returned["proposals_pending"]])

        # Nothing closed, nothing merged; the Outcome is no longer Delivered and its rounds start again.
        shown = self.shown()
        self.assertIsNone(shown["convoy"]["delivered"])
        self.assertEqual(0, shown["convoy"]["counters"]["end_rounds"])
        self.assertEqual("findings", shown["convoy"]["judgement"]["answers"][-1]["response"])
        self.assertNotEqual("closed", json.loads(self.tracker.read_text())["beads"][self.convoy]["status"])
        self.assertEqual(tracked, [ticket["id"] for ticket in shown["tickets"]])
        self.assertEqual((main, first["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertEqual([], self.requests())
        self.assertFalse(shown["unruled"])

        # The next pass publishes the one repair of the finding, by code, and says so; the door
        # answers again, and the same pass creates the proposition of his « plus tard ».
        (self.workspace / "proposal-door").write_text(
            '#!/bin/sh\n[ "$1" = create ] && echo "PROPOSITION CRÉÉE: fx-later — notée" || echo 0\n')
        self.order_pass()
        [published] = self.last_pass()["acceptance"]["owner_repairs"]
        self.assertEqual([{"finding": 2, "proposal": "fx-later"}], self.last_pass()["acceptance"]["owner_proposals"])
        self.assertEqual("fx-later", self.shown()["convoy"]["judgement"]["answers"][-1]["findings"][1]["proposal"])
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual((1, repair["id"], True), (published["finding"], published["id"], published["published"]))
        self.assertEqual(("repair", "open"), (repair["kind"], repair["status"]))
        self.assertEqual(repair["id"], shown["convoy"]["judgement"]["answers"][-1]["findings"][0]["ticket"])
        self.assertIsNone(shown["convoy"]["delivered"])

        # The whole flow passes again by itself: the repair through the ticket-end gate, then the
        # whole end of the Spec at the new tip.
        second = None
        for _ in range(48):
            event = self.driver("advance")
            second = self.shown()["convoy"]["delivered"]
            if second:
                break
            self.assertFalse(event["idle"], "the walk settled before the Outcome was Delivered again")
        self.assertTrue(second, "the Outcome is not Delivered again after 48 events")
        shown = self.shown()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in shown["tickets"]])
        self.assertEqual(["closed"] * len(shown["tickets"]), [ticket["status"] for ticket in shown["tickets"]])
        self.assertNotEqual(first["commit"], second["commit"])
        self.assertEqual(second["commit"], self.tip(integration))
        self.assertEqual(main, self.tip("main"))
        # What the repair delivered is in it: the product, on top of what Benjamin judged first.
        changed = subprocess.run(("git", "-C", str(self.repo), "diff", "--name-only", first["commit"], second["commit"]),
                                 text=True, capture_output=True, check=True).stdout.split()
        self.assertTrue([path for path in changed if path.endswith("/app.py")], changed)
        # A fresh Outcome Evaluation and a fresh end review, both at the new tip.
        rounds = shown["convoy"]["outcome_evaluation"]["rounds"]
        self.assertEqual([first["commit"], second["commit"]], [entry["commit"] for entry in rounds][-2:])
        self.assertEqual(second["commit"], shown["convoy"]["end_review"]["rounds"][-1]["commit"])
        self.assertEqual(0, shown["convoy"]["counters"]["end_rounds"])
        self.assertFalse(shown["unruled"])

        # A second dossier arrives, and it opens with what was done since his last judgement.
        self.assert_one_acceptance_request(second)
        second_pack, page = self.pack()
        self.assertNotEqual((first_pack["digest"], first_pack["page"]), (second_pack["digest"], second_pack["page"]))
        start, end = page.index('<section id="rubrique-0">'), page.index('<section id="rubrique-1">')
        self.assertLess(start, end)
        rubric = page[start:end]
        self.assertIn("Depuis ton dernier jugement", rubric)
        self.assertIn(html.escape(self.FINDING), rubric)
        self.assertIn(repair["id"], rubric)

        # « accepté », now: recorded with his words, the commit and the fingerprint. Nothing closes.
        words = "Accepté, le JSON est là."
        accepted = self.owner_ok("record", "--response", "accepté", "--words", words,
                                 "--commit", second["commit"], "--pack-digest", second["pack"])
        self.assertEqual("accepted", accepted["response"])
        shown = self.shown()
        last = shown["convoy"]["judgement"]["answers"][-1]
        self.assertEqual(("accepted", words, self.APPROVER, second["commit"], second["pack"]),
                         (last["response"], last["words"], last["approver"], last["commit"], last["pack"]))
        self.assertEqual(["findings", "accepted"], [entry["response"] for entry in shown["convoy"]["judgement"]["answers"]])
        self.assertEqual(second, shown["convoy"]["delivered"])
        self.assertNotEqual("closed", json.loads(self.tracker.read_text())["beads"][self.convoy]["status"])
        self.assertEqual((main, second["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertFalse(shown["unruled"])


class PromotionOnTheFixtureCity(OwnerAnswerOnTheFixtureCity):
    """T30 (af-vlzc6v; Spec §9 and §11) on the convoy the reference driver
    walks to its Delivered Outcome: Benjamin's answer is recorded by the real
    bin/owner-answer, and the next pass of the order follows it by itself --
    the one merge into the protected branch and the closing of the convoy,
    or the closing alone."""

    WORDS = "Accepté, c'est ce que je voulais."
    REASON = "Le besoin a disparu."
    test_accepted_waits_for_the_verdicts_a_returned_finding_is_repaired_and_judged_again_then_accepted = None

    def judged(self):
        """The Delivered Outcome, every proposition of its dossier judged.
        Returns its record, the integration branch and the protected tip."""
        delivered = self.walk_to_delivered(inject="proposition")
        shown = self.shown()
        for ticket in shown["tickets"]:
            for finding in ticket.get("findings") or []:
                if finding["classification"] == "proposal":
                    self.owner_ok("verdict", "--proposition", finding["id"], "--verdict", "sans suite", "--words", "Vu.")
        return delivered, shown["convoy"]["integration"]["branch"], self.tip("main")

    def accept(self, delivered):
        return self.owner_ok("record", "--response", "accepté", "--words", self.WORDS,
                             "--commit", delivered["commit"], "--pack-digest", delivered["pack"])

    def rev_list(self, *args):
        return subprocess.run(("git", "-C", str(self.repo), "rev-list", *args), text=True, capture_output=True,
                              check=True).stdout.split()

    def commit_to_main(self, path, text):
        """The protected branch receives a commit from elsewhere."""
        tree = self.workspace / "elsewhere"
        git = ("git", "-c", "user.name=Ailleurs", "-c", "user.email=ailleurs@example.invalid")
        subprocess.run((*git, "-C", str(self.repo), "worktree", "add", "-q", "--detach", str(tree), "main"), check=True)
        try:
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_text(text)
            subprocess.run((*git, "-C", str(tree), "add", "-A"), check=True)
            subprocess.run((*git, "-C", str(tree), "commit", "-q", "-m", "écrit ailleurs"), check=True)
            commit = subprocess.run(("git", "-C", str(tree), "rev-parse", "HEAD"), text=True, capture_output=True,
                                    check=True).stdout.strip()
            subprocess.run(("git", "-C", str(self.repo), "update-ref", "refs/heads/main", commit), check=True)
            return commit
        finally:
            subprocess.run(("git", "-C", str(self.repo), "worktree", "remove", "--force", str(tree)), check=True)

    def test_the_protected_branch_holds_nothing_of_the_convoy_before_accepted_then_one_merge_and_the_convoy_is_closed(self):
        delivered, integration, main = self.judged()
        # Delivered, and judged: the protected branch holds no commit of the convoy.
        convoy_commits = self.rev_list(f"main..{integration}")
        self.assertIn(delivered["commit"], convoy_commits)
        self.assertEqual([], self.rev_list("main", "--not", f"{integration}"))
        self.accept(delivered)
        self.assertEqual(main, self.tip("main"))
        self.assertEqual(("open", "delivered"), (self.shown()["convoy"]["status"], self.shown()["convoy"]["outcome"]))

        self.order_pass()

        promotion = self.last_pass()["promotion"]
        merged = self.tip("main")
        self.assertEqual((True, merged, delivered["commit"], True, "accepted"),
                         tuple(promotion[key] for key in ("promoted", "merged", "judged", "closed", "how")))
        self.assertEqual([merged], self.rev_list("--first-parent", f"{main}..main"))
        self.assertEqual([merged, main, delivered["commit"]], self.rev_list("--parents", "-n", "1", merged))
        self.assertEqual([], self.rev_list(f"main..{integration}"))
        shown = self.shown()
        self.assertEqual(("closed", "accepted", self.WORDS, self.APPROVER),
                         (shown["convoy"]["status"], shown["convoy"]["outcome"], shown["convoy"]["closed"]["said"],
                          shown["convoy"]["closed"]["approver"]))
        self.assertEqual((delivered["commit"], merged),
                         (shown["convoy"]["promotion"]["judged"], shown["convoy"]["promotion"]["merged"]))
        self.assertFalse(shown["unruled"])
        self.assertEqual([], self.requests())
        # The passes that follow leave it alone: closed by command, it is no longer walked.
        before = self.tracker.read_bytes()
        answer = json.loads(self.tool(ADVANCE, "--all", "--stopped-ok").stdout or "{}")
        self.assertNotIn(self.convoy, [result["id"] for result in answer.get("convoys", [])])
        self.assertEqual((before, merged), (self.tracker.read_bytes(), self.tip("main")))

    def test_an_abandoned_convoy_is_closed_with_the_reason_and_the_protected_branch_does_not_move(self):
        delivered, integration, main = self.judged()
        self.owner_ok("record", "--response", "abandonné", "--reason", self.REASON)

        self.order_pass()

        promotion = self.last_pass()["promotion"]
        self.assertEqual((False, None, True, "abandoned", self.REASON),
                         tuple(promotion[key] for key in ("promoted", "merged", "closed", "how", "said")))
        shown = self.shown()
        self.assertEqual(("closed", "abandoned", None),
                         (shown["convoy"]["status"], shown["convoy"]["outcome"], shown["convoy"]["promotion"]))
        self.assertEqual((main, delivered["commit"]), (self.tip("main"), self.tip(integration)))
        self.assertFalse(shown["unruled"])

    def test_a_protected_branch_in_conflict_after_accepted_merges_nothing_and_the_pass_publishes_one_repair(self):
        delivered, integration, _ = self.judged()
        self.accept(delivered)
        tracked = [ticket["id"] for ticket in self.shown()["tickets"]]
        [written] = [path for path in subprocess.run(
            ("git", "-C", str(self.repo), "diff", "--name-only", "--diff-filter=A", "main", integration),
            text=True, capture_output=True, check=True).stdout.split()][:1]
        moved = self.commit_to_main(written, "écrit ailleurs, autrement\n")

        self.driver("advance")

        promotion = self.last_pass()["promotion"]
        self.assertEqual((False, "conflict"), (promotion["promoted"], promotion["cause"]))
        self.assertIn("rien n'est fusionné", promotion["reason"])
        self.assertNotIn("error", promotion)
        self.assertEqual((moved, delivered["commit"]), (self.tip("main"), self.tip(integration)))
        shown = self.shown()
        [repair] = [ticket for ticket in shown["tickets"] if ticket["id"] not in tracked]
        self.assertEqual(("repair", "open", repair["id"]), (repair["kind"], repair["status"], promotion["repair"]["id"]))
        self.assertEqual(repair["id"], shown["convoy"]["integration_red"]["repair"])
        # Back before the end of the Spec: neither Delivered nor accepted, and not closed.
        last = shown["convoy"]["judgement"]["answers"][-1]
        self.assertEqual(("accepted", "conflict"), (last["response"], last["voided"]["cause"]))
        self.assertEqual((None, None, "open"),
                         (shown["convoy"]["delivered"], shown["convoy"]["acceptance"], shown["convoy"]["status"]))
        self.assertFalse(shown["unruled"])
        # One repair, whatever the number of passes.
        self.order_pass()
        self.assertEqual(tracked + [repair["id"]], [ticket["id"] for ticket in self.shown()["tickets"]])
        self.assertEqual(moved, self.tip("main"))


if __name__ == "__main__":
    unittest.main()
