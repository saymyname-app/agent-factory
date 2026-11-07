"""What the criterion tests of the destination « Analyses » share (D,
af-ten1sp; Spec af-fgcw0d, user stories 124, 148, 149, 150 and 175, Testing
Decisions 1, 5 and 8). Not a test file: the criterion test files of the
destination load it.

- `sources` and its records (`result`, `ticket`, `decision`, `pull`,
  `ci_run`): a dataset of the isolated cockpit whose Analyses read real
  records -- the results, the tickets and the decisions of the delivery
  flow, and what GitHub answers for the CI and the pull requests of the
  declared repository -- at a fixed time, the Monday 12/10/2026 at noon
  (Paris), so that the seven days of the page are the 06/10 to the 12/10.
  A case writes the records, and what it expects of them;
- `served`: the page the launched cockpit serves at one address, read over
  HTTP: the text of each anchor, the points of its daily chart, the views
  its tabs open;
- `Keyboard`: a headless Chromium on one page, driven key by key over its
  DevTools pipe: Tab and Enter pressed as a person presses them.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, and the page is read as the cockpit serves it.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from home_destination import LaunchTree, fetch

# --- the records of a dataset ---------------------------------------------------
#
# A case writes the records its dataset holds, and what it expects of them:
# these only put them in the shape the isolated cockpit reads (the records
# of the delivery flow, what GitHub answers), at the fixed time of every
# dataset of the Analyses, Monday 12/10/2026 at noon (Paris), so that the
# seven days of the page are the 06/10 to the 12/10.

GENERATED_AT = "2026-10-12T12:00:00+02:00"


def at(moment: str | None) -> str | None:
    """« 06/10 09:00 », an instant of October 2026 in Paris, as the tracker
    and GitHub write it; None stays None."""
    if moment is None:
        return None
    day, time = moment.split()
    return f"2026-{day[3:5]}-{day[0:2]}T{time}:00+02:00"


def result(title: str, project: str, published: str, delivered: str, accepted: str | None,
           merged: str | None) -> dict:
    """A result of the flow: published, delivered, accepted by Benjamin and
    merged (None when it was not)."""
    return {"title": title, "project": project, "published": at(published), "delivered": at(delivered),
            "accepted": at(accepted), "merged": at(merged)}


def ticket(title: str, project: str, dispatched: str, outcome: str, merge: str) -> dict:
    """A ticket of the flow, dispatched, then its merge into the integration
    branch: `merged`, or refused (`conflict`)."""
    return {"title": title, "project": project, "dispatched": at(dispatched),
            "merge": {"outcome": outcome, "at": at(merge)}}


def decision(title: str, project: str, asked: str, answered: str | None = None) -> dict:
    """A decision asked of Benjamin, answered or still open."""
    return {"title": title, "project": project, "asked": at(asked), "answered": at(answered)}


def pull(number: int, title: str, merged: str | None) -> dict:
    """A closed pull request, merged or not, as GitHub answers it."""
    return {"number": number, "title": title, "merged_at": at(merged), "updated_at": at(merged)}


def ci_run(number: int, conclusion: str | None, created: str) -> dict:
    """A CI run as GitHub answers it: completed with its conclusion, or
    still running (`conclusion` None)."""
    return {"id": number, "name": "CI", "status": "completed" if conclusion else "in_progress",
            "conclusion": conclusion, "created_at": at(created)}


def sources(name: str, *, results=(), tickets=(), decisions=(), repository: str | None = None, pulls=(),
            ci_runs=()) -> dict:
    """The dataset `name`: the records of the flow, and what GitHub answers
    for `repository` -- nothing when None: no CI the cockpit can read."""
    dataset = {"generated_at": GENERATED_AT, "synthetic": True, "ui": {"id": name, "page": "analysis"},
               "visible_text": "Analyses",
               "flow": {"results": list(results), "tickets": list(tickets), "decisions": list(decisions)}}
    if repository is not None:
        dataset["github"] = {"repository": repository, "pull_requests": list(pulls), "workflow_runs": list(ci_runs)}
    return dataset


# --- the page, read over HTTP ----------------------------------------------------

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# « Exécutions CI réussies · 08/10 : 3 »: one point of a daily chart.
POINT = re.compile(r"^(?P<series>.+?) · (?P<day>.*?(?P<date>\d\d/\d\d).*?) : (?P<value>\d+)$")


class _Page(HTMLParser):
    """The text of each anchor of a page, its links, and the points of the
    charts of daily volumes it draws."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str | None, dict]] = []
        self.texts: dict[str, list[str]] = {}
        self.links: dict[str, list[tuple[str, str]]] = {}
        self.charts: list[dict] = []
        self.body: list[str] = []
        self._link: tuple[str, list[str]] | None = None
        self._title: list[str] | None = None
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "body":
            self._in_body = True
        if tag in VOID:
            return
        anchor = attributes.get("data-anchor")
        if anchor:
            self.texts.setdefault(anchor, [])
        self.stack.append((tag, anchor, attributes))
        if tag == "svg" and (attributes.get("aria-label") or "").startswith("Volumes quotidiens"):
            self.charts.append({"label": attributes["aria-label"], "points": [], "text": []})
        if tag == "a" and attributes.get("href") is not None:
            self._link = (attributes["href"], [])
        if tag == "title" and any(t == "svg" for t, _, _ in self.stack[:-1]):
            self._title = []

    def handle_endtag(self, tag):
        if tag == "title" and self._title is not None:
            if self.charts and self._in_chart():
                self.charts[-1]["points"].append(" ".join("".join(self._title).split()))
            self._title = None
        if tag == "a" and self._link is not None:
            href, words = self._link
            text = " ".join(" ".join(words).split())
            for _, anchor, _ in self.stack:
                if anchor:
                    self.links.setdefault(anchor, []).append((text, href))
            self._link = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def _in_chart(self) -> bool:
        return any(t == "svg" and (a.get("aria-label") or "").startswith("Volumes quotidiens")
                   for t, _, a in self.stack)

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
            return
        if not self._in_body or any(t in ("script", "style") for t, _, _ in self.stack):
            return
        self.body.append(data)
        for _, anchor, _ in self.stack:
            if anchor:
                self.texts[anchor].append(data)
        if self._link is not None:
            self._link[1].append(data)
        if self.charts and self._in_chart():
            self.charts[-1]["text"].append(data)


