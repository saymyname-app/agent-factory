#!/usr/bin/env python3
"""2026-10-07 (af-3yo0we, af-yc2ly0, af-1ai5e3, af-r2y2w9): a proposal the
proposal door resolved on a merge proof (`gc.proposal_state=resolue`) leaves
« Ce qui t'attend » at the source, exactly as an accepted or rejected one
does, and the journal reads its « PROPOSITION RÉSOLUE par … — <preuve> »
trace as a resolution with its proof. Drives the two pure functions those
behaviours live in (``build_requests``, ``parse_trace_note``), the same way
cockpit-requests-test.py drives ``cockpit.text.validate``.
"""
import dataclasses
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.requests.builder import build_requests  # noqa: E402
from cockpit.ui.journal.entries import parse_trace_note  # noqa: E402

OPTIONS = [
    {"option": "Adopter la mise à jour", "consequence": "Réépingle la référence"},
    {"option": "Ne pas adopter", "consequence": "La référence reste inchangée"},
]


def proposal(bead_id, state, **extra):
    metadata = {
        "gc.proposal_quoi": "mattpocock/skills a publié v1.3.1, au-delà de la référence",
        "gc.proposal_pourquoi": "Référence épinglée à c55ee46073ed",
        "gc.proposal_que_faire": json.dumps(OPTIONS),
        "gc.proposal_state": state,
        "gc.proposal_horodatage": "2026-10-06T01:51:24Z",
    }
    metadata.update(extra)
    return {"id": bead_id, "status": "open", "labels": ["proposal"], "notes": "", "metadata": metadata}


def _dump(request):
    if dataclasses.is_dataclass(request):
        return json.dumps(dataclasses.asdict(request), ensure_ascii=False)
    return json.dumps(vars(request), ensure_ascii=False, default=str)


class ResolvedProposalTest(unittest.TestCase):
    def test_a_resolved_proposal_leaves_ce_qui_t_attend(self):
        requests = build_requests([
            proposal("af-pending", "ouverte"),
            proposal("af-done", "resolue", **{"gc.proposal_resolved_by": "PR #385 (merge a3393ef5a174)"}),
            proposal("af-acc", "a_planifier"),
        ])
        dumped = [_dump(r) for r in requests]
        self.assertEqual(1, len(dumped), dumped)
        self.assertIn("af-pending", dumped[0])
        self.assertNotIn("af-done", " ".join(dumped))

    def test_the_journal_reads_a_resolution_by_delivery_with_its_proof(self):
        entry = parse_trace_note(
            "af-done",
            "PROPOSITION RÉSOLUE par deliver-close — PR #385 (saymyname-app/agent-factory, merge a3393ef5a174)",
        )
        self.assertIsNotNone(entry)
        self.assertEqual("proposal-door", entry.voie)
        self.assertEqual("deliver-close", entry.par)
        self.assertIn("PR #385", entry.quoi)
        self.assertIn("résolue", entry.quoi)


if __name__ == "__main__":
    unittest.main()
