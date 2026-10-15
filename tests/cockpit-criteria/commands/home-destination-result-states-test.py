#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02, af-0gonc9; Spec af-2zseit, user stories 111 and 147,
Testing Decisions 1 and 5): the fourteen states result-* of its reference,
the contextual panels of a result on the same destination (their datasets
say ui.page=home: they are no second page).

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET / as a headless Chromium renders
it, held to the Validated Prototype (prototype/cockpit-b-zones-20261012 at
632deea, prototypes/c01-complete/frozen-panorama-home): the named parts of
the state with their elements and holders, the navigation B with this
destination open, and what the panel of the result says.

False if a state is omitted, if a result is shown on a page of its own
instead of the destination at GET /, or if a command not wired to its
door looks done: in the isolated cockpit every door that changes the
Factory refuses, so a confirmed choice that the page shows as answered
while the request stays open at its source is a false success.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402
    CONTENT_PARTS, LaunchTree, assert_destination, assert_inbox_follows_requests, assert_says, fetch, measure,
)


def without(parts: dict, *names: str) -> dict:
    return {name: value for name, value in parts.items() if name not in names}


# The follow-up of a result already judged: the panel says where the result
# is, with its history; no resource list and no Essai/Avis bar.
FOLLOW_UP_PARTS = without(CONTENT_PARTS, "resource-list-1", "actions-possibles-1")
# The dossier open in the panel: its lines (`row-1`, with a tag) take the
# place of the resource list; the rows of the projects follow, numbered on.
DOSSIER_PARTS = {
    **without(CONTENT_PARTS, "resource-list-1", "row-1", "row-2", "row-3", "small-stats-1", "release-info-1",
              "small-stats-2", "release-info-2", "small-stats-3", "release-info-3"),
    "row-1": ("div", "panel-3"), "tag-1": ("span", "row-1"),
    "row-2": ("div", "rows-1"), "small-stats-1": ("div", "row-2"), "release-info-1": ("div", "row-2"),
    "row-3": ("div", "rows-1"), "small-stats-2": ("div", "row-3"), "release-info-2": ("div", "row-3"),
    "row-4": ("div", "rows-1"), "small-stats-3": ("div", "row-4"), "release-info-3": ("div", "row-4"),
}
# A decision request open in the panel: its options in a bar of their own.
REQUEST_PARTS = {**FOLLOW_UP_PARTS, "actions-1": ("div", "panel-3")}
# The same, an option chosen: the confirmation under the options.
CONFIRMATION_PARTS = {**REQUEST_PARTS, "notice-1": ("div", "panel-3")}


class HomeDestinationResultStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def served(self, dataset: str, **options) -> tuple[str, dict]:
        """The address of the cockpit launched on `dataset`, and its page at
        GET / at 1440 px."""
        address = self.tree.launch(dataset)
        return address, measure(address, **options)[0]

    def assert_result_to_judge(self, address: str, page: dict) -> None:
        """The result ready to judge, as the reference shows it in the
        panel: what was delivered above, Essai and Avis in its bar, once."""
        assert_destination(self, page, CONTENT_PARTS)
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Usine · Reprise du cockpit", "Le cockpit attend ton avis",
                    "Les nouveaux parcours du cockpit sont prêts.")
        assert_says(self, page, "resource-list-1", "Ce qui a été livré", "Vérifications et preuves",
                    "Ce qui reste à vérifier", "Version et sources")
        assert_says(self, page, "actions-possibles-1", "Essai", "Avis")
        self.assertEqual(
            (1, 1),
            (sum(c["name"].startswith("Essai") for c in page["controls"]),
             sum(c["name"] == "Avis" for c in page["controls"])),
            "the page has not exactly one Essai and one Avis",
        )

    def assert_follow_up(self, address: str, page: dict, where: str) -> None:
        """A result already judged: the panel says where it is and keeps its
        history and proofs; nothing offers to judge it again."""
        assert_destination(self, page, FOLLOW_UP_PARTS)
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Usine · Reprise du cockpit", "Suivi du résultat", where,
                    "Historique et preuves")
        self.assertEqual([], [c["name"] for c in page["controls"] if c["name"].startswith("Essai") or c["name"] == "Avis"],
                         "a result already judged offers Essai or Avis")

    # Criterion 1 ---------------------------------------------------------

    def test_result_ready_is_the_result_to_judge_in_the_destination(self):
        address, page = self.served("result-ready")
        self.assert_result_to_judge(address, page)

    def test_result_findings_is_the_result_to_judge_in_the_destination(self):
        # The reference draws this state as result-ready.
        address, page = self.served("result-findings")
        self.assert_result_to_judge(address, page)

    def test_result_outdated_is_the_result_to_judge_in_the_destination(self):
        # The reference draws this state as result-ready.
        address, page = self.served("result-outdated")
        self.assert_result_to_judge(address, page)

    def test_result_outage_is_the_result_to_judge_in_the_destination(self):
        # The reference draws this state as result-ready.
        address, page = self.served("result-outage")
        self.assert_result_to_judge(address, page)

    def test_result_dossier_opens_the_dossier_of_the_result_in_its_panel(self):
        address, page = self.served("result-dossier")
        assert_destination(self, page, DOSSIER_PARTS)
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Usine · Reprise du cockpit", "Le cockpit attend ton avis",
                    "Dossier du résultat", "Reprise complète du cockpit · version 1")
        assert_says(self, page, "row-1", "Parcours et relecture", "Vérifiés · exemple")
        assert_says(self, page, "panel-3", "Pièces et version")
        assert_says(self, page, "actions-possibles-1", "Essai", "Avis")
        assert_says(self, page, "row-2", "Usine", "Reprise du cockpit · À juger")

    def test_result_returned_says_the_findings_were_returned(self):
        address, page = self.served("result-returned")
        self.assert_follow_up(address, page, "Tes constats ont été rendus.")

    def test_result_repairing_says_the_factory_repairs_the_findings(self):
        address, page = self.served("result-repairing")
        self.assert_follow_up(address, page, "L’usine corrige tes constats.")

    def test_result_accepted_says_the_merge_is_pending(self):
        address, page = self.served("result-accepted")
        self.assert_follow_up(address, page, "Tu as accepté. La fusion est en attente.")

    def test_result_merging_says_the_merge_is_under_way(self):
        address, page = self.served("result-merging")
        self.assert_follow_up(address, page, "La fusion est en cours.")

    def test_result_merged_says_the_merge_is_confirmed(self):
        address, page = self.served("result-merged")
        self.assert_follow_up(address, page, "La fusion est confirmée.")

    def test_result_conflict_says_the_acceptance_was_cancelled(self):
        address, page = self.served("result-conflict")
        self.assert_follow_up(address, page, "Acceptation annulée. Correction puis nouveau jugement.")

    def test_result_abandoned_says_nothing_was_merged(self):
        address, page = self.served("result-abandoned")
        self.assert_follow_up(address, page, "Chantier abandonné. Rien n’a été fusionné.")

    def test_result_request_opens_the_decision_with_its_options(self):
        address, page = self.served("result-request")
        assert_destination(self, page, REQUEST_PARTS)
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Notes · décision attendue", "Quel format d’export ?",
                    "Le projet attend ton choix.", "Contexte et ressources")
        assert_says(self, page, "actions-1", "CSV", "JSON")

    def test_result_confirmation_asks_to_confirm_and_never_shows_an_unrecorded_answer_as_given(self):
        address, page = self.served("result-confirmation", click="Confirmer")
        assert_destination(self, page, CONFIRMATION_PARTS)
        assert_inbox_follows_requests(self, address, page)
        assert_says(self, page, "panel-3", "Notes · décision attendue", "Quel format d’export ?")
        assert_says(self, page, "actions-1", "CSV", "JSON")
        assert_says(self, page, "notice-1", "Choix CSV préparé.", "Confirmer", "Annuler")

        # « Confirmer » activated: the door that would record the answer
        # refuses in the isolated cockpit, so the request stays open at its
        # source, and the page does not say it was answered.
        after = page["after"]
        self.assertTrue(after["found"], "no control « Confirmer » to activate")
        code, _, body = fetch(address + "/api/requests")
        self.assertEqual(200, code)
        self.assertIn("Choisir le format d’export", [r["quoi"] for r in json.loads(body)["requests"]])
        claimed = [word for word in ("répondu", "Réponse enregistrée", "enregistrée", "envoyée")
                   if word.lower() in after["text"].lower()]
        self.assertEqual([], claimed, f"the page shows an answer that was not recorded: « {after['text'][:400]} »")


if __name__ == "__main__":
    unittest.main()
