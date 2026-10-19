#!/usr/bin/env python3
"""Criterion test 1 of the run timeline « frise du run » (T03R, af-hd8wzb,
cut from T03; Spec af-2zseit, user story 129, Testing Decisions 5 and 7):
the anchors and the tokens the Runs reference approves, in each of its
five frozen states run-active, run-completed, run-waiting, run-abandoned
and run-stale.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET /runs/run -- as a headless Chromium renders
it, at 1280 and 390 px (the frames the reference is frozen in), in the dark
and the light theme, and from its style sources. It holds the page to the
Validated Prototype of Runs (prototype/c01-parcours-20261011 at d8cb462,
prototypes/c01-flow/frozen-runs/states/<state>.html), whose values are
written below, each case naming those of its state:

- every anchor of the state -- the run, its summary, the axis and its
  ticks, each lane and its name, each job with its control and each mark
  of its events, the legend, the place of the detail --, once, drawn by
  the same element inside the same anchor, in the type of the reference
  (its computed font-family and line-height);
- the tokens of the reference under their names (`--bg`, `--surface`,
  `--line`, `--ink`, `--muted`, `--accent`, `--human`, `--code`,
  `--agent`, `--ok`), with its values, in the dark and the light theme.

The frozen pages carry one more element, after their body: a root
injected by the browser the pages were captured in
(`codex-browser-sidebar-comments-root`), no part of the timeline nor of
any choice of the reference -- an accident of the capture, not held here.

False if an anchor of the reference is missing, doubled, drawn otherwise or
elsewhere, or set in another type, or if a token of the reference is absent
or has another value: the timeline approved is not the one served.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import measure_until  # noqa: E402
from run_timeline import (  # noqa: E402
    THEMES, TIMELINE, WIDTHS, LaunchTree, anchor_deviations, anchor_outline, token_deviations_at,
)

# The tokens of the reference, the same in its five run states: their names
# and their values, in the dark and the light theme.
TOKENS = {
    "dark": {"--bg": "#0d1015", "--surface": "#161a21", "--line": "#2a313d", "--ink": "#e6e9ef",
             "--muted": "#8a93a4", "--accent": "#8fa3ff", "--human": "#e4bc6d", "--code": "#55b5ae",
             "--agent": "#a897eb", "--ok": "#4dc48b"},
    "light": {"--bg": "#f2f4f8", "--surface": "white", "--line": "#d8dde6", "--ink": "#151b26",
              "--muted": "#687286", "--accent": "#2b4cc0", "--human": "#e4bc6d", "--code": "#55b5ae",
              "--agent": "#a897eb", "--ok": "#1f7b4b"},
}

# Every anchor of the frozen page of a state, in the order of the page: the
# anchor, the element that draws it, its line-height, « mono » when it is
# set in ui-monospace (system-ui otherwise), indented under the anchor that
# holds it. Read from the frozen pages as headless Chromium renders them at
# 1280 and 390 px in the dark and the light theme (the four renderings of
# each state agree).

RUN_ACTIVE_ANCHORS = anchor_outline("""
shell main normal
  brand header normal
    small small normal
  crumb div normal
    back button normal
    span span normal
  h1 h1 normal
  run-summary div normal
    badge span normal
      live-dot span normal
    span-2 span normal
    mono strong normal mono
    span-3 span normal
    span-4 span normal
    span-5 span normal
  p p 22.5px
    strong strong 22.5px
  chart-box div normal
    scroll div normal
      chart div normal
        axis div normal
          axis-title div normal
          ticks div normal
            tick span normal mono
            tick-2 span normal mono
            tick-3 span normal mono
            tick-4 span normal mono
            tick-5 span normal mono
            tick-6 span normal mono
        lane div normal
          lane-name div normal
            strong-2 strong normal
            small-2 small normal
          track div normal
            job div normal
              job-select button normal
                strong-3 strong normal
                small-3 small normal
              marks span normal
                v-nement-job-start-d-clencheur button normal
                v-nement-log-benjamin button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s button normal
                v-nement-gate-pass-preuve-enregistree button normal
                v-nement-job-end-termin button normal
        lane-2 div normal
          lane-name-2 div normal
            strong-4 strong normal
            small-4 small normal
          track-2 div normal
            job-2 div normal
              job-select-2 button normal
                strong-5 strong normal
                small-5 small normal
              marks-2 span normal
                v-nement-job-start-pr-parer-le-travail button normal
                v-nement-log-code button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-2 button normal
                v-nement-gate-pass-preuve-enregistree-2 button normal
                v-nement-job-end-termin-2 button normal
            job-3 div normal
              job-select-3 button normal
                strong-6 strong normal
                small-6 small normal
              marks-3 span normal
                v-nement-job-start-geler button normal
                v-nement-log-code-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-3 button normal
                v-nement-gate-pass-preuve-enregistree-3 button normal
                v-nement-job-end-termin-3 button normal
        lane-3 div normal
          lane-name-3 div normal
            strong-7 strong normal
            small-7 small normal
            small-8 small normal
            context-meter span normal
              i i normal
          track-3 div normal
            job-4 div normal
              job-select-4 button normal
                strong-8 strong normal
                small-9 small normal
              marks-4 span normal
                v-nement-job-start-pr-parer-les-tests button normal
                v-nement-agent-start-alex button normal
                v-nement-tool-call-read-spec-approuv-e button normal
                v-nement-tool-call-read-crit-res-et-dossier button normal
                v-nement-tool-call-exec-v-rification-cibl-e button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat button normal
                v-nement-gate-pass-preuve-enregistree-4 button normal
                v-nement-job-end-termin-4 button normal
            job-5 div normal
              job-select-5 button normal
                strong-9 strong normal
                small-10 small normal
              marks-5 span normal
                v-nement-job-start-r-aliser button normal
                v-nement-agent-start-alex-2 button normal
                v-nement-tool-call-read-spec-approuv-e-2 button normal
                v-nement-tool-call-read-crit-res-et-dossier-2 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-2 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-2 button normal
                v-nement-session-end-demo-cockpit-alex-1 button normal
                v-nement-agent-start-demo-cockpit-alex-2 button normal
                v-nement-gate-pass-preuve-enregistree-5 button normal
                v-nement-job-end-termin-5 button normal
        lane-4 div normal
          lane-name-4 div normal
            strong-10 strong normal
            small-11 small normal
            small-12 small normal
            context-meter-2 span normal
              i-2 i normal
          track-4 div normal
            job-6 div normal
              job-select-6 button normal
                strong-11 strong normal
                small-13 small normal
              marks-6 span normal
                v-nement-job-start-relire-les-tests button normal
                v-nement-agent-start-l-a button normal
                v-nement-tool-call-read-spec-approuv-e-3 button normal
                v-nement-tool-call-read-crit-res-et-dossier-3 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-3 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-3 button normal
                v-nement-gate-pass-preuve-enregistree-6 button normal
                v-nement-job-end-termin-6 button normal
            job-7 div normal
              job-select-7 button normal
                strong-12 strong normal
                small-14 small normal
              marks-7 span normal
                v-nement-job-start-revue-du-code button normal
                v-nement-agent-start-l-a-2 button normal
                v-nement-tool-call-read-spec-approuv-e-4 button normal
                v-nement-tool-call-read-crit-res-et-dossier-4 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-4 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-4 button normal
        lane-5 div normal
          lane-name-5 div normal
            strong-13 strong normal
            small-15 small normal
            small-16 small normal
            context-meter-3 span normal
              i-3 i normal
          track-5 div normal
            job-8 div normal
              job-select-8 button normal
                strong-14 strong normal
                small-17 small normal
              marks-8 span normal
                v-nement-job-start-essayer-la-t-che button normal
                v-nement-agent-start-no button normal
                v-nement-tool-call-read-spec-approuv-e-5 button normal
                v-nement-tool-call-read-crit-res-et-dossier-5 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-5 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-5 button normal
    legend div normal
  inspector div normal
