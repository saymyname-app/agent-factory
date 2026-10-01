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
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects import etat as etat_mod
from cockpit.projects.model import LIVRE, SANS_PROJET, STAGES

SECTION_TITLE = "Projets"
EMPTY_TEXT = "Aucun projet déclaré."
NO_CHANTIER_TEXT = "Aucun chantier actif."


def _hhmm(epoch):
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def render_projects_section(projects, sans_projet=None):
    """``projects``: list of :class:`cockpit.projects.model.Project`.
    ``sans_projet``: list of orphan :class:`cockpit.projects.model.Chantier`
    (spec .50)."""
    projects = projects or []
    sans_projet = sans_projet or []
    if not projects and not sans_projet:
        return (
            '<section class="cockpit-projects" data-state="empty">'
            "<h2>%s</h2><p class=\"cockpit-projects-status\">%s</p></section>\n"
        ) % (html.escape(SECTION_TITLE), html.escape(EMPTY_TEXT))

    body = "".join(_render_project(p) for p in projects)
    if sans_projet:
        body += _render_sans_projet(sans_projet)
    return (
        '<section class="cockpit-projects" data-state="filled">'
        '<h2>%s</h2><div class="cockpit-projects-list">%s</div></section>\n'
    ) % (html.escape(SECTION_TITLE), body)


def _render_roadmap(project):
    if project.roadmap_unknown_since is not None:
        since = _hhmm(project.roadmap_unknown_since)
        text = "Roadmap inconnue — illisible depuis %s" % since if since else "Roadmap inconnue — illisible"
        return '<span class="cockpit-project-roadmap" data-state="unknown">%s</span>' % html.escape(text)
    if project.roadmap_step is None:
        return ""
    text = "Roadmap : %s" % project.roadmap_step.title
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
    return "".join(spans)


def _render_project(project):
    roadmap_html = _render_roadmap(project)
    ecart_html = _render_ecart(project)
    if project.chantiers:
        chantiers_html = "".join(_render_chantier(c) for c in project.chantiers)
    else:
        chantiers_html = '<p class="cockpit-project-empty">%s</p>' % html.escape(NO_CHANTIER_TEXT)
    return (
        '<div class="cockpit-project" data-project="%s">'
        '<div class="cockpit-project-h"><h3>%s</h3>%s%s</div>'
        '<div class="cockpit-project-chantiers">%s</div>'
        "</div>"
    ) % (
        html.escape(project.project_id),
        html.escape(project.display_name),
        roadmap_html,
        ecart_html,
        chantiers_html,
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
    return '<div class="cockpit-stepper" aria-label="%s">%s</div>' % (html.escape(label), dots)


def _render_etat(chantier):
    texte = etat_mod.label(chantier.etat, chantier.etat_cible)
    return '<span class="cockpit-chantier-etat" data-etat="%s" data-cible="%s">%s</span>' % (
        html.escape(chantier.etat),
        html.escape(chantier.etat_cible or ""),
        html.escape(texte),
    )


def _render_chantier_actions(chantier):
    if chantier.stage != LIVRE:
        return ""
    return (
        '<div class="cockpit-chantier-actions">'
        '<button type="button" class="cockpit-action" data-action="accepter_chantier" data-bead-id="%s">Accepter</button>'
        '<button type="button" class="cockpit-action cockpit-action-tokens" data-action="pas_bon_vers_agent" '
        'data-bead-id="%s">Pas bon → agent (utilise un agent — consomme des tokens)</button>'
        "</div>"
    ) % (html.escape(chantier.id), html.escape(chantier.id))


def _render_chantier(chantier):
    return (
        '<div class="cockpit-chantier" data-stage="%s" data-termine="%s" data-abandonne="%s">'
        '<div class="cockpit-chantier-n">%s</div>'
        '<div class="cockpit-chantier-s">%s</div>'
        "%s"
        "%s"
        "%s"
        "</div>"
    ) % (
        html.escape(chantier.stage),
        "true" if chantier.termine else "false",
        "true" if chantier.abandonne else "false",
        html.escape(chantier.titre),
        html.escape(chantier.detail),
        _render_etat(chantier),
        _stepper(chantier.stage_index, chantier.promu_masque),
        _render_chantier_actions(chantier),
    )


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
        '<div class="cockpit-project cockpit-project-sans" data-project="sans-projet">'
        '<div class="cockpit-project-h"><h3>%s</h3><span class="cockpit-project-defect">%s</span></div>'
        '<div class="cockpit-project-chantiers">%s</div>'
        "</div>"
    ) % (html.escape(SANS_PROJET), html.escape(defect_note), items)
