#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Rituels et préparation release »
(T41, af-r4hrt7; Spec af-2zseit, user stories 124 and 175, Testing
Decisions 5): the destination and its panels, on the fourteen states of its
reference and on long content, at 1440 and 390 px, in the light and the
dark theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET /rituels in two frames, 1440 and 390 px wide, once with
the dark and once with the light colour scheme preferred. On each rendering
it requires the panels of the state, then reads what makes the page
unreadable or unusable (home_destination.problems, the reading of the
destination « Vue d’ensemble »):

- the document wider than the frame (a global overflow), a text cut by a
  box that hides what overflows it or pushed out of the frame -- a text
  inside a box that scrolls is not cut --, two texts drawn on each other,
  a contrast under 4.5:1 (3:1 when large);
- a useful local scroll lost: a box that scrolls on its own whose content
  larger than it is hidden rather than scrolled, or that the keyboard
  cannot reach;
- a control without a name, a control enabled but out of reach of the
  keyboard or that the keyboard cannot activate, a control whose focus a
  person does not see, a button or a field whose box stands out under 3:1;
- a page that is not in the theme the browser asked for.

The reference draws some of these defects itself (texts and buttons under
4.5:1 in its light theme, among others): they are measured on the product,
not copied from the frozen page.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rituals_destination import PATH, LaunchTree, measure, problems, says  # noqa: E402

WIDTHS = (1440, 390)
# The panels of the catalogue: the five rituals.
CATALOGUE_PANELS = ("nav-1", "main-1", "ritual-grid-1", "panel-1", "panel-2", "panel-3", "panel-4", "panel-5")
# The panels of a state of a review or of the preparation of a release: the
# way back, the path, the panel of the step.
STEP_PANELS = ("nav-1", "main-1", "crumb-1", "ritual-path-1", "panel-1")


class RitualsDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, panels: tuple[str, ...], commit: str | None = None) -> dict:
        """GET /rituels of the cockpit launched on `dataset` (at `commit`),
        rendered dark then light at both widths, shows `panels` and nothing
        that makes it unreadable or unusable: theme -> frames."""
        address = self.tree.launch(dataset, commit)
        renderings = {theme: measure(address, PATH, theme=theme, widths=WIDTHS) for theme in ("dark", "light")}
        found = {}
        for theme, frames in renderings.items():
            self.assertEqual([PATH] * len(WIDTHS), [frame["path"] for frame in frames])
            found.update(problems(frames, theme, panels))
        self.assertEqual({}, found)
        return renderings

    # Criterion 2: the catalogue --------------------------------------------

    def test_rituals_content_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("rituals-content", CATALOGUE_PANELS)

    def test_rituals_narrow_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("rituals-narrow", CATALOGUE_PANELS)

    def test_rituals_light_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("rituals-light", CATALOGUE_PANELS)

    # Criterion 2: a review -------------------------------------------------

    def test_ritual_confirm_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-confirm", STEP_PANELS + ("change-preview-1", "actions-1"))

    def test_ritual_review_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-review", STEP_PANELS + ("readonly-note-1",))

    def test_ritual_report_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-report", STEP_PANELS + ("proposal-choice-1", "proposal-choice-2", "actions-1"))

    def test_ritual_preparing_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-preparing", STEP_PANELS)

    def test_ritual_ready_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-ready", STEP_PANELS + ("change-preview-1", "actions-1"))

    def test_ritual_execution_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-execution", STEP_PANELS)

    def test_ritual_delivered_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("ritual-delivered", STEP_PANELS + ("readonly-note-1",))

    # Criterion 2: the preparation of the next release ---------------------

    def test_release_confirm_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("release-confirm", STEP_PANELS + ("change-preview-1", "actions-1"))

    def test_release_review_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("release-review", STEP_PANELS)

    def test_release_report_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("release-report", STEP_PANELS + ("release-columns-1", "release-decision-1",
                                                              "release-notice-1", "actions-1"))

    def test_release_saved_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("release-saved", STEP_PANELS + ("actions-1",))

    # Criterion 2: long content ---------------------------------------------

    def test_a_long_proposal_stays_whole_and_inside_the_page_at_both_widths_in_both_themes(self):
        # The report, at another commit, where a proposal has a long title
        # holding a word longer than a phone is wide: every rendering stays
        # readable, and the title is said whole in its proposal.
        long_title = ("Distinguer une lecture impossible d’un état vide dans chaque source du cockpit : "
                      "Référence/synthétique/chemin_de_ressource_assez_long_pour_vérifier_le_retour_à_la_ligne")
        reworded = self.tree.reword("ritual-report", {"Distinguer une lecture impossible d’un état vide": long_title})
        renderings = self.assert_readable("ritual-report", STEP_PANELS + ("proposal-choice-1", "proposal-choice-2"),
                                          commit=reworded)
        self.assertEqual(
            {}, {f"{frame['width']} px, {theme}": says(frame, "proposal-choice-2")
                 for theme, frames in renderings.items() for frame in frames
                 if long_title not in says(frame, "proposal-choice-2")},
            "the long title of the proposal is not said whole",
        )

    def test_a_long_framing_stays_whole_and_inside_the_page_at_both_widths_in_both_themes(self):
        # The framing proposed, at another commit, with a long open
        # question and a long criterion left to satisfy, each holding a
        # word longer than a phone is wide: every rendering stays readable,
        # and both are said whole.
        long_question = ("Le partage de notes entre plusieurs comptes, avec leurs droits de lecture et "
                         "d’écriture-séparés-par-dossier-et-par-étiquette-du-projet, est-il nécessaire dès cette "
                         "release ?")
        long_criterion = ("Vérifier le parcours sans assistance sur ordinateur et sur téléphone : "
                          "Référence/synthétique/chemin_de_ressource_assez_long_pour_vérifier_le_retour_à_la_ligne")
        reworded = self.tree.reword("release-report", {
            "Le partage de notes est-il nécessaire dès cette release ?": long_question,
            "Vérifier le parcours sans assistance": long_criterion,
        })
        renderings = self.assert_readable("release-report", STEP_PANELS + ("release-columns-1", "release-decision-1"),
                                          commit=reworded)
        self.assertEqual(
            {}, {f"{frame['width']} px, {theme}": (says(frame, "release-decision-1"), says(frame, "release-columns-1"))
                 for theme, frames in renderings.items() for frame in frames
                 if long_question not in says(frame, "release-decision-1")
                 or long_criterion not in says(frame, "release-columns-1")},
            "the long framing is not said whole",
        )

    # Criterion 2: the keyboard ---------------------------------------------

    def test_the_links_of_the_destination_open_with_the_keyboard_at_both_widths(self):
        # Activated by the keyboard -- focused, then Enter --, an entry of
        # the navigation, the run of a review under way and the project of
        # a framing kept lead where they go.
        for dataset, control, where in (("rituals-content", "Journal", r"/journal"),
                                        ("ritual-review", "Voir le run", r"/runs.*"),
                                        ("release-saved", "Voir le projet", r"/projet/notes")):
            address = self.tree.launch(dataset)
            for frame in measure(address, PATH, theme="dark", widths=WIDTHS, click=control, keys=True):
                after = frame["after"]
                self.assertTrue(after["found"], f"no control « {control} » on {dataset} at {frame['width']} px")
                self.assertRegex(after["path"], f"^{where}$",
                                 f"Enter on « {control} » did not lead where it goes at {frame['width']} px")


if __name__ == "__main__":
    unittest.main()