""")

RUN_COMPLETED_ANCHORS = anchor_outline("""
shell main normal
  brand header normal
    small small normal
  crumb div normal
    back button normal
    span span normal
  h1 h1 normal
  run-summary div normal
    badge span normal
    span-2 span normal
    mono strong normal mono
    span-3 span normal
    span-4 span normal
    span-5 span normal
  chart-box div normal
    scroll div normal
      chart div normal
        axis div normal
          axis-title div normal
          ticks div normal
            tick span normal mono
            tick-2 span normal mono
            tick-3 span normal mono
            tick-4 span normal mono
            tick-5 span normal mono
            tick-6 span normal mono
        lane div normal
          lane-name div normal
            strong strong normal
            small-2 small normal
          track div normal
            job div normal
              job-select button normal
                strong-2 strong normal
                small-3 small normal
              marks span normal
                v-nement-job-start-d-clencheur button normal
                v-nement-log-benjamin button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s button normal
                v-nement-gate-pass-preuve-enregistree button normal
                v-nement-job-end-termin button normal
            job-2 div normal
              job-select-2 button normal
                strong-3 strong normal
                small-4 small normal
              marks-2 span normal
                v-nement-job-start-juger-le-r-sultat button normal
                v-nement-log-benjamin-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-2 button normal
                v-nement-gate-pass-preuve-enregistree-2 button normal
                v-nement-job-end-termin-2 button normal
        lane-2 div normal
          lane-name-2 div normal
            strong-4 strong normal
            small-5 small normal
          track-2 div normal
            job-3 div normal
              job-select-3 button normal
                strong-5 strong normal
                small-6 small normal
              marks-3 span normal
                v-nement-job-start-pr-parer-le-travail button normal
                v-nement-log-code button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-3 button normal
                v-nement-gate-pass-preuve-enregistree-3 button normal
                v-nement-job-end-termin-3 button normal
            job-4 div normal
              job-select-4 button normal
                strong-6 strong normal
                small-7 small normal
              marks-4 span normal
                v-nement-job-start-geler button normal
                v-nement-log-code-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-4 button normal
                v-nement-gate-pass-preuve-enregistree-4 button normal
                v-nement-job-end-termin-4 button normal
            job-5 div normal
              job-select-5 button normal
                strong-7 strong normal
                small-8 small normal
              marks-5 span normal
                v-nement-job-start-v-rifier-l-ensemble button normal
                v-nement-log-code-3 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-5 button normal
                v-nement-gate-pass-preuve-enregistree-5 button normal
                v-nement-job-end-termin-5 button normal
            job-6 div normal
              job-select-6 button normal
                strong-8 strong normal
                small-9 small normal
              marks-6 span normal
                v-nement-job-start-fusionner-et-clore button normal
                v-nement-log-code-4 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-6 button normal
                v-nement-gate-pass-preuve-enregistree-6 button normal
                v-nement-job-end-termin-6 button normal
        lane-3 div normal
          lane-name-3 div normal
            strong-9 strong normal
            small-10 small normal
            small-11 small normal
            context-meter span normal
              i i normal
          track-3 div normal
            job-7 div normal
              job-select-7 button normal
                strong-10 strong normal
                small-12 small normal
              marks-7 span normal
                v-nement-job-start-pr-parer-les-tests button normal
                v-nement-agent-start-alex button normal
                v-nement-tool-call-read-spec-approuv-e button normal
                v-nement-tool-call-read-crit-res-et-dossier button normal
                v-nement-tool-call-exec-v-rification-cibl-e button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat button normal
                v-nement-gate-pass-preuve-enregistree-7 button normal
                v-nement-job-end-termin-7 button normal
            job-8 div normal
              job-select-8 button normal
                strong-11 strong normal
                small-13 small normal
              marks-8 span normal
                v-nement-job-start-r-aliser button normal
                v-nement-agent-start-alex-2 button normal
                v-nement-tool-call-read-spec-approuv-e-2 button normal
                v-nement-tool-call-read-crit-res-et-dossier-2 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-2 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-2 button normal
                v-nement-session-end-demo-search-alex-1 button normal
                v-nement-agent-start-demo-search-alex-2 button normal
                v-nement-gate-pass-preuve-enregistree-8 button normal
                v-nement-job-end-termin-8 button normal
        lane-4 div normal
          lane-name-4 div normal
            strong-12 strong normal
            small-14 small normal
            small-15 small normal
            context-meter-2 span normal
              i-2 i normal
          track-4 div normal
            job-9 div normal
              job-select-9 button normal
                strong-13 strong normal
                small-16 small normal
              marks-9 span normal
                v-nement-job-start-relire-les-tests button normal
                v-nement-agent-start-l-a button normal
                v-nement-tool-call-read-spec-approuv-e-3 button normal
                v-nement-tool-call-read-crit-res-et-dossier-3 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-3 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-3 button normal
                v-nement-gate-pass-preuve-enregistree-9 button normal
                v-nement-job-end-termin-9 button normal
            job-10 div normal
              job-select-10 button normal
                strong-14 strong normal
                small-17 small normal
              marks-10 span normal
                v-nement-job-start-revue-du-code button normal
                v-nement-agent-start-l-a-2 button normal
                v-nement-tool-call-read-spec-approuv-e-4 button normal
                v-nement-tool-call-read-crit-res-et-dossier-4 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-4 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-4 button normal
                v-nement-gate-pass-preuve-enregistree-10 button normal
                v-nement-job-end-termin-10 button normal
        lane-5 div normal
          lane-name-5 div normal
            strong-15 strong normal
            small-18 small normal
            small-19 small normal
            context-meter-3 span normal
              i-3 i normal
          track-5 div normal
            job-11 div normal
              job-select-11 button normal
                strong-16 strong normal
                small-20 small normal
              marks-11 span normal
                v-nement-job-start-essayer-la-t-che button normal
                v-nement-agent-start-no button normal
                v-nement-tool-call-read-spec-approuv-e-5 button normal
                v-nement-tool-call-read-crit-res-et-dossier-5 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-5 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-5 button normal
                v-nement-gate-pass-preuve-enregistree-11 button normal
                v-nement-job-end-termin-11 button normal
            job-12 div normal
              job-select-12 button normal
                strong-17 strong normal
                small-21 small normal
              marks-12 span normal
                v-nement-job-start-essayer-le-produit button normal
                v-nement-agent-start-no-2 button normal
                v-nement-tool-call-read-spec-approuv-e-6 button normal
                v-nement-tool-call-read-crit-res-et-dossier-6 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-6 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-6 button normal
                v-nement-gate-pass-preuve-enregistree-12 button normal
                v-nement-job-end-termin-12 button normal
    legend div normal
  inspector div normal
