#!/usr/bin/env python3
"""Criterion test 1 of B « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-4uzgzm; Spec af-fgcw0d, user
stories 27, 29 and 34, Testing Decisions 1, 3 and 8), its second half: the
gestures Pour moi lacked -- refuse a proposal with a reason, put it off,
relaunch a session the Factory paused --, each confirmed, then traced at
its source.

The datasets the criterion names, home-content-full and home-long, hold no
proposal and no paused session: each case launches the real cockpit with
the launcher of the profile, bin/project-launch, on a dataset that carries
a tracker as the doors of the Factory write it (pour_moi.serve_tracker): a
proposal of class decision as bin/proposal-door (create) leaves it, a
session the loop guard of the Factory paused (its bead, the Mayor paged
first by bin/escalation-door), and a question as bin/escalation-door
(benjamin) leaves it. The doors of that launch act on that tracker as the
doors of the Factory do.

Each gesture is done at GET / as a person does it, in a headless Chromium
(pour_moi.walk) behind the identity proxy of the host: the line of the
request activated in « Ce qui t’attend », the gesture activated, then
« Confirmer ». Before « Confirmer », the cockpit is read (GET /api/requests,
GET /api/journal, from the page): nothing was written, the request is
still waiting. After it, the source says what was done: the journal of the
requests resolved at their source holds the refusal and its reason, or the
relaunch; the tracker as the cockpit reads it at its source (GET
/api/status) holds the time a proposal is put off until; the request has
left « Ce qui t’attend ».

False if a gesture stays under the technical details, or if a gesture that
changes the Factory goes without its confirmation.

Only a session is relaunched here: nothing in the Factory pauses an order
yet (no door writes an order paused), so no tracker can hold one as written.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import (  # noqa: E402
    LEGACY_SUMMARY, control, escalation, journal_of, paused_session, proposal, read_json, requests_of,
    serve_tracker, wait_for, walk,
)

AT = "2026-10-12T08:00:00Z"
PROPOSAL = "af-p7k2m"
PROPOSAL_QUOI = "Ajouter un export des notes en CSV"
SESSION_BEAD = "af-s4l9q"
SESSION = "delivery-author-af-wisp-x1y2z3"
QUESTION = "af-q8n3v"
TRACKER = {
    PROPOSAL: proposal(PROPOSAL_QUOI, "Plusieurs lecteurs demandent à garder leurs notes hors du projet.", [
        {"lettre": "a", "option": "Ajouter l’export", "consequence": "un ticket de carte est préparé",
         "recommande": True, "raison": "la demande revient souvent"},
        {"lettre": "b", "option": "Ne rien faire", "consequence": "les notes restent dans le projet"},
    ], AT),
    SESSION_BEAD: paused_session(SESSION, 14, AT),
    QUESTION: escalation("Choisir le nom de la page d’accueil", "Le projet attend ton choix.", [
        {"lettre": "a", "option": "Accueil", "consequence": "le menu dit Accueil", "recommande": True,
         "raison": "c’est le mot le plus court"},
        {"lettre": "b", "option": "Tableau de bord", "consequence": "le menu dit Tableau de bord"},
    ], AT, "notes"),
}
REASON = "Les notes restent dans le projet pour cette version."
# The delay a proposal is put off by, among those the cockpit offers.
UNTIL = "Demain 09:00"
CONFIRM = "Confirmer"
# How long the source may take to say what a gesture did, once confirmed.
TRACED_SECONDS = 20
PARIS = ZoneInfo("Europe/Paris")
# What bin/proposal-door (reporter) leaves on the proposal it puts off: the
# time until which it is put off.
REPORT_UNTIL = "gc.proposal_report_until"


def tracker_read(address: str) -> tuple[dict, float]:
    """The beads of the tracker as the cockpit last read them at their
    source (GET /api/status), by their id, and when it read them."""
    beads = read_json(address, "/api/status").get("beads") or {}
    return {b.get("id"): b for b in beads.get("value") or [] if isinstance(b, dict)}, beads.get("read_at") or 0.0


class PourMoiGestures(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def launched(self, bead_id: str) -> tuple[str, str]:
        """The cockpit on the tracker, and the title its « Ce qui t’attend »
        gives the request of `bead_id`."""
        address = serve_tracker(self.tree, TRACKER)
        requests = wait_for(lambda: requests_of(address), lambda found: any(r["id"] == bead_id for r in found), 20)
        mine = [r for r in requests if r["id"] == bead_id]
        self.assertEqual(1, len(mine), f"« Ce qui t’attend » does not list {bead_id}: {[r['id'] for r in requests]}")
        return address, mine[0]["quoi"]

    def walked(self, address: str, line: str, gesture: list[dict]) -> list[dict]:
        """The request of `line` opened, then the steps of `gesture` up to
        the confirmation; the cockpit read from the page; « Confirmer ».
        Returns the steps walked, each found."""
        steps = [{"click": line}, *gesture,
                 {"fetch": "/api/requests"}, {"fetch": "/api/journal"}, {"click": CONFIRM, "wait": 4000}]
        walked = walk(address, steps)["steps"]
        for number, (step, done) in enumerate(zip(steps, walked)):
            self.assertTrue(done["found"], f"step {number} {step} found nothing to do; the page shows "
                                           f"{[c['name'] for c in done['page']['controls']]}")
        self.assertEqual(len(steps), len(walked), "the walk stopped before its end")
        return walked

    def assert_unfolded(self, page: dict, name: str) -> None:
        """The control `name` is shown, usable, and held by no folded part."""
        found = control(page, name)
        self.assertIsNotNone(found, f"no « {name} » on the request open: {[c['name'] for c in page['controls']]}")
        self.assertFalse(found["disabled"], f"« {name} » cannot be used")
        self.assertNotIn(LEGACY_SUMMARY, found["folds"], f"« {name} » is still under « {LEGACY_SUMMARY} »")
        self.assertEqual([], found["folds"], f"« {name} » is reached only by unfolding {found['folds']}")

    def assert_nothing_written_before(self, walked: list[dict], bead_id: str) -> None:
        """Before « Confirmer »: the cockpit asked for it, the request still
        waits, the journal holds nothing of it."""
        requests, journal, confirmation = walked[-3], walked[-2], walked[-1]
        self.assertIn(bead_id, [r["id"] for r in json.loads(requests["body"])["requests"]],
                      "the request left « Ce qui t’attend » before the gesture was confirmed")
        self.assertEqual([], [e for e in json.loads(journal["body"])["entries"] if e["bead_id"] == bead_id],
                         "the gesture was written before it was confirmed")
        self.assert_unfolded(requests["page"], CONFIRM)

    def assert_left(self, address: str, bead_id: str) -> None:
        requests = wait_for(lambda: requests_of(address), lambda found: all(r["id"] != bead_id for r in found),
                            TRACED_SECONDS)
        self.assertNotIn(bead_id, [r["id"] for r in requests], "the request is still waiting once its gesture is done")

    # --- Criterion 1 ------------------------------------------------------------

    def test_a_proposal_is_refused_with_its_reason_once_confirmed(self):
        address, line = self.launched(PROPOSAL)
        walked = self.walked(address, line, [{"fill": "Raison", "value": REASON}, {"click": "Refuser"}])
        self.assert_unfolded(walked[0]["page"], "Refuser")
        self.assert_nothing_written_before(walked, PROPOSAL)
        journal = wait_for(lambda: journal_of(address), lambda found: any(e["bead_id"] == PROPOSAL for e in found),
                           TRACED_SECONDS)
        refused = [e for e in journal if e["bead_id"] == PROPOSAL]
        self.assertEqual([f"proposition rejetée — {REASON}"], [e["quoi"] for e in refused],
                         "the source does not hold the refusal with its reason, once")
        self.assertEqual(["benjamin"], [e["par"] for e in refused], "the refusal is not the operator's")
        self.assert_left(address, PROPOSAL)

    def test_a_proposal_is_put_off_once_confirmed(self):
        address, line = self.launched(PROPOSAL)
        walked = self.walked(address, line, [{"click": "Reporter"}, {"click": UNTIL}])
        self.assert_unfolded(walked[0]["page"], "Reporter")
        self.assert_nothing_written_before(walked, PROPOSAL)
        self.assert_left(address, PROPOSAL)
        # The source holds the delay: the proposal is put off until
        # tomorrow 09:00 (Paris) by the cockpit's clock -- not only hidden
        # by the page or by the cockpit.
        beads, read_at = wait_for(lambda: tracker_read(address),
                                  lambda read: (read[0].get(PROPOSAL, {}).get("metadata") or {}).get(REPORT_UNTIL),
                                  TRACED_SECONDS)
        until = (beads.get(PROPOSAL, {}).get("metadata") or {}).get(REPORT_UNTIL)
        self.assertTrue(until, f"the source holds no time the proposal is put off until: {beads.get(PROPOSAL)}")
        tomorrow = datetime.fromtimestamp(read_at, PARIS).date() + timedelta(days=1)
        self.assertEqual(datetime.combine(tomorrow, time(9), PARIS), datetime.fromisoformat(until),
                         f"the source puts the proposal off until {until}, not « {UNTIL} »")
        self.assertEqual("open", beads[PROPOSAL].get("status"), "putting the proposal off closed it")
        # Put off is no decision: nothing resolved the proposal.
        self.assertEqual([], [e for e in journal_of(address) if e["bead_id"] == PROPOSAL],
                         "putting the proposal off was written as its decision")

    def test_a_paused_session_is_relaunched_once_confirmed(self):
        address, line = self.launched(SESSION_BEAD)
        walked = self.walked(address, line, [{"click": "Relancer"}])
        self.assert_unfolded(walked[0]["page"], "Relancer")
        self.assert_nothing_written_before(walked, SESSION_BEAD)
        journal = wait_for(lambda: journal_of(address),
                           lambda found: any(e["bead_id"] == SESSION_BEAD for e in found), TRACED_SECONDS)
        relaunched = [e for e in journal if e["bead_id"] == SESSION_BEAD]
        # The journal says a relaunch in its own words, never the name of
        # the gesture: « Relance demandée ».
        self.assertEqual(["Relance demandée"], [e["quoi"] for e in relaunched],
                         "the source does not hold the relaunch, once")
        self.assertEqual("benjamin", relaunched[0]["par"], "the relaunch is not the operator's")
        self.assert_left(address, SESSION_BEAD)


if __name__ == "__main__":
    unittest.main()
