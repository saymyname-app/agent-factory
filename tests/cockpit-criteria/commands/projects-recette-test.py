#!/usr/bin/env python3
"""Criterion test 3 of E « Projet — release, estimation, roadmap Factory et
historique » (af-8rbceu; Spec af-fgcw0d, user stories 124 and 175, Testing
Decisions 1 and 5): the states projects-narrow and projects-light of the
Validated Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-project), and the explicit recipe
of the states the reference does not draw (empty, loading, error, long
content: « non prototypé — recette explicite requise »).

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, and has a headless Chromium render the page of a
project at 1440 and 390 px, in the dark and the light theme
(home_destination.measure). On each rendering the page is held to the
navigation B and to the named parts of the reference
(project_destination.assert_fold), and to what makes it unreadable or
unusable (home_destination.problems: overflow, cut or overlapping texts,
contrast, controls out of reach of the keyboard or without a visible focus,
the theme asked for).

The recipe of the states the reference does not draw, each on its own
dataset, none deduced from a neighbouring screen:

- empty: no project declared (home-empty), /projets says so, readable and
  usable at both widths in both themes; a project declared with nothing
  yet -- no chantier, no release plan, no roadmap -- says each missing, and
  invents none;
- loading: the tracker of projects-content never answers (`ui.state`
  loading): the page of the project says its chantiers are being read, and
  says none of them absent;
- error: the tracker of projects-content fails (`ui.state` error): the
  page says the reading failed, and says none of them absent;
- long content: projects-content with a target, criteria, a milestone and
  a chantier said in long words, and more criteria: everything is shown,
  nothing overflows.

False if a state the reference does not draw is deduced from a
neighbouring screen without its recipe, a rendering defect of the
reference is copied, or the focus is invisible or trapped.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, measure_until, problems  # noqa: E402
from project_destination import (  # noqa: E402
    CONTENT_PARTS, MISSING_PARTS, SHELL, assert_fold, dataset_of, launch_declared, part,
)

WIDTHS = (1440, 390)
THEMES = ("dark", "light")
RELEASE = "Prochaine release"
PANELS = ("nav-1", "main-1", "panel-1")


class ProjectsRecette(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def rendered(self, address: str, project: str, parts: dict, ready=None) -> list[dict]:
        """The page of `project` at `address`, held at both widths in both
        themes to the named parts `parts` of the reference and to
        readability; with `ready`, once every frame says it. The frames of
        the last theme."""
        found = {}
        frames = []
        for theme in THEMES:
            if ready:
                frames = measure_until(address, lambda measured: all(ready.search(f.get("text", "")) for f in measured),
                                       seconds=15, path=f"/projet/{project}", theme=theme, widths=WIDTHS)
            else:
                frames = measure(address, f"/projet/{project}", theme=theme, widths=WIDTHS)
            self.assertEqual(list(WIDTHS), [frame["width"] for frame in frames])
            for frame in frames:
                assert_fold(self, frame, project, parts)
            found.update(problems(frames, theme, PANELS))
        self.assertEqual({}, found, f"the page of {project} is not readable and usable at both widths in both themes")
        return frames

    def assert_by_keyboard(self, address: str, control: str, shown: str) -> None:
        """At 390 px, `control` reached and activated by the keyboard shows
        `shown` in the release, and the page stays readable and usable."""
        for frame in measure(address, "/projet/notes", widths=(390,), click=control, keys=True):
            opened = frame.get("after", {})
            self.assertTrue(opened.get("found"), f"no « {control} » at 390 px")
            self.assertEqual("/projet/notes", opened.get("path"), f"« {control} » left the page of the project")
            self.assertRegex(part(opened, RELEASE), shown, f"« {control} » opened by the keyboard shows nothing")
            self.assertEqual({}, problems([opened], "dark", PANELS), f"the page with « {control} » open is not usable")

    def variant(self, name: str, **ui) -> str:
        """The address of the cockpit launched on projects-content declared
        again as `name`, its `ui` given `ui` besides."""
        dataset = dataset_of(self.tree, "projects-content")
        dataset["ui"] = {**dataset["ui"], "id": name, **ui}
        return launch_declared(self.tree, name, dataset)

    # --- Criterion 3 ------------------------------------------------------------

    def test_projects_narrow_is_faithful_readable_and_usable_at_both_widths_in_both_themes_and_by_the_keyboard(self):
        address = self.tree.launch("projects-narrow")
        self.rendered(address, "notes", CONTENT_PARTS)
        self.assert_by_keyboard(address, "Voir la preuve", r"Voir la preuve\s*\S.{19,}")

    def test_projects_light_is_faithful_readable_and_usable_at_both_widths_in_both_themes_and_by_the_keyboard(self):
        address = self.tree.launch("projects-light")
        self.rendered(address, "notes", CONTENT_PARTS)
        self.assert_by_keyboard(address, "Évolution de la cible", r"(?i)Évolution de la cible\s*\S*\s*cible initiale")

    def test_no_project_and_a_project_with_nothing_yet_each_say_what_is_missing_and_invent_nothing(self):
        # No project declared: /projets says so, readable and usable.
        address = self.tree.launch("home-empty")
        found = {}
        for theme in THEMES:
            listed = measure(address, "/projets", theme=theme, widths=WIDTHS)
            self.assertEqual(list(WIDTHS), [frame["width"] for frame in listed])
            for frame in listed:
                self.assertEqual("/projets", frame.get("path"))
                self.assertRegex(frame.get("text", ""), r"(?i)aucun projet déclaré",
                                 f"an empty list does not say so at {frame['width']} px in the {theme} theme")
            found.update(problems(listed, theme, ("nav-1", "main-1")))
        self.assertEqual({}, found, "/projets without a project is not readable and usable at both widths in both themes")
        # A project declared, with nothing yet.
        name = "projects-nothing-yet"
        dataset = dataset_of(self.tree, "projects-content")
        dataset["ui"] = {"id": name, "page": "projects", "selected": "Vide"}
        dataset["visible_text"] = "← Projets\nVide\n\nUn projet déclaré, sans rien encore."
        address = launch_declared(self.tree, name, dataset)
        for frame in self.rendered(address, "vide", MISSING_PARTS):
            release = part(frame, RELEASE)
            self.assertRegex(release, r"(?i)cadrage", f"the release does not say its release plan is missing at {frame['width']} px")
            self.assertRegex(release, r"(?i)dépôt", "the release does not point where the release plan lacks")
            for invented in ("Cible révisable", "Acquis vérifiés", "Reste connu", "Fourchette", "%"):
                self.assertNotIn(invented, release, f"a release plan the project does not have is shown: « {invented} »")
            self.assertRegex(frame.get("text", ""), r"(?i)aucun chantier", "the project does not say it has no chantier")

    def test_a_project_whose_tracker_is_still_being_read_says_so_and_says_no_chantier_absent(self):
        loading = re.compile(r"(?i)lecture[^.]{0,60}en cours|en cours de lecture")
        address = self.variant("projects-loading", state="loading")
        for frame in self.rendered(address, "notes", SHELL, ready=loading):
            self.assertRegex(frame.get("text", ""), loading, f"the page does not say its chantiers are being read at {frame['width']} px")
            # What the page would say, were it to deduce from the tracker
            # unread that the project has no chantier.
            self.assertNotRegex(frame.get("text", ""), r"(?i)aucun chantier|\b0 chantiers?\b|bloqué",
                                "the page deduces chantiers from a tracker unread")

    def test_a_project_whose_tracker_fails_says_the_reading_failed_and_says_no_chantier_absent(self):
        failed = re.compile(r"(?i)illisible|ne répond pas|lecture impossible|échec de la lecture|erreur")
        address = self.variant("projects-error", state="error")
        for frame in self.rendered(address, "notes", SHELL, ready=failed):
            self.assertRegex(frame.get("text", ""), failed, f"the page does not say the reading failed at {frame['width']} px")
            self.assertNotRegex(frame.get("text", ""), r"(?i)aucun chantier|\b0 chantiers?\b|bloqué",
                                "the page deduces chantiers from a tracker that failed")

    def test_long_content_is_shown_whole_and_stays_readable_at_both_widths_in_both_themes(self):
        # What projects-content says, and what it says instead.
        target = ("Permettre à un nouvel utilisateur de retrouver, classer, annoter, partager et exporter "
                  "l’intégralité de ses notes personnelles et professionnelles sans aucune aide extérieure, "
                  "y compris depuis un téléphone ancien : réinterprétabilité-anticonstitutionnellement-garantie.")
        criteria = ("Exporter les notes au format choisi, y compris les pièces jointes volumineuses et les "
                    "historiques de modification complets",
                    "Importer les carnets existants depuis trois applications concurrentes sans perte de mise en forme",
                    "Retrouver une note par une phrase approximative dictée à voix haute dans le métro")
        milestone = ("Faire essayer le parcours complet à trois utilisateurs débutants, sur trois appareils "
                     "différents, pendant une semaine d’usage réel et documenté")
        chantier = "Recherche dans les notes, les pièces jointes, les étiquettes et les historiques de modification"
        more = "\\n\\n○ ".join(criteria)
        commit = self.tree.reword("projects-content", {
            "Permettre à un nouvel utilisateur de retrouver et exporter ses notes sans aide.": target,
            "Reste connu 2\\n\\n○ Exporter les notes au format choisi": f"Reste connu 4\\n\\n○ {more}",
            "Faire essayer le parcours complet à trois utilisateurs\\n\\nTrois": f"{milestone}\\n\\nTrois",
            "CHANTIER ACTUEL\\nRecherche dans les notes": f"CHANTIER ACTUEL\\n{chantier}",
        })
        address = self.tree.launch("projects-content", commit)
        for frame in self.rendered(address, "notes", CONTENT_PARTS):
            text = " ".join(frame.get("text", "").split())
            for said in (target, *criteria, milestone, chantier):
                self.assertIn(said, text, f"a long text is not shown whole at {frame['width']} px")


if __name__ == "__main__":
    unittest.main()
