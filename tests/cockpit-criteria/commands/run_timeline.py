"""What the criterion tests of the run timeline « frise du run » share (T03R,
af-hd8wzb, cut from T03; Spec af-2zseit, user stories 129 and 175, Testing
Decisions 1, 5 and 7). Not a test file: the three criterion test files of
the timeline load it.

The launch, the measure and what a measured page is held to are those of
the destination « Vue d’ensemble » (home_destination.py), reused as they
are: `LaunchTree` starts the real cockpit with the launcher of the profile,
bin/project-launch, `measure` reads a page as a headless Chromium renders
it, `problems` says what makes it unreadable or unusable,
`anchor_deviations` how its anchors differ from those a case writes. This
file adds:

- `anchor_outline`: the anchors a case writes, each in its own type -- the
  Runs reference sets some in a monospace type, not all in one;
- `token_deviations_at`: the tokens of a page served at another address
  than GET /;
- `select_job`: a job of the timeline selected in a headless Chromium, by
  a click or by the keyboard, read then, and read again once the page was
  reloaded (run_timeline_select.js).

The values themselves are written in the cases. Nothing here reads the
code of the cockpit.
"""

from __future__ import annotations

import html
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from home_destination import (  # noqa: F401  (re-exported for the test files)
    COLOUR_SCHEMES, BROWSER_TIMEOUT, MEASURE_RE, LaunchTree, anchor_deviations, find_browser, measure, problems,
    says, text_of, tokens_of,
)

# The address of the timeline of a run: the run the cockpit shows.
TIMELINE = "/runs/run"
# The frames the Runs reference is frozen in (validated-prototype.json:
# desktop 1280 x 900, mobile 390 x 844).
WIDTHS = (1280, 390)
THEMES = ("dark", "light")
FRAME_HEIGHT = 900

# The navigation B, in the order of Panorama, and the destination open.
NAVIGATION = ["Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses"]

# The types of the Runs reference, as Chromium computes them.
FAMILIES = {"": "system-ui, sans-serif", "mono": "ui-monospace, monospace"}


def anchor_outline(text: str) -> list[tuple[str, str, str | None, str, str]]:
    """The anchors a case writes as an outline, one per line in the order
    of the page -- « name element line-height », followed by « mono » for
    an anchor set in the monospace type --, indented under the anchor that
    holds it, two spaces a level, as (anchor, element, the anchor that holds
    it, font-family, line-height): what `anchor_deviations` compares."""
    anchors, holders = [], []
    for line in text.strip("\n").split("\n"):
        depth = (len(line) - len(line.lstrip(" "))) // 2
        name, tag, leading, *family = line.split()
        del holders[depth:]
        anchors.append((name, tag, holders[-1] if holders else None, FAMILIES[family[0] if family else ""], leading))
        holders.append(name)
    return anchors


def token_deviations_at(address: str, path: str, expected: dict[str, dict[str, str]]) -> list[str]:
    """How the tokens the page at `address` + `path` declares differ from
    those `expected` (theme -> token -> value), one line per token and
    theme: absent, or another value."""
    served = tokens_of(address, path)
    return [
        f"{name} ({theme}) : {served[theme].get(name)!r}, the reference has {value!r}"
        for theme, tokens in expected.items() for name, value in tokens.items()
        if served[theme].get(name) != value
    ]


def lanes(frame: dict) -> list[str]:
    """The lanes of a measured timeline, in the order of the page: the text
    of each anchor `lane-name`, `lane-name-2`, … on one line."""
    names = [anchor["name"] for anchor in frame["anchors"]
             if anchor["name"] == "lane-name" or anchor["name"].startswith("lane-name-")]
    return [says(frame, name) for name in names]


def tracks(frame: dict) -> list[str]:
    """What each lane of a measured timeline draws, in the order of the
    page: the text of each anchor `track`, `track-2`, … on one line."""
    names = [anchor["name"] for anchor in frame["anchors"]
             if anchor["name"] == "track" or anchor["name"].startswith("track-")]
    return [says(frame, name) for name in names]


# --- selecting a job -------------------------------------------------------------

SELECT_SCRIPT = (Path(__file__).with_name("run_timeline_select.js")).read_text(encoding="utf-8")
SELECT_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>sélection</title></head>
<body style="margin:0">
<div id="frames"></div>
<pre id="measure"></pre>
<script>%s</script>
</body></html>
"""


class _SelectPage(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = (SELECT_PAGE % SELECT_SCRIPT).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


_server_lock = threading.Lock()
_server: ThreadingHTTPServer | None = None


def _select_url() -> str:
    """The selecting page, served over HTTP from this process, as the
    measuring page is: a page read from a file is refused its frame's
    document."""
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _SelectPage)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}/select.html"


def select_job(address: str, title: str, *, theme: str = "dark", width: int = 390, keys: bool = False,
               reload: bool = False, path: str = TIMELINE) -> dict:
    """The job titled `title` selected on the timeline at `address` +
    `path`, in a frame `width` px wide, in `theme`: its control -- the one
    whose text says the title -- clicked or, with `keys`, focused and
    Enter pressed on it; the frame read two seconds later (`selected`) and,
    with `reload`, read again once reloaded (`reloaded`). See
    run_timeline_select.js for what a reading holds."""
    query = urllib.parse.urlencode({
        "target": address + path, "width": width, "height": FRAME_HEIGHT, "title": title,
        "keys": "1" if keys else "", "reload": "1" if reload else "",
    })
    work = tempfile.mkdtemp(prefix="cockpit-run-select-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        "--disable-web-security", "--disable-site-isolation-trials",
        f"--window-size={width + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        "--virtual-time-budget=30000", "--dump-dom", f"{_select_url()}?{query}",
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
    read = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    if not isinstance(read, dict) or read.get("ok") is not True:
        raise RuntimeError(f"the browser read nothing on {address}{path} ({theme}, {width} px): {read}")
    return read


def selection_problems(reading: dict, title: str) -> list[str]:
    """What keeps a reading from showing the job `title` selected and in
    view: its control missing, the job not marked as the one selected, or
    another one marked with it, the job out of view -- less of it seen than
    its box or 44 px across, and 20 px down --, the document wider than its
    frame. Empty when none."""
    if not reading["found"]:
        return [f"no control of the timeline says « {title} »"]
    found = []
    if not reading["target"]:
        found.append(f"« {title} » is not marked as the job selected (marked: {reading['marked']})")
    others = [text for text in reading["marked"] if title not in text]
    if others:
        found.append(f"other parts are marked selected with « {title} »: {others}")
    box, seen = reading["box"], reading["visible"]
    if seen["width"] + 1 < min(box["width"], 44) or seen["height"] + 1 < min(box["height"], 20):
        found.append(f"« {title} » is out of view: {seen['width']:.0f} x {seen['height']:.0f} px seen "
                     f"of {box['width']:.0f} x {box['height']:.0f}")
    if reading["overflow"]:
        found.append(f"the document is {reading['overflow']} px wider than its frame")
    return found