""")

RUN_WAITING_ANCHORS = anchor_outline("""
shell main normal
  brand header normal
    small small normal
  crumb div normal
    back button normal
    span span normal
  h1 h1 normal
  run-summary div normal
    badge span normal
      live-dot span normal
    span-2 span normal
    mono strong normal mono
    span-3 span normal
    span-4 span normal
    span-5 span normal
  p p 22.5px
    strong strong 22.5px
  chart-box div normal
    scroll div normal
      chart div normal
        axis div normal
          axis-title div normal
          ticks div normal
            tick span normal mono
            tick-2 span normal mono
            tick-3 span normal mono
            tick-4 span normal mono
            tick-5 span normal mono
            tick-6 span normal mono
        lane div normal
          lane-name div normal
            strong-2 strong normal
            small-2 small normal
          track div normal
            job div normal
              job-select button normal
                strong-3 strong normal
                small-3 small normal
              marks span normal
                v-nement-job-start-d-clencheur button normal
                v-nement-log-benjamin button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s button normal
                v-nement-gate-pass-preuve-enregistree button normal
                v-nement-job-end-termin button normal
            job-2 div normal
              job-select-2 button normal
                strong-4 strong normal
                small-4 small normal
              marks-2 span normal
                v-nement-job-start-d-cision-attendue button normal
                v-nement-log-benjamin-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-2 button normal
        lane-2 div normal
          lane-name-2 div normal
            strong-5 strong normal
            small-5 small normal
          track-2 div normal
            job-3 div normal
              job-select-3 button normal
                strong-6 strong normal
                small-6 small normal
              marks-3 span normal
                v-nement-job-start-pr-parer-le-travail button normal
                v-nement-log-code button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-3 button normal
                v-nement-gate-pass-preuve-enregistree-2 button normal
                v-nement-job-end-termin-2 button normal
        lane-3 div normal
          lane-name-3 div normal
            strong-7 strong normal
            small-7 small normal
            small-8 small normal
            context-meter span normal
              i i normal
          track-3 div normal
            job-4 div normal
              job-select-4 button normal
                strong-8 strong normal
                small-9 small normal
              marks-4 span normal
                v-nement-job-start-pr-parer-les-tests button normal
                v-nement-agent-start-alex button normal
                v-nement-tool-call-read-spec-approuv-e button normal
                v-nement-tool-call-read-crit-res-et-dossier button normal
                v-nement-tool-call-exec-v-rification-cibl-e button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat button normal
                v-nement-gate-pass-preuve-enregistree-3 button normal
                v-nement-job-end-termin-3 button normal
        lane-4 div normal
          lane-name-4 div normal
            strong-9 strong normal
            small-10 small normal
            small-11 small normal
            context-meter-2 span normal
              i-2 i normal
          track-4 div normal
            job-5 div normal
              job-select-5 button normal
                strong-10 strong normal
                small-12 small normal
              marks-5 span normal
                v-nement-job-start-relire-les-tests button normal
                v-nement-agent-start-l-a button normal
                v-nement-tool-call-read-spec-approuv-e-2 button normal
                v-nement-tool-call-read-crit-res-et-dossier-2 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-2 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-2 button normal
                v-nement-gate-pass-preuve-enregistree-4 button normal
                v-nement-job-end-termin-4 button normal
    legend div normal
  inspector div normal
