"""Renders the Clean stop / restart zone (T23 af-s5e3yo, T24 af-j2mkpa --
spec af-oohx2x §"Arrêt propre et redémarrage"). Pure function of a
:class:`~cockpit.stop.driver.StopDriver`'s state -- same shape as
``ui/journal/render.py``.

Not wired into ``ui/home/page.py`` yet: process wiring (poller thread, the
button's HTTP action) is a later ticket's job, same precedent as T17/T18.

The stop button used to be permanently ``hidden`` until the three prior
factory corrections (T08/T09/T10) were delivered -- they now are, so this
renders it in **mode essai** instead: visible, but carrying a fixed
explanation that this is the real trial (spec "Bouton masqué tant que...").
It only turns into a plain button once ``driver.essai_reussi()`` reports a
persisted trace of a successful real trial (a clean stop followed by a
verified resume) -- never before, and never by itself reverting once set.
"""
import html

from cockpit.stop.driver import (
    ARRET_FORCE,
    ARRET_INTERROMPU,
    ARRETEE_PROPREMENT,
    EN_MARCHE,
)

SECTION_TITLE = "Arrêt propre de l'usine"
ESSAI_TEXT = (
    "Mode essai : ceci est l'essai réel de l'arrêt propre. "
    "Un arrêt suivi d'une reprise vérifiée rend ensuite ce bouton normal."
)
RESUME_STATES = (ARRETEE_PROPREMENT, ARRET_FORCE, ARRET_INTERROMPU)


def render_stop_section(driver):
    label = html.escape(driver.label())
    state = html.escape(driver.state())

    essai_html = ""
    stop_attrs = 'data-action="request-stop"'
    if not driver.essai_reussi():
        stop_attrs += ' data-mode="essai"'
        essai_html = '<p class="cockpit-stop-essai">%s</p>' % html.escape(ESSAI_TEXT)
    if driver.state() != EN_MARCHE:
        stop_attrs += " disabled"

    bilan_html = ""
    bilan = driver.bilan()
    if bilan:
        bilan_html = '<p class="cockpit-stop-bilan">Perdu : %s</p>' % html.escape(", ".join(bilan))

    ecarts_html = ""
    ecarts = driver.ecarts()
    if ecarts:
        ecarts_html = '<p class="cockpit-stop-ecarts">Écarts : %s</p>' % html.escape(", ".join(ecarts))

    resume_html = ""
    if driver.state() in RESUME_STATES:
        resume_html = '<button type="button" data-action="request-resume">Redémarrer</button>'

    return (
        '<section class="cockpit-stop" data-state="%s">'
        "<h2>%s</h2>"
        '<p class="cockpit-stop-label">%s</p>'
        "%s%s%s"
        '<button type="button" %s>Arrêter proprement l\'usine</button>'
        "%s"
        "</section>\n"
    ) % (state, html.escape(SECTION_TITLE), label, essai_html, bilan_html, ecarts_html, stop_attrs, resume_html)


__all__ = ["render_stop_section", "SECTION_TITLE", "ESSAI_TEXT"]
