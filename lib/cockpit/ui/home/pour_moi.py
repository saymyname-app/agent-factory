"""« Pour moi » in the foreground: a request of « Ce qui t’attend » opened in
the overview, with every gesture it has (B, af-4uzgzm; Spec af-fgcw0d, user
stories 6, 27, 29, 34, 73, 75, 76, 122 and 175; Validated Prototype
prototype/cockpit-b-zones-20261012 at 632deea, states result-request and
result-confirmation).

    html = render_request(request, now, links, stale=False, anchor="")

A request opens beside the list, where the result of a chantier opens: what
it is about, its title, why it waits, what can be done (its prepared
options), then its bar of gestures -- answer, acquit, put off, accept or
refuse a proposal with a reason or put it off, relaunch a session the
Factory paused, check the Factory when it fell silent. Every gesture that
changes the Factory is armed by a first click and sent by a second one,
« Confirmer ? » (:mod:`cockpit.ui.actions.render`). On a reading that is no
longer current, the gestures are drawn unavailable.

Its main text is the cockpit's French, never an identifier; the folded
details give what is technical: the identifier, the kind, the producer's
own words where they differ from what is shown, the precise source, the
links to where the request lives.

Pure: an :class:`~cockpit.requests.model.OperatorRequest`, no I/O.
"""
import dataclasses
import html

from cockpit.requests.model import TYPE_ESCALATION, TYPE_PROPOSAL, URGENT
from cockpit.requests.sources.paused_sessions import TYPE_SESSION_EN_PAUSE
from cockpit.requests.sources.readability import TYPE_SOURCE_ILLISIBLE
from cockpit.requests.sources.silence import TYPE_USINE_MUETTE
from cockpit.text.fallback import FALLBACK_NO_RECOMMENDATION, FIELD_LABELS, incomplete_label
from cockpit.ui.actions.render import REPORT_OPTIONS, FREE_TIME_OPTION, render_actions
from cockpit.ui.home.page import LEVEL_CLASS, _render_option, _since

# What a kind of request is, said in the folded details.
KINDS = {
    TYPE_ESCALATION: "Question qui t’est posée",
    TYPE_PROPOSAL: "Proposition de décision",
    TYPE_SESSION_EN_PAUSE: "Session mise en pause par l’usine",
    TYPE_USINE_MUETTE: "Usine muette",
    TYPE_SOURCE_ILLISIBLE: "Source illisible",
}
# The kinds that come from no bead: the cockpit raised them itself.
RAISED_BY_THE_COCKPIT = (TYPE_USINE_MUETTE, TYPE_SOURCE_ILLISIBLE)
STALE_GESTURES = "Lecture périmée : les gestes reviennent à la prochaine lecture."
FACTORY_PAGE = ("/usine", "Page Usine")
JOURNAL_PAGE = ("/journal", "Journal des demandes résolues")


def _e(text):
    return html.escape(str(text))


def links_of(request, project_url):
    """Where the request lives: the page of its project when it is known
    (``project_url``, or ``None``), the page of the Factory for what the
    Factory itself raised, and the journal where its resolution is
    written."""
    links = []
    if project_url:
        links.append((project_url, "Page du projet %s" % request.projet))
    if request.type in (TYPE_SESSION_EN_PAUSE, TYPE_USINE_MUETTE, TYPE_SOURCE_ILLISIBLE) or not project_url:
        links.append(FACTORY_PAGE)
    if request.type not in RAISED_BY_THE_COCKPIT:
        links.append(JOURNAL_PAGE)
    return links


