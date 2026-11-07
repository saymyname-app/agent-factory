#!/usr/bin/env python3
"""Criterion test 1 of K « Vue d'ensemble — indicateurs réels et cartes
Runs partagées » (af-jr8bsh; Spec af-fgcw0d, user stories 151 and 175,
decisions « Une seule carte de run » 7 and « Panorama et métriques »,
Testing Decisions 1 and 8): the cards of the recent runs on the home are
the cards of the page Runs. The indicators are in home-indicators-test.py.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset of the profile -- home-content, or
runs-all and its five workflows of every status, or runs-recent where the
waiting and abandoned ones are among the last started -- and reads the part
« Derniers runs » of the home at GET / -- the cards drawn there, in the
page or in the document of the frame the reference draws there -- and the
list of the page Runs at GET /runs (filter « Tous »): over HTTP, the markup
of each card, and in a headless Chromium, how each card is drawn.

False if a card of the home is another rendering than the card of the same
run on the page Runs (another markup, another text, another link, another
style) -- the home keeping a copy of the card of its own --, or if the
recent runs are not those of every status, the last started first.
"""

from __future__ import annotations

import html
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyses_destination import Keyboard  # noqa: E402
from home_destination import LaunchTree, fetch  # noqa: E402

# A card of a run: the link to the run's own page, as the page Runs draws it.
CARD = re.compile(r'<a\b[^>]*\bhref="(/runs/run\?id=[^"]+)"[^>]*>.*?</a>', re.S)
# The anchors of a page are numbered per page: not a part of the card.
ANCHOR = re.compile(r'\sdata-anchor="[^"]*"')

# How a card and each element inside it are drawn: what makes it look the
# same on two pages -- not its size, which follows the column it is in. The
# card is looked for in the page and in the documents of its frames.
STYLE = """(href => {
  const documents = [document, ...Array.from(document.querySelectorAll('iframe'))
    .map(frame => frame.contentDocument).filter(Boolean)];
  const card = documents.flatMap(doc => Array.from(doc.querySelectorAll('a[href]')))
    .find(el => el.getAttribute('href') === href && el.querySelector('h2, h3'));
  if (!card) return null;
  return [card, ...card.querySelectorAll('*')].map(el => {
    const s = el.ownerDocument.defaultView.getComputedStyle(el);
    return [el.tagName, s.display, s.fontFamily, s.fontSize, s.fontWeight, s.lineHeight, s.color,
            s.backgroundColor, s.borderTopWidth, s.borderTopStyle, s.borderTopColor, s.borderRadius,
            s.paddingTop, s.paddingLeft, s.textDecorationLine].join(' | ');
  });
})(%s)"""


def runs_cards(address: str) -> dict[str, str]:
    """The cards of the page Runs, filter « Tous », in the order of the
    page: the address of each run -> its markup, anchors aside."""
    _, _, page = fetch(address + "/runs?filtre=tous")
    main = page[page.find("<main"):]
    return {card.group(1): ANCHOR.sub("", card.group(0)) for card in CARD.finditer(main)}


def home_cards(address: str) -> dict[str, str]:
    """The cards of the part « Derniers runs » of the home, in their order:
    those drawn in the page, then those of the document a frame of the part
    shows (its `srcdoc`, or the page its `src` names): the address of each
    run -> its markup, anchors aside."""
    _, _, page = fetch(address + "/")
    start = page.find(">Derniers runs<")
    if start < 0:
        return {}
    part = page[start:page.find("</section>", start)]
    documents = [part]
    for frame in re.finditer(r"<iframe\b[^>]*>", part):
        inline = re.search(r'\ssrcdoc="([^"]*)"', frame.group(0))
        source = re.search(r'\ssrc="([^"]*)"', frame.group(0))
        if inline:
            documents.append(html.unescape(inline.group(1)))
        elif source:
            documents.append(fetch(address + html.unescape(source.group(1)))[2])
    return {card.group(1): ANCHOR.sub("", card.group(0)) for document in documents
            for card in CARD.finditer(re.sub(r"<iframe\b[^>]*>", "", document))}


