#!/usr/bin/env python3
"""The publication door and the patch door on the second part of the entry
contract of the new flow (T06, af-cgauf8; Spec af-wf4w5r §2, Testing
Decisions seam 2): coverage of the Spec's numbered user stories, operator
needs, launch recipe, pointers posed by the door, and the same rules on the
tickets a patch adds or withdraws. Only the command lines are exercised
(bin/ticket-graph-publish, bin/convoy-state, bin/planning-exception), on a
fake tracker state: one test per refusal and per pass, each refusal
re-reading the tracker to prove nothing was written."""

import copy
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
PUBLISHER = ROOT / "bin" / "ticket-graph-publish"
CONVOY_STATE = ROOT / "bin" / "convoy-state"
PLANNING_EXCEPTION = ROOT / "bin" / "planning-exception"
GRAPH_REVIEW = ROOT / "bin" / "graph-review"
FIXTURES = ROOT / "tests" / "fixtures" / "ticket-graph-publish"
FAKE_BD = FIXTURES / "bd-bead-mode"
FAKE_GC = FIXTURES / "gc"
PROJECTS_CONFIG_DIR = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"
FIXTURE_CITY = ROOT / "tests" / "fixtures" / "delivery-fixture-city"

CONFORMANT_DRAFT = FIXTURES / "fixture-city-new-flow-draft.yaml"
FIXTURE_SPEC = (FIXTURE_CITY / "spec.md").read_text(encoding="utf-8")
PROJECT = "delivery-fixture-city"

MARK = "new-flow/v1"
EXIT_NOT_NEW_FLOW = 4

STORY_1 = "1. As a visiteur, I want voir l'état du jeu de données sur la page d'accueil"
STORY_2 = "2. As a visiteur, I want voir la liste des éléments sur la page d'accueil"
STORY_3 = "3. As an exploitant, I want une sonde de santé"
T2_LINE = (
    "Sur le produit lancé avec le jeu de données « contenu », la page d'accueil (GET /) affiche "
    "les trois éléments « Alpha », « Bêta » et « Gamma »."
)
T4_LINE = "Sur le produit lancé, GET /health répond 200 avec le statut « ok »."


