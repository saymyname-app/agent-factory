"""What the criterion tests of I « Accès HTTPS sur la VM, veille de silence et
procédure de réglages opérateur » share (af-cp4fzd; Spec af-fgcw0d, user
stories 61, 67, 93 and 98, Implementation Decisions « Notifications et
veille » and « Accès hôte », Testing Decisions 1, 4 and 8). Not a test
file: the three criterion test files of I load it.

- `declare`: a dataset of the profile -- one it already declares, with what
  a case adds to it (`https_identity_proxy`, the synthetic identity proxy in
  front of the cockpit, as Tailscale Serve is in service; `heartbeat`, where
  the heartbeat of the launch goes and at what pace) -- declared at a commit
  of the launched tree of its own; the cockpit is then started on it by the
  launcher of the profile, bin/project-launch, through `LaunchTree`
  (home_destination.py);
- `section`: what a section of a page served says, found by its heading,
  with its links;
- `through_https`: a request to the HTTPS address the cockpit gives, as a
  member of the tailnet -- or nobody -- sends it through the identity proxy
  in front of it;
- `launch_logs`: what the launches of a cockpit wrote in their logs.

Nothing here reads the code of the cockpit: the launcher is an entry point
of the profile, a page is read where the cockpit serves it, a request goes
where a browser on the tailnet sends it.
"""

from __future__ import annotations

import html
import http.client
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from home_destination import PROFILE, LaunchTree, git

# Who a request through the identity proxy comes from: the member of the
# tailnet Serve recognises, said by the client of the synthetic proxy.
TAILNET_LOGIN = "X-Synthetic-Tailnet-Login"
# The login the launch recipe of the profile gives the operator of an
# isolated cockpit (docs/COCKPIT.md).
BENJAMIN = "synthetic@example.ts.net"


def declare(tree: LaunchTree, name: str, base: str, **added) -> str:
    """A commit of the launched tree where the profile declares the dataset
    `name`: the dataset `base` it declares, with the keys `added`; the tree
    is back at its first commit afterwards."""
    profile = json.loads((tree.repo / PROFILE).read_text(encoding="utf-8"))
    dataset = json.loads((tree.repo / profile["launch"]["datasets"][base]).read_text(encoding="utf-8"))
    dataset.update(added)
    path = Path("config") / "cockpit-datasets" / f"{name}.json"
    (tree.repo / path).write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    profile["launch"]["datasets"][name] = path.as_posix()
    (tree.repo / PROFILE).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git(tree.repo, "add", "--all")
    git(tree.repo, "commit", "--quiet", "--message", f"{name}: {base} with {', '.join(sorted(added))}")
    commit = git(tree.repo, "rev-parse", "HEAD")
    git(tree.repo, "checkout", "--quiet", tree.head)
    return commit


# --- what a page says --------------------------------------------------------------

class _Sections(HTMLParser):
    """Each <section> of a page: the text of its first heading, its text
    and its links (their text and address)."""

    HEADINGS = ("h1", "h2", "h3", "h4")
    SKIPPED = ("script", "style")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[dict] = []
        self.open: list[dict] = []
        self.heading: dict | None = None
        self.link: dict | None = None
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self.skipping += 1
        elif tag == "section":
            record = {"heading": "", "text": [], "links": []}
            self.open.append(record)
            self.found.append(record)
        elif tag in self.HEADINGS and self.open and not self.open[-1]["heading"]:
            self.heading = self.open[-1]
        elif tag == "a" and self.open:
            self.link = {"text": "", "href": dict(attrs).get("href") or ""}
            for record in self.open:
                record["links"].append(self.link)

    def handle_endtag(self, tag):
        if tag in self.SKIPPED:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "section" and self.open:
            self.open.pop()
        elif tag in self.HEADINGS:
            self.heading = None
        elif tag == "a":
            self.link = None

    def handle_data(self, data):
        if self.skipping:
            return
        if self.heading is not None:
            self.heading["heading"] += data
        if self.link is not None:
            self.link["text"] += data
        for record in self.open:
            record["text"].append(data)


def page(address: str, path: str) -> tuple[int, str]:
    """The status and the body of GET `path` of the cockpit at `address`
    (loopback, as the host reads it)."""
    try:
        with urllib.request.urlopen(address + path, timeout=20) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as answer:
        return answer.code, answer.read().decode("utf-8", errors="replace")


def text_of(source: str) -> str:
    """The text of an HTML page, scripts and styles left out, on one line."""
    source = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", source)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", source)).split())


def section(case, source: str, heading: str) -> dict:
    """The section of the page `source` whose first heading is `heading`:
    its `text` on one line and its `links` (each its `text` on one line and
    its `href`). Fails the case when the page has none."""
    parser = _Sections()
    parser.feed(source)
    found = [s for s in parser.found if " ".join(s["heading"].split()) == heading]
    case.assertTrue(found, f"the page has no section « {heading} »; its sections: "
                           f"{[' '.join(s['heading'].split()) for s in parser.found]}")
    return {"text": " ".join("".join(found[0]["text"]).split()),
            "links": [{"text": " ".join(link["text"].split()), "href": link["href"]} for link in found[0]["links"]]}


# --- through the identity proxy -----------------------------------------------------

class Answer:
    """What came back through HTTPS: its status, its headers, its body."""

    def __init__(self, status: int, headers: dict, body: str) -> None:
        self.status, self.headers, self.body = status, headers, body

    def __repr__(self) -> str:
        return f"Answer({self.status}, {self.body[:200]!r})"


def through_https(case, url: str, path: str, *, login: str | None, method: str = "GET",
                  headers: dict | None = None, data: bytes | None = None) -> Answer:
    """`method` `path` at the HTTPS address `url`, from the member of the
    tailnet `login` (None: from outside the tailnet), with `headers` and
    `data`. The certificate is the launch's own, made for the trial: the
    connection is HTTPS, its authority is not the host's. Fails the case
    when no HTTP answer comes."""
    parts = urllib.parse.urlsplit(url)
    case.assertEqual("https", parts.scheme, f"not an HTTPS address: {url}")
    sent = dict(headers or {})
    if login is not None:
        sent[TAILNET_LOGIN] = login
    connection = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=30,
                                             context=ssl._create_unverified_context())
    try:
        connection.request(method, path, body=data, headers=sent)
        response = connection.getresponse()
        return Answer(response.status, {k.lower(): v for k, v in response.getheaders()},
                      response.read().decode("utf-8", errors="replace"))
    except (OSError, http.client.HTTPException) as broke:
        case.fail(f"no answer through HTTPS to {method} {url}{path}: {type(broke).__name__}: {broke}")
    finally:
        connection.close()


def launch_logs(tree: LaunchTree) -> list[str]:
    """What each launch of `tree` still running wrote in its log, as the
    launcher keeps it beside the copy it runs (`launch.log`)."""
    written = []
    for state in tree.states:
        try:
            record = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        log = Path(record.get("worktree") or "") / "launch.log"
        if log.is_file():
            written.append(log.read_text(encoding="utf-8", errors="replace"))
    return written
