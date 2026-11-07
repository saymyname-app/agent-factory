#!/usr/bin/env python3
"""Criterion tests 1 and 2 of K « Vue d'ensemble — indicateurs réels et
cartes Runs partagées » (af-jr8bsh; Spec af-fgcw0d, user stories 148 and
151, decisions « Pas de valeur de démonstration en production » 2 and
« Panorama et métriques », Testing Decisions 1 and 8): the four indicators
of the home, computed as the Analyses compute them, each opening its view.
The cards of the recent runs are in home-recent-runs-test.py.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset -- home-content of the profile, or one the
case writes record by record (analyses_destination.sources: the records of
the flow and what GitHub answers, at noon on Monday 12/10/2026, Paris) in a
commit of its own tree -- and reads, over HTTP, the indicators of the home
at GET / and the views of the Analyses at GET /analyses.

Criterion 1 is false if an indicator of the home says another value than
its view in the Analyses, or if it does not open that view. Criterion 2 is
false if the home shows a value -- a figure of example -- for an indicator
the Analyses say unavailable, or does not say why. Criterion 3 (af-unu7jp,
replacement of K) is false if « Décisions à prendre » of the home or
« Décisions ouvertes » of the Analyses says another number than the
requests « Ce qui t’attend » lists, relaunches of a session or an order
included, or if a signal of an unknown producer leaves « Pour moi »; its
case declares a tracker as the doors of the Factory write it.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyses_destination import LaunchTree, Page, ci_run, decision, result, served, sources  # noqa: E402
from home_destination import fetch  # noqa: E402
from project_destination import descriptor_of, launch_declared  # noqa: E402

# The four indicators of the home, by their label, as the reference names them.
DECISIONS, RESULTS, DELAY, CI = ("Décisions à prendre", "Résultats fusionnés", "Délai de livraison",
                                 "Vérifications CI réussies")

# Six results of the flow over the seven days 06/10 -> 12/10 -- four merged,
# one merged before them, one delivered and not judged --, three decisions
# open and one answered, thirteen CI runs completed of which nine succeeded.
COMPUTED = dict(
    results=[
        result("Export des notes", "Notes", "06/10 09:00", "06/10 10:30", "06/10 11:00", "06/10 11:10"),
        result("Recherche plein texte", "Notes", "08/10 14:00", "08/10 17:00", "08/10 18:00", "08/10 18:20"),
        result("Reprise des sessions", "Usine", "11/10 08:00", "11/10 09:00", "11/10 09:15", "11/10 09:20"),
        result("Page Portfolio", "Portfolio", "12/10 07:00", "12/10 08:40", "12/10 10:40", "12/10 11:00"),
        result("Ancienne livraison", "Notes", "30/09 09:00", "01/10 09:00", "02/10 09:00", "02/10 10:00"),
        result("Résultat à juger", "Usine", "10/10 09:00", "10/10 15:00", None, None),
    ],
    decisions=[
        decision("Choisir le format d’export", "Notes", "08/10 10:00"),
        decision("Valider la reprise", "Usine", "10/10 16:00"),
        decision("Nommer la page", "Portfolio", "11/10 11:00"),
        decision("Ordre des colonnes", "Notes", "12/10 08:00", answered="12/10 09:00"),
    ],
    repository="saymyname-app/agent-factory",
    ci_runs=[
        ci_run(900, "failure", "03/10 10:00"),
        ci_run(901, "success", "06/10 09:00"), ci_run(902, "success", "06/10 10:00"),
        ci_run(903, "failure", "06/10 11:00"), ci_run(904, "success", "07/10 10:00"),
        ci_run(905, "success", "08/10 09:00"), ci_run(906, "success", "08/10 10:00"),
        ci_run(907, "success", "08/10 11:00"), ci_run(908, "failure", "08/10 12:00"),
        ci_run(909, "failure", "10/10 10:00"), ci_run(910, "success", "11/10 09:00"),
        ci_run(911, "success", "11/10 10:00"), ci_run(912, "success", "12/10 09:00"),
        ci_run(913, "failure", "12/10 10:00"), ci_run(914, None, "12/10 11:50"),
    ],
)


def home(address: str, seconds: float = 15) -> Page:
    """The home the cockpit at `address` serves at GET /, read over HTTP
    once its four indicators are drawn and no source it shows is still
    being read for the first time."""
    deadline = time.monotonic() + seconds
    while True:
        page = Page(address, "/")
        drawn = all(page.says(f"metric-label-{n}") for n in range(1, 5))
        if (drawn and "en cours de lecture" not in page.text) or time.monotonic() > deadline:
            return page


def indicator(page: Page, label: str) -> tuple[str, str | None]:
    """What the indicator of the home labelled `label` says after its label,
    on one line, and where it leads; ('', None) when the home has none."""
    for n in range(1, 5):
        if page.says(f"metric-label-{n}") == label:
            said = page.says(f"metric-{n}")
            links = list(page.links(f"metric-{n}").values())
            return said[len(label):].strip() if said.startswith(label) else said, (links[0] if links else None)
    return "", None


def one_line(fragment: str) -> str:
    """The text of an HTML fragment on one line, spaces collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


