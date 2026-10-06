"""Renders the "Page projet" (spec af-oohx2x .49, T22, af-9tfjsc): a single
project's chantiers by stage, in the two presentations Benjamin chose in
T21 (comment on af-1al0t1, 2026-09-30, mot pour mot: "je veux pouvoir
switcher entre la vue tableau (choix 1) et la vue bande (choix 3) avec un
selecteur de vue") -- "Tableau" (prototype origin/prototype/c01-project-page
variante 1: one column per stage, a card per chantier) and "Bande"
(variante 3: one list sorted most advanced first, each chantier carrying
its own stepper) --, then its travail hors chantier (bugs, propositions,
correctifs directs: no stage, :mod:`cockpit.projects.hors_chantier`) and
its historique (:func:`cockpit.ui.projects.page.render_historique_section`).

Markup and class names are the prototype's (``renderV1``/``renderV3``,
``topbar``, ``summary``); the ``cockpit-pp-*`` names beside them are this
page's own hooks. Pure function of already-built data -- no I/O.
:mod:`cockpit.core.server` serves it on :func:`project_page_url`.

Not specified by Benjamin, so agent choices, reversible (T21 comment): the
view shown first -- Tableau, or Bande on a narrow screen where the table
only fits by scrolling sideways -- and remembering the chosen view per
device; both live client-side in :data:`VIEW_SCRIPT`.
"""
import html

from cockpit.projects import etat as etat_mod
from cockpit.projects.model import STAGES
from cockpit.ui.projects.page import _render_ecart, _render_etat, _render_roadmap, _stepper
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
UNKNOWN_PROJECT_TEXT = "Projet inconnu : aucun projet déclaré ne porte ce nom."

# The chips of this page lead to the home screen, where the request or the
# acceptance panel they point at lives.
HOME = "/"


def project_page_url(project_id):
    """The href a project's "Page projet" link points at (spec .49)."""
    return "/projet/%s" % project_id


def _stages_shown(project):
    """spec .41: no Promu column or step for a project that declares no
    promotion branch."""
    return STAGES[:-1] if project.promu_masque else STAGES


def _render_tableau(project):
    """Variante 1 "Tableau": one column per stage, a card per chantier in
    its column -- every applicable stage shown even when empty."""
    chantiers = project.chantiers or []
    stages = _stages_shown(project)
    headers, cells = [], []
    for i, stage in enumerate(stages):
        items = [c for c in chantiers if c.stage_index == i]
        first = " first" if i == 0 else ""
        headers.append(
            '<div class="bh cockpit-pp-col-h%s" data-stage="%s">%s<span class="n">%s</span></div>'
            % (first, html.escape(stage), html.escape(stage), len(items) or "")
        )
        cards = "".join(
            '<div class="card cockpit-pp-card%s" data-chantier="%s">'
            '<span class="n cockpit-pp-card-n">%s</span>'
            '<span class="s cockpit-pp-card-s">%s</span>'
            "%s"
            "</div>"
            % (
                " urgent-b" if c.etat == etat_mod.BLOQUE else "",
                html.escape(c.id),
                html.escape(c.titre),
                html.escape(c.detail),
                _render_etat(c, home=HOME),
            )
            for c in items
        )
        cells.append('<div class="cockpit-pp-col%s" data-stage="%s">%s</div>' % (first, html.escape(stage), cards))
    return (
        '<div class="v1"><div class="pipe-scroll">'
        '<div class="board cockpit-pp-board" data-state="%s" style="--n:%d">%s%s</div>'
        "</div></div>"
    ) % ("filled" if chantiers else "empty", len(stages), "".join(headers), "".join(cells))


def _render_bande(project):
    """Variante 3 "Bande": one continuous list sorted most advanced first,
    each row carrying its own stepper and stage names."""
    stages = _stages_shown(project)
    ordered = sorted(project.chantiers or [], key=lambda c: -c.stage_index)
    items = "".join(
        '<div class="s-item cockpit-pp-strip-item" data-chantier="%s" data-stage="%s">'
        '<div class="top"><span class="n cockpit-pp-strip-n">%s</span>%s</div>'
        '<div class="s cockpit-pp-strip-s">%s</div>'
        '<div class="stepline">%s</div>'
        '<div class="stepnames">%s</div>'
        "</div>"
        % (
            html.escape(c.id),
            html.escape(c.stage),
            html.escape(c.titre),
            _render_etat(c, home=HOME),
            html.escape(c.detail),
            _stepper(c.stage_index, project.promu_masque or c.promu_masque),
            "".join(
                '<span class="%s">%s</span>' % ("on" if i == c.stage_index else "", html.escape(stage))
                for i, stage in enumerate(stages)
            ),
        )
        for c in ordered
    )
    return '<div class="v3"><div class="strip cockpit-pp-strip" data-state="%s">%s</div></div>' % (
        "filled" if ordered else "empty",
        items,
    )


def _render_hors_chantier(items):
    title = html.escape(HORS_CHANTIER_TITLE)
    if not items:
        return (
            '<section class="zone cockpit-pp-hors-chantier" data-state="empty">'
            '<div class="zone-h"><h2>%s</h2></div>'
            '<p class="muted cockpit-pp-hc-status">%s</p></section>\n'
        ) % (title, html.escape(HORS_CHANTIER_EMPTY_TEXT))
    rows = "".join(
        '<div class="cockpit-pp-hc-item" data-kind="%s" data-chantier="%s" data-stage="">'
        '<span class="chip cockpit-pp-hc-kind">%s</span>'
        '<span class="cockpit-pp-hc-n">%s</span>'
        "</div>"
        % (html.escape(item.kind), html.escape(item.id), html.escape(item.kind), html.escape(item.titre))
        for item in items
    )
    return (
        '<section class="zone cockpit-pp-hors-chantier" data-state="filled">'
        '<div class="zone-h"><h2>%s</h2></div>'
        '<div class="panel cockpit-pp-hc-list">%s</div></section>\n'
    ) % (title, rows)


