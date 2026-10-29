#!/usr/bin/env python3
"""Criterion test 2 of G2 « Usine — réglages et nettoyage par les portes
existantes » (af-f8nlhr; Spec af-fgcw0d, user story 166, the choice
« Maintenance » of af-2zseit: « Nettoyage par factory-maintain :
prévisualisation des candidats, protection des actifs/modifications
locales/commits non poussés ; confirmation du périmètre relu puis résultat
par élément. Périmètre modifié entre aperçu et commande : recalcul et
nouvelle confirmation, pas extension silencieuse. »; Testing Decisions 1 and
8): cleaning the unused work spaces.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the Usine of health-content
(usine_reglages.serve_usine): the door factory-maintain works there on throwaway Git repositories, whose worktrees are `af-merged`,
merged and pushed, the one candidate, and three to keep -- `af-modified` (a
local change), `af-unpushed` (a commit not pushed), `af-active` (work under
way). The page GET /usine is walked in a headless Chromium behind the
identity proxy of the host; its folded details are read in the HTML it
serves; a confirmation sent from an older preview is sent as the browser
sends it (pour_moi.Operator): the worktrees it names, each at the commit
the preview read (`{"name", "sha"}`).

False if a worktree under way, with a local change or with a commit not
pushed is removed, or if a scope grown since its preview, or a worktree
replaced under the same name, is cleaned without a new confirmation.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree  # noqa: E402
from usine_reglages import Operator, PAGE, control, folded, serve_usine, visible_text, walk  # noqa: E402

PREVIEW = [{"click": "Examiner le périmètre"}]
CLEAN = [{"click": "Examiner le périmètre"}, {"click": "Confirmer"}]
KEPT = ("af-modified", "af-unpushed", "af-active")
# A commit no worktree of the launch is at.
ELSEWHERE = "0123456789abcdef0123456789abcdef01234567"


def said_of(text: str, name: str, names: tuple[str, ...]) -> str:
    """What `text` says of the element `name`: from its name to the name of
    the next element of `names`, or to the end."""
    at = text.find(name)
    if at < 0:
        return ""
    ends = [found for other in names if other != name and (found := text.find(other, at + len(name))) >= 0]
    return text[at:min(ends) if ends else len(text)]


class FactoryClean(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own per case: serve_usine commits the dataset of the
        # case in it, and a case never sees what another case left.
        self.tree = LaunchTree()

    def tearDown(self) -> None:
        self.tree.remove()

    def assert_walked(self, walked: dict, steps: list[dict]) -> list[dict]:
        found = walked["steps"]
        for index, step in enumerate(steps):
            self.assertLess(index, len(found), f"the walk stopped before « {step['click']} »: {walked}")
            self.assertTrue(found[index]["found"], f"no control « {step['click']} » to activate: {found[index]}")
        return [step["page"] for step in found[:len(steps)]]

    def assert_preview_of_one_candidate_and_its_protections(self, page: dict) -> None:
        text = visible_text(page)
        self.assertRegex(text, r"(?i)\b1 espace\b[^.]*candidat", f"the preview does not show its one candidate: "
                                                                   f"« {text} »")
        self.assertRegex(text, r"(?i)modification(s)? locale", f"the preview does not protect a local change: « {text} »")
        self.assertRegex(text, r"(?i)non (poussé|publié)", f"the preview does not protect commits not pushed: « {text} »")
        self.assertRegex(text, r"(?i)en cours|actif", f"the preview does not keep the work under way: « {text} »")
        confirm = control(page, "Confirmer")
        self.assertIsNotNone(confirm, "the preview offers no confirmation")
        self.assertRegex(confirm["name"], r"\b1\b", f"the confirmation does not name the scope read: {confirm}")
        self.assertFalse(confirm["disabled"], f"the confirmation cannot be given: {confirm}")

    def test_the_confirmed_scope_is_cleaned_and_each_element_has_its_result(self):
        address = serve_usine(self.tree)
        preview, done = self.assert_walked(walk(address, CLEAN, path=PAGE), CLEAN)
        self.assert_preview_of_one_candidate_and_its_protections(preview)

        result = visible_text(done)
        self.assertRegex(result, r"(?i)\b1 espace\b[^.]*retiré", f"the result does not say what was removed: « {result} »")
        self.assertRegex(result, r"(?i)\b3 espaces\b[^.]*(conservés|protégés)",
                         f"the result does not say what was kept: « {result} »")
        self.assertNotRegex(result, r"(?i)simulation|aucun fichier réel", f"the cleaning is said simulated: « {result} »")

        details = " ".join(d["text"] for d in folded(address, PAGE))
        names = ("af-merged", *KEPT)
        self.assertRegex(said_of(details, "af-merged", names), r"(?i)retiré",
                         f"the details do not say af-merged was removed: « {details} »")
        for name in KEPT:
            self.assertRegex(said_of(details, name, names), r"(?i)conservé|protégé",
                             f"the details do not say {name} was kept: « {details} »")

        # Read again: nothing left to clean, the three kept still there.
        again = visible_text(self.assert_walked(walk(address, PREVIEW, path=PAGE), PREVIEW)[0])
        self.assertRegex(again, r"(?i)aucun (espace|candidat)|\b0 espace", f"af-merged was not removed: « {again} »")
        self.assertRegex(again, r"(?i)modification(s)? locale", f"the local change is gone: « {again} »")
        self.assertRegex(again, r"(?i)non (poussé|publié)", f"the commits not pushed are gone: « {again} »")
        self.assertRegex(again, r"(?i)en cours|actif", f"the work under way is gone: « {again} »")

    def assert_recomputed(self, answer, what: str) -> None:
        self.assertEqual("", answer.broken, f"the request broke: {answer}")
        self.assertIsNotNone(answer.status, f"no HTTP answer: {answer}")
        self.assertGreaterEqual(answer.status, 400, f"a scope that changed is cleaned ({what}): {answer}")
        self.assertNotEqual(500, answer.status, f"the cockpit broke: {answer}")
        self.assertIsInstance(answer.body, dict, f"the answer is no readable error: {answer}")
        self.assertRegex(answer.error(), r"(?i)périmètre", f"the refusal does not say the scope changed ({what}): {answer}")
        self.assertRegex(answer.error(), r"(?i)confirm", f"the refusal does not ask a new confirmation ({what}): {answer}")

    def test_a_scope_changed_since_its_preview_is_recomputed_and_asks_a_new_confirmation(self):
        address = serve_usine(self.tree)
        operator = Operator(address)
        # The preview of the scope is read now, as the operator reads it
        # before confirming.
        self.assert_walked(walk(address, PREVIEW, path=PAGE), PREVIEW)
        # Confirmed from a preview that listed a worktree since gone, and not
        # af-merged: the scope now is another one.
        self.assert_recomputed(operator.gesture("nettoyer", {"perimetre": [{"name": "af-gone", "sha": ELSEWHERE}],
                                                             "confirm": True}), "a worktree since gone")
        # Confirmed from a preview where the worktree af-merged was at another
        # commit: the same name, another worktree -- never removed on a name.
        self.assert_recomputed(operator.gesture("nettoyer", {"perimetre": [{"name": "af-merged", "sha": ELSEWHERE}],
                                                             "confirm": True}), "af-merged at another commit")

        # Recomputed: af-merged is still there, waiting for its own confirmation.
        page = self.assert_walked(walk(address, PREVIEW, path=PAGE), PREVIEW)[0]
        self.assert_preview_of_one_candidate_and_its_protections(page)
        details = " ".join(d["text"] for d in folded(address, PAGE))
        self.assertNotRegex(said_of(details, "af-merged", ("af-merged", *KEPT)), r"(?i)retiré",
                            f"af-merged was removed by a scope never confirmed: « {details} »")


if __name__ == "__main__":
    unittest.main()
