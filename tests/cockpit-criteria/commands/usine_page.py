"""What the criterion tests of the destination « Usine » share (G1, af-wrxrmg,
Prototype Fold of the reference « Panorama — Usine, configuration et
maintenance »; Spec af-fgcw0d, user stories 63, 65, 124, 160, 161, 162 and
175, Testing Decisions 1, 5 and 8). Not a test file: the criterion test
files of the destination load it.

The cockpit is launched by the launcher of the profile, bin/project-launch,
through `LaunchTree` (home_destination.py), and its page GET /usine is read
where a headless Chromium renders it (`measure`). What a page is cut into
is read from the anchors of the reference (prototype/cockpit-b-zones-20261012
at 632deea, prototypes/c01-complete/frozen-panorama-factory, attribute
`data-anchor`): its sections are the anchored `<section>` elements, its
connections the anchors `connection-row-N` of the section « Connexions »
(the reference draws the providers' rows with the same anchors, in their
own section), its flow the anchor `flow-down-1`.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it, and the
configuration a case changes is the one the Factory's own files hold, at a
commit of the launched tree.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from home_destination import LaunchTree, git, measure, problems, says  # noqa: F401  (re-exported for the cases)

PAGE = "/usine"

# A time of day a person reads on the page: « 14:42 » or « 14:42:07 ».
TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
# A time to the second: what changes when a section is read again a few
# seconds later.
TIME_TO_THE_SECOND = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
# A latency measured, in milliseconds: « 24 ms », « 3,2 ms ».
LATENCY = re.compile(r"\b\d+(?:,\d+)? ms\b")
UNKNOWN_SAYING = "inconnu — la source ne répond pas"


def anchors_by_name(frame: dict) -> dict[str, dict]:
    return {anchor["name"]: anchor for anchor in frame["anchors"]}


def sections(frame: dict) -> dict[str, str]:
    """The anchored `<section>` elements of a measured page: anchor -> its
    text on one line."""
    return {anchor["name"]: says(frame, anchor["name"]) for anchor in frame["anchors"] if anchor["tag"] == "section"}


def section_titled(case, frame: dict, title: str) -> tuple[str, str]:
    """The anchored section whose text begins with `title`, the innermost
    when several do: (anchor, text). Fails the case when there is none."""
    found = [(name, text) for name, text in sections(frame).items() if text.startswith(title)]
    case.assertTrue(found, f"the page has no section « {title} »; its sections: {sorted(sections(frame).values())}")
    return min(found, key=lambda item: len(item[1]))


def section_of(frame: dict, anchor: str | None) -> str | None:
    """The anchored section that holds the anchor `anchor` (or is it)."""
    by_name = anchors_by_name(frame)
    if anchor not in by_name:
        return None
    for name in [anchor, *by_name[anchor]["chain"]]:
        if by_name.get(name, {}).get("tag") == "section":
            return name
    return None


def connection_rows(frame: dict) -> dict[str, str]:
    """The connections the page shows (anchors `connection-row-N` of the
    section « Connexions »): anchor -> its text on one line."""
    held = [name for name, text in sections(frame).items() if text.startswith("Connexions")]
    return {anchor["name"]: says(frame, anchor["name"]) for anchor in frame["anchors"]
            if re.fullmatch(r"connection-row-\d+", anchor["name"]) and set(held) & set(anchor["chain"])}


def colour(frame: dict, anchor: str) -> str:
    """The computed colour of the text of the anchor `anchor`."""
    return anchors_by_name(frame)[anchor]["styles"]["color"]


def section_titles(frame: dict) -> list[str]:
    """The text each anchored section of the page begins with, in the
    order of the page."""
    return [says(frame, anchor["name"]) for anchor in frame["anchors"] if anchor["tag"] == "section"]


def in_order(expected: list[str], titles: list[str]) -> list[str]:
    """The titles of `expected` the page does not show in that order,
    each as the start of one of its sections (`titles`); other sections of
    the page may come between them."""
    missing, at = [], 0
    for title in expected:
        found = next((index for index in range(at, len(titles)) if titles[index].startswith(title)), None)
        if found is None:
            missing.append(title)
        else:
            at = found + 1
    return missing


def connection(case, frame: dict, name: str) -> str:
    """The text of the connection whose text begins with `name`. Fails the
    case when the page shows none."""
    rows = connection_rows(frame)
    found = [text for text in rows.values() if text.startswith(name)]
    case.assertEqual(1, len(found), f"the page has not one connection « {name} »; its connections: {rows}")
    return found[0]


def recheck_controls(frame: dict) -> list[dict]:
    """The controls of a measured page whose accessible name begins with
    « Revérifier »."""
    return [control for control in frame["controls"] if control["name"].startswith("Revérifier")]


def recheck_of(case, frame: dict, section: str) -> dict:
    """The one control « Revérifier… » the anchored section `section` holds.
    Fails the case when it holds none, or several."""
    held = [control for control in recheck_controls(frame) if section_of(frame, control["anchor"]) == section]
    case.assertEqual(1, len(held), f"the section {section} does not hold one control « Revérifier… »: {held}")
    return held[0]


def reconfigure(tree: LaunchTree, edits: dict[str, Callable[[str], str]]) -> str:
    """A commit of the launched tree where each file of `edits` (a path of
    the Factory's own configuration) is what its function makes of its
    text; the tree is back at its first commit afterwards."""
    for path, edit in edits.items():
        target = Path(tree.repo) / path
        before = target.read_text(encoding="utf-8")
        after = edit(before)
        assert after != before, f"{path} is not changed by its edit"
        target.write_text(after, encoding="utf-8")
    git(tree.repo, "commit", "--quiet", "--all", "--message", "the configuration says something else")
    commit = git(tree.repo, "rev-parse", "HEAD")
    git(tree.repo, "checkout", "--quiet", tree.head)
    return commit


def observed(tree: LaunchTree, files: dict[str, str]) -> str:
    """A commit of the launched tree that holds, besides the Factory's own
    files, the files `files` (path -> text) a host writes beside them and
    no commit of the Factory holds -- what the provider failover observed;
    the tree is back at its first commit afterwards."""
    for path, text in files.items():
        target = Path(tree.repo) / path
        assert not target.exists(), f"{path} is already in the launched tree"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(tree.repo, "add", "--force", path)
    git(tree.repo, "commit", "--quiet", "--message", "the host observed something")
    commit = git(tree.repo, "rev-parse", "HEAD")
    git(tree.repo, "checkout", "--quiet", tree.head)
    return commit


def replaced(before: str, after: str) -> Callable[[str], str]:
    """An edit that writes `after` where the text says `before`, once."""
    def edit(text: str) -> str:
        assert text.count(before) == 1, f"the text does not say {before!r} once"
        return text.replace(before, after)
    return edit


# --- how the destination renders (criterion 3 of G1) ---------------------------

# The configured models the roles-test cases look for, as a person reads them.
GPT_5_6 = re.compile(r"gpt[\s-]*5[.,-]6", re.I)
OPUS_5_5 = re.compile(r"opus[\s-]*5[.,-]5", re.I)


def assert_usable(case, tree: LaunchTree, dataset: str, *, themes: tuple[str, ...], widths: tuple[int, ...],
                  panels: tuple[str, ...], agents_say: tuple[str, ...], section_order: list[str] | None) -> None:
    """GET /usine of the cockpit launched on `dataset`, rendered in each
    theme of `themes` at each width of `widths`, draws the anchors `panels`,
    its section « Agents dans le workflow » matches each pattern of
    `agents_say` (case-insensitive), and nothing makes it unreadable or
    unusable (home_destination.problems: overflow, cut or overlapping
    texts, contrast, controls without a name, out of reach of the keyboard
    or without a visible focus, a lost local scroll, the wrong theme). With
    `section_order`, the page shows sections beginning with those titles, in
    that order. Every value checked is the case's own."""
    address = tree.launch(dataset)
    found = {}
    for theme in themes:
        frames = measure(address, PAGE, theme=theme, widths=widths)
        case.assertEqual(list(widths), [frame["width"] for frame in frames])
        found.update(problems(frames, theme, panels))
        for frame in frames:
            agents = [text for text in sections(frame).values() if text.startswith("Agents dans le workflow")]
            case.assertTrue(agents, f"no section « Agents dans le workflow » at {frame['width']} px, {theme}")
            for pattern in agents_say:
                case.assertRegex(agents[0], re.compile(pattern, re.I),
                                 f"« {pattern} » is not said by the roles ({frame['width']} px, {theme})")
            if section_order is not None:
                case.assertEqual([], in_order(section_order, section_titles(frame)),
                                 f"sections missing or out of their order ({frame['width']} px, {theme})")
    case.assertEqual({}, found)

