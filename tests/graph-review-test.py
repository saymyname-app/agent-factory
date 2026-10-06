#!/usr/bin/env python3
"""The graph reviewer of a Ticket Graph Draft (T08, af-n575g4; Spec af-wf4w5r
§2, user stories 7 and 8; Testing Decisions seam 2): the command line of
bin/graph-review and of the publication door on a fake tracker state, one
test per refusal and per pass, each refusal re-reading the tracker to prove
nothing was written. No agent runs here: tests/fixtures/graph-review/reviewer
stands in for the dispatch door and the reviewer session it starts, and only
what goes in and out of the command is observed."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "graph-review"
PUBLISHER = ROOT / "bin" / "ticket-graph-publish"
FIXTURES = ROOT / "tests" / "fixtures" / "graph-review"
PUBLISH_FIXTURES = ROOT / "tests" / "fixtures" / "ticket-graph-publish"
PROJECTS_CONFIG_DIR = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"

NOT_DEMONSTRABLE_DRAFT = FIXTURES / "not-demonstrable-draft.yaml"
FIXTURE_CITY = ROOT / "tests" / "fixtures" / "delivery-fixture-city"
# The Spec the draft slices: the publication door holds the graph to its
# numbered user stories (T06) before it asks for the graph review.
SPEC_TEXT = """Spec synthétique de la Fixture City : une page d'accueil servie par le produit.

## User Stories

1. As a visiteur, I want la page d'accueil lister les éléments servis par l'API, so that je voie ce que le produit contient.
2. As a visiteur, I want voir le total des éléments sur la page d'accueil, so that je sache combien il y en a sans les compter.