class Page:
    """A page the cockpit serves, read over HTTP."""

    def __init__(self, address: str, path: str) -> None:
        self.address, self.path = address, path
        status, _, html = fetch(address + path)
        self.status = status
        parsed = _Page()
        parsed.feed(html)
        self._texts = {name: " ".join(" ".join(chunks).split()) for name, chunks in parsed.texts.items()}
        self._links = parsed.links
        self.charts = parsed.charts
        self.text = " ".join(" ".join(parsed.body).split())

    def says(self, anchor: str) -> str:
        """The text of the anchor, on one line; '' when the page has none."""
        return self._texts.get(anchor, "")

    def anchors(self) -> set[str]:
        return set(self._texts)

    def links(self, anchor: str) -> dict[str, str]:
        """The links inside the anchor: their text -> where they lead."""
        return dict(self._links.get(anchor, []))

    def series(self) -> dict[str, list[tuple[str, int]]]:
        """The series of the chart of daily volumes: series -> [(dd/mm,
        value)], in the order drawn; {} when the page draws no such chart."""
        found: dict[str, list[tuple[str, int]]] = {}
        for chart in self.charts:
            for point in chart["points"]:
                matched = POINT.match(point)
                if matched:
                    found.setdefault(matched["series"], []).append((matched["date"], int(matched["value"])))
        return found

    def chart_text(self) -> str:
        """What the chart of daily volumes says: its label, its axes and
        legend inside it, the titles of its points."""
        return " ".join(" ".join(" ".join([chart["label"], *chart["text"], *chart["points"]]).split())
                        for chart in self.charts)

    def method(self) -> dict[str, str]:
        """What the method of the indicator states, by label: « Raison : … »,
        « Population : … », « Période : … » …, read in the page."""
        labels = "|".join(("Raison", "Population", "Période", "Sources", "Horodatage", "Calcul"))
        found = {}
        for matched in re.finditer(rf"\b({labels}) : (.+?)(?=\s(?:{labels}) : |$)", self.text):
            found.setdefault(matched.group(1), matched.group(2).strip())
        return found


def served(address: str, view: str | None = None) -> Page:
    """The page « Analyses » of the cockpit at `address`, on the view whose
    tab is named `view` (« Délais »…), followed from the tab of its first
    page; the first page when None. Read once no source it shows is still
    being read for the first time: a cockpit just launched reads them one
    after the other."""
    page = _read(address, "/analyses")
    if view is None:
        return page
    href = page.links("metric-tabs-1").get(view)
    if href is None:
        raise AssertionError(f"the Analyses have no tab « {view} » leading to its view: "
                             f"{page.links('metric-tabs-1')}")
    return _read(address, href if href.startswith("/") else "/analyses" + href)


def _read(address: str, path: str, seconds: float = 15) -> Page:
    import time

    deadline = time.monotonic() + seconds
    while True:
        page = Page(address, path)
        if "en cours de lecture" not in page.text or time.monotonic() > deadline:
            return page
        time.sleep(0.2)


# --- the keyboard, key by key ----------------------------------------------------

# What the element that has the focus is, read in the page: its accessible
# name, its element and where it leads; null when no control of the page
# has it (the focus left the document).
_FOCUSED = """(() => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.title || '').trim().replace(/\\s+/g, ' ');
  return {name: name, tag: el.tagName.toLowerCase(), href: el.getAttribute('href')};
})()"""
# The controls a person reaches with Tab: shown, not disabled, in the order
# of the document (the page sets no positive tabindex).
_REACHABLE = """(() => Array.from(document.querySelectorAll(
    'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex]'))
  .filter(el => el.tabIndex >= 0 && !el.disabled && el.getClientRects().length > 0
                && getComputedStyle(el).visibility !== 'hidden')
  .map(el => (el.getAttribute('aria-label') || el.innerText || el.value || el.title || '').trim()
                .replace(/\\s+/g, ' ')))()"""


