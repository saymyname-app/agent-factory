#!/usr/bin/env python3
"""The publication door on a draft that declares the new-flow contract (T05,
af-c8n7ep; Spec af-wf4w5r §2, Testing Decisions seam 2): the command line of
bin/ticket-graph-publish on a fake tracker state, one test per refusal and
per pass, each refusal re-reading the tracker to prove nothing was written.
What a published convoy carries is read back through bin/convoy-state, the
command every later gate reads it with."""

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
GRAPH_REVIEW = ROOT / "bin" / "graph-review"
FIXTURES = ROOT / "tests" / "fixtures" / "ticket-graph-publish"
FAKE_BD = FIXTURES / "bd-bead-mode"
FAKE_GC = FIXTURES / "gc"
PROJECTS_CONFIG_DIR = ROOT / "tests" / "fixtures" / "spec-approve" / "projects"

CONFORMANT_DRAFT = FIXTURES / "fixture-city-new-flow-draft.yaml"
FIXTURE_CITY = ROOT / "tests" / "fixtures" / "delivery-fixture-city"
# The Spec the conformant draft slices: numbered user stories 1 to 3 (T06).
FIXTURE_SPEC = (FIXTURE_CITY / "spec.md").read_text(encoding="utf-8")
LEGACY_SPEC = "spec de la fixture"
COCKPIT_V2_DRAFT = FIXTURES / "cockpit-v2-draft.yaml"
LEGACY_GOLDEN = FIXTURES / "legacy-publication-golden.json"

MARK = "new-flow/v1"
EXIT_NOT_NEW_FLOW = 4


class EntryContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ticket-graph-publish-entry-contract-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_path = self.tmp / "beads.json"
        self.gc_log = self.tmp / "gc.log"
        self.gc_log.write_text("")
        self.repo_root = self.tmp / "repo"
        self.repo_root.mkdir()
        # The repository of the project: the door opens the integration
        # branch of the Spec there, at the tip of its protected branch (T18).
        for argv in (("init", "-q", "-b", "main"),
                     ("-c", "user.name=essai", "-c", "user.email=essai@example.invalid",
                      "commit", "-q", "--allow-empty", "-m", "base")):
            subprocess.run(("git", "-C", str(self.repo_root), *argv), check=True,
                           env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
        # The project's profile, with its launch recipe and entry points (T06).
        self.descriptors = self.tmp / "descriptors"
        self.descriptors.mkdir()
        shutil.copy(FIXTURE_CITY / "descriptor.json", self.descriptors / "delivery-fixture-city.json")
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

    # --- harness ------------------------------------------------------------

    def digest(self, description):
        return "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()

    def seed(self, description, revises_digest=None, spec_text=FIXTURE_SPEC):
        """An approved Ticket Graph Draft bead with this description, bound to
        an approved Spec bead."""
        draft_metadata = {
            "spec_id": "spec-1", "approved_by": "benjamin",
            "approved_evidence": "« j'approuve le graphe » (Benjamin, fixture)",
            "approved_digest": self.digest(description),
            "display_title": "Fixture City : liste des éléments", "language": "fr",
        }
        if revises_digest:
            draft_metadata["revises_digest"] = revises_digest
        self.state_path.write_text(json.dumps({"next_id": 1, "beads": {
            "draft-1": {"id": "draft-1", "title": "Draft", "description": description, "status": "open",
                        "labels": [], "metadata": draft_metadata},
            "spec-1": {"id": "spec-1", "title": "Spec", "description": spec_text, "status": "open",
                       "labels": [], "metadata": {
                           "spec_state": "APPROVED_SPEC", "approved_digest": self.digest(spec_text),
                           "gc.project_id": "delivery-fixture-city", "planning_run_target": "F01"}},
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

    def conformant(self):
        return yaml.safe_load(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

    def seed_draft(self, draft, **kwargs):
        self.seed(yaml.safe_dump(draft, allow_unicode=True, sort_keys=False), **kwargs)

    def ticket(self, draft, ticket_id):
        return next(t for t in draft["tickets"] if t["id"] == ticket_id)

    def door(self, command="bd-publish", extra=(), env=None):
        return subprocess.run(
            (str(PUBLISHER), command, "draft-1", "--project", "acme", "--repo-root", str(self.repo_root),
             "--config-dir", str(PROJECTS_CONFIG_DIR), "--descriptors-dir", str(self.descriptors), *extra),
            env={**self.env, **(env or {})}, text=True, capture_output=True,
        )

    def beads(self):
        return json.loads(self.state_path.read_text())["beads"]

    def tracker_writes(self):
        return [line for line in self.gc_log.read_text().splitlines() if json.loads(line)[:2] == ["bd", "update"]]

    def mayor_mails(self):
        return [line for line in self.gc_log.read_text().splitlines() if "mail" in json.loads(line)]

    def assert_refused_and_nothing_written(self, *mentions, command="bd-publish", extra=()):
        before = self.state_path.read_bytes()
        proc = self.door(command, extra)
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        for mention in mentions:
            self.assertIn(mention, proc.stderr)
        self.assertEqual(before, self.state_path.read_bytes())
        self.assertEqual({"draft-1", "spec-1"}, set(self.beads()))
        self.assertEqual([], self.tracker_writes())
        self.assertEqual([], self.mayor_mails())
        return proc

    def refusal_lines(self, proc, ticket_id):
        return [line for line in proc.stderr.splitlines() if line.startswith(f"- {ticket_id} :")]

    def published(self):
        proc = self.door()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def convoy_state(self, convoy_id):
        return subprocess.run(
            (str(CONVOY_STATE), "show", convoy_id, "--repo", str(self.repo_root)),
            env=self.env, text=True, capture_output=True,
        )

    # --- AC1: kind declared, no default -------------------------------------

    def test_refuses_a_ticket_without_kind_and_applies_no_default(self):
        draft = self.conformant()
        del self.ticket(draft, "T2")["kind"]
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written("rien n'est écrit")
        self.assertTrue(any("genre absent" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)
        self.assertEqual([], self.refusal_lines(proc, "T3"))

    def test_refuses_a_ticket_with_an_unknown_kind(self):
        for unknown in ("prefactor", "prototype", "foundation"):
            with self.subTest(kind=unknown):
                draft = self.conformant()
                self.ticket(draft, "T2")["kind"] = unknown
                self.seed_draft(draft)

                proc = self.assert_refused_and_nothing_written()
                self.assertTrue(
                    any("genre inconnu" in line and unknown in line for line in self.refusal_lines(proc, "T2")),
                    proc.stderr,
                )

    # --- AC2: demonstration line --------------------------------------------

    def test_refuses_a_vertical_slice_without_demonstration_line(self):
        draft = self.conformant()
        del self.ticket(draft, "T2")["demonstration_line"]
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("ligne de démonstration" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)

    def test_refuses_a_repair_without_demonstration_line(self):
        draft = self.conformant()
        self.ticket(draft, "T3")["demonstration_line"] = "   "
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("ligne de démonstration" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    def test_refuses_a_demonstration_line_left_inside_the_ticket_text(self):
        # "Champ distinct": a line written in what_it_delivers, as the graphs
        # before this contract did, is not a demonstration line.
        draft = self.conformant()
        ticket = self.ticket(draft, "T2")
        ticket["what_it_delivers"] += "\n\nLigne de démonstration : " + ticket.pop("demonstration_line")
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("ligne de démonstration" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)

    # --- AC3: criteria ------------------------------------------------------

    def refused_criterion(self, criterion, *mentions):
        draft = self.conformant()
        self.ticket(draft, "T2")["acceptance_criteria"][1] = criterion
        self.seed_draft(draft)
        proc = self.assert_refused_and_nothing_written()
        lines = self.refusal_lines(proc, "T2")
        self.assertEqual(1, len(lines), proc.stderr)
        self.assertIn("critère 2", lines[0])
        for mention in mentions:
            self.assertIn(mention, lines[0])
        return lines[0]

    def test_refuses_un_test_montre_que(self):
        text = "Un test montre que la page d'accueil liste les éléments."
        line = self.refused_criterion(text, text, "nomme un test")
        self.assertIn("point d'entrée", line)

    def test_refuses_a_structured_criterion_that_names_a_test(self):
        self.refused_criterion(
            {"entry_point": "GET /", "observable": "un test montre que la région « liste » a trois lignes",
             "false_if": "une ligne manque"},
            "un test montre que la région « liste » a trois lignes", "nomme un test",
        )

    def test_refuses_a_criterion_whose_entry_point_is_a_test(self):
        self.refused_criterion(
            {"entry_point": "pytest tests/test_home.py", "observable": "sortie 0", "false_if": "sortie non nulle"},
            "nomme un test",
        )

    def test_refuses_a_criterion_that_names_a_file(self):
        self.refused_criterion(
            {"entry_point": "GET /", "observable": "la région « liste » est rendue par lib/home/render.py",
             "false_if": "la région est absente"},
            "lib/home/render.py", "nomme un fichier",
        )

    def test_refuses_a_criterion_that_names_an_internal_function(self):
        self.refused_criterion(
            {"entry_point": "GET /api/items", "observable": "load_items() rend trois éléments",
             "false_if": "load_items() rend une liste vide"},
            "load_items()", "nomme une fonction interne",
        )

    def test_accepts_a_plural_in_parentheses_and_a_path_as_entry_point(self):
        # "ligne(s)" is not a call, and a command or a route is a path.
        draft = self.conformant()
        self.ticket(draft, "T2")["acceptance_criteria"][1] = {
            "entry_point": "bin/fixture-product list --format json, puis GET /static/app.css",
            "observable": "la sortie liste la ou les ligne(s) du jeu de données, champ « label » compris",
            "false_if": "une ligne(s) manque, ou la route répond 404",
        }
        self.seed_draft(draft)
        self.published()

    def test_refuses_a_criterion_without_entry_point(self):
        self.refused_criterion(
            {"observable": "la région « liste » a trois lignes", "false_if": "une ligne manque"},
            "point d'entrée",
        )

    def test_refuses_a_criterion_without_observable(self):
        self.refused_criterion({"entry_point": "GET /", "false_if": "une ligne manque"}, "observable")

    def test_refuses_a_criterion_that_does_not_say_what_would_make_it_false(self):
        self.refused_criterion(
            {"entry_point": "GET /", "observable": "la région « liste » a trois lignes", "false_if": ""},
            "ce qui le rendrait faux",
        )

    def test_refuses_a_plain_sentence_even_when_it_names_nothing_internal(self):
        self.refused_criterion("La page d'accueil liste les éléments.", "point d'entrée", "observable")

    # --- AC4: what a prefactoring unblocks, what a repair restores ----------

    def test_refuses_a_prefactoring_that_does_not_name_the_slice_it_unblocks(self):
        draft = self.conformant()
        del self.ticket(draft, "T1")["unblocks"]
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("débloque" in line for line in self.refusal_lines(proc, "T1")), proc.stderr)

    def test_refuses_a_prefactoring_that_names_a_ticket_it_does_not_unblock(self):
        for target, why in (("T9", "inconnu"), ("T1", "lui-même"), ("T3", "T3")):
            with self.subTest(unblocks=target):
                draft = self.conformant()
                self.ticket(draft, "T1")["unblocks"] = target
                if target == "T3":  # T3 no longer waits for T1, even through T2
                    self.ticket(draft, "T3")["blocked_by"] = []
                self.seed_draft(draft)

                proc = self.assert_refused_and_nothing_written()
                self.assertTrue(
                    any("débloque" in line and why in line for line in self.refusal_lines(proc, "T1")), proc.stderr,
                )

    def test_refuses_a_prefactoring_with_a_demonstration_line(self):
        draft = self.conformant()
        self.ticket(draft, "T1")["demonstration_line"] = "La page d'accueil s'affiche plus vite."
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("comportement" in line for line in self.refusal_lines(proc, "T1")), proc.stderr)

    def test_refuses_a_repair_that_does_not_name_what_it_restores(self):
        cases = (
            None,
            "la liste",
            {"kind": "user_story", "ref": ""},
            {"kind": "nice_to_have", "ref": "une page plus jolie"},
        )
        for restores in cases:
            with self.subTest(restores=restores):
                draft = self.conformant()
                if restores is None:
                    del self.ticket(draft, "T3")["restores"]
                else:
                    self.ticket(draft, "T3")["restores"] = restores
                self.seed_draft(draft)

                proc = self.assert_refused_and_nothing_written()
                self.assertTrue(any("rétablit" in line for line in self.refusal_lines(proc, "T3")), proc.stderr)

    # --- a ticket carries only the fields the door knows --------------------

    def test_refuses_a_field_the_door_does_not_know(self):
        draft = self.conformant()
        self.ticket(draft, "T2")["review"] = "un relecteur indépendant relit le code"
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertTrue(any("review" in line for line in self.refusal_lines(proc, "T2")), proc.stderr)

    def test_refuses_a_copied_execution_contract(self):
        draft = self.conformant()
        draft["global_execution_contract"] = {"tdd": "Tests écrits d'abord et vus rouges."}
        self.seed_draft(draft)

        self.assert_refused_and_nothing_written("global_execution_contract")

    def test_refuses_a_contract_the_door_does_not_know(self):
        draft = self.conformant()
        draft["flow_contract"] = "new-flow/v2"
        self.seed_draft(draft)

        self.assert_refused_and_nothing_written("new-flow/v2", MARK)

    def test_refusal_lists_every_ticket_and_every_reason_at_once(self):
        draft = self.conformant()
        del self.ticket(draft, "T1")["unblocks"]
        del self.ticket(draft, "T2")["demonstration_line"]
        self.ticket(draft, "T2")["acceptance_criteria"][0] = "Un test montre que la liste s'affiche."
        del self.ticket(draft, "T3")["kind"]
        self.seed_draft(draft)

        proc = self.assert_refused_and_nothing_written()
        self.assertEqual(1, len(self.refusal_lines(proc, "T1")), proc.stderr)
        self.assertEqual(2, len(self.refusal_lines(proc, "T2")), proc.stderr)
        self.assertEqual(1, len(self.refusal_lines(proc, "T3")), proc.stderr)

    # --- demonstration line of the ticket: Cockpit V2, redeclared -----------

    def test_cockpit_v2_draft_redeclared_is_refused_ticket_by_ticket(self):
        draft = yaml.safe_load(COCKPIT_V2_DRAFT.read_text(encoding="utf-8"))
        ticket_ids = [str(t["id"]) for t in draft["tickets"]]
        self.assertEqual(25, len(ticket_ids))
        self.seed(COCKPIT_V2_DRAFT.read_text(encoding="utf-8") + f"\nflow_contract: {MARK}\n")

        proc = self.assert_refused_and_nothing_written("rien n'est écrit")
        for ticket_id in ticket_ids:
            self.assertTrue(self.refusal_lines(proc, ticket_id), f"{ticket_id} absent du refus")
        # T03 is a vertical_slice of that graph: no demonstration line, and
        # criteria of the "un test montre…" kind.
        t03 = "\n".join(self.refusal_lines(proc, "T03"))
        self.assertIn("ligne de démonstration", t03)
        self.assertIn("Un test montre que l'outil de roadmap", t03)
        self.assertIn("nomme un test", t03)
        # Its kinds were free text: "prefactor" and "prototype" are not kinds.
        self.assertIn("genre inconnu", "\n".join(self.refusal_lines(proc, "T01")))
        self.assertIn("genre inconnu", "\n".join(self.refusal_lines(proc, "T21")))

    def test_same_cockpit_v2_draft_without_the_declaration_is_still_published_as_before(self):
        draft = yaml.safe_load(COCKPIT_V2_DRAFT.read_text(encoding="utf-8"))
        draft["tickets"] = [t for t in draft["tickets"] if t.get("kind") != "prototype"]
        for ticket in draft["tickets"]:
            ticket["blocked_by"] = [b for b in ticket["blocked_by"] if b != "T21"]
        self.seed_draft(draft)

        result = self.published()
        self.assertEqual(len(draft["tickets"]) + 1, len(result["ids"]))
        self.assertEqual([], self.tracker_writes())

    # --- AC5: a conformant draft is published, marked, and re-read by code --

    def test_conformant_draft_is_published_with_mark_kind_and_demonstration_line(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

        result = self.published()
        self.assertEqual({"_convoy", "T1", "T2", "T3", "T4"}, set(result["ids"]))
        self.assertEqual(MARK, result["flow_contract"])

        shown = self.convoy_state(result["ids"]["_convoy"])
        self.assertEqual(0, shown.returncode, shown.stdout + shown.stderr)
        state = json.loads(shown.stdout)
        self.assertFalse(state["unruled"])
        self.assertEqual(MARK, state["convoy"]["mark"])
        by_id = {t["id"]: t for t in state["tickets"]}
        self.assertEqual({result["ids"][key] for key in ("T1", "T2", "T3", "T4")}, set(by_id))
        t1, t2, t3 = (by_id[result["ids"][key]] for key in ("T1", "T2", "T3"))
        self.assertEqual([MARK] * 3, [t["mark"] for t in (t1, t2, t3)])
        self.assertEqual(["prefactoring", "vertical_slice", "repair"], [t["kind"] for t in (t1, t2, t3)])
        self.assertIsNone(t1["demonstration_line"])
        self.assertEqual(
            "Sur le produit lancé avec le jeu de données « contenu », la page d'accueil (GET /) affiche "
            "les trois éléments « Alpha », « Bêta » et « Gamma ».",
            t2["demonstration_line"],
        )
        self.assertEqual(
            "Sur le produit lancé, GET /api/items rend pour chaque élément un champ « label » non vide.",
            t3["demonstration_line"],
        )

    def test_published_ticket_text_carries_no_copied_execution_contract(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

        result = self.published()
        beads = self.beads()
        for key in ("T1", "T2", "T3"):
            description = beads[result["ids"][key]]["description"]
            self.assertNotIn("execution contract", description.lower())
            self.assertIn("## Acceptance criteria", description)
        t2 = beads[result["ids"]["T2"]]["description"]
        self.assertIn("la région « liste » affiche le libellé « Aucun élément »", t2)
        self.assertIn("la région est vide, ou la page répond par une erreur", t2)
        self.assertIn("affiche les trois éléments « Alpha », « Bêta » et « Gamma »", t2)
        self.assertIn("user story 2", beads[result["ids"]["T3"]]["description"])
        self.assertIn("T2", beads[result["ids"]["T1"]]["description"])

    def test_published_new_flow_convoy_is_not_handed_to_the_mayor_for_dispatch(self):
        # Spec §0 rule 3: code, not the Mayor, starts the tickets of a marked convoy.
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

        result = self.published()
        self.assertEqual([], self.mayor_mails())
        self.assertIsNone(result["mayor_notified"])

    def test_publishing_again_changes_nothing(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))
        first = self.published()
        shown_before = self.convoy_state(first["ids"]["_convoy"]).stdout
        state_before = self.state_path.read_bytes()

        second = self.published()
        self.assertEqual(first["ids"], second["ids"])
        self.assertEqual(state_before, self.state_path.read_bytes())
        self.assertEqual(shown_before, self.convoy_state(first["ids"]["_convoy"]).stdout)

    def test_publication_whose_marking_fails_says_so_and_is_completed_by_a_rerun(self):
        self.seed(CONFORMANT_DRAFT.read_text(encoding="utf-8"))

        proc = self.door(env={"TICKET_GRAPH_GC_BD_UPDATE_FAIL": "1"})
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("marque du nouveau flux", proc.stderr)
        self.assertIn("relancer", proc.stderr)
        self.assertEqual([], self.mayor_mails())

        result = self.published()
        shown = self.convoy_state(result["ids"]["_convoy"])
        self.assertEqual(0, shown.returncode, shown.stdout + shown.stderr)
        self.assertEqual(MARK, json.loads(shown.stdout)["convoy"]["mark"])

    # --- AC6: a draft that does not declare the contract --------------------

    LEGACY_DRAFT = (
        "global_execution_contract:\n"
        "  models: none\n"
        "  review: Un test montre que le relecteur a relu.\n"
        "\n"
        "tickets:\n"
        "  - id: T1\n"
        "    title: First\n"
        "    blocked_by: []\n"
        "    target_rigs: [fixture_city]\n"
        "    what_it_delivers: does a thing\n"
        "    acceptance_criteria: [Un test montre que la chose est faite, La CI est verte]\n"
        "    scope:\n"
        "      paths: [bin/foo.py]\n"
        "  - id: T2\n"
        "    kind: prefactor\n"
        "    title: Second\n"
        "    blocked_by: [T1]\n"
        "    target_rigs: [fixture_city]\n"
        "    what_it_delivers: does another thing\n"
        "    acceptance_criteria: [does the other thing]\n"
    )

    def test_undeclared_draft_is_published_exactly_as_before_this_ticket(self):
        # The golden file was written by the door as it was before T05
        # (commit 15374c7), on this same seed.
        golden = json.loads(LEGACY_GOLDEN.read_text(encoding="utf-8"))
        self.seed(self.LEGACY_DRAFT, spec_text=LEGACY_SPEC)

        result = self.published()
        result.pop("mayor_city")
        self.assertEqual(golden["result"], result)
        self.assertEqual(golden["beads"], self.beads())
        self.assertEqual(1, len(self.mayor_mails()))
        self.assertEqual([], self.tracker_writes())

    def test_undeclared_draft_is_published_without_mark(self):
        self.seed(self.LEGACY_DRAFT)

        result = self.published()
        for bead in self.beads().values():
            self.assertEqual([], [key for key in bead["metadata"] if key.startswith("gc.flow.")])
        shown = self.convoy_state(result["ids"]["_convoy"])
        self.assertEqual(EXIT_NOT_NEW_FLOW, shown.returncode, shown.stdout)
        self.assertIn("pas un convoi du nouveau flux", json.loads(shown.stdout)["message"])


if __name__ == "__main__":
    unittest.main()
