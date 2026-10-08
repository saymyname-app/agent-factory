#!/usr/bin/env python3
"""bin/spec-end-review on a fake tracker state (T25, af-ji2ruy; Spec af-wf4w5r
§6 « Fin de Spec », §9 point 4; Testing Decisions seam 2): one test per pass
and per refusal, each refusal re-reading the tracker, the store and the
branches to prove nothing was written. Only command lines are exercised. The
convoy is the one of tests/spec-end-test.py, whose harness is taken as it
is: a copy of the Delivery Fixture City in a throwaway repository with its
own remote, its two tickets walked to their closing by the real commands,
the three mechanical verdicts rendered by the real bin/spec-end. A stop
reaches the operator through the real bin/escalation-door, read back from
its list. No agent runs: tests/fixtures/spec-end-review/reviewer stands in
for the dispatch door and the reviewer sessions it starts."""

import importlib.machinery
import importlib.util
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "spec-end-review"
FAKE_REVIEWER = ROOT / "tests" / "fixtures" / "spec-end-review" / "reviewer"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gate = load("spec-end-test.py")
CONVOY, SPEC, SLICE, SCREEN = gate.CONVOY, gate.SPEC, gate.SLICE, gate.SCREEN
PROTECTED, INTEGRATION = gate.PROTECTED, gate.INTEGRATION
EXIT_REFUSED, EXIT_NOT_NEW_FLOW = gate.EXIT_REFUSED, gate.EXIT_NOT_NEW_FLOW

RULES = "AGENTS.md"
RULE_LINE = "Toute page servie porte un titre."
# The line of the Spec the two tickets, each correct alone, contradict together.
SPEC_LINE = "As Benjamin, I want la liste de la page d'accueil triée par date, so that je voie d'abord le plus récent."
SPEC_TEXT = (f"## User Stories\n\n1. {SPEC_LINE}\n2. As Benjamin, I want la page d'accueil porter les ancres du "
             "prototype.\n\n## Testing Decisions\n\nSeams : GET / et GET /health.\n")
SORTED_BY_DATE = "docs/tri-des-lignes.md"
SORTED_BY_NAME = "docs/tri-de-l-entete.md"
HANDOFF_PROSE = "Critère 1 observé sur GET /."

DRAFT = {
    "title": "Trier la liste de la page d'accueil par date, en-tête compris",
    "what_it_delivers": "La page d'accueil trie sa liste par date, quel que soit l'en-tête qui la commande.",
    "restores": {"kind": "spec_line", "ref": SPEC_LINE},
    "demonstration_line": "Sur le produit lancé, la liste de la page d'accueil est triée par date.",
    "acceptance_criteria": [{"entry_point": "GET / sur le produit lancé avec le jeu de données « content »",
                             "observable": "la liste est triée par date, la plus récente d'abord",
                             "false_if": "une ligne plus ancienne précède une ligne plus récente"}],
}
CONTRADICTS = {"axis": "spec", "blocking": True,
               "summary": f"{SORTED_BY_NAME} trie par nom ce que {SORTED_BY_DATE} trie par date.",
               "citation": {"source": "spec", "quote": SPEC_LINE}, "repair": DRAFT}
TASTE = {"axis": "standards", "blocking": True, "summary": "Possible Feature Envy : render() lit tout de dataset."}


