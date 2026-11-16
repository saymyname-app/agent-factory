"""What the criterion tests of B « Pour moi au premier plan, gestes complets
et commandes qui n'échouent plus en silence » share (af-4uzgzm; Spec
af-fgcw0d, Testing Decisions 1, 3 and 8). Not a test file: the three
criterion test files of B load it.

- `serve_tracker`: the cockpit the launcher of the profile,
  bin/project-launch, starts on a dataset that carries a tracker as the
  doors of the Factory write it (`{"beads": {id: bead}}`), and, when a case
  asks, how the doors of that launch answer (`doors`: the name of a door,
  `expires` -- it never answers -- or `records-then-expires` -- it writes
  its record, then never answers);
- `proposal`, `paused_session`, `escalation`: the beads the doors write, as
  bin/proposal-door (create), the session loop guard of the Factory (a
  session it paused, the Mayor paged first) and bin/escalation-door
  (benjamin) leave them;
- `Operator`: the gestures of the operator over HTTP, as the browser sends
  them from a page the cockpit served -- its cookie, its Origin -- behind
  the identity proxy of the host (the login it adds);
- `walk`: the page at GET / as a headless Chromium shows it, then after
  each step of a gesture done in it (a control activated, a field filled),
  the browser going through an identity proxy that adds the login of the
  operator, as Tailscale Serve does in front of the cockpit. The page that
  walks is served by that proxy at the address of the cockpit itself, so
  the cockpit's page is read from its own origin and the browser keeps its
  web security: a gesture it sends carries the Origin a browser sends;
- what a page says: `visible_text`, `control`, and `folded`, the folded
  details of the page apart from the old zone « Détails techniques et
  actions ».

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it, the
gestures are sent where the browser sends them.
"""

from __future__ import annotations

import html
import http.client
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from home_destination import COLOUR_SCHEMES, PROFILE, find_browser, git

# The login the launch recipe of the profile gives the operator of an
# isolated cockpit: the one its identity check expects (docs/COCKPIT.md).
LOGIN = "synthetic@example.ts.net"
IDENTITY_HEADER = "Tailscale-User-Login"
# The fixed time of the datasets of the Vue d'ensemble.
GENERATED_AT = "2026-10-12T12:00:00+02:00"
# The old zone that folded the inbox and its gestures under the overview.
LEGACY_SUMMARY = "Détails techniques et actions"
# How long a gesture may take to answer: longer than any command of the
# cockpit is waited for, so that a command that expires answers in it.
ANSWER_SECONDS = 90


# --- the tracker, as the doors write it ------------------------------------------

def proposal(quoi: str, pourquoi: str, options: list[dict], at: str) -> dict:
    """A proposal of class `decision`, open, as bin/proposal-door create
    leaves it: its title, its label, its description, its note, its
    fields. `options`: the prepared choices, each a letter, an option, a
    consequence, one of them recommended with its reason."""
    return {
        "title": f"PROPOSITION: {quoi}", "status": "open", "issue_type": "task", "priority": 2,
        "labels": ["proposal"], "description": pourquoi, "notes": f"PROPOSITION: {quoi}",
        "created_at": at, "updated_at": at,
        "metadata": {
            "gc.proposal_quoi": quoi, "gc.proposal_pourquoi": pourquoi,
            "gc.proposal_que_faire": json.dumps(options, ensure_ascii=False), "gc.proposal_langue": "fr",
            "gc.proposal_classe": "decision", "gc.proposal_state": "ouverte", "gc.proposal_horodatage": at,
        },
    }


def paused_session(session: str, cycles: int, at: str) -> dict:
    """The bead the session loop guard of the Factory files when it pauses a
    session that wakes and stops in a loop: its title and description, the
    session it suspended, its source, and the Mayor paged first by
    bin/escalation-door (mayor)."""
    message = f"session {session} woke and stopped {cycles} times in the last hour"
    reason = f"factory-session-loop-guard: session {session} looping -- {message}"
    return {
        "title": f"[session-loop] {session}", "status": "open", "issue_type": "bug", "priority": 1,
        "labels": [], "created_at": at, "updated_at": at,
        "description": (f"{message}\n\nDetected by factory-session-loop-guard. Session suspended pending "
                        f"investigation (reversible: `factory-session-loop-guard resume {session}`). af-6675l "
                        "safety net -- this pages independent of cause."),
        "notes": f"MAYOR FIRST: {reason}",
        "metadata": {
            "gc.session_id": session, "gc.source": "factory-session-loop-guard",
            "gc.escalation_mayor_paged_at": at, "gc.escalation_mayor_reason": reason,
        },
    }


