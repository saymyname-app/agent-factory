"""The destination « Vue d’ensemble » of B/Panorama, with the panels of a
result (T02 Prototype Fold, af-0gonc9; Spec af-2zseit, user stories 111,
124, 147 and 175; Validated Prototype prototype/cockpit-b-zones-20261012 at
632deea, prototypes/c01-complete/frozen-panorama-home).

    view = overview_view(snapshot, requests)
    main_html = render_overview(view, anchors, details_html)

:func:`overview_view` reads, from the read model's snapshot and the
requests already assembled from it, which state the destination is in and
what it shows; :func:`render_overview` draws it, inside the shell of
:mod:`cockpit.ui.panorama.shell`. Neither reads a source.

The states:

- ``loading``: the tracker has not answered yet; ``error``: it was never
  read and its last read failed -- the page says the real state is unknown
  and offers to read again;
- ``empty``: nothing waits, no project, no result, no indicator;
- ``content``: four indicators, the activity, the last runs, what waits
  (« Ce qui t’attend ») beside the result open under it, the projects. A
  reading of the supervisor or the tracker that is no longer current keeps
  the last values under a notice that says so.

The result open is the record of a result to judge a bead carries under
``gc.result_dossier``; without one, the first request. The panels of a
result in its other states (its dossier, its follow-up, a decision) are
T02S's. A part of it that unfolds says, open, the lines its record gives it
(« Compte rendu long » its findings), or that the source gave none. Its
commands are not wired to a door here: Essai and Avis are drawn disabled,
and the panel says so -- nothing on the page shows a command done that no
door recorded.
"""
import html
import json
from datetime import datetime

from cockpit.core.freshness import FRESH
from cockpit.core.readmodel import PARIS
from cockpit.projects.source import from_value as projects_from_value
from cockpit.ui.panorama.shell import anchor_slug
from cockpit.ui.projects.project_page import project_page_url

LOADING, ERROR, EMPTY, CONTENT = "loading", "error", "empty", "content"
RESULT_DOSSIER = "gc.result_dossier"
PROJECT_CARD = "gc.project_card"
SAID = "said"

DECISIONS = "Décisions à prendre"
# The indicators the cockpit has no source for yet: what the tracker keeps
# as said of them (one bead under each title: its value, then its period),
# or « non collecté ».
SAID_INDICATORS = ("Résultats fusionnés", "Délai de livraison", "Vérifications CI réussies")
CHART_LABEL = ("Volumes quotidiens comparés sur sept jours : PR fusionnées, tickets livrés, "
               "exécutions CI réussies")
CHART_SERIES = (("PR fusionnées", "#91a7ff"), ("Tickets livrés", "#52c9b1"), ("CI réussies", "#e6ba70"))
UNWIRED_RESULT = "Essai et Avis ne sont pas encore raccordés à cette vue : rien n’est lancé ni préparé d’ici."
NOT_GIVEN = "Contenu non fourni par la source."
LEGACY_SUMMARY = "Détails techniques et actions"


def overview_view(snapshot, requests):
    """What the destination shows: ``state`` (see the module), ``stale``,
    ``checked`` (HH:MM of the reading shown), ``requests``, ``indicators``,
    ``dossier``, ``projects``."""
    beads_row = snapshot.get("beads")
    view = {"state": CONTENT, "stale": False, "checked": None, "requests": [], "indicators": [],
            "dossier": None, "projects": []}
    if beads_row is None or beads_row["value"] is None:
        view["state"] = ERROR if (beads_row or {}).get("failed_at") is not None else LOADING
        return view
    beads = [bead for bead in beads_row["value"] if isinstance(bead, dict)]
    rows = [snapshot[name] for name in ("gc", "beads") if snapshot.get(name)]
    view["stale"] = any(row["freshness"] != FRESH for row in rows)
    read_ats = [row["read_at"] for row in rows if row["read_at"] is not None]
    view["checked"] = _hhmm(min(read_ats) if view["stale"] else max(read_ats))
    view["requests"] = [
        {"id": r.id, "quoi": r.quoi, "projet": r.projet, "pourquoi": r.pourquoi,
         "origine": (r.texte_origine or {}).get("quoi")}
        for r in requests
    ]
    view["dossier"] = next(filter(None, (_record(bead, RESULT_DOSSIER) for bead in beads)), None)
    said = {bead.get("title"): _lines(bead) for bead in beads if SAID in (bead.get("labels") or [])}
    view["indicators"] = [(DECISIONS, str(len(requests)), "Maintenant · demandes ouvertes", "#pn-inbox")] + [
        (label, *(said[label] + ["", ""])[:2], "/analyses") if said.get(label)
        else (label, "—", "Non collecté", "/analyses")
        for label in SAID_INDICATORS
    ]
    view["projects"] = _projects(snapshot.get("projets"), beads, view["requests"])
    if not (view["requests"] or view["dossier"] or view["projects"]
            or any(said.get(label) for label in SAID_INDICATORS)):
        view["state"] = EMPTY
    return view


