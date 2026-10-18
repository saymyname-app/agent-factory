"""What the criterion tests of the destination « Vue d’ensemble, décisions et
résultat » share (T02R Prototype Fold, af-vbb4ol, replacing T02 af-0gonc9;
Spec af-2zseit, Testing Decisions 1 and 5). Not a test file: the two
criterion test files of the destination load it.

- `LaunchTree`: a disposable Git repository holding the tree the tests run
  in, at one commit or more, from which the real launcher of the profile
  starts the cockpit on a named dataset;
- `measure`: the page the launched cockpit serves at one of its addresses,
  as a headless Chromium renders it, in frames of the given widths and in
  the given theme (the preferred colour scheme of the browser), read by a
  small script of this file -- named anchors, text, controls, overflow,
  clipping, overlaps and contrast -- and, when asked, what the page shows
  after one control was activated.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = "bin/project-launch"
PROFILE = "config/project-descriptors/agent-factory.json"

# Anchors named after their element and a number (`div-3`, `button-7`) are
# the frozen page's numbering, not a part of the page with a name of its
# own: the hierarchy the tests hold is that of the named parts (`inbox-1`,
# `panel-3`, `nav-1`, `main-1`). The fidelity measure at the end of the
# ticket compares every anchor.
NUMBERED_HEADS = {
    "a", "article", "b", "button", "circle", "code", "dd", "details", "div", "dl", "dt", "em", "footer", "g",
    "h1", "h2", "h3", "h4", "header", "i", "img", "input", "label", "li", "line", "link", "ol", "option", "p",
    "path", "polyline", "rect", "section", "select", "small", "span", "strong", "summary", "svg", "table", "td",
    "text", "textarea", "th", "time", "title", "tr", "ul",
}


def named_part(anchor: str) -> bool:
    """An anchor that names a part of the page: `inbox-1`, `panel-3`,
    `metric-grid-1`, `nav-1`; not `div-3` or `span-9`."""
    head, _, number = anchor.rpartition("-")
    return not (number.isdigit() and head in NUMBERED_HEADS)


def git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
        "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, env=env
    ).stdout.strip()


def fetch(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


class LaunchTree:
    """The tree under test in a disposable Git repository, and the cockpits
    launched from it by the launcher of the profile."""

    def __init__(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="cockpit-home-criteria-"))
        self.repo = self.work / "repo"
        shutil.copytree(
            ROOT, self.repo, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        git(self.repo, "init", "--quiet", "--initial-branch", "main")
        git(self.repo, "add", "--all", "--force")
        git(self.repo, "commit", "--quiet", "--message", "the tree under test")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.states: list[Path] = []
        self.lock = threading.Lock()

    def reword(self, name: str, replacements: dict[str, str]) -> str:
        """A commit where the dataset `name` the profile declares says, for
        each text of `replacements`, the other one, wherever it is written;
        the tree is back at the first commit afterwards."""
        profile = json.loads((self.repo / PROFILE).read_text(encoding="utf-8"))
        declared = self.repo / profile["launch"]["datasets"][name]
        text = declared.read_text(encoding="utf-8")
        for before, after in replacements.items():
            assert before in text, f"{name} does not say {before!r}"
            text = text.replace(before, after)
        declared.write_text(text, encoding="utf-8")
        git(self.repo, "commit", "--quiet", "--all", "--message", f"{name} says something else")
        reworded = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "--quiet", self.head)
        return reworded

    def launch(self, dataset: str, commit: str | None = None) -> str:
        """The address of the cockpit the launcher started at `commit` (the
        tree as it is by default) on `dataset`."""
        commit = commit or self.head
        with self.lock:
            state = self.work / f"launch-{len(self.states)}.json"
            self.states.append(state)
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "start", str(self.repo / PROFILE),
             "--commit", commit, "--dataset", dataset, "--state-file", str(state), "--timeout", "30"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        try:
            record = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise AssertionError(
                f"the launcher answered no JSON on {dataset} (exit {proc.returncode}): {proc.stdout}{proc.stderr}"
            ) from None
        if record.get("started") is not True or record.get("commit") != commit:
            raise AssertionError(f"the cockpit was not started on {dataset} at {commit}: {record}")
        return record["address"]

    def stop_all(self) -> None:
        for state in self.states:
            if state.exists():
                subprocess.run(
                    [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "stop",
                     "--state-file", str(state)],
                    text=True, capture_output=True, stdin=subprocess.DEVNULL,
                )
        self.states = []

    def remove(self) -> None:
        self.stop_all()
        shutil.rmtree(self.work, ignore_errors=True)


# --- the browser ---------------------------------------------------------------

BROWSER_NAMES = ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
BROWSER_CACHE_GLOBS = ("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
                       "chromium-*/chrome-linux*/chrome")
# The preferred colour scheme the browser is given (chrome-headless-shell
# 1243: 0 is dark, 1 is light).
COLOUR_SCHEMES = {"light": "1", "dark": "0"}
FRAME_HEIGHT = 900
BROWSER_TIMEOUT = 90


def find_browser() -> str:
    """A headless Chromium of this host: the one named by
    EVIDENCE_CAPTURE_BROWSER, else one on the PATH or in the Playwright cache."""
    configured = os.environ.get("EVIDENCE_CAPTURE_BROWSER")
    if configured:
        return configured
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ".cache" / "ms-playwright")
    for names, pattern in ((BROWSER_NAMES[:1], BROWSER_CACHE_GLOBS[0]), (BROWSER_NAMES[1:], BROWSER_CACHE_GLOBS[1])):
        for name in names:
            found = shutil.which(name)
            if found:
                return found
        for candidate in sorted(cache.glob(pattern), reverse=True):
            if os.access(candidate, os.X_OK):
                return str(candidate)
    raise RuntimeError(f"no headless Chromium on this host ({', '.join(BROWSER_NAMES)} or {cache})")


MEASURE_SCRIPT = (Path(__file__).with_name("home_destination_measure.js")).read_text(encoding="utf-8")
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
    """The measuring page, served over HTTP from this process: a page read
    from a file is refused the documents of its frames."""
    global _server
    with _server_lock:
        if _server is None:
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _MeasurePage)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{_server.server_address[1]}/measure.html"


def measure(address: str, path: str = "/", *, theme: str = "dark", widths: tuple[int, ...] = (1440,),
            click: str | None = None, keys: bool = False) -> list[dict]:
    """How the page at `address` + `path` renders in `theme`, one record per
    frame width: see home_destination_measure.js for what a record holds.
    With `click`, the control whose accessible name is `click` (or starts
    with it) is activated in each frame -- with `keys`, by the keyboard:
    focused, then Enter pressed on it --, and the record holds, under
    `after`, the frame read again two seconds later."""
    query = urllib.parse.urlencode({
        "target": address + path, "widths": ",".join(str(w) for w in widths),
        "height": FRAME_HEIGHT, "click": click or "", "keys": "1" if keys else "",
    })
    work = tempfile.mkdtemp(prefix="cockpit-home-browser-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        # The measuring page reads frames served from another port of this
        # host: both switches are needed (as for the fidelity measure).
        "--disable-web-security", "--disable-site-isolation-trials",
        f"--window-size={max(widths) + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        "--virtual-time-budget=30000", "--dump-dom", f"{_measure_url()}?{query}",
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
        raise RuntimeError(f"the browser measured nothing on {address}{path} ({theme}): {measured}")
    return measured["frames"]


def measure_until(address: str, ready, *, seconds: float = 20, **options) -> list[dict]:
    """`measure`, again until `ready(frames)` holds or `seconds` passed: a
    state that the cockpit reaches after a time (a source that falls
    silent, a reading that never ends) is measured once reached, or as it
    stands at the end, for the assertions to say what is missing."""
    deadline = time.monotonic() + seconds
    while True:
        frames = measure(address, **options)
        if ready(frames) or time.monotonic() > deadline:
            return frames
        time.sleep(1)


def hierarchy(frame: dict) -> dict[str, tuple[str, str | None]]:
    """The named parts of a measured page: anchor -> (element, the named
    part that holds it, or None)."""
    parts = {}
    for anchor in frame["anchors"]:
        if not named_part(anchor["name"]):
            continue
        holder = next((name for name in anchor["chain"] if named_part(name)), None)
        parts[anchor["name"]] = (anchor["tag"], holder)
    return parts


def text_of(frame: dict, anchor: str) -> str:
    """The text of the named anchor of a measured page, lines trimmed, or
    '' when the page has no such anchor."""
    return frame["texts"].get(anchor, "")


def says(frame: dict, anchor: str) -> str:
    """The text of an anchor of a measured page on one line, spaces
    collapsed: what a phrase of the reference is looked for in."""
    return " ".join(text_of(frame, anchor).split())


# --- the reference -------------------------------------------------------------

# The named parts of the destination with its content, as the Validated
# Prototype draws them (prototype/cockpit-b-zones-20261012 at 632deea,
# prototypes/c01-complete/frozen-panorama-home, states/home-content.html and
# the eight states drawn the same): part -> (element, the named part that
# holds it). The other states are written in the tests from this one.
CONTENT_PARTS = {
    "shell-nav-1": ("aside", None),
    "brand-1": ("header", "shell-nav-1"),
    "live-1": ("span", "brand-1"),
    "nav-1": ("nav", "shell-nav-1"),
    "selected-1": ("button", "nav-1"),
    "badge-count-1": ("span", "selected-1"),
    "main-1": ("main", None),
    "overview-head-1": ("div", "main-1"),
    "metric-grid-1": ("div", "main-1"),
    "metric-1": ("div", "metric-grid-1"),
    "metric-label-1": ("span", "metric-1"),
    "metric-2": ("div", "metric-grid-1"),
    "metric-label-2": ("span", "metric-2"),
    "metric-3": ("div", "metric-grid-1"),
    "metric-label-3": ("span", "metric-3"),
    "metric-4": ("div", "metric-grid-1"),
    "metric-label-4": ("span", "metric-4"),
    "bilan-1": ("details", "main-1"),
    "chart-key-1": ("div", "bilan-1"),
    "volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1":
        ("svg", "bilan-1"),
    "panel-1": ("section", "main-1"),
    "section-heading-1": ("div", "panel-1"),
    "overview-runs-1": ("iframe", "panel-1"),
    "inbox-1": ("div", "main-1"),
    "panel-2": ("div", "inbox-1"),
    "request-1": ("button", "panel-2"),
    "request-2": ("button", "panel-2"),
    "panel-3": ("article", "inbox-1"),
    "resource-list-1": ("div", "panel-3"),
    "actions-possibles-1": ("div", "panel-3"),
    "panel-4": ("section", "main-1"),
    "rows-1": ("div", "panel-4"),
    "row-1": ("div", "rows-1"),
    "small-stats-1": ("div", "row-1"),
    "release-info-1": ("div", "row-1"),
    "row-2": ("div", "rows-1"),
    "small-stats-2": ("div", "row-2"),
    "release-info-2": ("div", "row-2"),
    "row-3": ("div", "rows-1"),
    "small-stats-3": ("div", "row-3"),
    "release-info-3": ("div", "row-3"),
}
# The named parts the other states of the reference add.
REFERENCE_PARTS = set(CONTENT_PARTS) | {
    "error-1", "notice-1", "skeleton-1", "skeleton-2", "skeleton-3", "actions-1", "tag-1", "row-4",
}
# The parts every state shows: the shell, its navigation and the head of
# the destination.
SHELL_PARTS = {name: CONTENT_PARTS[name] for name in (
    "shell-nav-1", "brand-1", "live-1", "nav-1", "selected-1", "badge-count-1", "main-1", "overview-head-1")}


# --- what the criterion tests assert ----------------------------------------------

# The navigation B, in the order of the reference, and the destination it
# shows as the one open.
NAVIGATION = ["Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses"]


def assert_destination(case, frame: dict, parts: dict) -> None:
    """The page measured is the destination « Vue d’ensemble » served at its
    own address: the navigation B with this destination marked as the one
    open, and exactly the named parts `parts` of the reference among those
    the reference knows -- each its element, inside the same named part."""
    case.assertEqual("/", frame["path"], "the destination is not served at its own address")
    labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
    case.assertEqual(NAVIGATION, labels, "the navigation B is not the reference's")
    current = [label for label, entry in zip(labels, frame["nav"]) if entry["current"]]
    case.assertEqual(["Vue d’ensemble"], current, "the navigation does not say which destination is open")
    served = hierarchy(frame)
    known = set(REFERENCE_PARTS) | set(parts)
    case.assertEqual(parts, {name: value for name, value in served.items() if name in known},
                     "the named parts of the page are not the reference's")


def assert_says(case, frame: dict, anchor: str, *phrases: str) -> None:
    """Each phrase of the reference is said inside the named part `anchor`."""
    text = says(frame, anchor)
    case.assertEqual([], [phrase for phrase in phrases if phrase not in text],
                     f"{anchor} does not say it; it says « {text} »")


def assert_inbox_follows_requests(case, address: str, frame: dict) -> None:
    """« Ce qui t’attend » lists the requests the cockpit serves at
    GET /api/requests, in their order: one line each (`request-N`), saying
    its title -- the page reads the requests where every other reader of
    the cockpit reads them."""
    code, _, body = fetch(address + "/api/requests")
    case.assertEqual(200, code)
    titles = [request["quoi"] for request in json.loads(body)["requests"]]
    lines = sorted((anchor["name"] for anchor in frame["anchors"] if re.fullmatch(r"request-\d+", anchor["name"])),
                   key=lambda name: int(name.rsplit("-", 1)[1]))
    case.assertEqual([f"request-{n}" for n in range(1, len(titles) + 1)], lines,
                     f"« Ce qui t’attend » has not one line per request served {titles}")
    case.assertEqual([], [(line, title) for line, title in zip(lines, titles) if title not in says(frame, line)],
                     "a line of « Ce qui t’attend » does not say the title of its request")


def problems(frames: list[dict], theme: str, panels: tuple[str, ...]) -> dict[str, list]:
    """What makes a measured page unreadable or unusable, by frame: a panel
    of the destination missing, the document wider than the frame, a text
    cut or drawn on another, a contrast under 4.5:1, a control without a
    name, out of reach of the keyboard, that the keyboard cannot activate
    (reached, but neither a link, a button, a field nor a summary: Enter
    does what a script makes of it, if anything) or without a visible
    focus, a button or a field whose box stands out from what is behind it
    under 3:1, a page that is not in the theme the browser asked for.
    Empty when none."""
    found = {}
    for frame in frames:
        names = {anchor["name"] for anchor in frame["anchors"]}
        background = frame["background"]
        wrong_theme = background is None or (background > 0.1 if theme == "dark" else background < 0.5)
        controls = frame["controls"]
        frame_problems = {
            "panels missing": [panel for panel in panels if panel not in names],
            "document wider than the frame (px)": [frame["overflow"]] if frame["overflow"] else [],
            "texts cut": frame["clipped"],
            "texts drawn on each other": frame["overlaps"],
            "contrast too low": frame["contrast"],
            "controls without a name": [c["tag"] + " in " + str(c["anchor"]) for c in controls if not c["name"]],
            "controls out of reach of the keyboard": [c["name"] for c in controls
                                                      if not c["disabled"] and not c["reachable"]],
            "controls the keyboard cannot activate": [c["name"] for c in controls
                                                      if c["reachable"] and not c["native"]],
            "controls without a visible focus": [c["name"] for c in controls if c["reachable"] and not c["focus_visible"]],
            "control boxes under 3:1": [f"{c['name']} : {c['boundary']:.2f}:1" for c in controls
                                        if c["boundary"] is not None and c["boundary"] < 3 - 0.01],
            f"not a {theme} page (background luminance)": [background] if wrong_theme else [],
        }
        frame_problems = {what: items for what, items in frame_problems.items() if items}
        if frame_problems:
            found[f"{frame['width']} px, {theme}"] = frame_problems
    return found
