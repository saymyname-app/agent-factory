#!/usr/bin/env python3
"""Criterion test 1 of E « Projet — release, estimation, roadmap Factory et
historique » (af-8rbceu; Spec af-fgcw0d, user stories 152, 153, 154, 155
and 156, Testing Decisions 1, 5 and 8): the states projects-content,
release-expanded, release-estimate and project-missing of the Validated
Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-project).

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and reads the page a
headless Chromium renders (home_destination.measure): /projets, where the
whole line of a project opens its page, by a click and by the keyboard;
then the page of the project, /projet/<project>, whose « Prochaine
release » is read from the release plan (cadrage) of the project: its
revisable target, its gains verified each with its proof, what remains,
its decisions, its next milestone and how it is verified, and the history
of its scope kept apart from the gains; its estimate, conditional with its
scope and hypotheses, or said unavailable with why.

The values are those the reference writes for each state.

False if the release shows a global percentage or a certain date on an
incomplete scope, a release plan the project does not have, or an estimate
without its hypotheses.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure  # noqa: E402
from project_destination import DATE, part  # noqa: E402

RELEASE = "Prochaine release"
PROOF = "Voir la preuve"
HISTORY = "Évolution de la cible"
HYPOTHESES = "Hypothèses"


class ProjectsRelease(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def page(self, dataset: str, project: str, click: str | None = None) -> dict:
        """The page of `project` the cockpit launched on `dataset` serves,
        1440 px wide, dark; with `click`, read again under `after` once that
        control was activated."""
        address = self.tree.launch(dataset)
        return measure(address, f"/projet/{project}", click=click)[0]

    def release(self, frame: dict) -> str:
        text = part(frame, RELEASE)
        self.assertTrue(text, f"the page of the project has no « {RELEASE} »; it says « {frame.get('text', '')[:400]} »")
        return text

    def assert_no_false_promise(self, release: str, computed: str | None = None) -> None:
        """No global percentage, and no date but `computed`, the date the
        estimate says it was computed at -- none when it shows no range:
        the scope is incomplete, a date of delivery would be a promise."""
        self.assertNotIn("%", release, "the release shows a percentage")
        for found in DATE.finditer(release):
            self.assertEqual(computed, found.group(0), f"the release shows a date that is not the date of its "
                                                       f"computation: « {found.group(0)} »")
            self.assertRegex(release[:found.start()], r"(?i)calculée le\s*$",
                             f"the date « {found.group(0)} » is not said the date the estimate was computed")

    def assert_target(self, release: str, target: str, gains: tuple[str, ...], remaining: tuple[str, ...],
                      milestone: str, check: str) -> None:
        """The revisable `target`, the `gains` verified then what remains,
        among it each criterion of `remaining`, the `milestone` and how it
        is verified, its `check`."""
        self.assertRegex(release, r"(?i)cible révisable", "the target is not said revisable")
        self.assertIn(target, release, "the release does not say its target")
        self.assertRegex(release, rf"Acquis vérifiés\s*{len(gains)}\b", f"the release does not count its {len(gains)} "
                                                                       "gains verified")
        gained = release.index("Acquis vérifiés")
        remains = release.find("Reste connu")
        self.assertGreater(remains, gained, "the release does not say what remains after its gains")
        for gain in gains:
            self.assertTrue(gained < release.find(gain) < remains, f"« {gain} » is not among the gains verified")
        for criterion in remaining:
            self.assertGreater(release.find(criterion), remains, f"« {criterion} » is not among what remains")
        self.assertIn(milestone, release, "the release does not say its next milestone")
        self.assertIn(check, release, "the milestone does not say how it is verified")

    def history_of(self, dataset: str, project: str) -> tuple[str, str]:
        """The release of `project` on `dataset`, then once the history of
        its target is opened: the part of it that history adds."""
        page = self.page(dataset, project, click=HISTORY)
        before = self.release(page)
        after = page.get("after", {})
        self.assertTrue(after.get("found"), f"the release has no « {HISTORY} »")
        opened = part(after, RELEASE)
        self.assertIn(HISTORY, opened)
        return before, opened[opened.index(HISTORY):]

    # --- Criterion 1 ------------------------------------------------------------

    def test_the_whole_line_of_a_project_opens_its_page_by_a_click_and_by_the_keyboard(self):
        address = self.tree.launch("projects-content")
        listed = measure(address, "/projets")[0]
        self.assertEqual("/projets", listed["path"])
        # The control of the line holds the whole line: the project and
        # what the line says of it, its current chantier.
        lines = [control["name"] for control in listed["controls"]
                 if "Notes" in control["name"] and "Recherche dans les notes" in control["name"]
                 and not control["disabled"]]
        self.assertEqual(1, len(lines), "the line of Notes is not one control holding the whole line: "
                                        f"{[c['name'] for c in listed['controls']]}")
        for keys in (False, True):
            opened = measure(address, "/projets", click=lines[0], keys=keys)[0]["after"]
            self.assertTrue(opened.get("found"))
            self.assertEqual("/projet/notes", opened.get("path"),
                             f"the line does not open the page of Notes {'by the keyboard' if keys else 'by a click'}")
            self.assertIn(RELEASE, opened.get("text", ""), "the page opened does not show the release of the project")

    def test_projects_content_shows_the_target_the_gains_with_their_proofs_what_remains_the_decision_and_the_milestone(self):
        gains = ("Créer et retrouver une note", "Conserver ses notes après reconnexion")
        proof = ("Preuve illustrative : parcours essayé, résultat conforme au critère et avis favorable. "
                 "Aucune validation réelle représentée par cette donnée fictive.")
        address = self.tree.launch("projects-content")
        page = measure(address, "/projet/notes")[0]
        release = self.release(page)
        self.assert_target(release, "Permettre à un nouvel utilisateur de retrouver et exporter ses notes sans aide.",
                           gains, ("Exporter les notes au format choisi", "Vérifier le parcours sans assistance"),
                           "Faire essayer le parcours complet à trois utilisateurs",
                           "Trois essais documentés ; blocages et réussites observés.")
        self.assertRegex(release, r"Reste connu\s*2\b", "the release does not count the two criteria that remain")
        self.assertRegex(release, r"(?i)décision ouverte\s*Le partage de notes est-il nécessaire dès cette release \?",
                         "the release does not say its open decision")
        self.assertNotIn(proof, release, "the proofs are not folded under their gains")
        # Each gain has its proof, which opens under it, and under it only.
        proofs = [c["name"] for c in page["controls"] if c["name"].startswith(PROOF)]
        self.assertEqual([f"{PROOF} : {gain}" for gain in gains], proofs, "each gain verified has not its proof")
        for gain, following in ((gains[0], gains[1]), (gains[1], "Reste connu")):
            after = measure(address, "/projet/notes", click=f"{PROOF} : {gain}")[0].get("after", {})
            self.assertTrue(after.get("found"), f"no proof of « {gain} » to open")
            opened = part(after, RELEASE)
            self.assertIn(proof, opened[opened.index(gain):opened.index(following)],
                          f"the proof of « {gain} » does not open under it: « {opened} »")
            self.assertEqual(1, opened.count(proof), f"opening the proof of « {gain} » opens another")
            self.assert_no_false_promise(opened)

    def test_projects_content_says_its_estimate_unavailable_and_keeps_the_history_of_its_target_apart(self):
        release, history = self.history_of("projects-content", "notes")
        self.assertRegex(release, r"(?i)estimation (non disponible|indisponible)", "the estimate is not said unavailable")
        self.assertRegex(release, r"(?i)historique comparable insuffisant", "the estimate does not say why it is unavailable")
        self.assertRegex(history, r"(?i)cible initiale proposée · parcours individuel",
                         "the history of the target does not hold the initial target")
        for gain in ("Créer et retrouver une note", "Conserver ses notes après reconnexion"):
            self.assertNotIn(gain, history, "the history of the target mixes the gains")
        self.assert_no_false_promise(release + " " + history)

    def test_release_expanded_adds_the_included_criterion_to_what_remains_and_keeps_its_gains(self):
        gains = ("Créer et retrouver une note", "Conserver ses notes après reconnexion")
        added = "Partager une note avec une autre personne"
        release, history = self.history_of("release-expanded", "notes")
        self.assert_target(release, "Permettre à un nouvel utilisateur de retrouver et exporter ses notes sans aide.",
                           gains, ("Exporter les notes au format choisi", "Vérifier le parcours sans assistance", added),
                           "Faire essayer le parcours complet à trois utilisateurs",
                           "Trois essais documentés ; blocages et réussites observés.")
        self.assertRegex(release, r"Reste connu\s*3\b", "the criterion included is not counted among what remains")
        self.assertRegex(release, r"(?i)périmètre élargi", "the decision included is not said")
        self.assertRegex(release, r"(?i)estimation (non disponible|indisponible)",
                         "the estimate of the scope widened is not said unavailable")
        self.assertRegex(history, r"(?i)cible initiale", "the history lost the initial target")
        self.assertRegex(history, r"(?i)cible élargie", "the history does not hold the widening of the target")
        for gain in gains:
            self.assertNotIn(gain, history, "the history of the target mixes the gains")
        self.assert_no_false_promise(release + " " + history)

    def test_release_estimate_shows_a_range_only_with_its_scope_and_its_hypotheses(self):
        page = self.page("release-estimate", "portfolio", click=HYPOTHESES)
        release = self.release(page)
        self.assertIn("Permettre à un visiteur de comprendre mon travail et de me contacter.", release)
        self.assertIn("Fourchette indicative · 1 à 3 semaines", release, "the release does not show its range")
        # The scope and the conditions of the range, said beside it.
        self.assertRegex(release, r"(?i)deux critères restants", "the range does not say its scope")
        self.assertRegex(release, r"(?i)capacité", "the range does not say its condition on capacity")
        self.assertRegex(release, r"(?i)dépendances", "the range does not say its condition on dependencies")
        self.assertRegex(release, r"(?i)décision ouverte est exclue", "the range does not exclude the open decision")
        after = page.get("after", {})
        self.assertTrue(after.get("found"), f"the range has no « {HYPOTHESES} »")
        opened = part(after, RELEASE)
        hypotheses = opened[opened.find(HYPOTHESES):] if HYPOTHESES in opened else ""
        self.assertIn("12 résultats comparables", hypotheses, "the hypotheses do not say the comparable data")
        self.assertRegex(hypotheses, r"(?i)capacité stable", "the hypotheses do not say the capacity")
        self.assertIn("calculée le 12/10/2026", hypotheses, "the hypotheses do not say when the range was computed")
        self.assert_no_false_promise(opened, computed="12/10/2026")

    def test_project_missing_says_the_release_plan_absent_points_what_lacks_and_deduces_nothing(self):
        page = self.page("project-missing", "notes")
        release = self.release(page)
        self.assertRegex(release, r"(?i)cadrage", "the release does not say what is missing: its release plan")
        self.assertRegex(release, r"(?i)non collecté|absent|aucun cadrage", "the release plan is not said absent")
        self.assertRegex(release, r"(?i)aucun avancement déduit", "the release does not say no progress is deduced")
        self.assertRegex(release, r"(?i)dépôt", "the release does not point where the release plan lacks")
        for invented in ("Cible révisable", "Permettre à un nouvel utilisateur de retrouver et exporter ses notes sans aide.",
                         "Acquis vérifiés", "Reste connu", "Fourchette", "Créer et retrouver une note",
                         "Conserver ses notes après reconnexion", "Exporter les notes au format choisi",
                         "Vérifier le parcours sans assistance"):
            self.assertNotIn(invented, release, f"a release plan the project does not have is shown: « {invented} »")
        self.assert_no_false_promise(release)


if __name__ == "__main__":
    unittest.main()
