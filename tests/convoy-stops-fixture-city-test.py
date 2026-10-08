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

No agent runs here: what an author session leaves (a Planning Exception, a
closed repair) is written the way its tools write it."""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVANCE = ROOT / "bin" / "convoy-advance"
STATE = ROOT / "bin" / "convoy-state"
INTEGRATION_TOOL = ROOT / "bin" / "spec-integration"
ESCALATION = ROOT / "bin" / "escalation-door"
FLOW_GC = ROOT / "tests" / "fixtures" / "convoy-state" / "gc"
GATE_REPORT = ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json"

RIG = "fixture_city"
RED = "branche d'intégration rouge"
# The regression command of the profile: red while the product holds this file.
RED_FILE = "rouge"
REGRESSION = f"sh -c 'test ! -e {RED_FILE}'"
SESSION_IDENTITY = ("GC_AGENT", "GC_ALIAS", "GC_SESSION_NAME", "GC_SESSION_ID", "BEADS_ACTOR", "GC_TEMPLATE")

EXIT_REFUSED = 1


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
            "DISPATCH_DOOR_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
            "DISPATCH_DOOR_MEMINFO_FILE": str(self.tmp / "no-meminfo"),
            "ESCALATION_DOOR_LOCK_FILE": str(self.tmp / "escalation-door.lock"),
            "PROPOSAL_DOOR_BIN": str(self.tmp / "proposal-door"),
            "GC_ESCALATION_RECIPIENT": "human",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
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
                    "start": {"formula": "fx-start", "role": None}}
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


if __name__ == "__main__":
    unittest.main()
