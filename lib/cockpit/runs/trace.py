"""The trace of the sessions: what each session was sent and ran with,
collected from the supervisor that sends them, kept in a private projection
(C2a, af-k2rbw1; Spec af-fgcw0d, user stories 130, 137, 138, 139 and 145).

    trace = SessionTrace(path)
    trace.collect(agents, supervisor)   # at each reading of the sessions
    observed = trace.read()             # {session name: what was observed}

The supervisor is what sends the sessions their work: it wakes a session,
sends it its prompts, and stops it. It records each of those moments in its
log (``session.woke``, ``session.stopped``: ``supervisor.session_events``),
keeps each session it sent (``supervisor.session``: its provider, model,
context, options, work directory, the bead it works) and the record its
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
  was working; when the supervisor woke it and stopped it;
- of what it was sent: the system prompt (Codex records it,
  ``session_meta.base_instructions``; Claude Code does not, it is then not
  collected), each user prompt (the message the provider records as typed
  -- Codex ``event_msg`` UserMessage, Claude Code a ``user`` record of
  text), each with its version (``sha256:`` and the first twelve digits of
  the digest of its exact text), and the names of the tools it called.

Everything else the provider recorded -- what tools printed and were
given, reasoning, environment, tokens -- is never read into a record. A
record written before the session was created belongs to an earlier
session the trace replays, and is not what this one was sent.
"""
import hashlib
import json
import os
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
LOGGED = {"session.woke": "woke", "session.stopped": "stopped"}


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
            if moment["at"] is not None:
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
        it called; "ended_at": when the supervisor stopped it, if it did and
        did not wake it again since, else None}}."""
        try:
            size = os.stat(self.path).st_size
        except FileNotFoundError:
            size = 0
        with self._lock:
            if self._read[0] == size:
                return json.loads(json.dumps(self._read[1]))
            lines = self._lines()
        found, moments = {}, {}
        for line in lines:
            if line.get("kind") in ("woke", "stopped") and line.get("id"):
                moments.setdefault(line["id"], []).append((line.get("at") or 0, line["kind"]))
                continue
            name = line.get("session")
            if not name:
                continue
            seen = found.setdefault(name, {"session": name, "prompts": [], "tools": [], "beads": []})
            if line.get("kind") == "session":
                seen.update({key: value for key, value in line.items() if key not in ("key", "kind")})
                if line.get("active_bead") and line["active_bead"] not in seen["beads"]:
                    seen["beads"].append(line["active_bead"])
            elif line.get("kind") == "prompt":
                if all(p["version"] != line.get("version") or p["role"] != line.get("role") for p in seen["prompts"]):
                    seen["prompts"].append({key: line.get(key) for key in ("role", "text", "version", "at")})
            elif line.get("kind") == "tools":
                seen["tools"] = list(line.get("tools") or [])
        for seen in found.values():
            seen["prompts"].sort(key=lambda p: (p["role"] != SYSTEM, p.get("at") or 0))
            last = max(moments.get(seen.get("id") or seen["session"]) or [(0, None)])
            seen["ended_at"] = last[0] if last[1] == "stopped" else None
        with self._lock:
            self._read = (size, found)
        return json.loads(json.dumps(found))