def escalation(quoi: str, pourquoi: str, options: list[dict], at: str, project: str) -> dict:
    """A question to the operator, as bin/escalation-door (benjamin) leaves
    it on the bead it asks about: the words of its producer, as written."""
    return {
        "title": quoi, "status": "open", "issue_type": "task", "priority": 2, "labels": [],
        "description": pourquoi, "notes": "", "created_at": at, "updated_at": at,
        "metadata": {
            "gc.needs_benjamin": quoi, "gc.escalation_pourquoi": pourquoi,
            "gc.escalation_que_faire": json.dumps(options, ensure_ascii=False), "gc.escalation_bloquant": "false",
            "gc.escalation_horodatage": at, "gc.project_id": project,
        },
    }


def serve_tracker(tree, beads: dict[str, dict], doors: dict[str, str] | None = None) -> str:
    """The address of the cockpit the launcher of the profile starts on a
    dataset that carries `beads` as its tracker -- and, with `doors`, how
    the doors of the launch answer --, declared in the profile at a commit
    of its own, on top of the others."""
    with tree.lock:
        tree.launches_of_trackers = getattr(tree, "launches_of_trackers", 0) + 1
        name = f"pour-moi-{tree.launches_of_trackers}"
    dataset = {"generated_at": GENERATED_AT, "synthetic": True, "ui": {"id": name, "page": "home"},
               "tracker": {"beads": beads}}
    if doors:
        dataset["doors"] = doors
    repo = tree.repo
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    profile["launch"]["datasets"][name] = path.as_posix()
    (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--message", f"{name}: a tracker as the doors write it")
    return tree.launch(name, git(repo, "rev-parse", "HEAD"))


# --- what the cockpit serves -------------------------------------------------------

def read_json(address: str, path: str) -> dict:
    with urllib.request.urlopen(address + path, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def requests_of(address: str) -> list[dict]:
    """The requests « Ce qui t'attend » lists, as GET /api/requests serves
    them."""
    return read_json(address, "/api/requests").get("requests") or []


def journal_of(address: str) -> list[dict]:
    """The requests resolved at their source, as GET /api/journal serves
    them."""
    return read_json(address, "/api/journal").get("entries") or []


def wait_for(read, ready, seconds: float, interval: float = 0.5):
    """`read()`, again until `ready(value)` holds or `seconds` passed; the
    last value read, for the assertion to say what it was."""
    deadline = time.monotonic() + seconds
    while True:
        value = read()
        if ready(value) or time.monotonic() > deadline:
            return value
        time.sleep(interval)


class Answer:
    """What the cockpit answered to a gesture: its HTTP status, its body
    read as JSON (None when it is not), its raw text, how long it took;
    `broken` names how the request broke when no HTTP answer came."""

    def __init__(self, status=None, body=None, text="", seconds=0.0, broken=""):
        self.status, self.body, self.text, self.seconds, self.broken = status, body, text, seconds, broken

    def error(self) -> str:
        return (self.body or {}).get("error") or "" if isinstance(self.body, dict) else ""

    def __repr__(self) -> str:
        return f"Answer(status={self.status}, body={self.text[:300]!r}, {self.seconds:.1f}s, broken={self.broken!r})"


class Operator:
    """The operator's gestures over HTTP, as the browser sends them from a
    page the cockpit served (its session cookie, its Origin) behind the
    identity proxy of the host (its login)."""

    def __init__(self, address: str):
        self.address = address
        with urllib.request.urlopen(address + "/", timeout=20) as response:
            cookie = response.headers.get("Set-Cookie") or ""
        self.cookie = cookie.split(";", 1)[0]

    def gesture(self, name: str, payload: dict) -> Answer:
        request = urllib.request.Request(
            f"{self.address}/api/actions/{name}", data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Origin": self.address, "Cookie": self.cookie,
                     IDENTITY_HEADER: LOGIN},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=ANSWER_SECONDS) as response:
                status, raw = response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as answer:
            status, raw = answer.code, answer.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException, OSError) as broke:
            return Answer(seconds=time.monotonic() - started, broken=f"{type(broke).__name__}: {broke}")
        try:
            body = json.loads(raw)
        except ValueError:
            body = None
        return Answer(status, body, raw, time.monotonic() - started)


# --- the identity proxy -------------------------------------------------------------

class _Forward(BaseHTTPRequestHandler):
    """A forward proxy for the browser: each request goes on to the address
    it names, with the login of the operator added, as the identity proxy
    of the host adds it in front of the cockpit -- but the page that walks
    (`WALK_PATH`), which it serves itself at that address."""

    def _forward(self) -> None:
        url = urllib.parse.urlsplit(self.path)
        if not url.hostname:
            self.send_error(400, "a proxy is asked an absolute address")
            return
        if url.path == WALK_PATH:
            body = (WALK_PAGE % WALK_SCRIPT).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in ("proxy-connection", "connection", "keep-alive", IDENTITY_HEADER.lower())}
        headers[IDENTITY_HEADER] = LOGIN
        connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=ANSWER_SECONDS)
        try:
            connection.request(self.command, url.path + (f"?{url.query}" if url.query else ""), body=body,
                               headers=headers)
            response = connection.getresponse()
            data = response.read()
        except (OSError, http.client.HTTPException) as broke:
            self.send_error(502, f"the cockpit did not answer: {broke}")
            return
        finally:
            connection.close()
        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = _forward

    def log_message(self, *args):
        pass


