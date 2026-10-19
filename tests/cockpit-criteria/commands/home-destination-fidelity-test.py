#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02R2, af-r2c0tx, replacing T02R af-vbb4ol; Spec af-2zseit,
Testing Decisions 5): the anchors and the tokens the reference approves, in
each of the ten states home-*.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET / -- as a headless Chromium renders it, at
1440 and 390 px, in the dark and the light theme, and from its style
sources. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-home/states/<state>.html), whose
values are written below, each case naming those of its state:

- every anchor of the state, numbered ones (`div-3`, `strong-1`, `circle-7`)
  as much as named ones, once, drawn by the same element inside the same
  anchor, in the type of the reference (its computed font-family and
  line-height);
- the tokens of the reference under their names (`--bg`, `--surface`,
  `--line`, `--ink`, `--muted`, `--accent`, `--ok`, `--warn`), with its
  values, in the dark and the light theme.

False if an anchor of the reference is missing, doubled, drawn otherwise or
elsewhere, or set in another type, or if a token of the reference is absent
or has another value: the hierarchy approved is not the one served.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402
    LaunchTree, anchor_deviations, measure, measure_until, outline, token_deviations,
)

WIDTHS = (1440, 390)
THEMES = ("dark", "light")

# The tokens of the reference, the same in its ten home states: their names
# and their values, in the dark and the light theme.
TOKENS = {
    "dark": {"--bg": "#0d1015", "--surface": "#161b23", "--line": "#2a3240", "--ink": "#ecedf3",
             "--muted": "#9aa6b9", "--accent": "#99aaff", "--ok": "#55c89d", "--warn": "#efc778"},
    "light": {"--bg": "#f3f5f9", "--surface": "#fff", "--line": "#dbe0e8", "--ink": "#17202e",
              "--muted": "#657185", "--accent": "#415fce", "--ok": "#1c7954", "--warn": "#97691e"},
}

# Every anchor of the frozen page of a state, in the order of the page: the
# anchor, the element that draws it, its line-height, indented under the
# anchor that holds it -- all in system-ui, the type of the reference. Read
# from the frozen pages as headless Chromium renders them at 1440 and 390 px
# in the dark and the light theme (the four renderings agree); the states
# drawn the same share one outline.

# home-content, home-content-full, home-narrow, home-light
CONTENT_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  metric-grid-1 div normal
    metric-1 div normal
      metric-label-1 span normal
      strong-2 strong normal
      small-3 small normal
    metric-2 div normal
      metric-label-2 span normal
      strong-3 strong normal
      small-4 small normal
    metric-3 div normal
      metric-label-3 span normal
      strong-4 strong normal
      small-5 small normal
    metric-4 div normal
      metric-label-4 span normal
      strong-5 strong normal
      small-6 small normal
  bilan-1 details normal
    summary-1 summary normal
    chart-key-1 div normal
      span-1 span normal
      span-2 span normal
      span-3 span normal
    volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1 svg normal
      g-1 g normal
        line-1 line normal
        line-2 line normal
        line-3 line normal
        line-4 line normal
      g-2 g normal
        text-1 text normal
        text-2 text normal
        text-3 text normal
        text-4 text normal
        text-5 text normal
        text-6 text normal
        text-7 text normal
        text-8 text normal
        text-9 text normal
        text-10 text normal
        text-11 text normal
      polyline-1 polyline normal
      circle-1 circle normal
        title-1 title normal
      circle-2 circle normal
        title-2 title normal
      circle-3 circle normal
        title-3 title normal
      circle-4 circle normal
        title-4 title normal
      circle-5 circle normal
        title-5 title normal
      circle-6 circle normal
        title-6 title normal
      circle-7 circle normal
        title-7 title normal
      polyline-2 polyline normal
      circle-8 circle normal
        title-8 title normal
      circle-9 circle normal
        title-9 title normal
      circle-10 circle normal
        title-10 title normal
      circle-11 circle normal
        title-11 title normal
      circle-12 circle normal
        title-12 title normal
      circle-13 circle normal
        title-13 title normal
      circle-14 circle normal
        title-14 title normal
      polyline-3 polyline normal
      circle-15 circle normal
        title-15 title normal
      circle-16 circle normal
        title-16 title normal
      circle-17 circle normal
        title-17 title normal
      circle-18 circle normal
        title-18 title normal
      circle-19 circle normal
        title-19 title normal
      circle-20 circle normal
        title-20 title normal
      circle-21 circle normal
        title-21 title normal
    link-1 button normal
  panel-1 section normal
    section-heading-1 div normal
      h2-1 h2 normal
      link-2 button normal
    overview-runs-1 iframe normal
  inbox-1 div normal
    panel-2 div normal
      h2-2 h2 normal
      request-1 button normal
        strong-6 strong normal
        small-7 small normal
      request-2 button normal
        strong-7 strong normal
        small-8 small normal
    panel-3 article normal
      small-9 small normal
      h2-3 h2 normal
      p-1 p 22.5px
      resource-list-1 div normal
        button-7 button normal
          span-4 span normal
            strong-8 strong normal
            small-10 small normal
          span-5 span normal
        button-8 button normal
          span-6 span normal
            strong-9 strong normal
            small-11 small normal
          span-7 span normal
        details-1 details normal
          summary-2 summary normal
          p-2 p 21px
        details-2 details normal
          summary-3 summary normal
          p-3 p 21px
      actions-possibles-1 div normal
        button-9 a normal
        button-10 button normal
  panel-4 section normal
    h2-4 h2 normal
    rows-1 div normal
      row-1 div normal
        div-3 div normal
          strong-10 strong normal
          small-12 small normal
          small-stats-1 div normal
            span-8 span normal
            span-9 span normal
          release-info-1 div normal
        span-10 span normal
      row-2 div normal
        div-4 div normal
          strong-11 strong normal
          small-13 small normal
          small-stats-2 div normal
            span-11 span normal
            span-12 span normal
          release-info-2 div normal
        span-13 span normal
      row-3 div normal
        div-5 div normal
          strong-12 strong normal
          small-14 small normal
          small-stats-3 div normal
            span-14 span normal
            span-15 span normal
          release-info-3 div normal
        span-16 span normal
