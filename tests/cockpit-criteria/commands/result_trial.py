"""What the criterion tests of A2 « Essai et Avis » share (af-ocz64w; Spec
af-fgcw0d, user stories 30, 31, 109, 110, 112-116, 118, 120, 121, Testing
Decisions 1, 2 and 8). Not a test file: the criterion test files of A2 load
it.

- `serve`: a dataset the profile declares, as it is or with what its result
  says of itself (`result`: its commit, the words of its answer…), written
  at a commit of its own in the tree of a `home_destination.LaunchTree`,
  and the cockpit the launcher of the profile starts on it: the address the
  operator reaches it at, the HTTPS address of the identity proxy in front
  of it when its dataset carries one (`https_identity_proxy`, #781), as
  the section « Accès » of GET /usine gives it;
- `read_json`, `Operator`: what the cockpit serves, and the gestures of the
  operator as the browser sends them (pour_moi.Operator), at that address:
  through the identity proxy, as the member of the tailnet the operator is,
  when it is an HTTPS address;
- `walk`: the page the launched cockpit serves, walked in a headless
  Chromium behind the identity proxy of B (pour_moi), as the walk of B does
  it, with the choices a judgement needs besides -- a radio button, an
  option of a list -- and what the page leaves behind it: the addresses
  the tabs it opened went to, as the proxy saw them, the texts it copied
  for the session (result_walk.js). At an HTTPS address, the browser goes
  to the identity proxy in front of the cockpit through that proxy of B,
  which ends its tunnel and says who connects;
- `result_of`: the chantier whose result the cockpit serves at
  GET /api/projects, and that result;
- `product_text`: what the address a tab was opened on answers, once it
  answers;
- `redelivered_once_read`: the cockpits served meanwhile find their result
  delivered again at another commit once they have read it -- the tracker
  of the launch rewritten as the Acceptance Session of the launch opens,
  before it reads the dossier, as a new delivery can land between the read
  of the cockpit and the session in service (R11, af-ksan9t).

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it, the result
where the cockpit serves it.
"""

from __future__ import annotations

import contextlib
import html
import http.client
import json
import os
import re
import shutil
import signal
import socketserver
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pour_moi  # noqa: E402
from home_destination import COLOUR_SCHEMES, PROFILE, find_browser, git  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fixtures" / "cockpit" / "synthetic-city"))
import identity_proxy  # noqa: E402

# The datasets this file writes are named after it, numbered.
SERVED = "a2-result"
# The HTTPS address of the identity proxy in front of a launch, as the
# section « Accès » of GET /usine gives it.
SECURE_ADDRESS = re.compile(r"https://127\.0\.0\.1:\d+")
# The certificate of the identity proxy is the launch's own, made for the
# trial: the operator's client trusts it as it is.
TRUSTED = ssl._create_unverified_context()


