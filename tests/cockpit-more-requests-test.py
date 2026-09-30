"""Tests for T15 (af-icxjc4, Spec af-oohx2x): the "other" Operator
Request sources (lib/cockpit/requests/sources/**) and the journal des
demandes résolues (lib/cockpit/ui/journal/**).

Neither module has a CLI or HTTP surface of its own — wiring them into
the running cockpit process (readmodel pollers, requests/builder merge,
server.py routes) is out of this ticket's declared scope
(gc.scope_paths: lib/cockpit/requests/sources/**, lib/cockpit/ui/journal/**
only) and left to the wiring ticket. This matches the precedent
``cockpit-requests-test.py`` itself sets for ``cockpit.text.validate``
("no CLI or HTTP surface of its own ... drive that function directly"):
every assertion here drives the pure functions that *are* this ticket's
whole public interface, with fixture data shaped exactly like the real
``bd show --json`` / ``bd comments --json`` output the wiring ticket will
hand them.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "more-requests"

sys.path.insert(0, str(ROOT / "lib"))

from cockpit.requests.model import A_FAIRE, QUAND_TU_VEUX  # noqa: E402
from cockpit.requests.sources.hitl import build_hitl_requests  # noqa: E402
from cockpit.requests.sources.readability import build_readability_requests  # noqa: E402
from cockpit.requests.sources.rituals import build_ritual_requests  # noqa: E402
from cockpit.requests.sources.specs_and_graphs import (  # noqa: E402
    TYPE_GRAPHE_A_APPROUVER,
    TYPE_SPEC_A_APPROUVER,
    build_specs_and_graphs_requests,
)
from cockpit.requests.sources.unknown_signal import build_unknown_signal_requests  # noqa: E402
from cockpit.ui.actions.render import render_actions  # noqa: E402
from cockpit.ui.journal.entries import JournalEntry, build_journal, parse_trace_note  # noqa: E402
from cockpit.ui.journal.render import render_journal_section  # noqa: E402


def load_fixture(name):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


class SpecsAndGraphsTest(unittest.TestCase):
    def test_draft_spec_is_a_faire_and_exits_when_approved(self):
        beads = load_fixture("spec-draft.json")
        requests = build_specs_and_graphs_requests(beads, verifie_a=1000.0)
        self.assertEqual(1, len(requests))
        request = requests[0]
        self.assertEqual(A_FAIRE, request.niveau)
        self.assertEqual(TYPE_SPEC_A_APPROUVER, request.type)
        self.assertIn("Spec", request.quoi)

        # Exit at-source: spec_state flips to APPROVED_SPEC on the same bead.
        beads[0]["metadata"]["spec_state"] = "APPROVED_SPEC"
        self.assertEqual([], build_specs_and_graphs_requests(beads, verifie_a=1000.0))

    def test_draft_graph_is_a_faire_and_exits_when_published(self):
        beads = load_fixture("graph-draft.json")
        requests = build_specs_and_graphs_requests(beads, verifie_a=1000.0)
        self.assertEqual(1, len(requests))
        request = requests[0]
        self.assertEqual(A_FAIRE, request.niveau)
        self.assertEqual(TYPE_GRAPHE_A_APPROUVER, request.type)

        # Exit at-source: publish adds the approved label (draft label stays).
        beads[0]["labels"].append("approved-ticket-graph")
        self.assertEqual([], build_specs_and_graphs_requests(beads, verifie_a=1000.0))

    def test_no_execute_button_for_a_benjamin_level_decision(self):
        """Spec .37: approving a Spec, approving or publishing a graph
        (a Benjamin-level decision) never gets an execute button in the
        cockpit -- only acquitter/reporter/continuer (the Operator
        Action catalogue) render, and continuer only ever copies a
        prompt, never runs anything."""
        beads = load_fixture("spec-draft.json")
        request = build_specs_and_graphs_requests(beads, verifie_a=1000.0)[0]
        actions_html = render_actions(request)
        for forbidden in ("approuver", "Approuver", "data-action=\"approuver\"", "publier", "Publier"):
            self.assertNotIn(forbidden, actions_html)
        # que_faire itself only ever offers a prompt to copy, never an
        # "exécuter"/"approuver" option (T15's own contract, checked
        # directly since render_actions never renders que_faire options
        # as buttons in the first place).
        for option in request.que_faire:
            self.assertIn("Copier", option["option"])


class RitualsTest(unittest.TestCase):
    def test_due_ritual_is_quand_tu_veux_never_pushed_and_exits_when_done(self):
        rituals = load_fixture("rituals-due.json")
        requests = build_ritual_requests(rituals, verifie_a=1000.0)
        self.assertEqual(1, len(requests))
        self.assertEqual(QUAND_TU_VEUX, requests[0].niveau)

        rituals[0]["due"] = False
        self.assertEqual([], build_ritual_requests(rituals, verifie_a=1000.0))


class HitlTest(unittest.TestCase):
    def test_ready_unlaunched_hitl_ticket_is_quand_tu_veux_and_exits_when_launched(self):
        beads = load_fixture("hitl-ready.json")
        requests = build_hitl_requests(beads, verifie_a=1000.0)
        self.assertEqual(1, len(requests))
        self.assertEqual(QUAND_TU_VEUX, requests[0].niveau)

        # Launched: a session claims it (assignee set) -- exit at-source.
        beads[0]["assignee"] = "factory-worker-1"
        self.assertEqual([], build_hitl_requests(beads, verifie_a=1000.0))

    def test_hitl_ticket_not_open_is_not_a_request(self):
        beads = load_fixture("hitl-ready.json")
        beads[0]["status"] = "blocked"
        self.assertEqual([], build_hitl_requests(beads, verifie_a=1000.0))


class ReadabilityTest(unittest.TestCase):
    def test_source_unreadable_over_15_min_becomes_a_faire(self):
        now = 10_000.0
        sources = [{"name": "github", "display_name": "GitHub", "last_good_read_at": now - 16 * 60}]
        requests = build_readability_requests(sources, now)
        self.assertEqual(1, len(requests))
        self.assertEqual(A_FAIRE, requests[0].niveau)
        self.assertIn("GitHub", requests[0].quoi)

    def test_source_unreadable_under_15_min_is_not_yet_a_request(self):
        now = 10_000.0
        sources = [{"name": "github", "display_name": "GitHub", "last_good_read_at": now - 5 * 60}]
        self.assertEqual([], build_readability_requests(sources, now))

    def test_source_exits_the_instant_it_reads_again(self):
        now = 10_000.0
        sources = [{"name": "github", "display_name": "GitHub", "last_good_read_at": now - 16 * 60}]
        self.assertEqual(1, len(build_readability_requests(sources, now)))
        sources[0]["last_good_read_at"] = now - 1
        self.assertEqual([], build_readability_requests(sources, now))


class UnknownSignalTest(unittest.TestCase):
    def test_unknown_signal_is_quand_tu_veux_and_names_its_source(self):
        signals = [{"id": "sig-1", "source": "loop-guard", "texte_brut": "wat=42"}]
        requests = build_unknown_signal_requests(signals, verifie_a=1000.0)
        self.assertEqual(1, len(requests))
        self.assertEqual(QUAND_TU_VEUX, requests[0].niveau)
        self.assertIn("loop-guard", requests[0].quoi)
        self.assertIn("Signal non reconnu venant de", requests[0].quoi)

    def test_unknown_signal_exits_when_the_source_stops_reporting_it(self):
        signals = [{"id": "sig-1", "source": "loop-guard", "texte_brut": "wat=42"}]
        self.assertEqual(1, len(build_unknown_signal_requests(signals, verifie_a=1000.0)))
        self.assertEqual([], build_unknown_signal_requests([], verifie_a=1000.0))


class JournalTest(unittest.TestCase):
    def test_journal_reads_a_repondre_resolution_from_its_trace_comment(self):
        comments_by_bead = load_fixture("journal-repondre.json")
        entries = build_journal(comments_by_bead)
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("af-need1", entry.bead_id)
        self.assertEqual("escalation-door", entry.voie)
        self.assertIn("répondu", entry.quoi)
        self.assertTrue(entry.quand)
        self.assertTrue(entry.par)

    def test_journal_reads_proposition_accepted_and_rejected(self):
        comments_by_bead = load_fixture("journal-propositions.json")
        entries = build_journal(comments_by_bead)
        voies = sorted(e.voie for e in entries)
        self.assertEqual(["proposal-door", "proposal-door"], voies)
        quois = sorted(e.quoi for e in entries)
        self.assertTrue(any("acceptée" in q for q in quois))
        self.assertTrue(any("rejetée" in q for q in quois))

    def test_non_resolving_cockpit_actions_are_not_journalled(self):
        """acquitter and reporter never close a request at the source --
        their trace comments must not show up as a "resolved" row."""
        comments = [
            "Cockpit: acquitter sur af-x1 (-) — 2026-09-30T10:00:00Z, par benjamin",
            "Cockpit: reporter sur af-x1 (1h) — 2026-09-30T10:05:00Z, par benjamin",
        ]
        self.assertIsNone(parse_trace_note("af-x1", comments[0]))
        self.assertIsNone(parse_trace_note("af-x1", comments[1]))
        self.assertEqual([], build_journal({"af-x1": comments}))

    def test_relancer_is_journalled_as_cockpit(self):
        text = "Cockpit: relancer sur session s1 (session) — 2026-09-30T10:00:00Z, par benjamin"
        entry = parse_trace_note("af-x2", text)
        self.assertIsNotNone(entry)
        self.assertEqual("cockpit", entry.voie)
        self.assertEqual("benjamin", entry.par)
        self.assertEqual("2026-09-30T10:00:00Z", entry.quand)

    def test_a_request_that_recurs_after_resolution_is_a_new_request_with_two_journal_entries(self):
        """spec .19: recurrence is a new request, not a reopening of the
        old one. Two répondre comments on the same bead id (resolved,
        reopened by a fresh NEEDS BENJAMIN, resolved again) must produce
        two distinct journal entries -- never collapsed into one."""
        comments_by_bead = {
            "af-need1": [
                {"body": "RÉPONSE: a — première réponse", "created_at": "2026-09-30T09:00:00Z", "author": "benjamin"},
                {"body": "RÉPONSE: b — deuxième réponse", "created_at": "2026-09-30T14:00:00Z", "author": "benjamin"},
            ]
        }
        entries = build_journal(comments_by_bead)
        self.assertEqual(2, len(entries))
        self.assertEqual(["première réponse", "deuxième réponse"], [e.quoi.split("— ", 1)[1] for e in entries])
        self.assertNotEqual(entries[0].quand, entries[1].quand)

    def test_render_journal_section_shows_quoi_quand_par_and_empty_state(self):
        self.assertIn("Aucune demande résolue", render_journal_section([]))
        entry = JournalEntry(bead_id="af-1", quoi="répondu a — ok", quand="2026-09-30T10:00:00Z", par="benjamin", voie="escalation-door")
        html_out = render_journal_section([entry])
        self.assertIn("répondu a — ok", html_out)
        self.assertIn("2026-09-30T10:00:00Z", html_out)
        self.assertIn("benjamin", html_out)


if __name__ == "__main__":
    unittest.main()
