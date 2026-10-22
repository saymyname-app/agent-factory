"""The trace of the sessions: what each session was sent and ran with,
collected where the supervisor shows it, kept in a private projection
(C2a, af-k2rbw1; Spec af-fgcw0d, user stories 130, 137, 138, 139 and 145).

    trace = SessionTrace(path)
    trace.collect(agents, transcript_of)   # at each reading of the sessions
    observed = trace.read()                # {session name: what was observed}

The supervisor lists the sessions it runs (``GET /v0/city/<city>/sessions``:
its provider, model, context, options, work directory, the bead it works)
and keeps the record the provider wrote of each one (``GET
/v0/city/<city>/session/<id>/transcript?format=raw``). Neither keeps a
session once it is gone: the projection does. It is a file of one JSON
record per line, written only by appending, private to the cockpit's user
(0600); a record already in it is not written again, so reading the same
sources again -- at each reading of the sessions, or a trace that replays
the records of an earlier session at its head -- adds nothing.

What a record keeps is chosen field by field, never copied whole:

- of a session: its identity (id, name, agent, template), its provider,
  model, effort and permission mode, its context observed and the window
  it is a part of, its work directory, when it was created, the bead it
  was working;
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
        # The keys written, and the projection as last read with the size of
        # the file it was read at: each reading of the sessions and each page
        # would otherwise read the whole file again.
        self._known = None
        self._read = (None, {})

    def collect(self, agents, transcript_of, clock=time.time):
        """Record what `agents` (the sessions the supervisor lists) say,
        and what `transcript_of(session id)` (the records of its provider,
        or None) says it was sent: a session once, then again while it
        runs, at most every TRANSCRIPT_EVERY_SECONDS. Returns what the
        projection holds."""
        records = []
        for item in agents or []:
            record = session_record(item)
            if record is None:
                continue
            records.append({"kind": "session", **record})
            name, now = record["session"], clock()
            last = self._read_at.get(name)
            if last is not None and (not item.get("running") or now - last < TRANSCRIPT_EVERY_SECONDS):
                continue
            self._read_at[name] = now
            try:
                provider_records = transcript_of(record.get("id") or name)
            except (OSError, ValueError):
                self._read_at.pop(name, None)
                continue
            prompts, tools = sent(provider_records, _epoch(record.get("created_at")))
            records += [{"kind": "prompt", "session": name, **prompt} for prompt in prompts]
            if tools:
                records.append({"kind": "tools", "session": name, "tools": tools})
        self._append(records)
        return self.read()

    def _append(self, records):
        with self._lock:
            if self._known is None:
                self._known = {line.get("key") for line in self._lines()}
            known = self._known
            fresh = []
            for record in records:
                key = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
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
        it called}}."""
        try:
            size = os.stat(self.path).st_size
        except FileNotFoundError:
            size = 0
        with self._lock:
            if self._read[0] == size:
                return json.loads(json.dumps(self._read[1]))
            lines = self._lines()
        found = {}
        for line in lines:
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
        with self._lock:
            self._read = (size, found)
        return json.loads(json.dumps(found))
