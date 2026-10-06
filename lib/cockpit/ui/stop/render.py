"""Renders the Clean stop / restart zone (T23 af-s5e3yo, T24 af-j2mkpa --
spec af-oohx2x §"Arrêt propre et redémarrage"). Pure function of a
:class:`~cockpit.stop.driver.StopDriver`'s state and of the work in
flight -- no I/O.

``enabled`` decides whether the stop and restart controls exist at all.
Spec .91 keeps the button hidden until a real trial triggered by Benjamin
has succeeded; the served page passes ``enabled=False`` (af-mjfvwx slice
7a: nothing in the cockpit can stop the factory yet) and the zone then
says so. With ``enabled=True`` the stop button is in **mode essai** until
``driver.essai_reussi()`` reports a persisted successful trial (a clean
stop followed by a verified resume), a plain button after.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.stop.driver import (
    ARRET_FORCE,
    ARRET_INTERROMPU,
    ARRETEE_PROPREMENT,
    EN_MARCHE,
    REPRISE_VERIFIEE,
)

SECTION_TITLE = "Arrêt propre de l'usine"
ESSAI_TEXT = (
    "Mode essai : ceci est l'essai réel de l'arrêt propre. "
    "Un arrêt suivi d'une reprise vérifiée rend ensuite ce bouton normal."
)
NOT_AVAILABLE_TEXT = (
    "L'arrêt depuis le cockpit n'est pas encore disponible : il attend ton essai réel."
)
WORK_UNKNOWN_TEXT = "Travail en vol : inconnu — le superviseur ne répond pas."
WORK_NONE_TEXT = "Aucun travail en vol : aucun agent ne tient de ticket."
UNTITLED_TICKET_TEXT = "ticket dont le titre n'a pas été lu"
RESUME_STATES = (ARRETEE_PROPREMENT, ARRET_FORCE, ARRET_INTERROMPU)
_OK_STATES = (EN_MARCHE, REPRISE_VERIFIEE)


def _line(level, inner):
    return '<div class="hl"><span class="lvl %s"><i></i></span><span>%s</span></div>' % (level, inner)


def _render_work(work):
    """What a stop would wait for (spec .81, .82): one line per agent on a
    ticket, with its last sign of life. ``work``: ``{"known": bool,
    "sessions": [{"titre", "last_event_at"}]}``."""
    if not work.get("known"):
        return _line("info", '<span class="cockpit-stop-work">%s</span>' % html.escape(WORK_UNKNOWN_TEXT))
    sessions = work.get("sessions") or []
    if not sessions:
        return _line("ok", '<span class="cockpit-stop-work">%s</span>' % html.escape(WORK_NONE_TEXT))
    n = len(sessions)
    lines = [
        _line(
            "info",
            '<span class="cockpit-stop-work">Travail en vol : %d agent%s sur un ticket.</span>'
            % (n, "s" if n > 1 else ""),
        )
    ]
    for session in sessions:
        last = session.get("last_event_at")
        when = (
            " · dernier signe de vie <time>%s</time>" % datetime.fromtimestamp(last, tz=PARIS).strftime("%H:%M")
            if last
            else ""
        )
        lines.append(
            '<div class="hl cockpit-stop-session"><span class="lvl"></span><span>%s%s</span></div>'
            % (html.escape(session.get("titre") or UNTITLED_TICKET_TEXT), when)
        )
    return "".join(lines)


def render_stop_section(driver, enabled=True, work=None, factory=None):
    """``factory``: ``(level, text)`` for what gc itself says of the
    factory, shown while the driver has no stop in progress. The driver's
    own "En marche" only means "no stop was requested from here": it is
    never shown as a fact about a supervisor that was not read (spec .63)."""
    state = driver.state()
    level, text = ("ok" if state in _OK_STATES else "normal"), driver.label()
    if state == EN_MARCHE and factory is not None:
        level, text = factory
    label = '<span class="cockpit-stop-label">%s</span>' % html.escape(text)
    body = [_line(level, label)]

    bilan = driver.bilan()
    if bilan:
        body.append(_line("urgent", '<span class="cockpit-stop-bilan">Perdu : %s</span>' % html.escape(", ".join(bilan))))
    ecarts = driver.ecarts()
    if ecarts:
        body.append(_line("normal", '<span class="cockpit-stop-ecarts">Écarts : %s</span>' % html.escape(", ".join(ecarts))))
    if work is not None:
        body.append(_render_work(work))

    controls = ""
    if enabled:
        stop_attrs = 'data-action="request-stop"'
        essai_html = ""
        if not driver.essai_reussi():
            stop_attrs += ' data-mode="essai"'
            essai_html = '<p class="hint cockpit-stop-essai">%s</p>' % html.escape(ESSAI_TEXT)
        if state != EN_MARCHE:
            stop_attrs += " disabled"
        resume_html = ""
        if state in RESUME_STATES:
            resume_html = '<button type="button" class="btn" data-action="request-resume">Redémarrer</button>'
        controls = (
            '%s<div class="acts"><button type="button" class="btn" %s>Arrêter proprement l\'usine</button>%s</div>'
        ) % (essai_html, stop_attrs, resume_html)
    else:
        controls = '<p class="hint cockpit-stop-unavailable">%s</p>' % html.escape(NOT_AVAILABLE_TEXT)

    return (
        '<section class="zone cockpit-stop" id="arret" data-state="%s" data-enabled="%s">'
        '<div class="zone-h"><h2>%s</h2></div>'
        '<div class="health"><div class="hlist">%s</div>%s</div>'
        "</section>\n"
    ) % (html.escape(state), "true" if enabled else "false", html.escape(SECTION_TITLE), "".join(body), controls)


__all__ = ["render_stop_section", "SECTION_TITLE", "ESSAI_TEXT"]