""")

# home-empty
EMPTY_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
""")

# home-loading
LOADING_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  panel-1 section normal
    h2-1 h2 normal
    skeleton-1 div normal
    skeleton-2 div normal
    skeleton-3 div normal
""")

# home-error
ERROR_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  error-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    button-7 button normal
""")

# home-long
LONG_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  metric-grid-1 div normal
    metric-1 div normal
      metric-label-1 span normal
      strong-2 strong normal
      small-3 small normal
    metric-2 div normal
      metric-label-2 span normal
      strong-3 strong normal
      small-4 small normal
    metric-3 div normal
      metric-label-3 span normal
      strong-4 strong normal
      small-5 small normal
    metric-4 div normal
      metric-label-4 span normal
      strong-5 strong normal
      small-6 small normal
  bilan-1 details normal
    summary-1 summary normal
    chart-key-1 div normal
      span-1 span normal
      span-2 span normal
      span-3 span normal
    volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1 svg normal
      g-1 g normal
        line-1 line normal
        line-2 line normal
        line-3 line normal
        line-4 line normal
      g-2 g normal
        text-1 text normal
        text-2 text normal
        text-3 text normal
        text-4 text normal
        text-5 text normal
        text-6 text normal
        text-7 text normal
        text-8 text normal
        text-9 text normal
        text-10 text normal
        text-11 text normal
      polyline-1 polyline normal
      circle-1 circle normal
        title-1 title normal
      circle-2 circle normal
        title-2 title normal
      circle-3 circle normal
        title-3 title normal
      circle-4 circle normal
        title-4 title normal
      circle-5 circle normal
        title-5 title normal
      circle-6 circle normal
        title-6 title normal
      circle-7 circle normal
        title-7 title normal
      polyline-2 polyline normal
      circle-8 circle normal
        title-8 title normal
      circle-9 circle normal
        title-9 title normal
      circle-10 circle normal
        title-10 title normal
      circle-11 circle normal
        title-11 title normal
      circle-12 circle normal
        title-12 title normal
      circle-13 circle normal
        title-13 title normal
      circle-14 circle normal
        title-14 title normal
      polyline-3 polyline normal
      circle-15 circle normal
        title-15 title normal
      circle-16 circle normal
        title-16 title normal
      circle-17 circle normal
        title-17 title normal
      circle-18 circle normal
        title-18 title normal
      circle-19 circle normal
        title-19 title normal
      circle-20 circle normal
        title-20 title normal
      circle-21 circle normal
        title-21 title normal
    link-1 button normal
  panel-1 section normal
    section-heading-1 div normal
      h2-1 h2 normal
      link-2 button normal
    overview-runs-1 iframe normal
  inbox-1 div normal
    panel-2 div normal
      h2-2 h2 normal
      request-1 button normal
        strong-6 strong normal
        small-7 small normal
      request-2 button normal
        strong-7 strong normal
        small-8 small normal
    panel-3 article normal
      small-9 small normal
      h2-3 h2 normal
      p-1 p 22.5px
      resource-list-1 div normal
        button-7 button normal
          span-4 span normal
            strong-8 strong normal
            small-10 small normal
          span-5 span normal
        button-8 button normal
          span-6 span normal
            strong-9 strong normal
            small-11 small normal
          span-7 span normal
        details-1 details normal
          summary-2 summary normal
          p-2 p 21px
        details-2 details normal
          summary-3 summary normal
          p-3 p 21px
      details-3 details normal
        summary-4 summary normal
        p-4 p 21px
        p-5 p 21px
        p-6 p 21px
        p-7 p 21px
        p-8 p 21px
        p-9 p 21px
        p-10 p 21px
        p-11 p 21px
        p-12 p 21px
        p-13 p 21px
        p-14 p 21px
        p-15 p 21px
        p-16 p 21px
        p-17 p 21px
        p-18 p 21px
        p-19 p 21px
        p-20 p 21px
        p-21 p 21px
      actions-possibles-1 div normal
        button-9 a normal
        button-10 button normal
  panel-4 section normal
    h2-4 h2 normal
    rows-1 div normal
      row-1 div normal
        div-3 div normal
          strong-10 strong normal
          small-12 small normal
          small-stats-1 div normal
            span-8 span normal
            span-9 span normal
          release-info-1 div normal
        span-10 span normal
      row-2 div normal
        div-4 div normal
          strong-11 strong normal
          small-13 small normal
          small-stats-2 div normal
            span-11 span normal
            span-12 span normal
          release-info-2 div normal
        span-13 span normal
      row-3 div normal
        div-5 div normal
          strong-12 strong normal
          small-14 small normal
          small-stats-3 div normal
            span-14 span normal
            span-15 span normal
          release-info-3 div normal
        span-16 span normal
