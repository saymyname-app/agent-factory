"""What the criterion tests of the events, controls, outputs and usage of a
job share (C2b, af-ofz29f; Spec af-fgcw0d, user stories 140 to 144 and
175, Testing Decisions 1, 5, 7 and 8). Not a test file: the criterion test
files of C2b load it, beside runs_destination.py and runs_trace.py.

- what a provider records of a session, in its own format, as the
  supervisor answers it (``GET …/session/<id>/transcript?format=raw``):
  Codex (`codex_*`, the records of the rollout files the installed Codex
  writes: a ``custom_tool_call`` and its ``custom_tool_call_output``
  sharing a ``call_id``, an ``event_msg`` ``token_count`` holding the
  usage of the session so far in ``total_token_usage``) and Claude Code
  (`claude_*`: an ``assistant`` record per block of a message, each
  repeating the ``usage`` of that message, a ``user`` record holding the
  ``tool_result`` of a ``tool_use``);
- `job_of`: the job of a dataset a case changes;
- what a detail of a job is read through: its controls (anchors ``gate``),
  its outputs (anchors ``output``), the table of its usage (anchor
  ``usage``) as the cockpit serves it, its tool calls among its events, a
  count of tokens as a person reads it.

The values a case verifies -- the records a session wrote, the attempts of
a job, the counts, times and durations expected -- are written in the case;
nothing here chooses one.

Nothing here reads the code of the cockpit: the page is read where the
browser renders it, or over HTTP as the cockpit serves it.
"""

from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser

from home_destination import fetch
from runs_destination import anchors, events, section

DAY = "2026-10-12"
# The kind of event a tool call is listed under, as the legend says it.
TOOL = "outil"


def utc(clock: str) -> str:
    """« 12:13:15.200 » of the day of the datasets, as a provider writes
    its timestamps (UTC)."""
    return f"{DAY}T{clock}Z"


def _seconds(clock: str) -> float:
    hours, minutes, seconds = clock.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clock(seconds: float) -> str:
    whole = int(seconds)
    millis = round((seconds - whole) * 1000)
    return "%02d:%02d:%02d.%03d" % (whole // 3600, whole % 3600 // 60, whole % 60, millis)


# --- Codex -----------------------------------------------------------------------

def codex_start(session: str, clock: str, system: str, user: str) -> list[dict]:
    """The records Codex writes when it starts a session: its meta (the
    system prompt it was given), its context, the user prompt it was
    typed."""
    return [
        {"timestamp": utc(clock), "type": "session_meta",
         "payload": {"id": session, "cwd": "/srv/synthetic/worktrees/recherche-dans-les-notes",
                     "originator": "codex_exec", "model_provider": "openai", "base_instructions": {"text": system}}},
        {"timestamp": utc(clock), "type": "turn_context",
         "payload": {"cwd": "/srv/synthetic/worktrees/recherche-dans-les-notes", "approval_policy": "never",
                     "sandbox_policy": {"type": "workspace-write"}, "model": "gpt-6.1-sol"}},
        {"timestamp": utc(clock), "type": "event_msg",
         "payload": {"type": "item_completed",
                     "item": {"type": "UserMessage", "content": [{"type": "text", "text": user}]}}},
    ]


def codex_tool(call: str, clock: str, seconds: float, name: str, given: str, printed: str = "ok") -> list[dict]:
    """A tool `name` Codex called at `clock` with `given`, and what it
    printed `seconds` later."""
    return [
        {"timestamp": utc(clock), "type": "response_item",
         "payload": {"type": "custom_tool_call", "status": "completed", "call_id": call, "name": name,
                     "input": given}},
        {"timestamp": utc(_clock(_seconds(clock) + seconds)), "type": "response_item",
         "payload": {"type": "custom_tool_call_output", "call_id": call,
                     "output": [{"type": "input_text", "text": printed}]}},
    ]


def codex_usage(points: list[tuple[str, dict]]) -> list[dict]:
    """The ``token_count`` records of a session: at each clock of `points`,
    the usage of the session so far as Codex counts it (``input_tokens``,
    of which ``cached_input_tokens``; ``output_tokens``, of which
    ``reasoning_output_tokens``; ``cache_write_input_tokens``;
    ``total_tokens``), and what the turn since the previous one used."""
    records, before = [], {}
    for clock, total in points:
        last = {key: value - before.get(key, 0) for key, value in total.items()}
        records.append({"timestamp": utc(clock), "type": "event_msg",
                        "payload": {"type": "token_count",
                                    "info": {"total_token_usage": dict(total), "last_token_usage": last,
                                             "model_context_window": 258400},
                                    "rate_limits": {"limit_id": "codex", "primary": {"used_percent": 26.0}}}})
        before = total
    return records


def tokens(given: int, cached: int, printed: int, reasoning: int, cache_written: int = 0) -> dict:
    """A ``total_token_usage`` of Codex: its total is what it was given
    and what it printed, the cache read and the reasoning being parts of
    those."""
    return {"input_tokens": given, "cached_input_tokens": cached, "cache_write_input_tokens": cache_written,
            "output_tokens": printed, "reasoning_output_tokens": reasoning, "total_tokens": given + printed}


# --- Claude Code -----------------------------------------------------------------

def claude_user(session: str, clock: str, text: str) -> dict:
    return {"type": "user", "sessionId": session, "timestamp": utc(clock), "uuid": f"{session}-{clock}",
            "message": {"role": "user", "content": text}}


def claude_message(session: str, clock: str, message: str, usage: dict, blocks: list[dict]) -> list[dict]:
    """A message of the model, as Claude Code records it: one ``assistant``
    record per block, a second apart, each repeating the ``usage`` of the
    whole message."""
    start = _seconds(clock)
    return [{"type": "assistant", "sessionId": session, "timestamp": utc(_clock(start + number)),
             "uuid": f"{message}-{number}",
             "message": {"id": message, "role": "assistant", "model": "claude-opus-5-5", "usage": dict(usage),
                         "content": [block]}}
            for number, block in enumerate(blocks)]


def claude_result(session: str, clock: str, tool_use: str, printed: str = "ok") -> dict:
    return {"type": "user", "sessionId": session, "timestamp": utc(clock), "uuid": f"{tool_use}-result",
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use,
                                                     "content": printed}]}}


