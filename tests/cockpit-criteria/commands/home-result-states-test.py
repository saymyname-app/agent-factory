#!/usr/bin/env python3
"""Criterion test 1 of A1 « Vue d’ensemble — résultat réel lu depuis le
flux, sans faux blocage » (af-c662qx; Spec af-fgcw0d, user stories 44, 108,
111, 117, 119, 120, 123 and 136, Testing Decisions 1 and 5): the states
result-ready, result-dossier, result-accepted, result-merging,
result-merged, result-abandoned and result-outdated of the Validated
Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-home).

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET / as a headless Chromium renders
it (home_destination.measure). It holds the result open in « Ce qui
t’attend » (`panel-3`) to the issue of its state, said in the words of the
reference, and the project of the result (its line under « Projets ») to
the same issue.

In every state Essai and Avis are there, under every other part of the
result: usable on a result to judge (A2, which holds what they do), and
otherwise unavailable, each state saying why: its dossier is outdated, or
the result is already judged (accepted, merging, merged, abandoned). A
control that is absent is not one that is unavailable.

False if a Delivered result on an open convoy is shown blocked, a closed
ticket is shown merged, an abandon lets one believe in a merge, or Essai or
Avis looks usable where it is not.

Two places where the reference is not followed, both rendering defects the
Spec asks to correct (Testing Decisions 5, « incohérences entre vues »;
user stories 119 and 120):
- the reference leaves the line of the project at « À juger » once the
  result is accepted, merging, merged or abandoned, and the request « Le
  cockpit attend ton avis · résultat prêt » in « Ce qui t’attend »: the
  two parts of the page contradict the result; here they say its issue;
- the reference draws result-outdated exactly as result-ready, and
  result-abandoned without its reason: here the dossier is said outdated,
  and the abandon keeps its reason.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, assert_says, measure, says  # noqa: E402

# The project of the result, and its chantier, in every result-* state.
PROJECT = "Usine"
CHANTIER = "Reprise du cockpit"
# The resources of the result to judge, above its bar, as the reference
# draws result-ready: label, then detail.
READY_RESOURCES = ("Ce qui a été livré", "Changements et version à essayer", "Vérifications et preuves",
                   "Parcours, tests et relecture", "Ce qui reste à vérifier", "Version et sources")
# The parts of the dossier, above its bar, as the reference draws
# result-dossier.
DOSSIER_PARTS = ("Dossier du résultat", "Reprise complète du cockpit · version 1", "Parcours et relecture",
                 "Pièces et version")
# Why Essai and Avis cannot be used on an outdated dossier, and on a result
# already judged.
OUTDATED = "périmé"
JUDGED = "déjà jugé"
# The part of a result judged that holds its follow-up, above its bar.
HISTORY = "Historique et preuves"


class HomeResultStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def served(self, dataset: str, click: str | None = None) -> dict:
        """The page at GET / of the cockpit launched on `dataset`, 1440 px
        wide, dark; with `click`, the control of that name activated, the
        page read again under `after`."""
        address = self.tree.launch(dataset)
        return measure(address, click=click)[0]

    # --- what every result is held to ---------------------------------------

    def project_line(self, page: dict) -> str:
        """The line of the project of the result under « Projets », on one
        line: the row inside `rows-1` that starts with its name."""
        rows = [anchor["name"] for anchor in page["anchors"]
                if re.fullmatch(r"row-\d+", anchor["name"]) and "rows-1" in anchor["chain"]]
        lines = [says(page, row) for row in rows if says(page, row).startswith(PROJECT)]
        self.assertEqual(1, len(lines), f"not one line of the project {PROJECT} under « Projets »: {lines}")
        return lines[0]

    def assert_issue(self, page: dict, stage: str) -> None:
        """The project of the result says the issue of its chantier, the
        stage `stage`, and never that it is blocked."""
        self.assertIn(f"{CHANTIER} · {stage}", self.project_line(page),
                      "the line of the project does not say the issue of its result")
        self.assertNotRegex(page["text"], r"(?i)bloqué", "the result is shown blocked")

    def requests_ready(self, page: dict) -> list[str]:
        """The lines of « Ce qui t’attend » that ask for the judgement of a
        result ready."""
        lines = [anchor["name"] for anchor in page["anchors"] if re.fullmatch(r"request-\d+", anchor["name"])]
        return [says(page, line) for line in lines if "résultat prêt" in says(page, line)]

    def assert_above_the_bar(self, page: dict, *resources: str) -> None:
        """The result has its bar of actions, Essai then Avis, and every
        other part of the result -- `resources` among them -- above it: in
        the result, nothing comes after the bar."""
        assert_says(self, page, "panel-3", *resources)
        inside = [anchor["name"] for anchor in page["anchors"] if "panel-3" in anchor["chain"]]
        self.assertIn("actions-possibles-1", inside, "the result has no bar of actions")
        after_bar = [name for name in inside[inside.index("actions-possibles-1") + 1:]
                     if "actions-possibles-1" not in next(a["chain"] for a in page["anchors"] if a["name"] == name)]
        self.assertEqual([], after_bar, "a part of the result comes below its bar of actions")
        bar = says(page, "actions-possibles-1")
        self.assertTrue("Essai" in bar and "Avis" in bar and bar.index("Essai") < bar.index("Avis"),
                        f"the bar does not hold Essai, then Avis; it says « {bar} »")

    def assert_usable(self, page: dict) -> None:
        """Essai and Avis are there, once each, and can be used."""
        actions = [c for c in page["controls"] if c["name"].startswith("Essai") or c["name"] == "Avis"]
        self.assertEqual([("Essai", False), ("Avis", False)],
                         [("Essai" if c["name"].startswith("Essai") else "Avis", c["disabled"]) for c in actions],
                         "the result to judge has not one usable Essai and one usable Avis")

    def assert_unavailable(self, page: dict, reason: str) -> None:
        """Essai and Avis are there, once each, and cannot be used; the bar
        says why, in the words `reason`. A control that is absent is not
        one that is unavailable."""
        actions = [c for c in page["controls"] if c["name"].startswith("Essai") or c["name"] == "Avis"]
        self.assertEqual(["Essai", "Avis"], [("Essai" if c["name"].startswith("Essai") else "Avis") for c in actions],
                         "the result has not one Essai and one Avis")
        self.assertEqual([], [c["name"] for c in actions if not c["disabled"]], "Essai or Avis looks usable")
        assert_says(self, page, "actions-possibles-1", reason)

    def history(self, dataset: str) -> tuple[dict, str]:
        """The page of `dataset`, and the text of its result once
        « Historique et preuves » is opened."""
        page = self.served(dataset, click=HISTORY)
        self.assertTrue(page["after"]["found"], f"the result has no « {HISTORY} »")
        return page, says(page["after"], "panel-3")

    # --- Criterion 1 ------------------------------------------------------------

    def test_result_ready_is_to_judge_with_its_dossier_above_the_bar(self):
        page = self.served("result-ready")
        assert_says(self, page, "panel-3", f"{PROJECT} · {CHANTIER}", "Le cockpit attend ton avis",
                    "Les nouveaux parcours du cockpit sont prêts.")
        self.assert_above_the_bar(page, *READY_RESOURCES)
        self.assert_usable(page)
        self.assert_issue(page, "À juger")
        self.assertEqual(1, len(self.requests_ready(page)),
                         "« Ce qui t’attend » does not ask for the judgement of the result ready")

    def test_result_dossier_shows_the_dossier_above_the_bar(self):
        page = self.served("result-dossier")
        assert_says(self, page, "panel-3", f"{PROJECT} · {CHANTIER}", "Le cockpit attend ton avis")
        self.assert_above_the_bar(page, *DOSSIER_PARTS)
        self.assert_usable(page)
        self.assert_issue(page, "À juger")

    def test_result_accepted_says_accepted_and_the_merge_pending(self):
        page, history = self.history("result-accepted")
        assert_says(self, page, "panel-3", f"{PROJECT} · {CHANTIER}", "Suivi du résultat",
                    "Tu as accepté. La fusion est en attente.")
        self.assertIn("Réponse enregistrée", history)
        self.assertIn("Aucune preuve de fusion à ce stade.", history)
        self.assertNotIn("Fusion confirmée", history, "an accepted result is shown merged")
        self.assert_above_the_bar(page, HISTORY)
        self.assert_unavailable(page, JUDGED)
        self.assert_issue(page, "Accepté")
        self.assertEqual([], self.requests_ready(page), "the result accepted is still asked to be judged")

    def test_result_merging_says_the_merge_under_way(self):
        page, history = self.history("result-merging")
        assert_says(self, page, "panel-3", "Suivi du résultat", "La fusion est en cours.")
        self.assertIn("Aucune preuve de fusion à ce stade.", history)
        self.assertNotIn("Fusion confirmée", history, "a merge under way is shown confirmed")
        self.assert_above_the_bar(page, HISTORY)
        self.assert_unavailable(page, JUDGED)
        self.assert_issue(page, "Fusion en cours")
        self.assertEqual([], self.requests_ready(page), "the result merging is still asked to be judged")

    def test_result_merged_says_the_merge_confirmed_by_its_proof(self):
        page, history = self.history("result-merged")
        assert_says(self, page, "panel-3", "Suivi du résultat", "La fusion est confirmée.")
        # The proof of the merge: the result judged, and the commit merged.
        self.assertIn("Fusion confirmée · résultat jugé 1111111 → commit fusionné 2222222", history)
        self.assert_above_the_bar(page, HISTORY)
        self.assert_unavailable(page, JUDGED)
        self.assert_issue(page, "Fusionné")
        self.assertEqual([], self.requests_ready(page), "the result merged is still asked to be judged")

    def test_result_abandoned_says_nothing_was_merged_and_keeps_its_reason(self):
        page, history = self.history("result-abandoned")
        assert_says(self, page, "panel-3", "Suivi du résultat", "Chantier abandonné. Rien n’a été fusionné.")
        # Its reason is kept: « Raison », then the words given.
        self.assertRegex(history, r"Raison\s*:\s*\S.{3,}", "the abandon does not keep its reason")
        for merge in ("Fusion confirmée", "commit fusionné", "La fusion est"):
            self.assertNotIn(merge, history, "an abandon lets one believe in a merge")
        # An abandon merges nothing, legitimately: not an inconsistency.
        self.assertNotRegex(page["after"]["text"], r"(?i)incohéren", "an abandon without merge is shown as an anomaly")
        self.assert_above_the_bar(page, HISTORY)
        self.assert_unavailable(page, JUDGED)
        self.assert_issue(page, "Abandonné")
        self.assertEqual([], self.requests_ready(page), "the result abandoned is still asked to be judged")

    def test_result_outdated_says_its_dossier_is_outdated_and_offers_nothing(self):
        page = self.served("result-outdated")
        assert_says(self, page, "panel-3", f"{PROJECT} · {CHANTIER}")
        self.assertRegex(says(page, "panel-3"), r"(?i)dossier périmé", "the result does not say its dossier is outdated")
        self.assert_above_the_bar(page)
        self.assert_unavailable(page, OUTDATED)
        self.assertNotRegex(page["text"], r"(?i)bloqué", "the result is shown blocked")


if __name__ == "__main__":
    unittest.main()
