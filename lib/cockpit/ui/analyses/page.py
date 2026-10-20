"""The destination « Analyses » of B/Panorama (T42 Prototype Fold, af-muqyxm;
Spec af-2zseit, user stories 124, 149, 150 and 175; Validated Prototype
prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-analysis).

    view = analyses_view(snapshot, tab)
    main_html = render_analyses(view, anchors)

:func:`analyses_view` reads, from the read model's snapshot, what each tab
of the destination shows; :func:`render_analyses` draws the tab open,
inside the shell of :mod:`cockpit.ui.panorama.shell`. Neither reads a
source.

The tracker keeps each view as it is said, one bead under its heading
(« Résultats fusionnés », « Où passe le temps ? »): its lines in their
order, the marks of its drawing (« Résultats fusionnés · Lundi : 1 »,
« Attentes · Attente de départ : 12 ») and, after the label of the part
that unfolds (« Définition et sources », « Méthode et couverture »), what
that part says open. A view the tracker holds nothing for, and the tabs
the reference does not draw (« Vérifications », « Activité »), say that
nothing is collected for them -- no figure is drawn that no source gave.

The tabs are links of the page: each opens its view at GET /analyses
(``?vue=``), by a click or Enter, with no script. The tab open is marked as
the one open (``aria-current``), and drawn filled and bold.

Every part carries the anchor of the reference (``data-anchor``), numbered
by the :class:`~cockpit.ui.panorama.shell.Anchors` of the page as the frozen
pages number them.
"""
import html
import re
from datetime import datetime

from cockpit.core.freshness import FRESH
from cockpit.core.readmodel import PARIS
from cockpit.ui.home.overview import CHART_DAYS, CHART_HEIGHT, CHART_STEP, CHART_ZERO
from cockpit.ui.panorama.shell import anchor_slug

PATH = "/analyses"
LOADING, ERROR, CONTENT = "loading", "error", "content"
RESULTS, TIME, CHECKS, ACTIVITY = "resultats", "delais", "verifications", "activite"
# The tabs, in the order of the reference: key, label.
TABS = ((RESULTS, "Résultats"), (TIME, "Délais"), (CHECKS, "Vérifications"), (ACTIVITY, "Activité"))
SCOPE = "Toute l’usine · 7 derniers jours"
SAID = "said"

MERGED_HEADING = "Résultats fusionnés"
DEFINITION = "Définition et sources"
# The anchor of the chart, as the reference names it (its label there).
CHART_ANCHOR = anchor_slug("Volumes quotidiens comparés sur sept jours : PR fusionnées, tickets livrés, "
                           "exécutions CI réussies") + "-1"
TIME_HEADING = "Où passe le temps ?"
METHOD = "Méthode et couverture"
WORK, WAITS = "Travail et vérifications", "Attentes"
NOTICE = "À examiner"
# The tabs the reference does not draw: what each would show, and that no
# source gives it yet.
NOT_COLLECTED = {
    CHECKS: ("Vérifications CI réussies", "Vérifications non collectées : aucune source ne les fournit encore au "
             "cockpit."),
    ACTIVITY: ("Activité sur 7 jours", "Volumes quotidiens non collectés : aucune source ne les fournit encore au "
               "cockpit."),
}

# A mark of a drawing: « série · point : valeur ».
MARK = re.compile(r"^(?P<series>.+?) · (?P<point>[^·]+?) : (?P<value>\d+(?:[.,]\d+)?)$")
# What is said under a merged result: « projet · quand ».
UNDER = re.compile(r"^[^·]+ · [^·]+$")
COUNT = re.compile(r"^(?P<count>\d+ \S+)(?P<rest>.*)$")


