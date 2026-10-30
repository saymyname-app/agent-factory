"""What the criterion tests of A2 « Essai et Avis » share (af-ocz64w; Spec
af-fgcw0d, user stories 30, 31, 109, 110, 112-116, 118, 120, 121, Testing
Decisions 1, 2 and 8). Not a test file: the criterion test files of A2 load
it.

- `serve`: a dataset the profile declares, as it is or with what its result
  says of itself (`result`: its commit, the words of its answer…), written
  at a commit of its own in the tree of a `home_destination.LaunchTree`,
  and the cockpit the launcher of the profile starts on it;
- `walk`: the page the launched cockpit serves, walked in a headless
  Chromium behind the identity proxy of B (pour_moi), as the walk of B does
  it, with the choices a judgement needs besides -- a radio button, an
  option of a list -- and what the page leaves behind it: the addresses
  the tabs it opened went to, as the proxy saw them, the texts it copied
  for the session (result_walk.js);
- `result_of`: the chantier whose result the cockpit serves at
  GET /api/projects, and that result;
- `product_text`: what the address a tab was opened on answers, once it
  answers.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, the page is read where the browser renders it, the result
where the cockpit serves it.
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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pour_moi  # noqa: E402
from home_destination import COLOUR_SCHEMES, PROFILE, find_browser, git  # noqa: E402

# The datasets this file writes are named after it, numbered.
SERVED = "a2-result"


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
    return tree.launch(name, git(repo, "rev-parse", "HEAD"))


def read_json(address: str, path: str) -> dict:
    with urllib.request.urlopen(address + path, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


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


class _Walk(pour_moi._Forward):
    """The identity proxy of B, which serves this walking page besides, and
    sees each tab of the browser: a page the browser loads as a document of
    its own, not in the frame of the walk. `opened`: their addresses, for
    the walk under way."""

    opened: list[str] = []

    def _forward(self) -> None:
        url = urllib.parse.urlsplit(self.path)
        if url.path != WALK_PATH and self.headers.get("Sec-Fetch-Dest") == "document":
            _Walk.opened.append(self.path)
        if url.hostname and url.path == WALK_PATH:
            body = (WALK_PAGE % WALK_SCRIPT).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        super()._forward()

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
    browser refuses every tab. `seconds` bounds the browser."""
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
