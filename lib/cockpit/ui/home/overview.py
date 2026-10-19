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
(a report, « Compte rendu long », its findings), or that the source gave
none. Its commands are not wired to a door here: Essai, Avis and the
resources that open are drawn unavailable, and the panel says so -- nothing
on the page shows a command done that no door recorded.

Every part carries the anchor of the reference (``data-anchor``), numbered
by the :class:`~cockpit.ui.panorama.shell.Anchors` of the page as the frozen
pages number them: the generic ones too (``div-3``, ``strong-8``,
``circle-7``), in the order the reference draws them.
"""
import html
import json
from datetime import datetime

from cockpit.core.freshness import FRESH
from cockpit.core.readmodel import PARIS
from cockpit.projects.source import from_value as projects_from_value
from cockpit.ui.panorama.shell import Anchors, anchor_slug, open_button
from cockpit.ui.projects.project_page import project_page_url

LOADING, ERROR, EMPTY, CONTENT = "loading", "error", "empty", "content"
RESULT_DOSSIER = "gc.result_dossier"
PROJECT_CARD = "gc.project_card"
RUN_CARD = "gc.run_card"
SAID = "said"

DECISIONS = "Décisions à prendre"
# The indicators the cockpit has no source for yet: what the tracker keeps
# as said of them (one bead under each title: its value, then its period),
# or « non collecté ».
SAID_INDICATORS = ("Résultats fusionnés", "Délai de livraison", "Vérifications CI réussies")
CHART_LABEL = ("Volumes quotidiens comparés sur sept jours : PR fusionnées, tickets livrés, "
               "exécutions CI réussies")
# Each series its colour (a token of the page, 3:1 at least on the surface
# in both themes) and its dashes, so that it is told apart without its
# colour: a plain, a dashed and a dotted line.
CHART_SERIES = (("PR fusionnées", "var(--pn-series-1)", ""), ("Tickets livrés", "var(--pn-series-2)", "8 5"),
                ("CI réussies", "var(--pn-series-3)", "1 5"))
ACTIVITY = "Activité sur 7 jours"
UNWIRED_RESULT = "Essai et Avis ne sont pas encore raccordés à cette vue : rien n’est lancé ni préparé d’ici."
NOT_GIVEN = "Contenu non fourni par la source."
LEGACY_SUMMARY = "Détails techniques et actions"


def overview_view(snapshot, requests):
    """What the destination shows: ``state`` (see the module), ``stale``,
    ``checked`` (HH:MM of the reading shown), ``requests``, ``indicators``,
    ``activity``, ``runs`` (the cards of the last runs), ``dossier``,
    ``projects``."""
    beads_row = snapshot.get("beads")
    view = {"state": CONTENT, "stale": False, "checked": None, "requests": [], "indicators": [],
            "activity": {}, "runs": [], "dossier": None, "projects": []}
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
    view["activity"] = _activity(said.get(ACTIVITY) or [])
    view["runs"] = [card for card in (_record(bead, RUN_CARD) for bead in beads) if card]
    view["projects"] = _projects(snapshot.get("projets"), beads, view["requests"])
    if not (view["requests"] or view["dossier"] or view["projects"] or view["activity"] or view["runs"]
            or any(said.get(label) for label in SAID_INDICATORS)):
        view["state"] = EMPTY
    return view


def _activity(lines):
    """The daily volumes the tracker keeps as said under « Activité sur 7
    jours », one line a day and a series (« PR fusionnées · Lundi : 1 »):
    series -> its seven volumes, Monday first. A series without its seven
    days is left out: no line is drawn of a day no source gave."""
    days = [day for _, day in CHART_DAYS]
    said = {}
    for line in lines:
        series, _, rest = line.partition(" · ")
        day, _, volume = rest.partition(" : ")
        try:
            said.setdefault(series, {})[day] = float(volume.replace(",", "."))
        except ValueError:
            continue
    return {series: [volumes[day] for day in days] for series, volumes in said.items()
            if series in {label for label, _, _ in CHART_SERIES} and set(days) <= set(volumes)}


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
    """The ``main`` of the destination for ``view``, numbered by ``anchors``
    as the reference numbers its parts; ``details_html``, the zones of the
    cockpit not folded into Panorama yet, folded under it."""
    state = view["state"]
    if state == LOADING:
        checked = "Lecture des sources en cours"
    elif state == ERROR:
        checked = "Aucune source lue"
    elif view["stale"]:
        checked = "Dernière observation · %s (Paris)" % view["checked"]
    else:
        checked = "Vérifié à %s (Paris)" % view["checked"]
    parts = ['<div class="pn-overview-head" %s><div %s><h1 %s>Vue d’ensemble</h1><small %s>%s</small></div></div>'
             % (anchors("overview-head"), anchors("div"), anchors("h1"), anchors("small"), _e(checked))]
    if state == LOADING:
        parts.append(
            '<section class="pn-panel" role="status" %s><h2 %s>Lecture en cours…</h2>%s</section>'
            % (anchors("panel"), anchors("h2"), "".join('<div class="pn-skeleton" %s></div>' % anchors("skeleton")
                                                         for _ in range(3))))
    elif state == ERROR:
        parts.append(
            '<section class="pn-error" role="alert" %s><h2 %s>Cette vue est indisponible</h2>'
            "<p %s>L’état réel est inconnu. Les sources de l’usine n’ont pas répondu.</p>"
            '<form method="post" action="/api/health/recheck"><button type="submit" %s>Réessayer</button></form>'
            "</section>" % (anchors("error"), anchors("h2"), anchors("p"), anchors("button")))
    elif state == EMPTY:
        parts.append('<section class="pn-panel pn-empty" %s><h2 %s>Rien à afficher ici</h2>'
                     "<p %s>Aucun élément dans cette vue.</p></section>"
                     % (anchors("panel"), anchors("h2"), anchors("p")))
    else:
        parts.append(_render_content(view, anchors))
    legacy = ""
    if details_html:
        legacy = ('<details class="pn-legacy" id="pn-legacy"><summary>%s</summary>'
                  '<div class="pn-legacy-body">%s</div></details>' % (LEGACY_SUMMARY, details_html))
    return '<div class="pn-overview">%s</div>%s%s' % ("".join(parts), legacy, SCRIPT)


def _render_content(view, anchors):
    parts = []
    if view["stale"]:
        parts.append('<div class="pn-notice" role="status" %s>Lecture périmée · état actuel inconnu. '
                     "Dernières valeurs conservées ; actions indisponibles.</div>" % anchors("notice"))
    metrics = []
    grid = anchors("metric-grid")
    for number, (label, value, caption, href) in enumerate(view["indicators"]):
        metrics.append(
            '<div class="pn-metric%s" %s><a href="%s">'
            '<span class="pn-metric-label" %s>%s</span><strong %s>%s</strong><small %s>%s</small></a></div>'
            % (" pn-emphasis" if number == 0 else "", anchors("metric"), _e(href), anchors("metric-label"),
               _e(label), anchors("strong"), _e(value), anchors("small"), _e(caption)))
    parts.append('<div class="pn-metric-grid" %s>%s</div>' % (grid, "".join(metrics)))
    parts.append(_render_activity(view["activity"], anchors))
    panel, heading = anchors("panel"), anchors("section-heading")
    parts.append(
        '<section class="pn-panel" %s><div class="pn-section-heading" %s><h2 %s>Derniers runs</h2>%s</div>'
        '<iframe class="pn-runs" title="Cartes des derniers runs" srcdoc="%s" %s></iframe></section>'
        % (panel, heading, anchors("h2"), open_button("/runs", "Tout voir", anchors("link"), "pn-link"),
           _e(_runs_document(view["runs"])), anchors("overview-runs")))
    inbox, requests_panel = anchors("inbox"), anchors("panel")
    title = '<h2 %s>Ce qui t’attend</h2>' % anchors("h2")
    lines = "".join(
        '<button type="button" class="pn-request"%s data-request="%s" %s><strong %s>%s</strong>%s<small %s>%s</small>'
        "</button>"
        % (' aria-current="true"' if number == 0 else "", _e(request["id"]), anchors("request"), anchors("strong"),
           _e(request["quoi"]),
           # A title its producer wrote outside the contract of the text:
           # the cockpit's label, then what was written, whole.
           '<span class="pn-origin">Texte écrit : « %s »</span>' % _e(request["origine"]) if request["origine"] else "",
           anchors("small"), _e(" · ".join(filter(None, (request["projet"], request["pourquoi"])))))
        for number, request in enumerate(view["requests"])
    ) or "<p>Rien ne t’attend.</p>"
    parts.append('<div class="pn-inbox" id="pn-inbox" %s><div class="pn-panel pn-requests" %s>%s%s</div>%s</div>'
                 % (inbox, requests_panel, title, lines, _render_result(view, anchors)))
    parts.append(_render_projects(view["projects"], anchors))
    return "".join(parts)


# The frame of the chart of the reference: the days along x, 105 px apart
# from x 55; the volumes along y, from y 195 (none) up to 162 px higher, with
# four lines of the grid at a quarter, a half and three quarters of the top.
CHART_DAYS = (("Lun", "Lundi"), ("Mar", "Mardi"), ("Mer", "Mercredi"), ("Jeu", "Jeudi"), ("Ven", "Vendredi"),
              ("Sam", "Samedi"), ("Dim", "Dimanche"))
CHART_ZERO, CHART_HEIGHT, CHART_STEP = 195, 162, 105


def _render_activity(activity, anchors):
    """« Activité sur 7 jours », folded: the key of the three series, then
    their chart, the volumes a source said of each day (``activity``:
    series -> seven volumes, Monday first), or, without one, that they are
    not collected -- no line is drawn of a volume no source gave."""
    bilan, summary, chart_key = anchors("bilan"), anchors("summary"), anchors("chart-key")
    key = "".join('<span style="--series:%s;--dash:%s" %s>%s</span>'
                  % (colour, "dashed" if dashes.startswith("8") else "dotted" if dashes else "solid",
                     anchors("span"), _e(label))
                  for label, colour, dashes in CHART_SERIES)
    if activity:
        top = max(3, -(-max(max(volumes) for volumes in activity.values()) // 3) * 3)
        scale = CHART_HEIGHT / top
        lines = "".join('<line x1="40" y1="%s" x2="695" y2="%s" %s></line>'
                        % (_n(CHART_ZERO - tick * scale), _n(CHART_ZERO - tick * scale), anchors("line"))
                        for tick in (0, top / 3, 2 * top / 3, top))
        grid = '<g stroke="var(--line)" %s>%s</g>' % (anchors("g"), lines)
        g = anchors("g")
        labels = "".join('<text x="20" y="%s" %s>%s</text>' % (_n(CHART_ZERO + 4 - tick * scale), anchors("text"),
                                                               _n(tick))
                         for tick in (0, top / 3, 2 * top / 3, top))
        labels += "".join('<text x="%d" y="222" %s>%s</text>' % (45 + CHART_STEP * day, anchors("text"), short)
                          for day, (short, _) in enumerate(CHART_DAYS))
        series = []
        for label, colour, dashes in CHART_SERIES:
            volumes = activity.get(label)
            if not volumes:
                continue
            points = [(55 + CHART_STEP * day, _n(CHART_ZERO - volume * scale)) for day, volume in enumerate(volumes)]
            series.append('<polyline fill="none" stroke="%s" stroke-width="2.5" stroke-linejoin="round" '
                          'stroke-linecap="round"%s points="%s" %s></polyline>'
                          % (colour, ' stroke-dasharray="%s"' % dashes if dashes else "",
                             " ".join("%d,%s" % point for point in points), anchors("polyline")))
            for (x, y), volume, (_, day) in zip(points, volumes, CHART_DAYS):
                series.append('<circle cx="%d" cy="%s" r="4" fill="%s" %s><title %s>%s · %s : %s</title></circle>'
                              % (x, y, colour, anchors("circle"), anchors("title"), _e(label), day, _n(volume)))
        chart = grid + '<g fill="var(--muted)" font-size="11" %s>%s</g>%s' % (g, labels, "".join(series))
        note = _activity_table(activity)
    else:
        chart = '<g stroke="var(--line)">%s</g>' % "".join(
            '<line x1="40" y1="%d" x2="695" y2="%d"></line>' % (y, y) for y in (195, 141, 87, 33))
        note = "<p>Volumes quotidiens non collectés : aucune source ne les fournit encore au cockpit.</p>"
    return (
        '<details class="pn-panel pn-activity" %s><summary %s>Activité sur 7 jours</summary>'
        '<div class="pn-chart-key" %s>%s</div>'
        '<svg class="pn-chart" viewBox="0 0 720 235" role="img" aria-label="%s" data-anchor="%s-1">%s</svg>'
        "%s%s</details>"
    ) % (bilan, summary, chart_key, key, _e(CHART_LABEL), anchor_slug(CHART_LABEL), chart, note,
         open_button("/analyses", "Explorer les métriques", anchors("link"), "pn-link"))


def _activity_table(activity):
    """The volumes of the chart as a table, for a reader that does not see
    it: one row a series, one column a day."""
    head = "".join('<th scope="col">%s</th>' % day for _, day in CHART_DAYS)
    rows = "".join('<tr><th scope="row">%s</th>%s</tr>'
                   % (_e(label), "".join("<td>%s</td>" % _n(volume) for volume in activity[label]))
                   for label, _, _ in CHART_SERIES if activity.get(label))
    return ('<table class="pn-sr-only"><caption>%s</caption><tr><th scope="col">Série</th>%s</tr>%s</table>'
            % (_e(CHART_LABEL), head, rows))


def _n(number):
    """A number of the chart as the reference writes it: no ``.0``."""
    return ("%.2f" % number).rstrip("0").rstrip(".")


def _render_result(view, anchors):
    """The panel of the result open under « Ce qui t’attend »."""
    record = view["dossier"]
    if record is None:
        return _render_request_panel(view["requests"], anchors)
    panel = anchors("panel")
    parts = ['<small %s>%s</small><h2 %s>%s</h2><p %s>%s</p>'
             % (anchors("small"), _e(record.get("about") or ""), anchors("h2"), _e(record.get("title") or ""),
                anchors("p"), _e(record.get("summary") or ""))]
    resource_list = anchors("resource-list")
    parts.append('<div class="pn-resources" %s>%s</div>'
                 % (resource_list, "".join(_render_resource(r, anchors) for r in record.get("resources") or [])))
    parts.append("".join(_render_folded(report, anchors) for report in record.get("reports") or []))
    dock = anchors("actions-possibles")
    parts.append(
        '<div class="pn-dock" role="group" aria-label="Actions possibles" %s>'
        '<a class="pn-button" role="link" aria-disabled="true" tabindex="-1" %s>Essai ↗</a><button type="button" disabled %s>Avis</button>'
        '<p class="pn-unwired">%s</p></div>' % (dock, anchors("button"), anchors("button"), UNWIRED_RESULT))
    return '<article class="pn-panel pn-result" %s>%s</article>' % (panel, "".join(parts))


def _render_resource(resource, anchors):
    """A resource of the dossier: one that opens -- not from this view yet,
    so drawn unavailable --, or one that unfolds."""
    if not resource.get("opens"):
        return _render_folded(resource, anchors)
    button, label = anchors("button"), anchors("span")
    return ('<button type="button" class="pn-resource" disabled %s><span %s><strong %s>%s</strong><small %s>%s</small>'
            '</span><span aria-hidden="true" %s>↗</span></button>'
            % (button, label, anchors("strong"), _e(resource.get("label")), anchors("small"),
               _e(resource.get("detail") or ""), anchors("span")))


def _render_folded(part, anchors):
    """A part of the dossier that unfolds: open, the lines its record gives
    it, or that the source gave none."""
    said = [line for line in part.get("said") or [] if isinstance(line, str)] or [NOT_GIVEN]
    details, summary = anchors("details"), anchors("summary")
    return "<details %s><summary %s>%s</summary>%s</details>" % (
        details, summary, _e(part.get("label")), "".join("<p %s>%s</p>" % (anchors("p"), _e(line)) for line in said))


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
    panel, title, rows_anchor = anchors("panel"), '<h2 %s>Projets</h2>' % anchors("h2"), anchors("rows")
    rows = []
    for project in projects:
        row, holder, name, chantier, stats = (anchors("row"), anchors("div"), anchors("strong"), anchors("small"),
                                              anchors("small-stats"))
        figures = "".join("<span %s>%s</span>" % (anchors("span"), _e(figure)) for figure in project["figures"]) or \
            "<span %s>Volumes non collectés</span>" % anchors("span")
        rows.append(
            '<div class="pn-row pn-project" %s><a href="%s">'
            '<div %s><strong %s>%s</strong><small %s>%s</small><div class="pn-stats" %s>%s</div>'
            '<div class="pn-release" %s>%s</div></div><span aria-hidden="true" %s>→</span></a></div>'
            % (row, _e(project_page_url(project["id"])), holder, name, _e(project["name"]), chantier,
               _e(project["chantier"]), stats, figures, anchors("release-info"),
               _e(project["release"] or "Release non cadrée"), anchors("span")))
    body = "".join(rows) or "<p>Aucun projet déclaré.</p>"
    return '<section class="pn-panel pn-projects" %s>%s<div class="pn-rows" %s>%s</div></section>' % (
        panel, title, rows_anchor, body)


# The cards of the last runs, inside their frame, as the reference draws
# them: three a row, one under the other in a frame under 850 px. A card
# opens the destination Runs; opening the run itself is T44's. The status of
# a run waiting for a decision is written darker in the light theme, where
# the reference's is under 4.5:1 on the surface.
RUNS_CSS = (
    ":root{color-scheme:light;--surface:#fff;--line:#dbe0e8;--ink:#17202e;--muted:#657185;--accent:#415fce;"
    "--ok:#1c7954;--human:#e4bc6d;--code:#55b5ae;--agent:#a897eb;--wait:#85590f}"
    "@media (prefers-color-scheme: dark){:root{color-scheme:dark;--surface:#161b23;--line:#2a3240;--ink:#ecedf3;"
    "--muted:#9aa6b9;--accent:#99aaff;--ok:#55c89d;--wait:#e4bc6d}}"
    "*{box-sizing:border-box}html,body{margin:0;background:var(--surface);color:var(--ink);font:15px system-ui,sans-serif}"
    ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}"
    ".card{display:block;height:100%;background:var(--surface);border:1px solid var(--line);border-radius:10px;"
    "padding:18px;color:inherit;text-decoration:none}"
    ".card:hover{border-color:var(--accent)}.card:focus-visible{outline:2px solid var(--accent);outline-offset:-4px}"
    ".card h2{margin:12px 0 7px;font-size:18px;overflow-wrap:anywhere}"
    ".card p{margin:0 0 14px;font-size:14px;line-height:1.5;color:var(--muted);overflow-wrap:anywhere}"
    ".card-top{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--muted)}"
    ".badge{color:var(--ok)}.badge.live{color:var(--accent)}.badge.wait{color:var(--wait)}"
    ".live-dot{display:inline-block;width:7px;height:7px;border-radius:100%;background:var(--accent);margin-right:6px}"
    ".card-foot{display:flex;justify-content:space-between;gap:10px;margin-top:15px;font-size:13px;color:var(--muted)}"
    ".mono{font:13px ui-monospace,monospace}"
    ".mini{display:grid;gap:6px;font-size:11px}"
    ".mini-row{display:grid;grid-template-columns:70px 1fr;gap:8px;align-items:center}"
    ".mini-track{height:8px;position:relative;border-bottom:1px solid var(--line);"
    "background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),var(--line) 25%)}"
    ".mini-bar{position:absolute;height:5px;border-radius:4px;top:1px;background:var(--agent);min-width:2px}"
    ".mini-bar.code{background:var(--code)}.mini-bar.human{background:var(--human)}"
    ".mini-axis{margin:8px 0 0 78px;display:flex;justify-content:space-between;color:var(--muted);font-size:10px}"
    ".none{margin:12px 0;font-size:14px;line-height:1.5;color:var(--muted)}"
    "@media(max-width:850px){.grid{grid-template-columns:1fr}}"
)


def _runs_document(runs):
    """The document of the frame « Derniers runs »: a card for each run of
    ``runs``, or that the cockpit reads none."""
    anchors = Anchors()
    cards = "".join(_run_card(run, anchors) for run in runs)
    body = ('<div class="grid" %s>%s</div>' % (anchors("grid"), cards) if cards
            else '<p class="none">Aucun run récent n’est lu par le cockpit.</p>')
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><base target="_top">'
            "<style>%s</style></head><body>%s</body></html>" % (RUNS_CSS, body))


def _run_card(run, anchors):
    """One card: the workflow and the status of the run, its title and its
    step, a lane per participant with a bar per job, placed within the run,
    its axis, its start and its duration."""
    elapsed = run["elapsed"]
    card, top = anchors("card"), anchors("card-top")
    tone = run.get("tone")
    dot = '<span class="live-dot" %s></span>' % anchors("live-dot") if tone in ("wait", "live") else ""
    head = ('<div class="card-top" %s><span %s>%s</span><span class="badge %s" %s>%s%s</span></div>'
            % (top, anchors("span"), _e(run["type"]), tone if tone in ("wait", "live") else "", anchors("badge"),
               dot, _e(run["status"])))
    title = "<h2 %s>%s</h2><p %s>%s</p>" % (anchors("h2"), _e(run["title"]), anchors("p"), _e(run["step"]))
    mini = anchors("mini")
    rows = []
    for lane in run["lanes"]:
        row, name, track = anchors("mini-row"), anchors("span"), anchors("mini-track")
        bars = "".join('<span class="mini-bar %s" style="left:%s%%;width:%s%%" %s></span>'
                       % (_e(lane["kind"]), _n(100 * start / elapsed), _n(100 * (end - start) / elapsed),
                          anchors("mini-bar"))
                       for start, end in lane["jobs"])
        rows.append('<div class="mini-row" %s><span %s>%s</span><div class="mini-track" %s>%s</div></div>'
                    % (row, name, _e(lane["name"]), track, bars))
    axis = anchors("mini-axis")
    ticks = "".join("<span %s>%s</span>" % (anchors("span"), _tick(seconds)) for seconds in (0, elapsed / 2, elapsed))
    foot = anchors("card-foot")
    return (
        '<a class="card" href="/runs" %s>%s%s<div class="mini" %s>%s</div><div class="mini-axis" %s>%s</div>'
        '<div class="card-foot" %s><span %s>Début %s (Paris)</span><span class="mono" %s>%d min %d s</span></div></a>'
    ) % (card, head, title, mini, "".join(rows), axis, ticks, foot, anchors("span"), _e(run["started"]),
         anchors("mono"), elapsed // 60, elapsed % 60)


def _tick(seconds):
    """A mark of the axis of a card: « 0s », « 45s », « 6m », « 4m06s »."""
    seconds = int(round(seconds))
    minutes, rest = divmod(seconds, 60)
    if not minutes:
        return "%ds" % rest
    return "%dm%02ds" % (minutes, rest) if rest else "%dm" % minutes

CSS = """
:root{--pn-series-1:#415fce;--pn-series-2:#1c7954;--pn-series-3:#97691e}
@media (prefers-color-scheme: dark){:root{--pn-series-1:#91a7ff;--pn-series-2:#52c9b1;--pn-series-3:#e6ba70}}
.pn-overview-head small{display:block;margin-bottom:20px;color:var(--pn-muted-text);font-size:12px}
.pn-overview-head h1{font-size:27px;margin:0 0 6px}
.pn-overview small{color:var(--pn-muted-text);font-size:12px}
.pn-overview button{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:10px 14px;cursor:pointer}
.pn-overview button:hover{border-color:var(--accent)}
.pn-overview button:disabled{opacity:.5;cursor:not-allowed}
.pn-overview button.pn-link{padding:0;border:0;border-radius:4px;background:none;color:var(--accent)}
.pn-overview button.pn-link:hover{text-decoration:underline}
.pn-notice{padding:12px;border:1px solid var(--line);border-radius:6px;color:var(--pn-warn-text);margin-bottom:18px;
  overflow-wrap:anywhere}
.pn-metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
.pn-metric{border:1px solid var(--line);border-radius:10px;background:var(--surface);min-width:0}
.pn-metric>a{display:block;padding:18px;border-radius:10px;color:inherit;text-decoration:none}
.pn-metric:hover{border-color:var(--accent)}
.pn-metric.pn-emphasis{border-color:var(--accent)}
.pn-metric strong{display:block;font-size:28px;margin:7px 0}
.pn-metric small{display:block}
.pn-metric-label{font-size:13px;color:var(--pn-muted-text)}
.pn-activity summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-chart-key{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;margin:12px 0}
.pn-chart-key span:before{content:'';display:inline-block;width:20px;height:0;border-top:3px var(--dash) var(--series);
  vertical-align:middle;margin-right:8px}
.pn-sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);
  white-space:nowrap;border:0}
.pn-chart{width:100%;height:auto;max-height:290px;display:block}
.pn-activity p{margin:8px 0;color:var(--pn-muted-text);font-size:14px}
.pn-section-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:6px}
.pn-section-heading h2{margin:0}
.pn-runs{display:block;width:100%;height:330px;margin-top:12px;border:0;background:var(--surface)}
@media (max-width:850px){.pn-runs{height:890px}}
.pn-inbox{display:grid;grid-template-columns:330px minmax(0,1fr);gap:20px;align-items:start}
.pn-inbox>*{min-width:0}
.pn-requests{padding:0}
.pn-requests h2{padding:20px 20px 0}
.pn-requests>p{padding:0 20px 20px}
.pn-overview .pn-request{display:block;width:100%;text-align:left;border:0;border-top:1px solid var(--line);
  border-radius:0;padding:20px;background:transparent}
