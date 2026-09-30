"""Renders the Clean stop zone (T23, af-s5e3yo -- spec af-oohx2x §"Arrêt
propre et redémarrage"). Pure function of a
:class:`~cockpit.stop.driver.StopDriver`'s state -- same shape as
``ui/journal/render.py``.

Not wired into ``ui/home/page.py``: "le bouton d'arrêt n'est pas affiché ;
le chemin est piloté par le test" (spec AC5) until the three prior factory
corrections are delivered and Benjamin has triggered a successful real
trial (spec "Bouton masqué tant que..."). The button element this renders
carries ``hidden`` for that reason -- a later ticket removes it once that
condition is met; nothing here should be read as "ready to show".
"""
import html

from cockpit.stop.driver import EN_MARCHE

SECTION_TITLE = "Arrêt propre de l'usine"


def render_stop_section(driver):
    label = html.escape(driver.label())
    state = html.escape(driver.state())
    button_attrs = 'data-action="request-stop" hidden'
    if driver.state() != EN_MARCHE:
        button_attrs = 'data-action="request-stop" hidden disabled'

    bilan_html = ""
    bilan = driver.bilan()
    if bilan:
        bilan_html = '<p class="cockpit-stop-bilan">Perdu : %s</p>' % html.escape(", ".join(bilan))

    ecarts_html = ""
    ecarts = driver.ecarts()
    if ecarts:
        ecarts_html = '<p class="cockpit-stop-ecarts">Écarts : %s</p>' % html.escape(", ".join(ecarts))

    return (
        '<section class="cockpit-stop" data-state="%s">'
        "<h2>%s</h2>"
        '<p class="cockpit-stop-label">%s</p>'
        "%s%s"
        '<button type="button" %s>Arrêter proprement l\'usine</button>'
        "</section>\n"
    ) % (state, html.escape(SECTION_TITLE), label, bilan_html, ecarts_html, button_attrs)


__all__ = ["render_stop_section", "SECTION_TITLE"]