def text(markup: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", markup).split())


class HomeRecentRuns(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_cards_of_runs(self, address: str) -> dict[str, str]:
        """Each card of the home is, in the page itself, the card the page
        Runs draws for the same run -- read before or after the home, as an
        open run's duration may have moved by a second between the two."""
        before = runs_cards(address)
        cards = home_cards(address)
        after = runs_cards(address)
        self.assertTrue(cards, "the home draws no card of a run in its part « Derniers runs »")
        for href, card in cards.items():
            self.assertIn(card, (before.get(href), after.get(href)),
                          f"the card of {href} on the home is not the card the page Runs draws")
        return cards

    def test_home_content_draws_the_card_the_page_runs_draws(self):
        """home-content: the run of « Reprise du cockpit » waits for
        Benjamin's decision. The home draws its card, in the page, as the
        page Runs draws it, leading to the page of the run."""
        address = self.tree.launch("home-content")
        cards = self.assert_cards_of_runs(address)
        said = [text(card) for card in cards.values()]
        self.assertTrue(said and all(part in said[0] for part in ("Livraison D01", "Ta décision",
                                                                  "Reprise du cockpit")),
                        f"the first card of the home is not the run of « Reprise du cockpit »: {said}")
        status, _, page = fetch(address + next(iter(cards)))
        self.assertEqual(200, status)
        self.assertIn("Reprise du cockpit", page, "the card does not lead to the page of its run")

    def test_the_recent_runs_are_of_every_status_the_last_started_first(self):
        """runs-all: five workflows, started at 15:00 (in progress), 14:10
        (merged), 13:45 (a maintenance, finished), 13:00 (waits for Benjamin)
        and 12:20 (abandoned); runs-recent: the same, the one that waits
        started at 14:40 and the abandoned one at 14:30. The home draws the
        three last started, of whatever status -- in progress, merged and
        finished, then in progress, waiting and abandoned --, the last
        first, each as the page Runs draws it."""
        for dataset, expected in (
            ("runs-all", [("Reprise du cockpit", "En cours", "Début 15:00 (Paris)"),
                          ("Recherche dans les notes", "Fusionné", "Début 14:10 (Paris)"),
                          ("Corriger le tri des demandes", "Terminé", "Début 13:45 (Paris)")]),
            ("runs-recent", [("Reprise du cockpit", "En cours", "Début 15:00 (Paris)"),
                             ("Préciser le périmètre du dossier", "Ta décision", "Début 14:40 (Paris)"),
                             ("Ancienne proposition de filtre", "Abandonné", "Début 14:30 (Paris)")]),
        ):
            with self.subTest(dataset=dataset):
                address = self.tree.launch(dataset)
                cards = [text(card) for card in self.assert_cards_of_runs(address).values()]
                self.assertEqual(len(expected), len(cards),
                                 f"{dataset}: the home does not draw the three runs last started: {cards}")
                self.assertEqual(expected, [tuple(part for part in parts if part in card)
                                            for card, parts in zip(cards, expected)],
                                 f"{dataset}: the home does not draw the three runs last started, "
                                 f"the last first: {cards}")
                self.tree.stop_all()

    def test_a_card_of_the_home_is_drawn_as_on_the_page_runs(self):
        """runs-all, in a headless Chromium, dark at 1440 px and light at
        390 px: each card of the home and each element inside it have the
        font, colours, border and spacing of the same card on the page
        Runs."""
        address = self.tree.launch("runs-all")
        hrefs = list(home_cards(address))
        self.assertTrue(hrefs, "the home draws no card of a run in its part « Derniers runs »")
        for width, theme in ((1440, "dark"), (390, "light")):
            on_home, on_runs = Keyboard(address + "/", width, theme), Keyboard(address + "/runs", width, theme)
            try:
                for href in hrefs:
                    drawn = on_runs.evaluate(STYLE % repr(href))
                    self.assertIsNotNone(drawn, f"the page Runs draws no card for {href}")
                    self.assertEqual(drawn, on_home.evaluate(STYLE % repr(href)),
                                     f"the card of {href} is not drawn on the home as on the page Runs "
                                     f"({width} px, {theme})")
            finally:
                on_home.close()
                on_runs.close()


if __name__ == "__main__":
    unittest.main()
