"""The trace of the sessions: what each session was sent and ran with,
collected from the supervisor that sends them, kept in a private projection
(C2a, af-k2rbw1; Spec af-fgcw0d, user stories 130, 137, 138, 139 and 145).

    trace = SessionTrace(path)
    trace.collect(agents, supervisor)   # at each reading of the sessions
    observed = trace.read()             # {session name: what was observed}

The supervisor is what sends the sessions their work: it wakes a session,
sends it its prompts, and stops it. It records each of those moments in its
log (``session.woke``, ``session.stopped``, and ``execution.step_started``
for each bead a session took: ``supervisor.session_events``), keeps each
session it sent (``supervisor.session``: its provider, model, context,
options, work directory, the bead it works while it runs -- none once it
stopped, so the log alone says the bead of a session past) and the record its
provider wrote of it (``supervisor.transcript``) -- also once the session
stopped and it no longer lists it among those it runs (the ``agents`` of a
reading). The collection follows that log: a session that woke and stopped
between two readings is read from it, and a session that stopped is read
once more, so what it was sent after an earlier reading is kept. It adds
no reading of its own: it runs at each reading of the sessions.

The projection keeps what the supervisor does not keep for ever. It is a
file of one JSON record per line, written only by appending, private to the
cockpit's user (0600); a record already in it is not written again, so
reading the same sources again -- at each reading of the sessions, another
cockpit reading the log from its start, or a trace that replays the
records of an earlier session at its head -- adds nothing.

What a record keeps is chosen field by field, never copied whole:

- of a session: its identity (id, name, agent, template), its provider,
  model, effort and permission mode, its context observed and the window
  it is a part of, its work directory, when it was created, the bead it
  was working; when the supervisor woke it and stopped it, and each bead
  its log says the session took;
- of what it was sent: the system prompt (Codex records it,
  ``session_meta.base_instructions``; Claude Code does not, it is then not
  collected), each user prompt (the message the provider records as typed
  -- Codex ``event_msg`` UserMessage, Claude Code a ``user`` record of
  text), each with its version (``sha256:`` and the first twelve digits of
  the digest of its exact text), and the names of the tools it called.

- of what it did (C2b, af-ofz29f): each tool it called -- its name, what
  it was given, credentials masked (:func:`masked`), when, and how long
  until what the tool printed was recorded (Codex a ``custom_tool_call``
  or ``function_call`` and its output sharing a ``call_id``; Claude Code a
  ``tool_use`` and the ``tool_result`` naming it) --, and its usage as the
  provider counts it, so far, at each moment it counted it: Codex its
  ``token_count`` (``total_token_usage``: what it was given, of which read
  from the cache; what it printed, of which reasoning; written to the
  cache; its total), Claude Code the ``usage`` of each message, counted
  once however many records repeat it (what it was given, written to and
  read from the cache, printed, of which thinking; its total, these
  added, as none is a part of another).

Everything else the provider recorded -- what tools printed, reasoning,
environment -- is never read into a record. A record written before the
session was created belongs to an earlier session the trace replays, and
is not what this one was sent nor did.
"""
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone

# What a session record keeps, as the supervisor lists it.
# What changes at each reading (when it was last active, whether it runs)
# is not kept: the projection would grow at each one.
SESSION_FIELDS = ("id", "name", "session_name", "agent_name", "template", "provider", "model", "context_pct",
                  "context_window", "work_dir", "created_at", "active_bead")
# Of its options, the ones that say how it runs.
OPTION_FIELDS = ("effort", "permission_mode")
# A session at work is read again at most this often: what it was sent
# grows while it runs.
TRANSCRIPT_EVERY_SECONDS = 60
SYSTEM, USER = "system", "user"
# The moments of the log of the supervisor a record keeps.
LOGGED = {"session.woke": "woke", "session.stopped": "stopped", "execution.step_started": "started"}


# The categories of a usage, as the page names them: what the session was
# given, read from and written to the cache, printed, of which reasoning,
# and the total its provider counts.
USAGE_KEYS = ("input", "cache_read", "cache_write", "output", "reasoning", "total")
# What a tool was given is kept up to this many characters.
CALL_INPUT_CHARACTERS = 2000
# What a credential looks like where a tool was given it: a token of a
# known service, a secret after a name that says so, the password of an
# address. Each is replaced by MASK, what names it kept.
CREDENTIALS = (
    re.compile(r"()\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{12,}"
               r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|glpat-[A-Za-z0-9_-]{16,})"),
    re.compile(r"(?i)(\b[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Z0-9_]*\s*[=:]\s*)[^\s\"']+"),
    re.compile(r"(?i)(\bauthorization:\s*(?:bearer|basic|token)\s+)[^\s\"']+"),
    re.compile(r"(://)[^/\s@]+@"),
)
MASK = "•••"


