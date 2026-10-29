"""What the criterion tests of the trace of the jobs share (C2a, af-k2rbw1;
Spec af-fgcw0d, user stories 130, 137, 138, 139, 145 and 175, Testing
Decisions 1, 5, 7 and 8): how a page of Runs, and the projection the
collection keeps, are read. Not a test file: the criterion test files of the
trace load it, beside runs_destination.py.

The values a case verifies -- the sessions of a job, their times, models and
contexts, the prompts sent and their versions, the secrets never collected
-- are written in the case.

Nothing here reads the code of the cockpit: the page is read where the
browser renders it, or over HTTP as the cockpit serves it, and the
projection where the launch was told to keep it.
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

from home_destination import fetch
from runs_destination import anchor, section


def percent(value: int) -> re.Pattern:
    """« 7 % » and not the end of « 27 % »."""
    return re.compile(rf"(?<!\d){value}\s%")


def prompts(reading: dict) -> dict[str, list[dict]]:
    """The prompts listed in the section « Prompts envoyés » of the detail,
    by their kind (« Prompt système », « Prompt utilisateur »), in the order
    of the page: each its title, whether it is open, its rendered text, its
    whole text, and its raw text as drawn (`raw`, '' when the raw text is
    not shown)."""
    found = {}
    listed = section(reading, "Prompts envoyés")
    if listed is None:
        return found
    for block in reading["anchors"]:
        if block["tag"] != "details" or listed["name"] not in block["chain"]:
            continue
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [block["name"]]), "")
        kind = next((name for name in ("Prompt système", "Prompt utilisateur") if title.startswith(name)), None)
        if kind is None:
            continue
        raw = next((a for a in reading["anchors"] if a["tag"] == "pre" and block["name"] in a["chain"]), None)
        found.setdefault(kind, []).append({
            "title": title, "open": block["open"], "text": block["text"], "content": block["content"],
            "raw": raw["text"] if raw and raw["drawn"] else "",
        })
    return found


def line(text: str) -> str:
    """A text on one line, as the browser draws a raw text that wraps."""
    return " ".join(text.split())


def raw_texts(address: str, path: str) -> list[str]:
    """The texts of the page at `path` the cockpit serves as they are, in
    <pre> elements: the raw prompts, each exactly as it was sent."""
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    return [html.unescape(found) for found in re.findall(r"<pre\b[^>]*>(.*?)</pre>", body, re.S)]


def served_text(address: str, path: str) -> str:
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    return html.unescape(body)


def head_says(reading: dict) -> str:
    found = anchor(reading, "inspector-head")
    return found["text"] if found else ""


def history_links(reading: dict) -> dict[str, str]:
    """The controls of the section « Sessions du job », by the session each
    names first: each its accessible name, what a person reads of it."""
    found = {}
    for control in reading.get("controls") or []:
        if control["tag"] == "a" and (control["anchor"] or "").startswith("session-history"):
            words = control["name"].split()
            if words:
                found[words[0]] = control["name"]
    return found


def wait_served(address: str, path: str, texts: tuple[str, ...], seconds: float = 30) -> list[str]:
    """The raw texts of the page at `path` once they hold each of `texts`,
    read again every half second for at most `seconds`; what they hold then
    if they never do."""
    deadline = time.monotonic() + seconds
    while True:
        sent = raw_texts(address, path)
        if all(text in sent for text in texts) or time.monotonic() > deadline:
            return sent
        time.sleep(0.5)


def projection(path: Path) -> list[dict]:
    """The records of the projection kept at `path`, one JSON object a
    line, as written."""
    return [json.loads(record) for record in path.read_text(encoding="utf-8").splitlines() if record.strip()]