Aucune story ne décrit une interface prototypée : il n'y a pas de Validated Prototype.
"""
REVIEWER_MODEL = "modele-relecteur"
AUTHOR_MODEL = "modele-auteur"
NOT_DEMONSTRABLE = {"T2": {"demonstrable_alone": "GET / n'affiche « Total : 3 » qu'une fois T3 livré"}}
EXIT_NOT_NEW_FLOW, EXIT_THIRD_PASS = 4, 5


class GraphReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="graph-review-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.door_log = self.tmp / "door.log"
        self.door_log.write_text("")
        self.gc_log = self.tmp / "gc.log"
        self.gc_log.write_text("")
        self.refusals_path = self.tmp / "refusals.json"
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()
        # The project's profile, with its launch recipe (T06).
        self.descriptors = self.tmp / "descriptors"
        self.descriptors.mkdir()
        shutil.copy(FIXTURE_CITY / "descriptor.json", self.descriptors / "delivery-fixture-city.json")
        # The Factory the command reads its reviewer role from: one role, one
        # provider profile, one model.
        factory = self.tmp / "factory"
        (factory / "config").mkdir(parents=True)
        (factory / "config" / "delivery-roles.json").write_text(
            json.dumps({"roles": {"reviewer": {"agent": "delivery-reviewer"}}}))
        (factory / "city.toml").write_text(
            f'[providers.reviewer-profile]\nargs_append = ["--model", "{REVIEWER_MODEL}"]\n\n[providers.no-model]\n')
        self.env = {
            **os.environ,
            "FACTORY_ROOT": str(factory),
            "BD_BIN": str(PUBLISH_FIXTURES / "bd-bead-mode"),
            "GC_BIN": str(PUBLISH_FIXTURES / "gc"),
            "TICKET_GRAPH_BD_STATE": str(self.state_path),
            "TICKET_GRAPH_GC_LOG": str(self.gc_log),
            "TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY": "1",
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
            "GRAPH_REVIEW_DISPATCH_DOOR_BIN": str(FIXTURES / "reviewer"),
            "GRAPH_REVIEW_PROVIDER_FAILOVER_BIN": str(FIXTURES / "provider-failover"),
            "GRAPH_REVIEW_FAKE_LOG": str(self.door_log),
            "GRAPH_REVIEW_FAKE_REFUSALS": str(self.refusals_path),
            "GRAPH_REVIEW_POLL_SECONDS": "0.05",
        }
        self.env.pop("DELIVERY_ROLE_READ_ONLY", None)
        self.reviewer_refuses({})
        self.seed(self.draft())

    # --- harness ------------------------------------------------------------

    def digest(self, description):
        return "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()

    def draft(self):
        return yaml.safe_load(NOT_DEMONSTRABLE_DRAFT.read_text(encoding="utf-8"))

    def text(self, draft):
        return yaml.safe_dump(draft, allow_unicode=True, sort_keys=False)

    def seed(self, draft):
        """A Ticket Graph Draft bead approved at its current digest, bound to
        an approved Spec bead: only the graph review is left to decide."""
        description, spec_text = self.text(draft), SPEC_TEXT
        self.state_path.write_text(json.dumps({"next_id": 1, "beads": {
            "draft-1": {"id": "draft-1", "title": "Draft", "description": description, "status": "open",
                        "labels": [], "metadata": {
                            "spec_id": "spec-1", "approved_by": "benjamin",
                            "approved_evidence": "« j'approuve le graphe » (Benjamin, fixture)",
                            "approved_digest": self.digest(description),
                            "display_title": "Fixture City : total des éléments", "language": "fr"}},
            "spec-1": {"id": "spec-1", "title": "Spec", "description": spec_text, "status": "open",
                       "labels": [], "metadata": {
                           "spec_state": "APPROVED_SPEC", "approved_digest": self.digest(spec_text),
                           "gc.project_id": "delivery-fixture-city", "planning_run_target": "F01"}},
        }}))

    def rewrite_draft(self, change):
        """Benjamin and the /to-tickets session correct the draft, and he
        approves the corrected text: its digest changes."""
        state = json.loads(self.state_path.read_text())
        bead = state["beads"]["draft-1"]
        draft = yaml.safe_load(bead["description"])
        change(draft)
        bead["description"] = self.text(draft)
        bead["metadata"]["approved_digest"] = self.digest(bead["description"])
        self.state_path.write_text(json.dumps(state))

    def make_t2_demonstrable(self, draft):
        t2 = next(t for t in draft["tickets"] if t["id"] == "T2")
        t2["what_it_delivers"] = "Le chargeur calcule le total des éléments et la page d'accueil l'affiche."

    def reviewer_refuses(self, by_pass):
        self.refusals_path.write_text(json.dumps(by_pass, ensure_ascii=False))

    def tool(self, *argv, env=None):
        proc = subprocess.run((str(TOOL), *argv), env={**self.env, **(env or {})}, text=True, capture_output=True)
        try:
            proc.json = json.loads(proc.stdout)
        except ValueError:
            proc.json = None
        return proc

    def review(self, author_model=AUTHOR_MODEL, env=None, timeout="5"):
        return self.tool("review", "draft-1", "--author-model", author_model,
                         "--timeout", timeout, env=env)

    def reviewed(self, **kwargs):
        proc = self.review(**kwargs)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc.json

    def decide(self, *argv, approved_by="benjamin", words="je garde ce ticket tel quel", decision="publish"):
        return self.tool("decide", "draft-1", *argv, "--decision", decision, "--approved-by", approved_by,
                         "--words", words, "--project", "acme", "--config-dir", str(PROJECTS_CONFIG_DIR))

    def publish(self):
        return subprocess.run(
            (str(PUBLISHER), "bd-publish", "draft-1", "--project", "acme", "--repo-root", str(self.repo_root),
             "--config-dir", str(PROJECTS_CONFIG_DIR), "--descriptors-dir", str(self.descriptors)),
            env=self.env, text=True, capture_output=True,
        )

    def beads(self):
        return json.loads(self.state_path.read_text())["beads"]

    def current_digest(self):
        return self.digest(self.beads()["draft-1"]["description"])

    def shown(self):
        proc = self.tool("show", "draft-1")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.json

    def assert_refused_nothing_written(self, run, *mentions, code=1):
        before = self.state_path.read_bytes()
        proc = run()
        self.assertEqual(code, proc.returncode, proc.stdout + proc.stderr)
        for mention in mentions:
            self.assertIn(mention, proc.stderr)
        self.assertEqual(before, self.state_path.read_bytes())
        return proc

    def assert_publication_refused(self, *mentions):
        proc = self.assert_refused_nothing_written(self.publish, "rien n'est écrit", *mentions)
        self.assertEqual({"draft-1", "spec-1"}, {k for k in self.beads() if not self.is_review_bead(k)})
        return proc

    def is_review_bead(self, bead_id):
        return "graph-review" in self.beads()[bead_id].get("labels", [])

    def two_passes_refusing_t2(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE, "2": NOT_DEMONSTRABLE})
        self.reviewed()
        return self.reviewed()

    def verdict_file(self, change=lambda verdict: None):
        """A verdict as a reviewer session writes it from the brief: every
        question answered favorably, then altered by `change`."""
        brief = self.tool("brief", "draft-1").json
        answers = lambda checks: {"checks": {
            name: {"state": "not_applicable", "reason": "aucun ticket d'interface"}
            if name == "prototype_fold_present_and_first" else {"state": "favorable"} for name in checks}}
        verdict = {"digest": brief["digest"], "graph": answers(brief["graph_checks"]),
                   "tickets": {t["id"]: answers(t["checks"]) for t in brief["tickets"]}}
        change(verdict)
        path = self.tmp / "verdict.json"
        path.write_text(json.dumps(verdict, ensure_ascii=False))
        return str(path)

    def record(self, path, read_only=True):
        return self.tool("record", "draft-1", "--verdict-file", path,
                         env={"DELIVERY_ROLE_READ_ONLY": "1"} if read_only else None)

    def requested(self):
        proc = self.tool("request", "draft-1", "--author-model", AUTHOR_MODEL)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.json

    # --- AC1: one verdict per ticket and one on the graph, bound to the digest

    def test_review_refuses_the_ticket_that_is_not_demonstrable_alone(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE})

        result = self.reviewed()

        self.assertEqual(self.current_digest(), result["digest"])
        self.assertEqual(1, result["pass"])
        self.assertEqual({"T1": "favorable", "T2": "unfavorable", "T3": "favorable"},
                         {ticket: entry["verdict"] for ticket, entry in result["tickets"].items()})
        self.assertEqual([{"target": "T2", "reasons": [{
            "check": "demonstrable_alone", "question": "démontrable seul",
            "reason": NOT_DEMONSTRABLE["T2"]["demonstrable_alone"]}]}], result["refusals"])

    def test_review_records_every_closed_question_per_ticket_and_on_the_graph(self):
        result = self.reviewed()

        asked = {"demonstrable_alone", "criteria_observable_falsifiable", "size_tenable", "same_surface_ordered",
                 "declared_scope_includes_wiring"}
        for ticket in ("T1", "T2", "T3"):
            self.assertEqual(asked, set(result["tickets"][ticket]["checks"]), ticket)
        # Only T3 declares a scope: the question is asked of it alone.
        self.assertEqual("not_applicable", result["tickets"]["T1"]["checks"]["declared_scope_includes_wiring"]["state"])
        self.assertEqual("favorable", result["tickets"]["T3"]["checks"]["declared_scope_includes_wiring"]["state"])
        self.assertEqual({"no_orphan_story", "assembly_point_not_confiscated", "prototype_fold_present_and_first"},
                         set(result["graph"]["checks"]))
        self.assertEqual("favorable", result["graph"]["verdict"])
        stored = self.shown()["passes"]
        self.assertEqual([self.current_digest()], [record["digest"] for record in stored])
        self.assertEqual(result["tickets"], stored[0]["tickets"])

    def test_review_is_routed_to_the_reviewer_role_as_a_fresh_piece_of_work(self):
        result = self.reviewed()

        calls = [json.loads(line) for line in self.door_log.read_text().splitlines()]
        self.assertEqual([[result["review_bead"], "--rig", "agent-factory", "--formula", "mol-graph-review",
                           "--role", "reviewer"]], calls)
        self.assertIn("draft: draft-1", self.beads()[result["review_bead"]]["description"])

    def test_a_graph_refusal_is_a_refusal_like_a_ticket_one(self):
        self.reviewer_refuses({"1": {"graphe": {"no_orphan_story": "la user story 4 n'est couverte par aucun ticket"}}})

        result = self.reviewed()

        self.assertEqual("unfavorable", result["graph"]["verdict"])
        self.assertEqual(["graphe"], [refusal["target"] for refusal in result["refusals"]])

    def test_review_without_a_verdict_is_not_passed_and_counts_no_pass(self):
        proc = self.review(env={"GRAPH_REVIEW_FAKE_MODE": "silent"}, timeout="0")

        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("sans résultat", proc.stderr)
        self.assertEqual([], self.shown()["passes"])
        self.assert_publication_refused("n'a pas de relecture de graphe")
        self.assertEqual(1, self.reviewed()["pass"])

    def test_review_the_door_does_not_route_counts_no_pass(self):
        proc = self.review(env={"GRAPH_REVIEW_FAKE_MODE": "door-refuses"})

        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("n'a pas été routée vers le rôle relecteur", proc.stderr)
        self.assertEqual([], self.shown()["passes"])

    def test_a_draft_that_does_not_declare_the_new_flow_is_not_touched(self):
        draft = self.draft()
        del draft["flow_contract"]
        self.seed(draft)

        for argv in (("review", "draft-1", "--author-model", AUTHOR_MODEL), ("check", "draft-1"),
                     ("remaining", "draft-1")):
            self.assert_refused_nothing_written(
                lambda: self.tool(*argv), "pas un brouillon du nouveau flux", code=EXIT_NOT_NEW_FLOW)
        self.assertEqual("", self.door_log.read_text())

    # --- the verdict a reviewer session hands in ------------------------------

    def test_record_refuses_a_verdict_on_another_digest(self):
        self.requested()
        path = self.verdict_file(lambda verdict: verdict.update(digest="sha256:" + "0" * 64))

        self.assert_refused_nothing_written(lambda: self.record(path), "porte sur le digest")

    def test_record_refuses_a_verdict_that_skips_a_ticket(self):
        self.requested()
        path = self.verdict_file(lambda verdict: verdict["tickets"].pop("T2"))

        self.assert_refused_nothing_written(lambda: self.record(path), "- T2 : pas de verdict")

    def test_record_refuses_a_verdict_on_an_unknown_ticket(self):
        self.requested()
        path = self.verdict_file(lambda verdict: verdict["tickets"].update(T9=verdict["tickets"]["T1"]))

        self.assert_refused_nothing_written(lambda: self.record(path), "- T9 : ticket inconnu du brouillon")

    def test_record_refuses_a_verdict_that_skips_a_question(self):
        self.requested()
        path = self.verdict_file(lambda verdict: verdict["tickets"]["T1"]["checks"].pop("size_tenable"))

        self.assert_refused_nothing_written(lambda: self.record(path), "- T1 : pas de réponse à « size_tenable »")

    def test_record_refuses_a_declared_scope_left_unjudged(self):
        self.requested()
        path = self.verdict_file(
            lambda verdict: verdict["tickets"]["T3"]["checks"].pop("declared_scope_includes_wiring"))

        self.assert_refused_nothing_written(
            lambda: self.record(path), "- T3 : pas de réponse à « declared_scope_includes_wiring »")

    def test_record_refuses_a_refusal_without_a_reason(self):
        self.requested()
        path = self.verdict_file(
            lambda verdict: verdict["tickets"]["T2"]["checks"].update(demonstrable_alone={"state": "unfavorable"}))

        self.assert_refused_nothing_written(lambda: self.record(path), "« demonstrable_alone » est unfavorable sans raison")

    def test_record_refuses_a_state_outside_the_closed_list(self):
        self.requested()
        path = self.verdict_file(
            lambda verdict: verdict["tickets"]["T2"]["checks"].update(size_tenable={"state": "plutôt oui"}))

        self.assert_refused_nothing_written(lambda: self.record(path), "état hors liste pour « size_tenable »")

    def test_record_refuses_a_global_verdict_given_by_the_reviewer_in_place_of_answers(self):
        self.requested()
        path = self.verdict_file(lambda verdict: verdict["tickets"].update(T1={"verdict": "favorable"}))

        self.assert_refused_nothing_written(lambda: self.record(path), "- T1 : pas de réponses")

    def test_record_refuses_outside_a_read_only_reviewer_session(self):
        self.requested()
        path = self.verdict_file()

        self.assert_refused_nothing_written(lambda: self.record(path, read_only=False), "en lecture seule")

    def test_record_refuses_when_no_review_was_requested(self):
        self.requested()
        path = self.verdict_file()
        self.seed(self.draft())

        self.assert_refused_nothing_written(lambda: self.record(path), "aucune relecture de graphe n'est demandée")

    # --- AC2: the verdicts hold for one digest; the publication door refuses --

    def test_publication_refuses_a_draft_that_was_never_reviewed(self):
        self.assert_publication_refused("n'a pas de relecture de graphe")

    def test_publication_passes_with_a_favorable_review_of_the_current_digest(self):
        self.reviewed()

        proc = self.publish()

        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual({"T1", "T2", "T3", "_convoy"}, set(result["ids"]))
        self.assertEqual(1, result["graph_review"]["pass"])
        self.assertEqual(self.current_digest(), result["graph_review"]["digest"])

    def test_a_draft_modified_after_its_review_is_refused_at_publication(self):
        reviewed_digest = self.reviewed()["digest"]

        self.rewrite_draft(self.make_t2_demonstrable)

        self.assertNotEqual(reviewed_digest, self.current_digest())
        check = self.assert_refused_nothing_written(lambda: self.tool("check", "draft-1"), reviewed_digest)
        self.assertIn(self.current_digest(), check.stderr)
        self.assert_publication_refused("a changé depuis sa relecture de graphe", reviewed_digest)

    def test_a_first_pass_with_refusals_is_refused_at_publication(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE})
        self.reviewed()

        self.assert_publication_refused("la première passe du relecteur de graphe refuse T2", "seconde passe")

    def test_the_second_pass_on_the_corrected_draft_opens_publication(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE})
        self.reviewed()
        self.rewrite_draft(self.make_t2_demonstrable)

        second = self.reviewed()

        self.assertEqual((2, self.current_digest(), []), (second["pass"], second["digest"], second["refusals"]))
        self.assertEqual(0, self.publish().returncode)

    # --- AC3: no third pass; the remaining refusals go to Benjamin ------------

    def test_a_third_review_is_refused_and_lists_the_remaining_refusals(self):
        self.two_passes_refusing_t2()
        calls_before = self.door_log.read_text()

        proc = self.assert_refused_nothing_written(
            self.review, "pas de troisième passe", "- T2 — à trancher par Benjamin",
            "démontrable seul : " + NOT_DEMONSTRABLE["T2"]["demonstrable_alone"], code=EXIT_THIRD_PASS)

        self.assertEqual(["T2"], [item["target"] for item in proc.json["remaining"]])
        self.assertEqual(calls_before, self.door_log.read_text())
        self.assertEqual(2, len(self.shown()["passes"]))

    def test_remaining_lists_what_the_second_pass_still_refuses(self):
        self.reviewer_refuses({"1": {**NOT_DEMONSTRABLE, "T3": {"size_tenable": "trois écrans en un ticket"}},
                               "2": NOT_DEMONSTRABLE})
        self.reviewed()
        self.assertEqual([], self.tool("remaining", "draft-1").json["remaining"])
        self.reviewed()

        state = self.tool("remaining", "draft-1").json
        text = self.tool("remaining", "draft-1", "--text").stdout

        self.assertEqual([("T2", None)], [(item["target"], item["decision"]) for item in state["remaining"]])
        self.assertIn("- T2 — à trancher par Benjamin", text)
        self.assertNotIn("- T3", text)

    # --- AC4: Benjamin rules ticket by ticket, his words recorded -------------

    def test_publication_refuses_while_a_remaining_refusal_has_no_decision(self):
        self.two_passes_refusing_t2()

        self.assert_publication_refused("1 refus restant(s)", "sans décision de Benjamin", "T2")

    def test_a_decision_is_recorded_with_benjamins_words_and_opens_publication(self):
        self.two_passes_refusing_t2()

        proc = self.decide("--ticket", "T2", words="  T2 reste ainsi : T3 suit dans la même Spec.  ")

        self.assertEqual(0, proc.returncode, proc.stderr)
        decision = self.shown()["decisions"]["T2"]
        self.assertEqual(("publish", "T2 reste ainsi : T3 suit dans la même Spec.", "benjamin", self.current_digest()),
                         (decision["decision"], decision["words"], decision["by"], decision["digest"]))
        self.assertIn("« T2 reste ainsi : T3 suit dans la même Spec. »", self.tool("remaining", "draft-1", "--text").stdout)
        published = self.publish()
        self.assertEqual(0, published.returncode, published.stderr)
        self.assertEqual(decision, json.loads(published.stdout)["graph_review"]["decisions"]["T2"])

    def test_a_decision_without_benjamins_words_is_refused(self):
        self.two_passes_refusing_t2()

        for words in ("", "   \n "):
            self.assert_refused_nothing_written(
                lambda: self.decide("--ticket", "T2", words=words), "avec les mots de Benjamin")
        self.assert_publication_refused("sans décision de Benjamin")

    def test_a_decision_by_anyone_but_the_declared_human_approver_is_refused(self):
        self.two_passes_refusing_t2()

        self.assert_refused_nothing_written(
            lambda: self.decide("--ticket", "T2", approved_by="delivery-reviewer"),
            "n'est pas l'approbateur humain déclaré")

    def test_a_decision_on_a_ticket_that_is_not_a_remaining_refusal_is_refused(self):
        self.two_passes_refusing_t2()

        self.assert_refused_nothing_written(lambda: self.decide("--ticket", "T1"), "T1 n'est pas un refus restant")

    def test_a_decision_before_the_second_pass_is_refused(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE})
        self.reviewed()

        self.assert_refused_nothing_written(lambda: self.decide("--ticket", "T2"), "T2 n'est pas un refus restant")

    def test_a_ticket_is_ruled_once(self):
        self.two_passes_refusing_t2()
        self.assertEqual(0, self.decide("--ticket", "T2").returncode)

        self.assert_refused_nothing_written(
            lambda: self.decide("--ticket", "T2", decision="rework"), "T2 est déjà tranché")

    def test_each_remaining_refusal_needs_its_own_decision_the_graph_included(self):
        graph_refusal = {"graphe": {"no_orphan_story": "la user story 4 n'est couverte par aucun ticket"}}
        self.reviewer_refuses({"2": {**NOT_DEMONSTRABLE, **graph_refusal}})
        self.reviewed()
        self.reviewed()
        self.assertEqual(0, self.decide("--ticket", "T2").returncode)

        self.assert_publication_refused("1 refus restant(s)", "graphe")

        self.assertEqual(0, self.decide("--graph", words="la story 4 sort de cette Spec").returncode)
        self.assertEqual(0, self.publish().returncode)

    def test_a_ticket_benjamin_sends_back_keeps_publication_closed(self):
        self.two_passes_refusing_t2()
        self.assertEqual(0, self.decide("--ticket", "T2", decision="rework", words="T2 est à refaire").returncode)

        self.assert_publication_refused("« à reprendre » pour T2", "nouveau brouillon")

    def test_a_decision_does_not_survive_a_change_of_the_draft(self):
        self.two_passes_refusing_t2()
        self.assertEqual(0, self.decide("--ticket", "T2").returncode)

        self.rewrite_draft(self.make_t2_demonstrable)

        self.assert_publication_refused("a changé depuis sa relecture de graphe", "nouveau brouillon")
        self.assertEqual([], self.tool("remaining", "draft-1").json["remaining"])

    # --- AC5: a reviewer of the author's model is never silent ----------------

    def test_a_reviewer_of_another_model_is_recorded_as_such(self):
        result = self.reviewed()

        self.assertEqual((False, None, REVIEWER_MODEL, AUTHOR_MODEL),
                         (result["same_model"], result["model_independence"], result["reviewer_model"],
                          result["author_model"]))

    def test_a_reviewer_of_the_authors_model_is_flagged_in_the_verdict_and_wherever_it_is_read(self):
        self.reviewer_refuses({"1": NOT_DEMONSTRABLE, "2": NOT_DEMONSTRABLE})
        # The same model, as another session would spell it.
        self.reviewed(author_model="Modele Relecteur")
        result = self.reviewed(author_model="Modele Relecteur")

        self.assertTrue(result["same_model"])
        self.assertIn("même modèle que l'auteur du graphe", result["model_independence"])
        self.assertTrue(self.shown()["passes"][1]["same_model"])
        self.assertIn("même modèle que l'auteur du graphe", self.tool("remaining", "draft-1", "--text").stdout)
        self.assertEqual(0, self.decide("--ticket", "T2").returncode)
        published = json.loads(self.publish().stdout)
        self.assertTrue(published["graph_review"]["same_model"])
        self.assertIn("même modèle que l'auteur du graphe", published["graph_review"]["model_independence"])

    def test_a_review_whose_author_model_is_not_declared_is_refused(self):
        self.assert_refused_nothing_written(lambda: self.review(author_model="  "), "--author-model est requis")
        self.assertEqual("", self.door_log.read_text())

    def test_a_review_whose_reviewer_model_is_unknown_is_refused(self):
        for provider, mention in (("no-model", "le modèle du fournisseur no-model"), ("", "aucun fournisseur")):
            self.assert_refused_nothing_written(
                lambda: self.review(env={"GRAPH_REVIEW_FAKE_PROVIDER": provider}), mention)
        self.assertEqual("", self.door_log.read_text())


if __name__ == "__main__":
    unittest.main()
