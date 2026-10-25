#!/usr/bin/env python3
"""Criterion test 1 of R1 « Vue d’ensemble et page projet comptent les
mêmes décisions ouvertes d’un chantier » (af-d6anqb; Spec af-fgcw0d, user
story 123, decision « État D01 commun aux vues » 2, Testing Decisions 1, 3
and 8): an open request on a ticket of a chantier counts for that chantier
and its project on every screen that says what waits for Benjamin.

The case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case sees
none of it). Its tracker holds one chantier of the Factory under way -- a
Spec, the convoy of its graph carrying the new-flow mark, four tickets of
that graph -- in the shapes the flow writes, as the tracker of the Factory
held them on 22/10/2026 when the defect was seen: the open requests sit on
the tickets themselves (`gc.needs_benjamin` and the `gc.escalation_*` the
escalation door writes), and a ticket carries its graph and its rig, no
project. Of the four tickets, two carry an open request, one a request
already answered, one none.

The four screens are read over HTTP, each in the part that says it:

- GET /: the indicator « Décisions à prendre » and the requests listed in
  the inbox;
- GET /runs/run?id=<convoy>: the head of the run of the chantier;
- GET /projet/agent-factory: the counter « Décisions attendues » and the
  card « Chantier actuel ».

False if one screen says 0 or « Aucune décision attendue » while another
shows an open request on a ticket of the same chantier, or if the screens
give different numbers.
"""

from __future__ import annotations

import html
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, fetch  # noqa: E402
from project_destination import descriptor_of, launch_declared  # noqa: E402

FACTORY = "agent-factory"
AT = "2026-10-22T12:00:00+02:00"
CONVOY = "convoy-panorama"
GRAPH = "sha256:" + "c" * 64

FIRST_REQUEST = "Le critère de la page Usine demande un réglage que la Spec ne fixe pas"
SECOND_REQUEST = "La régression du profil dépasse le plafond de durée de la vérification"
ANSWERED_REQUEST = "Le jeu de données du journal manque une source de logs"


def options() -> str:
    return json.dumps([
        {"lettre": "a", "option": "Corriger par maintenance sur main",
         "consequence": "Le ticket reprend sur la réponse, après la fusion", "recommande": True},
        {"lettre": "b", "option": "Retirer le critère du ticket",
         "consequence": "Le ticket est livré sans ce critère", "recommande": False},
    ], ensure_ascii=False)


def ticket(bead_id: str, title: str, **metadata) -> dict:
    """A ticket of the graph of the chantier, an author at work on it since
    the morning, as the flow writes it: its graph, its rig, the new-flow
    mark, its dispatch and the model of its author."""
    return {"id": bead_id, "title": title, "status": "in_progress", "issue_type": "task",
            "labels": ["approved-ticket-graph", "delivery-plane"], "created_at": "2026-10-22T08:00:00+02:00",
            "updated_at": "2026-10-22T11:00:00+02:00", "dependencies": [], "description": "",
            "metadata": {"gc.graph_digest": GRAPH, "gc.dispatch_rig": FACTORY, "gc.flow.mark": "new-flow/v1",
                         "gc.flow.gate.dispatch": json.dumps({"at": "2026-10-22T08:05:00+02:00"}),
                         "gc.flow.models": json.dumps({"author": {"at": "2026-10-22T08:06:00+02:00",
                                                                  "model": "claude-opus"}}),
                         **metadata}}


def request(what: str, asked: str) -> dict:
    """The fields the escalation door writes on a ticket when it asks
    Benjamin, blocking, at `asked`."""
    return {"gc.needs_benjamin": what, "gc.escalation_bloquant": "true", "gc.escalation_horodatage": asked,
            "gc.escalation_pourquoi": "L’auteur ne peut pas livrer le critère sans ta réponse.",
            "gc.escalation_que_faire": options(), "gc.escalation_mayor_paged_at": "none"}


def text(fragment: str) -> str:
    """The text of an HTML fragment on one line, spaces collapsed."""
    fragment = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def numbers_of_decisions(said: str) -> list[int]:
    """Every number a text gives of decisions or requests: « 2 décisions »,
    « 1 demande ouverte », « À toi de jouer · 2 »."""
    found = [int(n) for n in re.findall(r"(?i)\b(\d+)\s+(?:décisions?|demandes?)\b", said)]
    return found + [int(n) for n in re.findall(r"(?i)à toi de jouer\s*·\s*(\d+)", said)]


