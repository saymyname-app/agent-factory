#!/usr/bin/env python3
"""bin/owner-answer and the judgement records of bin/convoy-state (T29,
Spec §11), on a fake tracker state and on the Delivered Outcome of the
delivery fixture: one test per pass and per refusal, each refusal
re-reading the tracker, the Evidence Packs and the calls made to the
proposition door to prove nothing was written."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "lib"))
from fixture_prototype import materialize  # noqa: E402
TOOL = ROOT / "bin" / "owner-answer"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sessions = load("acceptance-session-test.py")
packs = sessions.packs
gate = packs.gate
CONVOY, PLAIN_CONVOY, INTEGRATION, SLICE = packs.CONVOY, packs.PLAIN_CONVOY, packs.INTEGRATION, packs.SLICE
EXIT_REFUSED, EXIT_UNRULED, EXIT_NOT_NEW_FLOW = 1, 3, 4
APPROVER = "benjamin"
PROPOSITION = packs.FINDING_ID if ":" in packs.FINDING_ID else f"{SLICE}:{packs.FINDING_ID}"
WORDS = "Le pied de page est bon, j'accepte."
CRITERION = {"entry_point": "GET /", "observable": "le pied de page porte l'année en cours",
             "false_if": "le pied de page porte une autre année"}


def cited(text="L'accueil ne montre pas le titre attendu.", story="1"):
    """An Owner Finding that cites a user story, with the repair the agent
    of the session drafted for it."""
    return {"text": text, "cites": {"kind": "user_story", "ref": f"user story {story}"},
            "repair": {"title": "Rétablir le titre de l'accueil", "what_it_delivers": "Le titre attendu sur l'accueil.",
                       "demonstration_line": "GET / montre le titre attendu.", "acceptance_criteria": [CRITERION]}}


class OwnerAnswerTest(sessions.AcceptanceSessionTest):
    def setUp(self):
        super().setUp()
        self.proposals = self.tmp / "proposals.log"
        door = self.tmp / "path" / "owner-proposal-door"
        door.write_text(
            "#!/bin/sh\n"
            # The escalation door asks it for the count of pending proposals.
            '[ "$1" = create ] || { echo 0; exit 0; }\n'
            f'n=$(( $(wc -l < "{self.proposals}" 2>/dev/null || echo 0) + 1 ))\n'
            f'printf \'%s\\n\' "$2" >> "{self.proposals}"\n'
            'echo "PROPOSITION CRÉÉE: fx-p$n — notée"\n')
        door.chmod(0o755)
        self.env["PROPOSAL_DOOR_BIN"] = str(door)
        self.working_door = door.read_text()
        self.proposal_door = door

    # --- harness ------------------------------------------------------------

    def owner(self, command, *args, convoy=CONVOY):
        proc = self.run_cmd(TOOL, command, convoy, "--repo", self.repo, *args)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"réponse illisible (exit {proc.returncode}) : {proc.stdout}{proc.stderr}")

    def proposals_made(self):
        return [json.loads(line) for line in self.proposals.read_text(encoding="utf-8").splitlines()] \
            if self.proposals.exists() else []

    def everything(self):
        return (super().everything(), self.proposals.read_bytes() if self.proposals.exists() else b"")

    def delivered_dossier(self):
        """The Delivered Outcome of the fixture, whose project declares its
        human approver; one proposition awaits a verdict. Returns the commit
        and the fingerprint of its dossier."""
        commit = self.delivered_outcome()
        declared = self.root / "config" / "projects" / "fx-rig.toml"
        declared.write_text(declared.read_text() + f'human_approver = "{APPROVER}"\n')
        return commit, self.show()["convoy"]["delivered"]["pack"]

    def judgement(self):
        return self.show()["convoy"]["judgement"]

    def give_verdict(self, verdict, *args, proposition=PROPOSITION, by=APPROVER, words="Vu."):
        return self.owner("verdict", "--proposition", proposition, "--verdict", verdict,
                             "--approved-by", by, "--words", words, *args)

    def respond(self, response, commit, digest, *args, by=APPROVER, words=WORDS):
        given = [*(("--commit", commit) if commit else ()), *(("--pack-digest", digest) if digest else ()),
                 *(("--words", words) if words else ())]
        return self.owner("record", "--response", response, "--approved-by", by, *given, *args)

    def passed(self, status_and_answer):
        status, answer = status_and_answer
        self.assertEqual(0, status, answer)
        return answer

    def refusal_of(self, call):
        before = self.everything()
        status, answer = call()
        self.assertEqual(EXIT_REFUSED, status, answer)
        self.assertTrue(answer["error"].startswith("refus : "), answer)
        self.assertEqual(before, self.everything())
        return answer["error"]

    def break_the_proposition_door(self):
        self.proposal_door.write_text("#!/bin/sh\necho 'porte en panne' >&2\nexit 1\n")

    def mend_the_proposition_door(self):
        self.proposal_door.write_text(self.working_door)

    def findings_file(self, *findings):
        return self.json_file("constats.json", {"findings": list(findings)})

    # --- « accepté » ----------------------------------------------------------

    def test_accepted_is_refused_while_a_proposition_has_no_verdict(self):
        commit, digest = self.delivered_dossier()

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest))

        self.assertIn(PROPOSITION, error)
        self.assertIn("verdict", error)
        self.assertIsNone(self.judgement())

    def test_accepted_is_recorded_with_the_words_the_commit_and_the_fingerprint_of_the_dossier(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        answer = self.passed(self.respond("accepté", commit, digest))

        self.assertEqual(("accepted", commit, digest), (answer["response"], answer["commit"], answer["pack"]))
        shown = self.show()
        (last,) = shown["convoy"]["judgement"]["answers"]
        self.assertEqual(("accepted", WORDS, APPROVER, commit, digest),
                         (last["response"], last["words"], last["approver"], last["commit"], last["pack"]))
        # Recording closes nothing and merges nothing: the Outcome is still the Delivered one.
        self.assertEqual(commit, shown["convoy"]["delivered"]["commit"])
        self.assertEqual("open", shown["convoy"]["status"])
        self.assertFalse(shown["unruled"])
        # The pack Benjamin judged still holds after his answer.
        status, held = self.pack("check")
        self.assertEqual((0, "à jour"), (status, held["state"]))

    def test_accepted_is_refused_from_anyone_but_the_declared_human_approver(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest, by="delivery-author"))

        self.assertIn("approbateur humain", error)

    def test_a_verdict_is_refused_from_anyone_but_the_declared_human_approver(self):
        self.delivered_dossier()

        error = self.refusal_of(lambda: self.give_verdict("sans suite", by="delivery-author"))

        self.assertIn("approbateur humain", error)

    def test_accepted_is_refused_when_the_commit_is_no_longer_the_tip_of_the_integration_branch(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        added = self.note(INTEGRATION)

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest))

        self.assertIn("pointe", error)
        self.assertIn(added[:12], error)

    def test_accepted_is_refused_at_a_commit_that_is_not_the_one_of_the_dossier(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        error = self.refusal_of(lambda: self.respond("accepté", self.base, digest))

        self.assertIn("commit", error)

    def test_accepted_is_refused_when_the_dossier_is_outdated(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        # No commit more: a record the page shows changed since the dossier.
        self.state("set-model", CONVOY, packs.SCREEN, "--role", "author", "--agent", "delivery-author",
                   "--provider", "p-claude", "--model", "un-autre-modele")

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest))

        self.assertIn("périmé", error)

    def test_accepted_is_refused_with_another_fingerprint_than_the_one_of_the_dossier(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        error = self.refusal_of(lambda: self.respond("accepté", commit, "sha256:" + "0" * 64))

        self.assertIn("empreinte", error)

    def test_accepted_is_refused_without_words(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest, words=None))

        self.assertIn("mots", error)

    def test_nothing_is_recorded_after_an_accepted_outcome(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("accepté", commit, digest))

        error = self.refusal_of(lambda: self.respond("constats rendus", commit, digest, "--findings", self.findings_file(cited())))

        self.assertIn("travail nouveau", error)

    # --- the verdicts on the propositions ---------------------------------------

    def test_a_verdict_later_creates_a_proposition_through_the_door_and_does_not_block(self):
        commit, digest = self.delivered_dossier()

        answer = self.passed(self.give_verdict("plus tard"))

        (made,) = self.proposals_made()
        self.assertEqual("fr", made["langue"])
        self.assertIn("pied de page", made["quoi"])
        self.assertEqual("fx-p1", answer["proposal"])
        (verdict,) = self.judgement()["verdicts"]
        self.assertEqual((PROPOSITION, "plus_tard", "fx-p1", APPROVER, "Vu."),
                         (verdict["proposition"], verdict["verdict"], verdict["proposal"], verdict["approver"], verdict["words"]))
        # The same verdict again creates nothing more.
        self.passed(self.give_verdict("plus tard"))
        self.assertEqual(1, len(self.proposals_made()))
        self.passed(self.respond("accepté", commit, digest))

    def test_a_verdict_to_do_before_accepting_blocks_accepted(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("à faire avant d'accepter"))

        error = self.refusal_of(lambda: self.respond("accepté", commit, digest))

        self.assertIn("à faire avant d'accepter", error)
        self.assertIn(PROPOSITION, error)

    def test_a_verdict_outside_the_three_or_on_an_unknown_proposition_is_refused(self):
        self.delivered_dossier()

        self.assertIn("verdict", self.refusal_of(lambda: self.give_verdict("peut-être")))
        self.assertIn("proposition", self.refusal_of(lambda: self.give_verdict("sans suite", proposition=f"{SLICE}:out_of_ticket.9")))

    # --- « constats rendus » and the route of each Owner Finding -------------------------

    def test_findings_returned_route_each_one_by_code_and_put_the_outcome_back_in_delivery(self):
        commit, _ = self.delivered_dossier()
        # A round of the end was counted before this Outcome was Delivered.
        self.edit(CONVOY, **{"gc.flow.counter.end_rounds": 1})
        self.generate()
        status, answer = self.run_gate()
        self.assertEqual((0, True), (status, answer["delivered"]), answer)
        digest = self.show()["convoy"]["delivered"]["pack"]
        self.assertEqual(1, self.show()["convoy"]["counters"]["end_rounds"])
        self.passed(self.give_verdict("sans suite"))
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        statuses = {CONVOY: self.show()["convoy"]["status"]}
        tickets = {ticket["id"]: ticket["status"] for ticket in self.show()["tickets"]}
        findings = self.findings_file(
            cited(),
            {"text": "Je veux un mode sombre."},
            {"text": "Le bouton devrait être bleu.", "cites": {"kind": "user_story", "ref": "user story 999"}},
            {"text": "Un export CSV serait utile.", "later": True})

        answer = self.passed(self.respond("constats rendus", commit, digest, "--findings", findings,
                                       words="Trois choses à revoir."))

        self.assertEqual(["repair", "planning_exception", "planning_exception", "later"],
                         [finding["route"] for finding in answer["findings"]])
        shown = self.show()
        convoy = shown["convoy"]
        (last,) = convoy["judgement"]["answers"]
        self.assertEqual(("findings", "Trois choses à revoir.", APPROVER, commit, digest),
                         (last["response"], last["words"], last["approver"], last["commit"], last["pack"]))
        # One Planning Exception for the batch: the second finding joined the first.
        self.assertEqual([2, 3], last["exception"]["findings"])
        self.assertNotIn("ticket", last["findings"][1])
        self.assertNotIn("draft", last["findings"][1])
        self.assertNotIn("draft", last["findings"][2])
        self.assertEqual("user_story", last["findings"][0]["draft"]["restores"]["kind"])
        # « plus tard » : a proposition, created by code.
        self.assertEqual("fx-p1", last["findings"][3]["proposal"])
        self.assertIn("export CSV", self.proposals_made()[0]["quoi"])
        # Nothing closes, the Outcome is no longer Delivered, the rounds start again from zero.
        self.assertIsNone(convoy["delivered"])
        self.assertIsNone(convoy["acceptance"])
        self.assertIsNone(convoy["end_round"])
        self.assertEqual(0, convoy["counters"]["end_rounds"])
        self.assertEqual(statuses[CONVOY], convoy["status"])
        self.assertEqual(tickets, {ticket["id"]: ticket["status"] for ticket in shown["tickets"]})
        self.assertFalse(shown["unruled"])

    def test_the_outcome_is_not_delivered_again_while_a_returned_finding_has_no_repair_or_its_exception_is_open(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("constats rendus", commit, digest, "--findings",
                              self.findings_file(cited(), {"text": "Je veux un mode sombre."})))
        before = self.everything()

        proc = self.run_cmd(gate.STATE_TOOL, "record-delivered", CONVOY, "--commit", commit, "--pack-digest", digest)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
        error = json.loads(proc.stdout)["error"]
        self.assertIn("constat", error)
        self.assertIn("Planning Exception", error)
        self.assertEqual(before, self.everything())

    def anchored(self, anchor):
        """An Owner Finding that cites an anchor, with its drafted repair.
        The prototype branch of the Spec lives on the remote of the
        project, never merged: it is read from there."""
        materialize(self.origin)
        return {**cited("La liste n'est pas où le prototype la place."), "cites": {"kind": "anchor", "ref": anchor}}

    def test_a_finding_that_cites_an_anchor_the_validated_prototype_does_not_hold_is_a_planning_exception(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        answer = self.passed(self.respond("constats rendus", commit, digest, "--findings",
                                          self.findings_file(self.anchored("pied-de-page"))))

        self.assertEqual(["planning_exception"], [finding["route"] for finding in answer["findings"]])
        (last,) = self.judgement()["answers"]
        # No repair is drafted for it, and it joins the Planning Exception of the batch.
        self.assertNotIn("draft", last["findings"][0])
        self.assertNotIn("ticket", last["findings"][0])
        self.assertEqual([1], last["exception"]["findings"])

    def test_a_finding_that_cites_an_anchor_of_the_validated_prototype_is_a_repair(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        answer = self.passed(self.respond("constats rendus", commit, digest, "--findings",
                                          self.findings_file(self.anchored("fixture-items"))))

        self.assertEqual(["repair"], [finding["route"] for finding in answer["findings"]])
        (last,) = self.judgement()["answers"]
        self.assertEqual({"kind": "anchor", "ref": "fixture-items"}, last["findings"][0]["draft"]["restores"])
        self.assertNotIn("exception", last)

    def test_findings_that_cite_an_anchor_are_refused_when_the_validated_prototype_cannot_be_read(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.env["PROTOTYPE_CONFORMANCE_BIN"] = "/bin/false"
        findings = self.findings_file(self.anchored("fixture-items"))

        error = self.refusal_of(lambda: self.respond("constats rendus", commit, digest, "--findings", findings))

        self.assertIn("ancres du Validated Prototype", error)

    def amended_spec_published(self):
        """The Spec amended and approved again, and the revised graph
        published from it: what the patch door leaves on the convoy (its
        digest, tests/ticket-graph-publish-citation-test.py)."""
        raised_on = self.show()["convoy"]["spec_digest"]
        amended = "sha256:" + "5" * 64
        self.assertNotEqual(raised_on, amended)
        self.edit(CONVOY, **{"gc.spec_digest": amended})

    def test_the_planning_exception_of_the_batch_is_not_resolved_while_the_spec_has_not_been_amended(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("constats rendus", commit, digest, "--findings",
                                 self.findings_file({"text": "Je veux un mode sombre."})))
        self.assertEqual(self.show()["convoy"]["spec_digest"], self.judgement()["answers"][-1]["exception"]["spec_digest"])

        error = self.refusal_of(
            lambda: self.owner("resolve-exception", "--approved-by", APPROVER, "--words", "La Spec est amendée."))

        self.assertIn("n'a pas été amendée", error)
        self.assertNotIn("resolved", self.judgement()["answers"][-1]["exception"])

    def test_the_planning_exception_of_the_batch_holds_delivered_until_it_is_resolved_on_the_approver_words(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("constats rendus", commit, digest, "--findings",
                                 self.findings_file({"text": "Je veux un mode sombre."})))
        refused = self.run_cmd(gate.STATE_TOOL, "record-delivered", CONVOY, "--commit", commit, "--pack-digest", digest)
        self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stdout)
        self.amended_spec_published()
        self.assertIn("approbateur humain", self.refusal_of(
            lambda: self.owner("resolve-exception", "--approved-by", "delivery-author", "--words", "C'est réglé.")))

        answer = self.passed(self.owner("resolve-exception", "--approved-by", APPROVER, "--words", "La Spec est amendée."))

        self.assertEqual((APPROVER, "La Spec est amendée."),
                         (answer["exception"]["resolved"]["approver"], answer["exception"]["resolved"]["words"]))
        # Nothing of the batch holds the Outcome any more: it is Delivered again on its green conditions.
        self.state("record-delivered", CONVOY, "--commit", commit, "--pack-digest", digest)
        self.assertEqual(commit, self.show()["convoy"]["delivered"]["commit"])

    def test_the_repair_of_a_returned_finding_is_named_once_and_only_by_a_repair_of_the_convoy(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.passed(self.respond("constats rendus", commit, digest, "--findings",
                                 self.findings_file(cited(), {"text": "Je veux un mode sombre."})))
        for args, said in ((("--finding", "1", "--ticket", SLICE), "n'est pas un repair"),
                           (("--finding", "2", "--ticket", SLICE), "route"),
                           (("--finding", "7", "--ticket", SLICE), "constat inconnu")):
            before = self.everything()
            proc = self.run_cmd(gate.STATE_TOOL, "set-owner-repair", CONVOY, *args)
            self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn(said, json.loads(proc.stdout)["error"])
            self.assertEqual(before, self.everything())

    def test_the_acceptance_request_no_longer_waits_for_benjamin_once_he_answered(self):
        commit, digest = self.delivered_dossier()
        page = self.show()["convoy"]["evidence_pack"]["path"] + "/index.html"
        self.door("benjamin", CONVOY, json.dumps({
            "quoi": "Acceptance Request — un Delivered Outcome attend ton jugement", "pourquoi": "Tout est livré.",
            "que_faire": [{"option": "Ouvrir l'Acceptance Session", "consequence": "Le produit est lancé."}],
            "langue": "fr", "bloquant": True, "lien": page}, ensure_ascii=False))
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        self.assertIn(CONVOY, self.door("list"))
        self.passed(self.give_verdict("sans suite"))

        answer = self.passed(self.respond("accepté", commit, digest))

        self.assertNotIn("door", answer)
        self.assertNotIn(CONVOY, self.door("list"))

    def test_findings_returned_without_any_finding_are_refused(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        self.assertIn("constat", self.refusal_of(lambda: self.respond("constats rendus", commit, digest)))
        self.assertIn("constat", self.refusal_of(
            lambda: self.respond("constats rendus", commit, digest, "--findings", self.findings_file())))

    def test_a_finding_that_cites_a_story_without_its_repair_is_refused(self):
        commit, digest = self.delivered_dossier()
        finding = cited()
        del finding["repair"]

        error = self.refusal_of(lambda: self.respond("constats rendus", commit, digest, "--findings", self.findings_file(finding)))

        self.assertIn("repair", error)

    def test_a_proposition_to_do_before_accepting_is_returned_with_the_findings_and_no_longer_blocks(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("à faire avant d'accepter"))

        answer = self.passed(self.respond("constats rendus", commit, digest, words="À faire d'abord."))

        (finding,) = answer["findings"]
        self.assertEqual((PROPOSITION, "planning_exception"), (finding["proposition"], finding["route"]))
        self.assertIn("pied de page", finding["text"])

    def test_findings_returned_are_refused_from_anyone_but_the_declared_human_approver(self):
        commit, digest = self.delivered_dossier()

        error = self.refusal_of(lambda: self.respond("constats rendus", commit, digest, "--findings",
                                                 self.findings_file(cited()), by="delivery-author"))

        self.assertIn("approbateur humain", error)

    # --- the second dossier ------------------------------------------------------

    def test_the_dossier_generated_after_findings_opens_with_what_was_done_since_the_last_judgement(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        first = self.page({"page": self.show()["convoy"]["evidence_pack"]["path"] + "/index.html"})
        self.assertNotIn("Depuis ton dernier jugement", first)
        self.passed(self.respond("constats rendus", commit, digest, "--findings", self.findings_file(
            {"text": "Je veux un mode sombre."}, {"text": "Un export CSV serait utile.", "later": True}),
            words="Deux choses."))

        _, generated = self.pack("generate")
        page = self.page(generated)

        self.assertLess(page.index('<section id="rubrique-0">'), page.index('<section id="rubrique-1">'))
        rubric = self.rubric(page, 0)
        self.assertIn("Depuis ton dernier jugement", rubric)
        self.assertIn("Deux choses.", rubric)
        self.assertIn("Je veux un mode sombre.", rubric)
        self.assertIn("Planning Exception", rubric)
        self.assertIn("Un export CSV serait utile.", rubric)
        self.assertIn("fx-p1", rubric)

    # --- « abandonné », and what the tool does not know ------------------------------

    def test_abandoned_requires_a_one_line_reason(self):
        commit, digest = self.delivered_dossier()

        self.assertIn("raison", self.refusal_of(lambda: self.respond("abandonné", None, None, words=None)))
        self.assertIn("ligne", self.refusal_of(
            lambda: self.respond("abandonné", None, None, "--reason", "Trop tard.\nEt trop cher.", words=None)))

        answer = self.passed(self.respond("abandonné", None, None, "--reason", "Le besoin a disparu.", words=None))

        self.assertEqual("abandoned", answer["response"])
        (last,) = self.judgement()["answers"]
        self.assertEqual(("abandoned", "Le besoin a disparu.", APPROVER, commit, digest),
                         (last["response"], last["reason"], last["approver"], last["commit"], last["pack"]))
        self.assertFalse(self.show()["unruled"])

    def test_refused_and_partial_acceptance_are_not_answers(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))

        self.assertIn("refusé", self.refusal_of(lambda: self.respond("refusé", commit, digest)))
        self.assertIn("partielle", self.refusal_of(lambda: self.respond("accepté partiellement", commit, digest)))
        self.assertIn("partielle", self.refusal_of(lambda: self.respond("accepté", commit, digest, "--stories", "1")))
        self.assertEqual([], self.judgement()["answers"])

    def test_an_answer_is_refused_on_a_convoy_that_is_not_delivered(self):
        commit = self.ready()
        declared = self.root / "config" / "projects" / "fx-rig.toml"
        declared.write_text(declared.read_text() + f'human_approver = "{APPROVER}"\n')

        error = self.refusal_of(lambda: self.respond("accepté", commit, "sha256:" + "0" * 64))

        self.assertIn("Delivered", error)

    def test_a_proposition_door_that_fails_leaves_the_verdict_recorded_and_its_proposition_to_create(self):
        self.delivered_dossier()
        self.break_the_proposition_door()

        answer = self.passed(self.give_verdict("plus tard"))

        self.assertNotIn("proposal", answer)
        (pending,) = answer["proposals_pending"]
        self.assertEqual(PROPOSITION, pending["proposition"])
        self.assertIn("porte en panne", pending["detail"])
        (verdict,) = self.judgement()["verdicts"]
        self.assertEqual("plus_tard", verdict["verdict"])
        self.assertNotIn("proposal", verdict)
        # Once the door answers again, what is missing is created, once.
        self.mend_the_proposition_door()
        completed = self.passed(self.owner("proposals"))
        self.assertEqual(([{"proposition": PROPOSITION, "proposal": "fx-p1"}], []),
                         (completed["created"], completed["proposals_pending"]))
        self.assertEqual("fx-p1", self.judgement()["verdicts"][0]["proposal"])
        again = self.passed(self.owner("proposals"))
        self.assertEqual(([], []), (again["created"], again["proposals_pending"]))
        self.assertEqual(1, len(self.proposals_made()))

    def test_a_proposition_door_that_fails_leaves_the_findings_recorded_and_the_request_answered(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        self.door("benjamin", CONVOY, json.dumps({
            "quoi": "Acceptance Request — un Delivered Outcome attend ton jugement", "pourquoi": "Tout est livré.",
            "que_faire": [{"option": "Ouvrir l'Acceptance Session", "consequence": "Le produit est lancé."}],
            "langue": "fr", "bloquant": True,
            "lien": self.show()["convoy"]["evidence_pack"]["path"] + "/index.html"}, ensure_ascii=False))
        self.state("acceptance-requested", CONVOY, "--bead", CONVOY)
        self.break_the_proposition_door()
        findings = self.findings_file(cited(), {"text": "Un export CSV serait utile.", "later": True})

        answer = self.passed(self.respond("constats rendus", commit, digest, "--findings", findings))

        (pending,) = answer["proposals_pending"]
        self.assertEqual(2, pending["finding"])
        (last,) = self.judgement()["answers"]
        self.assertEqual("findings", last["response"])
        self.assertNotIn("proposal", last["findings"][1])
        self.assertIsNone(self.show()["convoy"]["delivered"])
        self.assertNotIn("door", answer)
        # The convoy is no longer Delivered: the proposition is still created once the door answers.
        self.mend_the_proposition_door()
        self.assertNotIn(CONVOY, self.door("list"))
        completed = self.passed(self.owner("proposals"))
        self.assertEqual([{"finding": 2, "proposal": "fx-p1"}], completed["created"])
        self.assertEqual("fx-p1", self.judgement()["answers"][-1]["findings"][1]["proposal"])
        self.assertIn("export CSV", self.proposals_made()[0]["quoi"])

    def test_abandoned_on_a_non_conforme_dossier_takes_its_request_off_the_operators_list(self):
        commit = self.non_conforme()
        declared = self.root / "config" / "projects" / "fx-rig.toml"
        declared.write_text(declared.read_text() + f'human_approver = "{APPROVER}"\n')
        self.assertIn(CONVOY, self.door("list"))

        answer = self.passed(self.respond("abandonné", None, None, "--reason", "Le besoin a disparu.", words=None))

        self.assertNotIn("door", answer)
        self.assertEqual(("abandoned", commit), (self.judgement()["answers"][-1]["response"], answer["commit"]))
        self.assertNotIn(CONVOY, self.door("list"))

    def test_a_convoy_in_a_state_without_rule_takes_no_answer(self):
        commit, digest = self.delivered_dossier()
        self.passed(self.give_verdict("sans suite"))
        # Closed outside its gate: the record of the gate is gone.
        self.edit(SLICE, unset=("gc.flow.gate.ticket_end",))
        before = self.everything()

        status, answer = self.respond("accepté", commit, digest)

        self.assertEqual(EXIT_UNRULED, status, answer)
        self.assertFalse(answer["ok"])
        self.assertTrue(answer["unruled"], answer)
        self.assertIn("état sans règle", answer["message"])
        self.assertEqual(before, self.everything())

    def test_a_convoy_without_the_mark_is_answered_as_not_of_the_new_flow(self):
        self.delivered_dossier()
        before = self.everything()

        status, answer = self.owner("record", "--response", "accepté", "--approved-by", APPROVER, "--words", WORDS,
                                       "--commit", self.base, "--pack-digest", "sha256:" + "0" * 64, convoy=PLAIN_CONVOY)

        self.assertEqual((EXIT_NOT_NEW_FLOW, False), (status, answer["new_flow"]))
        self.assertEqual(before, self.everything())


for inherited in (sessions.AcceptanceSessionTest,):
    for name in dir(inherited):
        if name.startswith("test_") and name not in OwnerAnswerTest.__dict__:
            setattr(OwnerAnswerTest, name, None)


if __name__ == "__main__":
    unittest.main()
