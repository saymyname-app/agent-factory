"""Renders the "Projets" section (spec af-oohx2x §"Accueil", §"Suivre les
projets", T19; prototype variant D, branch prototype/c01-home-screen: one
card per project, a stepper bar per chantier).

Pure function of :func:`cockpit.projects.builder.build_projects`'s output --
no I/O, exercised directly by tests, the same way
:mod:`cockpit.ui.home.page`/:mod:`cockpit.ui.health.page` are.
"""
import html
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects.model import SANS_PROJET, STAGES

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


def _render_project(project):
    roadmap_html = _render_roadmap(project)
    if project.chantiers:
        chantiers_html = "".join(_render_chantier(c) for c in project.chantiers)
    else:
        chantiers_html = '<p class="cockpit-project-empty">%s</p>' % html.escape(NO_CHANTIER_TEXT)
    return (
        '<div class="cockpit-project" data-project="%s">'
        '<div class="cockpit-project-h"><h3>%s</h3>%s</div>'
        '<div class="cockpit-project-chantiers">%s</div>'
        "</div>"
    ) % (
        html.escape(project.project_id),
        html.escape(project.display_name),
        roadmap_html,
        chantiers_html,
    )


def _stepper(stage_index):
    n = len(STAGES)
    dots = "".join(
        '<span class="%s" title="%s"></span>'
        % ("done" if i < stage_index else ("cur" if i == stage_index else ""), html.escape(STAGES[i]))
        for i in range(n)
    )
    label = "Étape %d sur %d : %s" % (stage_index + 1, n, STAGES[stage_index])
    return '<div class="cockpit-stepper" aria-label="%s">%s</div>' % (html.escape(label), dots)


def _render_chantier(chantier):
    return (
        '<div class="cockpit-chantier" data-stage="%s">'
        '<div class="cockpit-chantier-n">%s</div>'
        '<div class="cockpit-chantier-s">%s</div>'
        "%s"
        "</div>"
    ) % (
        html.escape(chantier.stage),
        html.escape(chantier.titre),
        html.escape(chantier.detail),
        _stepper(chantier.stage_index),
    )


def _render_sans_projet(chantiers):
    items = "".join(_render_chantier(c) for c in chantiers)
    defect_note = "%d défaut producteur" % len(chantiers) if len(chantiers) == 1 else "%d défauts producteur" % len(chantiers)
    return (
        '<div class="cockpit-project cockpit-project-sans" data-project="sans-projet">'
        '<div class="cockpit-project-h"><h3>%s</h3><span class="cockpit-project-defect">%s</span></div>'
        '<div class="cockpit-project-chantiers">%s</div>'
        "</div>"
    ) % (html.escape(SANS_PROJET), html.escape(defect_note), items)