def analyses_view(snapshot, tab=None):
    """What the destination shows: ``state`` (``loading``: the tracker has
    not answered yet; ``error``: its read failed; ``content``), ``stale``
    (HH:MM of the last reading, or None when it is current), ``tab`` (the
    one open: ``tab`` if it is one, else the first view the tracker holds),
    ``results`` and ``time`` (None when the tracker holds nothing for
    them)."""
    beads_row = snapshot.get("beads")
    view = {"state": CONTENT, "stale": None, "tab": tab, "results": None, "time": None}
    if beads_row is None or beads_row["value"] is None:
        view["state"] = ERROR if (beads_row or {}).get("failed_at") is not None else LOADING
    else:
        said = {bead.get("title"): _lines(bead) for bead in beads_row["value"]
                if isinstance(bead, dict) and SAID in (bead.get("labels") or [])}
        view["results"] = _results(said.get(MERGED_HEADING))
        view["time"] = _time(said.get(TIME_HEADING))
        if beads_row["freshness"] != FRESH and beads_row["read_at"] is not None:
            view["stale"] = datetime.fromtimestamp(beads_row["read_at"], tz=PARIS).strftime("%H:%M")
    if tab not in dict(TABS):
        view["tab"] = TIME if view["time"] and not view["results"] else RESULTS
    return view


def _lines(bead):
    return [line.strip() for line in (bead.get("description") or "").split("\n") if line.strip()]


def _unfolded(lines, label):
    """The lines of `lines` before the label of the part that unfolds, and
    what that part says open (the lines after it that are no mark)."""
    if label not in lines:
        return lines, []
    at = lines.index(label)
    return lines[:at], [line for line in lines[at + 1:] if not MARK.match(line)]


def _marks(lines):
    """The marks of a drawing among `lines`: (series, point, value)."""
    return [(m["series"], m["point"], float(m["value"].replace(",", "."))) for m in map(MARK.match, lines) if m]


def _results(lines):
    """« Résultats fusionnés »: the summary, the volume of each day of the
    week (Monday first, all seven or none), the ticks of its scale, the
    merged results (title, project and when) and how they are counted."""
    if not lines:
        return None
    shown, definition = _unfolded(lines, DEFINITION)
    days = {point: value for series, point, value in _marks(lines) if series == MERGED_HEADING}
    volumes = [days[day] for _, day in CHART_DAYS] if all(day in days for _, day in CHART_DAYS) else None
    body = [line for line in shown[1:] if not MARK.match(line) and line != MERGED_HEADING]
    merged = [(title, under) for title, under in zip(body, body[1:]) if UNDER.match(under) and not UNDER.match(title)]
    return {"summary": shown[0], "volumes": volumes, "ticks": _ticks(body, volumes), "merged": merged,
            "definition": definition}


