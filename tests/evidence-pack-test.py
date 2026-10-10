#!/usr/bin/env python3
"""bin/evidence-pack on a fake tracker state (T27, af-r43we4; Spec af-wf4w5r
§10, §9 point 6, Testing Decisions seam 2): one test per pass and per
refusal, each refusal re-reading the tracker, the evidence store and the
folder of the packs to prove nothing was written. Only command lines are
exercised, and the page they write is read as a browser is given it.

The convoy is the delivered one of tests/spec-end-test.py, evaluated as in
tests/outcome-evaluation-test.py: a copy of the Delivery Fixture City in a
throwaway repository with its own remote, its tickets closed by the real
bin/ticket-end, the mechanical verdicts rendered by the real bin/spec-end,
its assembled product launched by the real bin/project-launch and every
piece captured and sealed by the real bin/evidence-capture. No agent runs."""

import copy
import hashlib
import html
import importlib.machinery
import importlib.util
import json
import re
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "evidence-pack"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


outcome = load("outcome-evaluation-test.py")
gate = outcome.gate
CONVOY, SPEC, SLICE, SCREEN = gate.CONVOY, gate.SPEC, gate.SLICE, gate.SCREEN
PLAIN_CONVOY, INTEGRATION = gate.PLAIN_CONVOY, gate.INTEGRATION
EXIT_REFUSED, EXIT_NOT_NEW_FLOW = 1, 4
NAMES = (*outcome.NAMES, "evidence_pack")
PACK = len(NAMES)

FINDING, FINDING_ID = outcome.FINDING, outcome.FINDING_ID
EXPLORATION = "Une adresse inconnue répond 404 en JSON, sans page d'erreur."
SEEN_DEVIATION = "Le titre de l'état « content » est plus serré que sur le prototype."
NOT_DONE = gate.NOT_DONE
REPAIR = "fx-r1"
OVERRIDE_WORDS = "Je passe outre : ce constat ne vaut pas un tour de plus."
OUTSIDE = "docs/hors-perimetre.md"
EXCEPTION = "La Spec ne dit pas si la liste se trie par date."
MODEL = "claude-opus-5-5"
RUBRICS = (
    "En-tête", "Ce qui demande les yeux de Benjamin", "Ce qui n'a PAS été vérifié", "Par user story", "Par ticket",
    "Éléments suivis", "Hors graphe initial", "Relevés", "Preuves TDD et constats de revue")
SETTINGS = {
    "contract": "agent-factory-evidence-pack/v1",
    "baseline_without_mechanism": [{"criterion": "Secrets", "detail": "Aucun contrôle ne cherche un secret dans le diff."}],
    "known_limits": ["L'agent choisit ce qu'il capture."],
}