.pn-overview .pn-request[aria-current=true]{background:var(--pn-surface-2);box-shadow:inset 4px 0 0 var(--accent)}
.pn-request strong{display:block;margin-bottom:8px;overflow-wrap:anywhere}
.pn-request small{display:block;overflow-wrap:anywhere}
.pn-origin{display:block;margin-bottom:8px;font-size:14px;overflow-wrap:anywhere}
.pn-result h2{margin-top:12px;overflow-wrap:anywhere}
.pn-result>p{margin:0 0 8px}
.pn-resources{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:22px}
.pn-overview .pn-resource{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;width:100%;
  min-height:95px;padding:15px;text-align:left;border-color:var(--line)}
.pn-overview .pn-resource:disabled{opacity:1;cursor:default}
.pn-resource>span:first-child{display:flex;flex-direction:column;gap:4px;min-width:0;overflow-wrap:anywhere}
.pn-resources details{grid-column:1/-1}
.pn-result details{border-top:1px solid var(--line);padding:14px 0}
.pn-result>details{margin-top:8px}
.pn-result summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-result details p{font-size:14px;margin:10px 0 0;overflow-wrap:anywhere}
.pn-dock{display:flex;flex-wrap:wrap;gap:12px;align-items:center;border-top:1px solid var(--line);
  padding-top:18px;margin-top:22px}
