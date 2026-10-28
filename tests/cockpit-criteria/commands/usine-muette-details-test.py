#!/usr/bin/env python3
"""Criterion test 3 of B « Pour moi au premier plan, gestes complets et
commandes qui n'échouent plus en silence » (af-4uzgzm; Spec af-fgcw0d, user
stories 6, 73 and 75, Testing Decisions 1, 3 and 8): a Factory that falls
silent is an Urgent request « usine muette »; the main texts of « Ce qui
t’attend » are French, without an identifier or an internal term; its
folded details give the identifiers, links and original text.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset:

- home-offline: the supervisor is read once, then answers no more -- the
  heartbeat goes out only on fresh readings, so it stops;
- home-loading: nothing is ever read -- no heartbeat goes out;
- a tracker as bin/escalation-door (benjamin) leaves a question whose
  producer wrote an identifier in its words, and others whose producers
  wrote English, German and Spanish (pour_moi.serve_tracker).

The silence is waited for longer than the threshold of the launch: the
request « usine muette » is read at GET /api/requests, Urgent, and on the
page at GET / as a headless Chromium shows it (pour_moi.walk). The folded
details are read in the HTML served (pour_moi.folded), apart from the old
zone « Détails techniques et actions ».

A main text is French: no request of « Ce qui t’attend » says a sentence
told English by its grammatical words (« the », « is », « your »…), and
the words a producer wrote in another language than French are not shown
as main text.

On each dataset, every request of « Ce qui t’attend » has its folded
details, which give its identifier and at least one link.

False if the silent Factory is not Urgent, or an internal identifier shows
in a main text.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from pour_moi import escalation, folded, requests_of, serve_tracker, visible_text, wait_for, walk  # noqa: E402

MUETTE = re.compile(r"(?i)usine muette")
# Longer than the silence the launch waits before saying the Factory muette.
SILENCE_SECONDS = 40
# What a main text never shows (user story 73): an identifier of the
# tracker or of a pull request, an internal term.
IDENTIFIER = re.compile(r"\baf-[a-z0-9]{3,}\b|(?<![\w&])#\d+\b|\bsynthetic-[\w-]+")
INTERNAL_TERM = re.compile(r"(?i)\b(?:beads?|convoys?|orders?|molecules?|wisps?|rigs?)\b")
# What tells a sentence English (user story 73: « tout texte principal en
# français »): its grammatical words, none of them a French word.
ENGLISH = re.compile(r"(?i)\b(?:the|and|is|are|was|were|of|for|with|this|that|it|be|not|should|will|has|have|"
                     r"please|from|by|which|what|when|you|your|we|our|to|before|after)\b")

AT = "2026-10-12T08:00:00Z"
QUESTION = "af-r3t5y"
# The words of a producer that wrote identifiers where the operator reads.
WRITTEN = "Relire af-k2j4h avant la fusion de #712"
OPTIONS = [
    {"lettre": "a", "option": "Relire maintenant", "consequence": "la fusion attend la relecture", "recommande": True,
     "raison": "la carte change le parcours"},
    {"lettre": "b", "option": "Fusionner sans relire", "consequence": "la fusion part tout de suite"},
]
QUESTION_IN_ENGLISH = "af-e7n2w"
# The words of a producer that wrote English, with no identifier and no
# internal term in them.
WRITTEN_IN_ENGLISH = "Please review the export before the merge"
# The words of producers that wrote German and Spanish: no English word in
# them, and no French sentence either (user story 73: French, the
# operator's language, not merely « not English »).
QUESTION_IN_GERMAN = "af-g4d8m"
WRITTEN_IN_GERMAN = "Bitte die Karte vor der Zusammenführung prüfen"
QUESTION_IN_SPANISH = "af-s5p6n"
WRITTEN_IN_SPANISH = "Revisar el mapa antes de la fusión, por favor"
WRITTEN_BY = {QUESTION: WRITTEN, QUESTION_IN_ENGLISH: WRITTEN_IN_ENGLISH, QUESTION_IN_GERMAN: WRITTEN_IN_GERMAN,
              QUESTION_IN_SPANISH: WRITTEN_IN_SPANISH}
TRACKER = {
    QUESTION: escalation(WRITTEN, "La relecture de la carte attend ton avis.", OPTIONS, AT, "notes"),
    QUESTION_IN_ENGLISH: escalation(WRITTEN_IN_ENGLISH, "La relecture de l’export attend ton avis.", OPTIONS, AT,
                                    "notes"),
    QUESTION_IN_GERMAN: escalation(WRITTEN_IN_GERMAN, "La relecture de la carte attend ton avis.", OPTIONS, AT,
                                   "notes"),
    QUESTION_IN_SPANISH: escalation(WRITTEN_IN_SPANISH, "La relecture de la carte attend ton avis.", OPTIONS, AT,
                                    "notes"),
}


class UsineMuetteDetails(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def silent(self, dataset: str) -> tuple[str, dict, list[dict]]:
        """The cockpit on `dataset` once its silence lasted longer than the
        threshold: its address, the request « usine muette », every request."""
        address = self.tree.launch(dataset)
        requests = wait_for(lambda: requests_of(address),
                            lambda found: any(MUETTE.search(r["quoi"]) for r in found), SILENCE_SECONDS, interval=1)
        muette = [r for r in requests if MUETTE.search(r["quoi"])]
        self.assertEqual(1, len(muette), f"no one request « usine muette »: {[r['quoi'] for r in requests]}")
        self.assertEqual("Urgent", muette[0]["niveau"], f"the silent Factory is not Urgent: {muette[0]}")
        return address, muette[0], requests

    def assert_shown(self, address: str, request: dict) -> str:
        """The request is said on the page, in « Ce qui t’attend »; returns
        the text of the page as shown."""
        page = walk(address, [])["start"]
        shown = visible_text(page)
        self.assertIn("Ce qui t’attend", shown)
        self.assertIn(request["quoi"], shown.split("Ce qui t’attend", 1)[1], "the page does not say the request")
        return shown

    def assert_main_texts_clean(self, shown: str, requests: list[dict]) -> None:
        self.assertEqual([], IDENTIFIER.findall(shown), "an identifier shows in a main text")
        self.assertEqual([], INTERNAL_TERM.findall(shown), "an internal term shows in a main text")
        self.assertEqual([], [r["id"] for r in requests if r["id"] in shown], "the identifier of a request shows")
        said = [text for r in requests
                for text in [r.get("quoi"), r.get("pourquoi")] + [o.get("option") for o in r.get("que_faire") or []]
                if isinstance(text, str)]
        self.assertEqual([], [text for text in said if ENGLISH.search(text)], "a main text is not French")
        self.assertEqual([], ENGLISH.findall(shown.split("Ce qui t’attend", 1)[-1]), "a main text is not French")

    def details_of(self, address: str, request: dict) -> list[dict]:
        """The folded details of the page that give the identifier of
        `request`, apart from the old technical zone."""
        return [d for d in folded(address) if request["id"] in d["text"]]

    def assert_details_folded(self, address: str, requests: list[dict]) -> None:
        """Each request has folded details that give its identifier and a
        link (user story 75)."""
        for request in requests:
            details = self.details_of(address, request)
            self.assertTrue(details, f"no folded details give the identifier of « {request['quoi']} »")
            self.assertTrue(any(d["links"] for d in details),
                            f"the folded details of « {request['quoi']} » give no link: {details}")

    # --- Criterion 3 ------------------------------------------------------------

    def test_home_offline_says_the_factory_muette_urgent_in_clean_words_with_its_details_folded(self):
        address, muette, requests = self.silent("home-offline")
        shown = self.assert_shown(address, muette)
        self.assert_main_texts_clean(shown, requests)
        self.assert_details_folded(address, requests)

    def test_home_loading_says_the_factory_muette_urgent(self):
        address, muette, requests = self.silent("home-loading")
        self.assert_main_texts_clean(self.assert_shown(address, muette), requests)
        self.assert_details_folded(address, requests)

    def test_a_producer_text_with_identifiers_is_shown_without_them_and_kept_whole_in_its_details(self):
        address = serve_tracker(self.tree, TRACKER)
        requests = wait_for(lambda: requests_of(address),
                            lambda found: set(WRITTEN_BY) <= {r["id"] for r in found}, 20)
        for bead_id in WRITTEN_BY:
            self.assertIn(bead_id, [r["id"] for r in requests], f"« Ce qui t’attend » does not list {bead_id}")
        shown = visible_text(walk(address, [])["start"])
        self.assertIn("Ce qui t’attend", shown)
        self.assert_main_texts_clean(shown, requests)
        for written in (WRITTEN_IN_ENGLISH, WRITTEN_IN_GERMAN, WRITTEN_IN_SPANISH):
            self.assertNotIn(written, shown, f"the words a producer wrote in another language show as main text: "
                                             f"« {written} »")
        self.assert_details_folded(address, requests)
        for bead_id, written in WRITTEN_BY.items():
            question = next(r for r in requests if r["id"] == bead_id)
            details = self.details_of(address, question)
            self.assertTrue(any(written in d["text"] for d in details),
                            f"the folded details of {bead_id} do not keep the words of its producer as written: "
                            f"{details}")


if __name__ == "__main__":
    unittest.main()