def serve(tree, base: str, result: dict | None = None) -> str:
    """The address of the cockpit the launcher of the profile starts on the
    dataset `base` of the profile, with `result` -- what its result says of
    itself, written in the dataset under `result` -- when given: a dataset
    of its own, declared in the profile at a commit of its own, on top of
    the tree as it is. The tree stays at that commit."""
    repo = tree.repo
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    dataset = json.loads((repo / profile["launch"]["datasets"][base]).read_text(encoding="utf-8"))
    if result is not None:
        dataset["result"] = result
    tree.launches_served = getattr(tree, "launches_served", 0) + 1
    name = f"{SERVED}-{tree.launches_served}"
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    dataset["ui"] = {**dataset["ui"], "id": name}
    (repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile["launch"]["datasets"][name] = path.as_posix()
    (repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--message", f"{name}: {base} with its result")
    address = tree.launch(name, git(repo, "rev-parse", "HEAD"))
    if not dataset.get("https_identity_proxy"):
        return address
    with urllib.request.urlopen(address + "/usine", timeout=20) as response:
        secure = set(SECURE_ADDRESS.findall(response.read().decode("utf-8")))
    assert len(secure) == 1, f"GET /usine of {name} gives not one HTTPS address: {sorted(secure)}"
    return secure.pop()


def _open(address: str, path: str, *, data: bytes | None = None, headers: dict | None = None,
          timeout: float = 20):
    """`path` of the cockpit at `address`, asked as the operator: through
    the identity proxy, as the member of the tailnet the operator is, when
    `address` is HTTPS."""
    sent = dict(headers or {})
    secure = address.startswith("https://")
    if secure:
        sent[identity_proxy.IDENTITY] = pour_moi.LOGIN
    request = urllib.request.Request(address + path, data=data, headers=sent,
                                     method="POST" if data is not None else "GET")
    return urllib.request.urlopen(request, timeout=timeout, context=TRUSTED if secure else None)


def read_json(address: str, path: str) -> dict:
    with _open(address, path) as response:
        return json.loads(response.read().decode("utf-8"))


class Operator(pour_moi.Operator):
    """The operator's gestures as the browser sends them from a page the
    cockpit served at `address` (pour_moi.Operator): its session cookie,
    its Origin -- `address` -- and, at an HTTPS address, through the
    identity proxy in front of the cockpit."""

    def __init__(self, address: str):
        if not address.startswith("https://"):
            super().__init__(address)
            return
        self.address = address
        with _open(address, "/") as response:
            self.cookie = (response.headers.get("Set-Cookie") or "").split(";", 1)[0]

    def gesture(self, name: str, payload: dict) -> pour_moi.Answer:
        if not self.address.startswith("https://"):
            return super().gesture(name, payload)
        started = time.monotonic()
        try:
            with _open(self.address, f"/api/actions/{name}", data=json.dumps(payload).encode("utf-8"),
                       headers={"Content-Type": "application/json", "Origin": self.address,
                                "Cookie": self.cookie},
                       timeout=pour_moi.ANSWER_SECONDS) as response:
                status, raw = response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as answer:
            status, raw = answer.code, answer.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as broke:
            return pour_moi.Answer(seconds=time.monotonic() - started, broken=f"{type(broke).__name__}: {broke}")
        try:
            body = json.loads(raw)
        except ValueError:
            body = None
        return pour_moi.Answer(status, body, raw, time.monotonic() - started)


def result_of(address: str) -> tuple[str, dict]:
    """The chantier whose result the cockpit serves at GET /api/projects --
    the one chantier that has one -- and that result."""
    found = [(chantier["id"], chantier["outcome"]) for project in read_json(address, "/api/projects")["projects"]
             for chantier in project["chantiers"] if chantier.get("outcome")]
    assert len(found) == 1, f"not one chantier with a result at GET /api/projects: {found}"
    return found[0]


def text_of_html(source: str) -> str:
    """The text of an HTML page on one line, spaces collapsed."""
    source = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", source)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", source)).split())


def product_text(address: str, seconds: float = 60) -> str:
    """The text of the page at `address`, once it answers 200 -- a product
    just launched may still be starting -- or '' if it never did within
    `seconds`."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            with urllib.request.urlopen(address, timeout=10) as response:
                if response.status == 200:
                    return text_of_html(response.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        if time.monotonic() > deadline:
            return ""
        time.sleep(1)


# The Acceptance Session the isolated launch of the cockpit runs, in the
# tree of a LaunchTree, and where it is kept while another stands in for it.
SESSION = Path("tests") / "fixtures" / "cockpit" / "synthetic-city" / "acceptance-session"
SESSION_KEPT = SESSION.with_name("acceptance-session-kept")
REDELIVERING_SESSION = """#!/usr/bin/env python3
# The Acceptance Session of the launch, the result delivered again at %(commit)s
# once the cockpit read it (result_trial.redelivered_once_read): that
# delivery written in the tracker of the launch, then the session itself.
import json, os, subprocess, sys
from pathlib import Path