""")

# home-stale, home-offline
STALE_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    selected-1 button normal
      badge-count-1 span normal
    button-1 button normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
main-1 main normal
  overview-head-1 div normal
    div-2 div normal
      h1-1 h1 normal
      small-2 small normal
  notice-1 div normal
  metric-grid-1 div normal
    metric-1 div normal
      metric-label-1 span normal
      strong-2 strong normal
      small-3 small normal
    metric-2 div normal
      metric-label-2 span normal
      strong-3 strong normal
      small-4 small normal
    metric-3 div normal
      metric-label-3 span normal
      strong-4 strong normal
      small-5 small normal
    metric-4 div normal
      metric-label-4 span normal
      strong-5 strong normal
      small-6 small normal
  bilan-1 details normal
    summary-1 summary normal
    chart-key-1 div normal
      span-1 span normal
      span-2 span normal
      span-3 span normal
    volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1 svg normal
      g-1 g normal
        line-1 line normal
        line-2 line normal
        line-3 line normal
        line-4 line normal
      g-2 g normal
        text-1 text normal
        text-2 text normal
        text-3 text normal
        text-4 text normal
        text-5 text normal
        text-6 text normal
        text-7 text normal
        text-8 text normal
        text-9 text normal
        text-10 text normal
        text-11 text normal
      polyline-1 polyline normal
      circle-1 circle normal
        title-1 title normal
      circle-2 circle normal
        title-2 title normal
      circle-3 circle normal
        title-3 title normal
      circle-4 circle normal
        title-4 title normal
      circle-5 circle normal
        title-5 title normal
      circle-6 circle normal
        title-6 title normal
      circle-7 circle normal
        title-7 title normal
      polyline-2 polyline normal
      circle-8 circle normal
        title-8 title normal
      circle-9 circle normal
        title-9 title normal
      circle-10 circle normal
        title-10 title normal
      circle-11 circle normal
        title-11 title normal
      circle-12 circle normal
        title-12 title normal
      circle-13 circle normal
        title-13 title normal
      circle-14 circle normal
        title-14 title normal
      polyline-3 polyline normal
      circle-15 circle normal
        title-15 title normal
      circle-16 circle normal
        title-16 title normal
      circle-17 circle normal
        title-17 title normal
      circle-18 circle normal
        title-18 title normal
      circle-19 circle normal
        title-19 title normal
      circle-20 circle normal
        title-20 title normal
      circle-21 circle normal
        title-21 title normal
    link-1 button normal
  panel-1 section normal
    section-heading-1 div normal
      h2-1 h2 normal
      link-2 button normal
    overview-runs-1 iframe normal
  inbox-1 div normal
    panel-2 div normal
      h2-2 h2 normal
      request-1 button normal
        strong-6 strong normal
        small-7 small normal
      request-2 button normal
        strong-7 strong normal
        small-8 small normal
    panel-3 article normal
      small-9 small normal
      h2-3 h2 normal
      p-1 p 22.5px
      resource-list-1 div normal
        button-7 button normal
          span-4 span normal
            strong-8 strong normal
            small-10 small normal
          span-5 span normal
        button-8 button normal
          span-6 span normal
            strong-9 strong normal
            small-11 small normal
          span-7 span normal
        details-1 details normal
          summary-2 summary normal
          p-2 p 21px
        details-2 details normal
          summary-3 summary normal
          p-3 p 21px
      actions-possibles-1 div normal
        button-9 a normal
        button-10 button normal
  panel-4 section normal
    h2-4 h2 normal
    rows-1 div normal
      row-1 div normal
        div-3 div normal
          strong-10 strong normal
          small-12 small normal
          small-stats-1 div normal
            span-8 span normal
            span-9 span normal
          release-info-1 div normal
        span-10 span normal
      row-2 div normal
        div-4 div normal
          strong-11 strong normal
          small-13 small normal
          small-stats-2 div normal
            span-11 span normal
            span-12 span normal
          release-info-2 div normal
        span-13 span normal
      row-3 div normal
        div-5 div normal
          strong-12 strong normal
          small-14 small normal
          small-stats-3 div normal
            span-14 span normal
            span-15 span normal
          release-info-3 div normal
        span-16 span normal
""")



