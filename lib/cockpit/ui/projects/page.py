"""Renders the "Projets" section (spec af-oohx2x §"Accueil", §"Suivre les
projets", T19/T20; prototype variant D, branch prototype/c01-home-screen:
one card per project, a stepper bar per chantier).

Pure function of :func:`cockpit.projects.builder.build_projects`'s output --
no I/O, exercised directly by tests, the same way
:mod:`cockpit.ui.home.page`/:mod:`cockpit.ui.health.page` are.

T20 adds: the état badge (:mod:`cockpit.projects.etat`), the stepper's
Accepté/Promu dots (Promu's dot omitted when ``promu_masque``), "dev a N
commits d'avance" per rig, and the Accepter/« Pas bon -> agent » buttons on
a Livré-non-Accepté chantier -- rendered as ``data-action`` targets only,
the same deferred-wiring precedent T13's :mod:`cockpit.ui.actions.render`
set (server/home wiring is a later ticket's job, out of this one's
declared scope).

T22 adds: the "Page projet" link on every project card
(:func:`_render_page_projet_link`, spec .49) pointing at
:func:`cockpit.ui.projects.project_page.project_page_url` --
:mod:`cockpit.ui.projects.project_page` is this link's destination page.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects import etat as etat_mod
from cockpit.projects.model import LIVRE, SANS_PROJET, STAGES

# The panel of the result open on the home page (cockpit.ui.home.overview):
# where the chip of a chantier whose Outcome is to judge leads.
RESULT_PANEL_ID = "pn-result"

SECTION_TITLE = "Projets"
EMPTY_TEXT = "Aucun projet déclaré."
NO_CHANTIER_TEXT = "Aucun chantier actif."
UNKNOWN_TEXT = "Inconnu : projets illisibles depuis %s"
UNKNOWN_TEXT_NO_TIME = "Inconnu : projets illisibles depuis toujours"


def _hhmm(epoch):
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def render_projects_section(projects, sans_projet=None, with_page_link=True, stale_since=None):
    """``projects``: list of :class:`cockpit.projects.model.Project`.
    ``sans_projet``: list of orphan :class:`cockpit.projects.model.Chantier`
    (spec .50). ``with_page_link``: the "Page projet" link, off while the
    caller serves no such page. ``stale_since``: when the read behind this
    is no longer fresh, the hour it was taken — the zone is then greyed
    and says so (spec .63)."""
    projects = projects or []
    sans_projet = sans_projet or []
    title = html.escape(SECTION_TITLE)
    if not projects and not sans_projet:
        return (
            '<section class="zone cockpit-projects" data-state="empty">'
            '<div class="zone-h"><h2>%s</h2></div>'
            '<p class="muted cockpit-projects-status">%s</p></section>\n'
        ) % (title, html.escape(EMPTY_TEXT))

    body = "".join(_render_project(p, with_page_link) for p in projects)
    if sans_projet:
        body += _render_sans_projet(sans_projet)
    stale_note = ""
    if stale_since is not None:
        stale_note = '<span class="muted" style="font-size:var(--fs-xs)">vu à <time>%s</time></span>' % _hhmm(
            stale_since
        )
    return (
        '<section class="zone cockpit-projects" data-state="filled">'
        '<div class="zone-h"><h2>%s</h2>%s</div>'
        '<div class="zone-body%s"><div class="projects cockpit-projects-list">%s</div></div></section>\n'
    ) % (title, stale_note, " stale-val" if stale_since is not None else "", body)


def render_projects_unknown(last_known_at=None):
    """The whole zone when its read never succeeded or is failing: never an
    empty project list passed off as "no chantier" (spec .16, .63)."""
    since = _hhmm(last_known_at)
    text = UNKNOWN_TEXT % since if since else UNKNOWN_TEXT_NO_TIME
    return (
        '<section class="zone cockpit-projects" data-state="unknown">'
        '<div class="zone-h"><h2>%s</h2></div>'
        '<div class="unknown">%s</div></section>\n'
    ) % (html.escape(SECTION_TITLE), html.escape(text))


def _render_roadmap(project):
    if project.roadmap_unknown or project.roadmap_unknown_since is not None:
        since = _hhmm(project.roadmap_unknown_since)
        text = "Roadmap inconnue — illisible depuis %s" % since if since else "Roadmap inconnue — illisible"
        return '<span class="cockpit-project-roadmap" data-state="unknown">%s</span>' % html.escape(text)
    if project.roadmap_step is None:
        return ""
    text = "Roadmap : %s" % project.roadmap_step.title
    if project.roadmap_step.reserve:
        text += " · %s" % project.roadmap_step.reserve
    return '<span class="cockpit-project-roadmap" data-state="known">%s</span>' % html.escape(text)


def _render_ecart(project):
    if not project.ecart_commits_par_rig:
        return ""
    spans = []
    for rig, n in sorted(project.ecart_commits_par_rig.items()):
        if n is None:
            spans.append(
                '<span class="cockpit-project-ecart" data-state="unknown">%s : écart inconnu</span>'
                % html.escape(rig)
            )
        else:
            spans.append(
                '<span class="cockpit-project-ecart" data-state="known">%s : dev a %d commit%s d\'avance</span>'
                % (html.escape(rig), n, "s" if n != 1 else "")
            )
    return '<div class="s muted" style="font-size:var(--fs-s);padding-top:6px">%s</div>' % " · ".join(spans)


PAGE_PROJET_LINK_TEXT = "Page projet"


def _render_page_projet_link(project):
    """spec .49: "un lien « Page projet » depuis chaque projet, qui
    montre ses chantiers par étape, afin d'avoir le détail sans
    surcharger l'accueil" (T22, af-9tfjsc)."""
    from cockpit.ui.projects.project_page import project_page_url

    return '<a class="cockpit-project-page-link" href="%s" style="color:var(--accent)">%s</a>' % (
        html.escape(project_page_url(project.project_id)),
        html.escape(PAGE_PROJET_LINK_TEXT),
    )


