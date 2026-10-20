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
# « name=value » or « name: value », the value quoted or up to a space or a
# separator.
FIELD = re.compile(r"""(?P<name>[A-Za-z][\w.-]*)(?P<sep>\s*[=:]\s*)(?P<value>"[^"]*"|'[^']*'|[^\s,;&]+)""")
SECRET_NAMES = re.compile(
    r"(?i)(?:^|[_.-])(?:token|secret|password|passwd|pwd|api[_-]?key|apikey|private[_-]?key|credentials?"
    r"|authorization|auth|cookie|session[_-]?key)$"
)
REASONING_NAMES = re.compile(r"(?i)^(?:reasoning|thinking)$")


def _field(match):
    name = match.group("name")
    if SECRET_NAMES.search(name):
        return "%s%s%s" % (name, match.group("sep"), SECRET)
    if REASONING_NAMES.match(name):
        return "%s%s%s" % (name, match.group("sep"), REASONING)
    return match.group(0)


def redact(text):
    """``text`` without its secrets and its private reasoning; anything
    that is not a string is returned as it is."""
    if not isinstance(text, str) or not text:
        return text
    text = BEARER.sub(lambda m: "%s %s" % (m.group(1), SECRET), text)
    text = FIELD.sub(_field, text)
    return TOKEN_SHAPES.sub(SECRET, text)