if len(sys.argv) > 2:
    bd, convoy = os.environ["COCKPIT_BD_BIN"], sys.argv[2]
    bead = json.loads(subprocess.run([bd, "show", convoy, "--json"], capture_output=True, text=True,
                                     check=True).stdout)
    bead = bead[0] if isinstance(bead, list) else bead
    delivered = dict(json.loads(bead["metadata"]["gc.flow.delivered"]), commit=%(commit)r)
    subprocess.run([bd, "update", convoy, "--set-metadata",
                    "gc.flow.delivered=" + json.dumps(delivered, ensure_ascii=False)],
                   capture_output=True, text=True, check=True)
kept = str(Path(__file__).resolve().with_name(%(kept)r))
os.execv(sys.executable, [sys.executable, kept, *sys.argv[1:]])
"""


@contextlib.contextmanager
def redelivered_once_read(tree, commit: str):
    """The cockpits `serve` starts on `tree` meanwhile find the result they
    serve delivered again at `commit` when Essai opens its Acceptance
    Session: the session of the launch writes that delivery in the tracker,
    then reads the dossier and launches it. The tree has its own session
    back afterwards, at a commit of its own."""
    repo = tree.repo
    session, kept = repo / SESSION, repo / SESSION_KEPT
    session.replace(kept)
    session.write_text(REDELIVERING_SESSION % {"commit": commit, "kept": kept.name}, encoding="utf-8")
    session.chmod(0o755)
    try:
        yield
    finally:
        kept.replace(session)
        git(repo, "add", "--all")
        git(repo, "commit", "--quiet", "--message", "the Acceptance Session of the launch back")


# --- the browser ------------------------------------------------------------------

WALK_SCRIPT = (Path(__file__).with_name("result_walk.js")).read_text(encoding="utf-8")
WALK_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>avis</title></head>
<body style="margin:0">
<div id="frames"></div>
<pre id="walk"></pre>
<script>%s</script>
</body></html>
"""
# Where the identity proxy serves this walking page, at the address of the
# cockpit: a path the cockpit does not serve.
WALK_PATH = "/__result-walk__"
WALK_RE = re.compile(r'<pre id="walk">(.*?)</pre>', re.S)
FRAME_HEIGHT = 900


_tunnel_context: ssl.SSLContext | None = None


def _tunnel() -> ssl.SSLContext:
    """What the proxy of the walk ends the browser's HTTPS tunnels with: a
    certificate for 127.0.0.1 made for this process, which the browser of
    the walk is told to accept."""
    global _tunnel_context
    if _tunnel_context is None:
        cert, key = identity_proxy.certificate(Path(tempfile.mkdtemp(prefix="cockpit-result-tunnel-")))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        _tunnel_context = context
    return _tunnel_context


class _Walk(pour_moi._Forward):
    """The identity proxy of B, which serves this walking page besides, and
    sees each tab of the browser: a page the browser loads as a document of
    its own, not in the frame of the walk. `opened`: their addresses, for
    the walk under way. The browser's HTTPS tunnel to the identity proxy in
    front of a cockpit ends here: what it asks in it goes on to that proxy,
    from the member of the tailnet the operator is, its Origin as the
    browser sent it."""

    opened: list[str] = []
    tunnel = ""

    def do_CONNECT(self) -> None:  # noqa: N802
        self.send_response(200, "Connection Established")
        self.end_headers()
        try:
            tls = _tunnel().wrap_socket(self.connection, server_side=True)
        except (ssl.SSLError, OSError):
            self.close_connection = True
            return
        self.connection, self.tunnel = tls, self.path
        self.rfile = tls.makefile("rb")
        self.wfile = socketserver._SocketWriter(tls)
        self.close_connection = False

    def finish(self) -> None:
        super().finish()
        if self.tunnel:
            self.connection.close()

    def _forward(self) -> None:
        url = urllib.parse.urlsplit(self.path)
        asked = f"https://{self.tunnel}{self.path}" if self.tunnel else self.path
        if url.path != WALK_PATH and self.headers.get("Sec-Fetch-Dest") == "document":
            _Walk.opened.append(asked)
        if (url.hostname or self.tunnel) and url.path == WALK_PATH:
            body = (WALK_PAGE % WALK_SCRIPT).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.tunnel:
            self._through_identity_proxy()
            return
        super()._forward()

    def _through_identity_proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in ("proxy-connection", "connection", "keep-alive")}
        headers[identity_proxy.IDENTITY] = pour_moi.LOGIN
        host, _, port = self.tunnel.rpartition(":")
        connection = http.client.HTTPSConnection(host, int(port), timeout=pour_moi.ANSWER_SECONDS, context=TRUSTED)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
        except (OSError, http.client.HTTPException) as broke:
            self.send_error(502, f"the identity proxy did not answer: {broke}")
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


