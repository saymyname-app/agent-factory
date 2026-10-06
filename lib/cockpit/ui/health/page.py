"""Renders the factory's health twice (spec .64-.69, T16; prototype
origin/prototype/c01-home-screen): the one-line state at the top of the
home screen, and the "Santé de l'usine" zone listing every line.

Pure functions of a health snapshot (:func:`cockpit.health.engine.compute_health`
output) and of the read model's ``gc`` row — no I/O.
"""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from cockpit.core.freshness import FRESH, UNKNOWN

PARIS = ZoneInfo("Europe/Paris")

KIND_LEVEL = {"bad": "urgent", "warn": "normal", "ok": "ok"}
STATUS_LINES_SHOWN = 2


def _hhmm(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _short(text):
    """A health sentence as a clause of the status line."""
    text = text.rstrip(".")
    return text[:1].lower() + text[1:]


def render_status_line(gc_row, health):
    """"En marche · 2 agents au travail · …" — never a state or a count
    the supervisor was not read for (spec .63)."""
    gc_row = gc_row or {}
    value = gc_row.get("value")
    if not value or gc_row.get("freshness") == UNKNOWN:
        return (
            '<span class="lvl info"><i></i>État de l\'usine inconnu</span> '
            "<span>le superviseur ne répond pas</span>"
        )
    if value.get("suspended"):
        label = '<span class="lvl normal"><i></i>Suspendue</span>'
    else:
        label = '<span class="lvl ok"><i></i>En marche</span>'
    agents = int(value.get("agents_running") or 0)
    parts = ["%d agent%s au travail" % (agents, "s" if agents > 1 else "")]
    lines = [_short(line["text"]) for line in (health.get("lines") or [])]
    parts.extend(lines[:STATUS_LINES_SHOWN])
    if len(lines) > STATUS_LINES_SHOWN:
        more = len(lines) - STATUS_LINES_SHOWN
        parts.append("%d autre%s point%s en santé" % (more, "s" if more > 1 else "", "s" if more > 1 else ""))
    text = html.escape(" · ".join(parts))
    if gc_row.get("freshness") != FRESH:
        return '%s <span class="stale-val">%s · vu à <time>%s</time></span>' % (
            label, text, _hhmm(gc_row["read_at"]),
        )
    return "%s <span>%s</span>" % (label, text)


def render_health_zone(health, checked_at=None):
    lines = health.get("lines") or []
    if not lines:
        body = (
            '<div class="hl cockpit-health-ok"><span class="lvl ok"><i></i></span>'
            "<span>Aucun problème détecté.</span></div>"
        )
    else:
        body = "".join(
            '<div class="hl" data-kind="%s"><span class="lvl %s"><i></i></span><span>%s</span></div>'
            % (html.escape(line["kind"]), KIND_LEVEL.get(line["kind"], "info"), html.escape(line["text"]))
            for line in lines
        )
    checked_html = ""
    if checked_at is not None:
        checked_html = (
            '<span class="muted cockpit-health-checked" style="font-size:var(--fs-xs)">'
            "vérifié à <time>%s</time></span>" % _hhmm(checked_at)
        )
    return (
        '<section class="zone cockpit-health" id="sante" data-ok="%s">'
        '<div class="zone-h"><h2>Santé de l\'usine</h2>%s</div>'
        '<div class="health"><div class="hlist">%s</div></div>'
        "</section>"
    ) % (
        "true" if health.get("ok") else "false",
        checked_html,
        body,
    )
