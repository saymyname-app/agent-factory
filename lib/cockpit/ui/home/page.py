"""Renders "Ce qui t'attend" (spec af-oohx2x §"Accueil", §"Demandes
opérateur"; CONTEXT.md "Operator Request"). Pure function of a list of
:class:`~cockpit.requests.model.OperatorRequest` plus the beads source's
own freshness — no I/O, exercised directly as well as through the HTTP
seam (ui/base/page.py's ``render_home`` embeds this section's HTML).
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.requests.model import URGENT

SECTION_TITLE = "Ce qui t'attend"
EMPTY_TEXT = "Rien ne t'attend — vérifié à %s"
UNKNOWN_TEXT = "Inconnu : illisible depuis %s"
UNKNOWN_TEXT_NO_TIME = "Inconnu : illisible depuis toujours"


def _hhmm(epoch):
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def render_requests_section(requests, verified_at=None, source_unknown=False, last_known_at=None):
    """``requests``: sorted list from :func:`cockpit.requests.builder.build_requests`.
    ``source_unknown``: True when the beads source's own Freshness is
    "unknown" (spec .16) — the whole section then shows the illisible
    message instead of any list, stale or not."""
    if source_unknown:
        since = _hhmm(last_known_at)
        body = html.escape(UNKNOWN_TEXT % since if since else UNKNOWN_TEXT_NO_TIME)
        return (
            '<section class="cockpit-requests" data-state="unknown">'
            '<h2>%s</h2><p class="cockpit-requests-status">%s</p></section>\n'
        ) % (html.escape(SECTION_TITLE), body)

    if not requests:
        when = _hhmm(verified_at) or "??:??"
        body = html.escape(EMPTY_TEXT % when)
        return (
            '<section class="cockpit-requests" data-state="empty">'
            '<h2>%s</h2><p class="cockpit-requests-status">%s</p></section>\n'
        ) % (html.escape(SECTION_TITLE), body)

    items = "".join(_render_request(r) for r in requests)
    return (
        '<section class="cockpit-requests" data-state="filled">'
        '<h2>%s</h2><ul class="cockpit-requests-list">%s</ul></section>\n'
    ) % (html.escape(SECTION_TITLE), items)


def _render_request(r):
    niveau_class = "urgent" if r.niveau == URGENT else ("a-faire" if r.niveau == "À faire" else "quand-tu-veux")
    incomplete_badge = ""
    if r.incomplete:
        first_missing = r.missing_fields[0] if r.missing_fields else "?"
        from cockpit.text.fallback import incomplete_label

        incomplete_badge = '<p class="cockpit-request-incomplete">%s</p>' % html.escape(
            incomplete_label(first_missing)
        )

    depuis = _hhmm(r.depuis_quand)
    verifie = _hhmm(r.verifie_a)
    meta = "%s · depuis %s · vérifié %s" % (
        html.escape(r.projet),
        depuis or "??:??",
        verifie or "??:??",
    )

    options_html = "".join(_render_option(o) for o in r.que_faire)
    recommande_note = ""
    if r.recommande_absent:
        from cockpit.text.fallback import FALLBACK_NO_RECOMMENDATION

        recommande_note = '<p class="cockpit-request-no-recommendation">%s</p>' % html.escape(
            FALLBACK_NO_RECOMMENDATION
        )

    details = (
        '<details class="cockpit-request-details"><summary>Détails</summary>'
        "<dl><dt>identifiant</dt><dd>%s</dd><dt>type</dt><dd>%s</dd></dl></details>"
    ) % (html.escape(r.id), html.escape(r.type))

    return (
        '<li class="cockpit-request" data-level="%s" data-incomplete="%s">'
        '<span class="cockpit-request-level">%s</span>'
        "<p class=\"cockpit-request-quoi\">%s</p>"
        "%s"
        "<p class=\"cockpit-request-pourquoi\">%s</p>"
        '<div class="cockpit-request-que-faire">%s</div>'
        "%s"
        '<p class="cockpit-request-meta">%s</p>'
        "%s"
        "</li>"
    ) % (
        niveau_class,
        "true" if r.incomplete else "false",
        html.escape(r.niveau),
        html.escape(r.quoi),
        incomplete_badge,
        html.escape(r.pourquoi),
        options_html,
        recommande_note,
        meta,
        details,
    )


def _render_option(option):
    recommande = ""
    if option.get("recommande"):
        recommande = ' <span class="cockpit-option-recommande">Recommandé — %s</span>' % html.escape(
            option.get("raison") or ""
        )
    return (
        '<p class="cockpit-option">%s — %s%s</p>'
        % (html.escape(option.get("option") or ""), html.escape(option.get("consequence") or ""), recommande)
    )