class HomeDestinationFidelity(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_reference(self, state: str, anchors: list[tuple], ready: str | None = None) -> None:
        """The page served at GET / on the dataset `state` carries every
        anchor of `anchors` and every token of TOKENS, at both widths in
        both themes; with `ready`, once the page shows that anchor (a state
        the cockpit reaches after a time)."""
        address = self.tree.launch(state)
        self.assertEqual([], token_deviations(address, TOKENS), f"the tokens of {state} are not the reference's")
        found = {}
        for theme in THEMES:
            options = {"theme": theme, "widths": WIDTHS}
            if ready is None:
                frames = measure(address, **options)
            else:
                frames = measure_until(
                    address, lambda frames: all(ready in frame["texts"] for frame in frames), seconds=15, **options)
            for frame in frames:
                self.assertEqual("/", frame["path"], "the state is not served at GET /")
                deviations = anchor_deviations(frame, anchors)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        self.assertEqual({}, found, f"the anchors of {state} are not the reference's")

    # Criterion 1 ---------------------------------------------------------

    def test_home_content_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-content", CONTENT_ANCHORS)

    def test_home_content_full_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-content-full", CONTENT_ANCHORS)

    def test_home_narrow_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-narrow", CONTENT_ANCHORS)

    def test_home_light_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-light", CONTENT_ANCHORS)

    def test_home_long_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-long", LONG_ANCHORS)

    def test_home_empty_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-empty", EMPTY_ANCHORS)

    def test_home_loading_carries_every_anchor_and_token_of_its_reference(self):
        # Nothing is read yet: the page is measured as soon as it is served.
        self.assert_reference("home-loading", LOADING_ANCHORS)

    def test_home_error_carries_every_anchor_and_token_of_its_reference(self):
        # Once the cockpit has given up reading the sources.
        self.assert_reference("home-error", ERROR_ANCHORS, ready="error-1")

    def test_home_stale_carries_every_anchor_and_token_of_its_reference(self):
        # Once the reading is stale.
        self.assert_reference("home-stale", STALE_ANCHORS, ready="notice-1")

    def test_home_offline_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-offline", STALE_ANCHORS, ready="notice-1")


if __name__ == "__main__":
    unittest.main()