def _render_project(project, with_page_link=True):
    beside_name = [part for part in (_render_roadmap(project),) if part]
    if with_page_link:
        beside_name.append(_render_page_projet_link(project))
    if project.chantiers:
        chantiers_html = "".join(_render_chantier(c) for c in project.chantiers)
    else:
        chantiers_html = '<p class="s muted cockpit-project-empty">%s</p>' % html.escape(NO_CHANTIER_TEXT)
    return (
        '<div class="proj cockpit-project" data-project="%s">'
        '<div class="proj-h cockpit-project-h"><h3>%s</h3>'
        '<span class="muted" style="font-size:var(--fs-s)">%s</span></div>'
        '<div class="cockpit-project-chantiers">%s</div>'
        "%s"
        "</div>"
    ) % (
        html.escape(project.project_id),
        html.escape(project.display_name),
        " · ".join(beside_name),
        chantiers_html,
        _render_ecart(project),
    )


def _stepper(stage_index, promu_masque):
    n = len(STAGES)
    dots = "".join(
        '<span class="%s" title="%s"></span>'
        % ("done" if i < stage_index else ("cur" if i == stage_index else ""), html.escape(STAGES[i]))
        for i in range(n)
        # spec .41: Promu's dot is omitted entirely when the rig has no
        # promotion branch configured -- not greyed, not shown as N/A.
        if not (promu_masque and STAGES[i] == "Promu")
    )
    label = "Étape %d sur %d : %s" % (stage_index + 1, n, STAGES[stage_index])
    return '<div class="stepper cockpit-stepper" aria-label="%s">%s</div>' % (html.escape(label), dots)


_CHIP_CLASS = {
    etat_mod.A_TOI_DE_JOUER: "atoi",
    etat_mod.PROBLEME_REMONTE: "probleme",
    etat_mod.BLOQUE: "bloque",
}