""")

RUN_ABANDONED_ANCHORS = anchor_outline("""
shell main normal
  brand header normal
    small small normal
  crumb div normal
    back button normal
    span span normal
  h1 h1 normal
  run-summary div normal
    badge span normal
    span-2 span normal
    mono strong normal mono
    span-3 span normal
    span-4 span normal
    span-5 span normal
  chart-box div normal
    scroll div normal
      chart div normal
        axis div normal
          axis-title div normal
          ticks div normal
            tick span normal mono
            tick-2 span normal mono
            tick-3 span normal mono
            tick-4 span normal mono
            tick-5 span normal mono
            tick-6 span normal mono
        lane div normal
          lane-name div normal
            strong strong normal
            small-2 small normal
          track div normal
            job div normal
              job-select button normal
                strong-2 strong normal
                small-3 small normal
              marks span normal
                v-nement-job-start-d-clencheur button normal
                v-nement-log-benjamin button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s button normal
                v-nement-gate-pass-preuve-enregistree button normal
                v-nement-job-end-termin button normal
            job-2 div normal
              job-select-2 button normal
                strong-3 strong normal
                small-4 small normal
              marks-2 span normal
                v-nement-job-start-abandonner button normal
                v-nement-log-benjamin-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-2 button normal
                v-nement-gate-pass-preuve-enregistree-2 button normal
                v-nement-job-end-termin-2 button normal
        lane-2 div normal
          lane-name-2 div normal
            strong-4 strong normal
            small-5 small normal
          track-2 div normal
            job-3 div normal
              job-select-3 button normal
                strong-5 strong normal
                small-6 small normal
              marks-3 span normal
                v-nement-job-start-pr-parer-le-travail button normal
                v-nement-log-code button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-3 button normal
                v-nement-gate-pass-preuve-enregistree-3 button normal
                v-nement-job-end-termin-3 button normal
        lane-3 div normal
          lane-name-3 div normal
            strong-6 strong normal
            small-7 small normal
            small-8 small normal
            context-meter span normal
              i i normal
          track-3 div normal
            job-4 div normal
              job-select-4 button normal
                strong-7 strong normal
                small-9 small normal
              marks-4 span normal
                v-nement-job-start-pr-parer-les-tests button normal
                v-nement-agent-start-alex button normal
                v-nement-tool-call-read-spec-approuv-e button normal
                v-nement-tool-call-read-crit-res-et-dossier button normal
                v-nement-tool-call-exec-v-rification-cibl-e button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat button normal
                v-nement-gate-pass-preuve-enregistree-4 button normal
                v-nement-job-end-termin-4 button normal
    legend div normal
  inspector div normal
