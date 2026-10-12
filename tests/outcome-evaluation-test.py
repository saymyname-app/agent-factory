#!/usr/bin/env python3
"""bin/outcome-evaluation on a fake tracker state (T24, af-oy7v3i; Spec
af-wf4w5r §7, §9, Testing Decisions seam 2): one test per pass and per
refusal, each refusal re-reading the tracker, the evidence store and the
branches to prove nothing was written. Only command lines are exercised.

The convoy is the delivered one of tests/spec-end-test.py: a copy of the
Delivery Fixture City in a throwaway repository with its own remote, its
tickets closed by the real bin/ticket-end, the three mechanical verdicts
rendered by the real bin/spec-end. The assembled product is launched by the
real bin/project-launch from a clean copy of the commit of the gate, every
piece is captured and sealed by the real bin/evidence-capture on it, and a
stop is read back from the list of the real bin/escalation-door. No agent
runs: tests/fixtures/outcome-evaluation/evaluator stands in for the dispatch
door and the Evaluator session of the end, and uses the launched product for
real."""

import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "outcome-evaluation"
LAUNCH_TOOL = ROOT / "bin" / "project-launch"
FAKE_EVALUATOR = ROOT / "tests" / "fixtures" / "outcome-evaluation" / "evaluator"
FETCH = "import sys, urllib.request; sys.stdout.write(urllib.request.urlopen(sys.argv[1], timeout=10).read().decode())"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gate = load("spec-end-test.py")
CONVOY, SPEC, SLICE, SCREEN = gate.CONVOY, gate.SPEC, gate.SLICE, gate.SCREEN
PLAIN_CONVOY = gate.PLAIN_CONVOY
EXIT_REFUSED, EXIT_NOT_NEW_FLOW = 1, 4
NAMES = ("registry", "tests", "fidelity", "outcome_evaluation", "findings", "end_review")

SESSION = {"DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": "delivery-evaluator-fx"}
FINDING = "Le pied de page de la page d'accueil porte une année périmée."
OTHER_FINDING = "La sonde de santé ne dit pas la version servie."
FINDING_ID = f"{SLICE}:out_of_ticket.1"
# A story the assembled fixture does not serve, covered by the slice whose
# Ticket Evaluation observed every criterion; and one no ticket covers.
STORY_3 = "3. As an exploitant, I want une sonde de santé, so that je sache que le produit répond."
UNSERVED = "3. As an exploitant, I want une page de version, so that je sache quelle version est servie."
UNCOVERED = "4. As a visiteur, I want une page à propos, so that je sache qui publie la fixture."
UNSERVED_PLAN = {"stories": {"3": {"path": "/version"}, "4": {"path": "/a-propos"}}}


def repair(story=None, restores=None):
    what = f"la user story {story}" if story else "le pied de page"
    return {
        "title": f"Rétablir {what}",
        "what_it_delivers": f"Le produit assemblé sert {what}, que la Spec demande.",
        "restores": restores or {"kind": "user_story", "ref": f"user story {story}"},
        "demonstration_line": f"Sur le produit lancé, {what} est servi comme la Spec le demande.",
        "acceptance_criteria": [{"entry_point": "GET / sur le produit lancé", "observable": f"{what} y est servi",
                                 "false_if": f"{what} n'y est pas servi"}],
    }


