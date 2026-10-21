"""What the criterion tests of the destination Runs share (C1, af-lzti7w;
Spec af-fgcw0d, user stories 127 to 135, Testing Decisions 1, 5 and 7). Not
a test file: the criterion test files of the destination load it.

- `LaunchTree` (from home_destination.py): the tree under test in a
  disposable Git repository, from which the real launcher of the profile,
  bin/project-launch, starts the cockpit on a named dataset;
- `observe`: the page the launched cockpit serves at one of its addresses,
  as a headless Chromium renders it, in frames of the given widths, read by
  runs_destination_measure.js -- then read again after each step asked for:
  a click on a control, a wait, a reload of the page;
- what a reading is looked at through: its anchors, the cards of the list,
  the lanes of the frise and their jobs, the detail of a job, its sections
  and its events, the family of a colour, a duration.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it. The values a
case verifies are written in the case.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from home_destination import BROWSER_TIMEOUT, COLOUR_SCHEMES, FRAME_HEIGHT, LaunchTree, find_browser  # noqa: F401

MEASURE_SCRIPT = (Path(__file__).with_name("runs_destination_measure.js")).read_text(encoding="utf-8")
MEASURE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>mesure</title></head>
<body style="margin:0">
<div id="frames"></div>
<pre id="measure"></pre>
<script>%s</script>
</body></html>
"""
MEASURE_RE = re.compile(r'<pre id="measure">(.*?)</pre>', re.S)


class _MeasurePage(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = (MEASURE_PAGE % MEASURE_SCRIPT).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


_server_lock = threading.Lock()
_server: ThreadingHTTPServer | None = None


def _measure_url() -> str:
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _MeasurePage)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}/measure.html"


def observe(address: str, path: str, *, widths: tuple[int, ...] = (1440,), theme: str = "dark",
            steps: tuple[dict, ...] = ()) -> list[list[dict]]:
    """How the page at `address` + `path` renders in `theme`: per frame
    width, the reading once it settled, then one reading after each of
    `steps` -- {"click": name, "within": anchor} activates the control
    drawn inside that anchor whose accessible name starts with (or holds)
    `name`, {"wait": ms} waits, {"reload": True} reloads the page. See
    runs_destination_measure.js for what a reading holds."""
    query = urllib.parse.urlencode({
        "target": address + path, "widths": ",".join(str(w) for w in widths), "height": FRAME_HEIGHT,
        "steps": json.dumps(list(steps)),
    })
    work = tempfile.mkdtemp(prefix="cockpit-runs-browser-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        "--disable-web-security", "--disable-site-isolation-trials",
        f"--window-size={max(widths) + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        "--virtual-time-budget=90000", "--dump-dom", f"{_measure_url()}?{query}",
    ]
    proc = None
    try:
        with open(Path(work) / "dom.html", "wb") as out, open(Path(work) / "browser.log", "wb") as log:
            proc = subprocess.Popen(argv, cwd=work, stdin=subprocess.DEVNULL, stdout=out, stderr=log,
                                    start_new_session=True)
            proc.wait(timeout=BROWSER_TIMEOUT)
        dom = (Path(work) / "dom.html").read_text(encoding="utf-8", errors="replace")
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        shutil.rmtree(work, ignore_errors=True)
    found = MEASURE_RE.search(dom)
    measured = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    if not isinstance(measured, dict) or measured.get("ok") is not True:
        raise AssertionError(f"the browser read nothing of {address}{path} ({theme}): {measured}")
    return [frame["readings"] for frame in measured["frames"]]


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
    page: the time of day each says, its text, whether it is open, its
    whole text and the colours its type is drawn with."""
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
