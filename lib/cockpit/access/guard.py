"""Operator Action request guard (spec af-oohx2x §"Accès et sécurité",
T13 AC1).

Threat model (spec .9): a local process on this host already has every
power there is, so a spoofed local header adds nothing new to guard
against. What the guard actually closes is a *remote* browser somewhere
else on the tailnet being tricked into firing a POST at the cockpit
(cross-site request forgery): a write is only ever performed when all of
these hold —

  * the HTTP method is POST,
  * the ``Origin`` header equals the cockpit's own origin,
  * the ``SESSION_COOKIE_NAME`` cookie handed out on every GET comes back
    with the exact token this server process generated at startup — a
    cross-site POST never carries a ``SameSite=Strict`` cookie at all, so
    its absence alone proves the browser did not get here from a page the
    cockpit served,
  * the ``Tailscale-User-Login`` header equals Benjamin's configured
    login — this is the *identity* check, separate from the three above:
    without it (or with a different login) the request is refused, never
    silently downgraded to a read (spec: "sinon lecture seule" describes
    ``GET /``, not an action endpoint).

Any single failure refuses the whole request without touching Beads —
the caller is expected to return without invoking the action at all.
"""
import secrets

SESSION_COOKIE_NAME = "cockpit_session"

REFUSED_METHOD = "method"
REFUSED_ORIGIN = "origin"
REFUSED_SESSION = "session"
REFUSED_IDENTITY = "identity"


def new_session_token():
    """One token per cockpit process lifetime (spec: no password, no
    per-request secret beyond what a local browser session already
    holds)."""
    return secrets.token_urlsafe(32)


def parse_cookie_header(value):
    cookies = {}
    if not value:
        return cookies
    for part in value.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, raw_value = part.partition("=")
        cookies[key.strip()] = raw_value.strip()
    return cookies


class GuardResult:
    def __init__(self, allowed, reason=""):
        self.allowed = allowed
        self.reason = reason

    def __bool__(self):
        return self.allowed


class ActionGuard:
    """Checked once per action POST. Reads only the request line and
    headers handed to it — never touches Beads, gc, or any other source."""

    def __init__(self, expected_login, allowed_origin, session_token):
        self._expected_login = expected_login
        self._allowed_origin = allowed_origin
        self._session_token = session_token

    def check(self, method, headers):
        """``headers``: anything with a ``.get(name, default)`` method
        (``email.message.Message``, as ``BaseHTTPRequestHandler.headers``
        is, or a plain dict in a test)."""
        if method != "POST":
            return GuardResult(False, REFUSED_METHOD)
        origin = headers.get("Origin", "") or ""
        if not self._allowed_origin or origin != self._allowed_origin:
            return GuardResult(False, REFUSED_ORIGIN)
        cookies = parse_cookie_header(headers.get("Cookie", ""))
        if not self._session_token or cookies.get(SESSION_COOKIE_NAME) != self._session_token:
            return GuardResult(False, REFUSED_SESSION)
        login = headers.get("Tailscale-User-Login", "") or ""
        if not login or login != self._expected_login:
            return GuardResult(False, REFUSED_IDENTITY)
        return GuardResult(True, "")


def session_cookie_header(token):
    """The ``Set-Cookie`` value handed out on every GET so a same-origin
    POST can prove it. ``HttpOnly`` is irrelevant to this cookie's job
    (it is never read by the page's own JS, only echoed by the browser)
    but is set anyway as the safer default."""
    return "%s=%s; Path=/; SameSite=Strict; HttpOnly" % (SESSION_COOKIE_NAME, token)