class Harness(gate.Harness):
    """The verified convoy of the gate's suite, its assembled product evaluated: shared with
    tests/evidence-pack-test.py."""

    def setUp(self):
        super().setUp()
        self.outcome_profile = self.tmp / "outcome-descriptor.json"
        self.door_log = self.tmp / "outcome-door.log"
        self.plan = self.tmp / "outcome-plan.json"
        self.briefs = self.tmp / "outcome-briefs"
        self.launches_dir = self.tmp / "outcome-launches"
        self.env.update({
            "OUTCOME_EVALUATION_DISPATCH_DOOR_BIN": str(FAKE_EVALUATOR),
            "OUTCOME_EVALUATION_STATE_DIR": str(self.launches_dir),
            "TICKET_EVALUATION_STATE_DIR": str(self.tmp / "ticket-launches"),
            "EVALUATION_CAPACITY_STATE_DIR": str(self.tmp / "capacity"),
            "OUTCOME_EVALUATION_FAKE_LOG": str(self.door_log),
            "OUTCOME_EVALUATION_FAKE_PLAN": str(self.plan),
            "OUTCOME_EVALUATION_FAKE_BRIEFS": str(self.briefs),
            "DELIVERY_ROLE_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
        })
        self.env.pop("DELIVERY_ROLE_READ_ONLY", None)
        self.session = {**self.env, **SESSION}
        # No product a test launched outlives it.
        self.addCleanup(self.stop_every_product)
        self.evaluator({})

    def seed(self):
        """The seeded city of the gate's suite, plus what the Outcome
        Evaluation reads: the Spec of the convoy with its numbered user
        stories, the settings of the evaluation and the delivery roles."""
        base = super().seed()
        state = json.loads(self.tracker.read_text())
        state["beads"][SPEC] = {"title": "Spec de la fixture", "status": "open", "issue_type": "task",
                                "description": (ROOT / gate.FIXTURE / "spec.md").read_text(), "metadata": {}}
        # The slice covers stories 1 and 3, the interface ticket story 2.
        state["beads"][SLICE]["metadata"]["gc.flow.user_stories"] = json.dumps({"stories": ["1", "3"]})
        self.tracker.write_text(json.dumps(state))
        config = self.root / "config"
        self.settings(timeout_seconds=3600)
        shutil.copy(ROOT / "config" / "delivery-roles.json", config / "delivery-roles.json")
        (config / "model-catalog.json").write_text(json.dumps({"providers": {"p-codex": {"recommended": ["gpt-5.6-sol"]}}}))
        (config / "provider-policy.json").write_text(json.dumps({"providers": {
            "p-claude": {"pool": "anthropic"}, "p-claude-ro": {"pool": "anthropic"}, "p-codex": {"pool": "openai"}}}))
        (self.root / "city.toml").write_text(
            '[providers.p-claude]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-claude-ro]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-codex]\nargs_append = ["-m", "gpt-5.6-sol"]\n')
        # The Evaluator session is given no repository: the command finds the
        # project of the convoy from the rig its tickets name.
        (config / "projects").mkdir()
        (config / "projects" / "fx-rig.toml").write_text(f'rig_dir = "{self.repo}"\n')
        (config / "project-descriptors").mkdir()
        profile = json.loads((ROOT / gate.FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = ["fx-rig"]
        profile["launch"]["datasets"] = {"content": profile["launch"]["datasets"]["content"]}
        for screen in profile["launch"]["screens"]:
            screen["states"] = ["content"]
        (self.tmp / "outcome-descriptor.json").write_text(json.dumps(profile))
        (config / "project-descriptors" / "fx.json").write_text(json.dumps(profile))
        self.providers(evaluator=["p-codex"])
        return base

    # --- harness ------------------------------------------------------------

    def settings(self, **outcome):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "outcome_evaluation": {"formula": "mol-outcome-evaluation", "role": "evaluator", "rig": "agent-factory",
                                   "start_timeout_seconds": 15, **outcome}}))

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

    def evaluator(self, *steps):
        """What the stand-in of the Evaluator session does, call by call."""
        self.plan.write_text(json.dumps(list(steps), ensure_ascii=False))

    def stop_every_product(self):
        for record in self.launches_dir.rglob("*.json") if self.launches_dir.is_dir() else []:
            subprocess.run((str(LAUNCH_TOOL), "stop", "--state-file", str(record)), env=self.env, capture_output=True)

    def alive(self):
        """The launch records of the products that still run."""
        running = []
        for record in sorted(self.launches_dir.rglob("*.json")) if self.launches_dir.is_dir() else []:
            try:
                pid = json.loads(record.read_text())["pid"]
                subprocess.run(("kill", "-0", str(pid)), check=True, capture_output=True)
                running.append(str(record))
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
                continue
        return running

    def tool(self, command, *args, env=None, repo=True):
        proc = self.run_cmd(TOOL, command, CONVOY, *args, *(("--repo", self.repo) if repo else ()), env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def settle(self, expect=0):
        status, answer = self.tool("settle", "--profile", self.outcome_profile)
        self.assertEqual(expect, status, answer)
        return answer

    def outcome(self):
        status, answer = self.tool("show")
        self.assertEqual(0, status, answer)
        return answer

    def verdict(self):
        status, answer = self.tool("verdict")
        self.assertEqual(0, status, answer)
        return answer

    def calls(self):
        return [json.loads(line) for line in self.door_log.read_text().splitlines()] if self.door_log.exists() else []

    def unserved(self):
        """The Spec of the convoy asks for a page the assembled fixture does
        not serve (story 3, covered by the slice) and for one no ticket
        covers (story 4)."""
        state = json.loads(self.tracker.read_text())
        text = state["beads"][SPEC]["description"]
        self.assertIn(STORY_3, text)
        state["beads"][SPEC]["description"] = text.replace(STORY_3, f"{UNSERVED}\n{UNCOVERED}")
        self.tracker.write_text(json.dumps(state))

    def opened(self, findings=()):
        """The verified convoy, its Outcome Evaluation open on the launched
        product and no answer yet: what an Evaluator session of the end
        finds. Returns its brief."""
        self.verified()
        if findings:
            self.declare(SLICE, out_of_ticket=list(findings))
        self.evaluator("silent")
        self.assertEqual("launched", self.settle()["action"])
        status, brief = self.tool("brief", "--profile", self.outcome_profile, env=self.session)
        self.assertEqual(0, status, brief)
        return brief

    def observe(self, brief, piece, path="/", env=None):
        """One entry point of the launched product, captured by the real tool."""
        product = brief["environments"][0]
        proc = self.run_cmd(gate.CAPTURE_TOOL, "command", CONVOY, CONVOY, "--piece", piece, "--launch-state",
                            product["launch_state"], "--", sys.executable, "-c", FETCH, product["address"] + path,
                            env=env or self.session)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return piece

    def states(self, brief, **forced):
        """One « observed » state per story, each on a captured piece;
        `forced` gives another state to a story (`s3={...}`)."""
        stories = []
        for story in brief["stories"]:
            piece = self.observe(brief, f"outcome.s{story['number']}")
            stories.append({"number": story["number"], "text": story["text"], "state": "observed", "evidence": piece,
                            **forced.get(f"s{story['number']}", {})})
        return stories

    def result(self, brief, **fields):
        stories = self.states(brief)
        return {"commit": brief["commit"], "stories": stories,
                "coverage": [{"dataset": "content", "evidence": stories[0]["evidence"]}],
                "exploration": "aucun", "fidelity_deviations": "aucun", **fields}

    def record(self, result, env=None, expect=0):
        status, answer = self.tool("record", "--file", self.json_file("outcome-result.json", result),
                                   env=env or self.session)
        self.assertEqual(expect, status, answer)
        return answer

    def classify(self, finding, *args, env=None, expect=0):
        status, answer = self.tool("classify", finding, *args, env=env or self.session)
        self.assertEqual(expect, status, answer)
        return answer

    def assert_record_refused(self, result, *mentions, env=None):
        before = self.snapshot()
        answer = self.record(result, env=env, expect=EXIT_REFUSED)
        for mention in mentions:
            self.assertIn(mention, answer["error"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.outcome()["rounds"])
        return answer

    def conditions(self, answer):
        return [(entry["number"], entry["name"], entry["verdict"]) for entry in answer["conditions"]]

    def assert_green_before_the_pack(self):
        """The six conditions this suite and the end review's judge are met:
        the gate refuses on its last one alone, the Evidence Pack, which
        tests/evidence-pack-test.py judges."""
        status, answer = self.run_gate()
        self.assertEqual((EXIT_REFUSED, [len(NAMES) + 1]), (status, answer["missing"]), answer)

    def reviewed(self):
        """The end code review of the commit of the gate, favorable (T25):
        the gate then refuses on what this suite judges, and on nothing else."""
        self.end_reviewed(self.show()["convoy"]["spec_end"]["commit"])


class OutcomeEvaluationTest(Harness):
    # --- AC1: one state and one Evidence Record per numbered user story, at the commit of the gate ------

    def test_conforming_fixture_every_story_is_observed_with_proof_and_the_gate_passes(self):
        commit = self.verified()

        launched = self.settle()

        self.assertEqual(("launched", commit), (launched["action"], launched["commit"]))
        shown = self.outcome()
        self.assertEqual(1, len(shown["rounds"]))
        round_ = shown["rounds"][0]
        self.assertEqual((commit, "favorable", "favorable"), (round_["commit"], round_["outcome"], round_["verdict"]))
        # One state per numbered user story of the Spec, each « observée » with its own piece.
        self.assertEqual([(1, "observed"), (2, "observed"), (3, "observed")],
                         [(story["number"], story["state"]) for story in round_["stories"]])
        for story in round_["stories"]:
            proc = self.run_cmd(gate.CAPTURE_TOOL, "verify", CONVOY, CONVOY, "--piece", story["evidence"])
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            piece = json.loads(Path(json.loads(proc.stdout)["pieces"][0]["path"]).read_text())
            # Captured on the product code launched from the commit of the gate.
            self.assertEqual(commit, piece["commit"])
            self.assertIn(piece["address"], [entry["address"] for entry in round_["environment"]])
        self.assertEqual(([], [], []), (round_["repairs"], round_["contradictions"], shown["state"]["not_observed"]))
        verdict = self.verdict()
        self.assertTrue(verdict["favorable"], verdict)
        self.assertEqual((commit, commit, []), (verdict["commit"], verdict["gate_commit"], verdict["reasons"]))
        # The gate: six conditions green on that one commit, its end code review made there too. The
        # seventh, the Evidence Pack generated on that commit, is tests/evidence-pack-test.py's.
        self.reviewed()
        status, answer = self.run_gate()
        self.assertEqual((EXIT_REFUSED, [len(NAMES) + 1]), (status, answer["missing"]), answer)
        self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)],
                         self.conditions(answer)[:len(NAMES)])
        self.assertEqual(commit, answer["commit"])
        # The products are stopped by code once the states are in.
        self.assertEqual("none", self.settle()["action"])
        self.assertEqual([], self.alive())
        self.assertFalse(self.show()["unruled"])

    def test_two_datasets_are_opened_one_at_a_time_with_proof_from_each(self):
        commit = self.verified()
        profile = json.loads((ROOT / gate.FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = ["fx-rig"]
        self.outcome_profile.write_text(json.dumps(profile))
        (self.root / "config" / "project-descriptors" / "fx.json").write_text(json.dumps(profile))
        self.evaluator("silent")
        self.assertEqual("launched", self.settle()["action"])
        _, first_brief = self.tool("brief", "--profile", self.outcome_profile, env=self.session)
        self.assertEqual(["content"], [entry["dataset"] for entry in first_brief["environments"]])
        result = self.result(first_brief)
        first = first_brief["environments"][0]
        status, pending = self.tool("product", "--dataset", "empty", env=self.session)
        self.assertEqual(0, status)
        self.assertFalse(pending["ready"])
        self.assertEqual("product_ready", self.settle()["action"])
        self.assertFalse(Path(first["launch_state"]).exists())
        _, second_brief = self.tool("brief", "--profile", self.outcome_profile, env=self.session)
        self.assertEqual(["empty"], [entry["dataset"] for entry in second_brief["environments"]])
        self.assertEqual(1, len(self.alive()))
        second = second_brief["environments"][0]
        self.assertEqual(commit, json.loads(Path(second["launch_state"]).read_text())["commit"])
        result["coverage"].append({"dataset": "empty", "evidence": self.observe(second_brief, "outcome.empty")})
        self.record(result)
        self.assertTrue(self.verdict()["favorable"])

    def test_legacy_open_multi_game_request_requires_address_bound_coverage(self):
        self.verified()
        profile = json.loads((ROOT / gate.FIXTURE / "descriptor.json").read_text())
        profile["rigs"] = ["fx-rig"]
        self.outcome_profile.write_text(json.dumps(profile))
        (self.root / "config" / "project-descriptors" / "fx.json").write_text(json.dumps(profile))
        self.evaluator("silent")
        self.assertEqual("launched", self.settle()["action"])
        _, brief = self.tool("brief", "--profile", self.outcome_profile, env=self.session)
        result = self.result(brief)
        self.tool("product", "--dataset", "empty", env=self.session)
        self.assertEqual("product_ready", self.settle()["action"])
        tracker = json.loads(self.tracker.read_text())
        metadata = tracker["beads"][CONVOY]["metadata"]
        legacy = json.loads(metadata["gc.flow.outcome_evaluation"])
        self.assertEqual(2, len(legacy["request"]["environment"]))
        legacy["request"].pop("datasets")
        metadata["gc.flow.outcome_evaluation"] = json.dumps(legacy)
        self.tracker.write_text(json.dumps(tracker))

        result.pop("coverage")
        self.assert_record_refused(result, "couverture")
        result["coverage"] = [{"dataset": "content", "evidence": result["stories"][0]["evidence"]},
                              {"dataset": "empty", "evidence": result["stories"][0]["evidence"]}]
        self.assert_record_refused(result, "adresse")

    def test_the_evaluator_is_given_the_stories_of_the_spec_and_the_launched_products_and_nothing_of_the_authors(self):
        brief = self.opened(findings=[FINDING])

        self.assertEqual([1, 2, 3], [story["number"] for story in brief["stories"]])
        self.assertIn("sonde de santé", brief["stories"][2]["text"])
        self.assertEqual(self.show()["convoy"]["spec_end"]["commit"], brief["commit"])
        self.assertEqual(["content"], sorted(entry["dataset"] for entry in brief["environments"]))
        self.assertEqual([{"finding": FINDING_ID, "ticket": SLICE, "text": FINDING, "state": "non classé"}],
                         brief["findings"])
        # Neither a Ticket Handoff, nor a diff, nor a repository, nor a branch.
        said = json.dumps(brief, ensure_ascii=False)
        for hidden in (str(self.repo), gate.branch_of(SLICE), gate.INTEGRATION, "Critère 1 observé"):
            self.assertNotIn(hidden, said)
        # Never silent: no author's supplier is recorded on this convoy.
        self.assertIn("non établie", brief["independence"])

    def test_record_without_a_state_for_a_story_is_refused_and_nothing_is_written(self):
        brief = self.opened()
        result = self.result(brief)
        result["stories"] = result["stories"][:2]

        self.assert_record_refused(result, "user story 3 sans état", "sonde de santé")

    def test_record_with_a_story_without_proof_is_refused(self):
        brief = self.opened()
        result = self.result(brief)
        del result["stories"][1]["evidence"]

        self.assert_record_refused(result, "user story 2", "sans Evidence Record valide")

    def test_piece_written_by_hand_is_not_a_proof(self):
        brief = self.opened()
        result = self.result(brief)
        # The fingerprint is in the tracker, the file of the store was rewritten.
        path = self.store / SPEC / CONVOY / "outcome.s2.json"
        piece = json.loads(path.read_text())
        piece["output"] = "<html>tout va bien</html>"
        path.write_text(json.dumps(piece))

        answer = self.record(result, expect=EXIT_REFUSED)

        self.assertIn("sans Evidence Record valide", answer["error"])
        self.assertIn("outcome.s2", answer["error"])
        self.assertEqual([], self.outcome()["rounds"])

    def test_piece_captured_elsewhere_than_on_the_launched_assembled_product_is_refused(self):
        brief = self.opened()
        result = self.result(brief)
        # A piece of the convoy captured on the repository, at the commit of the gate, not on the launched product.
        self.git("fetch", "-q", "origin")
        tree = self.tmp / "ailleurs"
        self.git("worktree", "add", "-q", "--detach", str(tree), brief["commit"])
        proc = self.run_cmd(gate.CAPTURE_TOOL, "command", CONVOY, CONVOY, "--piece", "outcome.s1", "--repo", tree,
                            "--", "printf", "%s", "<html>", env=self.session)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        answer = self.record(result, expect=EXIT_REFUSED)

        self.assertIn("n'a pas été capturée sur le produit assemblé lancé pour cette évaluation", answer["error"])
        self.assertEqual([], self.outcome()["rounds"])

    def test_record_for_another_commit_than_the_one_of_the_gate_is_refused(self):
        brief = self.opened()

        self.assert_record_refused(self.result(brief, commit=self.base), "porte sur le commit", brief["commit"])

    def test_verdict_given_by_the_evaluator_is_refused(self):
        brief = self.opened()

        self.assert_record_refused(self.result(brief, verdict="favorable"), "le verdict est calculé par du code")

    def test_reworded_story_is_refused(self):
        brief = self.opened()
        result = self.result(brief)
        result["stories"][0]["text"] = "As a visiteur, I want voir quelque chose."

        self.assert_record_refused(result, "user story 1 reformulé")

    def test_record_outside_a_read_only_evaluator_session_is_refused(self):
        brief = self.opened()

        self.assert_record_refused(self.result(brief), "rôle Evaluator, en lecture seule", env=self.env)

    def test_record_while_no_evaluation_is_open_is_refused(self):
        self.verified()
        before = self.snapshot()

        status, answer = self.tool("record", "--file", self.json_file("r.json", {"commit": self.base}), env=self.session)

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertIn("aucune Outcome Evaluation n'est demandée", answer["error"])
        self.assertEqual(before, self.snapshot())

    def test_no_evaluation_is_opened_before_the_mechanical_verdicts_are_green(self):
        self.delivered()
        before = self.snapshot()

        answer = self.settle()

        self.assertEqual("waiting", answer["action"])
        self.assertIn("verdicts mécaniques", answer["reason"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(([], []), (self.calls(), self.alive()))

    def test_commit_added_after_the_evaluation_outdates_it_and_the_gate_replays_everything(self):
        commit = self.verified()
        self.settle()
        self.assertTrue(self.verdict()["favorable"])
        self.note(gate.INTEGRATION)

        # The gate renders its mechanical verdicts on the new tip; the evaluation of the old one does not count.
        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(1, "registry", "pass"), (2, "tests", "pass"), (3, "fidelity", "pass"),
                          (4, "outcome_evaluation", "fail"), (5, "findings", "not_run")], self.conditions(answer)[:5])
        self.assertNotEqual(commit, answer["commit"])
        self.assertIn("non au commit de la porte", answer["error"])
        # A new evaluation, in full, on the new tip.
        again = self.settle()
        self.assertEqual(("launched", answer["commit"]), (again["action"], again["commit"]))
        self.assertEqual([commit, answer["commit"]], [round_["commit"] for round_ in self.outcome()["rounds"]])
        self.reviewed()
        self.assert_green_before_the_pack()

    def test_evaluation_left_open_on_an_outdated_commit_is_withdrawn_with_its_products(self):
        brief = self.opened()
        self.assertEqual(1, len(self.alive()))
        result = self.result(brief)
        self.note(gate.INTEGRATION)

        answer = self.settle()

        self.assertEqual("waiting", answer["action"])
        self.assertEqual([], self.alive())
        self.assertIsNone(self.outcome()["request"])
        # What its session hands in later is refused.
        self.assertIn("aucune Outcome Evaluation n'est demandée", self.record(result, expect=EXIT_REFUSED)["error"])

    # --- AC2: the verdict, computed; a drafted repair per story « non observée » --------------------------

    def test_story_not_observed_is_recorded_with_its_proof_a_drafted_repair_and_the_contradiction(self):
        commit = self.verified()
        # After the stage: reaching a stage restores the tracker it left.
        self.unserved()
        self.evaluator(UNSERVED_PLAN)

        self.settle()

        shown = self.outcome()
        round_ = shown["rounds"][0]
        self.assertEqual(("repair", "unfavorable", commit), (round_["outcome"], round_["verdict"], round_["commit"]))
        states = {story["number"]: story for story in round_["stories"]}
        self.assertEqual(["observed", "observed", "not_observed", "not_observed"],
                         [states[number]["state"] for number in (1, 2, 3, 4)])
        # « non observé » with its proof: what the product answered instead.
        piece = json.loads((self.store / SPEC / CONVOY / f"{states[3]['evidence']}.json").read_text())
        self.assertIn("/version", " ".join(piece["command"]))
        self.assertIn("404", piece["output"])
        self.assertTrue(states[3]["reason"].strip())
        # A drafted repair appears, that cites the story; it is not published.
        self.assertEqual([3, 4], [entry["story"] for entry in shown["repairs"]])
        self.assertEqual({"kind": "user_story", "ref": "user story 3"}, shown["repairs"][0]["draft"]["restores"])
        self.assertNotIn("repair", shown["repairs"][0])
        self.assertEqual([SLICE, SCREEN], [ticket["id"] for ticket in self.show()["tickets"]])
        # Story 3 is covered by the slice, whose every criterion was « observé »: a contradiction, written by
        # code. Story 4 is covered by no ticket: no ticket's proof is contradicted.
        self.assertEqual([3], [entry["story"] for entry in shown["contradictions"]])
        contradiction = shown["contradictions"][0]
        self.assertEqual([SLICE], [ticket["id"] for ticket in contradiction["tickets"]])
        self.assertEqual(self.shown(SLICE)["evaluation"]["rounds"][-1]["commit"], contradiction["tickets"][0]["commit"])
        self.assertEqual(contradiction, self.show()["convoy"]["outcome_evaluation"]["state"]["contradictions"][0])
        # The verdict is unfavorable and the gate refuses, the story named.
        verdict = self.verdict()
        self.assertFalse(verdict["favorable"])
        status, answer = self.run_gate()
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual((4, "outcome_evaluation", "fail"), self.conditions(answer)[3])
        self.assertIn("user story 3", answer["error"])

    def test_one_story_not_observed_among_the_others_makes_the_verdict_unfavorable(self):
        brief = self.opened()
        piece = self.observe(brief, "outcome.absent", path="/version")
        result = self.result(brief, repairs=[{"story": 2, **repair(2)}])
        result["stories"][1].update(state="not_observed", evidence=piece, reason="La liste n'est pas servie.")

        answer = self.record(result)

        self.assertEqual(("repair", "unfavorable"), (answer["outcome"], answer["verdict"]))
        self.assertEqual([2], answer["state"]["not_observed"])
        self.assertFalse(self.verdict()["favorable"])

    def test_story_not_observed_without_a_drafted_repair_is_refused(self):
        brief = self.opened()
        piece = self.observe(brief, "outcome.absent", path="/version")
        result = self.result(brief)
        result["stories"][2].update(state="not_observed", evidence=piece, reason="Aucune sonde.")

        self.assert_record_refused(result, "user story 3 « not_observed » sans repair rédigé qui la cite")

    def test_drafted_repair_that_does_not_cite_its_story_is_refused(self):
        brief = self.opened()
        piece = self.observe(brief, "outcome.absent", path="/version")
        result = self.result(brief, repairs=[{"story": 3, **repair(3, {"kind": "user_story", "ref": "user story 1"})}])
        result["stories"][2].update(state="not_observed", evidence=piece, reason="Aucune sonde.")

        self.assert_record_refused(result, "le repair rédigé pour la user story 3 ne la cite pas")

    def test_drafted_repair_for_a_story_that_was_observed_is_refused(self):
        brief = self.opened()

        self.assert_record_refused(self.result(brief, repairs=[{"story": 1, **repair(1)}]), "repair rédigé pour 1")

    def test_state_outside_the_closed_list_is_refused(self):
        brief = self.opened()
        result = self.result(brief)
        result["stories"][0]["state"] = "partiel"

        self.assert_record_refused(result, "état hors de la liste fermée")

    # --- AC3: the classification of a finding « hors ticket » ------------------------------------------

    def test_finding_classified_repaired_without_the_citation_of_what_it_restores_is_refused(self):
        self.opened(findings=[FINDING])
        before = self.snapshot()
        draft = repair()
        del draft["restores"]

        without_file = self.classify(FINDING_ID, "--as", "repaired", expect=EXIT_REFUSED)
        without_citation = self.classify(FINDING_ID, "--as", "repaired", "--file", self.json_file("d.json", draft),
                                         expect=EXIT_REFUSED)

        for answer in (without_file, without_citation):
            self.assertIn("sans citation de ce qu'il rétablit", answer["error"])
        self.assertEqual(before[0], self.snapshot()[0])
        self.assertEqual("non classé", self.shown(SLICE)["findings"][0]["state"])

    def test_finding_classified_repaired_that_cites_a_story_the_spec_does_not_have_is_refused(self):
        self.opened(findings=[FINDING])
        before = self.snapshot()

        answer = self.classify(FINDING_ID, "--as", "repaired", "--file",
                               self.json_file("d.json", repair(restores={"kind": "user_story", "ref": "user story 9"})),
                               expect=EXIT_REFUSED)

        self.assertIn("cite une user story absente de la Spec", answer["error"])
        self.assertEqual(before[0], self.snapshot()[0])

    def test_finding_classified_repaired_with_its_citation_keeps_the_drafted_repair(self):
        self.opened(findings=[FINDING])
        cited = {"kind": "spec_line", "ref": "La page d'accueil porte les ancres du Validated Prototype."}

        answer = self.classify(FINDING_ID, "--as", "repaired", "--file", self.json_file("d.json", repair(restores=cited)))

        finding = answer["finding"]
        self.assertEqual(("à réparer", "repaired", cited),
                         (finding["state"], finding["classification"], finding["draft"]["restores"]))
        self.assertEqual("delivery-evaluator-fx", finding["recorded_by"])
        # Drafted, not published: no ticket was added to the convoy.
        self.assertNotIn("repair", finding)
        self.assertEqual([SLICE, SCREEN], [ticket["id"] for ticket in self.show()["tickets"]])

    def test_finding_dismissed_without_a_reason_is_refused(self):
        self.opened(findings=[FINDING])
        before = self.snapshot()

        answer = self.classify(FINDING_ID, "--as", "dismissed", expect=EXIT_REFUSED)

        self.assertIn("écarté sans raison", answer["error"])
        self.assertEqual(before[0], self.snapshot()[0])

    def test_finding_dismissed_with_its_reason_is_in_a_final_state(self):
        self.opened(findings=[FINDING])

        finding = self.classify(FINDING_ID, "--as", "dismissed", "--reason", "Le pied de page ne porte aucune année.")["finding"]

        self.assertEqual(("écarté", "Le pied de page ne porte aucune année."), (finding["state"], finding["reason"]))

    def test_finding_classified_as_a_proposal_is_kept_for_the_dossier(self):
        brief = self.opened(findings=[FINDING, OTHER_FINDING])
        self.classify(FINDING_ID, "--as", "proposal")
        self.classify(f"{SLICE}:out_of_ticket.2", "--as", "dismissed", "--reason", "Hors de la Spec.")
        self.record(self.result(brief))

        shown = self.outcome()

        # What the generator of the Evidence Pack reads: the proposal, with its text.
        self.assertEqual([(FINDING_ID, FINDING, "proposition pour Benjamin")],
                         [(p["id"], p["text"], p["state"]) for p in shown["proposals"]])
        self.assertEqual(["proposition pour Benjamin", "écarté"], [finding["state"] for finding in shown["findings"]])
        # Both are final: the gate passes.
        self.reviewed()
        self.assert_green_before_the_pack()

    def test_classification_outside_the_closed_list_or_of_an_unknown_finding_is_refused(self):
        self.opened(findings=[FINDING])
        before = self.snapshot()

        outside = self.classify(FINDING_ID, "--as", "plus tard", expect=EXIT_REFUSED)
        unknown = self.classify(f"{SLICE}:out_of_ticket.2", "--as", "proposal", expect=EXIT_REFUSED)
        tracked = self.classify(f"{SLICE}:not_done.1", "--as", "proposal", expect=EXIT_REFUSED)

        self.assertIn("classement du constat hors ticket", outside["error"])
        self.assertIn("ne porte pas le constat hors ticket", unknown["error"])
        self.assertIn("mal nommé", tracked["error"])
        self.assertEqual(before[0], self.snapshot()[0])

    def test_finding_is_classified_by_the_evaluator_of_the_end_during_its_evaluation_only(self):
        self.verified()
        self.declare(SLICE, out_of_ticket=[FINDING])
        before = self.snapshot()

        closed = self.classify(FINDING_ID, "--as", "proposal", expect=EXIT_REFUSED)
        self.assertIn("aucune Outcome Evaluation n'est ouverte", closed["error"])
        self.evaluator("silent")
        self.settle()
        outside = self.classify(FINDING_ID, "--as", "proposal", env=self.env, expect=EXIT_REFUSED)

        self.assertIn("rôle Evaluator, en lecture seule", outside["error"])
        self.assertEqual("non classé", self.shown(SLICE)["findings"][0]["state"])
        self.assertNotIn("gc.flow.findings", self.metadata(SLICE))
        self.assertEqual(before[1], self.snapshot()[1])

    # --- AC4: the gate with a finding left unclassified, or not in a final state ---------------------------

    def test_record_while_a_finding_is_left_unclassified_is_refused(self):
        brief = self.opened(findings=[FINDING])

        self.assert_record_refused(self.result(brief), "non classé", FINDING_ID)

    def test_gate_with_an_unclassified_finding_refuses_and_names_it(self):
        self.verified()
        self.settle()
        self.reviewed()
        self.assert_green_before_the_pack()
        # A finding the evaluation of this commit did not classify.
        self.declare(SLICE, out_of_ticket=[FINDING])
        before = self.snapshot()

        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertFalse(answer["ok"])
        self.assertEqual([(1, "registry", "pass"), (2, "tests", "pass"), (3, "fidelity", "pass"),
                          (4, "outcome_evaluation", "fail"), (5, "findings", "not_run")], self.conditions(answer)[:5])
        self.assertEqual([4], answer["missing"])
        for mention in ("condition 4", FINDING, SLICE, "non classé"):
            self.assertIn(mention, answer["error"])
        self.assertEqual(before, self.snapshot())
        # `check` says the same and writes nothing.
        status, checked = self.check()
        self.assertEqual((EXIT_REFUSED, (4, "outcome_evaluation", "fail")), (status, self.conditions(checked)[3]))
        self.assertIn(FINDING, checked["error"])
        self.assertEqual(before, self.snapshot())

    def test_gate_with_a_finding_to_repair_whose_repair_is_not_closed_refuses_at_the_final_states(self):
        brief = self.opened(findings=[FINDING])
        self.classify(FINDING_ID, "--as", "repaired", "--file", self.json_file("d.json", repair(restores={
            "kind": "repo_rule", "ref": "README.md : le pied de page porte l'année en cours."})))
        self.record(self.result(brief))
        self.reviewed()
        before = self.snapshot()

        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(4, "outcome_evaluation", "pass"), (5, "findings", "fail")], self.conditions(answer)[3:5])
        self.assertEqual([5], answer["missing"])
        for mention in ("condition 5", FINDING, "à réparer", "pas encore publié"):
            self.assertIn(mention, answer["error"])
        self.assertEqual(before, self.snapshot())

    # --- AC6: the free exploration and the fidelity deviations are recorded and change nothing to the verdict --

    def test_exploration_and_fidelity_deviations_are_recorded_and_do_not_change_the_verdict(self):
        brief = self.opened()
        piece = self.observe(brief, "outcome.exploration", path="/inconnu")
        exploration = [{"text": "Une adresse inconnue répond 404 en JSON, sans page d'erreur.", "evidence": piece},
                       {"text": "La page d'accueil n'a pas de titre de niveau 2."}]
        deviations = [{"text": "Le titre de l'état « content » est plus serré que sur le prototype."}]

        answer = self.record(self.result(brief, exploration=exploration, fidelity_deviations=deviations))

        self.assertEqual(("favorable", "favorable"), (answer["outcome"], answer["verdict"]))
        shown = self.outcome()
        self.assertEqual((exploration, deviations), (shown["exploration"], shown["fidelity_deviations"]))
        self.assertTrue(self.verdict()["favorable"])
        self.reviewed()
        self.assert_green_before_the_pack()

    def test_record_without_the_exploration_or_the_fidelity_deviations_is_refused(self):
        brief = self.opened()
        result = self.result(brief)
        del result["exploration"], result["fidelity_deviations"]

        self.assert_record_refused(result, "rubrique exploration absente", "rubrique fidelity_deviations absente")

    # --- the roles, an evaluation without result, a convoy without the mark -------------------------------

    def test_evaluator_on_the_supplier_of_an_author_is_said_and_deferred_when_another_one_is_available(self):
        self.verified()
        self.state("set-model", CONVOY, SLICE, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", "claude-opus-5-5")
        self.providers(evaluator=["p-claude-ro", "p-codex"])
        before = self.snapshot()

        deferred = self.settle()

        self.assertEqual("deferred", deferred["action"])
        self.assertIn("openai", deferred["reason"])
        self.assertEqual((before, [], []), (self.snapshot(), self.calls(), self.alive()))
        # No other supplier declared: evaluated, with the mention.
        self.providers(evaluator=["p-claude-ro"])
        self.settle()
        shown = self.outcome()
        self.assertTrue(shown["roles"]["same_provider"])
        self.assertIn("même fournisseur qu'un auteur (anthropic)", shown["independence"])

    def test_evaluation_without_result_is_sent_once_more_then_stopped_and_raised_once(self):
        commit = self.verified()
        self.settings(timeout_seconds=0)
        self.evaluator("silent")
        self.write_log.write_text("")

        actions = [self.settle()["action"] for _ in range(4)]

        self.assertEqual(["launched", "relaunched", "stopped", "none"], actions)
        self.assertEqual(2, len(self.calls()))
        shown = self.outcome()
        self.assertEqual(("outcome_evaluation_no_result", commit), (shown["stop"]["reason"], shown["stop"]["commit"]))
        self.assertIn("raised", shown["stop"])
        self.assertEqual(([], None, []), (shown["rounds"], shown["request"], self.alive()))
        listed = [line for line in self.door("list").splitlines() if line.strip().startswith(f"{CONVOY} ")]
        self.assertEqual(1, len(listed), listed)
        mails = [line for line in self.write_log.read_text().splitlines() if line.startswith('["mail"')]
        self.assertEqual(1, len(mails), mails)
        # No result is not an agreement: the gate refuses, and says why.
        status, answer = self.run_gate()
        self.assertEqual((EXIT_REFUSED, (4, "outcome_evaluation", "fail")), (status, self.conditions(answer)[3]))
        self.assertIn("outcome_evaluation_no_result", answer["error"])

    def test_second_settlement_on_the_same_state_does_nothing(self):
        self.opened()
        before = self.snapshot()

        answer = self.settle()

        self.assertEqual("pending", answer["action"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, len(self.calls()))

    def test_convoy_without_the_mark_is_not_touched(self):
        before = self.snapshot()

        for command, env in (("settle", self.env), ("brief", self.session), ("verdict", self.env), ("show", self.env)):
            proc = self.run_cmd(TOOL, command, PLAIN_CONVOY, "--repo", self.repo, env=env)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
