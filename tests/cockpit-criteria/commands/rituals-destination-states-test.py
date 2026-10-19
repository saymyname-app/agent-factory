#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Rituels et préparation release »
(T41, af-r4hrt7; Spec af-2zseit, user stories 167 to 175, Testing Decisions
1 and 5): the fourteen states of its reference.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at the address of the destination,
GET /rituels -- the same entry point as the ordinary data -- as a headless
Chromium renders it. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-rituals): the navigation B with
this destination open, what the reference says in each part of the state,
the step of its path under way, and its behaviour -- where a link of the
state leads, which commands it offers.

False if a state is omitted (its words missing), if the page is an
artificial one distinct from the product (served elsewhere than at
GET /rituels, or not following the data the cockpit serves), if a command
no door records -- launching a review, having a selection prepared,
launching the corrections, launching the preparation of a release, keeping
a framing -- is offered or answers as if it were done, or if the
destination cannot be reached from the navigation of the others.

The anchors and the tokens of each state are held to the reference in
rituals-destination-fidelity-test.py; criterion 2 is in
rituals-destination-layout-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rituals_destination import (  # noqa: E402
    PATH, RELEASE_STEPS, REVIEW_STEPS, LaunchTree, assert_no_command_offered, assert_path, assert_rituals,
    assert_says, assert_theme, assert_unwired, measure, options_of, projects_served, served,
)


class RitualsDestinationStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def state(self, dataset: str, commit: str | None = None, **options) -> tuple[str, dict]:
        """The page of the destination on `dataset`: the destination, at
        its address, with no command offered as if a door recorded it."""
        address, page = served(self.tree, dataset, commit, **options)
        assert_rituals(self, page)
        assert_no_command_offered(self, page)
        return address, page

    def assert_catalogue(self, page: dict) -> None:
        """What the reference says of the destination with its catalogue:
        the framing of the next release and the four reviews, each with
        what it is for, its last run and the way to prepare its launch."""
        assert_says(self, page, "h1-1", "Rituels")
        assert_says(self, page, "page-lead-1",
                    "Une revue produit des propositions. Tu choisis lesquelles faire préparer.")
        assert_says(self, page, "panel-1", "CADRAGE DU PROJET", "Préparer la prochaine release",
                    "Relier les acquis à une cible révisable, éclaircir les inconnues et proposer le prochain jalon.",
                    "Dernier cadrage : non renseigné", "Préparer le lancement")
        assert_says(self, page, "panel-2", "REVUE CONSEILLÉE", "Revue d’incidents",
                    "Comprendre les causes récurrentes et proposer les corrections qui évitent leur retour.",
                    "Dernière revue : 11 octobre · historique disponible", "Préparer le lancement",
                    "Voir le dernier rapport")
        assert_says(self, page, "panel-3", "LANCEMENT MANUEL", "Revue d’architecture",
                    "Repérer les parties difficiles à modifier et proposer des améliorations ciblées.",
                    "Dernière revue : non renseignée", "Préparer le lancement")
        assert_says(self, page, "panel-4", "LANCEMENT MANUEL", "Qualité / AI Slop",
                    "Trouver code inutile, duplications et complexité évitable.",
                    "Dernière revue : non renseignée", "Préparer le lancement")
        assert_says(self, page, "panel-5", "À LA DEMANDE", "Diagnostic Factory",
                    "Comprendre un blocage ou un comportement incohérent de la Factory.",
                    "Dernière revue : non renseignée", "Préparer le lancement")

    def assert_review_head(self, page: dict, current: str | None) -> None:
        """The head of a state of the review of incidents: the way back to
        the catalogue, its title, its scope, its path."""
        assert_says(self, page, "crumb-1", "← Rituels")
        assert_says(self, page, "h1-1", "Revue d’incidents")
        assert_says(self, page, "page-lead-1", "Usine")
        assert_path(self, page, REVIEW_STEPS, current)

    def assert_release_head(self, page: dict, current: str, lead: str) -> None:
        """The head of a state of the preparation of the next release."""
        assert_says(self, page, "crumb-1", "← Rituels")
        assert_says(self, page, "h1-1", "Préparer la prochaine release")
        assert_says(self, page, "page-lead-1", "Notes", lead)
        assert_path(self, page, RELEASE_STEPS, current)

    # Criterion 1: the catalogue --------------------------------------------

    def test_rituals_content_is_the_catalogue_of_the_rituals(self):
        # The reference draws rituals-content dark, at 1440 px.
        address, page = self.state("rituals-content")
        self.assert_catalogue(page)
        assert_theme(self, page, "dark")

    def test_rituals_narrow_is_the_catalogue_at_390_px(self):
        # The reference draws rituals-narrow dark, 390 px wide: the same
        # catalogue, within the width of the phone.
        address, page = self.state("rituals-narrow", width=390)
        self.assertEqual(390, page["width"])
        self.assert_catalogue(page)
        assert_theme(self, page, "dark")
        self.assertEqual(0, page["overflow"], "the page is wider than the phone")

    def test_rituals_light_is_the_catalogue_in_the_light_theme(self):
        # The reference draws rituals-light in the light theme, at 1440 px.
        address, page = self.state("rituals-light", theme="light")
        self.assert_catalogue(page)
        assert_theme(self, page, "light")

    # Criterion 1: a review, from its launch to its result -----------------

    def test_ritual_confirm_asks_the_scope_and_says_an_agent_is_used_before_launching(self):
        address, page = self.state("ritual-confirm")
        self.assert_review_head(page, None)
        assert_says(self, page, "panel-1", "Lancer la revue",
                    "Comprendre les causes récurrentes et proposer les corrections qui évitent leur retour.",
                    "Périmètre")
        assert_says(self, page, "change-preview-1",
                    "Produit un rapport et des propositions. Ne modifie aucun code ni paramètre.",
                    "Utilise un agent et consomme des tokens. Coût exact non connu.")
        assert_says(self, page, "actions-1", "Annuler")
        # The scope is chosen among the projects the cockpit serves, the
        # one of the review first.
        self.assertEqual(["Usine", "Notes", "Portfolio"], options_of(page))
        self.assertEqual(set(options_of(page)), projects_served(self, address),
                         "the scopes offered are not the projects the cockpit serves")
        assert_unwired(self, address, page, "Lancer la revue")

    def test_ritual_review_says_the_review_is_under_way_and_leads_to_its_run(self):
        address, page = self.state("ritual-review")
        self.assert_review_head(page, "1 · Revue")
        assert_says(self, page, "panel-1", "Revue en cours", "L’agent examine les sources du périmètre Usine.",
                    "Voir le run")
        assert_says(self, page, "readonly-note-1",
                    "Les propositions apparaîtront dans « Pour moi » à la fin de la revue.")
        # « Voir le run » opens the run of the review where runs are
        # followed: Runs.
        after = measure(address, PATH, click="Voir le run")[0]["after"]
        self.assertTrue(after["found"], "no control « Voir le run »")
        self.assertTrue(after["path"].startswith("/runs"), f"« Voir le run » leads to {after['path']}")

    def test_ritual_report_shows_the_proposals_to_choose_from(self):
        address, page = self.state("ritual-report")
        self.assert_review_head(page, "2 · Ton choix")
        assert_says(self, page, "panel-1", "Deux propositions à examiner", "Aucune correction lancée.")
        assert_says(self, page, "proposal-choice-1", "Regrouper les signalements d’un même incident",
                    "Détection et regroupement des alertes ; aucun changement produit.")
        assert_says(self, page, "proposal-choice-2", "Distinguer une lecture impossible d’un état vide",
                    "Une source indisponible peut masquer une attente.",
                    "Lecture et affichage de fraîcheur ; aucun changement des règles de jugement.")
        assert_says(self, page, "details-1", "Preuves et limites du rapport")
        assert_says(self, page, "actions-1", "Plus tard")
        assert_unwired(self, address, page, "Faire préparer ma sélection")

    def test_ritual_preparing_says_the_work_is_being_made_precise_and_nothing_is_started(self):
        address, page = self.state("ritual-preparing")
        self.assert_review_head(page, "3 · Travail précis")
        assert_says(self, page, "panel-1", "Préparation du travail",
                    "L’usine précise le périmètre, les critères et les limites des propositions choisies.",
                    "Aucune réalisation commencée.")

    def test_ritual_ready_shows_the_exact_work_its_result_and_its_limits_before_launching(self):
        address, page = self.state("ritual-ready")
        self.assert_review_head(page, "3 · Travail précis")
        assert_says(self, page, "panel-1", "Travail prêt à valider")
        assert_says(self, page, "h3-1", "Regrouper les signalements d’un même incident")
        assert_says(self, page, "change-preview-1", "Résultat attendu",
                    "Chaque défaut sélectionné est reproduit, corrigé et vérifié ; le résultat assemblé est prêt à juger.",
                    "Limites",
                    "Un lot limité aux propositions choisies. Aucun nouveau service, accès public ou changement de "
                    "production. Toute extension demande une nouvelle décision.")
        assert_says(self, page, "details-1", "Travail précis et critères")
        assert_says(self, page, "actions-1", "Revoir la sélection")
        assert_unwired(self, address, page, "Lancer les corrections")

    def test_ritual_execution_says_the_validated_work_is_under_way(self):
        address, page = self.state("ritual-execution")
        self.assert_review_head(page, "4 · Réalisation")
        assert_says(self, page, "panel-1", "Réalisation en cours",
                    "L’usine réalise et vérifie le travail validé. Le résultat reviendra pour ton jugement.")

    def test_ritual_delivered_says_the_result_is_ready_to_judge_without_deducing_an_acceptance(self):
        address, page = self.state("ritual-delivered")
        self.assert_review_head(page, None)
        assert_says(self, page, "panel-1", "Résultat prêt à juger",
                    "Aucune acceptation ni fusion n’est déduite de leur fin.")

    # Criterion 1: the preparation of the next release ---------------------

    def test_release_confirm_asks_the_project_and_says_nothing_is_fixed_or_launched(self):
        address, page = self.state("release-confirm")
        self.assert_release_head(page, "1 · Périmètre", "cible révisable")
        assert_says(self, page, "panel-1", "Préparer le cadrage", "Projet",
                    "Relire les objectifs, les décisions, les résultats vérifiés et les dépendances connues. "
                    "Proposer une cible de release et le jalon le plus utile pour avancer ou lever une incertitude.")
        assert_says(self, page, "change-preview-1",
                    "Tu pourras garder des questions ouvertes et modifier la proposition. "
                    "Aucun périmètre figé, aucune réalisation lancée.", "tokens")
        assert_says(self, page, "actions-1", "Retour aux rituels")
        # The project is chosen among those the cockpit serves, the one of
        # the framing first.
        self.assertEqual(["Notes", "Portfolio", "Usine"], options_of(page))
        self.assertEqual(set(options_of(page)), projects_served(self, address),
                         "the projects offered are not those the cockpit serves")
        assert_unwired(self, address, page, "Lancer la préparation")

    def test_release_review_says_the_preparation_is_under_way(self):
        address, page = self.state("release-review")
        self.assert_release_head(page, "2 · Préparation", "cible révisable")
        assert_says(self, page, "panel-1", "Préparation en cours",
                    "Rapprochement des acquis, de la cible et des questions ouvertes. "
                    "Le résultat sera une proposition à examiner.")

    def test_release_report_shows_the_proposed_framing_to_adjust(self):
        address, page = self.state("release-report")
        self.assert_release_head(page, "3 · Ton cadrage", "cible révisable")
        assert_says(self, page, "panel-1", "Proposition à examiner",
                    "Garde une cible provisoire et un prochain jalon précis. Les questions peuvent rester ouvertes.")
        assert_says(self, page, "r-sultat-attendu-pour-cette-release-1",
                    "Permettre à un nouvel utilisateur de retrouver et exporter ses notes sans aide.")
        assert_says(self, page, "release-columns-1", "Acquis à conserver", "✓ Créer et retrouver une note",
                    "✓ Conserver ses notes après reconnexion", "Critères restant à satisfaire",
                    "○ Exporter les notes au format choisi", "○ Vérifier le parcours sans assistance")
        assert_says(self, page, "release-decision-1", "Le partage de notes est-il nécessaire dès cette release ?",
                    "Garder la question ouverte", "Reporter après cette release",
                    "Inclure dans la cible de cette release")
        assert_says(self, page, "prochain-jalon-1", "Faire essayer le parcours complet à trois utilisateurs")
        assert_says(self, page, "comment-v-rifier-ce-jalon-1",
                    "Trois essais documentés ; blocages et réussites observés.")
        assert_says(self, page, "release-notice-1", "Estimation non disponible",
                    "Historique comparable insuffisant. Prochaine réévaluation après le jalon.")
        assert_says(self, page, "details-1", "Sources et inconnues")
        assert_says(self, page, "actions-1", "Revenir au projet sans conserver")
        assert_unwired(self, address, page, "Conserver ce cadrage")

    def test_release_saved_says_the_framing_is_kept_in_the_project_and_leads_to_it(self):
        address, page = self.state("release-saved")
        self.assert_release_head(page, "4 · Projet mis à jour", "cadrage conservé")
        assert_says(self, page, "panel-1", "Cadrage conservé",
                    "La cible révisable, le prochain jalon et les décisions ouvertes sont visibles dans le projet Notes.",
                    "Le jalon reste à préparer avant toute réalisation. Conserver le cadrage n’approuve pas une Spec "
                    "ni un lancement de travaux.", "Revoir le cadrage")
        # « Voir le projet » opens the page of the project Notes.
        after = measure(address, PATH, click="Voir le projet")[0]["after"]
        self.assertEqual((True, "/projet/notes"), (after["found"], after["path"]),
                         "« Voir le projet » does not open the page of the project Notes")

    # Criterion 1: the same entry point as the ordinary data ---------------

    def test_the_destination_is_reached_from_the_other_destinations_and_leads_to_them(self):
        # From the other destinations the cockpit serves, the entry
        # « Rituels » of their navigation opens this destination, at
        # GET /rituels, with its catalogue.
        address = self.tree.launch("rituals-content")
        for start in ("/", "/journal"):
            frame = measure(address, start, click="Rituels")[0]
            self.assertEqual(start, frame["path"], f"{start} is not served at its own address")
            after = frame["after"]
            self.assertTrue(after["found"], f"no entry « Rituels » in the navigation of {start}")
            assert_rituals(self, after)
            self.assert_catalogue(after)
        # From this destination, each other entry of the navigation B opens
        # the address of its destination.
        reached = {}
        for entry in ("Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Analyses"):
            after = measure(address, PATH, click=entry)[0]["after"]
            reached[entry] = after["path"] if after["found"] else None
        self.assertEqual(
            {"Vue d’ensemble": "/", "Projets": "/projets", "Runs": "/runs", "Journal": "/journal",
             "Usine": "/usine", "Analyses": "/analyses"},
            reached,
        )

    def test_the_proposals_of_a_report_follow_the_data_the_cockpit_serves_not_a_page_of_its_own(self):
        # The same dataset, at another commit, where the second proposal of
        # the report has another title: the page says the new title, in
        # that proposal -- a page drawn for the state would not change.
        reworded = self.tree.reword("ritual-report", {
            "Distinguer une lecture impossible d’un état vide": "Signaler une source muette depuis une heure"})
        address, page = self.state("ritual-report", commit=reworded)
        assert_says(self, page, "proposal-choice-2", "Signaler une source muette depuis une heure")
        self.assertNotIn("Distinguer une lecture impossible", page["text"])

    def test_the_framing_of_a_release_follows_the_data_the_cockpit_serves_not_a_page_of_its_own(self):
        # The same, for the framing proposed: another criterion left to
        # satisfy, another open question.
        reworded = self.tree.reword("release-report", {
            "Exporter les notes au format choisi": "Importer les notes d’un autre outil",
            "Le partage de notes est-il nécessaire dès cette release ?":
                "L’export en PDF est-il nécessaire dès cette release ?",
        })
        address, page = self.state("release-report", commit=reworded)
        assert_says(self, page, "release-columns-1", "○ Importer les notes d’un autre outil")
        assert_says(self, page, "release-decision-1", "L’export en PDF est-il nécessaire dès cette release ?")
        self.assertNotIn("Exporter les notes au format choisi", page["text"])
        self.assertNotIn("Le partage de notes", page["text"])


if __name__ == "__main__":
    unittest.main()