def _ticks(lines, volumes):
    """The four ticks of the scale: those the source says (four numbers
    from 0, evenly spaced, the last at least the largest volume), else
    0 to a multiple of 3 that holds the largest volume."""
    said = [int(line) for line in lines if line.isdigit()]
    top = max(volumes or [0])
    if len(said) == 4 and said[0] == 0 and said[3] >= top and said[1] > 0 and said == [said[1] * n for n in range(4)]:
        return said
    top = max(3, -(-int(top) // 3) * 3)
    return [0, top // 3, 2 * top // 3, top]


def _time(lines):
    """« Où passe le temps ? »: the summary, each part of the lead time
    (label, minutes, a wait or not), the notice of what is to look at, and
    how it is computed."""
    if not lines:
        return None
    shown, method = _unfolded(lines, METHOD)
    rows = [(point, value, series == WAITS) for series, point, value in _marks(lines) if series in (WORK, WAITS)]
    notice = next((line for line in shown if line.startswith(NOTICE)), None)
    return {"summary": shown[0], "rows": rows, "notice": notice, "method": method}


# --- rendering -----------------------------------------------------------------

def _e(text):
    return html.escape(str(text))


def _n(number):
    """A number as the reference writes it: no ``.0``."""
    return ("%.2f" % number).rstrip("0").rstrip(".")


def _minutes(minutes):
    """« 18 min », « 2 h 40 »."""
    hours, rest = divmod(int(round(minutes)), 60)
    return "%d min" % rest if not hours else "%d h %02d" % (hours, rest)


def tab_link(key, label, anchor):
    """A tab that opens its view: the button of a form of its own sent by
    GET to the destination -- Enter or a click opens it, with no script."""
    return ('<form class="pn-open" method="get" action="%s"><input type="hidden" name="vue" value="%s">'
            '<button type="submit" class="pn-tab" %s>%s</button></form>') % (PATH, key, anchor, _e(label))


def render_analyses(view, anchors):
    """The ``main`` of the destination for ``view``, numbered by
    ``anchors`` as the reference numbers its parts."""
    lead = SCOPE if view["stale"] is None else "%s · lecture périmée à %s (Paris), état actuel inconnu" % (
        SCOPE, view["stale"])
    parts = ['<h1 %s>Analyses</h1><p class="pn-lead" %s>%s</p>' % (anchors("h1"), anchors("page-lead"), _e(lead))]
    tabs = anchors("metric-tabs")
    links = []
    for key, label in TABS:
        if key == view["tab"]:
            links.append('<button type="button" class="pn-tab" aria-current="true" %s>%s</button>'
                         % (anchors("primary"), _e(label)))
        else:
            links.append(tab_link(key, label, anchors("button")))
    parts.append('<div class="pn-tabs" %s>%s</div>' % (tabs, "".join(links)))
    if view["state"] == LOADING:
        parts.append(_panel(anchors, "Lecture en cours…", "Les analyses s’affichent dès que la source répond."))
    elif view["state"] == ERROR:
        # The page is read again from the sources, then served again.
        parts.append(
            '<section class="pn-panel" role="alert" %s><h2 %s>Cette vue est indisponible</h2>'
            "<p %s>L’état réel est inconnu. Les sources de l’usine n’ont pas répondu.</p>"
            '<form method="post" action="/api/health/recheck"><button type="submit" class="pn-tab" %s>Réessayer'
            "</button></form></section>" % (anchors("panel"), anchors("h2"), anchors("p"), anchors("button")))
    elif view["tab"] == RESULTS:
        parts.append(_render_results(view["results"], anchors))
    elif view["tab"] == TIME:
        parts.append(_render_time(view["time"], anchors))
    else:
        parts.append(_panel(anchors, *NOT_COLLECTED[view["tab"]]))
    return "".join(parts)


def _panel(anchors, heading, text):
    return '<section class="pn-panel" %s><h2 %s>%s</h2><p %s>%s</p></section>' % (
        anchors("panel"), anchors("h2"), _e(heading), anchors("p"), _e(text))


def _summary(text, anchors, strong):
    """The line under the heading of a view, its figure in bold: the count
    that opens it, or the value after « : »."""
    if strong == "count":
        found = COUNT.match(text)
        head, figure, rest = "", found and found["count"], found and found["rest"]
    else:
        head, _, after = text.partition(" : ")
        figure, sep, rest = after.partition(" · ")
        head, rest = head + " : ", sep + rest
    if not figure:
        return "<p %s>%s</p>" % (anchors("p"), _e(text))
    return "<p %s>%s<strong %s>%s</strong>%s</p>" % (anchors("p"), _e(head), anchors("strong"), _e(figure), _e(rest))


def _render_results(results, anchors):
    """« Résultats fusionnés »: the summary, the chart of each day, the
    merged results, how they are counted."""
    if results is None:
        results = {"summary": "Résultats fusionnés non collectés : aucune source ne les fournit encore au cockpit.",
                   "volumes": None, "merged": [], "definition": []}
    panel, heading = anchors("panel"), anchors("h2")
    parts = ['<section class="pn-panel" %s><h2 %s>%s</h2>' % (panel, heading, _e(MERGED_HEADING)),
             _summary(results["summary"], anchors, "count"),
             '<div class="pn-chart-key" %s><span style="--series:var(--pn-series-1)" %s>%s</span></div>'
             % (anchors("chart-key"), anchors("span"), _e(MERGED_HEADING)),
             _chart(results, anchors)]
    history = anchors("metrics-history")
    if results["merged"]:
        items = "".join('<div %s><strong %s>%s</strong><small %s>%s</small></div>'
                        % (anchors("div"), anchors("strong"), _e(title), anchors("small"), _e(under))
                        for title, under in results["merged"])
    else:
        items = "<p>Aucun résultat fusionné lu sur la période.</p>"
    parts.append('<div class="pn-history" %s>%s</div>' % (history, items))
    parts.append(_details(DEFINITION, results["definition"], anchors))
    parts.append("</section>")
    return "".join(parts)


def _chart(results, anchors):
    """The volume of each day, Monday to Sunday, on the scale of its ticks,
    said in its name to a reader that does not see it; without the seven
    volumes, its grid only, and that they are not collected."""
    volumes = results["volumes"]
    if volumes is None:
        label = "Résultats fusionnés par jour : non collectés"
        grid = "".join('<line x1="40" y1="%d" x2="695" y2="%d"></line>' % (y, y) for y in (195, 141, 87, 33))
        return ('<svg class="pn-chart" viewBox="0 0 720 235" role="img" aria-label="%s" data-anchor="%s">'
                '<g stroke="var(--line)">%s</g></svg><p class="pn-chart-note">Volumes quotidiens non collectés : '
                "aucune source ne les fournit encore au cockpit.</p>") % (_e(label), CHART_ANCHOR, grid)
    ticks = results["ticks"]
    scale = CHART_HEIGHT / ticks[-1]
    lines = "".join('<line x1="40" y1="%s" x2="695" y2="%s" %s></line>'
                    % (_n(CHART_ZERO - tick * scale), _n(CHART_ZERO - tick * scale), anchors("line"))
                    for tick in ticks)
    grid = '<g stroke="var(--line)" %s>%s</g>' % (anchors("g"), lines)
    g = anchors("g")
    texts = "".join('<text x="20" y="%s" %s>%s</text>' % (_n(CHART_ZERO + 4 - tick * scale), anchors("text"), tick)
                    for tick in ticks)
    texts += "".join('<text x="%d" y="222" %s>%s</text>' % (45 + CHART_STEP * day, anchors("text"), short)
                     for day, (short, _) in enumerate(CHART_DAYS))
    points = [(55 + CHART_STEP * day, _n(CHART_ZERO - volume * scale)) for day, volume in enumerate(volumes)]
    marks = ['<polyline fill="none" stroke="var(--pn-series-1)" stroke-width="2.5" stroke-linejoin="round" '
             'points="%s" %s></polyline>' % (" ".join("%d,%s" % point for point in points), anchors("polyline"))]
    for (x, y), volume, (_, day) in zip(points, volumes, CHART_DAYS):
        marks.append('<circle cx="%d" cy="%s" r="4" fill="var(--pn-series-1)" %s><title %s>%s · %s : %s</title>'
                     "</circle>" % (x, y, anchors("circle"), anchors("title"), _e(MERGED_HEADING), day, _n(volume)))
    label = "Résultats fusionnés par jour : %s" % ", ".join(
        "%s %s" % (day.lower(), _n(volume)) for (_, day), volume in zip(CHART_DAYS, volumes))
    return ('<svg class="pn-chart" viewBox="0 0 720 235" role="img" aria-label="%s" data-anchor="%s">%s'
            '<g fill="var(--pn-muted-text)" font-size="11" %s>%s</g>%s</svg>') % (
        _e(label), CHART_ANCHOR, grid, g, texts, "".join(marks))


def _render_time(time, anchors):
    """« Où passe le temps ? »: the median lead time, each of its parts --
    work and waits told apart by their bar, filled or hatched, and by
    their key --, what is to look at, how it is computed."""
    if time is None:
        return _panel(anchors, TIME_HEADING, "Délais non collectés : aucune source ne les fournit encore au cockpit.")
    panel, heading = anchors("panel"), anchors("h2")
    parts = ['<section class="pn-panel" %s><h2 %s>%s</h2>' % (panel, heading, _e(TIME_HEADING)),
             _summary(time["summary"], anchors, "value"),
             '<div class="pn-chart-key" %s><span class="pn-key-work" %s>%s</span><span class="pn-key-wait" %s>%s</span>'
             "</div>" % (anchors("chart-key"), anchors("span"), _e(WORK), anchors("span"), _e(WAITS))]
    longest = max([minutes for _, minutes, _ in time["rows"]] or [0]) or 1
    for label, minutes, wait in time["rows"]:
        parts.append(
            '<div class="pn-duration" %s><span %s>%s</span><div %s><div class="pn-bar%s" style="width:%s%%" %s>'
            "</div></div><strong %s>%s</strong></div>"
            % (anchors("duration-row"), anchors("span"), _e(label), anchors("div"), " pn-wait" if wait else "",
               _n(100 * minutes / longest), anchors("duration-bar"), anchors("strong"), _minutes(minutes)))
    if time["notice"]:
        parts.append('<div class="pn-notice" %s>%s</div>' % (anchors("notice"), _e(time["notice"])))
    parts.append(_details(METHOD, time["method"], anchors))
    parts.append("</section>")
    return "".join(parts)


def _details(label, paragraphs, anchors):
    """A part that unfolds: its label, and what the source says of it open,
    or that it said nothing."""
    details, summary = anchors("details"), anchors("summary")
    body = "".join("<p %s>%s</p>" % (anchors("p"), _e(text)) for text in paragraphs) or (
        "<p %s>Contenu non fourni par la source.</p>" % anchors("p"))
    return "<details %s><summary %s>%s</summary>%s</details>" % (details, summary, _e(label), body)


CSS = """
.pn-main>h1{font-size:27px;margin:0 0 20px}
.pn-main .pn-lead{color:var(--pn-muted-text);margin:-10px 0 24px;line-height:1.6;overflow-wrap:anywhere}
.pn-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:15px 0 25px}
.pn-tab{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--pn-control-line);
  border-radius:8px;padding:10px 14px;cursor:pointer}
.pn-tab:hover{border-color:var(--accent)}
.pn-tab[aria-current=true]{background:var(--accent);border-color:var(--accent);color:var(--pn-accent-ink);
  font-weight:700;cursor:default}
.pn-main .pn-panel p strong{font-weight:700}
.pn-chart-key{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;margin:12px 0}
.pn-chart-key span:before{content:'';display:inline-block;width:20px;height:3px;background:var(--series);
  vertical-align:middle;margin-right:8px}
.pn-chart-key .pn-key-work:before{height:10px;background:var(--accent)}
.pn-chart-key .pn-key-wait:before{height:10px;background:repeating-linear-gradient(135deg,var(--warn) 0 3px,
  transparent 3px 6px);outline:1px solid var(--warn);outline-offset:-1px}
.pn-chart{width:100%;height:auto;max-height:290px;display:block}
.pn-chart-note{color:var(--pn-muted-text);font-size:14px}
.pn-history{display:grid;gap:10px}
.pn-history>div{padding:14px;border-bottom:1px solid var(--line);min-width:0}
.pn-history strong{display:block;overflow-wrap:anywhere}
.pn-history small{display:block;margin-top:5px;font-size:12px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.pn-duration{display:grid;grid-template-columns:170px minmax(0,1fr) 90px;align-items:center;gap:18px;margin:15px 0;
  font-size:14px}
.pn-duration>*{min-width:0;overflow-wrap:anywhere}
.pn-bar{height:24px;border-radius:5px;background:var(--accent);min-width:3px}
.pn-bar.pn-wait{background:repeating-linear-gradient(135deg,var(--warn) 0 6px,transparent 6px 10px);
  box-shadow:inset 0 0 0 2px var(--warn)}
.pn-main .pn-notice{padding:12px;border:1px solid var(--line);border-radius:6px;color:var(--pn-warn-text);
  margin:18px 0;overflow-wrap:anywhere}
.pn-main details{border-top:1px solid var(--line);padding:16px 0}
.pn-main summary{cursor:pointer;color:var(--pn-muted-text)}
.pn-main details p{font-size:14px;margin:10px 0 0}
@media (max-width:800px){
  .pn-main>h1{font-size:24px}
  .pn-tab{font-size:12px}
  .pn-duration{grid-template-columns:115px minmax(0,1fr) 65px;gap:8px;font-size:12px}
  .pn-chart{min-height:190px}
  .pn-chart-key{gap:10px}
}
"""