.pn-dock>:is(button,.pn-button){flex:1;min-height:54px;font-size:16px;font-weight:650}
.pn-button{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;color:var(--ink);
  background:var(--surface);border:1px solid var(--pn-control-line);border-radius:8px;text-decoration:none}
.pn-button[aria-disabled=true]{opacity:.5;cursor:not-allowed}
.pn-unwired{flex-basis:100%;margin:0;font-size:13px;color:var(--pn-muted-text)}
.pn-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  border-bottom:1px solid var(--line)}
.pn-row:last-child{border-bottom:0}
.pn-row>*{min-width:0}
.pn-row strong{display:block;margin-bottom:5px;overflow-wrap:anywhere}
.pn-row small{display:block;overflow-wrap:anywhere}
.pn-project{display:block;padding:0}
.pn-project>a{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 0;
  color:inherit;text-decoration:none}
.pn-project>a>*{min-width:0}
.pn-project:hover strong{color:var(--accent)}
.pn-rows{display:grid}
.pn-stats{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:12px;font-size:12px;color:var(--pn-muted-text)}
.pn-release{margin-top:8px;font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.pn-skeleton{height:16px;background:var(--line);border-radius:5px;margin:14px 0;width:65%}
.pn-skeleton:nth-of-type(2){width:85%}
.pn-error{border-left:3px solid var(--pn-warn-text);padding:20px;background:var(--surface);margin-bottom:20px}
.pn-error h2{font-size:19px;margin:0 0 10px}
.pn-error p{margin:0 0 14px}
.pn-empty{text-align:center;padding:55px 20px}
.pn-empty p{color:var(--pn-muted-text)}
.pn-legacy{margin-top:28px;border-top:1px solid var(--line);padding-top:16px}
.pn-legacy>summary{cursor:pointer;color:var(--pn-muted-text)}
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
    var target = detail || legacy.querySelector('summary');
    target.scrollIntoView({block: 'start'});
    // The focus goes where the page went: the keyboard goes on from the
    // detail, not from a line now out of sight.
    if (target.tabIndex < 0 && !target.hasAttribute('tabindex')) { target.setAttribute('tabindex', '-1'); }
    target.focus({preventScroll: true});
  }
  // The frame of the last runs is as tall as its cards: none is cut, none
  // is scrolled to inside the page.
  function fit(frame) {
    var doc = frame.contentDocument;
    if (doc && doc.body) { frame.style.height = Math.ceil(doc.body.getBoundingClientRect().height) + 'px'; }
  }
  document.querySelectorAll('iframe.pn-runs').forEach(function (frame) {
    frame.addEventListener('load', function () { fit(frame); });
    if (frame.contentDocument && frame.contentDocument.readyState === 'complete') { fit(frame); }
  });
  window.addEventListener('resize', function () { document.querySelectorAll('iframe.pn-runs').forEach(fit); });
  document.addEventListener('click', function (event) {
    var request = event.target.closest('[data-request]');
    if (request) { openRequest(request.getAttribute('data-request')); }
  });
})();
</script>
"""