class SpecEndReviewTest(gate.Harness):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Renamed so that the stages archived here are not the gate suite's.
        cls.holder = cls.holder.rename(cls.holder.with_name(cls.holder.name.replace("spec-end-test", "spec-end-review-test")))
        cls.tmp = cls.holder / "city"

    def setUp(self):
        super().setUp()
        self.door_log = self.tmp / "door.log"
        self.plan = self.tmp / "plan.json"
        self.briefs = self.tmp / "briefs"
        self.env.update({
            "SPEC_END_REVIEW_DISPATCH_DOOR_BIN": str(FAKE_REVIEWER),
            "SPEC_END_REVIEW_FAKE_LOG": str(self.door_log),
            "SPEC_END_REVIEW_FAKE_PLAN": str(self.plan),
            "SPEC_END_REVIEW_FAKE_REPO": str(self.repo),
            "SPEC_END_REVIEW_FAKE_BRIEFS": str(self.briefs),
            "DELIVERY_ROLE_PROVIDER_FAILOVER_BIN": str(self.tmp / "provider-failover"),
        })
        self.env.pop("DELIVERY_ROLE_READ_ONLY", None)
        self.settings(timeout_seconds=3600)
        self.providers("p-codex")
        self.reviewer("favorable")

    # --- harness ------------------------------------------------------------

    def seed(self):
        """The seeded city of the gate tests, plus what the end review
        reads: the Spec of the convoy, a written rule of the repository,
        the delivery roles and the models of their providers."""
        base = super().seed()
        state = json.loads(self.tracker.read_text())
        state["beads"][SPEC] = {"title": "Spec d'essai", "status": "open", "issue_type": "task", "description": SPEC_TEXT}
        self.tracker.write_text(json.dumps(state))
        config = self.root / "config"
        shutil.copy(ROOT / "config" / "delivery-roles.json", config / "delivery-roles.json")
        (config / "model-catalog.json").write_text(json.dumps({"providers": {"p-codex": {"recommended": ["gpt-5.6-sol"]}}}))
        (self.root / "city.toml").write_text(
            '[providers.p-claude]\nargs_append = ["--model", "claude-opus-5-5"]\n\n'
            '[providers.p-codex]\nargs_append = ["-m", "gpt-5.6-sol"]\n')
        return base

    def seed_repo(self):
        super().seed_repo()
        (self.repo / RULES).write_text(f"# Règles du dépôt\n\n- {RULE_LINE}\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "règles du dépôt")
        self.git("push", "-q", "origin", PROTECTED)
        self.base = self.git("rev-parse", "HEAD")

    def settings(self, **end_review):
        (self.root / "config" / "delivery-flow.json").write_text(json.dumps({
            "contract": "agent-factory-delivery-flow/v1", "max_sessions": 2,
            "start": {"formula": "mol-ticket-author", "role": "author"},
            "end_review": {"formula": "mol-end-review", "role": "reviewer", "rig": "agent-factory", **end_review}}))

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

    def contradiction(self):
        """The assembled fixture of the ticket: two tickets, each correct
        alone, that contradict each other on a line of the Spec. Every
        ticket is closed by its gate, and the three mechanical verdicts are
        green on the tip. Returns that tip."""
        def build():
            self.closed(SLICE, {SORTED_BY_DATE: "Les lignes de la liste sont triées par date.\n"})
            self.closed(SCREEN, {SORTED_BY_NAME: "L'en-tête de la liste la trie par nom.\n"})
            status, answer = self.run_gate()
            self.assert_mechanical_green(status, answer)
            return answer["commit"]
        return self.stage("contradiction", build)

    def review_tool(self, command, *args, env=None):
        proc = self.run_cmd(TOOL, command, CONVOY, "--repo", self.repo, *args, env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def settle(self, expect=0):
        status, answer = self.review_tool("settle")
        self.assertEqual(expect, status, answer)
        return answer

    def review(self):
        return self.show()["convoy"]["end_review"]

    def launches(self):
        if not self.door_log.exists():
            return []
        return [json.loads(line) for line in self.door_log.read_text().splitlines()]

    def brief_given(self, number=1):
        return json.loads((self.briefs / f"brief-{number}.json").read_text())

    def record(self, content, env=None):
        session = {**self.env, "DELIVERY_ROLE_READ_ONLY": "1", "GC_SESSION_NAME": "delivery-reviewer-essai", **(env or {})}
        return self.review_tool("record", "--file", self.json_file("handed.json", content), env=session)

    def escalation_list(self):
        return self.door("list")

    def gate_error(self):
        status, answer = self.run_gate()
        self.assert_mechanical_green(status, answer)
        return answer["error"]

    # --- AC1: started on the commit of the gate, on the whole diff ----------------

    def test_the_end_review_is_launched_on_the_commit_of_the_gate_and_covers_the_whole_assembled_diff(self):
        tip = self.contradiction()

        answer = self.settle()

        self.assertEqual(("launched", tip, self.base, 1),
                         tuple(answer[name] for name in ("action", "commit", "base", "launches")))
        # One reviewer session, through the dispatch door, on the reviewer role.
        self.assertEqual([[answer["bead"], "--rig", "agent-factory", "--formula", "mol-end-review", "--role", "reviewer"]],
                         self.launches())
        # The preparation record names the extent under review: the whole
        # diff of the integration branch against the protected branch.
        brief = self.brief_given()
        self.assertEqual((tip, self.base, INTEGRATION, PROTECTED),
                         (brief["commit"], brief["base"], brief["branch"], brief["protected"]))
        self.assertEqual(self.base, brief["diff"]["fixed_point"])
        self.assertIn(f"{self.base}...{tip}", brief["diff"]["command"])
        self.assertIn("tout le diff", brief["diff"]["scope"])
        changed = sorted(self.git("diff", "--name-only", self.base, tip).splitlines())
        self.assertEqual(changed, sorted(entry["path"] for entry in brief["diff"]["files"]))
        # The work of both tickets is in it, not the diff of one of them.
        self.assertIn(SORTED_BY_DATE, changed)
        self.assertIn(SORTED_BY_NAME, changed)
        self.assertEqual((len(changed), len(brief["diff"]["commits"])),
                         (brief["diff"]["extent"]["files"], brief["diff"]["extent"]["commits"]))
        # The extent is kept with the round that read it.
        round_ = self.review()["rounds"][0]
        self.assertEqual((tip, self.base, brief["diff"]["extent"]), (round_["commit"], round_["base"], round_["extent"]))

    def test_the_brief_gives_the_spec_the_tickets_and_the_standards_and_no_prose_of_an_author(self):
        self.contradiction()

        self.settle()

        brief = self.brief_given()
        self.assertEqual((SPEC, SPEC_TEXT), (brief["spec"]["id"], brief["spec"]["text"]))
        self.assertEqual([SLICE, SCREEN], [ticket["id"] for ticket in brief["tickets"]])
        self.assertIn(gate.CRITERION, brief["tickets"][0]["description"])
        self.assertEqual((["standards", "spec"], ["spec", "ticket", "repo_rule"], "code-review"),
                         (brief["axes"], brief["citation_sources"], brief["skill"]))
        self.assertIn(RULES, brief["standards"])
        # Neither a Ticket Handoff nor a commit message: the diff alone speaks for the authors.
        text = json.dumps(brief, ensure_ascii=False)
        self.assertNotIn(HANDOFF_PROSE, text)
        self.assertNotIn("travail du ticket", text)
        self.assertNotIn("handoff", text.lower())

    def test_a_favorable_end_review_meets_the_condition_of_the_gate_and_nothing_is_launched_again(self):
        tip = self.contradiction()

        self.settle()

        review = self.review()
        self.assertEqual({"commit": tip, "outcome": "favorable", "unsettled": []}, review["state"])
        self.assertNotIn("request", review)
        self.assert_end_review_met(self.run_gate()[1])
        before = self.snapshot()
        again = self.settle()
        self.assertEqual(("reviewed", "favorable", []), (again["action"], again["outcome"], again["blocking"]))
        self.assertNotIn("repairs_due", again)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, len(self.launches()))

    def test_the_end_review_waits_for_the_three_mechanical_verdicts(self):
        self.delivered()
        before = self.snapshot()

        answer = self.settle()

        self.assertEqual("waiting", answer["action"])
        self.assertIn("ne sont pas encore rendus", answer["reason"])
        self.assertEqual(([], before), (self.launches(), self.snapshot()))

    def test_no_end_review_is_launched_while_a_ticket_is_open(self):
        self.one_closed()
        before = self.snapshot()

        answer = self.settle()

        self.assertEqual("waiting", answer["action"])
        self.assertIn(SCREEN, answer["reason"])
        self.assertEqual(([], before), (self.launches(), self.snapshot()))

    # --- AC2: a cited Blocking Finding, and the repair its reviewer drafted ---------

    def test_two_tickets_that_contradict_a_line_of_the_spec_get_a_cited_blocking_finding_and_a_drafted_repair(self):
        tip = self.contradiction()
        self.reviewer({"findings": [CONTRADICTS, TASTE]})

        self.settle()

        review = self.review()
        self.assertEqual({"commit": tip, "outcome": "unfavorable", "unsettled": ["F1.1"]}, review["state"])
        finding, taste = review["rounds"][0]["findings"]
        self.assertEqual((True, {"source": "spec", "quote": SPEC_LINE}, DRAFT),
                         (finding["blocking"], finding["citation"], finding["repair_draft"]))
        # A finding of taste is recorded, and blocks nothing.
        self.assertEqual((False, True), (taste["blocking"], "sans citation" in taste["demoted"]))
        # The gate refuses while the finding has no favorable verdict, and names it.
        error = self.gate_error()
        for mention in ("Revue de code de fin", "F1.1", "sans verdict favorable", SORTED_BY_NAME):
            self.assertIn(mention, error)
        # The repair to publish is the draft of the reviewer, and it cites the finding and its line.
        due = self.settle()["repairs_due"]
        self.assertEqual(["F1.1"], [entry["finding"] for entry in due])
        repair = due[0]["repair"]
        self.assertEqual((DRAFT["restores"], DRAFT["demonstration_line"], DRAFT["acceptance_criteria"]),
                         (repair["restores"], repair["demonstration_line"], repair["acceptance_criteria"]))
        for mention in ("F1.1", tip[:12], SPEC_LINE, CONTRADICTS["summary"]):
            self.assertIn(mention, repair["what_it_delivers"])
        self.assertIn("F1.1", repair["title"])
        self.assertEqual(1, len(self.launches()))
        self.assertEqual({"end_rounds": 1}, self.counters())

    def test_a_finding_whose_repair_is_published_is_not_handed_over_twice_and_still_refuses_the_gate(self):
        tip = self.contradiction()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()
        state = json.loads(self.tracker.read_text())
        state["beads"]["fx-r1"] = {"title": "repair", "status": "open", "issue_type": "task",
                                   "description": "## Target rigs\n\nfx-rig", "metadata": {"gc.ticket_kind": "repair"}}
        state["beads"][CONVOY]["tracks"].append("fx-r1")
        self.tracker.write_text(json.dumps(state))
        self.state("mark", CONVOY, "--demonstration-line", "fx-r1=La liste est triée par date")
        self.state("record-gate", CONVOY, "fx-r1", "--gate", "dispatch")
        self.state("set-end-review-repair", CONVOY, "--finding", "F1.1", "--ticket", "fx-r1")

        # The repair is at work: the tip has not moved, nothing is handed over again.
        answer = self.settle()
        self.assertEqual("waiting", answer["action"])
        self.assertIn("fx-r1", answer["reason"])
        # Closed by its gate without having moved the tip (a false state): still nothing to hand over.
        self.state("close-ticket", CONVOY, "fx-r1", "--commit", tip, "--file",
                   ROOT / "tests" / "fixtures" / "convoy-state" / "ticket-end-report.json")
        answer = self.settle()

        self.assertEqual(("reviewed", "unfavorable"), (answer["action"], answer["outcome"]))
        self.assertNotIn("repairs_due", answer)
        self.assertEqual(1, len(self.launches()))

    def test_a_citation_that_is_not_a_line_of_its_source_does_not_block(self):
        self.contradiction()
        invented = {**CONTRADICTS, "citation": {"source": "spec", "quote": "La liste est triée par couleur, toujours."}}
        elsewhere = {**CONTRADICTS, "citation": {"source": "ticket", "ticket": "fx-absent", "quote": gate.CRITERION}}
        self.reviewer({"findings": [invented, elsewhere]})

        self.settle()

        review = self.review()
        self.assertEqual("favorable", review["state"]["outcome"])
        first, second = review["rounds"][0]["findings"]
        self.assertEqual((False, True), (first["blocking"], "n'est pas une ligne de la Spec" in first["demoted"]))
        self.assertEqual((False, True), (second["blocking"], "pas un ticket livré du convoi" in second["demoted"]))
        self.assertNotIn("repair_draft", first)

    def test_a_line_of_a_ticket_of_the_convoy_and_a_written_rule_of_the_repository_are_citations_that_block(self):
        self.contradiction()
        of_ticket = {**CONTRADICTS, "citation": {"source": "ticket", "ticket": SLICE, "quote": gate.CRITERION}}
        of_rule = {**CONTRADICTS, "axis": "standards", "citation": {"source": "repo_rule", "path": RULES, "quote": RULE_LINE},
                   "repair": {**DRAFT, "restores": {"kind": "repo_rule", "ref": RULE_LINE}}}
        self.reviewer({"findings": [of_ticket, of_rule]})

        self.settle()

        self.assertEqual(["F1.1", "F1.2"], self.review()["state"]["unsettled"])

    def test_record_refuses_a_blocking_finding_without_its_drafted_repair_and_a_verdict_of_the_reviewer(self):
        tip = self.contradiction()
        self.reviewer("silent")
        self.settle()
        files = [entry["path"] for entry in json.loads(self.run_cmd(TOOL, "brief", CONVOY, "--repo", self.repo).stdout)["diff"]["files"]]
        coverage = {"axes": ["standards", "spec"], "files": files}
        undrafted = {name: value for name, value in CONTRADICTS.items() if name != "repair"}
        before = self.snapshot()

        for content, mention in (
            ({"commit": tip, "findings": [undrafted], "coverage": coverage}, "sans repair rédigé"),
            ({"commit": tip, "findings": [], "coverage": coverage, "verdict": "favorable"}, "calculée par du code"),
            ({"commit": self.base, "findings": [], "coverage": coverage}, "porte sur le commit"),
        ):
            with self.subTest(mention=mention):
                status, answer = self.record(content)
                self.assertEqual(EXIT_REFUSED, status, answer)
                self.assertIn(mention, answer["error"])
                self.assertEqual(before, self.snapshot())
        # Outside a read-only session of the reviewer role, nothing is recorded.
        status, answer = self.record({"commit": tip, "findings": [], "coverage": coverage},
                                     env={"DELIVERY_ROLE_READ_ONLY": "0"})
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertIn("lecture seule", answer["error"])
        self.assertEqual(before, self.snapshot())

    # --- AC3: absent, crashed, incomplete: never an agreement -----------------------

    def test_an_end_review_still_running_is_pending_and_is_not_launched_again(self):
        self.contradiction()
        self.reviewer("silent")
        self.assertEqual("launched", self.settle()["action"])
        before = self.snapshot()

        answer = self.settle()

        self.assertEqual(("pending", 1), (answer["action"], answer["launches"]))
        self.assertEqual((before, 1), (self.snapshot(), len(self.launches())))
        self.assertIn("revue de fin en cours", self.gate_error())

    def test_an_end_review_without_result_is_launched_once_more_then_stopped_and_raised_once(self):
        tip = self.contradiction()
        self.reviewer("silent")
        self.settings(timeout_seconds=0)
        self.write_log.write_text("")

        self.assertEqual(["launched", "relaunched"], [self.settle()["action"] for _ in range(2)])
        answer = self.settle()

        self.assertEqual(("stopped", "end_review_no_result", True), (answer["action"], answer["stop"], answer["raised"]))
        stop = self.review()["stop"]
        self.assertEqual((tip, "end_review_no_result"), (stop["commit"], stop["reason"]))
        self.assertEqual(2, len(self.launches()))
        # Once, on a bead of its own, on the list of the operator.
        listed = [line for line in self.escalation_list().splitlines() if line.strip().startswith(f"{stop['bead']} ")]
        self.assertEqual(1, len(listed), listed)
        self.assertIn("revue de code de fin", listed[0])
        mails = [line for line in self.write_log.read_text().splitlines() if line.startswith('["mail"')]
        self.assertEqual(1, len(mails), mails)
        # Nothing more is launched, nothing more is asked; the gate goes on refusing.
        before = self.snapshot()
        again = self.settle()
        self.assertEqual(("stopped", False), (again["action"], again["raised"]))
        self.assertEqual((before, 2), (self.snapshot(), len(self.launches())))
        self.assertIn("arrêtée sans verdict", self.gate_error())

    def test_a_reviewer_that_closes_its_bead_without_an_output_is_a_review_without_result(self):
        self.contradiction()
        self.reviewer("closed", "favorable")

        self.assertEqual(["launched", "relaunched"], [self.settle()["action"] for _ in range(2)])

        self.assertEqual("favorable", self.review()["state"]["outcome"])
        self.assertEqual(2, len(self.launches()))

    def test_an_incomplete_output_is_recorded_with_its_duration_counts_as_not_passed_and_is_launched_again(self):
        tip = self.contradiction()
        # The first session leaves two files of the diff out; the second reads everything.
        self.reviewer({"skip": 2}, "favorable")

        self.assertEqual("launched", self.settle()["action"])

        review = self.review()
        round_ = review["rounds"][0]
        # The record says whether the review held: its duration, and that its output is not complete.
        self.assertEqual((tip, "incomplete"), (round_["commit"], round_["outcome"]))
        self.assertIsInstance(round_["duration_seconds"], int)
        self.assertEqual((round_["extent"]["files"] - 2, 2), (round_["coverage"]["files"], len(round_["coverage"]["missing"])))
        self.assertIn("request", review)
        error = self.gate_error()
        self.assertIn("incomplète", error)
        # Not a passed review: launched once more, for a new session.
        self.assertEqual("relaunched", self.settle()["action"])
        review = self.review()
        self.assertEqual(["incomplete", "favorable"], [entry["outcome"] for entry in review["rounds"]])
        self.assert_end_review_met(self.run_gate()[1])

    def test_an_output_that_leaves_one_axis_out_is_incomplete_and_two_of_them_stop_the_review(self):
        self.contradiction()
        self.reviewer({"axes": ["spec"]})

        self.assertEqual(["launched", "relaunched", "stopped"], [self.settle()["action"] for _ in range(3)])

        review = self.review()
        self.assertEqual(["incomplete", "incomplete"], [entry["outcome"] for entry in review["rounds"]])
        self.assertEqual("end_review_no_result", review["stop"]["reason"])
        self.assertEqual({"end_rounds": 0}, self.counters())

    def test_a_dispatch_the_door_refuses_counts_no_launch_and_one_it_defers_is_retried(self):
        self.contradiction()
        self.reviewer("door-refuses", "door-defers", "favorable")

        status, refused = self.review_tool("settle")
        self.assertEqual(EXIT_REFUSED, status, refused)
        self.assertIn("n'a pas été routée", refused["error"])
        self.assertEqual([], self.review()["request"]["launches"])
        deferred = self.settle()
        self.assertEqual("deferred", deferred["action"])
        self.assertEqual([], self.review()["request"]["launches"])

        self.assertEqual(("launched", 1), (lambda a: (a["action"], a["launches"]))(self.settle()))
        self.assertEqual("favorable", self.review()["state"]["outcome"])

    def test_a_drafted_repair_the_patch_door_refused_stops_the_review_and_is_raised_once(self):
        self.contradiction()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()
        self.state("set-end-review-repair", CONVOY, "--finding", "F1.1", "--refused",
                   "critère qui nomme un fichier interne")

        answer = self.settle()

        self.assertEqual(("stopped", "end_review_repair_refused", True), (answer["action"], answer["stop"], answer["raised"]))
        stop = self.review()["stop"]
        self.assertIn("critère qui nomme un fichier interne", stop["detail"])
        listed = [line for line in self.escalation_list().splitlines() if line.strip().startswith(f"{stop['bead']} ")]
        self.assertEqual(1, len(listed), listed)
        self.assertIn("refusé par la porte de publication", self.gate_error())

    # --- AC4: a new round of the end replays the review in full ---------------------

    def test_a_new_tip_has_the_review_replayed_in_full_and_the_verdict_of_the_earlier_round_is_never_reused(self):
        tip = self.contradiction()
        self.settle()
        self.assert_end_review_met(self.run_gate()[1])
        # What the merge of a repair does: one commit more on the integration branch.
        added = self.note(INTEGRATION)

        # The favorable review of the earlier tip passes nothing here, and
        # none is launched before the gate has replayed its verdicts.
        waiting = self.settle()
        self.assertEqual("waiting", waiting["action"])
        self.assertIn("périmés", waiting["reason"])
        self.assertEqual(1, len(self.launches()))
        status, replayed = self.run_gate()
        self.assert_mechanical_green(status, replayed)
        self.assertIn("jamais réutilisé", replayed["error"])

        answer = self.settle()

        self.assertEqual(("launched", added, self.base), (answer["action"], answer["commit"], answer["base"]))
        # In full: the diff of the second round is the whole one again, the new commit included.
        first, second = self.brief_given(1), self.brief_given(2)
        self.assertEqual((tip, added), (first["commit"], second["commit"]))
        self.assertEqual(self.base, second["diff"]["fixed_point"])
        self.assertEqual(sorted([*(entry["path"] for entry in first["diff"]["files"]), "NOTES.md"]),
                         sorted(entry["path"] for entry in second["diff"]["files"]))
        self.assertEqual([(tip, "favorable"), (added, "favorable")],
                         [(entry["commit"], entry["outcome"]) for entry in self.review()["rounds"]])
        self.assert_end_review_met(self.run_gate()[1])

    # --- models, and what the command is not called on ------------------------------

    def test_a_reviewer_of_the_model_of_an_author_is_said_and_so_is_a_model_that_is_not_recorded(self):
        self.contradiction()
        # No author model is recorded on the tickets of this convoy.
        self.settle()
        self.assertIn("non établie", self.brief_given()["independence"])
        self.assertIsNone(self.review()["rounds"][0]["models"]["same_model"])

    def test_a_reviewer_on_the_same_model_as_an_author_is_recorded_as_not_independent(self):
        self.contradiction()
        for ticket in (SLICE, SCREEN):
            self.state("set-model", CONVOY, ticket, "--role", "author", "--agent", "delivery-author",
                       "--provider", "p-claude", "--model", "claude-opus-5-5")
        self.providers("p-claude")

        self.settle()

        models = self.review()["rounds"][0]["models"]
        self.assertEqual((["claude-opus-5-5"], "claude-opus-5-5", True),
                         (models["authors"], models["reviewer"], models["same_model"]))
        self.assertIn("non indépendante", self.brief_given()["independence"])
        status, shown = self.review_tool("show")
        self.assertEqual(0, status, shown)
        self.assertIn("non indépendante", shown["independence"])

    def test_show_gives_the_rounds_the_state_and_the_commit_the_review_is_due_on(self):
        tip = self.contradiction()
        self.reviewer({"findings": [CONTRADICTS]})
        self.settle()
        before = self.snapshot()

        status, shown = self.review_tool("show")

        self.assertEqual(0, status, shown)
        self.assertEqual((tip, {"commit": tip, "outcome": "unfavorable", "unsettled": ["F1.1"]}, 1),
                         (shown["gate_commit"], shown["state"], len(shown["rounds"])))
        self.assertEqual((tip, "end_review"), (shown["end_round"]["commit"], shown["end_round"]["source"]))
        self.assertEqual(before, self.snapshot())

    def test_brief_and_record_are_refused_when_no_end_review_is_open(self):
        self.contradiction()
        before = self.snapshot()

        for status, answer in (self.review_tool("brief"), self.record({"commit": self.base, "findings": []})):
            self.assertEqual(EXIT_REFUSED, status, answer)
            self.assertIn("aucune revue de fin n'est demandée", answer["error"])
        self.assertEqual(before, self.snapshot())

    def test_a_convoy_without_the_mark_is_not_touched(self):
        self.contradiction()
        before = self.snapshot()

        for command in ("settle", "brief", "show"):
            proc = self.run_cmd(TOOL, command, gate.PLAIN_CONVOY, "--repo", self.repo)
            self.assertEqual(EXIT_NOT_NEW_FLOW, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("pas un convoi du nouveau flux", json.loads(proc.stdout)["message"])
        self.assertEqual(([], before), (self.launches(), self.snapshot()))


if __name__ == "__main__":
    unittest.main()