def walk(address: str, steps: list[dict], *, width: int = 1440, theme: str = "dark", settle_ms: int = 2500,
         seconds: int = 150, blocked: bool = False) -> dict:
    """The page at `address` as a headless Chromium shows it behind the
    identity proxy, then after each of `steps` (result_walk.js): `click`,
    `fill`, `check`, `choose`, `fetch`, each with its `wait`. Returns
    `{"start": page, "steps": [{"found", "page", "body"?}]}`, a page being
    its `path`, its `text` as shown, its visible `controls` (`name`,
    `disabled`, `field`, `checked`, `holder`), its `folded` details
    (`summary`, `text`) and the texts it `copied`; the walk stops at the
    first step whose control is not found. The page as the walk left it
    (`last`) has besides `opened`: the address of each real tab the browser
    opened during the walk, as the proxy saw it asked. `blocked`: the
    browser refuses every tab. `seconds` bounds the browser. At an HTTPS
    `address`, the identity proxy in front of the cockpit, the browser
    accepts the certificate the proxy of the walk ends its tunnel with."""
    proxy = pour_moi._served("result-walk", _Walk)
    _Walk.opened = []
    query = urllib.parse.urlencode({
        "target": address + "/", "width": width, "height": FRAME_HEIGHT, "settle": settle_ms,
        "steps": json.dumps(steps, ensure_ascii=False), **({"blocked": "1"} if blocked else {}),
    })
    work = tempfile.mkdtemp(prefix="cockpit-result-browser-")
    argv = [
        find_browser(), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/profile",
        f"--proxy-server=http://127.0.0.1:{proxy}", "--proxy-bypass-list=<-loopback>",
        *(["--ignore-certificate-errors"] if address.startswith("https://") else []),
        f"--window-size={width + 20},{FRAME_HEIGHT + 20}",
        f"--blink-settings=preferredColorScheme={COLOUR_SCHEMES[theme]}",
        f"--virtual-time-budget={seconds * 1000}", "--dump-dom", f"{address}{WALK_PATH}?{query}",
    ]
    proc = None
    try:
        with open(Path(work) / "dom.html", "wb") as out, open(Path(work) / "browser.log", "wb") as log:
            proc = subprocess.Popen(argv, cwd=work, stdin=subprocess.DEVNULL, stdout=out, stderr=log,
                                    start_new_session=True)
            proc.wait(timeout=seconds + 30)
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
        raise RuntimeError(f"the browser walked nothing on {address}: {walked}")
    last(walked)["opened"] = list(_Walk.opened)
    return walked


def last(walked: dict) -> dict:
    """The page as the walk left it: after its last step, or as first read."""
    return walked["steps"][-1]["page"] if walked["steps"] else walked["start"]


def shown(page: dict) -> str:
    """The text of a walked page as shown, on one line, spaces collapsed."""
    return " ".join((page.get("text") or "").split())


def controls(page: dict, name: str) -> list[dict]:
    """The visible controls of a walked page whose accessible name is
    `name` or starts with it."""
    return [c for c in page.get("controls") or [] if c["name"] == name or c["name"].startswith(name)]


def folded(page: dict, summary: str) -> list[str]:
    """The whole text of each <details> of a walked page whose summary
    holds `summary`."""
    return [d["text"] for d in page.get("folded") or [] if summary in d["summary"]]