class EvidencePackTest(outcome.Harness):
    def setUp(self):
        super().setUp()
        self.packs = self.tmp / "packs"
        self.env["EVIDENCE_PACK_DIR"] = str(self.packs)

    def seed(self):
        base = super().seed()
        # The digest of the Spec the publication door wrote on the convoy.
        text = json.loads(self.tracker.read_text())["beads"][SPEC]["description"]
        self.edit(CONVOY, **{"gc.spec_digest": "sha256:" + hashlib.sha256(text.encode()).hexdigest()})
        return base

    # --- harness ------------------------------------------------------------

    def ready(self):
        """The fixture whose conditions of the end of the Spec are green
        before the pack: delivered, its mechanical verdicts rendered, its
        assembled product evaluated -- a finding kept as a proposal, a remark
        of exploration, a fidelity deviation seen, an Evaluator of the
        supplier of an author -- and its end code review favorable. Returns
        the commit of the gate."""
        def build():
            self.verified()
            self.state("set-model", CONVOY, SLICE, "--role", "author", "--agent", "delivery-author",
                       "--provider", "p-claude", "--model", MODEL)
            self.providers(evaluator=["p-claude-ro"])
            self.declare(SLICE, out_of_ticket=[FINDING])
            self.evaluator("silent")
            self.assertEqual("launched", self.settle()["action"])
            status, brief = self.tool("brief", "--profile", self.profile, env=self.session)
            self.assertEqual(0, status, brief)
            self.classify(FINDING_ID, "--as", "proposal")
            piece = self.observe(brief, "outcome.exploration", path="/inconnu")
            self.record(self.result(brief, exploration=[{"text": EXPLORATION, "evidence": piece}],
                                    fidelity_deviations=[{"text": SEEN_DEVIATION}]))
            self.settle()
            # The code review of the interface ticket ran on the model of its author.
            review = json.loads(self.metadata(SCREEN)["gc.flow.code_review"])
            review["rounds"][0]["models"] = {"author": MODEL, "reviewer": MODEL, "same_model": True}
            self.edit(SCREEN, **{"gc.flow.code_review": json.dumps(review)})
            self.reviewed()
            return self.show()["convoy"]["spec_end"]["commit"]
        return self.stage("pack-ready", build)

    def pack(self, command, *args, convoy=CONVOY, env=None):
        proc = self.run_cmd(TOOL, command, convoy, "--repo", self.repo, *args, env=env)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def generate(self, expect=0):
        status, answer = self.pack("generate")
        self.assertEqual(expect, status, answer)
        return answer

    def packed(self):
        """The ready fixture, its pack generated by the real command: the
        decor of the cases that judge what follows a generation (a check, the
        gate), built once and restored afterwards like `ready`. A case that
        judges the generation itself calls `generate`. Returns the commit of
        the gate and the answer of the generation."""
        def build():
            commit = self.ready()
            return commit, self.generate()
        return copy.deepcopy(self.stage("pack-generated", build))

    def packed_red(self):
        """The verified fixture, its pack generated while its Outcome
        Evaluation and its end code review are not made: the same decor, for
        the cases that judge what the gate says of such a pack. Returns the
        commit of the gate and the answer of the generation."""
        def build():
            commit = self.verified()
            return commit, self.generate()
        return copy.deepcopy(self.stage("pack-generated-red", build))

    def page(self, answer):
        return Path(answer["page"]).read_text(encoding="utf-8")

    def rubric(self, page, number):
        """One rubric of the page, as the Spec numbers it."""
        match = re.search(rf'<section id="rubrique-{number}">(.*?)</section>', page, re.S)
        self.assertIsNotNone(match, f"rubrique {number} absente")
        return match.group(1)

    def pack_files(self):
        return {str(path.relative_to(self.packs)): path.read_bytes()
                for path in sorted(self.packs.rglob("*")) if path.is_file()} if self.packs.is_dir() else {}

    def everything(self):
        return (self.snapshot(), self.pack_files())

    def conditions(self, answer):
        return [(entry["number"], entry["name"], entry["verdict"]) for entry in answer["conditions"]]

    # --- AC1: a static page, its header, the rubrics 1 to 9 in order --------------------------------

    def test_generation_on_a_conforming_convoy_writes_a_static_page_with_its_header_and_the_nine_rubrics_in_order(self):
        commit = self.ready()

        answer = self.generate()

        self.assertEqual((True, CONVOY, SPEC, INTEGRATION, commit, True),
                         (answer["ok"], answer["convoy"], answer["spec"], answer["branch"], answer["commit"],
                          answer["conforming"]))
        page_file = Path(answer["page"])
        self.assertEqual((self.packs, "index.html"), (page_file.parents[3], page_file.name))
        page = page_file.read_text(encoding="utf-8")
        self.assertEqual("sha256:" + hashlib.sha256(page_file.read_bytes()).hexdigest(), answer["digest"])
        # A static page: no script, and nothing fetched from elsewhere than its own folder.
        self.assertTrue(page.startswith("<!DOCTYPE html>"))
        self.assertNotIn("<script", page)
        for source in re.findall(r'(?:src|href)="([^"#][^"]*)"', page):
            self.assertRegex(source, r"^pieces/[0-9a-f]{64}\.(json|png)$")
            self.assertTrue((page_file.parent / source).is_file(), source)
        # The header: the Spec and its digest, the branch, the commit, the verdict of each condition.
        header = self.rubric(page, 1)
        for expected in (SPEC, self.show()["convoy"]["spec_digest"], INTEGRATION, commit):
            self.assertIn(expected, header)
        status, checked = self.gate("check", "--before-pack")
        self.assertEqual(0, status, checked)
        self.assertEqual(list(outcome.NAMES), [entry["name"] for entry in checked["conditions"]])
        for entry in checked["conditions"]:
            self.assertRegex(header, rf'data-condition="{entry["number"]}" data-verdict="pass"')
        self.assertNotIn("non conforme", header.lower())
        # The rubrics 1 to 9 of the Spec §10, in order.
        self.assertEqual([(str(number), f"{number}. {title}") for number, title in enumerate(RUBRICS, start=1)],
                         [(number, html.unescape(title)) for number, title in
                          re.findall(r'<section id="rubrique-(\d+)">\s*<h2>([^<]*)</h2>', page)])
        # Per user story and per ticket: the state and the proof.
        stories = self.rubric(page, 4)
        for story in self.outcome()["rounds"][-1]["stories"]:
            self.assertIn(f'data-story="{story["number"]}" data-state="observed"', stories)
            self.assertIn(story["evidence"], stories)
        tickets = self.rubric(page, 5)
        for ticket in (SLICE, SCREEN):
            shown = self.shown(ticket)
            self.assertIn(f'data-ticket="{ticket}"', tickets)
            self.assertIn(html.escape(shown["demonstration_line"]), tickets)
            self.assertIn("evaluation.seen", tickets)
        # The pack is recorded on the convoy, tied to that commit.
        recorded = self.show()["convoy"]["evidence_pack"]
        self.assertEqual((commit, answer["digest"], str(page_file.parent), True, 0),
                         (recorded["commit"], recorded["digest"], recorded["path"], recorded["conforming"],
                          recorded["inadmissible"]))

    # --- AC2: two generations on the same state are the same bytes -----------------------------------

    def test_two_generations_on_the_same_state_write_two_identical_pages(self):
        self.ready()
        first = self.generate()
        files = self.pack_files()
        before = self.snapshot()
        shutil.rmtree(self.packs)

        second = self.generate()

        self.assertEqual(files, self.pack_files())
        self.assertEqual((first["digest"], first["page"]), (second["digest"], second["page"]))
        self.assertTrue(files[str(Path(second["page"]).relative_to(self.packs))].startswith(b"<!DOCTYPE html>"))
        # The same pack again writes nothing in the tracker.
        self.assertEqual(before, self.snapshot())

    def test_generation_takes_no_text_from_its_caller(self):
        self.ready()
        before = self.everything()

        for option in ("--summary", "--note", "--title"):
            proc = self.run_cmd(TOOL, "generate", CONVOY, "--repo", self.repo, option, "Tout est conforme.")
            self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)

        self.assertEqual(before, self.everything())

    # --- AC3: « Ce qui n'a PAS été vérifié », always there; refused when it cannot be filled -------------

    def test_not_verified_rubric_lists_the_states_not_prototyped_the_baseline_without_mechanism_and_the_known_limits(self):
        self.ready()
        (self.root / "config" / "evidence-pack.json").write_text(json.dumps(SETTINGS, ensure_ascii=False))

        rubric = self.rubric(self.page(self.generate()), 3)

        for state in ("erreur", "contenu long", "écran étroit"):
            self.assertIn(f'data-screen="accueil" data-state="{state}"', rubric)
        for state in ("vide", "contenu"):
            self.assertNotIn(f'data-state="{state}"', rubric)
        self.assertIn("Secrets", rubric)
        self.assertIn("Aucun contrôle ne cherche un secret dans le diff.", rubric)
        self.assertIn(html.escape(SETTINGS["known_limits"][0]), rubric)

    def test_factory_settings_fill_the_not_verified_rubric_when_the_city_sets_none(self):
        self.ready()

        rubric = self.rubric(self.page(self.generate()), 3)

        declared = json.loads((ROOT / "config" / "evidence-pack.json").read_text())
        self.assertTrue(declared["baseline_without_mechanism"] and declared["known_limits"])
        for entry in declared["baseline_without_mechanism"]:
            self.assertIn(entry["criterion"], rubric)

    def test_generation_is_refused_when_the_not_verified_rubric_cannot_be_filled(self):
        self.ready()
        for settings, mention in (
                ({**SETTINGS, "baseline_without_mechanism": []}, "baseline_without_mechanism"),
                ({**SETTINGS, "known_limits": []}, "known_limits"),
                ("pas du JSON", "evidence-pack.json")):
            with self.subTest(mention=mention):
                (self.root / "config" / "evidence-pack.json").write_text(
                    settings if isinstance(settings, str) else json.dumps(settings))
                before = self.everything()

                answer = self.generate(expect=EXIT_REFUSED)

                self.assertFalse(answer["ok"])
                self.assertIn("Ce qui n'a PAS été vérifié", answer["error"])
                self.assertIn(mention, answer["error"])
                self.assertEqual(before, self.everything())
                self.assertIsNone(self.show()["convoy"]["evidence_pack"])

    def test_generation_is_refused_when_the_spec_names_a_prototype_without_the_inventory_of_its_states(self):
        self.ready()
        state = json.loads(self.tracker.read_text())
        text = state["beads"][SPEC]["description"]
        state["beads"][SPEC]["description"] = text[:text.index("### Écran")] + text[text.index("## Implementation Decisions"):]
        self.tracker.write_text(json.dumps(state))
        before = self.everything()

        answer = self.generate(expect=EXIT_REFUSED)

        self.assertIn("Ce qui n'a PAS été vérifié", answer["error"])
        self.assertIn("inventaire des états", answer["error"])
        self.assertEqual(before, self.everything())

    # --- AC4: « Ce qui demande les yeux de Benjamin » ------------------------------------------------------

    def test_benjamins_eyes_rubric_holds_each_proposal_each_fidelity_deviation_with_its_captures_and_each_mention(self):
        self.ready()

        answer = self.generate()

        rubric = self.rubric(self.page(answer), 2)
        folder = Path(answer["path"])
        # Each proposal.
        self.assertIn(f'data-proposal="{FINDING_ID}"', rubric)
        self.assertIn(html.escape(FINDING), rubric)
        # Each fidelity deviation the Evaluator of the end listed.
        self.assertIn(html.escape(SEEN_DEVIATION), rubric)
        # Each prototyped state, at each rendering: the two captures side by side and the image of their difference.
        store = self.store / SPEC / SCREEN
        for state in ("empty", "content"):
            for viewport in ("desktop", "narrow"):
                record = json.loads((store / f"fidelity.{state}.{viewport}.json").read_text())
                block = re.search(rf'<figure data-comparison="fidelity\.{state}\.{viewport}"(.*?)</figure>', rubric, re.S)
                self.assertIsNotNone(block, f"{state}/{viewport}")
                for digest in (record["image_digest"], record["difference_digest"]):
                    name = f"pieces/{digest.removeprefix('sha256:')}.png"
                    self.assertIn(f'src="{name}"', block.group(1))
                    self.assertEqual(digest, "sha256:" + hashlib.sha256((folder / name).read_bytes()).hexdigest())
                self.assertIn(record["commit"], block.group(1))
        # A remark of the free exploration, with its piece.
        self.assertIn(html.escape(EXPLORATION), rubric)
        self.assertIn("outcome.exploration", rubric)
        # Each mention « même fournisseur ou même modèle que l'auteur ».
        self.assertIn(f'data-mention="same_model" data-ticket="{SCREEN}"', rubric)
        self.assertIn('data-mention="same_provider" data-check="outcome_evaluation"', rubric)
        self.assertIn("anthropic", rubric)
        # An independence nobody recorded is said too, apart.
        self.assertIn(f'data-mention="unknown" data-ticket="{SLICE}"', rubric)

    # --- AC5: contradictions, repairs, Planning Exceptions, overrides, files outside the Declared Scope ------

    def rich(self):
        """A convoy that is not conforming, with something in every record
        the pack files: a « non fait » Benjamin accepted through a Planning
        Exception, an open Planning Exception, a story the assembled product
        does not show although its ticket observed it, the repair code
        published for it, an override of the operator, and a file touched
        outside the Declared Scope."""
        def build():
            self.verified()
            self.declare(SLICE, not_done=[NOT_DONE])
            self.assertEqual(EXIT_REFUSED, self.run_gate()[0])
            self.door("repondre", SLICE, self.shown(SLICE)["planning_exceptions"][-1]["accept_option"])
            self.unserved()
            self.evaluator(outcome.UNSERVED_PLAN)
            self.settle()
            # The repair of story 3, published since by the patch door and named on the story.
            state = json.loads(self.tracker.read_text())
            state["beads"][REPAIR] = {
                "title": "Rétablir la user story 3", "status": "open", "issue_type": "task",
                "description": f"## Acceptance criteria\n\n- [ ] {gate.CRITERION}\n\n## Target rigs\n\nfx-rig",
                "metadata": {"gc.ticket_kind": "repair"}}
            state["beads"][CONVOY]["tracks"].append(REPAIR)
            self.tracker.write_text(json.dumps(state))
            self.state("mark", CONVOY, "--demonstration-line", f"{REPAIR}=La page de version est servie")
            self.state("set-outcome-repair", CONVOY, "--repair", REPAIR, "--story", "3")
            self.state("raise-planning-exception", CONVOY, SCREEN, "--kind", "semantic", "--summary", EXCEPTION)
            review = self.shown(SCREEN)["code_review"]["rounds"][0]
            self.edit(SCREEN, **{"gc.flow.overrides": json.dumps({"entries": [{
                "finding": "F1.1", "approver": "benjamin", "words": OVERRIDE_WORDS, "commit": review["commit"],
                "at": "2026-10-08T10:00:00Z"}]})})
            handoff = json.loads(self.metadata(SLICE)["gc.flow.handoff"])
            handoff["records"].update(declared_scope=["tests/"], files_outside_declared_scope=[OUTSIDE])
            self.edit(SLICE, **{"gc.flow.handoff": json.dumps(handoff), "gc.scope_paths": "tests/"})
        return self.stage("pack-rich", build)

    def test_contradictions_repairs_planning_exceptions_overrides_and_files_outside_the_scope_are_in_their_rubrics(self):
        self.rich()
        self.assertEqual([3], [entry["story"] for entry in self.outcome()["contradictions"]])

        page = self.page(self.generate())

        tracked, outside_graph, records = (self.rubric(page, number) for number in (6, 7, 8))
        # 6. Tracked elements: the « non fait », with its final state.
        self.assertIn(html.escape(NOT_DONE), tracked)
        self.assertIn("accepté par Benjamin", tracked)
        # 7. Outside the initial graph: the repair created, the Planning Exceptions and the answer, the override.
        self.assertIn(f'data-repair="{REPAIR}"', outside_graph)
        self.assertIn("user story 3", outside_graph)
        self.assertIn(EXCEPTION, outside_graph)
        self.assertEqual(2, outside_graph.count("data-planning-exception="))
        self.assertIn('data-state="resolved"', outside_graph)
        self.assertIn('data-state="open"', outside_graph)
        self.assertIn(f'data-override="{SCREEN}:F1.1"', outside_graph)
        self.assertIn(OVERRIDE_WORDS, outside_graph)
        # 8. Records: the file outside the Declared Scope, the contradiction with the proof of the ticket.
        self.assertIn(f'data-outside-scope="{SLICE}"', records)
        self.assertIn(OUTSIDE, records)
        self.assertIn(f'data-contradiction="3"', records)
        self.assertIn(SLICE, re.search(r'data-contradiction="3"(.*?)</li>', records, re.S).group(1))
        # Each record in its own rubric only.
        for rubric in (tracked, outside_graph):
            self.assertNotIn(OUTSIDE, rubric)
            self.assertNotIn("data-contradiction", rubric)
        self.assertNotIn(OVERRIDE_WORDS, records)

    # --- AC6: a red condition: the page is written, « non conforme » in its header -------------------------

    def test_generation_with_a_red_condition_writes_the_page_with_non_conforme_and_the_verdict_of_each_condition(self):
        commit = self.verified()
        status, checked = self.gate("check", "--before-pack")
        self.assertEqual(EXIT_REFUSED, status, checked)

        answer = self.generate()

        self.assertEqual((True, False, commit), (answer["ok"], answer["conforming"], answer["commit"]))
        header = self.rubric(self.page(answer), 1)
        self.assertIn("non conforme", header.lower())
        for entry in checked["conditions"]:
            self.assertRegex(header, rf'data-condition="{entry["number"]}" data-verdict="{entry["verdict"]}"')
        self.assertEqual(["pass", "pass", "pass", "fail", "not_run", "fail"],
                         re.findall(r'data-condition="\d" data-verdict="(\w+)"', header))
        self.assertFalse(self.show()["convoy"]["evidence_pack"]["conforming"])
        # Still the nine rubrics, and the one that is mandatory.
        self.assertEqual(9, len(re.findall(r'<section id="rubrique-\d">', self.page(answer))))

    def test_generation_on_a_convoy_whose_rounds_of_the_end_are_stopped_says_the_stop_among_its_records(self):
        commit = self.verified()
        detail = "2 tour(s) de réparation consommé(s) (borne : 2), et la fin de Spec est encore refusée"
        self.edit(CONVOY, **{"gc.flow.end_stop": json.dumps({
            "reason": "end_rounds_exhausted", "detail": detail, "commit": commit, "source": "outcome_evaluation",
            "rounds": 2, "at": "2026-10-08T10:00:00Z"})})

        first = self.generate()

        self.assertFalse(first["conforming"])
        records = self.rubric(self.page(first), 8)
        for said in ("Tours de réparation de fin arrêtés", "tours de réparation épuisés", html.escape(detail), commit,
                     "2026-10-08T10:00:00Z"):
            self.assertIn(said, records)
        # The « non conforme » request is written once the page exists: it does not change the page.
        self.state("end-stop-raised", CONVOY, "--bead", CONVOY)
        self.assertIn("request", self.show()["convoy"]["end_stop"])
        self.assertEqual(first["digest"], self.generate()["digest"])

    def test_generation_on_a_convoy_whose_rounds_are_not_stopped_says_no_stop(self):
        self.verified()

        records = self.rubric(self.page(self.generate()), 8)

        self.assertNotIn("arrêtés", records)

    def test_generation_on_a_convoy_whose_tickets_are_not_all_closed_writes_a_non_conforming_page(self):
        self.one_closed()

        answer = self.generate()

        self.assertFalse(answer["conforming"])
        page = self.page(answer)
        self.assertIn('data-condition="1" data-verdict="fail"', self.rubric(page, 1))
        self.assertIn(f'data-ticket="{SCREEN}"', self.rubric(page, 5))

    # --- AC7: one commit more outdates the pack; the gate refuses without a complete pack that holds ---------

    def test_check_after_one_commit_more_on_the_branch_says_the_pack_is_outdated(self):
        commit, generated = self.packed()
        status, held = self.pack("check")
        self.assertEqual((0, True, "à jour", commit), (status, held["ok"], held["state"], held["commit"]))
        added = self.note(INTEGRATION)
        before = self.everything()

        status, answer = self.pack("check")

        self.assertEqual((EXIT_REFUSED, False, "périmé"), (status, answer["ok"], answer["state"]))
        self.assertEqual((commit, added, generated["digest"]), (answer["commit"], answer["tip"], answer["digest"]))
        self.assertIn("périmé", answer["error"])
        self.assertEqual(before, self.everything())

    def test_check_before_any_generation_says_no_pack_was_generated(self):
        self.ready()
        before = self.everything()

        status, answer = self.pack("check")

        self.assertEqual((EXIT_REFUSED, "absent"), (status, answer["state"]))
        self.assertEqual(before, self.everything())

    def test_check_of_a_pack_whose_recorded_state_changed_since_says_it_is_outdated(self):
        self.packed()
        # No commit more: a record of the tracker the page shows changed.
        self.state("set-model", CONVOY, SCREEN, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", MODEL)

        status, answer = self.pack("check")

        self.assertEqual((EXIT_REFUSED, "périmé"), (status, answer["state"]))
        self.assertIn("état enregistré", answer["error"])

    def test_check_of_a_page_or_of_a_capture_rewritten_by_hand_refuses_it(self):
        _, answer = self.packed()
        page, image = Path(answer["page"]), sorted(Path(answer["path"]).glob("pieces/*.png"))[0]
        for target in (page, image):
            with self.subTest(target=target.name):
                kept = target.read_bytes()
                target.write_bytes(kept + b"\n<p>Tout est conforme.</p>")

                status, checked = self.pack("check")

                self.assertEqual((EXIT_REFUSED, "altéré"), (status, checked["state"]))
                target.write_bytes(kept)
        self.assertEqual(0, self.pack("check")[0])

    def test_gate_refuses_while_no_pack_is_generated_and_names_its_last_condition(self):
        commit = self.ready()
        before = self.everything()

        status, answer = self.run_gate()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual([(number, name, "fail" if name == "evidence_pack" else "pass")
                          for number, name in enumerate(NAMES, start=1)], self.conditions(answer))
        self.assertEqual(([PACK], commit), (answer["missing"], answer["commit"]))
        self.assertIn(f"condition {PACK}", answer["error"])
        self.assertIn("Evidence Pack", answer["error"])
        self.assertEqual(before, self.everything())
        self.assertEqual((EXIT_REFUSED, [PACK]), (self.check()[0], self.check()[1]["missing"]))

    def test_gate_passes_its_last_condition_on_the_pack_generated_at_the_commit_of_its_verdicts(self):
        commit, _ = self.packed()

        status, answer = self.run_gate()

        self.assertEqual(0, status, answer)
        self.assertEqual([(number, name, "pass") for number, name in enumerate(NAMES, start=1)], self.conditions(answer))
        self.assertEqual((commit, []), (answer["commit"], answer["missing"]))
        self.assertIn(self.show()["convoy"]["evidence_pack"]["digest"], answer["conditions"][-1]["detail"])
        self.assertEqual(0, self.check()[0])

    def test_gate_refuses_a_pack_generated_while_a_condition_was_red(self):
        commit, _ = self.packed_red()
        # Evaluated and reviewed since: the six conditions before the pack are green, on the commit of the pack.
        self.settle()
        self.reviewed()
        self.assertEqual(commit, self.show()["convoy"]["evidence_pack"]["commit"])

        status, answer = self.run_gate()

        self.assertEqual((EXIT_REFUSED, [PACK]), (status, answer["missing"]))
        self.assertIn("périmé", answer["conditions"][-1]["detail"])
        self.generate()
        self.assertEqual(0, self.run_gate()[0])

    def test_gate_refuses_after_one_commit_more_whatever_the_pack(self):
        self.packed()
        self.assertEqual(0, self.run_gate()[0])
        self.note(INTEGRATION)

        status, answer = self.check()

        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertEqual({"stale"}, {entry["verdict"] for entry in answer["conditions"]})
        self.assertEqual(len(NAMES), len(answer["conditions"]))

    # --- Delivered: every condition of the end green on one commit, complete pack included (T26) ----------------

    def outcome_delivered(self):
        return self.show()["convoy"]["delivered"]

    def refused_delivered(self, commit, digest):
        """`record-delivered` called directly: refused, and nothing written."""
        before = self.everything()
        proc = self.run_cmd(gate.STATE_TOOL, "record-delivered", CONVOY, "--commit", commit, "--pack-digest", digest)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, self.everything())
        return json.loads(proc.stdout)["error"]

    def test_gate_records_the_delivered_outcome_once_its_seven_conditions_are_green_on_one_commit(self):
        commit, pack = self.packed()
        self.assertIsNone(self.outcome_delivered())

        status, answer = self.run_gate()

        self.assertEqual((0, True), (status, answer["delivered"]))
        delivered = self.outcome_delivered()
        self.assertEqual((commit, pack["digest"], answer["protected"]["commit"]),
                         (delivered["commit"], delivered["pack"], delivered["protected"]))
        # Recording it outdates neither the pack nor the verdicts: the gate still passes, and says Delivered.
        status, checked = self.check()
        self.assertEqual((0, True, None), (status, checked["delivered"], checked["end_stop"]))
        # The gate again on the same tip writes nothing.
        before = self.everything()
        self.assertEqual((0, True), (self.run_gate()[0], self.run_gate()[1]["delivered"]))
        self.assertEqual(before, self.everything())
        self.assertFalse(self.show()["convoy"]["unruled"])

    def test_gate_never_records_delivered_while_no_pack_is_generated(self):
        commit = self.ready()

        status, answer = self.run_gate()

        self.assertEqual((EXIT_REFUSED, False, None), (status, answer["delivered"], self.outcome_delivered()))
        self.assertFalse(self.check()[1]["delivered"])
        self.assertIn("Evidence Pack", self.refused_delivered(commit, "sha256:" + "ab" * 32))

    def test_gate_never_records_delivered_on_a_pack_generated_while_a_condition_was_red(self):
        commit, stale = self.packed_red()
        self.settle()
        self.reviewed()

        status, answer = self.run_gate()

        self.assertEqual((EXIT_REFUSED, False, None), (status, answer["delivered"], self.outcome_delivered()))
        self.assertIn("Evidence Pack", self.refused_delivered(commit, stale["digest"]))

    def test_gate_never_records_delivered_while_a_condition_before_the_pack_is_red(self):
        commit, pack = self.packed_red()

        status, answer = self.run_gate()

        self.assertEqual((EXIT_REFUSED, False, None), (status, answer["delivered"], self.outcome_delivered()))
        error = self.refused_delivered(commit, pack["digest"])
        for named in ("Outcome Evaluation", "revue de code de fin", "Evidence Pack"):
            self.assertIn(named, error)

    def test_delivered_does_not_stand_for_one_commit_more(self):
        commit, pack = self.packed()
        self.assertEqual(0, self.run_gate()[0])
        tip = self.note(INTEGRATION)

        status, checked = self.check()

        # The record is the one of the commit before: the gate does not say Delivered of this tip.
        self.assertEqual((EXIT_REFUSED, False, commit), (status, checked["delivered"], self.outcome_delivered()["commit"]))
        self.assertIn("ne sont pas enregistrés à ce commit", self.refused_delivered(tip, pack["digest"]))
        # The mechanical verdicts replayed on the new tip withdraw it, in the write that records them.
        status, answer = self.run_gate()
        self.assertEqual((EXIT_REFUSED, False, tip), (status, answer["delivered"], answer["commit"]))
        self.assertIsNone(self.outcome_delivered())

    # --- a piece the store no longer holds, a convoy without the mark ------------------------------------------

    def test_piece_that_is_no_longer_the_sealed_one_is_said_and_makes_the_pack_incomplete(self):
        self.ready()
        record = self.store / SPEC / SLICE / "demonstration.json"
        forged = json.loads(record.read_text())
        forged["output"] = "Tout est conforme."
        record.write_text(json.dumps(forged))

        answer = self.generate()

        self.assertEqual([f"{SLICE}/demonstration"], [entry["piece"] for entry in answer["inadmissible"]])
        page = self.page(answer)
        self.assertNotIn("Tout est conforme.", page)
        self.assertIn(f'data-inadmissible="{SLICE}/demonstration"', self.rubric(page, 3))
        self.assertEqual(1, self.show()["convoy"]["evidence_pack"]["inadmissible"])
        status, checked = self.pack("check")
        self.assertEqual((EXIT_REFUSED, "incomplet"), (status, checked["state"]))
        self.assertEqual((EXIT_REFUSED, [PACK]), (self.run_gate()[0], self.run_gate()[1]["missing"]))

    def test_convoy_without_the_mark_is_not_touched(self):
        self.ready()
        before = self.everything()

        for command in ("generate", "check"):
            status, answer = self.pack(command, convoy=PLAIN_CONVOY)
            self.assertEqual(EXIT_NOT_NEW_FLOW, status, answer)
            self.assertFalse(answer["new_flow"])

        self.assertEqual(before, self.everything())

    def test_generation_without_a_repository_is_refused(self):
        self.ready()
        before = self.everything()

        proc = self.run_cmd(TOOL, "generate", CONVOY)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("--repo", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.everything())


if __name__ == "__main__":
    unittest.main()
