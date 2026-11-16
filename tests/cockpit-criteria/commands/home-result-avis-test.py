#!/usr/bin/env python3
"""Criterion test 2 of A2 « Essai et Avis » (af-ocz64w; Spec af-fgcw0d,
user stories 30, 110, 112, 113 and 114, Implementation Decisions 4 and 6
of af-2zseit kept, Testing Decisions 1 and 8), on the datasets it names:
the cockpit launched, Avis, datasets result-request, result-confirmation
and result-findings.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset, and walks the page it serves at GET /
in a headless Chromium (result_trial.walk), which records what the page
copies for the session.

- On each of the three, once the result to judge is open in « Ce qui
  t’attend », there is one Essai and one Avis, side by side in the bar of
  the result; Avis opens the panel C in the result, its context kept, and
  its actions -- closing it, preparing the message -- in that same bar,
  beside the one Essai: no second Essai, no second Avis.
- Avis prepares « abandonné » only with the reason of the abandon; the
  message prepared carries the words, the reason, the commit and the
  fingerprint of the dossier; changing the draft withdraws the message
  prepared, which can no longer be copied until prepared again; copying it
  records nothing -- the cockpit still serves the result as it was, to
  judge.

The verdict on each proposition, and the answer the session records with
the message copied, are held by home-result-avis-records-test.py, on the
records of the public commands of D01.

False if the cockpit records a judgement itself, says it recorded at the
copy, or offers twice Essai or Avis.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from result_trial import controls, folded, last, result_of, serve, shown, walk  # noqa: E402

# The line of « Ce qui t’attend » that opens the result to judge.
RESULT_LINE = "Le cockpit attend ton avis"
# What the result to judge says, kept while Avis is open.
CONTEXT = "Les nouveaux parcours du cockpit sont prêts."
# The three answers of D01 Avis prepares, and its fields.
ANSWERS = ("Accepté", "Constats rendus", "Abandonné")
WORDS = "Ton avis"
REASON = "Raison de l’abandon"
# The actions of the panel, in the bar of the result.
CLOSE = "Fermer l’avis"
PREPARE = "Continuer avec un agent"
COPY = "Copier pour ma session"
MESSAGE = "Message pour ma session"
NOT_RECORDED = "aucune réponse enregistrée"


def opened_result(*more: dict) -> list[dict]:
    """The steps that open the result to judge, then Avis, then `more`."""
    return [{"click": RESULT_LINE}, {"click": "Avis"}, *more]


class HomeResultAvis(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_found(self, walked: dict) -> None:
        missing = [index for index, step in enumerate(walked["steps"]) if not step["found"]]
        self.assertEqual([], missing, f"a control of the walk is not on the page: {last(walked)['controls']}")

    def enabled(self, page: dict, name: str) -> bool:
        found = controls(page, name)
        self.assertEqual(1, len(found), f"not one « {name} » on the page: {[c['name'] for c in page['controls']]}")
        return not found[0]["disabled"]

    # --- Criterion 2 ------------------------------------------------------------

    def assert_one_essai_and_one_avis_and_avis_in_the_bar(self, dataset: str) -> None:
        """On `dataset`, the result to judge open in « Ce qui t’attend »:
        one Essai and one Avis side by side; Avis open in the result, its
        actions in the same bar as the one Essai."""
        walked = walk(serve(self.tree, dataset), opened_result())
        self.assert_found(walked)
        start, result, avis = walked["start"], walked["steps"][0]["page"], walked["steps"][1]["page"]
        self.assertLessEqual(len(controls(start, "Essai")), 1, "Essai is offered twice")
        self.assertLessEqual(len(controls(start, "Avis")), 1, "Avis is offered twice")

        # The result open: one Essai, one Avis, side by side.
        essai, entry = controls(result, "Essai"), controls(result, "Avis")
        self.assertEqual((1, 1), (len(essai), len(entry)), "the result has not one Essai and one Avis")
        self.assertEqual([False, False], [essai[0]["disabled"], entry[0]["disabled"]],
                         "Essai or Avis cannot be used on a result to judge")
        self.assertEqual(essai[0]["holder"], entry[0]["holder"], "Essai and Avis are not at the same level")

        # Avis open: the panel in the result, its context kept, its
        # actions in the same bar as the one Essai.
        self.assertIn(CONTEXT, shown(avis), "the result is no longer shown beside Avis")
        self.assertEqual(1, len(controls(avis, "Essai")), "Avis open, Essai is not offered once")
        self.assertEqual([], controls(avis, "Avis"), "Avis open, a second entry Avis is offered")
        bar = {c["name"]: c["holder"] for c in avis["controls"] if c["name"] in (CLOSE, PREPARE)}
        self.assertEqual({CLOSE: essai[0]["holder"], PREPARE: essai[0]["holder"]}, bar,
                         "the actions of Avis are not in the bar of the result")
        self.assertEqual([True], [c["field"] for c in controls(avis, WORDS)], f"Avis has no field « {WORDS} »")
        self.assertEqual([[name] for name in ANSWERS], [[c["name"] for c in controls(avis, name)] for name in ANSWERS],
                         "Avis does not offer the three answers of D01")

    def test_result_request_offers_one_essai_and_one_avis_at_the_same_level_and_avis_opens_in_the_bar(self):
        self.assert_one_essai_and_one_avis_and_avis_in_the_bar("result-request")

    def test_result_confirmation_offers_one_essai_and_one_avis_at_the_same_level_and_avis_opens_in_the_bar(self):
        self.assert_one_essai_and_one_avis_and_avis_in_the_bar("result-confirmation")

    def test_result_findings_offers_one_essai_and_one_avis_at_the_same_level_and_avis_opens_in_the_bar(self):
        self.assert_one_essai_and_one_avis_and_avis_in_the_bar("result-findings")

    def test_abandon_needs_its_reason_a_changed_draft_withdraws_the_message_and_copying_records_nothing(self):
        address = serve(self.tree, "result-findings")
        chantier, before = result_of(address)
        first, second = "Le besoin a changé depuis la Spec.", "Le besoin a disparu avec la version 2."
        reason = "Une autre version du tableau remplace ce chantier."
        walked = walk(address, opened_result(
            {"fill": WORDS, "value": first}, {"check": "Abandonné"},     # 2, 3: no reason yet
            {"fill": REASON, "value": reason},                            # 4
            {"click": PREPARE},                                           # 5: prepared
            {"fill": WORDS, "value": second},                             # 6: the draft changed
            {"click": PREPARE},                                           # 7: prepared again
            {"click": COPY},                                              # 8: copied
        ))
        self.assert_found(walked)
        pages = [step["page"] for step in walked["steps"]]

        self.assertFalse(self.enabled(pages[3], PREPARE), "« abandonné » is prepared without its reason")
        self.assertTrue(self.enabled(pages[4], PREPARE), "« abandonné » with its reason cannot be prepared")

        prepared = pages[5]
        self.assertIn(NOT_RECORDED, shown(prepared), "the message prepared is not said unrecorded")
        [message] = folded(prepared, MESSAGE)
        for said in (first, reason, before["commit"], before["pack"]):
            self.assertIn(said, message, f"the message prepared does not carry « {said} »")
        self.assertTrue(self.enabled(prepared, COPY), "the message prepared cannot be copied")

        changed = pages[6]
        self.assertEqual([], [c for c in controls(changed, COPY) if not c["disabled"]],
                         "the draft changed, the message prepared before can still be copied")
        self.assertEqual([], [text for text in folded(changed, MESSAGE) if first in text],
                         "the draft changed, the message prepared before is still offered")
        self.assertEqual([], changed["copied"], "a message was copied before it was asked")

        again = pages[7]
        [message] = folded(again, MESSAGE)
        self.assertIn(second, message, "the message prepared again does not carry the new words")
        self.assertNotIn(first, message, "the message prepared again carries the words withdrawn")

        copied = pages[8]
        self.assertEqual(1, len(copied["copied"]), "copying did not copy one message")
        self.assertIn(second, copied["copied"][0])
        self.assertIn(reason, copied["copied"][0])
        self.assertNotIn(first, copied["copied"][0], "the message copied carries the words withdrawn")
        text = shown(copied)
        self.assertIn(NOT_RECORDED, text, "the copy is not said unrecorded")
        self.assertNotRegex(text, r"(?i)(?<!aucune )réponse enregistrée", "the copy is said recorded")
        # Nothing recorded: the cockpit serves the result as before, to judge.
        self.assertEqual((chantier, before), result_of(address), "the cockpit recorded something at the copy")


if __name__ == "__main__":
    unittest.main()
