"""What the criterion tests of the destination Runs share (C1, af-lzti7w;
Spec af-fgcw0d, user stories 127 to 135, Testing Decisions 1, 5 and 7). Not
a test file: the criterion test files of the destination load it.

- `LaunchTree` (from home_destination.py): the tree under test in a
  disposable Git repository, from which the real launcher of the profile,
  bin/project-launch, starts the cockpit on a named dataset;
- `observe`: the page the launched cockpit serves at one of its addresses,
  as a headless Chromium renders it, in frames of the given widths -- the
  measure of home_destination.py --, then read again after each step asked
  for: a click on a control, a wait, a reload of the page;
- `observe_themes`: the same, in the dark theme and in the light one, and
  `unreadable`: what makes those readings unreadable or unusable -- the
  `problems` of home_destination.py: the document wider than the screen, a
  text cut or drawn on another, a contrast too low, a control out of reach
  of the keyboard or without a visible focus, a local scroll lost;
- what a reading is looked at through: its anchors, the cards of the list,
  the lanes of the frise and their jobs, the detail of a job, its sections
  and its events, the family of a colour, a duration.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it. The values a
case verifies are written in the case.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from home_destination import LaunchTree, measure, problems  # noqa: F401

THEMES = ("dark", "light")
# A desktop and a phone, as the reference measures them.
SCREENS = (1440, 390)


def observe(address: str, path: str, *, widths: tuple[int, ...] = (1440,), theme: str = "dark",
            steps: tuple[dict, ...] = ()) -> list[list[dict]]:
    """How the page at `address` + `path` renders in `theme`: per frame
    width, the reading once it settled, then one reading after each of
    `steps` -- {"click": name, "within": anchor} activates the control
    drawn inside that anchor whose accessible name starts with (or holds)
    `name` (with "keys": true, by the keyboard), {"wait": ms} waits,
    {"reload": True} reloads the page. See home_destination_measure.js for
    what a reading holds."""
    return [frame["readings"] for frame in measure(address, path, theme=theme, widths=widths, steps=steps)]


def observe_themes(address: str, path: str, *, widths: tuple[int, ...] = SCREENS,
                   steps: tuple[dict, ...] = ()) -> dict[str, list[list[dict]]]:
    """`observe` in each theme of THEMES, side by side: theme -> per frame
    width, the readings."""
    with ThreadPoolExecutor(max_workers=len(THEMES)) as pool:
        found = pool.map(lambda theme: observe(address, path, widths=widths, theme=theme, steps=steps), THEMES)
        return dict(zip(THEMES, found))


def unreadable(by_theme: dict[str, list[list[dict]]], panels: tuple[str, ...]) -> dict[str, dict]:
    """What makes the readings of `observe_themes` unreadable or unusable,
    by screen and theme (`problems`, each panel of `panels` required); empty
    when nothing does."""
    found = {}
    for theme, frames in by_theme.items():
        for number, readings in enumerate(zip(*frames)):
            for screen, said in problems(list(readings), theme, panels).items():
                found[screen if number == 0 else f"{screen}, after step {number}"] = said
    return found


# --- a reading ------------------------------------------------------------------

def anchors(reading: dict, pattern: str, within: str | None = None) -> list[dict]:
    """The anchors of `reading` whose name is `pattern` followed or not by
    its number (`card`, `card-2`, …), in the order of the page; with
    `within`, those inside the anchor of that name only."""
    named = re.compile(rf"{re.escape(pattern)}(?:-\d+)?")
    return [a for a in reading["anchors"]
            if named.fullmatch(a["name"]) and (within is None or within in a["chain"])]


def anchor(reading: dict, name: str) -> dict | None:
    """The anchor of that exact name, or None."""
    return next((a for a in reading["anchors"] if a["name"] == name), None)


def text(reading: dict, name: str) -> str:
    """The rendered text of the anchor of that exact name, '' when absent."""
    found = anchor(reading, name)
    return found["text"] if found else ""


def cards(reading: dict) -> list[dict]:
    """The cards of the list of runs, in the order of the page: the text of
    each, and its mini frise -- (the label of each row, the number of bars
    drawn in it)."""
    found = []
    for card in anchors(reading, "card", within="grid"):
        rows = []
        for row in anchors(reading, "mini-row", within=card["name"]):
            label = next((a["text"] for a in reading["anchors"]
                          if row["name"] in a["chain"][:1] and a["tag"] == "span" and a["text"]), "")
            bars = [a for a in anchors(reading, "mini-bar", within=row["name"]) if a["drawn"]]
            rows.append((label or row["text"], len(bars)))
        found.append({"text": card["text"], "rows": rows})
    return found


def lanes(reading: dict) -> list[dict]:
    """The lanes of the frise, in the order of the page: the text of the
    name of each (who, role), and the text of each of its jobs."""
    found = []
    for lane in anchors(reading, "lane", within="chart"):
        name = next((a["text"] for a in anchors(reading, "lane-name", within=lane["name"])), "")
        jobs = [a["text"] for a in anchors(reading, "job", within=lane["name"]) if a["text"]]
        found.append({"name": name, "jobs": jobs})
    return found


def details(reading: dict) -> list[dict]:
    """The details of a job drawn on the page (anchors `detail`)."""
    return [a for a in anchors(reading, "detail") if a["drawn"]]


def sections(reading: dict) -> dict[str, dict]:
    """The sections of the detail of the job, by the text of their title:
    each its element, whether it is open, and its whole text."""
    found = {}
    for section in anchors(reading, "details", within="inspector-sections") + \
            anchors(reading, "session-history", within="inspector-sections"):
        if section["chain"][:1] != ["inspector-sections"]:
            continue
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [section["name"]]), "")
        found[title] = section
    return found


def section(reading: dict, title: str) -> dict | None:
    """The section of the detail whose title starts with `title`."""
    return next((value for name, value in sections(reading).items() if name.startswith(title)), None)


TIME = re.compile(r"(?<!\d)(\d\d:\d\d:\d\d)(?!\d)")


def events(reading: dict) -> list[dict]:
    """The events listed beside the detail of the job, in the order of the
    page: the time of day each says, its text, its kind as it says it
    (`kind`), whether it is open, its whole text and the colours its kind
    is drawn with."""
    found = []
    for event in anchors(reading, "event", within="event-list"):
        if event["chain"][:1] != ["event-list"]:
            continue
        summary = next((a for a in reading["anchors"]
                        if a["tag"] == "summary" and a["chain"][:1] == [event["name"]]), None)
        said = summary["content"] if summary else event["content"]
        kind = next((a for a in anchors(reading, "event-type", within=event["name"])), None)
        moment = TIME.search(said)
        found.append({"time": moment.group(1) if moment else None, "text": said, "open": event["open"],
                      "kind": kind["content"] if kind else "",
                      "content": event["content"], "colours": (kind or event)["colours"]})
    return found


# --- colours and durations -------------------------------------------------------

RGB = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)")


def family(colour: str) -> str:
    """The family of an rgb() colour as the legend of the frise names them:
    gris (no hue to speak of), turquoise, vert, violet, or autre."""
    found = RGB.search(colour)
    if not found:
        return "autre"
    r, g, b = (float(v) / 255 for v in found.groups())
    high, low = max(r, g, b), min(r, g, b)
    if high - low < 0.12:
        return "gris"
    if high == r:
        hue = (60 * ((g - b) / (high - low))) % 360
    elif high == g:
        hue = 60 * ((b - r) / (high - low)) + 120
    else:
        hue = 60 * ((r - g) / (high - low)) + 240
    if 160 <= hue < 200:
        return "turquoise"
    if 80 <= hue < 160:
        return "vert"
    if 240 <= hue < 300:
        return "violet"
    return "autre"


DURATION = re.compile(r"(?:(\d+) j )?(?:(\d+) h )?(?:(\d+) min )?(\d+) s|(\d+) j (\d+) h|(\d+) h (\d+) min")


def seconds(said: str) -> int | None:
    """The first duration `said` holds -- « 18 s », « 1 min 20 s »,
    « 2 h 05 min », « 3 j 4 h » -- in seconds, or None."""
    found = DURATION.search(said)
    if not found:
        return None
    days, hours, minutes, secs, d2, h2, h3, m3 = (int(v) if v else 0 for v in found.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + secs + d2 * 86400 + h2 * 3600 + h3 * 3600 + m3 * 60