def _hhmm(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _lines(bead):
    return [line.strip() for line in (bead.get("description") or "").split("\n") if line.strip()]


def _record(bead, key):
    """The record ``key`` of ``bead``'s metadata, or None."""
    raw = (bead.get("metadata") or {}).get(key)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def _projects(row, beads, requests):
    """One card per declared project, those something waits for first, in
    the order of what waits: its name, its current chantier and its stage,
    its figures and the line of its release when the tracker holds them."""
    if row is None or row["value"] is None:
        return []
    projects, _ = projects_from_value(row["value"])
    cards = {bead.get("id"): _record(bead, PROJECT_CARD) for bead in beads}
    waiting = [request["projet"] for request in requests]
    order = {name: waiting.index(name) if name in waiting else len(waiting) for name in waiting}
    out = []
    for project in sorted(projects, key=lambda p: order.get(p.display_name, len(waiting))):
        current = next((c for c in project.chantiers if not c.termine), None)
        card = (cards.get(current.id) if current else None) or {}
        out.append({
            "id": project.project_id,
            "name": project.display_name,
            "chantier": "%s · %s" % (current.titre, card.get("stage") or current.stage) if current
            else "Aucun chantier en cours",
            "figures": [str(figure) for figure in card.get("figures") or []],
            "release": card.get("release"),
        })
    return out


# --- rendering -----------------------------------------------------------------

def _e(text):
    return html.escape(str(text))


def render_overview(view, anchors, details_html=""):
    """The ``main`` of the destination for ``view``; ``details_html``, the
    zones of the cockpit not folded into Panorama yet, folded under it."""
    state = view["state"]
    if state == LOADING:
        checked = "Lecture des sources en cours"
    elif state == ERROR:
        checked = "Aucune source lue"
    elif view["stale"]:
        checked = "Dernière observation · %s (Paris)" % view["checked"]
    else:
        checked = "Vérifié à %s (Paris)" % view["checked"]
    parts = ['<div class="pn-overview-head" %s><div><h1>Vue d’ensemble</h1><small>%s</small></div></div>'
             % (anchors("overview-head"), _e(checked))]
    if state == LOADING:
        parts.append(
            '<section class="pn-panel" role="status" %s><h2>Lecture en cours…</h2>%s</section>'
            % (anchors("panel"), "".join('<div class="pn-skeleton" %s></div>' % anchors("skeleton")
                                         for _ in range(3))))
    elif state == ERROR:
        parts.append(
            '<section class="pn-error" role="alert" %s><h2>Cette vue est indisponible</h2>'
            "<p>L’état réel est inconnu. Les sources de l’usine n’ont pas répondu.</p>"
            '<form method="post" action="/api/health/recheck"><button type="submit">Réessayer</button></form>'
            "</section>" % anchors("error"))
    elif state == EMPTY:
        parts.append('<section class="pn-panel pn-empty" %s><h2>Rien à afficher ici</h2>'
                     "<p>Aucun élément dans cette vue.</p></section>" % anchors("panel"))
    else:
        parts.append(_render_content(view, anchors))
    if details_html:
        parts.append('<details class="pn-legacy" id="pn-legacy"><summary>%s</summary><div class="pn-legacy-body">%s</div></details>'
                     % (LEGACY_SUMMARY, details_html))
    legacy = parts.pop() if details_html else ""
    return '<div class="pn-overview">%s</div>%s%s' % ("".join(parts), legacy, SCRIPT)


def _render_content(view, anchors):
    parts = []
    if view["stale"]:
        parts.append('<div class="pn-notice" role="status" %s>Lecture périmée · état actuel inconnu. '
                     "Dernières valeurs conservées ; actions indisponibles.</div>" % anchors("notice"))
    metrics = []
    for number, (label, value, caption, href) in enumerate(view["indicators"]):
        metrics.append(
            '<div class="pn-metric%s" %s><a href="%s">'
            '<span class="pn-metric-label" %s>%s</span><strong>%s</strong><small>%s</small></a></div>'
            % (" pn-emphasis" if number == 0 else "", anchors("metric"), _e(href), anchors("metric-label"),
               _e(label), _e(value), _e(caption)))
    parts.append('<div class="pn-metric-grid" %s>%s</div>' % (anchors("metric-grid"), "".join(metrics)))
    parts.append(_render_activity(anchors))
    parts.append(
        '<section class="pn-panel" %s><div class="pn-section-heading" %s><h2>Derniers runs</h2>'
        '<a class="pn-link" href="/runs">Tout voir</a></div>'
        '<iframe class="pn-runs" title="Cartes des derniers runs" srcdoc="%s" %s></iframe></section>'
        % (anchors("panel"), anchors("section-heading"), _e(RUNS_DOC), anchors("overview-runs")))
    requests = view["requests"]
    lines = "".join(
        '<button type="button" class="pn-request"%s data-request="%s" %s><strong>%s</strong>%s<small>%s</small></button>'
        % (' aria-current="true"' if number == 0 else "", _e(request["id"]), anchors("request"), _e(request["quoi"]),
           # A title its producer wrote outside the contract of the text:
           # the cockpit's label, then what was written, whole.
           '<span class="pn-origin">Texte écrit : « %s »</span>' % _e(request["origine"]) if request["origine"] else "",
           _e(" · ".join(filter(None, (request["projet"], request["pourquoi"])))))
        for number, request in enumerate(requests)
    ) or "<p>Rien ne t’attend.</p>"
    parts.append('<div class="pn-inbox" id="pn-inbox" %s><div class="pn-panel pn-requests" %s><h2>Ce qui t’attend</h2>%s</div>%s</div>'
                 % (anchors("inbox"), anchors("panel"), lines, _render_result(view, anchors)))
    parts.append(_render_projects(view["projects"], anchors))
    return "".join(parts)


def _render_activity(anchors):
    """« Activité sur 7 jours », folded: the key of the three series and
    their chart, drawn empty -- no source of daily volumes is read yet."""
    key = "".join('<span style="--series:%s">%s</span>' % (colour, _e(label)) for label, colour in CHART_SERIES)
    grid = "".join('<line x1="40" y1="%d" x2="695" y2="%d"></line>' % (y, y) for y in (195, 141, 87, 33))
    return (
        '<details class="pn-panel pn-activity" %s><summary>Activité sur 7 jours</summary>'
        '<div class="pn-chart-key" %s>%s</div>'
        '<svg class="pn-chart" viewBox="0 0 720 235" role="img" aria-label="%s" data-anchor="%s-1">'
        '<g stroke="var(--pn-line)">%s</g></svg>'
        "<p>Volumes quotidiens non collectés : aucune source ne les fournit encore au cockpit.</p>"
        '<a class="pn-link" href="/analyses">Explorer les métriques</a></details>'
    ) % (anchors("bilan"), anchors("chart-key"), key, _e(CHART_LABEL), anchor_slug(CHART_LABEL), grid)


def _render_result(view, anchors):
    """The panel of the result open under « Ce qui t’attend »."""
    record = view["dossier"]
    if record is None:
        return _render_request_panel(view["requests"], anchors)
    parts = [
        '<small>%s</small><h2>%s</h2><p>%s</p>'
        % (_e(record.get("about") or ""), _e(record.get("title") or ""), _e(record.get("summary") or "")),
        '<div class="pn-resources" %s>%s</div>' % (anchors("resource-list"), _render_resources(record.get("resources") or [])),
        '<div class="pn-dock" role="group" aria-label="Actions possibles" %s>'
        '<button type="button" disabled>Essai ↗</button><button type="button" disabled>Avis</button>'
        '<p class="pn-unwired">%s</p></div>' % (anchors("actions-possibles"), UNWIRED_RESULT),
    ]
    return '<article class="pn-panel pn-result" %s>%s</article>' % (anchors("panel"), "".join(parts))


def _render_resources(resources):
    out = []
    for resource in resources:
        if resource.get("opens"):
            out.append('<div class="pn-resource"><strong>%s</strong><small>%s</small></div>'
                       % (_e(resource.get("label")), _e(resource.get("detail") or "")))
        else:
            said = [line for line in resource.get("said") or [] if isinstance(line, str)] or [NOT_GIVEN]
            out.append("<details><summary>%s</summary>%s</details>"
                       % (_e(resource.get("label")), "".join("<p>%s</p>" % _e(line) for line in said)))
    return "".join(out)


def _render_request_panel(requests, anchors):
    """No result is open: the first request, and the way to its detail and
    its actions."""
    if not requests:
        return ('<article class="pn-panel pn-result" %s><h2>Rien ne t’attend</h2>'
                "<p>Aucune demande ouverte.</p></article>" % anchors("panel"))
    first = requests[0]
    return (
        '<article class="pn-panel pn-result" %s><small>%s</small><h2>%s</h2>'
        "<p>Son détail et ses actions sont sous « %s ».</p>"
        '<button type="button" class="pn-open-request" data-request="%s">Voir le détail et les actions</button>'
        "</article>"
    ) % (anchors("panel"), _e(" · ".join(filter(None, (first["projet"], first["pourquoi"])))), _e(first["quoi"]),
         LEGACY_SUMMARY, _e(first["id"]))


def _render_projects(projects, anchors):
    rows = []
    for project in projects:
        figures = "".join("<span>%s</span>" % _e(figure) for figure in project["figures"]) or \
            "<span>Volumes non collectés</span>"
        rows.append(
            '<div class="pn-row pn-project" %s><a href="%s">'
            '<div><strong>%s</strong><small>%s</small><div class="pn-stats" %s>%s</div>'
            '<div class="pn-release" %s>%s</div></div><span aria-hidden="true">→</span></a></div>'
            % (anchors("row"), _e(project_page_url(project["id"])), _e(project["name"]), _e(project["chantier"]),
               anchors("small-stats"), figures, anchors("release-info"),
               _e(project["release"] or "Release non cadrée")))
    body = "".join(rows) or "<p>Aucun projet déclaré.</p>"
    return '<section class="pn-panel pn-projects" %s><h2>Projets</h2><div class="pn-rows" %s>%s</div></section>' % (
        anchors("panel"), anchors("rows"), body)


# The cards of the last runs, inside their frame: none is read on this
# destination yet.
RUNS_DOC = (
    '<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>'
    ":root{color-scheme:light;--bg:#FFFFFF;--ink:#566175}"
    "@media (prefers-color-scheme: dark){:root{color-scheme:dark;--bg:#161B23;--ink:#9AA6B9}}"
    "body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,sans-serif}"
    "p{margin:12px 0;line-height:1.5}</style></head><body>"
    "<p>Aucune carte de run sur cette vue : les cartes Runs n’y sont pas encore raccordées. "
    "La page Runs les liste.</p></body></html>"
)

CSS = """
.pn-overview-head small{display:block;margin-bottom:20px;color:var(--pn-muted);font-size:12px}
.pn-overview-head h1{font-size:27px;margin:0 0 6px}
.pn-overview small{color:var(--pn-muted);font-size:12px}
.pn-overview button{font:inherit;color:var(--pn-ink);background:var(--pn-surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:10px 14px;cursor:pointer}
.pn-overview button:hover{border-color:var(--pn-accent)}
.pn-overview button:disabled{opacity:.5;cursor:not-allowed}
.pn-link{color:var(--pn-accent);text-decoration:none}
.pn-link:hover{text-decoration:underline}
.pn-notice{padding:12px;border:1px solid var(--pn-line);border-radius:6px;color:var(--pn-warn);margin-bottom:18px;
  overflow-wrap:anywhere}
.pn-metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
.pn-metric{border:1px solid var(--pn-line);border-radius:10px;background:var(--pn-surface);min-width:0}
.pn-metric>a{display:block;padding:18px;border-radius:10px;color:inherit;text-decoration:none}
.pn-metric:hover{border-color:var(--pn-accent)}
.pn-metric.pn-emphasis{border-color:var(--pn-accent)}
.pn-metric strong{display:block;font-size:28px;margin:7px 0}
.pn-metric small{display:block}
.pn-metric-label{font-size:13px;color:var(--pn-muted)}
.pn-activity summary{cursor:pointer;color:var(--pn-muted)}
.pn-chart-key{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;margin:12px 0}
.pn-chart-key span:before{content:'';display:inline-block;width:20px;height:3px;background:var(--series);
  vertical-align:middle;margin-right:8px}
.pn-chart{width:100%;height:auto;max-height:290px;display:block}
.pn-activity p{margin:8px 0;color:var(--pn-muted);font-size:14px}
.pn-section-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:6px}
.pn-section-heading h2{margin:0}
.pn-runs{display:block;width:100%;height:110px;margin-top:12px;border:0;background:var(--pn-surface)}
.pn-inbox{display:grid;grid-template-columns:330px minmax(0,1fr);gap:20px;align-items:start}
.pn-inbox>*{min-width:0}
.pn-requests{padding:0}
.pn-requests h2{padding:20px 20px 0}
.pn-requests>p{padding:0 20px 20px}
.pn-overview .pn-request{display:block;width:100%;text-align:left;border:0;border-top:1px solid var(--pn-line);
  border-radius:0;padding:20px;background:transparent}
.pn-overview .pn-request[aria-current=true]{background:var(--pn-surface-2);box-shadow:inset 4px 0 0 var(--pn-accent)}
.pn-request strong{display:block;margin-bottom:8px;overflow-wrap:anywhere}
.pn-request small{display:block;overflow-wrap:anywhere}
.pn-origin{display:block;margin-bottom:8px;font-size:14px;overflow-wrap:anywhere}
.pn-result h2{margin-top:12px;overflow-wrap:anywhere}
.pn-result>p{margin:0 0 8px}
.pn-resources{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:22px}
.pn-resource{display:flex;flex-direction:column;justify-content:start;gap:4px;padding:15px;min-height:95px;
  border:1px solid var(--pn-line);border-radius:8px}
.pn-resources details{grid-column:1/-1}
.pn-result details{border-top:1px solid var(--pn-line);padding:14px 0}
.pn-result summary{cursor:pointer;color:var(--pn-muted)}
.pn-result details p{font-size:14px;margin:10px 0 0;overflow-wrap:anywhere}
.pn-dock{display:flex;flex-wrap:wrap;gap:12px;align-items:center;border-top:1px solid var(--pn-line);
  padding-top:18px;margin-top:22px}
.pn-dock>button{flex:1;min-height:54px;font-size:16px;font-weight:650}
.pn-unwired{flex-basis:100%;margin:0;font-size:13px;color:var(--pn-muted)}
.pn-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  border-bottom:1px solid var(--pn-line)}
.pn-row:last-child{border-bottom:0}
.pn-row>*{min-width:0}
.pn-row strong{display:block;margin-bottom:5px;overflow-wrap:anywhere}
.pn-row small{display:block;overflow-wrap:anywhere}
.pn-project{display:block;padding:0}
.pn-project>a{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  color:inherit;text-decoration:none}
.pn-project>a>*{min-width:0}
.pn-project:hover strong{color:var(--pn-accent)}
.pn-rows{display:grid}
.pn-stats{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:12px;font-size:12px;color:var(--pn-muted)}
.pn-release{margin-top:8px;font-size:12px;color:var(--pn-muted);overflow-wrap:anywhere}
.pn-skeleton{height:16px;background:var(--pn-line);border-radius:5px;margin:14px 0;width:65%}
.pn-skeleton:nth-of-type(2){width:85%}
.pn-error{border-left:3px solid var(--pn-warn);padding:20px;background:var(--pn-surface);margin-bottom:20px}
.pn-error h2{font-size:19px;margin:0 0 10px}
.pn-error p{margin:0 0 14px}
.pn-empty{text-align:center;padding:55px 20px}
.pn-empty p{color:var(--pn-muted)}
.pn-legacy{margin-top:28px;border-top:1px solid var(--pn-line);padding-top:16px}
.pn-legacy>summary{cursor:pointer;color:var(--pn-muted)}
.pn-legacy:not([open])>.pn-legacy-body{display:none}
@media (max-width:1100px){.pn-inbox{grid-template-columns:minmax(0,1fr)}}
@media (max-width:800px){
  .pn-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pn-metric>a{padding:13px}
  .pn-metric strong{font-size:24px}
  .pn-overview-head h1{font-size:24px}
  .pn-resources{grid-template-columns:minmax(0,1fr)}
  .pn-row,.pn-project>a{align-items:flex-start}
}
"""

# A request opens its detail and its actions, under « Détails techniques et
# actions ».
SCRIPT = """
<script>
(function () {
  function openRequest(id) {
    var legacy = document.getElementById('pn-legacy');
    if (!legacy) { return; }
    legacy.open = true;
    var item = legacy.querySelector('.li[data-id="' + id.replace(/"/g, '') + '"]');
    if (item) { item.click(); }
    var detail = document.getElementById('d-' + id);
    (detail || legacy).scrollIntoView({block: 'start'});
  }
  document.addEventListener('click', function (event) {
    var request = event.target.closest('[data-request]');
    if (request) { openRequest(request.getAttribute('data-request')); }
  });
})();
</script>
"""
