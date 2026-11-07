#!/usr/bin/env python3
"""Criterion test 3 of K2 « Vue d'ensemble — indicateurs réels et cartes
Runs partagées », replacement of K (af-unu7jp; Spec af-fgcw0d, user
stories 148 and 76, decision « État D01 commun aux vues » 2, Testing
Decisions 1 and 8; rule of Benjamin, 07/11/2026: the indicator of the
decisions counts every request « Ce qui t’attend » lists, relaunches
included, the same number everywhere). Criteria 1 and 2 are K's, in
home-indicators-test.py and home-recent-runs-test.py.

The case declares a dataset of its own in the profile of the tree under
test and launches the real cockpit on it with the launcher of the profile,
bin/project-launch (project_destination.launch_declared: the next case sees
none of it). Its tracker holds, as the doors of the Factory write them, a
question of the escalation door, a session the loop guard paused and an
order paused by bin/order-pause -- the last two in no record of the journal
of decisions --, and a signal of a producer the cockpit has no reading for.

Read over HTTP: the requests « Ce qui t’attend » lists and the indicator
« Décisions à prendre » at GET /, then the view « Activité » of the
Analyses, its « Décisions ouvertes » and the decisions it lists.

False if one of the two numbers differs from the number of requests
« Ce qui t’attend » lists or leaves out a relaunch, or if the signal of the
unknown producer is no longer shown in « Pour moi » as information.
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

from analyses_destination import LaunchTree, Page, served  # noqa: E402
from home_destination import fetch  # noqa: E402
from project_destination import descriptor_of, launch_declared  # noqa: E402

DECISIONS = "Décisions à prendre"


def one_line(fragment: str) -> str:
    """The text of an HTML fragment on one line, spaces collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def decisions_indicator(address: str, seconds: float = 15) -> str:
    """What the indicator « Décisions à prendre » of the home says after its
    label, read over HTTP once the four indicators are drawn and no source
    is still being read for the first time; '' when the home has none."""
    deadline = time.monotonic() + seconds
    while True:
        page = Page(address, "/")
        drawn = all(page.says(f"metric-label-{n}") for n in range(1, 5))
        if (drawn and "en cours de lecture" not in page.text) or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    for n in range(1, 5):
        if page.says(f"metric-label-{n}") == DECISIONS:
            said = page.says(f"metric-{n}")
            return said[len(DECISIONS):].strip() if said.startswith(DECISIONS) else said
    return ""


class HomeDecisionsRelaunches(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_the_relaunches_waiting_count_in_the_decisions_of_the_home_and_of_the_analyses(self):
        """« Ce qui t’attend » lists the question and the two relaunches;
        « Décisions à prendre » on the home and « Décisions ouvertes » in
        the Analyses say 3, and the view of the decisions lists these three
        requests. The signal stays in « Pour moi » as information, listed
        as no request."""
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

        said = decisions_indicator(address)
        _, _, body = fetch(address + "/")
        inbox = body[body.index('id="pn-inbox"'):]
        listed = [one_line(what) for what in
                  re.findall(r'(?s)<button[^>]*class="pn-request"[^>]*data-request="[^"]+"[^>]*>\s*<strong[^>]*>(.*?)'
                             r'</strong>', inbox)]
        self.assertEqual(3, len(listed), f"« Ce qui t’attend » does not list the three requests: {listed}")
        self.assertIn("Choisir le format de l’export des notes", listed)

        self.assertRegex(said, r"^3(?![\d,])", f"the indicator « {DECISIONS} » of the home does not say 3: "
                                               f"« {said} »")
        view = served(address, "Activité")
        self.assertIn("3 décisions ouvertes", view.says("p-1"),
                      "« Décisions ouvertes » of the Analyses does not count the three requests waiting")
        history = re.search(r'(?s)<div class="an-history"[^>]*>(.*?)</div>\s*(?:<p|$)',
                            fetch(address + view.path)[2])
        in_analyses = [one_line(what) for what in re.findall(r"(?s)<strong[^>]*>(.*?)</strong>",
                                                             history.group(1) if history else "")]
        self.assertEqual(sorted(listed), sorted(in_analyses),
                         "the view of the decisions of the Analyses does not list what « Ce qui t’attend » lists")

        self.assertIn('id="s-af-sig1"', inbox, "the signal of an unknown producer is no longer in « Pour moi »")
        self.assertNotIn('data-request="af-sig1"', body, "the signal of an unknown producer is listed as a request")


if __name__ == "__main__":
    unittest.main()
