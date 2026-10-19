#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Rituels et préparation release »
(T41, af-r4hrt7; Spec af-2zseit, Testing Decisions 5): the anchors and the
tokens the reference approves, in each of its fourteen states.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET /rituels -- as a headless Chromium renders
it, at 1440 and 390 px, in the dark and the light theme, and from its style
sources. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-rituals/states/<state>.html), whose
values are written below, each case naming those of its state:

- every anchor of the state, numbered ones (`div-1`, `strong-2`, `option-3`)
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

from rituals_destination import PATH, LaunchTree, anchor_deviations, measure, outline, token_deviations  # noqa: E402

WIDTHS = (1440, 390)
THEMES = ("dark", "light")

# The tokens of the reference, the same in its fourteen states: their names
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
# drawn the same share one outline, and every state the same shell.

# The shell: the brand and the navigation B, « Rituels » the entry open.
SHELL = """
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    selected-1 button normal
    button-6 button normal
"""

# rituals-content, rituals-narrow, rituals-light
CATALOGUE_ANCHORS = outline(SHELL + """main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-grid-1 div normal
    panel-1 section normal
      small-2 small normal
      h2-1 h2 normal
      p-1 p 21px
      small-3 small normal
      actions-1 div normal
        primary-1 button normal
    panel-2 section normal
      small-4 small normal
      h2-2 h2 normal
      p-2 p 21px
      small-5 small normal
      actions-2 div normal
        primary-2 button normal
        link-1 button normal
    panel-3 section normal
      small-6 small normal
      h2-3 h2 normal
      p-3 p 21px
      small-7 small normal
      actions-3 div normal
        primary-3 button normal
    panel-4 section normal
      small-8 small normal
      h2-4 h2 normal
      p-4 p 21px
      small-9 small normal
      actions-4 div normal
        primary-4 button normal
    panel-5 section normal
      small-10 small normal
      h2-5 h2 normal
      p-5 p 21px
      small-11 small normal
      actions-5 div normal
        primary-5 button normal
""")

# ritual-confirm
RITUAL_CONFIRM_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
    span-4 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    label-1 label normal
      ritual-target-1 select normal
        option-1 option normal
        option-2 option normal
        option-3 option normal
    change-preview-1 div normal
      p-2 p 21px
    actions-1 div normal
      button-7 button normal
      primary-1 button normal
""")

# ritual-review
RITUAL_REVIEW_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    current-1 span normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    link-2 button normal
    readonly-note-1 p 18px
""")

# ritual-report
RITUAL_REPORT_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    current-1 span normal
    span-2 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    proposal-choice-1 label normal
      input-1 input normal
      span-4 span normal
        strong-2 strong normal
        small-2 small 19.2px
        small-3 small 19.2px
    proposal-choice-2 label normal
      input-2 input normal
      span-5 span normal
        strong-3 strong normal
        small-4 small 19.2px
        small-5 small 19.2px
    details-1 details normal
      summary-1 summary normal
      p-2 p 21px
    actions-1 div normal
      button-7 button normal
      primary-1 button normal
""")

# ritual-preparing
RITUAL_PREPARING_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    current-1 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    p-2 p 22.5px
""")

# ritual-ready
RITUAL_READY_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    current-1 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    h3-1 h3 normal
    p-1 p 22.5px
    change-preview-1 div normal
      strong-2 strong normal
      p-2 p 21px
      strong-3 strong normal
      p-3 p 21px
    details-1 details normal
      summary-1 summary normal
      p-4 p 21px
    actions-1 div normal
      button-7 button normal
      primary-1 button normal
""")

# ritual-execution
RITUAL_EXECUTION_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
    current-1 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
""")

# ritual-delivered
RITUAL_DELIVERED_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
    span-4 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    readonly-note-1 p 18px
