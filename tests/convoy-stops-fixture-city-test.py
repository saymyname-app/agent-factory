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

No agent runs here: what an author session leaves (a Planning Exception, a
closed repair, a Ticket Handoff) is written the way its tools write it."""

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

    # --- the end of the Spec: what a pass does once every ticket is closed (T23, af-s5uysn) ---

    NOT_DONE = "L'export CSV de la liste n'est pas livré."

    def delivered(self, not_done=None):
        """Every ticket of the convoy closed by the ticket-end gate; with
        `not_done`, T4 left it in its Ticket Handoff. The product is still
        red from its protected branch on."""
        self.env["SPEC_END_LOCK_DIR"] = str(self.tmp / "locks")
        self.env["SPEC_END_WORK_DIR"] = str(self.tmp / "gate-work")
        if not_done:
            self.run_ok(STATE, "add-evidence", self.convoy, self.ids["T4"], "--piece", "handoff_records",
                        "--digest", "sha256:" + "ab" * 32, "--commit", self.base)
            handoff = self.tmp / "handoff.json"
            handoff.write_text(json.dumps({
                "sections": {"done": ["Critère 1 observé sur GET /health."], "deviations": "aucun",
                             "not_done": [not_done], "out_of_ticket": "aucun"},
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
        self.assertEqual({"registry": "pass", "tests": "fail", "fidelity": "not_run", "end_review": "not_run"}, ending["verdicts"])
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
        self.assertIn(f"anchor : {detail}", description)
        self.assertIn("Validated Prototype", description)
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
        self.assertEqual({"registry": "fail", "tests": "not_run", "fidelity": "not_run", "end_review": "not_run"}, ending["verdicts"])
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


    # --- the end code review of the assembled diff (T25, af-ji2ruy) --------------------

    STORY_LINE = "As an exploitant, I want une sonde de santé, so that je sache que le produit répond."
    FINDING = {
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
            "version": "spec-end/v2",
            "conditions": [{"number": number, "name": name, "verdict": "pass", "detail": "réunie (relevé d'essai)"}
                           for number, name in enumerate(("registry", "tests", "fidelity"), start=1)]}))
        self.run_ok(STATE, "record-spec-end", self.convoy, "--commit", self.base, "--protected",
                    self.git("rev-parse", "main"), "--file", report)
        settings = self.repo_root / "config" / "delivery-flow.json"
        flow = json.loads(settings.read_text())
        flow["end_review"] = {"formula": "mol-end-review", "role": "reviewer", "rig": RIG, "timeout_seconds": 3600}
        settings.write_text(json.dumps(flow))
        (self.tmp / "end-review-plan.json").write_text(json.dumps(list(plan), ensure_ascii=False))
        self.env.update({
            "SPEC_END_REVIEW_DISPATCH_DOOR_BIN": str(ROOT / "tests" / "fixtures" / "spec-end-review" / "reviewer"),
            "SPEC_END_REVIEW_FAKE_LOG": str(self.tmp / "end-review-door.log"),
            "SPEC_END_REVIEW_FAKE_PLAN": str(self.tmp / "end-review-plan.json"),
            "SPEC_END_REVIEW_FAKE_REPO": str(self.repo_root),
        })
        self.write_log.write_text("")

    def end_review(self):
        return self.shown()["convoy"]["end_review"]

    def test_a_cited_blocking_finding_of_the_end_review_gets_its_drafted_repair_through_the_patch_door(self):
        self.verified({"findings": [self.FINDING]}, "favorable")

        first = self.one_pass()

        # The pass that reads the three green verdicts launches the review on their commit.
        self.assertEqual({"registry": "pass", "tests": "pass", "fidelity": "pass", "end_review": "fail"},
                         first["spec_end"]["verdicts"])
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
        self.assertEqual(self.FINDING["repair"]["demonstration_line"], ticket["demonstration_line"])
        description = self.beads()[repair["id"]]["description"]
        # The drafted repair cites the finding and the line of the Spec it restores.
        for mention in ("F1.1", self.base[:12], self.FINDING["summary"], f"spec_line : {self.STORY_LINE}"):
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
        self.verified({"findings": [self.FINDING]}, "favorable")
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
        self.assertEqual({"registry": "pass", "tests": "pass", "fidelity": "pass", "end_review": "pass"},
                         final["spec_end"]["verdicts"])
        self.assertEqual(1, self.end_rounds())


if __name__ == "__main__":
    unittest.main()