# --- a dataset -------------------------------------------------------------------

def job_of(dataset: dict, run: str, job: str) -> dict:
    """The job `job` of the run `run` of `dataset`, to change in place."""
    found = next(item for item in dataset["fixtures"]["runs"] if item["id"] == run)
    return next(item for item in found["jobs"] if item["id"] == job)


# --- a reading -------------------------------------------------------------------

def _titled(reading: dict, name: str) -> list[dict]:
    found = []
    for block in anchors(reading, name):
        if block["tag"] != "details":
            continue
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [block["name"]]), "")
        found.append({"title": " ".join(title.split()), "content": " ".join(block["content"].split()),
                      "open": block["open"], "chain": block["chain"]})
    return found


def gates(reading: dict) -> list[dict]:
    """The controls listed in the section « Contrôles » of the detail, in
    the order of the page: each its title, its whole text, whether it is
    open."""
    listed = section(reading, "Contrôles")
    if listed is None:
        return []
    return [gate for gate in _titled(reading, "gate") if listed["name"] in gate["chain"]]


def outputs(reading: dict) -> list[dict]:
    """The outputs listed in the section « Sorties » of the detail."""
    listed = section(reading, "Sorties")
    if listed is None:
        return []
    return [output for output in _titled(reading, "output") if listed["name"] in output["chain"]]


def tool_calls(reading: dict) -> list[dict]:
    """The events listed as tool calls beside the detail, in the order of
    the page (see runs_destination.events)."""
    return [event for event in events(reading) if event["kind"].strip().lower().startswith(TOOL)]


def number(value: int) -> re.Pattern:
    """`value` as a person reads a count of tokens: its digits, grouped by
    three or not (« 54 537 », « 54537 »), and no digit around it."""
    digits = str(value)
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return re.compile(r"(?<![\d,.])" + r"[\s  ]?".join(groups) + r"(?![\d]|[\s  ]\d)")


def duration(said: str) -> re.Pattern:
    """A duration in seconds as the page writes it, « 0,64 s »."""
    return re.compile(rf"(?<![\d,]){re.escape(said)}\s?s\b")


class _Table(HTMLParser):
    """The rows of the first table carrying data-anchor="usage"."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth, self.rows, self.cell = 0, [], None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.depth or (dict(attrs).get("data-anchor") == "usage" and not self.rows):
                self.depth += 1
        elif self.depth and tag == "tr":
            self.rows.append([])
        elif self.depth and tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth and tag in ("td", "th") and self.cell is not None and self.rows:
            self.rows[-1].append(" ".join("".join(self.cell).split()))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def usage_table(address: str, path: str) -> dict[str, list[str]]:
    """The table of the usage of the job the page at `path` details, as the
    cockpit serves it: by the first cell of each row (« Entrée », « Total »,
    …), the cells after it; empty when the page draws no such table."""
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    table = _Table()
    table.feed(body)
    return {row[0]: row[1:] for row in table.rows if row}


def served(address: str, path: str) -> str:
    code, _, body = fetch(address + path)
    assert code == 200, f"{path} answered {code}"
    return html.unescape(body)


def wait_page(address: str, path: str, texts: tuple[str, ...], seconds: float = 40) -> str:
    """The page at `path` once it holds each of `texts`, read again every
    half second for at most `seconds`; what it holds then if it never
    does."""
    deadline = time.monotonic() + seconds
    while True:
        page = served(address, path)
        if all(text in page for text in texts) or time.monotonic() > deadline:
            return page
        time.sleep(0.5)
