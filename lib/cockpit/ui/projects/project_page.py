"""Renders the "Page projet" (spec af-oohx2x .49, T22, af-9tfjsc): a single
project's chantiers grouped by stage, per the view variant Benjamin chose
in T21 (comment on af-1al0t1, 2026-09-30, mot pour mot: "je veux pouvoir
switcher entre la vue tableau (choix 1) et la vue bande (choix 3) avec un
selecteur de vue") -- a sélecteur between "Tableau" (prototype
prototype/c01-project-page variante 1: colonnes par étape, une carte par
chantier dans sa colonne) and "Bande" (variante 3: liste continue triée
par avancement, chaque chantier porte sa propre barre d'étapes inline) --
its travail hors chantier (bugs, propositions, correctifs directs, spec
"Étapes d'un chantier", :mod:`cockpit.projects.hors_chantier`) shown with
no stage, and access to the project's historique
(:func:`cockpit.ui.projects.page.render_historique_section`, already
built by T20 specifically for this page: "a separate section so a caller
never shows this on the accueil, only on a project's own page (T22)").

Pure function of already-built data
(:mod:`cockpit.projects.builder`/:mod:`cockpit.projects.hors_chantier`) --
no I/O, exercised directly by tests the same way
:mod:`cockpit.ui.projects.page` is. Wiring a real ``/projet/<id>`` HTTP
route into the running cockpit process (server.py) is deferred past this
ticket's declared scope, the same precedent T19/T20/T21 set for
``lib/cockpit/ui/projects/**`` -- the home screen link this module's
:func:`project_page_url` feeds (see ``cockpit.ui.projects.page``'s
``_render_project``) is a plain ``<a href>`` a later ticket points at a
real handler; the default view-variant the agent chose as reversible
(T21 comment) and the per-device memorization both live client-side in
:data:`VIEW_SCRIPT`, needing no server round trip either.
"""
import html

from cockpit.projects.model import STAGES
from cockpit.ui.projects.page import render_historique_section  # noqa: F401 (re-exported for callers)

VIEW_TABLEAU = "tableau"
VIEW_BANDE = "bande"
VIEWS = (VIEW_TABLEAU, VIEW_BANDE)

TITLE_TABLEAU = "Tableau"
TITLE_BANDE = "Bande"

NO_CHANTIER_TEXT = "Aucun chantier actif."
HORS_CHANTIER_TITLE = "Travail hors chantier"
HORS_CHANTIER_EMPTY_TEXT = "Aucun travail hors chantier."
HISTORIQUE_LINK_TEXT = "Historique du projet →"
BACK_TEXT = "← Accueil"
PAGE_PROJET_LINK_TEXT = "Page projet →"


def project_page_url(project_id):
    """The href a project card's "Page projet" link points at (spec .49)
    -- a plain path, no query string, so a future server.py route can
    match on it directly."""
    return "/projet/%s" % project_id


def _stepper(stage_index):
    n = len(STAGES)
    dots = "".join(
        '<span class="%s" title="%s"></span>'
        % ("done" if i < stage_index else ("cur" if i == stage_index else ""), html.escape(STAGES[i]))
        for i in range(n)
    )
    label = "Étape %d sur %d : %s" % (stage_index + 1, n, STAGES[stage_index])
    return '<div class="cockpit-stepper" aria-label="%s">%s</div>' % (html.escape(label), dots)


def _render_tableau(chantiers):
    """Variante 1 "Tableau" (prototype): one column per stage, a card per
    chantier in its column -- every stage shown even when empty (0), so a
    reader can see at a glance which stages have nothing moving."""
    columns = []
    for i, stage in enumerate(STAGES):
        items = [c for c in chantiers if c.stage_index == i]
        cards = "".join(
            '<div class="cockpit-pp-card" data-chantier="%s">'
            '<span class="cockpit-pp-card-n">%s</span>'
            '<span class="cockpit-pp-card-s">%s</span>'
            "</div>"
            % (html.escape(c.id), html.escape(c.titre), html.escape(c.detail))
            for c in items
        )
        columns.append(
            '<div class="cockpit-pp-col" data-stage="%s">'
            '<div class="cockpit-pp-col-h">%s<span class="cockpit-pp-col-n">%d</span></div>'
            "%s"
            "</div>" % (html.escape(stage), html.escape(stage), len(items), cards)
        )
    return '<div class="cockpit-pp-board" data-state="%s">%s</div>' % (
        "filled" if chantiers else "empty",
        "".join(columns),
    )


def _render_bande(chantiers):
    """Variante 3 "Bande" (prototype): one continuous list sorted most
    advanced first, each row carrying its own inline stepper."""
    ordered = sorted(chantiers, key=lambda c: -c.stage_index)
    items = "".join(
        '<div class="cockpit-pp-strip-item" data-chantier="%s" data-stage="%s">'
        '<span class="cockpit-pp-strip-n">%s</span>'
        '<span class="cockpit-pp-strip-s">%s</span>'
        "%s"
        "</div>"
        % (
            html.escape(c.id),
            html.escape(c.stage),
            html.escape(c.titre),
            html.escape(c.detail),
            _stepper(c.stage_index),
        )
        for c in ordered
    )
    return '<div class="cockpit-pp-strip" data-state="%s">%s</div>' % (
        "filled" if chantiers else "empty",
        items,
    )