def _render_summary(project):
    """"7 chantiers actifs · 2 à toi de jouer · 1 problème remonté ·
    Historique du projet →" (prototype ``summary``)."""
    chantiers = project.chantiers or []
    n = len(chantiers)
    parts = ["<span><b>%d</b> chantier%s actif%s</span>" % (n, "s" if n > 1 else "", "s" if n > 1 else "")]
    for etat, chip, singular, plural in (
        (etat_mod.A_TOI_DE_JOUER, "atoi", "à toi de jouer", "à toi de jouer"),
        (etat_mod.PROBLEME_REMONTE, "probleme", "problème remonté", "problèmes remontés"),
        (etat_mod.BLOQUE, "bloque", "bloqué", "bloqués"),
    ):
        count = sum(1 for c in chantiers if c.etat == etat)
        if count:
            parts.append(
                '<span class="chip %s">%d %s</span>' % (chip, count, singular if count == 1 else plural)
            )
    parts.append(
        '<a class="history-link cockpit-pp-historique-link" href="#cockpit-pp-historique">%s</a>'
        % html.escape(HISTORIQUE_LINK_TEXT)
    )
    return '<div class="summary-row">%s</div>' % '<span class="sep"></span>'.join(parts)


# Which view shows: both are always in the DOM (server-rendered, no round
# trip to switch); this only flips the root's data-view, which the
# stylesheet reads. A device's own choice is remembered; with none, a
# narrow screen starts on Bande.
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
  if (saved !== "tableau" && saved !== "bande") {
    saved = window.matchMedia("(max-width: 899px)").matches ? "bande" : null;
  }
  if (saved) root.setAttribute("data-view", saved);
  var buttons = root.querySelectorAll("[data-view-choice]");
  function mark() {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute(
        "aria-pressed", buttons[i].getAttribute("data-view-choice") === root.getAttribute("data-view") ? "true" : "false"
      );
    }
  }
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (ev) {
      var v = ev.currentTarget.getAttribute("data-view-choice");
      root.setAttribute("data-view", v);
      try { localStorage.setItem(KEY, v); } catch (e) {}
      mark();
    });
  }
  mark();
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


def _render_topbar(project, fresh_html):
    roadmap_html = _render_roadmap(project)
    roadmap = '<span class="who">%s</span>' % roadmap_html if roadmap_html else ""
    return (
        '<header class="topbar cockpit-pp-header"><div class="brand">'
        '<a class="back cockpit-pp-back" href="/">%s</a><h1>%s</h1>%s</div>%s</header>'
    ) % (html.escape(BACK_TEXT), html.escape(project.display_name), roadmap, fresh_html)


def render_project_page(project, hors_chantier=None, historique_html="", view=VIEW_TABLEAU, fresh_html=""):
    """``project``: a :class:`cockpit.projects.model.Project` whose
    ``chantiers`` holds only its active chantiers
    (:func:`cockpit.projects.builder.build_projects`). ``hors_chantier``:
    this project's :class:`cockpit.projects.hors_chantier.HorsChantierItem`
    rows. ``historique_html``: pre-rendered by
    :func:`cockpit.ui.projects.page.render_historique_section`, already
    scoped to this project. ``view``: the view shown before
    :data:`VIEW_SCRIPT` runs. ``fresh_html``: the freshness headline
    (:func:`cockpit.ui.base.page.render_fresh`), shown top right as on the
    prototype."""
    hors_chantier = hors_chantier or []
    view = view if view in VIEWS else VIEW_TABLEAU

    if project.chantiers:
        tableau_html = _render_tableau(project)
        bande_html = _render_bande(project)
    else:
        empty = '<p class="muted cockpit-pp-empty">%s</p>' % html.escape(NO_CHANTIER_TEXT)
        tableau_html = bande_html = empty

    return (
        '<div class="cockpit-project-page" id="cockpit-pp-root" data-project="%s" data-view="%s">'
        "%s"
        "%s"
        '<section class="zone cockpit-pp-zone">'
        '<div class="zone-h cockpit-pp-zone-h"><h2>Chantiers par étape</h2>%s</div>'
        '<div class="cockpit-pp-view cockpit-pp-view-tableau">%s</div>'
        '<div class="cockpit-pp-view cockpit-pp-view-bande">%s</div>'
        "%s"
        "</section>"
        "%s"
        '<div id="cockpit-pp-historique">%s</div>'
        "%s"
        "</div>\n"
    ) % (
        html.escape(project.project_id),
        html.escape(view),
        _render_topbar(project, fresh_html),
        _render_summary(project),
        _view_selector(),
        tableau_html,
        bande_html,
        _render_ecart(project),
        _render_hors_chantier(hors_chantier),
        historique_html,
        VIEW_SCRIPT,
    )


def render_project_unknown(fresh_html="", unknown_project=False):
    """The page's top bar alone, with the way back -- for when there is
    no project to show. ``unknown_project``: the address names no
    declared project, said plainly rather than a blank page."""
    message = '<div class="unknown">%s</div>' % html.escape(UNKNOWN_PROJECT_TEXT) if unknown_project else ""
    return (
        '<div class="cockpit-project-page" data-state="unknown">'
        '<header class="topbar"><div class="brand"><a class="back cockpit-pp-back" href="/">%s</a></div>%s</header>'
        "%s</div>\n"
    ) % (html.escape(BACK_TEXT), fresh_html, message)