""")

RUN_STALE_ANCHORS = anchor_outline("""
shell main normal
  brand header normal
    small small normal
  crumb div normal
    back button normal
    span span normal
  h1 h1 normal
  run-summary div normal
    badge span normal
      live-dot span normal
    span-2 span normal
    mono strong normal mono
    span-3 span normal
    span-4 span normal
    span-5 span normal
  p p 22.5px
    strong strong 22.5px
  notice p 22.5px
  chart-box div normal
    scroll div normal
      chart div normal
        axis div normal
          axis-title div normal
          ticks div normal
            tick span normal mono
            tick-2 span normal mono
            tick-3 span normal mono
            tick-4 span normal mono
            tick-5 span normal mono
            tick-6 span normal mono
        lane div normal
          lane-name div normal
            strong-2 strong normal
            small-2 small normal
          track div normal
            job div normal
              job-select button normal
                strong-3 strong normal
                small-3 small normal
              marks span normal
                v-nement-job-start-d-clencheur button normal
                v-nement-log-benjamin button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s button normal
                v-nement-gate-pass-preuve-enregistree button normal
                v-nement-job-end-termin button normal
        lane-2 div normal
          lane-name-2 div normal
            strong-4 strong normal
            small-4 small normal
          track-2 div normal
            job-2 div normal
              job-select-2 button normal
                strong-5 strong normal
                small-5 small normal
              marks-2 span normal
                v-nement-job-start-pr-parer-le-travail button normal
                v-nement-log-code button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-2 button normal
                v-nement-gate-pass-preuve-enregistree-2 button normal
                v-nement-job-end-termin-2 button normal
            job-3 div normal
              job-select-3 button normal
                strong-6 strong normal
                small-6 small normal
              marks-3 span normal
                v-nement-job-start-geler button normal
                v-nement-log-code-2 button normal
                v-nement-gate-pass-condition-pr-requis-v-rifi-s-3 button normal
                v-nement-gate-pass-preuve-enregistree-3 button normal
                v-nement-job-end-termin-3 button normal
        lane-3 div normal
          lane-name-3 div normal
            strong-7 strong normal
            small-7 small normal
            small-8 small normal
            context-meter span normal
              i i normal
          track-3 div normal
            job-4 div normal
              job-select-4 button normal
                strong-8 strong normal
                small-9 small normal
              marks-4 span normal
                v-nement-job-start-pr-parer-les-tests button normal
                v-nement-agent-start-alex button normal
                v-nement-tool-call-read-spec-approuv-e button normal
                v-nement-tool-call-read-crit-res-et-dossier button normal
                v-nement-tool-call-exec-v-rification-cibl-e button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat button normal
                v-nement-gate-pass-preuve-enregistree-4 button normal
                v-nement-job-end-termin-4 button normal
            job-5 div normal
              job-select-5 button normal
                strong-9 strong normal
                small-10 small normal
              marks-5 span normal
                v-nement-job-start-r-aliser button normal
                v-nement-agent-start-alex-2 button normal
                v-nement-tool-call-read-spec-approuv-e-2 button normal
                v-nement-tool-call-read-crit-res-et-dossier-2 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-2 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-2 button normal
                v-nement-session-end-demo-cockpit-alex-1 button normal
                v-nement-agent-start-demo-cockpit-alex-2 button normal
                v-nement-gate-pass-preuve-enregistree-5 button normal
                v-nement-job-end-termin-5 button normal
        lane-4 div normal
          lane-name-4 div normal
            strong-10 strong normal
            small-11 small normal
            small-12 small normal
            context-meter-2 span normal
              i-2 i normal
          track-4 div normal
            job-6 div normal
              job-select-6 button normal
                strong-11 strong normal
                small-13 small normal
              marks-6 span normal
                v-nement-job-start-relire-les-tests button normal
                v-nement-agent-start-l-a button normal
                v-nement-tool-call-read-spec-approuv-e-3 button normal
                v-nement-tool-call-read-crit-res-et-dossier-3 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-3 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-3 button normal
                v-nement-gate-pass-preuve-enregistree-6 button normal
                v-nement-job-end-termin-6 button normal
            job-7 div normal
              job-select-7 button normal
                strong-12 strong normal
                small-14 small normal
              marks-7 span normal
                v-nement-job-start-revue-du-code button normal
                v-nement-agent-start-l-a-2 button normal
                v-nement-tool-call-read-spec-approuv-e-4 button normal
                v-nement-tool-call-read-crit-res-et-dossier-4 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-4 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-4 button normal
        lane-5 div normal
          lane-name-5 div normal
            strong-13 strong normal
            small-15 small normal
            small-16 small normal
            context-meter-3 span normal
              i-3 i normal
          track-5 div normal
            job-8 div normal
              job-select-8 button normal
                strong-14 strong normal
                small-17 small normal
              marks-8 span normal
                v-nement-job-start-essayer-la-t-che button normal
                v-nement-agent-start-no button normal
                v-nement-tool-call-read-spec-approuv-e-5 button normal
                v-nement-tool-call-read-crit-res-et-dossier-5 button normal
                v-nement-tool-call-exec-v-rification-cibl-e-5 button normal
                v-nement-tool-call-write-pi-ce-de-r-sultat-5 button normal
    legend div normal
  inspector div normal