def masked(text):
    """`text` with every credential it shows replaced by MASK."""
    for pattern in CREDENTIALS:
        text = pattern.sub(lambda found: found.group(1) + MASK + ("@" if found.group(0).endswith("@") else ""), text)
    return text


def version(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _epoch(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).timestamp()


def session_record(item):
    """What a session the supervisor lists says of it, field by field;
    None for an item that is not a session."""
    if not isinstance(item, dict) or not (item.get("session_name") or item.get("name") or item.get("id")):
        return None
    record = {key: item[key] for key in SESSION_FIELDS if item.get(key) not in (None, "")}
    options = item.get("options") if isinstance(item.get("options"), dict) else {}
    record.update({key: options[key] for key in OPTION_FIELDS if isinstance(options.get(key), str) and options[key]})
    record["session"] = item.get("session_name") or item.get("name") or item.get("id")
    return record


def _texts(content):
    """The text parts of a message, joined; None when it holds anything else
    (a tool result, an image)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    texts = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") not in ("text", "input_text"):
            return None
        texts.append(part.get("text") or "")
    return "".join(texts) if texts else None


def sent(records, created_at=None):
    """What the records of a provider say a session was sent: (prompts,
    tools) -- each prompt {role, text, version, at} in the order it was
    sent, the names of the tools it called in the order of their first
    call. Records before `created_at` (epoch) are those of an earlier
    session it replays."""
    prompts, tools = [], []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        at = _epoch(record.get("timestamp"))
        if created_at is not None and at is not None and at < created_at:
            continue
        kind, payload = record.get("type"), record.get("payload") if isinstance(record.get("payload"), dict) else {}
        found = None
        # Codex: its base instructions, the messages typed, the tools called.
        if kind == "session_meta":
            base = payload.get("base_instructions")
            text = base.get("text") if isinstance(base, dict) else base if isinstance(base, str) else None
            found = (SYSTEM, text) if text else None
        elif kind == "event_msg" and payload.get("type") == "item_completed":
            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
            if item.get("type") == "UserMessage":
                text = _texts(item.get("content"))
                found = (USER, text) if text else None
        elif kind == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
            if isinstance(payload.get("name"), str) and payload["name"] not in tools:
                tools.append(payload["name"])
        # Claude Code: a user record of text (not a tool result, not a
        # message of its own), the tools an assistant record calls.
        elif kind == "user" and not record.get("isMeta") and isinstance(record.get("message"), dict):
            text = _texts(record["message"].get("content"))
            found = (USER, text) if text else None
        elif kind == "assistant" and isinstance(record.get("message"), dict):
            for part in record["message"].get("content") or []:
                if isinstance(part, dict) and part.get("type") == "tool_use" and isinstance(part.get("name"), str) \
                        and part["name"] not in tools:
                    tools.append(part["name"])
        if found:
            role, text = found
            prompts.append({"role": role, "text": text, "version": version(text), "at": at})
    return prompts, tools


def _given(value):
    """What a tool was given, as one text, credentials masked."""
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict) and len(value) == 1 and isinstance(next(iter(value.values())), str):
        text = next(iter(value.values()))
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return masked(text)[:CALL_INPUT_CHARACTERS]


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _counts(said, fields):
    found = {key: _count(said.get(field)) for key, field in fields}
    return {key: value for key, value in found.items() if value is not None}


CODEX_USAGE = (("input", "input_tokens"), ("cache_read", "cached_input_tokens"),
               ("cache_write", "cache_write_input_tokens"), ("output", "output_tokens"),
               ("reasoning", "reasoning_output_tokens"), ("total", "total_tokens"))
CLAUDE_USAGE = (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens"))


def done(records, created_at=None):
    """What the records of a provider say a session did: (calls, usage) --
    each tool call {call, tool, input, at, seconds} in the order made
    (``seconds`` None while nothing the tool printed is recorded); the
    usage of the session so far at each moment its provider counted it
    {at, provider, counts}, counts by USAGE_KEYS, those the provider gives.
    Records before `created_at` (epoch) are those of an earlier session it
    replays."""
    calls, ended, usage, messages = {}, {}, [], {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        at = _epoch(record.get("timestamp"))
        if at is None or (created_at is not None and at < created_at):
            continue
        kind, payload = record.get("type"), record.get("payload") if isinstance(record.get("payload"), dict) else {}
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        # Codex: a tool called, what it printed, a count of the usage.
        if kind == "response_item" and payload.get("type") in ("custom_tool_call", "function_call"):
            if isinstance(payload.get("call_id"), str) and isinstance(payload.get("name"), str):
                given = payload.get("input") if payload["type"] == "custom_tool_call" else payload.get("arguments")
                calls.setdefault(payload["call_id"], {"call": payload["call_id"], "tool": payload["name"],
                                                      "input": _given(given if given is not None else ""), "at": at})
        elif kind == "response_item" and payload.get("type") in ("custom_tool_call_output", "function_call_output"):
            if isinstance(payload.get("call_id"), str):
                ended.setdefault(payload["call_id"], at)
        elif kind == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            total = info.get("total_token_usage")
            counts = _counts(total, CODEX_USAGE) if isinstance(total, dict) else {}
            if "total" in counts:
                usage.append({"at": at, "provider": "codex", "counts": counts})
        # Claude Code: a message of the model -- the tools it calls, its
        # usage, repeated on each of its records --, the result of a tool.
        elif kind == "assistant":
            for part in message.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "tool_use" and isinstance(part.get("id"), str) \
                        and isinstance(part.get("name"), str):
                    calls.setdefault(part["id"], {"call": part["id"], "tool": part["name"],
                                                  "input": _given(part.get("input")), "at": at})
            said = message.get("usage")
            if not isinstance(said, dict) or not isinstance(message.get("id"), str) or message["id"] in messages:
                continue
            counts = _counts(said, CLAUDE_USAGE)
            details = said.get("output_tokens_details")
            thinking = _count(details.get("thinking_tokens")) if isinstance(details, dict) else None
            if thinking is not None:
                counts["reasoning"] = thinking
            messages[message["id"]] = counts
            sums = {}
            for one in messages.values():
                for key, value in one.items():
                    sums[key] = sums.get(key, 0) + value
            sums["total"] = sum(sums.get(key, 0) for key, _ in CLAUDE_USAGE)
            usage.append({"at": at, "provider": "claude", "counts": sums})
        elif kind == "user" and isinstance(message.get("content"), list):
            for part in message["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result" and isinstance(part.get("tool_use_id"), str):
                    ended.setdefault(part["tool_use_id"], at)
    found = []
    for call in sorted(calls.values(), key=lambda call: call["at"]):
        end = ended.get(call["call"])
        found.append(dict(call, seconds=round(max(0.0, end - call["at"]), 3) if end is not None else None))
    return found, usage


class SessionTrace:
    """The projection at `path` (created private on first write)."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._read_at = {}
        # The last event of the log of the supervisor collected: None until
        # the first collection, which reads the log of the last week.
        self._after = None
        # The keys written, and the projection as last read with the size of
        # the file it was read at: each reading of the sessions and each page
        # would otherwise read the whole file again.
        self._known = None
        self._read = (None, {})

    def collect(self, agents, supervisor, clock=time.time):
        """Record what `agents` (the sessions the supervisor lists) say,
        the moments the log of `supervisor` woke and stopped a session since
        the last collection, each session that log names, and what each
        session was sent (`supervisor.transcript(session id)`, the records
        of its provider, or None): a session the first time it is seen,
        again while it runs, at most every TRANSCRIPT_EVERY_SECONDS, and once
        more when it stopped. Returns what the projection holds."""
        records, listed, logged, failed, after = [], {}, {}, set(), self._after
        for item in agents or []:
            record = session_record(item)
            if record is not None:
                listed[record.get("id") or record["session"]] = (item, record)
        try:
            events = supervisor.session_events(self._after)
        except (OSError, ValueError, KeyError, TypeError):
            events = []
        for event in events:
            self._after = max(self._after or 0, event["seq"])
            moment = {"kind": LOGGED[event["type"]], "id": event["session_id"], "at": _epoch(event["ts"])}
            if moment["kind"] == "started":
                moment["bead"] = event.get("bead")
            if moment["at"] is not None and (moment["kind"] != "started" or moment["bead"]):
                logged.setdefault(event["session_id"], []).append(moment)
        # A moment the projection already holds was collected with its
        # session (another cockpit read the same log): it is not read again.
        fresh = self._fresh([moment for moments in logged.values() for moment in moments])
        stopped = {moment["id"] for moment in fresh if moment["kind"] == "stopped"}
        for session_id in {moment["id"] for moment in fresh} - set(listed):
            try:
                kept = supervisor.session(session_id)
            except (OSError, ValueError):
                failed.add(session_id)
                continue
            record = session_record(kept)
            if record is not None:
                listed[session_id] = (kept, record)
        for session_id, (item, record) in listed.items():
            records.append({"kind": "session", **record})
            name, now = record["session"], clock()
            last = self._read_at.get(name)
            if last is not None and session_id not in stopped and (
                    not item.get("running") or now - last < TRANSCRIPT_EVERY_SECONDS):
                continue
            self._read_at[name] = now
            try:
                provider_records = supervisor.transcript(record.get("id") or name)
            except (OSError, ValueError):
                self._read_at.pop(name, None)
                failed.add(session_id)
                continue
            prompts, tools = sent(provider_records, _epoch(record.get("created_at")))
            records += [{"kind": "prompt", "session": name, **prompt} for prompt in prompts]
            if tools:
                records.append({"kind": "tools", "session": name, "tools": tools})
            calls, usage = done(provider_records, _epoch(record.get("created_at")))
            records += [{"kind": "call", "session": name, **call} for call in calls]
            records += [{"kind": "usage", "session": name, **point} for point in usage]
        # A session that could not be read keeps its moments out of the
        # projection, and the log is read again from where it was: the next
        # collection reads it once more.
        records += [moment for moment in fresh if moment["id"] not in failed]
        if failed & {moment["id"] for moment in fresh}:
            self._after = after
        self._append(records)
        return self.read()

    @staticmethod
    def _key(record):
        return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _fresh(self, records):
        """Those of `records` the projection does not hold yet."""
        with self._lock:
            if self._known is None:
                self._known = {line.get("key") for line in self._lines()}
            return [record for record in records if self._key(record) not in self._known]

    def _append(self, records):
        with self._lock:
            if self._known is None:
                self._known = {line.get("key") for line in self._lines()}
            known = self._known
            fresh = []
            for record in records:
                key = self._key(record)
                if key not in known:
                    known.add(key)
                    fresh.append(json.dumps({"key": key, **record}, ensure_ascii=False))
            if not fresh:
                return
            os.makedirs(os.path.dirname(self.path) or ".", mode=0o700, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as out:
                out.write("\n".join(fresh) + "\n")

    def _lines(self):
        try:
            with open(self.path, encoding="utf-8") as kept:
                lines = []
                for line in kept:
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(value, dict):
                        lines.append(value)
                return lines
        except FileNotFoundError:
            return []

    def read(self):
        """{session name: {the fields observed of it, the latest one of each
        kept; "beads": every bead it was seen working; "prompts": what it
        was sent, each version once, in the order sent; "tools": the tools
        it called; "calls": each tool call once, in the order made, with how
        long it lasted once known; "usage": its usage so far at each moment
        its provider counted it, in order; "ended_at": when the supervisor
        stopped it, if it did and did not wake it again since, else None}}."""
        try:
            size = os.stat(self.path).st_size
        except FileNotFoundError:
            size = 0
        with self._lock:
            if self._read[0] == size:
                return json.loads(json.dumps(self._read[1]))
            lines = self._lines()
        found, moments, took = {}, {}, {}
        for line in lines:
            if line.get("kind") in ("woke", "stopped") and line.get("id"):
                moments.setdefault(line["id"], []).append((line.get("at") or 0, line["kind"]))
                continue
            if line.get("kind") == "started" and line.get("id"):
                took.setdefault(line["id"], []).append(line.get("bead"))
                continue
            name = line.get("session")
            if not name:
                continue
            seen = found.setdefault(name, {"session": name, "prompts": [], "tools": [], "beads": [], "calls": [],
                                           "usage": []})
            if line.get("kind") == "session":
                seen.update({key: value for key, value in line.items() if key not in ("key", "kind")})
                if line.get("active_bead") and line["active_bead"] not in seen["beads"]:
                    seen["beads"].append(line["active_bead"])
            elif line.get("kind") == "prompt":
                if all(p["version"] != line.get("version") or p["role"] != line.get("role") for p in seen["prompts"]):
                    seen["prompts"].append({key: line.get(key) for key in ("role", "text", "version", "at")})
            elif line.get("kind") == "tools":
                seen["tools"] = list(line.get("tools") or [])
            elif line.get("kind") == "call" and line.get("call"):
                call = {key: line.get(key) for key in ("call", "tool", "input", "at", "seconds")}
                known = next((c for c in seen["calls"] if c["call"] == call["call"]), None)
                if known is None:
                    seen["calls"].append(call)
                elif known["seconds"] is None:
                    known.update(call)
            elif line.get("kind") == "usage" and isinstance(line.get("counts"), dict):
                point = {key: line.get(key) for key in ("at", "provider", "counts")}
                if point not in seen["usage"]:
                    seen["usage"].append(point)
        for seen in found.values():
            seen["calls"].sort(key=lambda c: (c.get("at") or 0, c["call"]))
            seen["usage"].sort(key=lambda u: (u.get("at") or 0, u["counts"].get("total") or 0))
            seen["beads"] += [bead for bead in took.get(seen.get("id") or seen["session"]) or []
                              if bead and bead not in seen["beads"]]
            seen["prompts"].sort(key=lambda p: (p["role"] != SYSTEM, p.get("at") or 0))
            last = max(moments.get(seen.get("id") or seen["session"]) or [(0, None)])
            seen["ended_at"] = last[0] if last[1] == "stopped" else None
        with self._lock:
            self._read = (size, found)
        return json.loads(json.dumps(found))