class ChantierDecisions(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def page(self, address: str, path: str) -> str:
        code, _, body = fetch(address + path)
        self.assertEqual(200, code, f"{path} answered {code}")
        return body

    # --- Criterion 1 ------------------------------------------------------------

    def test_an_open_request_on_a_ticket_of_a_chantier_counts_the_same_on_the_home_the_run_and_the_project(self):
        beads = [
            {"id": "spec-panorama", "title": "Spec — Cockpit Panorama", "status": "in_progress", "issue_type": "task",
             "labels": [], "created_at": "2026-10-20T10:00:00+02:00", "dependencies": [], "description": "",
             "metadata": {"gc.project_id": FACTORY, "spec_state": "APPROVED_SPEC"}},
            {"id": CONVOY, "title": "Cockpit Panorama", "status": "open", "issue_type": "convoy",
             "labels": ["approved-ticket-graph"], "created_at": "2026-10-21T10:00:00+02:00", "dependencies": [],
             "description": "",
             "metadata": {"gc.project_id": FACTORY, "gc.graph_digest": GRAPH, "gc.spec_id": "spec-panorama",
                          "gc.flow.mark": "new-flow/v1"}},
            ticket("ticket-usine", "Usine — réglages", **request(FIRST_REQUEST, "2026-10-22T10:30:00+02:00")),
            ticket("ticket-runs", "Runs — sessions", **request(SECOND_REQUEST, "2026-10-22T10:45:00+02:00")),
            # A request Benjamin already answered: nothing waits on it.
            ticket("ticket-journal", "Journal — logs", **{
                **request(ANSWERED_REQUEST, "2026-10-22T09:00:00+02:00"), "gc.needs_benjamin": "none",
                "gc.escalation_response_at": "2026-10-22T09:20:00+02:00", "gc.escalation_response_option": "a"}),
            ticket("ticket-analyses", "Analyses — courbes"),
        ]
        dataset = {"generated_at": AT, "synthetic": True, "ui": {"id": "chantier-decisions", "page": "projects"},
                   "projects": [descriptor_of(self.tree, FACTORY)], "repos": {},
                   "tracker": {"beads": {bead["id"]: bead for bead in beads}}}
        address = launch_declared(self.tree, "chantier-decisions", dataset)

        # The home: two decisions to take, the two open requests listed.
        home = self.page(address, "/")
        indicator = re.search(r"(?is)Décisions à prendre(.{0,400}?)Maintenant · demandes ouvertes", text(home))
        self.assertIsNotNone(indicator, f"the home shows no indicator « Décisions à prendre »: {text(home)[:600]}")
        self.assertEqual(["2"], re.findall(r"\b\d+\b", indicator.group(1)),
                         f"the indicator « Décisions à prendre » does not say 2: « {indicator.group(0)} »")
        inbox = re.search(r'(?is)<div class="pn-inbox"[^>]*>(.*)', home)
        self.assertIsNotNone(inbox, "the home shows no inbox")
        for what in (FIRST_REQUEST, SECOND_REQUEST):
            self.assertIn(what, text(inbox.group(1)), f"the open request « {what} » is not among the home's decisions")
        self.assertNotIn(ANSWERED_REQUEST, text(inbox.group(1)), "a request already answered is among the decisions")

        # The run of the chantier: waiting for Benjamin, two decisions.
        run = self.page(address, f"/runs/run?id={CONVOY}")
        head = re.search(r'(?is)<div class="pn-head rn-head">(.*?)<section\b', run)
        self.assertIsNotNone(head, f"the run of the chantier has no head: {text(run)[:600]}")
        said = text(head.group(1))
        self.assertIn("Ta décision", said, f"the run of the chantier does not wait for Benjamin: « {said} »")
        self.assertEqual([2], numbers_of_decisions(said),
                         f"the head of the run does not say the 2 decisions of the chantier: « {said} »")

        # The page of the project: its counter and the card of its chantier.
        project = text(self.page(address, f"/projet/{FACTORY}"))
        counter = re.findall(r"(\S+)\s+Décisions attendues", project)
        self.assertEqual(["2"], counter, f"the counter « Décisions attendues » does not say 2: {counter}")
        card = re.search(r"(?s)CHANTIER ACTUEL(.*?)(?:ROADMAP|DERNIER CHANGEMENT|RESSOURCES|$)", project)
        self.assertIsNotNone(card, f"the page of the project shows no card « Chantier actuel »: {project[:800]}")
        self.assertIn("Cockpit Panorama", card.group(1), f"the card is not the chantier's: « {card.group(1)} »")
        self.assertNotIn("Aucune décision attendue", card.group(1),
                         "the card of the chantier says no decision waits while two requests are open on its tickets")
        self.assertEqual([2], numbers_of_decisions(card.group(1)),
                         f"the card of the chantier does not say its 2 decisions: « {card.group(1)} »")


if __name__ == "__main__":
    unittest.main()
