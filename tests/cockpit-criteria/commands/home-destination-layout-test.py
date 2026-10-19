#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02R2, af-r2c0tx, from T02R af-vbb4ol replacing T02
af-0gonc9; Spec af-2zseit, user stories 124 and 175, Testing Decisions 5):
the destination and its panels, on the ten states home-* of its reference
and on long content -- the long report of home-long opened among them --,
at 1440 and 390 px, in the light and the dark theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET / in two frames, 1440 and 390 px wide, once with the
dark and once with the light colour scheme preferred. On each rendering
it requires the panels of the state, then reads what makes the page
unreadable or unusable (home_destination.problems):

- the document wider than the frame (a global overflow), a text cut by a
  box that hides what overflows it or pushed out of the frame -- a text
  inside a box that scrolls is not cut: a useful local scroll is kept --,
  two texts drawn on each other, a contrast under 4.5:1 (3:1 when large);
- a control without a name, a control enabled but out of reach of the
  keyboard or that the keyboard cannot activate, a control whose focus is
  not visible, a button whose box stands out under 3:1;
- a page that is not in the theme the browser asked for.

The reference draws some of these defects itself (a control without a
visible focus, among others): they are measured on the product, not
copied from the frozen page. The result states result-* are the panels of
T02S, not of this ticket.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, measure_until, problems, says  # noqa: E402

WIDTHS = (1440, 390)
# The panels of the destination with its content: the requests, the result
# open with its bar of actions, the projects.
CONTENT_PANELS = ("nav-1", "main-1", "metric-grid-1", "inbox-1", "panel-2", "panel-3", "actions-possibles-1",
                  "panel-4")


class HomeDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def rendered(self, dataset: str, panels: tuple[str, ...], commit: str | None = None,
                 wait: bool = False) -> dict[str, list[dict]]:
        """GET / of the cockpit launched on `dataset`, rendered dark then
        light at both widths: theme -> frames. With `wait`, a state the
        cockpit reaches after a time (a source that gives up, a reading
        that goes stale) is rendered once its panels are drawn, or as it
        stands after 15 s."""
        address = self.tree.launch(dataset, commit)
        drawn = lambda frames: all(p in frames[0]["texts"] for p in panels)  # noqa: E731
        dark = (measure_until(address, drawn, seconds=15, theme="dark", widths=WIDTHS) if wait
                else measure(address, theme="dark", widths=WIDTHS))
        return {"dark": dark, "light": measure(address, theme="light", widths=WIDTHS)}

    def assert_readable(self, dataset: str, panels: tuple[str, ...], commit: str | None = None,
                        wait: bool = False) -> dict:
        renderings = self.rendered(dataset, panels, commit, wait)
        found = {}
        for theme, frames in renderings.items():
            found.update(problems(frames, theme, panels))
        self.assertEqual({}, found)
        return renderings

    # Criterion 2 ---------------------------------------------------------

    def test_home_content_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-content", CONTENT_PANELS)
        # Activated by the keyboard -- focused, then Enter --, an indicator,
        # a project and an entry of the navigation lead where a click does.
        address = self.tree.launch("home-content")
        for control, where in (("Décisions à prendre", r"/"), ("Notes", r"/projet/.+"), ("Journal", r"/journal")):
            for frame in measure(address, theme="dark", widths=WIDTHS, click=control, keys=True):
                after = frame["after"]
                self.assertTrue(after["found"], f"no control « {control} » at {frame['width']} px")
                self.assertRegex(after["path"], f"^{where}$",
                                 f"Enter on « {control} » did not lead where it goes at {frame['width']} px")

    def test_home_content_full_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-content-full", CONTENT_PANELS)

    def test_home_narrow_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-narrow", CONTENT_PANELS)

    def test_home_light_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-light", CONTENT_PANELS)

    def test_home_long_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-long", CONTENT_PANELS)
        # The long report itself, opened: its findings and their paths too
        # long for a line stay whole and inside the page, in both themes.
        address = self.tree.launch("home-long")
        found = {}
        for theme in ("dark", "light"):
            frames = measure(address, theme=theme, widths=WIDTHS, click="Compte rendu long")
            opened = [frame["after"] for frame in frames]
            self.assertEqual([True, True], [frame["found"] for frame in opened],
                             f"no control « Compte rendu long » to open ({theme})")
            self.assertEqual(
                [], [frame["width"] for frame in frames
                     if "Constat 18 —" not in says(frame["after"], "panel-3")],
                f"the long report is not drawn once opened ({theme})",
            )
            found.update(problems(opened, theme, CONTENT_PANELS))
        self.assertEqual({}, found)

    def test_home_empty_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-empty", ("nav-1", "main-1", "panel-1"))

    def test_home_loading_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-loading", ("nav-1", "main-1", "panel-1", "skeleton-1"))

    def test_home_error_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-error", ("nav-1", "main-1", "error-1"), wait=True)

    def test_home_stale_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-stale", ("notice-1",) + CONTENT_PANELS, wait=True)

    def test_home_offline_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("home-offline", ("notice-1",) + CONTENT_PANELS, wait=True)

    def test_long_titles_and_words_stay_whole_and_inside_the_page_at_both_widths_in_both_themes(self):
        # The same dataset, at another commit, where a request, the result
        # open and a chantier have long titles, one of them a word longer
        # than a phone is wide: every rendering stays readable, and each
        # title is said whole where the reference says the short one.
        long_result = ("Le cockpit attend ton avis sur la reprise complète de ses parcours, de ses panneaux "
                       "et de ses textes longs comme celui-ci")
        long_request = ("Choisir le format d’export des notes archivées depuis le premier trimestre : "
                        "Référence/synthétique/chemin_de_ressource_assez_long_pour_vérifier_le_retour_à_la_ligne")
        long_chantier = "Recherche plein texte dans les notes longues et les-identifiants-sans-espace-du-projet"
        reworded = self.tree.reword("home-content", {"Le cockpit attend ton avis": long_result,
                                                     "Choisir le format d’export": long_request,
                                                     "Recherche dans les notes": long_chantier})
        renderings = self.assert_readable("home-content", CONTENT_PANELS, commit=reworded)
        for theme, frames in renderings.items():
            for frame in frames:
                self.assertEqual(
                    (True, True, True, True),
                    (long_result in says(frame, "request-1"), long_request in says(frame, "request-2"),
                     long_result in says(frame, "panel-3"), long_chantier in says(frame, "row-2")),
                    f"a long title is not said whole at {frame['width']} px, {theme}",
                )


if __name__ == "__main__":
    unittest.main()
