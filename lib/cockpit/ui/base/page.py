"""Renders the freshness headline (spec .64) over the variant D base.

Pure function of a :class:`~cockpit.core.readmodel.ReadModel` snapshot — no
I/O, so it is exercised directly by tests without an HTTP round trip.

T25 (af-tzk0s4, spec .69): "sur l'iPhone déconnecté, un bandeau «
Déconnecté du cockpit depuis HH:MM » au-dessus de tout et toutes les
valeurs grisées, afin de ne pas lire un écran figé comme actuel." The
cockpit's HTTP handler always answers when reached — a client that stops
receiving updates has lost the connection itself (Wi-Fi, tailnet, PC off),
not a single source, so this is the page's own liveness, built on top of
the same Freshness/staleness concept as every other value (GLOSSARY.md),
never a new parallel one: it is driven client-side by :data:`DISCONNECT_SCRIPT`
polling ``/api/status`` and comparing the elapsed time since the last
success against :data:`DISCONNECT_AFTER_SECONDS`, exactly the way a
source becomes STALE then UNKNOWN. :func:`render_disconnected_banner` is
the pure, testable half of that same decision, used directly by a server
that already knows it has gone quiet for some other reason.
"""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from cockpit.ui.base.tokens import CSS

PARIS = ZoneInfo("Europe/Paris")

# How long the client-side poller waits without a successful response
# before declaring itself disconnected (spec .67 uses 5 min for "cockpit
# injoignable" health reporting; this is the page's own, stricter
# liveness signal so the iPhone screen never looks current once stale).
DISCONNECT_AFTER_SECONDS = 30

BANNER_ID = "cockpit-disconnected-banner"
GREYED_CLASS = "cockpit-greyed"


def render_disconnected_banner(disconnected_since=None):
    """"Déconnecté du cockpit depuis HH:MM" (spec .69), or an empty,
    hidden placeholder when currently connected. ``disconnected_since``:
    epoch seconds of the last successful update, or ``None`` when the
    page has never gone quiet -- pure function, no clock of its own, so a
    test drives it with any fixed value."""
    if disconnected_since is None:
        return (
            '<div id="%s" class="cockpit-disconnected-banner" data-state="connected" hidden></div>\n'
            % BANNER_ID
        )
    when = datetime.fromtimestamp(disconnected_since, tz=PARIS).strftime("%H:%M")
    text = "Déconnecté du cockpit depuis %s" % when
    return (
        '<div id="%s" class="cockpit-disconnected-banner" data-state="disconnected">%s</div>\n'
        % (BANNER_ID, html.escape(text))
    )


# Client-side half of the same decision: polls the cockpit's own public
# GET /api/status, and on repeated failure or silence past
# DISCONNECT_AFTER_SECONDS shows the banner and greys every value on the
# page -- never per-field, this is "the page itself stopped receiving
# updates" (spec .69), not a source's own Freshness.
DISCONNECT_SCRIPT = """
<script>
(function () {
  var AFTER_MS = %d * 1000;
  var lastOkAt = Date.now();
  var banner = document.getElementById(%r);
  function setDisconnected(sinceMs) {
    if (!banner) return;
    var d = new Date(sinceMs);
    var hh = ("0" + d.getHours()).slice(-2);
    var mm = ("0" + d.getMinutes()).slice(-2);
    banner.textContent = "Déconnecté du cockpit depuis " + hh + ":" + mm;
    banner.setAttribute("data-state", "disconnected");
    banner.hidden = false;
    document.body.classList.add(%r);
  }
  function setConnected() {
    if (!banner) return;
    banner.hidden = true;
    banner.setAttribute("data-state", "connected");
    document.body.classList.remove(%r);
  }
  function poll() {
    fetch("/api/status", {cache: "no-store"})
      .then(function (r) {
        if (!r.ok) throw new Error("bad status");
        lastOkAt = Date.now();
        setConnected();
      })
      .catch(function () {
        if (Date.now() - lastOkAt > AFTER_MS) setDisconnected(lastOkAt);
      })
      .finally(function () {
        setTimeout(poll, 5000);
      });
  }
  poll();
})();
</script>
""" % (DISCONNECT_AFTER_SECONDS, BANNER_ID, GREYED_CLASS, GREYED_CLASS)


def render_home(
    headline_text,
    stale_rows,
    requests_section_html="",
    disconnected_since=None,
    extra_sections_html="",
    extra_css="",
):
    """``stale_rows``: the same names :meth:`ReadModel.stale_or_unknown`
    returns, each resolved to its display name and freshness state.
    ``requests_section_html`` (T12, af-is5e97): the pre-rendered "Ce qui
    t'attend" section HTML, injected below the freshness headline; the
    empty default keeps every caller that predates it unchanged.
    ``disconnected_since`` (T25, af-tzk0s4): rendered above everything —
    the default ``None`` keeps every existing caller unchanged, showing a
    hidden placeholder banner that the inline :data:`DISCONNECT_SCRIPT`
    takes over client-side.
    ``extra_sections_html``/``extra_css`` let later tickets (T16's health
    zone) append their own section without this module knowing about them."""
    all_fresh = not stale_rows
    items = "".join(
        '<li data-freshness="%s">%s</li>'
        % (html.escape(row["freshness"]), html.escape(row["display_name"]))
        for row in stale_rows
    )
    stale_list = (
        '<ul class="cockpit-stale-list">%s</ul>' % items if stale_rows else ""
    )
    banner = render_disconnected_banner(disconnected_since)
    return (
        "<!doctype html>\n"
        '<html lang="fr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Cockpit</title>\n"
        "<style>%s%s</style>\n"
        "</head>\n"
        '<body id="cockpit-body">\n'
        "%s"
        '<header class="cockpit-headline" data-ok="%s">%s</header>\n'
        "%s\n"
        "%s\n"
        "%s"
        "</body>\n"
        "</html>\n"
    ) % (
        CSS,
        extra_css,
        banner,
        "true" if all_fresh else "false",
        html.escape(headline_text),
        stale_list,
        requests_section_html + extra_sections_html,
        DISCONNECT_SCRIPT,
    )
