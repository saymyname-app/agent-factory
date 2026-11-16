"""What a raw text the cockpit shows never carries (F, af-njwz8v; Spec
af-fgcw0d, user story 158 and the Journal decision: « Ne pas exposer secrets
ni raisonnement privé dans le brut »).

    redact("ci.completed token=ghp_…")  ->  "ci.completed token=[secret masqué]"

A raw event is shown as its producer wrote it, with two exceptions, both
replaced in place so that the rest stays readable as received:

  * a secret: a token of a known shape (GitHub, the model providers, Slack,
    a ``Bearer`` value), and the value of any field named as one (``token``,
    ``secret``, ``password``, ``api_key``, ``authorization``…);
  * a private reasoning: the value of a field ``reasoning`` or ``thinking``.

A field is ``name=value`` or ``name: value``, its name quoted or not, as
in a JSON object. Its value is a quoted text (escapes included), an object
or a list (to its closing bracket), or else the word that follows -- but
an unquoted reasoning runs to the end of its line, since its words are
not one word.

Pure code, applied where the cockpit reads its sources (cockpit.ui.journal
.entries), so nothing it serves -- a page, a JSON answer -- holds one.
"""
import re

SECRET = "[secret masqué]"
REASONING = "[raisonnement privé retiré]"

# Tokens recognised by their shape, wherever they are written.
TOKEN_SHAPES = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:ant-)?[A-Za-z0-9_-]{16,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})"
)
BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")
# A field's name, quoted or not, and its separator; its value is read by
# _value_end.
FIELD = re.compile(r"""(?P<quote>["']?)(?P<name>[A-Za-z][\w.-]*)(?P=quote)(?P<sep>\s*[=:]\s*)""")
WORD_END = re.compile(r"[\s,;&}\]]|$")
SECRET_NAMES = re.compile(
    r"(?i)(?:^|[_.-])(?:token|secret|password|passwd|pwd|api[_-]?key|apikey|private[_-]?key|credentials?"
    r"|authorization|auth|cookie|session[_-]?key)$"
)
REASONING_NAMES = re.compile(r"(?i)^(?:reasoning|thinking)$")
CLOSING = {"{": "}", "[": "]"}


def _string_end(text, start):
    """The index after the quoted text that opens at ``start``."""
    quote, index = text[start], start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index + 1
        index += 1
    return len(text)


def _value_end(text, start, to_line_end):
    """The index after the value that starts at ``start``."""
    if start >= len(text):
        return start
    opening = text[start]
    if opening in "\"'":
        return _string_end(text, start)
    if opening in CLOSING:
        depth, index = [], start
        while index < len(text):
            char = text[index]
            if char in "\"'":
                index = _string_end(text, index)
                continue
            if char in CLOSING:
                depth.append(CLOSING[char])
            elif depth and char == depth[-1]:
                depth.pop()
                if not depth:
                    return index + 1
            index += 1
        return len(text)
    if to_line_end:
        end = text.find("\n", start)
        return len(text) if end == -1 else end
    return WORD_END.search(text, start).start()


def _fields(text):
    """``text`` with the value of each secret or reasoning field replaced."""
    out, index = [], 0
    while True:
        match = FIELD.search(text, index)
        if not match:
            out.append(text[index:])
            return "".join(out)
        name = match.group("name")
        mask = SECRET if SECRET_NAMES.search(name) else REASONING if REASONING_NAMES.match(name) else None
        if mask is None:
            # Not one: what follows its name is read again, a field
            # inside its value included.
            out.append(text[index:match.end("name")])
            index = match.end("name")
            continue
        start = match.end()
        end = _value_end(text, start, to_line_end=mask == REASONING)
        quoted = text[start:start + 1] in ("\"", "'") and end > start
        out.append(text[index:start])
        out.append("%s%s%s" % (text[start], mask, text[start]) if quoted else mask)
        index = end


def redact(text):
    """``text`` without its secrets and its private reasoning; anything
    that is not a string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    text = BEARER.sub(lambda m: "%s %s" % (m.group(1), SECRET), text)
    text = _fields(text)
    return TOKEN_SHAPES.sub(SECRET, text)