_servers_lock = threading.Lock()
_servers: dict[str, ThreadingHTTPServer] = {}


def _served(name: str, handler) -> int:
    """The port of the server `name` of this process, started once."""
    with _servers_lock:
        if name not in _servers:
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            _servers[name] = server
        return _servers[name].server_address[1]


# --- the browser ------------------------------------------------------------------

WALK_SCRIPT = (Path(__file__).with_name("pour_moi_walk.js")).read_text(encoding="utf-8")
WALK_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>gestes</title></head>
<body style="margin:0">
<div id="frames"></div>
<pre id="walk"></pre>
<script>%s</script>
</body></html>
"""
# Where the identity proxy serves the page that walks, at the address of the
# cockpit: a path the cockpit does not serve.
WALK_PATH = "/__pour-moi-walk__"
WALK_RE = re.compile(r'<pre id="walk">(.*?)</pre>', re.S)
BROWSER_TIMEOUT = 150
FRAME_HEIGHT = 900


def walk(address: str, steps: list[dict], *, width: int = 1440, theme: str = "dark", settle_ms: int = 2500,
         path: str = "/") -> dict:
    """The page at `address` + `path` as a headless Chromium shows it, then
    after each of `steps`, done in it one after the other:
    `{"click": name}` activates the visible control whose accessible name is
    `name` or starts with it, `{"fill": name, "value": text}` writes `text`
    in the visible field whose accessible name holds `name`,
    `{"fetch": path}` reads `path` of the cockpit as the page's scripts
    would (its `body` is recorded). Returns
    `{"start": page, "steps": [{"found", "page", "body"?}]}`, a page being its
    `path`, its `text` as shown (what a closed details holds is not shown)
    and its visible `controls` (`name`, `disabled`, `field`, `folds`: the
    summaries of the details that hold it, nearest first); the walk stops
    at the first step whose control is not found. The browser goes through
    the identity proxy of this process, which serves the walking page at
    `address` itself."""
    proxy = _served("proxy", _Forward)
    query = urllib.parse.urlencode({
        "target": address + path, "width": width, "height": FRAME_HEIGHT, "settle": settle_ms,
        "steps": json.dumps(steps, ensure_ascii=False),
    })
    work = tempfile.mkdtemp(prefix="cockpit-pour-moi-browser-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        f"--proxy-server=http://127.0.0.1:{proxy}", "--proxy-bypass-list=<-loopback>",
        f"--window-size={width + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        "--virtual-time-budget=120000", "--dump-dom", f"{address}{WALK_PATH}?{query}",
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
    found = WALK_RE.search(dom)
    walked = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    if not isinstance(walked, dict) or walked.get("ok") is not True:
        raise RuntimeError(f"the browser walked nothing on {address}{path}: {walked}")
    return walked


def visible_text(page: dict) -> str:
    """The text of a walked page as shown, on one line, spaces collapsed."""
    return " ".join((page.get("text") or "").split())


def control(page: dict, name: str) -> dict | None:
    """The first visible control of a walked page whose accessible name is
    `name` or starts with it."""
    return next((c for c in page.get("controls") or [] if c["name"] == name or c["name"].startswith(name)), None)


# --- the folded details, in the HTML served -----------------------------------------

class _Details(HTMLParser):
    """Each <details> of a page: its summary, the summaries of the details
    that hold it, its text and the links it holds."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[dict] = []
        self.open: list[dict] = []
        self.summary_of: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag == "details":
            record = {"summary": "", "within": [d["summary"] for d in self.open], "text": [], "links": []}
            self.open.append(record)
            self.found.append(record)
        elif tag == "summary" and self.open:
            self.summary_of.append(self.open[-1])
        elif tag == "a" and self.open:
            href = dict(attrs).get("href")
            if href:
                for record in self.open:
                    record["links"].append(href)

    def handle_endtag(self, tag):
        if tag == "details" and self.open:
            self.open.pop()
        elif tag == "summary" and self.summary_of:
            self.summary_of.pop()

    def handle_data(self, data):
        if self.summary_of:
            self.summary_of[-1]["summary"] += data
        for record in self.open:
            record["text"].append(data)


def folded(address: str, path: str = "/") -> list[dict]:
    """The folded details of the page at `path`, apart from the old zone
    « Détails techniques et actions » and what it holds: each its summary,
    its text on one line and its links."""
    with urllib.request.urlopen(address + path, timeout=20) as response:
        source = response.read().decode("utf-8")
    parser = _Details()
    parser.feed(source)
    return [
        {"summary": " ".join(d["summary"].split()), "text": " ".join("".join(d["text"]).split()), "links": d["links"]}
        for d in parser.found
        if LEGACY_SUMMARY not in d["summary"] and not any(LEGACY_SUMMARY in s for s in d["within"])
    ]
