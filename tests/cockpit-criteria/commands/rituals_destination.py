"""What the criterion tests of the destination « Rituels et préparation
release » share (T41 Prototype Fold, af-r4hrt7; Spec af-2zseit, Testing
Decisions 1 and 5). Not a test file: the three criterion test files of the
destination load it.

The launcher, the browser and the reading of a served page are those of the
destination « Vue d’ensemble » (home_destination.py), reused as they are:
`LaunchTree` starts the real cockpit with bin/project-launch on a named
dataset, `measure` reads the page as a headless Chromium renders it,
`problems` says what makes it unreadable or unusable, `anchor_deviations`
holds its anchors to an outline a case writes. What this file adds is the
address of the destination and what holds a page to it:

- `served`: the page of the destination, measured, once the cockpit is
  launched on a dataset;
- `assert_rituals`: the page is the destination « Rituels » served at its
  own address, its navigation B with this destination open;
- `assert_says`, `assert_path`: what the reference says, and the step of its
  path the page marks as the current one;
- `assert_unwired`: a command no door records is drawn unavailable, says so,
  and does nothing when pressed;
- `token_deviations`: the tokens the page declares against those a case
  writes.

Nothing here reads the code of the cockpit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402,F401
    LaunchTree, anchor_deviations, fetch, measure, outline, problems, says, tokens_of,
)

# The address of the destination, where the profile serves its fourteen
# states.
PATH = "/rituels"

# The navigation B, in the order of the reference.
NAVIGATION = ["Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses"]

# The commands of the reference that would launch an agent or write in the
# factory, and that no door records from this destination: each is drawn
# unavailable where its state shows it.
COMMANDS = ("Lancer la revue", "Faire préparer ma sélection", "Lancer les corrections", "Lancer la préparation",
            "Conserver ce cadrage")

# The four steps of a review and of the preparation of a release, as the
# reference names them.
REVIEW_STEPS = "1 · Revue", "2 · Ton choix", "3 · Travail précis", "4 · Réalisation"
RELEASE_STEPS = "1 · Périmètre", "2 · Préparation", "3 · Ton cadrage", "4 · Projet mis à jour"


def served(tree: LaunchTree, dataset: str, commit: str | None = None, *, theme: str = "dark",
           width: int = 1440, click: str | None = None, keys: bool = False) -> tuple[str, dict]:
    """The address of the cockpit `tree` launched on `dataset` (at `commit`),
    and its page at the address of the destination, `width` px wide, in
    `theme`; with `click`, that control activated (see `measure`)."""
    address = tree.launch(dataset, commit)
    return address, measure(address, PATH, theme=theme, widths=(width,), click=click, keys=keys)[0]


def assert_rituals(case, frame: dict) -> None:
    """The page measured is the destination « Rituels » served at its own
    address, with the navigation B and this destination marked as the one
    open."""
    case.assertEqual(PATH, frame["path"], "the destination is not served at its own address")
    labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
    case.assertEqual(NAVIGATION, labels, "the navigation B is not the reference's")
    case.assertEqual(["Rituels"], [label for label, entry in zip(labels, frame["nav"]) if entry["current"]],
                     "the navigation does not say which destination is open")


def assert_says(case, frame: dict, anchor: str, *phrases: str) -> None:
    """Each phrase of the reference is said inside the anchor `anchor`."""
    text = says(frame, anchor)
    case.assertEqual([], [phrase for phrase in phrases if phrase not in text],
                     f"{anchor} does not say it; it says « {text} »")


def assert_path(case, frame: dict, steps: tuple[str, ...], current: str | None) -> None:
    """The path of the state (`ritual-path-1`) names the four `steps` in
    their order, and marks `current` as the step under way -- the anchor
    `current-1` of the reference --, or none when `current` is None."""
    case.assertEqual(" ".join(steps), says(frame, "ritual-path-1"), "the path is not the reference's")
    case.assertEqual(current or "", says(frame, "current-1"), "the step under way is not the reference's")


def assert_theme(case, frame: dict, theme: str) -> None:
    """The page is drawn in `theme`: a dark background (relative luminance
    at most 0.1) or a light one (at least 0.5), its texts readable on it."""
    background = frame["background"]
    case.assertTrue(background is not None and (background <= 0.1 if theme == "dark" else background >= 0.5),
                    f"the page is not drawn in the {theme} theme (background luminance {background})")
    case.assertEqual([], frame["contrast"], f"texts unreadable in the {theme} theme")


def assert_unwired(case, address: str, frame: dict, command: str, actions: str = "actions-1") -> None:
    """The command `command` is drawn once, unavailable, the bar of
    actions `actions` says that it is not wired yet, and pressing it does
    nothing: the page stays at the destination and its panel says what it
    said -- no command shown done."""
    drawn = [c for c in frame["controls"] if c["name"] == command]
    case.assertEqual([True], [c["disabled"] for c in drawn],
                     f"« {command} » is not drawn once, unavailable: {drawn}")
    assert_says(case, frame, actions, "pas encore raccordé")
    after = measure(address, PATH, click=command)[0]["after"]
    case.assertEqual((True, True, PATH), (after["found"], after["disabled"], after["path"]),
                     f"pressing « {command} » did something")
    case.assertEqual(says(frame, "panel-1"), says(after, "panel-1"), f"pressing « {command} » changed the panel")


def assert_no_command_offered(case, frame: dict) -> None:
    """No command of the reference is offered as if a door recorded it."""
    case.assertEqual([], [c["name"] for c in frame["controls"] if c["name"] in COMMANDS and not c["disabled"]],
                     "a command no door records is offered")


def projects_served(case, address: str) -> set[str]:
    """The names of the projects the cockpit serves at GET /api/projects."""
    code, _, body = fetch(address + "/api/projects")
    case.assertEqual(200, code)
    return {project["display_name"] for project in json.loads(body)["projects"]}


def options_of(frame: dict, count: int = 3) -> list[str]:
    """The texts of the options `option-1` … of the page, in their order."""
    return [says(frame, f"option-{n}") for n in range(1, count + 1)]


def token_deviations(address: str, expected: dict[str, dict[str, str]]) -> list[str]:
    """How the tokens the page of the destination declares differ from
    those `expected` (theme -> token -> value), one line per token and
    theme: absent, or another value."""
    declared = tokens_of(address, PATH)
    return [
        f"{name} ({theme}) : {declared[theme].get(name)!r}, the reference has {value!r}"
        for theme, tokens in expected.items() for name, value in tokens.items()
        if declared[theme].get(name) != value
    ]