""")


class RunTimelineFidelity(unittest.TestCase):
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
        """The page served at GET /runs/run on the dataset `state` carries
        every anchor of `anchors` and every token of TOKENS, at both widths
        in both themes -- once the page draws its timeline, or as it stands
        after 15 s."""
        address = self.tree.launch(state)
        self.assertEqual([], token_deviations_at(address, TIMELINE, TOKENS),
                         f"the tokens of {state} are not the reference's")
        found = {}
        for theme in THEMES:
            frames = measure_until(address, lambda frames: all("chart" in frame["texts"] for frame in frames),
                                   seconds=15, path=TIMELINE, theme=theme, widths=WIDTHS)
            for frame in frames:
                self.assertEqual(TIMELINE, frame["path"], "the state is not served at GET /runs/run")
                deviations = anchor_deviations(frame, anchors)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        self.assertEqual({}, found, f"the anchors of {state} are not the reference's")

    # Criterion 1 ---------------------------------------------------------

    def test_run_active_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("run-active", RUN_ACTIVE_ANCHORS)

    def test_run_completed_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("run-completed", RUN_COMPLETED_ANCHORS)

    def test_run_waiting_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("run-waiting", RUN_WAITING_ANCHORS)

    def test_run_abandoned_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("run-abandoned", RUN_ABANDONED_ANCHORS)

    def test_run_stale_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("run-stale", RUN_STALE_ANCHORS)


if __name__ == "__main__":
    unittest.main()