def digest_of(description):
    return "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ticket-graph-publish-coverage-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.gc_log = self.tmp / "gc.log"
        self.gc_log.write_text("")
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()
        self.descriptors = self.tmp / "descriptors"
        self.descriptors.mkdir()
        shutil.copy(FIXTURE_CITY / "descriptor.json", self.descriptors / f"{PROJECT}.json")
        self.env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "GC_BIN": str(FAKE_GC),
            "TICKET_GRAPH_BD_STATE": str(self.state_path),
            "TICKET_GRAPH_GC_LOG": str(self.gc_log),
            "CONVOY_STATE_LOCK_DIR": str(self.tmp / "locks"),
        }
        # The reviewer role the graph review (T08) reads: one provider, one model.
        factory = self.tmp / "factory"
        (factory / "config").mkdir(parents=True)
        (factory / "config" / "delivery-roles.json").write_text(
            json.dumps({"roles": {"reviewer": {"agent": "delivery-reviewer"}}}))
        (factory / "city.toml").write_text('[providers.reviewer-profile]\nargs_append = ["--model", "modele-relecteur"]\n')
        self.review_env = {
            **self.env, "FACTORY_ROOT": str(factory), "DELIVERY_ROLE_READ_ONLY": "1",
            "GRAPH_REVIEW_PROVIDER_FAILOVER_BIN": str(ROOT / "tests" / "fixtures" / "graph-review" / "provider-failover"),
        }

    # --- tracker state --------------------------------------------------------

    def state(self):
        return json.loads(self.state_path.read_text())

    def beads(self):
        return self.state()["beads"]

    def edit_bead(self, bead_id, **fields):
        state = self.state()
        metadata = fields.pop("metadata", {})
        state["beads"][bead_id].update(fields)
        state["beads"][bead_id].setdefault("metadata", {}).update(metadata)
        self.state_path.write_text(json.dumps(state))

    def draft_bead(self, description, approved=True, revises_digest=None):
        metadata = {"spec_id": "spec-1", "display_title": "Fixture City : liste des éléments", "language": "fr"}
        if approved:
            metadata.update({
                "approved_by": "benjamin",
                "approved_evidence": "« j'approuve le graphe » (Benjamin, fixture)",
                "approved_digest": digest_of(description),
            })
        if revises_digest:
            metadata["revises_digest"] = revises_digest
        return {"title": "Draft", "description": description, "status": "open", "labels": [], "metadata": metadata}

    def spec_bead(self, text=FIXTURE_SPEC):
        return {"id": "spec-1", "title": "Spec", "description": text, "status": "open", "labels": [], "metadata": {
            "spec_state": "APPROVED_SPEC", "approved_digest": digest_of(text),
            "gc.project_id": PROJECT, "planning_run_target": "F01"}}

    def seed(self, draft):
        description = draft if isinstance(draft, str) else self.dump(draft)
        self.state_path.write_text(json.dumps({"next_id": 1, "beads": {
            "draft-1": {"id": "draft-1", **self.draft_bead(description)},
            "spec-1": self.spec_bead(),
        }}))
        self.review_graph()

    def review_graph(self):
        """Every seeded draft of the new flow comes with a favorable graph
        review of its digest (T08, tests/graph-review-test.py): what these
        tests observe is the entry contract, checked before it."""
        def review(*argv):
            return subprocess.run((str(GRAPH_REVIEW), *argv), env=self.review_env, text=True, capture_output=True)

        if review("request", "draft-1", "--author-model", "modele-auteur").returncode != 0:
            return
        brief = json.loads(review("brief", "draft-1").stdout)
        answers = lambda checks: {"checks": {
            name: {"state": "not_applicable", "reason": "aucun ticket d'interface"}
            if name == "prototype_fold_present_and_first" else {"state": "favorable"} for name in checks}}
        verdict = self.tmp / "graph-verdict.json"
        verdict.write_text(json.dumps({
            "digest": brief["digest"], "graph": answers(brief["graph_checks"]),
            "tickets": {ticket["id"]: answers(ticket["checks"]) for ticket in brief["tickets"]}}))
        self.assertEqual(0, review("record", "draft-1", "--verdict-file", str(verdict)).returncode)

    def add_draft(self, draft_id, draft, **kwargs):
        state = self.state()
        state["beads"][draft_id] = {"id": draft_id, **self.draft_bead(self.dump(draft), **kwargs)}
        self.state_path.write_text(json.dumps(state))

    def amend_spec(self, text):
        state = self.state()
        state["beads"]["spec-1"] = self.spec_bead(text)
        self.state_path.write_text(json.dumps(state))

    def dump(self, draft):
        return yaml.safe_dump(draft, allow_unicode=True, sort_keys=False)

    def conformant(self):
        return yaml.safe_load(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

    def ticket(self, draft, ticket_id):
        return next(t for t in draft["tickets"] if t["id"] == ticket_id)

    # --- command lines --------------------------------------------------------

    def door(self, command="bd-publish", draft_id="draft-1", extra=(), env=None):
        return subprocess.run(
            (str(PUBLISHER), command, draft_id, "--project", "acme", "--repo-root", str(self.repo_root),
             "--config-dir", str(PROJECTS_CONFIG_DIR), "--descriptors-dir", str(self.descriptors), *extra),
            env={**self.env, **(env or {})}, text=True, capture_output=True,
        )

    def published(self, draft_id="draft-1"):
        proc = self.door(draft_id=draft_id)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def patch(self, draft_id="draft-2", extra=(), env=None):
        return self.door("bd-patch", draft_id, ("--author", "essai", "--reason", "essai de patch", *extra), env)

    def patched(self, draft_id="draft-2", extra=()):
        proc = self.patch(draft_id, extra)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def convoy_state(self, convoy_id, expect=0):
        proc = subprocess.run(
            (str(CONVOY_STATE), "show", convoy_id, "--repo", str(self.repo_root)),
            env=self.env, text=True, capture_output=True,
        )
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def state_tool(self, *args):
        proc = subprocess.run((str(CONVOY_STATE), *args), env=self.env, text=True, capture_output=True)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def shown_ticket(self, convoy_id, bead_id, expect=0):
        return next(t for t in self.convoy_state(convoy_id, expect)["tickets"] if t["id"] == bead_id)

    def gc_calls(self):
        return [json.loads(line) for line in self.gc_log.read_text().splitlines()]

    def assert_refused_and_nothing_written(self, proc_factory, *mentions):
        before = self.state_path.read_bytes()
        calls_before = self.gc_calls()
        proc = proc_factory()
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        for mention in mentions:
            self.assertIn(mention, proc.stderr)
        self.assertEqual(before, self.state_path.read_bytes())
        new_calls = self.gc_calls()[len(calls_before):]
        self.assertEqual([], [call for call in new_calls if call[:2] == ["bd", "update"] or "mail" in call])
        return proc

    def refusal_lines(self, proc, where):
        return [line for line in proc.stderr.splitlines() if line.startswith(f"- {where} :")]


class PublicationCoverageTest(Harness):
    def refused(self, *mentions):
        proc = self.assert_refused_and_nothing_written(self.door, "rien n'est écrit", *mentions)
        self.assertEqual({"draft-1", "spec-1"}, set(self.beads()))
        return proc

    # --- AC1: every numbered user story of the Spec is cited by a ticket -------

    def test_refuses_a_graph_with_an_orphan_user_story_and_names_its_number(self):
        draft = self.conformant()
        self.ticket(draft, "T2")["user_stories"] = [1]
        self.seed(draft)

        proc = self.refused()
        lines = self.refusal_lines(proc, "graphe")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("couvertes par aucun ticket : 2 ", lines[0] + " ")
        self.assertEqual([], self.refusal_lines(proc, "T2"))

    def test_refusal_lists_every_orphan_user_story(self):
        draft = self.conformant()
        self.ticket(draft, "T2")["user_stories"] = [1]
        self.ticket(draft, "T4")["user_stories"] = [1]
        self.seed(draft)

        proc = self.refused()
        self.assertIn("couvertes par aucun ticket : 2, 3", "\n".join(self.refusal_lines(proc, "graphe")))

    def test_orphan_story_corrected_is_published(self):
        # Demonstration line of the ticket, first half.
        draft = self.conformant()
        self.ticket(draft, "T2")["user_stories"] = [1]
        self.seed(draft)
        self.refused("2")

        self.ticket(draft, "T2")["user_stories"] = [1, 2]
        self.seed(draft)
        result = self.published()
        self.assertEqual({"_convoy", "T1", "T2", "T3", "T4"}, set(result["ids"]))

    # --- AC2: a vertical_slice covers at least one story of the Spec -----------

    def test_refuses_a_vertical_slice_that_cites_no_user_story(self):
        for absent in ("missing", "empty"):
            with self.subTest(user_stories=absent):
                draft = self.conformant()
                if absent == "missing":
                    del self.ticket(draft, "T4")["user_stories"]
                else:
                    self.ticket(draft, "T4")["user_stories"] = []
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(
                    any("ne couvre aucune user story" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)
                self.assertEqual([], self.refusal_lines(proc, "T2"))

    def test_refuses_a_slice_that_cites_a_number_absent_from_the_spec(self):
        draft = self.conformant()
        self.ticket(draft, "T4")["user_stories"] = [3, 9]
        self.seed(draft)

        proc = self.refused()
        lines = self.refusal_lines(proc, "T4")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("9", lines[0])
        self.assertIn("absente de la Spec", lines[0])
        self.assertEqual([], self.refusal_lines(proc, "graphe"))

    def test_refuses_user_stories_that_are_not_a_list_of_numbers(self):
        for value in ("3", ["trois"], [3, 3], [0], [3.5], {"story": 3}, [True]):
            with self.subTest(user_stories=value):
                draft = self.conformant()
                self.ticket(draft, "T4")["user_stories"] = value
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(any("user_stories" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)

    def test_refuses_user_stories_on_a_prefactoring_or_a_repair(self):
        for ticket_id in ("T1", "T3"):
            with self.subTest(ticket=ticket_id):
                draft = self.conformant()
                self.ticket(draft, ticket_id)["user_stories"] = [2]
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(
                    any("seule une vertical_slice" in line for line in self.refusal_lines(proc, ticket_id)),
                    proc.stderr)

    def test_a_prefactoring_or_a_repair_does_not_cover_a_story(self):
        # Story 2 is cited only by the prefactoring: it stays an orphan.
        draft = self.conformant()
        self.ticket(draft, "T2")["user_stories"] = [1]
        self.ticket(draft, "T1")["user_stories"] = [2]
        self.seed(draft)

        proc = self.refused()
        self.assertIn("couvertes par aucun ticket : 2", "\n".join(self.refusal_lines(proc, "graphe")))

    # --- a repair cites something the approved Spec holds ----------------------

    def test_refuses_a_repair_that_restores_a_user_story_absent_from_the_spec(self):
        for ref in ("user story 9", "la liste", "user stories 1 et 2"):
            with self.subTest(ref=ref):
                draft = self.conformant()
                self.ticket(draft, "T3")["restores"] = {"kind": "user_story", "ref": ref}
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(any("rétablit" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    def test_refuses_a_repair_that_cites_a_line_the_spec_does_not_hold(self):
        draft = self.conformant()
        self.ticket(draft, "T3")["restores"] = {"kind": "spec_line", "ref": "La page d'accueil clignote en rose."}
        self.seed(draft)

        proc = self.refused()
        self.assertTrue(any("absente de la Spec" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    def test_publishes_a_repair_that_cites_a_line_of_the_spec(self):
        draft = self.conformant()
        self.ticket(draft, "T3")["restores"] = {
            "kind": "spec_line", "ref": "La page d'accueil porte les   ancres du Validated Prototype."}
        self.seed(draft)
        self.published()

    # --- AC3: a declared operator need is lifted before publication ------------

    NEED = {"id": "cle_api_meteo", "kind": "secret", "what": "Clé de l'API météo dans le coffre de l'usine"}

    def with_need(self, need=None):
        draft = self.conformant()
        draft["operator_needs"] = [copy.deepcopy(need or self.NEED)]
        return draft

    def lift(self, *args, draft_id="draft-1"):
        return subprocess.run(
            (str(PUBLISHER), "lift-need", draft_id, "--project", "acme", "--config-dir", str(PROJECTS_CONFIG_DIR),
             *args),
            env=self.env, text=True, capture_output=True,
        )

    def test_refuses_while_a_declared_operator_need_is_not_lifted_and_names_it(self):
        self.seed(self.with_need())

        proc = self.refused("cle_api_meteo", "Clé de l'API météo")
        self.assertTrue(any("non levé" in line for line in self.refusal_lines(proc, "brouillon")), proc.stderr)
        # No convoy exists, so none can start with the need open.
        self.assertEqual([], [b for b in self.beads().values() if b.get("issue_type") == "convoy"])

    def test_publishes_once_the_operator_need_is_lifted(self):
        self.seed(self.with_need())
        self.refused("cle_api_meteo")

        proc = self.lift("--need", "cle_api_meteo", "--by", "benjamin", "--evidence", "« la clé est au coffre »")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("cle_api_meteo", json.loads(proc.stdout)["need"])

        result = self.published()
        self.assertEqual(MARK, result["flow_contract"])
        self.assertEqual("open", self.beads()[result["ids"]["_convoy"]]["status"])

    def test_lifting_one_need_leaves_the_other_one_blocking(self):
        draft = self.with_need()
        draft["operator_needs"].append({"id": "acces_registre", "kind": "access", "what": "Accès au registre"})
        self.seed(draft)
        self.assertEqual(0, self.lift("--need", "cle_api_meteo", "--by", "benjamin", "--evidence", "fait").returncode)

        proc = self.refused("acces_registre")
        self.assertNotIn("cle_api_meteo", proc.stderr)

    def test_lift_need_refuses_anyone_but_the_declared_human_approver(self):
        self.seed(self.with_need())
        self.assert_refused_and_nothing_written(
            lambda: self.lift("--need", "cle_api_meteo", "--by", "mayor", "--evidence", "fait"), "benjamin")

    def test_lift_need_refuses_without_the_words_of_the_approver(self):
        self.seed(self.with_need())
        self.assert_refused_and_nothing_written(
            lambda: self.lift("--need", "cle_api_meteo", "--by", "benjamin", "--evidence", "   "), "evidence")

    def test_lift_need_refuses_a_need_the_draft_does_not_declare(self):
        self.seed(self.with_need())
        self.assert_refused_and_nothing_written(
            lambda: self.lift("--need", "autre_besoin", "--by", "benjamin", "--evidence", "fait"), "autre_besoin")

    def test_a_need_marked_lifted_by_hand_without_the_approver_does_not_count(self):
        self.seed(self.with_need())
        self.edit_bead("draft-1", metadata={"operator_need.cle_api_meteo": json.dumps(
            {"lifted_by": "mayor", "evidence": "fait", "at": "2026-10-06T00:00:00Z"})})
        self.refused("cle_api_meteo")

    def test_refuses_a_malformed_operator_need(self):
        cases = (
            {"id": "Clé API", "kind": "secret", "what": "une clé"},
            {"id": "cle", "kind": "envie", "what": "une clé"},
            {"id": "cle", "kind": "secret", "what": "  "},
            {"id": "cle", "kind": "secret", "what": "une clé", "lifted": True},
            "une clé d'API",
        )
        for need in cases:
            with self.subTest(need=need):
                draft = self.conformant()
                draft["operator_needs"] = [need]
                self.seed(draft)

                proc = self.refused()
                self.assertTrue(
                    any("besoin opérateur" in line for line in self.refusal_lines(proc, "brouillon")), proc.stderr)

    def test_first_publication_withdraws_no_ticket(self):
        draft = self.conformant()
        draft["withdrawn"] = [{"ticket": "T4", "planning_exception": "pd-1"}]
        self.seed(draft)

        proc = self.refused()
        self.assertTrue(any("withdrawn" in line for line in self.refusal_lines(proc, "brouillon")), proc.stderr)

    def test_refuses_a_spec_without_numbered_user_stories(self):
        self.seed(self.conformant())
        self.amend_spec("Spec sans user stories numérotées.")
        self.assert_refused_and_nothing_written(self.door, "user stories numérotées", "rien n'est écrit")

    # --- AC4: the pointers are posed by the door -------------------------------

    def test_published_ticket_carries_spec_digest_stories_siblings_and_seams(self):
        # Demonstration line of the ticket, second half.
        description = CONFORMANT_DRAFT.read_text(encoding="utf-8")
        self.seed(description)
        spec_digest = digest_of(FIXTURE_SPEC)
        # None of the pointers is written in the draft.
        for pointer in (spec_digest, "spec-1", STORY_2, "/health (http)", "Fixture City Oracle"):
            self.assertNotIn(pointer, description)

        result = self.published()
        t2 = self.beads()[result["ids"]["T2"]]["description"]
        self.assertIn("## Spec", t2)
        self.assertIn("spec-1", t2)
        self.assertIn(spec_digest, t2)
        self.assertIn(STORY_1, t2)
        self.assertIn(STORY_2, t2)
        self.assertNotIn(STORY_3, t2)
        # Its sibling tickets, each with its demonstration line.
        siblings = t2.split("## Sibling tickets")[1].split("\n## ")[0]
        self.assertIn("T1", siblings)
        self.assertIn("T3", siblings)
        self.assertIn("Sur le produit lancé, GET /api/items rend pour chaque élément un champ « label » non vide.", siblings)
        self.assertIn("T4", siblings)
        self.assertIn(T4_LINE, siblings)
        self.assertNotIn(T2_LINE, siblings)
        # The seams: entry points of the profile and Testing Decisions of the Spec.
        seams = t2.split("## Seams")[1].split("\n## ")[0]
        self.assertIn("GET / (http)", seams)
        self.assertIn("GET /health (http)", seams)
        self.assertIn("Fixture City Oracle et ligne de commande des portes.", seams)

    def test_every_published_ticket_carries_the_pointers(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))
        result = self.published()
        beads = self.beads()
        for key in ("T1", "T2", "T3", "T4"):
            description = beads[result["ids"][key]]["description"]
            for heading in ("## Spec", "## User stories", "## Sibling tickets", "## Seams"):
                self.assertIn(heading, description, key)
            self.assertIn(digest_of(FIXTURE_SPEC), description, key)
        # A repair shows the story it restores, a slice the ones it covers.
        self.assertIn(STORY_2, beads[result["ids"]["T3"]]["description"])
        self.assertIn(STORY_3, beads[result["ids"]["T4"]]["description"])

    def test_published_slice_carries_its_user_stories_in_a_field_code_reads(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))
        result = self.published()
        convoy = result["ids"]["_convoy"]
        self.assertFalse(self.convoy_state(convoy)["unruled"])
        self.assertEqual(["1", "2"], self.shown_ticket(convoy, result["ids"]["T2"])["user_stories"])
        self.assertEqual(["3"], self.shown_ticket(convoy, result["ids"]["T4"])["user_stories"])
        self.assertIsNone(self.shown_ticket(convoy, result["ids"]["T1"])["user_stories"])
        self.assertIsNone(self.shown_ticket(convoy, result["ids"]["T3"])["user_stories"])

    # --- AC6: launch recipe ----------------------------------------------------

    def without_launch_recipe(self):
        descriptor = json.loads((FIXTURE_CITY / "descriptor.json").read_text(encoding="utf-8"))
        del descriptor["launch"]
        (self.descriptors / f"{PROJECT}.json").write_text(json.dumps(descriptor))

    def establishing(self):
        """The conformant graph whose first slice, T4, establishes the recipe."""
        draft = self.conformant()
        self.ticket(draft, "T4")["establishes_launch_recipe"] = True
        self.ticket(draft, "T2")["blocked_by"] = ["T1", "T4"]
        return draft

    def test_refuses_a_project_whose_profile_declares_no_launch_recipe(self):
        self.without_launch_recipe()
        self.seed(self.conformant())

        proc = self.refused(PROJECT)
        self.assertTrue(any("recette de lancement" in line for line in self.refusal_lines(proc, "graphe")), proc.stderr)

    def test_refuses_a_project_that_has_no_profile_at_all(self):
        (self.descriptors / f"{PROJECT}.json").unlink()
        self.seed(self.conformant())

        proc = self.refused(PROJECT)
        self.assertTrue(any("recette de lancement" in line for line in self.refusal_lines(proc, "graphe")), proc.stderr)

    def test_publishes_without_launch_recipe_when_the_first_slice_establishes_it(self):
        self.without_launch_recipe()
        self.seed(self.establishing())

        result = self.published()
        convoy = result["ids"]["_convoy"]
        self.assertTrue(self.shown_ticket(convoy, result["ids"]["T4"])["establishes_launch_recipe"])
        self.assertFalse(self.shown_ticket(convoy, result["ids"]["T2"])["establishes_launch_recipe"])
        self.assertIn("recette de lancement", self.beads()[result["ids"]["T4"]]["description"])
        # No entry point exists yet: the seams say so instead of inventing one.
        self.assertNotIn("(http)", self.beads()[result["ids"]["T2"]]["description"])

    def test_refuses_when_the_slice_that_establishes_the_recipe_is_not_the_first(self):
        self.without_launch_recipe()
        draft = self.conformant()
        self.ticket(draft, "T4")["establishes_launch_recipe"] = True  # T2 and T3 do not wait for T4
        self.seed(draft)

        proc = self.refused()
        self.assertTrue(any("T2" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)

    def test_refuses_a_recipe_established_by_anything_but_one_vertical_slice(self):
        self.without_launch_recipe()
        draft = self.establishing()
        self.ticket(draft, "T1")["establishes_launch_recipe"] = True
        self.seed(draft)
        proc = self.refused()
        self.assertTrue(
            any("establishes_launch_recipe" in line for line in self.refusal_lines(proc, "T1")), proc.stderr)

        draft = self.establishing()
        self.ticket(draft, "T4")["establishes_launch_recipe"] = "oui"
        self.seed(draft)
        proc = self.refused()
        self.assertTrue(
            any("establishes_launch_recipe" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)

    # --- AC8: overlapping Declared Scopes are serialised, as today -------------

    def test_two_unordered_tickets_with_overlapping_scopes_are_put_in_series(self):
        draft = self.conformant()
        self.ticket(draft, "T2")["scope"] = {"paths": ["app/home.py", "app/static/*"]}
        self.ticket(draft, "T4")["scope"] = {"paths": ["app/home.py"]}
        self.seed(draft)

        result = self.published()
        self.assertEqual([{"blocked": "T4", "by": "T2"}], result["scope_edges"])
        self.assertEqual("T2", self.beads()[result["ids"]["T4"]]["metadata"]["gc.blocked_by"])

    def test_two_ordered_tickets_with_overlapping_scopes_get_no_new_edge(self):
        draft = self.conformant()
        self.ticket(draft, "T1")["scope"] = {"paths": ["app/home.py"]}
        self.ticket(draft, "T2")["scope"] = {"paths": ["app/home.py"]}
        self.seed(draft)

        self.assertEqual([], self.published()["scope_edges"])


class PatchDoorTest(Harness):
    """bd-patch on a published new-flow convoy: draft-1 is published, draft-2
    revises it."""

    REPAIR = {
        "id": "R1", "kind": "repair", "title": "La liste retrouve son troisième élément",
        "blocked_by": [], "target_rigs": ["fixture_city"],
        "what_it_delivers": "La page d'accueil affiche de nouveau les trois éléments.",
        "restores": {"kind": "user_story", "ref": "user story 2"},
        "demonstration_line": "Sur le produit lancé, la page d'accueil (GET /) affiche de nouveau « Gamma ».",
        "acceptance_criteria": [{
            "entry_point": "GET / sur le produit lancé avec le jeu de données « contenu »",
            "observable": "la région « liste » contient la ligne « Gamma »",
            "false_if": "la ligne « Gamma » manque",
        }],
    }
    SLICE = {
        "id": "T5", "kind": "vertical_slice", "title": "La page d'accueil affiche l'heure de génération",
        "blocked_by": ["T2"], "target_rigs": ["fixture_city"],
        "what_it_delivers": "La page d'accueil affiche l'heure de génération du jeu de données.",
        "demonstration_line": "Sur le produit lancé, la page d'accueil (GET /) affiche l'heure de génération.",
        "user_stories": [1],
        "acceptance_criteria": [{
            "entry_point": "GET / sur le produit lancé avec le jeu de données « contenu »",
            "observable": "la région « état » affiche le libellé « Généré à 12:00 »",
            "false_if": "la région « état » n'affiche aucune heure",
        }],
    }

    def setUp(self):
        super().setUp()
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))
        self.first = self.published()
        self.ids = self.first["ids"]
        self.convoy = self.ids["_convoy"]

    def revision(self, *added, keep=("T1", "T2", "T3", "T4"), **top):
        """A draft that revises the published graph: the kept tickets as
        published, then the added ones."""
        draft = self.conformant()
        draft["tickets"] = [t for t in draft["tickets"] if t["id"] in keep] + [copy.deepcopy(t) for t in added]
        known = {t["id"] for t in draft["tickets"]}
        for ticket in draft["tickets"]:
            ticket["blocked_by"] = [b for b in ticket["blocked_by"] if b in known]
        draft.update(top)
        return draft

    def propose(self, draft, approved=True, draft_id="draft-2", revises=None):
        self.add_draft(draft_id, draft, approved=approved, revises_digest=revises or self.first["graph_digest"])

    def refused(self, *mentions, extra=()):
        return self.assert_refused_and_nothing_written(lambda: self.patch(extra=extra), "rien n'est écrit", *mentions)

    # --- AC5: the refusals of T05 and of this ticket apply as they are ---------

    def test_refuses_an_added_ticket_without_demonstration_line(self):
        # Demonstration line of the ticket, last part.
        added = copy.deepcopy(self.SLICE)
        del added["demonstration_line"]
        self.propose(self.revision(added))

        proc = self.refused()
        self.assertTrue(any("ligne de démonstration" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)
        self.assertNotIn("T5", {b["metadata"].get("gc.ticket_id") for b in self.beads().values()})

    def test_refuses_an_added_ticket_whose_criterion_names_a_test(self):
        added = copy.deepcopy(self.SLICE)
        added["acceptance_criteria"] = ["Un test montre que l'heure s'affiche."]
        self.propose(self.revision(added))

        proc = self.refused()
        self.assertTrue(any("nomme un test" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)

    def test_refuses_an_added_ticket_without_kind(self):
        added = copy.deepcopy(self.SLICE)
        del added["kind"]
        self.propose(self.revision(added))

        proc = self.refused()
        self.assertTrue(any("genre absent" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)

    def test_refuses_an_added_slice_that_cites_no_user_story(self):
        added = copy.deepcopy(self.SLICE)
        del added["user_stories"]
        self.propose(self.revision(added))

        proc = self.refused()
        self.assertTrue(
            any("ne couvre aucune user story" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)

    def test_refuses_an_added_repair_that_cites_nothing_to_restore(self):
        added = copy.deepcopy(self.REPAIR)
        del added["restores"]
        for approved in (True, False):
            with self.subTest(approved=approved):
                self.propose(self.revision(added), approved=approved)
                proc = self.refused()
                self.assertTrue(any("rétablit" in line for line in self.refusal_lines(proc, "R1")), proc.stderr)

    def test_refuses_while_an_operator_need_of_the_patch_is_not_lifted(self):
        self.propose(self.revision(self.SLICE, operator_needs=[
            {"id": "acces_horloge", "kind": "access", "what": "Accès au service d'horloge"}]))
        self.refused("acces_horloge")

    def test_approved_patch_adds_a_slice_marked_tracked_and_pointed(self):
        self.propose(self.revision(self.SLICE))

        result = self.patched()
        self.assertEqual(["T5"], result["created"])
        self.assertEqual(MARK, result["flow_contract"])
        self.assertIsNone(result["mayor_notified"])
        t5 = result["ids"]["T5"]

        shown = self.convoy_state(self.convoy)
        self.assertFalse(shown["unruled"])
        ticket = self.shown_ticket(self.convoy, t5)
        self.assertEqual(MARK, ticket["mark"])
        self.assertEqual("vertical_slice", ticket["kind"])
        self.assertEqual(["1"], ticket["user_stories"])
        self.assertEqual(self.SLICE["demonstration_line"], ticket["demonstration_line"])
        self.assertEqual({"resumes": 0, "correction_rounds": 0}, ticket["counters"])

        beads = self.beads()
        self.assertIn(STORY_1, beads[t5]["description"])
        self.assertIn(T4_LINE, beads[t5]["description"].split("## Sibling tickets")[1])
        # The tickets already published now name their new sibling.
        for key in ("T2", "T4"):
            siblings = beads[self.ids[key]]["description"].split("## Sibling tickets")[1].split("\n## ")[0]
            self.assertIn("T5", siblings, key)
            self.assertIn(self.SLICE["demonstration_line"], siblings, key)

    def test_patch_of_a_published_graph_does_not_wake_the_mayor(self):
        self.propose(self.revision(self.SLICE))
        self.patched()
        self.assertEqual([], [call for call in self.gc_calls() if "mail" in call])

    def test_unapproved_patch_that_only_adds_a_repair_is_published(self):
        # Code blocks T2 behind the repair; T1 is carried unchanged, as the
        # blocker T2 already had.
        draft = self.revision(self.REPAIR, keep=("T1", "T2"))
        self.ticket(draft, "T2")["blocked_by"] = ["T1", "R1"]
        self.propose(draft, approved=False)

        result = self.patched()
        self.assertEqual(["R1"], result["created"])
        r1 = result["ids"]["R1"]
        shown = self.convoy_state(self.convoy)
        self.assertFalse(shown["unruled"])
        ticket = self.shown_ticket(self.convoy, r1)
        self.assertEqual("repair", ticket["kind"])
        self.assertEqual(self.REPAIR["demonstration_line"], ticket["demonstration_line"])
        beads = self.beads()
        self.assertEqual("R1,T1", beads[self.ids["T2"]]["metadata"]["gc.blocked_by"])
        self.assertIn("user_story : user story 2", beads[r1]["description"])
        self.assertNotIn("approved_by", beads["draft-2"]["metadata"])

    def test_unapproved_patch_that_adds_anything_but_a_repair_is_refused(self):
        self.propose(self.revision(self.SLICE), approved=False)

        proc = self.refused("approbation")
        self.assertTrue(any("vertical_slice" in line for line in self.refusal_lines(proc, "T5")), proc.stderr)

    def test_unapproved_patch_whose_added_repair_breaks_the_entry_contract_is_refused(self):
        added = copy.deepcopy(self.REPAIR)
        del added["demonstration_line"]
        draft = self.revision(added)
        del self.ticket(draft, "T4")["kind"]
        self.propose(draft, approved=False)

        proc = self.refused()
        self.assertTrue(any("ligne de démonstration" in line for line in self.refusal_lines(proc, "R1")), proc.stderr)
        self.assertTrue(any("genre absent" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)

    def test_unapproved_patch_that_changes_a_published_ticket_is_refused(self):
        draft = self.revision(self.REPAIR)
        self.ticket(draft, "T4")["acceptance_criteria"][0]["observable"] = "la réponse a le statut 200"
        self.propose(draft, approved=False)

        proc = self.refused("approbation")
        self.assertTrue(self.refusal_lines(proc, "T4"), proc.stderr)

    def test_unapproved_patch_that_reorders_published_tickets_is_refused(self):
        draft = self.revision(self.REPAIR)
        self.ticket(draft, "T4")["blocked_by"] = ["T2"]
        self.propose(draft, approved=False)

        proc = self.refused("approbation")
        self.assertTrue(self.refusal_lines(proc, "T4"), proc.stderr)

    def test_unapproved_patch_that_withdraws_a_ticket_is_refused(self):
        register = self.register("resolved")
        self.propose(self.revision(self.REPAIR, keep=("T1", "T2", "T3"), withdrawn=[
            {"ticket": "T4", "planning_exception": "pd-1"}]), approved=False)
        self.refused("approbation", extra=("--planning-exception-register", str(register)))

    def test_patch_approved_by_someone_else_is_refused(self):
        self.propose(self.revision(self.REPAIR))
        self.edit_bead("draft-2", metadata={"approved_by": "mayor"})
        self.assert_refused_and_nothing_written(self.patch, "human approver")

    # --- a published ticket keeps what was frozen with the approved graph ------

    def test_refuses_a_patch_that_changes_a_frozen_field_of_a_published_ticket(self):
        changes = (
            ("T2", "demonstration_line", "Sur le produit lancé, la page d'accueil affiche deux éléments.", "ligne de démonstration"),
            ("T4", "user_stories", [3, 1], "user stories"),
            ("T1", "kind", "vertical_slice", "genre"),
        )
        for ticket_id, field, value, mention in changes:
            with self.subTest(field=field):
                draft = self.revision(self.SLICE)
                ticket = self.ticket(draft, ticket_id)
                ticket[field] = value
                if field == "kind":
                    ticket.pop("unblocks")
                    ticket["demonstration_line"] = "Sur le produit lancé, GET /api/items répond."
                    ticket["user_stories"] = [2]
                self.propose(draft)

                proc = self.refused()
                self.assertTrue(any(mention in line for line in self.refusal_lines(proc, ticket_id)), proc.stderr)

    def test_refuses_a_patch_that_touches_a_delivered_ticket(self):
        self.state_tool("record-gate", self.convoy, self.ids["T4"], "--gate", "ticket_end", "--commit", "a" * 40)
        self.edit_bead(self.ids["T4"], status="closed")
        self.propose(self.revision(self.SLICE))
        self.assert_refused_and_nothing_written(self.patch, "T4")

    def test_coverage_counts_a_delivered_ticket_the_revision_does_not_carry(self):
        self.state_tool("record-gate", self.convoy, self.ids["T4"], "--gate", "ticket_end", "--commit", "a" * 40)
        self.edit_bead(self.ids["T4"], status="closed")
        self.propose(self.revision(self.SLICE, keep=("T1", "T2", "T3")))

        result = self.patched()
        self.assertEqual(["T5"], result["created"])
        # The delivered sibling is still named to the added ticket.
        self.assertIn(T4_LINE, self.beads()[result["ids"]["T5"]]["description"])

    # --- the contract a convoy was published under is the one it is patched under

    def test_refuses_a_draft_without_the_declaration_against_a_marked_convoy(self):
        draft = self.revision(self.SLICE)
        del draft["flow_contract"]
        self.propose(draft)
        self.assert_refused_and_nothing_written(self.patch, "contrat du nouveau flux", "rien n'est écrit")

    def test_refuses_a_new_flow_draft_against_a_convoy_without_the_mark(self):
        old_digest = "sha256:" + "1" * 64
        state = self.state()
        state["beads"]["af-conv"] = {"id": "af-conv", "status": "open", "labels": [], "title": "", "description": "",
                                     "issue_type": "convoy", "metadata": {"gc.graph_digest": old_digest}}
        self.state_path.write_text(json.dumps(state))
        self.propose(self.revision(self.SLICE), revises=old_digest)
        self.assert_refused_and_nothing_written(self.patch, "contrat du nouveau flux", "rien n'est écrit")

    def test_refuses_a_revision_bound_to_another_spec_than_the_convoy(self):
        # A repair may only cite the Spec its convoy was published from.
        other = "Autre Spec.\n\n## User Stories\n\n1. As a visiteur, I want une page rose.\n2. As a visiteur, I want une liste.\n3. As an exploitant, I want une sonde.\n"
        state = self.state()
        state["beads"]["spec-2"] = {**self.spec_bead(other), "id": "spec-2"}
        self.state_path.write_text(json.dumps(state))
        for approved in (False, True):
            with self.subTest(approved=approved):
                draft = self.revision(self.REPAIR, keep=("T1", "T2"))
                self.propose(draft, approved=approved)
                self.edit_bead("draft-2", metadata={"spec_id": "spec-2"})
                self.assert_refused_and_nothing_written(self.patch, "spec-2", "spec-1", "rien n'est écrit")

    def test_refuses_a_mayor_reslice_of_a_marked_convoy(self):
        self.propose(self.revision(self.SLICE))
        self.refused("reslice", extra=("--reslice",))

    def test_refuses_a_revision_that_does_not_revise_the_current_graph(self):
        self.propose(self.revision(self.SLICE), revises="sha256:" + "2" * 64)
        self.assert_refused_and_nothing_written(self.patch, "sha256:" + "2" * 64)

    # --- a second patch sees the whole convoy, not only the last digest --------

    def test_second_patch_updates_a_ticket_the_first_one_did_not_carry(self):
        self.propose(self.revision(self.SLICE, keep=("T1", "T2")))
        first = self.patched()

        second = self.revision(self.SLICE, self.REPAIR)
        self.ticket(second, "T4")["blocked_by"] = ["R1"]
        self.propose(second, draft_id="draft-3", revises=first["graph_digest"])
        result = self.patched("draft-3")

        self.assertEqual(["R1"], result["created"])
        self.assertEqual(self.ids["T4"], result["ids"]["T4"])
        keys = [b["metadata"].get("gc.ticket_id") for b in self.beads().values()]
        self.assertEqual(1, keys.count("T4"))
        self.assertEqual(1, keys.count("T5"))
        self.assertFalse(self.convoy_state(self.convoy)["unruled"])

    # --- a patch whose marking fails is completed by a rerun -------------------

    def test_patch_whose_marking_fails_says_so_and_is_completed_by_a_rerun(self):
        self.propose(self.revision(self.SLICE))

        proc = self.patch(env={"TICKET_GRAPH_GC_BD_UPDATE_FAIL": "1"})
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("marque du nouveau flux", proc.stderr)
        self.assertIn("relancer", proc.stderr)

        result = self.patched()
        shown = self.convoy_state(self.convoy)
        self.assertFalse(shown["unruled"])
        self.assertEqual(MARK, self.shown_ticket(self.convoy, result["ids"]["T5"])["mark"])
        keys = [b["metadata"].get("gc.ticket_id") for b in self.beads().values()]
        self.assertEqual(1, keys.count("T5"))

    # --- AC6: launch recipe, on the resulting graph ----------------------------

    def test_refuses_a_patch_on_a_project_whose_profile_declares_no_launch_recipe(self):
        descriptor = json.loads((FIXTURE_CITY / "descriptor.json").read_text(encoding="utf-8"))
        del descriptor["launch"]
        (self.descriptors / f"{PROJECT}.json").write_text(json.dumps(descriptor))
        self.propose(self.revision(self.SLICE))

        proc = self.refused(PROJECT)
        self.assertTrue(any("recette de lancement" in line for line in self.refusal_lines(proc, "graphe")), proc.stderr)

    # --- AC7: a ticket withdrawn after a resolved Planning Exception -----------

    SPEC_WITHOUT_STORY_3 = FIXTURE_SPEC.replace(
        "3. As an exploitant, I want une sonde de santé, so that je sache que le produit répond.\n", "")

    def register(self, status):
        """A Planning Exception register written by bin/planning-exception:
        decision pd-1, open or resolved."""
        path = self.tmp / "register.json"
        graph = self.tmp / "graph.json"
        graph.write_text(json.dumps({"beads": {self.ids["T4"]: {"blocked_by": []}}}))

        def run(*args):
            proc = subprocess.run((str(PLANNING_EXCEPTION), *args), text=True, capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

        run("init", "--run", "run-fixture", "--out", str(path))
        run("raise", str(path), "--graph", str(graph), "--bead", self.ids["T4"], "--kind", "topology",
            "--run", "run-fixture", "--decision-id", "pd-1", "--summary", "la sonde n'est plus voulue",
            "--raised-by", "auteur-fixture")
        if status == "resolved":
            run("resolve", str(path), "--decision", "pd-1", "--kind", "tactical", "--note", "Benjamin retire la sonde")
        return path

    def withdrawal(self):
        return self.revision(keep=("T1", "T2", "T3"), withdrawn=[{"ticket": "T4", "planning_exception": "pd-1"}])

    def test_refuses_a_withdrawal_that_orphans_a_story_the_spec_still_holds(self):
        register = self.register("resolved")
        self.propose(self.withdrawal())

        proc = self.refused(extra=("--planning-exception-register", str(register)))
        self.assertIn("couvertes par aucun ticket : 3", "\n".join(self.refusal_lines(proc, "graphe")))
        self.assertEqual("open", self.beads()[self.ids["T4"]]["status"])

    def test_withdraws_a_ticket_whose_story_the_amended_spec_removed(self):
        register = self.register("resolved")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        self.propose(self.withdrawal())

        result = self.patched(extra=("--planning-exception-register", str(register)))
        self.assertEqual({"T4": self.ids["T4"]}, result["withdrawn"])
        self.assertEqual("closed", self.beads()[self.ids["T4"]]["status"])
        shown = self.convoy_state(self.convoy)
        self.assertFalse(shown["unruled"], shown)
        self.assertIn("withdrawn", self.shown_ticket(self.convoy, self.ids["T4"])["gates"])
        # The withdrawn ticket is no longer named as a sibling.
        self.assertNotIn(T4_LINE, self.beads()[self.ids["T2"]]["description"])

    def test_coverage_is_recomputed_when_another_slice_takes_the_story_over(self):
        register = self.register("resolved")
        taking_over = copy.deepcopy(self.SLICE)
        taking_over["user_stories"] = [1, 3]
        draft = self.withdrawal()
        draft["tickets"].append(taking_over)
        self.propose(draft)

        result = self.patched(extra=("--planning-exception-register", str(register)))
        self.assertEqual(["T5"], result["created"])
        self.assertEqual("closed", self.beads()[self.ids["T4"]]["status"])

    def test_refuses_a_withdrawal_whose_planning_exception_is_not_resolved(self):
        register = self.register("open")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        self.propose(self.withdrawal())

        proc = self.refused("pd-1", extra=("--planning-exception-register", str(register)))
        self.assertTrue(any("résolue" in line for line in self.refusal_lines(proc, "T4")), proc.stderr)

    def test_refuses_a_withdrawal_that_names_no_known_planning_exception(self):
        register = self.register("resolved")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        draft = self.withdrawal()
        draft["withdrawn"][0]["planning_exception"] = "pd-9"
        self.propose(draft)
        self.refused("pd-9", extra=("--planning-exception-register", str(register)))

        draft["withdrawn"] = [{"ticket": "T4"}]
        self.propose(draft)
        self.refused("planning_exception", extra=("--planning-exception-register", str(register)))

    def test_refuses_a_withdrawal_without_the_register_of_planning_exceptions(self):
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        self.propose(self.withdrawal())
        self.refused("--planning-exception-register")

    def test_refuses_to_withdraw_a_ticket_the_revision_still_carries_or_does_not_know(self):
        register = self.register("resolved")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        draft = self.revision(withdrawn=[{"ticket": "T4", "planning_exception": "pd-1"}])
        self.ticket(draft, "T4")["user_stories"] = [1]
        self.propose(draft)
        self.refused("T4", extra=("--planning-exception-register", str(register)))

        draft = self.withdrawal()
        draft["withdrawn"][0]["ticket"] = "T9"
        self.propose(draft)
        self.refused("T9", extra=("--planning-exception-register", str(register)))

    def test_refuses_to_withdraw_a_delivered_ticket(self):
        register = self.register("resolved")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3)
        self.state_tool("record-gate", self.convoy, self.ids["T4"], "--gate", "ticket_end", "--commit", "a" * 40)
        self.edit_bead(self.ids["T4"], status="closed")
        self.propose(self.withdrawal())
        self.assert_refused_and_nothing_written(
            lambda: self.patch(extra=("--planning-exception-register", str(register))), "T4", "livré")

    def test_refuses_a_withdrawal_that_leaves_a_ticket_waiting_for_the_withdrawn_one(self):
        register = self.register("resolved")
        self.amend_spec(self.SPEC_WITHOUT_STORY_3.replace(
            "1. As a visiteur, I want voir l'état du jeu de données sur la page d'accueil, so that je sache ce qui est servi. [interface]\n", ""))
        # T2 is withdrawn; T3 waits for it and the revision does not say what becomes of T3.
        draft = self.revision(keep=("T1", "T4"), withdrawn=[{"ticket": "T2", "planning_exception": "pd-1"}])
        self.ticket(draft, "T1")["unblocks"] = "T4"
        self.ticket(draft, "T4")["blocked_by"] = ["T1"]
        self.propose(draft)
        self.refused("T3", extra=("--planning-exception-register", str(register)))

    # --- AC8: overlapping Declared Scopes, with an added ticket ----------------

    def test_added_ticket_whose_scope_overlaps_an_unordered_one_is_put_in_series(self):
        added = copy.deepcopy(self.SLICE)
        added["scope"] = {"paths": ["app/health.py"]}
        draft = self.revision(added)
        self.ticket(draft, "T4")["scope"] = {"paths": ["app/health.py"]}
        self.propose(draft)

        result = self.patched()
        self.assertEqual([{"blocked": "T5", "by": "T4"}], result["scope_edges"])
        self.assertEqual("T2,T4", self.beads()[result["ids"]["T5"]]["metadata"]["gc.blocked_by"])


if __name__ == "__main__":
    unittest.main()