def _render_hors_chantier(items):
    if not items:
        return (
            '<section class="cockpit-pp-hors-chantier" data-state="empty">'
            "<h2>%s</h2><p class=\"cockpit-pp-hc-status\">%s</p></section>\n"
        ) % (html.escape(HORS_CHANTIER_TITLE), html.escape(HORS_CHANTIER_EMPTY_TEXT))
    rows = "".join(
        '<div class="cockpit-pp-hc-item" data-kind="%s" data-chantier="%s" data-stage="">'
        '<span class="cockpit-pp-hc-kind">%s</span>'
        '<span class="cockpit-pp-hc-n">%s</span>'
        "</div>"
        % (html.escape(item.kind), html.escape(item.id), html.escape(item.kind), html.escape(item.titre))
        for item in items
    )
    return (
        '<section class="cockpit-pp-hors-chantier" data-state="filled">'
        '<h2>%s</h2><div class="cockpit-pp-hc-list">%s</div></section>\n'
    ) % (html.escape(HORS_CHANTIER_TITLE), rows)


# Client-side view toggle + per-device memorization (T21 comment on
# af-1al0t1: "Non précisé par Benjamin, donc choix d'agent réversible : la
# vue par défaut et la mémorisation du choix de vue (par appareil)") --
# both views are always in the DOM (server-rendered, no round trip to
# switch); this script only flips which one shows, driven by a plain CSS
# attribute selector (see cockpit.ui.projects.tokens), the same pattern
# cockpit.ui.base.page's DISCONNECT_SCRIPT uses for its own client-only
# state.
VIEW_STORAGE_KEY = "cockpit-project-page-view"
VIEW_SCRIPT = (
    """
<script>
(function () {
  var KEY = %r;
  var root = document.getElementById("cockpit-pp-root");
  if (!root) return;
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (saved === "tableau" || saved === "bande") root.setAttribute("data-view", saved);
  var buttons = root.querySelectorAll("[data-view-choice]");
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (ev) {
      var v = ev.currentTarget.getAttribute("data-view-choice");
      root.setAttribute("data-view", v);
      try { localStorage.setItem(KEY, v); } catch (e) {}
    });
  }
})();
</script>
"""
    % VIEW_STORAGE_KEY
)


def _view_selector():
    return (
        '<div class="cockpit-pp-view-selector" role="group" aria-label="Sélecteur de vue">'
        '<button type="button" class="cockpit-pp-view-btn" data-view-choice="%s">%s</button>'
        '<button type="button" class="cockpit-pp-view-btn" data-view-choice="%s">%s</button>'
        "</div>"
    ) % (VIEW_TABLEAU, html.escape(TITLE_TABLEAU), VIEW_BANDE, html.escape(TITLE_BANDE))


def render_project_page(project, hors_chantier=None, historique_html="", view=VIEW_TABLEAU):
    """``project``: a :class:`cockpit.projects.model.Project` whose
    ``chantiers`` already holds only its active chantiers -- the same
    shape :func:`cockpit.ui.projects.page.render_projects_section`
    consumes (:mod:`cockpit.projects.builder`'s ``build_projects``
    output). ``hors_chantier``: this project's
    :class:`cockpit.projects.hors_chantier.HorsChantierItem` rows
    (:func:`cockpit.projects.hors_chantier.hors_chantier_par_projet`,
    keyed by ``project.project_id``). ``historique_html``: pre-rendered
    via :func:`cockpit.ui.projects.page.render_historique_section`, the
    caller already scoping it to this project's own chantiers/
    sans-projet rows alone -- this module never filters it itself.
    ``view``: the server's own default (T21: "vue par défaut ...
    réversible") -- a device that already chose overrides this
    client-side via :data:`VIEW_SCRIPT`; both views are rendered
    regardless, :data:`VIEW_SCRIPT` only toggles which one shows."""
    hors_chantier = hors_chantier or []
    view = view if view in VIEWS else VIEW_TABLEAU

    chantiers = project.chantiers or []
    if chantiers:
        tableau_html = _render_tableau(chantiers)
        bande_html = _render_bande(chantiers)
    else:
        empty = '<p class="cockpit-pp-empty">%s</p>' % html.escape(NO_CHANTIER_TEXT)
        tableau_html = bande_html = empty

    return (
        '<section class="cockpit-project-page" id="cockpit-pp-root" data-project="%s" data-view="%s">'
        '<header class="cockpit-pp-header">'
        '<a class="cockpit-pp-back" href="/">%s</a>'
        "<h1>%s</h1>"
        "</header>"
        "%s"
        '<div class="cockpit-pp-zone">'
        '<div class="cockpit-pp-zone-h"><h2>Chantiers par étape</h2>'
        '<a class="cockpit-pp-historique-link" href="#cockpit-pp-historique">%s</a></div>'
        '<div class="cockpit-pp-view cockpit-pp-view-tableau">%s</div>'
        '<div class="cockpit-pp-view cockpit-pp-view-bande">%s</div>'
        "</div>"
        "%s"
        '<div id="cockpit-pp-historique">%s</div>'
        "%s"
        "</section>\n"
    ) % (
        html.escape(project.project_id),
        html.escape(view),
        html.escape(BACK_TEXT),
        html.escape(project.display_name),
        _view_selector(),
        html.escape(HISTORIQUE_LINK_TEXT),
        tableau_html,
        bande_html,
        _render_hors_chantier(hors_chantier),
        historique_html,
        VIEW_SCRIPT,
    )
