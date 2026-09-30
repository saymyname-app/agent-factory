"""Renders the "Zone santé de l'usine" section (spec .64-.69, T16).

Pure function of a health snapshot (:func:`cockpit.health.engine.compute_health`
output) — no I/O, so it is exercised directly by tests without an HTTP round
trip, like cockpit.ui.base.page.render_home.
"""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def render_health_zone(health, checked_at=None):
    lines = health.get("lines") or []
    if not lines:
        body = '<p class="cockpit-health-ok">Aucun problème détecté.</p>'
    else:
        items = "".join(
            '<li data-kind="%s">%s</li>' % (html.escape(line["kind"]), html.escape(line["text"]))
            for line in lines
        )
        body = "<ul>%s</ul>" % items
    checked_html = ""
    if checked_at is not None:
        when = datetime.fromtimestamp(checked_at, tz=PARIS).strftime("%H:%M")
        checked_html = '<p class="cockpit-health-checked">Vérifié à %s</p>' % html.escape(when)
    return (
        '<section class="cockpit-health" data-ok="%s">'
        "<h2>Zone santé de l'usine</h2>"
        "%s"
        "%s"
        '<form method="post" action="/api/health/recheck">'
        '<button class="recheck" type="submit">Revérifier maintenant</button>'
        "</form>"
        "</section>"
    ) % (
        "true" if health.get("ok") else "false",
        body,
        checked_html,
    )