def _render_etat(chantier, home=""):
    """The état chip. "À toi de jouer" and "Problème remonté" lead in one
    click to where Benjamin acts (spec .43): the acceptance panel of a
    Livré chantier, otherwise the request carrying the question. An état
    that claims a target and has none shows as a defect (spec .45).
    ``home``: empty on the home screen itself, where both targets are
    on the page; the home screen's address from any other page."""
    texte = etat_mod.label(chantier.etat, chantier.etat_cible)
    attrs = 'data-etat="%s" data-cible="%s"' % (html.escape(chantier.etat), html.escape(chantier.etat_cible or ""))
    if chantier.etat == etat_mod.NORMAL:
        return '<span class="cockpit-chantier-etat" %s hidden>%s</span>' % (attrs, html.escape(texte))
    label = html.escape(texte[:1].upper() + texte[1:])
    if texte == etat_mod.DEFAUT_LABEL or chantier.etat == etat_mod.BLOQUE:
        return '<span class="chip bloque cockpit-chantier-etat" %s>%s</span>' % (attrs, label)
    chip = "chip go %s cockpit-chantier-etat" % _CHIP_CLASS[chantier.etat]
    if chantier.etat == etat_mod.A_TOI_DE_JOUER and chantier.outcome:
        # An Outcome of the new flow is judged at its Acceptance Session,
        # never by a button here (cockpit.projects.actions refuses it): the
        # chip leads to its result, open on the home page (A1).
        return '<a class="%s" %s href="%s#%s" title="Voir le résultat à juger">%s</a>' % (
            chip, attrs, html.escape(home), RESULT_PANEL_ID, label,
        )
    if chantier.etat == etat_mod.A_TOI_DE_JOUER and chantier.stage == LIVRE:
        if home:
            return '<a class="%s" %s href="%s#acc-%s" title="Aller là où tu dois agir">%s</a>' % (
                chip, attrs, html.escape(home), html.escape(chantier.id), label,
            )
        return (
            '<button type="button" class="%s" %s data-acc-open="%s" '
            'title="Aller là où tu dois agir">%s</button>'
        ) % (chip, attrs, html.escape(chantier.id), label)
    cible = html.escape(chantier.etat_cible)
    if home:
        return '<a class="%s" %s href="%s#d-%s" title="Aller là où tu dois agir">%s</a>' % (
            chip, attrs, html.escape(home), cible, label,
        )
    return '<a class="%s" %s href="#d-%s" data-goto="%s" title="Aller là où tu dois agir">%s</a>' % (
        chip, attrs, cible, cible, label,
    )


def _render_chantier_actions(chantier):
    """The acceptance panel of a Livré chantier (spec .30, .31), closed
    until its "À toi de jouer" chip opens it in place. None for an Outcome
    of the new flow: its acceptance is recorded at the Acceptance Session
    (bin/owner-answer), which this panel cannot do (A1)."""
    if chantier.stage != LIVRE or chantier.outcome:
        return ""
    bead_id = html.escape(chantier.id)
    return (
        '<div class="accpanel cockpit-chantier-actions" id="acc-%s" hidden>'
        "<div><b>Accepter la livraison « %s » ?</b> "
        "Tu as vérifié le résultat ; l'usine passe le chantier en Accepté.</div>"
        '<div class="acts">'
        '<button type="button" class="btn primary cockpit-action" data-action="accepter_chantier" '
        'data-bead-id="%s">Accepter</button>'
        '<button type="button" class="btn cockpit-action cockpit-action-tokens" data-action="pas_bon_vers_agent" '
        'data-bead-id="%s" data-titre="%s">Pas bon → agent '
        "<small>utilise un agent (consomme des tokens)</small></button>"
        '<button type="button" class="btn ghost" data-acc-close>Annuler</button>'
        "</div></div>"
    ) % (bead_id, html.escape(chantier.titre), bead_id, bead_id, html.escape(chantier.titre))


def _render_chantier(chantier):
    # "Livraison · 5/9 tickets mergés"; a detail that already starts with
    # its stage ("Livré : 4/4 tickets mergés") is not prefixed twice.
    if chantier.detail.startswith(chantier.stage):
        sous_titre = chantier.detail
    else:
        sous_titre = "%s · %s" % (chantier.stage, chantier.detail)
    return (
        '<div class="ch cockpit-chantier" id="ch-%s" data-stage="%s" data-termine="%s" data-abandonne="%s">'
        '<div><div class="n cockpit-chantier-n">%s</div>'
        '<div class="s cockpit-chantier-s">%s</div></div>'
        "<div>%s</div>"
        "%s"
        "%s"
        "</div>"
    ) % (
        html.escape(chantier.id),
        html.escape(chantier.stage),
        "true" if chantier.termine else "false",
        "true" if chantier.abandonne else "false",
        html.escape(chantier.titre),
        html.escape(sous_titre),
        _render_etat(chantier),
        _stepper(chantier.stage_index, chantier.promu_masque),
        _render_chantier_actions(chantier),
    )