""")

# release-confirm
RELEASE_CONFIRM_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    current-1 span normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    label-1 label normal
      select-1 select normal
        option-1 option normal
        option-2 option normal
        option-3 option normal
    p-1 p 22.5px
    change-preview-1 div normal
      p-2 p 21px
    actions-1 div normal
      button-7 button normal
      primary-1 button normal
""")

# release-review
RELEASE_REVIEW_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    current-1 span normal
    span-2 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
""")

# release-report
RELEASE_REPORT_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    current-1 span normal
    span-3 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    label-1 label normal
      r-sultat-attendu-pour-cette-release-1 textarea normal
    release-columns-1 div normal
      div-2 div normal
        h3-1 h3 normal
        ok-1 p 22.5px
        ok-2 p 22.5px
      div-3 div normal
        h3-2 h3 normal
        p-2 p 22.5px
        p-3 p 22.5px
    release-decision-1 fieldset normal
      legend-1 legend normal
      label-2 label normal
        input-1 input normal
      label-3 label normal
        input-2 input normal
      label-4 label normal
        input-3 input normal
    label-5 label normal
      prochain-jalon-1 textarea normal
    label-6 label normal
      comment-v-rifier-ce-jalon-1 textarea normal
    release-notice-1 div normal
      strong-2 strong normal
      p-4 p 22.5px
    details-1 details normal
      summary-1 summary normal
      p-5 p 21px
    actions-1 div normal
      button-7 button normal
      primary-1 button normal
    release-error-1 p 22.5px
""")

# release-saved
RELEASE_SAVED_ANCHORS = outline(SHELL + """main-1 main normal
  crumb-1 div normal
    link-1 button normal
  h1-1 h1 normal
  page-lead-1 p 24px
  ritual-path-1 div normal
    span-1 span normal
    span-2 span normal
    span-3 span normal
    current-1 span normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
    p-2 p 22.5px
    actions-1 div normal
      primary-1 button normal
      link-2 button normal
""")


class RitualsDestinationFidelity(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_reference(self, state: str, anchors: list[tuple]) -> None:
        """The page served at GET /rituels on the dataset `state` carries
        every anchor of `anchors` and every token of TOKENS, at both widths
        in both themes."""
        address = self.tree.launch(state)
        self.assertEqual([], token_deviations(address, TOKENS), f"the tokens of {state} are not the reference's")
        found = {}
        for theme in THEMES:
            for frame in measure(address, PATH, theme=theme, widths=WIDTHS):
                self.assertEqual(PATH, frame["path"], "the state is not served at GET /rituels")
                deviations = anchor_deviations(frame, anchors)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        self.assertEqual({}, found, f"the anchors of {state} are not the reference's")

    # Criterion 1 ---------------------------------------------------------

    def test_rituals_content_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("rituals-content", CATALOGUE_ANCHORS)

    def test_rituals_narrow_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("rituals-narrow", CATALOGUE_ANCHORS)

    def test_rituals_light_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("rituals-light", CATALOGUE_ANCHORS)

    def test_ritual_confirm_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-confirm", RITUAL_CONFIRM_ANCHORS)

    def test_ritual_review_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-review", RITUAL_REVIEW_ANCHORS)

    def test_ritual_report_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-report", RITUAL_REPORT_ANCHORS)

    def test_ritual_preparing_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-preparing", RITUAL_PREPARING_ANCHORS)

    def test_ritual_ready_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-ready", RITUAL_READY_ANCHORS)

    def test_ritual_execution_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-execution", RITUAL_EXECUTION_ANCHORS)

    def test_ritual_delivered_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("ritual-delivered", RITUAL_DELIVERED_ANCHORS)

    def test_release_confirm_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("release-confirm", RELEASE_CONFIRM_ANCHORS)

    def test_release_review_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("release-review", RELEASE_REVIEW_ANCHORS)

    def test_release_report_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("release-report", RELEASE_REPORT_ANCHORS)

    def test_release_saved_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("release-saved", RELEASE_SAVED_ANCHORS)


if __name__ == "__main__":
    unittest.main()