class HomeIndicators(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_says(self, said: str, value: str, label: str) -> None:
        self.assertRegex(said, rf"^{re.escape(value)}(?![\d,])",
                         f"the indicator « {label} » of the home does not say {value}")

    def assert_unavailable(self, said: str, reason: str, label: str) -> None:
        """Said unavailable, with its reason, and no figure."""
        self.assertTrue(said.startswith("indisponible"), f"the indicator « {label} » of the home is not "
                                                         f"unavailable: « {said} »")
        self.assertIn(reason, said, f"the indicator « {label} » of the home does not say why it is unavailable")
        self.assertNotRegex(said, r"\d", f"the unavailable indicator « {label} » of the home shows a figure")

    # --- criterion 1 -------------------------------------------------------------

    def test_home_content_counts_the_decisions_and_results_the_analyses_count(self):
        """home-content: two requests wait for Benjamin and the flow proves
        no merge over the seven days. The home says 2 and 0, as the views
        « Activité » and « Résultats » of the Analyses -- not the 6 merged
        results of example the home drew so far."""
        address = self.tree.launch("home-content")
        page = home(address)
        self.assert_says(indicator(page, DECISIONS)[0], "2", DECISIONS)
        self.assert_says(indicator(page, RESULTS)[0], "0", RESULTS)
        self.assertIn("2 décisions ouvertes", served(address, "Activité").says("p-1"))
        self.assertEqual("Aucun résultat sur sept jours · fusion prouvée", served(address, "Résultats").says("p-1"))

    def test_the_home_shows_the_four_indicators_the_records_give_as_the_analyses_do(self):
        """Four results merged within the seven days (from publication to
        proven merge 130, 260, 80 and 240 minutes: median 3 h 05), three
        decisions open, 9 CI runs succeeded of 13 completed (69 %): the home
        says each, and each view of the Analyses says the same."""
        address = launch_declared(self.tree, "home-indicators-computed",
                                  sources("home-indicators-computed", **COMPUTED))
        page = home(address)
        self.assert_says(indicator(page, DECISIONS)[0], "3", DECISIONS)
        self.assert_says(indicator(page, RESULTS)[0], "4", RESULTS)
        self.assert_says(indicator(page, DELAY)[0], "3 h 05", DELAY)
        self.assert_says(indicator(page, CI)[0], "69 %", CI)
        self.assertIn("3 décisions ouvertes", served(address, "Activité").says("p-1"))
        self.assertEqual("4 résultats sur sept jours · fusion prouvée", served(address, "Résultats").says("p-1"))
        self.assertEqual("Délai médian : 3 h 05 · 4 résultats fusionnés", served(address, "Délais").says("p-1"))
        self.assertIn("69 %", served(address, "Vérifications").says("p-1"))

    def test_each_indicator_of_the_home_opens_its_view_of_the_analyses(self):
        """Followed from the home, each indicator opens the view of the
        Analyses that computes it, under its heading."""
        address = launch_declared(self.tree, "home-indicators-views",
                                  sources("home-indicators-views", **COMPUTED))
        page = home(address)
        views = {DECISIONS: "Décisions ouvertes", RESULTS: "Résultats fusionnés", DELAY: "Où passe le temps ?",
                 CI: "Vérifications CI réussies"}
        opened = {}
        for label in views:
            href = indicator(page, label)[1]
            opened[label] = Page(address, href).says("h2-1") if href and href.startswith("/analyses") else href
        self.assertEqual(views, opened, "an indicator of the home does not open its view of the Analyses")

    # --- criterion 2 -------------------------------------------------------------

    def test_home_content_says_the_delay_and_the_ci_unavailable_as_the_analyses_do(self):
        """home-content: no merge over the seven days and no repository
        declared for the CI. The Analyses say the delay and the rate of the
        CI unavailable, with their reason; so does the home, instead of the
        2 h 40 and 94 % of example it drew so far."""
        address = self.tree.launch("home-content")
        page = home(address)
        self.assert_unavailable(indicator(page, DELAY)[0], "aucun résultat fusionné sur la période", DELAY)
        self.assert_unavailable(indicator(page, CI)[0], "aucun dépôt GitHub n’est déclaré pour la CI du cockpit",
                                CI)
        self.assertEqual("aucun résultat fusionné sur la période", served(address, "Délais").method().get("Raison"))
        self.assertIn("aucun dépôt GitHub n’est déclaré pour la CI du cockpit",
                      served(address, "Vérifications").method().get("Raison", ""))

    def test_without_a_readable_ci_the_home_says_it_unavailable_and_computes_the_others(self):
        """GitHub answers nothing for the CI: the home says its indicator
        unavailable with the reason the Analyses give, and still computes
        the three others from the flow."""
        without_ci = {key: value for key, value in COMPUTED.items() if key not in ("repository", "ci_runs")}
        address = launch_declared(self.tree, "home-indicators-without-ci",
                                  sources("home-indicators-without-ci", **without_ci))
        page = home(address)
        self.assert_unavailable(indicator(page, CI)[0], "aucun dépôt GitHub n’est déclaré pour la CI du cockpit",
                                CI)
        self.assertIn("aucun dépôt GitHub n’est déclaré pour la CI du cockpit",
                      served(address, "Vérifications").method().get("Raison", ""))
        self.assert_says(indicator(page, DECISIONS)[0], "3", DECISIONS)
        self.assert_says(indicator(page, RESULTS)[0], "4", RESULTS)
        self.assert_says(indicator(page, DELAY)[0], "3 h 05", DELAY)

    # --- criterion 3 -------------------------------------------------------------

    def test_the_relaunches_waiting_count_in_the_decisions_of_the_home_and_of_the_analyses(self):
        """The tracker holds, as the doors of the Factory write them, a
        question of the escalation door, a session the loop guard paused and
        an order paused by bin/order-pause -- the last two in no record of
        the journal of decisions --, and a signal of a producer the cockpit
        has no reading for. « Ce qui t’attend » lists the three requests;
        « Décisions à prendre » on the home and « Décisions ouvertes » in
        the Analyses say 3, and the view of the decisions lists these three
        requests. The signal stays in « Pour moi » as information, counted
        nowhere (rule of Benjamin, 07/11/2026: every request listed counts,
        relaunches included, the same number everywhere)."""
        options = json.dumps([{"lettre": "a", "option": "Garder le format actuel",
                               "consequence": "L’export reste en CSV", "recommande": True}], ensure_ascii=False)
        beads = [
            {"id": "af-esc1", "title": "Format de l’export", "status": "open", "labels": [], "notes": "",
             "description": "", "created_at": "2026-10-12T09:00:00+02:00",
             "metadata": {"gc.needs_benjamin": "Choisir le format de l’export des notes",
                          "gc.escalation_pourquoi": "Deux formats tiennent la Spec ; elle n’en fixe aucun.",
                          "gc.escalation_que_faire": options, "gc.escalation_bloquant": "false",
                          "gc.escalation_horodatage": "2026-10-12T09:00:00+02:00"}},
            # A session the Factory paused waits on the operator, to relaunch.
            {"id": "af-loop1", "title": "[session-loop] s-1", "status": "open", "labels": [], "notes": "",
             "description": "", "created_at": "2026-10-12T10:00:00+02:00",
             "metadata": {"gc.source": "factory-session-loop-guard", "gc.session_id": "s-1",
                          "gc.escalation_mayor_paged_at": "2026-10-12T10:00:00+02:00"}},
            # An order paused by its door, to relaunch.
            {"id": "af-ord1", "title": "Ordre en pause : convoy-advance", "status": "open",
             "labels": ["order-pause"], "notes": "", "description": "", "created_at": "2026-10-12T10:30:00+02:00",
             "metadata": {"gc.order_pause": "convoy-advance", "gc.order_pause_by": "mayor",
                          "gc.order_pause_words": "pause : intégration rouge",
                          "gc.order_pause_at": "2026-10-12T10:30:00+02:00", "gc.order_pause_reason": ""}},
            # A signal of a producer the cockpit has no reading for.
            {"id": "af-sig1", "title": "Disk quota at 92% on /var", "status": "open", "labels": [], "notes": "",
             "description": "backup volume nearly full", "created_at": "2026-10-12T11:00:00+02:00",
             "metadata": {"gc.source": "disk-watch"}},
        ]
        dataset = {"generated_at": "2026-10-12T12:00:00+02:00", "synthetic": True,
                   "ui": {"id": "home-decisions-relaunches", "page": "home"},
                   "projects": [descriptor_of(self.tree, "agent-factory")], "repos": {},
                   "tracker": {"beads": {bead["id"]: bead for bead in beads}}}
        address = launch_declared(self.tree, "home-decisions-relaunches", dataset)
        page = home(address)
        _, _, body = fetch(address + "/")
        inbox = body[body.index('id="pn-inbox"'):]
        listed = [one_line(said) for said in
                  re.findall(r'(?s)<button[^>]*class="pn-request"[^>]*data-request="[^"]+"[^>]*>\s*<strong[^>]*>(.*?)'
                             r'</strong>', inbox)]
        self.assertEqual(3, len(listed), f"« Ce qui t’attend » does not list the three requests: {listed}")
        self.assertIn("Choisir le format de l’export des notes", listed)

        self.assert_says(indicator(page, DECISIONS)[0], "3", DECISIONS)
        view = served(address, "Activité")
        self.assertIn("3 décisions ouvertes", view.says("p-1"),
                      "« Décisions ouvertes » of the Analyses does not count the three requests waiting")
        history = re.search(r'(?s)<div class="an-history"[^>]*>(.*?)</div>\s*(?:<p|$)',
                            fetch(address + view.path)[2])
        in_analyses = [one_line(said) for said in re.findall(r"(?s)<strong[^>]*>(.*?)</strong>",
                                                             history.group(1) if history else "")]
        self.assertEqual(sorted(listed), sorted(in_analyses),
                         "the view of the decisions of the Analyses does not list what « Ce qui t’attend » lists")

        self.assertIn('id="s-af-sig1"', inbox, "the signal of an unknown producer is no longer in « Pour moi »")
        self.assertNotIn('data-request="af-sig1"', body, "the signal of an unknown producer is listed as a request")


if __name__ == "__main__":
    unittest.main()