class Keyboard:
    """A headless Chromium driven over its DevTools pipe, on one page of the
    cockpit, in a frame of `width` pixels and the colour scheme `theme`:
    the keys are pressed as a person presses them, and the browser moves
    the focus itself."""

    def __init__(self, url: str, width: int, theme: str = "dark") -> None:
        import os
        import subprocess
        import tempfile

        from home_destination import FRAME_HEIGHT, find_browser

        self._work = tempfile.TemporaryDirectory(prefix="cockpit-analyses-keyboard-")
        to_browser, self._write = os.pipe()
        self._read, from_browser = os.pipe()

        def pipes() -> None:
            # Moved out of the way first: either end may already be fd 3 or 4.
            reading, writing = os.dup(to_browser), os.dup(from_browser)
            os.dup2(reading, 3)
            os.dup2(writing, 4)

        self._browser = subprocess.Popen(
            [find_browser(), "--headless", "--disable-gpu", "--remote-debugging-pipe", "--no-first-run",
             f"--user-data-dir={self._work.name}/profile", f"--window-size={width},{FRAME_HEIGHT}", "about:blank"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=False,
            preexec_fn=pipes, start_new_session=True)
        os.close(to_browser)
        os.close(from_browser)
        self._buffer, self._next, self._events = b"", 0, []
        page = next(t for t in self._call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self._session = self._call("Target.attachToTarget", targetId=page["targetId"], flatten=True)["sessionId"]
        self._call("Page.enable", session=True)
        self._call("Emulation.setFocusEmulationEnabled", enabled=True, session=True)
        self._call("Emulation.setDeviceMetricsOverride", width=width, height=FRAME_HEIGHT, deviceScaleFactor=1,
                   mobile=False, session=True)
        self._call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": theme}],
                   session=True)
        self.open(url)

    def open(self, url: str) -> None:
        self._events = []
        self._call("Page.navigate", url=url, session=True)
        self._wait_load()

    def tab(self) -> dict | None:
        """Tab pressed: the control that has the focus then, None when the
        focus left the page."""
        self._key("Tab", 9)
        return self.focused()

    def enter(self) -> None:
        """Enter pressed on the control that has the focus; what it opens is
        loaded before this returns."""
        self._events = []
        self._key("Enter", 13, text="\r")
        self._wait_load(seconds=5, required=False)

    def focused(self) -> dict | None:
        return self.evaluate(_FOCUSED)

    def reachable(self) -> list[str]:
        """The names of the controls a person reaches with Tab, in order."""
        return self.evaluate(_REACHABLE)

    def text(self, anchor: str) -> str:
        return self.evaluate(f"(document.querySelector('[data-anchor=\"{anchor}\"]') || {{}}).innerText || ''")

    def evaluate(self, expression: str):
        answer = self._call("Runtime.evaluate", expression=expression, returnByValue=True, session=True)
        return answer.get("result", {}).get("value")

    def close(self) -> None:
        import os
        import signal

        try:
            os.killpg(self._browser.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self._browser.wait()
        os.close(self._write)
        os.close(self._read)
        self._work.cleanup()

    def _key(self, key: str, code: int, text: str | None = None) -> None:
        down = {"type": "keyDown" if text is None else "keyDown", "key": key, "code": key,
                "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code}
        if text is not None:
            down["text"] = text
        self._call("Input.dispatchKeyEvent", **down, session=True)
        self._call("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode=code,
                   nativeVirtualKeyCode=code, session=True)

    def _wait_load(self, seconds: float = 20, required: bool = True) -> None:
        import time

        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if any(event.get("method") == "Page.loadEventFired" for event in self._events):
                return
            self._receive(deadline)
        if required:
            raise AssertionError("the page did not load in the browser driven by the keyboard")

    def _call(self, method: str, session: bool = False, **params):
        import os
        import time

        self._next += 1
        message = {"id": self._next, "method": method, "params": params}
        if session:
            message["sessionId"] = self._session
        os.write(self._write, json.dumps(message).encode("utf-8") + b"\0")
        deadline = time.monotonic() + 30
        while True:
            for received in self._receive(deadline):
                if received.get("id") == self._next:
                    if "error" in received:
                        raise AssertionError(f"the browser refused {method}: {received['error']}")
                    return received.get("result", {})

    def _receive(self, deadline: float) -> list[dict]:
        import os
        import select
        import time

        left = deadline - time.monotonic()
        if left <= 0:
            raise AssertionError("the browser driven by the keyboard did not answer")
        ready, _, _ = select.select([self._read], [], [], min(left, 0.5))
        if not ready:
            return []
        chunk = os.read(self._read, 1 << 16)
        if not chunk:
            raise AssertionError("the browser driven by the keyboard ended")
        self._buffer += chunk
        messages = []
        while b"\0" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\0", 1)
            message = json.loads(raw)
            if "method" in message:
                self._events.append(message)
            messages.append(message)
        return messages