# Chips and the acceptance panel. A "goto" chip opens the request it names
# in the inbox (the list row's own click does the selecting); one naming a
# request the inbox no longer holds says so instead of doing nothing.
PROJECTS_SCRIPT = """
<script>
(function () {
  function toast(text) {
    var el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('role', 'status');
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3200);
  }
  document.addEventListener('click', function (event) {
    var go = event.target.closest('[data-goto]');
    if (go) {
      event.preventDefault();
      var row = document.querySelector('.li[data-id="' + go.getAttribute('data-goto') + '"]');
      if (!row) { toast("Cette demande n'est pas dans la liste."); return; }
      row.click();
      document.getElementById('inbox').scrollIntoView({block: 'start'});
      return;
    }
    var open = event.target.closest('[data-acc-open]');
    if (open) {
      var panel = document.getElementById('acc-' + open.getAttribute('data-acc-open'));
      if (panel) { panel.hidden = false; panel.scrollIntoView({block: 'center'}); }
      return;
    }
    var close = event.target.closest('[data-acc-close]');
    if (close) { close.closest('.accpanel').hidden = true; }
  });
  // Arriving from a project page's "À toi de jouer": open that panel.
  if (location.hash.indexOf('#acc-') === 0) {
    var target = document.getElementById(location.hash.slice(1));
    if (target) { target.hidden = false; target.scrollIntoView({block: 'center'}); }
  }
})();
</script>
"""


HISTORIQUE_TITLE = "Historique"
HISTORIQUE_EMPTY_TEXT = "Aucun chantier terminé ou abandonné."


def render_historique_section(projects, sans_projet=None):
    """Terminé/abandonné chantiers (spec .46) -- a separate section so a
    caller never shows this on the accueil, only on a project's own page
    (T22)."""
    projects = projects or []
    sans_projet = sans_projet or []
    rows = [c for p in projects for c in p.chantiers] + list(sans_projet)
    if not rows:
        return (
            '<section class="cockpit-historique" data-state="empty">'
            "<h2>%s</h2><p class=\"cockpit-historique-status\">%s</p></section>\n"
        ) % (html.escape(HISTORIQUE_TITLE), html.escape(HISTORIQUE_EMPTY_TEXT))
    items = "".join(_render_historique_row(c) for c in rows)
    return (
        '<section class="cockpit-historique" data-state="filled">'
        '<h2>%s</h2><div class="cockpit-historique-list">%s</div></section>\n'
    ) % (html.escape(HISTORIQUE_TITLE), items)


def _render_historique_row(chantier):
    kind = "abandonne" if chantier.abandonne else "termine"
    return (
        '<div class="cockpit-historique-row" data-kind="%s" data-stage="%s">'
        '<span class="cockpit-historique-titre">%s</span>'
        '<span class="cockpit-historique-detail">%s</span>'
        "</div>"
    ) % (kind, html.escape(chantier.stage), html.escape(chantier.titre), html.escape(chantier.detail))


def _render_sans_projet(chantiers):
    items = "".join(_render_chantier(c) for c in chantiers)
    defect_note = "%d défaut producteur" % len(chantiers) if len(chantiers) == 1 else "%d défauts producteur" % len(chantiers)
    return (
        '<div class="proj cockpit-project cockpit-project-sans" data-project="sans-projet">'
        '<div class="proj-h cockpit-project-h"><h3>%s</h3>'
        '<span class="cockpit-project-defect" style="font-size:var(--fs-xs);color:var(--urgent)">%s</span></div>'
        "%s"
        "</div>"
    ) % (html.escape(SANS_PROJET), html.escape(defect_note), items)
