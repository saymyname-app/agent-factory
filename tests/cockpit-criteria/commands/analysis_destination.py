"""What the criterion tests of the destination « Analyses » share (T42
Prototype Fold, af-muqyxm; Spec af-2zseit, Testing Decisions 1 and 5). Not
a test file: the three criterion test files of the destination load it.

The launch of the cockpit by the launcher of the profile, bin/project-launch,
and the reading of a served page in a headless Chromium are those of the
destination « Vue d’ensemble » (home_destination.py): this file adds what
is particular to Analyses -- its address, its named parts as the reference
draws them, what a page of it is held to.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it.
"""

from __future__ import annotations

from home_destination import NAVIGATION, hierarchy, says, tokens_of

# The address of the destination: the entry point GET /analyses of the
# profile.
PATH = "/analyses"

# The named parts of the destination open on « Résultats », as the
# Validated Prototype draws them (prototype/cockpit-b-zones-20261012 at
# 632deea, prototypes/c01-complete/frozen-panorama-analysis,
# states/analysis-content.html, and analysis-narrow and analysis-light drawn
# the same): part -> (element, the named part that holds it). The tab open
# is `primary-1`, whichever it is.
SHELL_PARTS = {
    "shell-nav-1": ("aside", None),
    "brand-1": ("header", "shell-nav-1"),
    "live-1": ("span", "brand-1"),
    "nav-1": ("nav", "shell-nav-1"),
    "badge-count-1": ("span", "nav-1"),
    "selected-1": ("button", "nav-1"),
    "main-1": ("main", None),
    "page-lead-1": ("p", "main-1"),
    "metric-tabs-1": ("div", "main-1"),
    "primary-1": ("button", "metric-tabs-1"),
    "panel-1": ("section", "main-1"),
    "chart-key-1": ("div", "panel-1"),
}
CHART = "volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1"
RESULTS_PARTS = {
    **SHELL_PARTS,
    CHART: ("svg", "panel-1"),
    "metrics-history-1": ("div", "panel-1"),
}
# The destination open on « Délais » (states/analysis-time.html): its seven
# rows of durations, each with its bar, and the notice under them.
TIME_PARTS = {
    **SHELL_PARTS,
    **{f"duration-row-{n}": ("div", "panel-1") for n in range(1, 8)},
    **{f"duration-bar-{n}": ("div", f"duration-row-{n}") for n in range(1, 8)},
    "notice-1": ("div", "panel-1"),
}
REFERENCE_PARTS = set(RESULTS_PARTS) | set(TIME_PARTS)

# The tabs of the destination, in the order of the reference.
TABS = ["Résultats", "Délais", "Vérifications", "Activité"]


def assert_analyses(case, frame: dict, parts: dict, tab: str) -> None:
    """The page measured is the destination « Analyses » served at its own
    address, open on the tab `tab`: the navigation B with « Analyses »
    marked as the destination open, the tabs of the reference with `tab`
    the one open, and exactly the named parts `parts` of the reference
    among those the reference knows -- each its element, inside the same
    named part."""
    case.assertEqual(PATH, frame["path"], "the destination is not served at its own address")
    labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
    case.assertEqual(NAVIGATION, labels, "the navigation B is not the reference's")
    current = [label for label, entry in zip(labels, frame["nav"]) if entry["current"]]
    case.assertEqual(["Analyses"], current, "the navigation does not say which destination is open")
    tabs = [control["name"] for control in frame["controls"]
            if control["anchor"] == "metric-tabs-1" or control["anchor"] in tab_anchors(frame)]
    case.assertEqual(TABS, tabs, "the tabs of Analyses are not the reference's")
    case.assertEqual(tab, says(frame, "primary-1"), "the tab open is not the one the reference opens")
    served = hierarchy(frame)
    known = REFERENCE_PARTS | set(parts)
    case.assertEqual(parts, {name: value for name, value in served.items() if name in known},
                     "the named parts of the page are not the reference's")


def tab_anchors(frame: dict) -> set[str]:
    """The anchors held directly by the bar of tabs `metric-tabs-1`."""
    return {anchor["name"] for anchor in frame["anchors"]
            if anchor["chain"] and anchor["chain"][0] == "metric-tabs-1"}


def assert_says(case, frame: dict, anchor: str, *phrases: str) -> None:
    """Each phrase of the reference is said inside the anchor `anchor`."""
    text = says(frame, anchor)
    case.assertEqual([], [phrase for phrase in phrases if phrase not in text],
                     f"{anchor} does not say it; it says « {text} »")


def token_deviations(address: str, expected: dict[str, dict[str, str]]) -> list[str]:
    """How the tokens the page at GET /analyses declares differ from those
    `expected` (theme -> token -> value), one line per token and theme:
    absent, or another value."""
    served = tokens_of(address, PATH)
    return [
        f"{name} ({theme}) : {served[theme].get(name)!r}, the reference has {value!r}"
        for theme, tokens in expected.items() for name, value in tokens.items()
        if served[theme].get(name) != value
    ]