def render_request(request, now, links, stale=False, shown=False, anchor="", undelivered=False):
    """The article of ``request`` opened in the overview; hidden unless
    ``shown``. ``links``: (address, label) of where it lives;
    ``anchor``: the anchor of the reference it carries, if any;
    ``undelivered``: its push could not be delivered yet (spec .59)."""
    level = LEVEL_CLASS.get(request.niveau, "info")
    about = " · ".join(filter(None, (request.projet, request.pourquoi if request.type == TYPE_ESCALATION else "")))
    since = _since(request.depuis_quand, now)
    status = ['<span class="lvl %s"><i></i>%s</span>' % (level, _e(request.niveau))]
    if since:
        status.append("<small>depuis %s</small>" % _e(since))
    other_missing = [field for field in request.missing_fields if field != "quoi"]
    if request.incomplete and other_missing:
        status.append('<span class="incomplete cockpit-request-incomplete">%s</span>'
                      % _e(incomplete_label(other_missing[0])))
    if request.acquittee:
        status.append('<span class="chip ack">Acquittée · rappels coupés</span>')
    if request.reportee:
        status.append('<span class="chip ack">Reportée</span>')
    if undelivered:
        # Never let the operator believe he was warned (spec .59).
        status.append('<span class="chip bloque">notification non livrée</span>')
    options = "".join(_render_option(request, option) for option in request.que_faire)
    if request.recommande_absent and request.type not in RAISED_BY_THE_COCKPIT:
        options += '<span class="oc">%s</span>' % _e(FALLBACK_NO_RECOMMENDATION)
    gestures = _gestures(request)
    if stale:
        options, gestures = _unavailable(options), _unavailable(gestures) + '<p class="pn-unwired">%s</p>' % _e(
            STALE_GESTURES)
    return (
        '<article class="pn-panel pn-result pn-open-request cockpit-request" id="d-%s" data-open="%s" '
        'data-level="%s"%s%s>'
        '<small>%s</small><h2 class="cockpit-request-quoi">%s</h2><p>%s</p>'
        '<div class="pn-request-status">%s</div>'
        '<div class="pn-choices"><h3>Que faire</h3><div class="opts cockpit-request-que-faire">%s</div></div>'
        "%s"
        '<div class="pn-dock" role="group" aria-label="Actions possibles">%s</div>'
        "</article>"
    ) % (
        _e(request.id), _e(request.id), level, "" if shown else " hidden", (" " + anchor) if anchor else "",
        _e(about or request.projet), _e(request.quoi), _e(request.pourquoi), "".join(status), options,
        render_details(request, links), gestures,
    )


def _unavailable(controls):
    """``controls`` drawn, and none of them usable."""
    return ('<fieldset class="pn-gestures" disabled><legend class="pn-sr-only">Indisponible</legend>%s</fieldset>'
            % controls)


def _gestures(request):
    """The bar of the request: its gestures, the kind's own first."""
    bead = _e(request.id)
    own = ""
    if request.type == TYPE_PROPOSAL:
        own = (
            '<button type="button" class="btn primary" data-action="accepter_proposition" data-bead-id="%s">'
            "Accepter</button>"
            '<span class="pn-refuse"><input type="text" class="field cockpit-rejeter-raison" data-bead-id="%s" '
            'placeholder="Ex. : pas pour cette version" aria-label="Raison du refus">'
            '<button type="button" class="btn" data-action="rejeter_proposition" data-bead-id="%s">Refuser</button>'
            "</span>"
            '<button type="button" class="btn" data-action="reporter_proposition_ouvrir" data-bead-id="%s">'
            "Reporter</button>%s"
        ) % (bead, bead, bead, bead, _proposal_report_menu(bead))
        # A proposal is put off through its door, not by the trace of
        # the cockpit: one « Reporter », the proposal's.
        request = dataclasses.replace(request, reportable=False)
    elif request.type == TYPE_SESSION_EN_PAUSE:
        own = ('<button type="button" class="btn primary" data-action="relancer" data-bead-id="%s" '
               'data-target-type="session" data-session-id="%s">Relancer</button>' % (bead, _e(request.titre)))
    elif request.type == TYPE_USINE_MUETTE:
        return ('<a class="btn primary" href="%s">Vérifier l’usine</a>'
                '<form method="post" action="/api/health/recheck"><button type="submit" class="btn">'
                "Revérifier maintenant</button></form>" % FACTORY_PAGE[0])
    elif request.type == TYPE_SOURCE_ILLISIBLE:
        return ""
    return own + render_actions(request)


