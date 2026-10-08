#!/usr/bin/env python3
"""C01 Cockpit V2, T07: proposal-door is the one door for every proposal.
Proves: `create` refuses a proposal missing its required fields (quoi /
pourquoi / que_faire / langue in the Operator Language / classe) without
writing anything, and creates a complete one labelled `proposal`; `accepter`,
`rejeter` (refuses without a reason) and `reporter` each trace their action
on the bead (comment + metadata, acteur); `resoudre` resolves a pending
proposal only on a proof naming a PR or a commit; `compte` excludes
accepted, rejected and resolved proposals from the pending count, while a legacy proposal with no
gc.proposal_state still counts as pending.

ADR-0029 (2026-10-07): a `decision` needs exactly one « Recommandé » option
with its raison; a `maintenance` proposal becomes, at the door, one bug bead
authorized by ADR-0029, linked to the proposal, routed to the Mayor by mail
(never escalation-door mayor, whose sweep would promote it to the operator),
the proposal moving to `prise_en_charge`; `reconvertir` stops such a bead
and turns the proposal into a `decision`; `compte` and `list` filter by
class; an existing proposal is never rewritten.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "proposal-door"
FAKE_GC = ROOT / "tests" / "fixtures" / "proposal-door" / "fake-gc"


class ProposalDoorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bead_dir = root / "beads"
        self.bead_dir.mkdir()
        self.call_log = root / "calls.log"
        self.call_log.write_text("", encoding="utf-8")
        self.mail_log = root / "mail.log"
        self.mail_log.write_text("", encoding="utf-8")
        self.next_id_file = root / "next-id"
        self.next_id_file.write_text("af-prop1\naf-bug1\n", encoding="utf-8")
        self.env = {
            **os.environ,
            "GC_BIN": str(FAKE_GC),
            "PD_BEAD_DIR": str(self.bead_dir),
            "PD_CALL_LOG": str(self.call_log),
            "PD_MAIL_LOG": str(self.mail_log),
            "PD_NEXT_ID_FILE": str(self.next_id_file),
            "PROPOSAL_DOOR_LOCK_FILE": str(root / "lock"),
            "PROPOSAL_DOOR_NOW": "1790000000",
        }

    def door(self, *args, check=False):
        return subprocess.run(
            (str(SCRIPT),) + args, env=self.env, text=True, capture_output=True, check=check
        )

    def seed(self, bead_id, payload):
        (self.bead_dir / f"{bead_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    def bead(self, bead_id):
        return json.loads((self.bead_dir / f"{bead_id}.json").read_text(encoding="utf-8"))

    def set_next_ids(self, *bead_ids):
        self.next_id_file.write_text("".join(b + "\n" for b in bead_ids), encoding="utf-8")

    def calls(self):
        return [line for line in self.call_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    COMPLETE = {
        "quoi": "Proposer des leases dynamiques pour les conflits PR répétés",
        "pourquoi": "3 conflits PR sans chevauchement déclaré en 7 jours",
        "que_faire": [
            {
                "option": "Étudier les leases dynamiques au prochain Planning Run",
                "consequence": "Aucun changement immédiat ; trié à la prochaine carte.",
                "recommande": True,
                "raison": "Le seuil est franchi trois fois cette semaine.",
            }
        ],
        "langue": "fr",
        "classe": "decision",
    }

    MAINTENANCE = {
        "quoi": "Filtrer les pages périmées de la liste des tâches planifiées",
        "pourquoi": "Trois pages périmées encombrent la liste depuis deux jours",
        "que_faire": [
            {"option": "Filtrer les pages fermées", "consequence": "La liste ne montre que les pages ouvertes."}
        ],
        "langue": "fr",
        "classe": "maintenance",
    }

    # --- create --------------------------------------------------------

    def test_create_refuses_a_proposal_missing_a_required_field(self):
        missing = {k: v for k, v in self.COMPLETE.items() if k != "pourquoi"}
        result = self.door("create", json.dumps(missing))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))

    def test_create_refuses_an_option_with_no_consequence(self):
        payload = json.loads(json.dumps(self.COMPLETE))
        del payload["que_faire"][0]["consequence"]
        result = self.door("create", json.dumps(payload))
        self.assertNotEqual(0, result.returncode)

    def test_create_refuses_a_language_other_than_the_operator_language(self):
        payload = json.loads(json.dumps(self.COMPLETE))
        payload["langue"] = "en"
        result = self.door("create", json.dumps(payload))
        self.assertNotEqual(0, result.returncode)

    def test_create_refuses_a_proposal_without_a_class_or_with_an_unknown_one(self):
        # ADR-0029 point 1: the class is chosen by the producer, at creation.
        missing = {k: v for k, v in self.COMPLETE.items() if k != "classe"}
        result = self.door("create", json.dumps(missing))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("classe", result.stderr)
        unknown = dict(self.COMPLETE, classe="urgent")
        result = self.door("create", json.dumps(unknown))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))
        self.assertEqual([], self.calls())

    def test_create_refuses_a_decision_without_exactly_one_recommended_option(self):
        # ADR-0029 point 3: « porte obligatoirement une option Recommandé ».
        none = json.loads(json.dumps(self.COMPLETE))
        del none["que_faire"][0]["recommande"]
        del none["que_faire"][0]["raison"]
        result = self.door("create", json.dumps(none))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Recommandé", result.stderr)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))
        # ... with its raison (the existing rule, unchanged).
        no_reason = json.loads(json.dumps(self.COMPLETE))
        del no_reason["que_faire"][0]["raison"]
        result = self.door("create", json.dumps(no_reason))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))

    def test_create_writes_a_complete_decision_labelled_proposal(self):
        result = self.door("create", json.dumps(self.COMPLETE), check=True)
        self.assertIn("af-prop1", result.stdout)
        bead = self.bead("af-prop1")
        self.assertIn("proposal", bead["labels"])
        self.assertEqual(self.COMPLETE["quoi"], bead["metadata"]["gc.proposal_quoi"])
        self.assertEqual("ouverte", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("decision", bead["metadata"]["gc.proposal_classe"])
        # A decision waits on the operator: no bug bead, no mail.
        self.assertEqual(["af-prop1"], [p.stem for p in self.bead_dir.glob("*.json")])
        self.assertEqual("", self.mail_log.read_text(encoding="utf-8"))

    def test_maintenance_becomes_a_bug_bead_authorized_by_the_adr_and_routed_to_the_mayor(self):
        # ADR-0029 point 2. A maintenance proposal needs no recommendation.
        result = self.door("create", json.dumps(self.MAINTENANCE), check=True)
        self.assertIn("PROPOSITION CRÉÉE: af-prop1", result.stdout)
        self.assertIn("PRISE EN CHARGE: af-prop1 — ticket af-bug1", result.stdout)

        proposal = self.bead("af-prop1")
        self.assertEqual("maintenance", proposal["metadata"]["gc.proposal_classe"])
        self.assertEqual("prise_en_charge", proposal["metadata"]["gc.proposal_state"])
        self.assertEqual("af-bug1", proposal["metadata"]["gc.proposal_bug"])
        self.assertEqual("proposal-door", proposal["metadata"]["gc.proposal_response_actor"])
        self.assertIn("PROPOSITION PRISE EN CHARGE par proposal-door — ticket af-bug1", proposal["notes"])

        bug = self.bead("af-bug1")
        self.assertEqual("bug", bug["issue_type"])
        self.assertEqual(self.MAINTENANCE["quoi"], bug["title"])
        self.assertNotIn("proposal", bug["labels"])  # dispatch-door refuses a proposal-labelled bead
        self.assertIn("maintenance", bug["labels"])
        self.assertEqual("ADR-0029", bug["metadata"]["gc.authorized_by"])
        self.assertEqual("proposal-door", bug["metadata"]["gc.source"])
        self.assertEqual("af-prop1", bug["metadata"]["gc.proposal_id"])
        self.assertIn("ADR-0017", bug["description"])  # the defect only, never a refactor
        self.assertIn("reconvertir af-prop1", bug["description"])  # ADR-0029 point 6

        calls = "\n".join(self.calls())
        self.assertIn("bd dep relate af-bug1 af-prop1", calls)
        # Routed to the Mayor by mail (its turn's first item), never through
        # escalation-door mayor: that sweep promotes to the operator after 2 h.
        mail = self.mail_log.read_text(encoding="utf-8")
        self.assertIn("mayor", mail.split("\n")[0])
        self.assertIn("af-bug1", mail)
        self.assertIn("factory-work-dispatch", mail)
        self.assertNotIn("gc.needs_benjamin", calls)
        self.assertNotIn("gc.escalation_mayor_paged_at", calls)

    def test_maintenance_refused_before_any_write_when_incomplete(self):
        payload = json.loads(json.dumps(self.MAINTENANCE))
        payload["que_faire"] = []
        result = self.door("create", json.dumps(payload))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(self.bead_dir.glob("*.json")))
        self.assertEqual("", self.mail_log.read_text(encoding="utf-8"))

    # --- reconvertir (ADR-0029 point 6) -------------------------------------

    def test_reconvertir_stops_the_maintenance_bead_and_makes_the_proposal_a_decision(self):
        self.door("create", json.dumps(self.MAINTENANCE), check=True)
        options = json.dumps([
            {"option": "Filtrer les pages fermées", "consequence": "Tu ne verras plus les pages fermées dans la liste.",
             "recommande": True, "raison": "La liste redevient lisible."},
            {"option": "Garder la liste telle quelle", "consequence": "Rien ne change."},
        ])
        result = self.door("reconvertir", "af-prop1", "Touche ce que l'opérateur voit", options, "mayor", check=True)
        self.assertIn("RECONVERTIE: af-prop1", result.stdout)
        proposal = self.bead("af-prop1")
        self.assertEqual("decision", proposal["metadata"]["gc.proposal_classe"])
        self.assertEqual("ouverte", proposal["metadata"]["gc.proposal_state"])
        self.assertEqual("mayor", proposal["metadata"]["gc.proposal_response_actor"])
        self.assertEqual("Touche ce que l'opérateur voit", proposal["metadata"]["gc.proposal_reconversion_raison"])
        new_options = json.loads(proposal["metadata"]["gc.proposal_que_faire"])
        self.assertEqual(["a", "b"], [o["lettre"] for o in new_options])
        self.assertTrue(new_options[0]["recommande"])
        # The maintenance options are kept, never erased.
        old_options = json.loads(proposal["metadata"]["gc.proposal_que_faire_maintenance"])
        self.assertEqual("Filtrer les pages fermées", old_options[0]["option"])
        self.assertIn("PROPOSITION RECONVERTIE en décision par mayor — Touche ce que l'opérateur voit", proposal["notes"])
        bug = self.bead("af-bug1")
        self.assertEqual("closed", bug["status"])
        self.assertIn("Reconvertie", bug["close_reason"])

    def test_reconvertir_refuses_a_decision_or_options_without_a_recommendation(self):
        self.door("create", json.dumps(self.COMPLETE), check=True)
        options = json.dumps([{"option": "a", "consequence": "b", "recommande": True, "raison": "c"}])
        result = self.door("reconvertir", "af-prop1", "raison", options, "mayor")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("ouverte", self.bead("af-prop1")["metadata"]["gc.proposal_state"])

        self.set_next_ids("af-prop2", "af-bug2")
        self.door("create", json.dumps(self.MAINTENANCE), check=True)
        no_reco = json.dumps([{"option": "a", "consequence": "b"}])
        result = self.door("reconvertir", "af-prop2", "raison", no_reco, "mayor")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("prise_en_charge", self.bead("af-prop2")["metadata"]["gc.proposal_state"])
        self.assertEqual("open", self.bead("af-bug2")["status"])

    # --- accepter / rejeter / reporter ----------------------------------

    def test_accepter_moves_to_a_planifier_and_traces_actor(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("accepter", "af-x", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("a_planifier", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])
        self.assertIn("ACCEPTÉE", bead["notes"])

    def test_rejeter_without_a_reason_is_refused(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("rejeter", "af-x", "", "benjamin")
        self.assertNotEqual(0, result.returncode)
        bead = self.bead("af-x")
        self.assertNotIn("gc.proposal_state", bead["metadata"])

    def test_rejeter_with_a_reason_is_traced(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("rejeter", "af-x", "Hors périmètre du Planning Run", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("rejetee", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("Hors périmètre du Planning Run", bead["metadata"]["gc.proposal_reject_reason"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])

    def test_reporter_defers_until_an_hour_and_traces_actor(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        result = self.door("reporter", "af-x", "demain 09:00", "benjamin", check=True)
        self.assertIn("af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("demain 09:00", bead["metadata"]["gc.proposal_report_until"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])
        # A deferred proposal is still pending: reporter never sets proposal_state.
        self.assertNotIn("gc.proposal_state", bead["metadata"])

    def test_an_existing_proposal_is_never_rewritten_by_the_door(self):
        # The eight proposals open on 2026-10-07 keep their fields as they
        # are: accepting one adds its trace and nothing else.
        self.seed("af-old", {
            "id": "af-old", "status": "open", "notes": "PROPOSITION: ancienne", "labels": ["proposal"],
            "metadata": {"gc.proposal_quoi": "ancienne", "gc.proposal_pourquoi": "d'avant", "gc.proposal_que_faire": "[]"},
        })
        self.door("accepter", "af-old", "benjamin", check=True)
        bead = self.bead("af-old")
        self.assertEqual("ancienne", bead["metadata"]["gc.proposal_quoi"])
        self.assertNotIn("gc.proposal_classe", bead["metadata"])
        self.assertTrue(bead["notes"].startswith("PROPOSITION: ancienne"))

    # --- resoudre --------------------------------------------------------
    # 2026-10-07: four proposals (af-3yo0we, af-yc2ly0, af-1ai5e3, af-r2y2w9)
    # stayed pending in the Cockpit after the PRs that answered them had
    # merged. A merged delivery resolves a proposal through this door only.

    PROOF = "PR #385 (saymyname-app/agent-factory, merge a3393ef5a174)"

    def test_resoudre_on_a_merge_proof_traces_proof_and_actor(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {"gc.proposal_state": "ouverte"}, "notes": "", "labels": ["proposal"]})
        result = self.door("resoudre", "af-x", self.PROOF, "deliver-close", check=True)
        self.assertIn("RÉSOLUE: af-x", result.stdout)
        bead = self.bead("af-x")
        self.assertEqual("resolue", bead["metadata"]["gc.proposal_state"])
        self.assertEqual(self.PROOF, bead["metadata"]["gc.proposal_resolved_by"])
        self.assertEqual("deliver-close", bead["metadata"]["gc.proposal_response_actor"])
        self.assertIn("PROPOSITION RÉSOLUE par deliver-close — " + self.PROOF, bead["notes"])

    def test_resoudre_a_legacy_proposal_without_fields(self):
        # af-r2y2w9's shape: created before the door existed, metadata null.
        self.seed("af-legacy", {"id": "af-legacy", "status": "open", "metadata": None, "notes": "", "labels": ["proposal"]})
        self.door("resoudre", "af-legacy", "PR #340 (saymyname-app/agent-factory, merge d4933731c767)", "benjamin", check=True)
        self.assertEqual("resolue", self.bead("af-legacy")["metadata"]["gc.proposal_state"])

    def test_resoudre_a_taken_over_maintenance_proposal(self):
        # ADR-0029: the merged delivery of the maintenance bead resolves its
        # proposal (bin/deliver-close names it) -- prise_en_charge is not a
        # decision of the operator that a delivery would override.
        self.door("create", json.dumps(self.MAINTENANCE), check=True)
        self.door("resoudre", "af-prop1", self.PROOF, "deliver-close", check=True)
        self.assertEqual("resolue", self.bead("af-prop1")["metadata"]["gc.proposal_state"])

    def test_resoudre_without_a_merge_proof_is_refused(self):
        self.seed("af-x", {"id": "af-x", "status": "open", "metadata": {"gc.proposal_state": "ouverte"}, "notes": "", "labels": ["proposal"]})
        for proof in ("", "c'est corrigé", "voir la discussion"):
            result = self.door("resoudre", "af-x", proof, "deliver-close")
            self.assertNotEqual(0, result.returncode, proof)
        self.assertEqual("ouverte", self.bead("af-x")["metadata"]["gc.proposal_state"])
        self.assertNotIn("update", self.call_log.read_text(encoding="utf-8"))

    def test_resoudre_never_overrides_the_operators_decision(self):
        for state in ("a_planifier", "rejetee", "resolue"):
            self.seed("af-" + state, {"id": "af-" + state, "status": "open", "metadata": {"gc.proposal_state": state}, "notes": "", "labels": ["proposal"]})
            result = self.door("resoudre", "af-" + state, self.PROOF, "deliver-close")
            self.assertNotEqual(0, result.returncode, state)
            self.assertEqual(state, self.bead("af-" + state)["metadata"]["gc.proposal_state"])
        self.assertNotIn("update", self.call_log.read_text(encoding="utf-8"))

    def test_resoudre_refuses_a_bead_that_is_not_a_proposal(self):
        self.seed("af-ticket", {"id": "af-ticket", "status": "open", "metadata": {}, "notes": "", "labels": []})
        result = self.door("resoudre", "af-ticket", self.PROOF, "deliver-close")
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("gc.proposal_state", self.bead("af-ticket")["metadata"])

    # --- compte / list ----------------------------------------------------

    def _seed_mixed(self):
        self.seed("af-legacy", {"id": "af-legacy", "status": "open", "metadata": {}, "notes": "", "labels": ["proposal"]})
        self.seed("af-resolved", {"id": "af-resolved", "status": "open", "metadata": {"gc.proposal_state": "resolue"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-accepted", {"id": "af-accepted", "status": "open", "metadata": {"gc.proposal_state": "a_planifier"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-rejected", {"id": "af-rejected", "status": "open", "metadata": {"gc.proposal_state": "rejetee"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-open", {"id": "af-open", "status": "open", "metadata": {"gc.proposal_state": "ouverte", "gc.proposal_quoi": "d'avant la classe"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-deci", {"id": "af-deci", "status": "open", "metadata": {"gc.proposal_state": "ouverte", "gc.proposal_classe": "decision", "gc.proposal_quoi": "une décision"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-maint", {"id": "af-maint", "status": "open", "metadata": {"gc.proposal_state": "prise_en_charge", "gc.proposal_classe": "maintenance", "gc.proposal_quoi": "une maintenance"}, "notes": "", "labels": ["proposal"]})
        self.seed("af-maint-open", {"id": "af-maint-open", "status": "open", "metadata": {"gc.proposal_state": "ouverte", "gc.proposal_classe": "maintenance", "gc.proposal_quoi": "maintenance pas encore prise"}, "notes": "", "labels": ["proposal"]})

    def test_compte_excludes_accepted_rejected_resolved_and_taken_over_proposals(self):
        self._seed_mixed()
        result = self.door("compte", check=True)
        # legacy (sans champs), open (fields, no class), deci, maint-open
        self.assertEqual("4", result.stdout.strip())

    def test_compte_and_list_filter_by_class(self):
        self._seed_mixed()
        self.assertEqual("2", self.door("compte", "--classe", "decision", check=True).stdout.strip())
        self.assertEqual("1", self.door("compte", "--classe", "maintenance", check=True).stdout.strip())
        self.assertEqual("1", self.door("compte", "--classe", "sans_champs", check=True).stdout.strip())
        result = self.door("compte", "--classe", "autre")
        self.assertNotEqual(0, result.returncode)

        lines = self.door("list", "--classe", "decision", check=True).stdout.strip().splitlines()
        rows = sorted(line.split("\t") for line in lines)
        self.assertEqual(
            [["af-deci", "decision", "ouverte", "une décision"], ["af-open", "decision", "ouverte", "d'avant la classe"]],
            rows,
        )
        lines = self.door("list", check=True).stdout.strip().splitlines()
        self.assertEqual(4, len(lines))
        self.assertIn("af-legacy\tsans_champs\touverte\t", "\n".join(lines))

    def test_compte_is_zero_with_no_proposals(self):
        result = self.door("compte", check=True)
        self.assertEqual("0", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