def _proposal_report_menu(bead):
    """« Reporter jusqu’à : » for a proposal: one button per fixed delay,
    each armed then confirmed, as every gesture its door records."""
    fixed = "".join(
        '<button type="button" class="btn" data-action="reporter_proposition" data-bead-id="%s" '
        'data-option="%s">%s</button>' % (bead, _e(value), _e(label))
        for value, label in REPORT_OPTIONS if value != FREE_TIME_OPTION
    )
    return (
        '<div class="snoozemenu cockpit-proposal-report-menu" data-bead-id="%s" hidden>'
        '<span class="muted">Reporter jusqu’à :</span>%s'
        '<button type="button" class="btn ghost" data-action="reporter_proposition_fermer" data-bead-id="%s">'
        "Annuler</button></div>"
    ) % (bead, fixed, bead)


def render_details(request, links):
    """The folded details of a request (spec .75): its identifier and kind,
    the producer's own words, why a field was replaced, the precise source,
    and the links to where it lives."""
    rows = [("Identifiant", "<code>%s</code>" % _e(request.id)),
            ("Nature", "%s <code>%s</code>" % (_e(KINDS.get(request.type, "Signal non reconnu")), _e(request.type)))]
    for field_name in request.missing_fields:
        for reason in request.motifs.get(field_name, []):
            rows.append(("Remplacé (%s)" % FIELD_LABELS.get(field_name, field_name), _e(reason)))
    for field_name, written in (request.texte_origine or {}).items():
        if written:
            rows.append(("Texte écrit (%s)" % FIELD_LABELS.get(field_name, field_name), "<code>%s</code>" % _e(written)))
    if request.precisions:
        rows.append(("Précisions", "<code>%s</code>" % _e(request.precisions)))
    if links:
        rows.append(("Liens", " · ".join('<a href="%s">%s</a>' % (_e(url), _e(label)) for url, label in links)))
    body = "".join('<div class="row"><span>%s</span><span>%s</span></div>' % (_e(label), value) for label, value in rows)
    return ('<details class="more pn-request-details"><summary>Détails</summary><div class="det">%s</div></details>'
            % body)


CSS = """
.pn-open-request>small{display:block}
.pn-open-request>p{margin:0 0 10px;overflow-wrap:anywhere}
.pn-request-status{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-bottom:12px}
.pn-choices h3{font-size:13px;margin:16px 0 8px;color:var(--pn-muted-text);font-weight:600}
.pn-choices .opts{display:grid;gap:8px}
.pn-choices .btn.opt{min-height:44px}
.pn-request-details{margin-top:16px}
.pn-request-details .det .row{grid-template-columns:minmax(92px,auto) minmax(0,1fr)}
.pn-request-details .det .row>span{overflow-wrap:anywhere}
.pn-overview .pn-dock .acts{display:contents}
.pn-overview .pn-dock>.btn,.pn-overview .pn-dock .acts>.btn,.pn-overview .pn-dock .pn-refuse .btn{flex:0 1 auto;
  min-height:44px}
.pn-dock .pn-refuse{display:flex;flex-wrap:wrap;gap:8px;align-items:center;flex:1 1 280px}
.pn-dock .pn-refuse .field{flex:1 1 180px;min-height:44px;color:var(--ink)}
.pn-dock .snoozemenu{flex-basis:100%}
.pn-dock .snoozemenu:not([hidden]){display:flex}
.pn-dock .cockpit-actions-explication,.pn-dock .hint{flex-basis:100%;margin:0;font-size:13px;color:var(--pn-muted-text)}
.pn-dock form{margin:0}
.pn-gestures{display:contents;border:0;margin:0;padding:0;min-width:0}
.pn-overview .cockpit-armed{background:var(--accent-soft);border-color:var(--accent)}
"""
