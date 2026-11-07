"""The destination Analyses of Panorama: the four indicators of the factory,
each its view, and the daily volumes that compare, over the seven days that
end today (D, af-ten1sp; Spec af-fgcw0d, user stories 148, 149, 150, 124
and 175).

It follows the Analyses reference (prototypes/c01-complete/frozen-panorama-
analysis at 632deea): a lead, the tabs of the four views, then one panel --
its heading, its value, what is behind it and, folded, its method. Every
number comes from ``cockpit.analyses.indicators``, computed from the sources
the cockpit reads; a source not read shows its indicator unavailable with
the reason, never a zero.

Corrective deviations from the reference, its rendering defects not copied:
the chart draws the volumes its label names, one line a series, each told
apart by its dashes too, and says its unit; a merged result is dated by its
own day, where the reference says « avant-hier » of a day its chart counts
none, and every result counted is listed, not three of them; the tabs are
links to their view, opened with the keyboard as with a click; the method
says each of its parts on its line; « Délais » shows the portions the flow
dates, not those no record times. The anchors are numbered as the
reference numbers them (tests/cockpit-criteria/commands/analyses-
destination-layout-test.py holds every one).
"""
import html
from datetime import datetime, timedelta

from cockpit.analyses.indicators import CI, DECISIONS, DELAY, RESULTS, delay_text
from cockpit.core.readmodel import PARIS
from cockpit.ui.panorama.shell import anchor_slug

# The views, by the key of their address: their tab, their indicator, their
# heading and the label of their method.
VIEWS = (
    ("resultats", "Résultats", RESULTS, "Résultats fusionnés", "Définition et sources"),
    ("delais", "Délais", DELAY, "Où passe le temps ?", "Méthode et couverture"),
    ("verifications", "Vérifications", CI, "Vérifications CI réussies", "Définition et sources"),
    ("activite", "Activité", DECISIONS, "Décisions ouvertes", "Définition et sources"),
)
DEFAULT_VIEW = "resultats"
CHART_LABEL = ("Volumes quotidiens comparés sur sept jours : résultats fusionnés, PR fusionnées, tickets livrés, "
               "exécutions CI réussies")
# Each series its colour and its dashes, so that it is told apart without
# its colour.
SERIES_STYLE = {
    "Résultats fusionnés": ("var(--an-1)", ""),
    "PR fusionnées": ("var(--an-2)", "8 5"),
    "Tickets livrés": ("var(--an-3)", "1 5"),
    "Exécutions CI réussies": ("var(--an-4)", "12 4 2 4"),
}
WEEKDAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
# The frame of the chart: the days along x from x 55, the volumes along y
# from y 195 (none) up to 162 px higher.
CHART_ZERO, CHART_HEIGHT, CHART_LEFT, CHART_RIGHT = 195, 162, 55, 685
METHOD = (("reason", "Raison"), ("population", "Population"), ("period", "Période"), ("sources", "Sources"),
          ("read", "Horodatage"), ("calculation", "Calcul"))
UNMEASURED = ("La préparation avant la publication du graphe n’est pas comptée. Attente de départ, relectures et "
              "évaluation sont comprises dans « Réalisation et vérifications » : le flux ne les date pas séparément.")


def _e(value):
    return html.escape(str(value), quote=True)


def view_key(asked):
    """The view asked at the address (``?vue=``), the first one otherwise."""
    return asked if asked in {key for key, *_ in VIEWS} else DEFAULT_VIEW


def render_analyses(data, view):
    """The ``main`` of the destination on ``view``, from ``data`` (what
    ``cockpit.analyses.indicators.analyses`` gives): a function that draws it
    with the numbering of the page."""
    view = view_key(view)
    _, _, key, heading, method_label = next(entry for entry in VIEWS if entry[0] == view)
    indicator = data["indicators"][key]

    def draw(anchors):
        tabs = "".join(
            '<a class="an-tab%s" href="/analyses?vue=%s"%s %s>%s</a>'
            % (" on" if name == view else "", name, ' aria-current="page"' if name == view else "",
               anchors("primary" if name == view else "a"), _e(label))
            for name, label, *_ in VIEWS)
        head = ('<h1 class="an-title" %s>Analyses</h1><p class="an-lead" %s>Toute l’usine · %d derniers jours</p>'
                '<div class="an-tabs" %s>%s</div>'
                % (anchors("h1"), anchors("page-lead"), len(data["days"]), anchors("metric-tabs"), tabs))
        panel, h2, lead = anchors("panel"), anchors("h2"), anchors("p")
        body = {"resultats": _results, "delais": _delays, "verifications": _checks, "activite": _decisions}[view]
        headline, content = body(data, indicator, anchors)
        method = "".join('<p %s>%s : %s</p>' % (anchors("p"), label, _e(indicator[field]))
                         for field, label in METHOD if indicator.get(field))
        details = '<details class="an-def" %s><summary %s>%s</summary>%s</details>' % (
            anchors("details"), anchors("summary"), method_label, method)
        return head + '<section class="pn-panel an-panel" %s><h2 %s>%s</h2><p class="an-head" %s>%s</p>%s%s</section>' % (
            panel, h2, _e(heading), lead, headline, content, details)

    return draw


def _unavailable(what, indicator):
    """« Résultats indisponibles : les runs ne sont plus à jour (…) »: the
    headline of an indicator without a value, its reason said."""
    return "%s : %s" % (what, _e(indicator["reason"]))


def _results(data, indicator, anchors):
    if indicator["value"] is None:
        return _unavailable("Résultats indisponibles", indicator), _chart(data, anchors)
    else:
        count = int(indicator["value"])
        headline = "<strong %s>%s</strong> sur sept jours · fusion prouvée" % (
            anchors("strong"), "%d résultat%s" % (count, "s" if count > 1 else "") if count else "Aucun résultat")
    items = "".join(
        '<div %s><strong %s>%s</strong><small %s>%s · %s</small></div>'
        % (anchors("div"), anchors("strong"), _e(result["title"]), anchors("small"), _e(result["project"] or "Sans projet"),
           _day_word(result["merged"], data["now"]))
        for result in data["results"])
    history = '<div class="an-history" %s>%s</div>' % (
        anchors("metrics-history"), items or '<p class="an-muted">Aucun résultat fusionné sur la période.</p>')
    return headline, _chart(data, anchors) + history


def _delays(data, indicator, anchors):
    if indicator["value"] is None:
        return _unavailable("Délai médian indisponible", indicator), ""
    count = len(data["results"])
    headline = "Délai médian : <strong %s>%s</strong> · %d résultat%s fusionné%s" % (
        anchors("strong"), _e(indicator["value"]), count, "s" * (count > 1), "s" * (count > 1))
    key = ('<div class="an-key" %s><span style="--series:var(--accent)" %s>Travail et vérifications</span>'
           '<span style="--series:var(--warn)" %s>Attentes</span></div>'
           % (anchors("chart-key"), anchors("span"), anchors("span")))
    longest = max([portion["median"] or 0 for portion in data["portions"]] + [1])
    rows = "".join(
        '<div class="an-duration" %s><span %s>%s</span><div class="an-track" %s><div class="an-bar%s" '
        'style="width:%.1f%%" %s></div></div><strong %s>%s</strong></div>'
        % (anchors("duration-row"), anchors("span"), _e(portion["label"]), anchors("div"),
           " wait" if portion["wait"] else "", 100 * (portion["median"] or 0) / longest, anchors("duration-bar"),
           anchors("strong"), _e(delay_text(portion["median"])) if portion["median"] is not None else "non daté")
        for portion in data["portions"])
    notice = '<div class="an-notice" %s>%s</div>' % (anchors("notice"), _e(UNMEASURED))
    return headline, key + rows + notice


def _checks(data, indicator, anchors):
    if indicator["value"] is None:
        headline = _unavailable("Taux indisponible", indicator)
    else:
        headline = "<strong %s>%s</strong> des exécutions CI terminées ont réussi · %s" % (
            anchors("strong"), _e(indicator["value"]), _e(indicator["calculation"]))
    note = ('<p class="an-muted">Ce taux n’est pas tracé avec les volumes quotidiens : ce n’est pas la même unité. '
            'Les exécutions réussies par jour sont dans le graphique de « Résultats ».</p>')
    return headline, note


def _decisions(data, indicator, anchors):
    if indicator["value"] is None:
        return _unavailable("Décisions indisponibles", indicator), ""
    count = int(indicator["value"])
    headline = "<strong %s>%s</strong> · elles attendent ta réponse" % (
        anchors("strong"), "%d décision%s ouverte%s" % (count, "s" * (count > 1), "s" * (count > 1))
        if count else "Aucune décision ouverte")
    items = "".join('<div %s><strong %s>%s</strong><small %s>%s</small></div>'
                    % (anchors("div"), anchors("strong"), _e(decision["quoi"]), anchors("small"),
                       _e(decision["projet"] or "Sans projet"))
                    for decision in data["decisions"])
    link = '<p><a class="an-link" href="/#pn-inbox">Répondre depuis la Vue d’ensemble</a></p>' if count else ""
    return headline, ('<div class="an-history" %s>%s</div>' % (anchors("metrics-history"), items) if items else "") + \
        link + _answered(data)


def _answered(data):
    """The decisions answered over the period, as the journal records them."""
    if data["answered"] is None:
        return '<p class="an-muted">Décisions répondues sur la période : indisponibles, %s.</p>' % _e(
            data["answered_reason"])
    count = len(data["answered"])
    if not count:
        return '<p class="an-muted">Aucune décision répondue sur la période, selon le journal.</p>'
    items = "".join("<li>%s · %s</li>" % (_e(item["title"]), _day_word(item["at"], data["now"]))
                    for item in data["answered"])
    return ('<p class="an-muted">%d décision%s répondue%s sur la période, selon le journal :</p>'
            '<ul class="an-answered">%s</ul>' % (count, "s" * (count > 1), "s" * (count > 1), items))


def _chart(data, anchors):
    """The daily volumes on one chart, one unit -- a count per day -- for
    every series read; a series not read is said unavailable in the key and
    not drawn."""
    days, volumes = data["days"], data["volumes"]
    key = "".join(
        '<span style="--series:%s;--dash:%s" %s>%s%s</span>'
        % (SERIES_STYLE[serie["label"]][0], _dash(SERIES_STYLE[serie["label"]][1]), anchors("span"),
           _e(serie["label"]), "" if serie["values"] is not None else " : indisponible")
        for serie in volumes)
    drawn = [serie for serie in volumes if serie["values"] is not None]
    # The series not drawn, grouped by the reason their source gives.
    reasons = {}
    for serie in volumes:
        if serie["values"] is None:
            reasons.setdefault(serie["reason"], []).append(serie["label"])
    missing = "".join('<p class="an-muted">Non tracées : %s — %s.</p>' % (_e(", ".join(labels)), _e(reason))
                      for reason, labels in reasons.items())
    top = max([3] + [value for serie in drawn for value in serie["values"]])
    top = -(-top // 3) * 3
    step = (CHART_RIGHT - CHART_LEFT) / max(1, len(days) - 1)
    y = lambda value: CHART_ZERO - CHART_HEIGHT * value / top
    shapes = ['<g stroke="var(--line)" %s>%s</g>' % (anchors("g"), "".join(
        '<line x1="40" y1="%.1f" x2="695" y2="%.1f" %s></line>' % (y(tick), y(tick), anchors("line"))
        for tick in (0, top / 3, 2 * top / 3, top)))]
    shapes.append('<g fill="var(--muted)" font-size="11" %s>%s%s<text x="40" y="20" %s>nombre par jour</text></g>' % (
        anchors("g"),
        "".join('<text x="20" y="%.1f" %s>%d</text>' % (y(tick) + 4, anchors("text"), tick)
                for tick in (0, top // 3, 2 * top // 3, top)),
        "".join('<text x="%.1f" y="222" text-anchor="middle" %s>%s</text>'
                % (CHART_LEFT + step * i, anchors("text"), WEEKDAYS[day.weekday()]) for i, day in enumerate(days)),
        anchors("text")))
    for serie in drawn:
        colour, dashes = SERIES_STYLE[serie["label"]]
        points = [(CHART_LEFT + step * i, y(value)) for i, value in enumerate(serie["values"])]
        shapes.append('<polyline fill="none" stroke="%s" stroke-width="2.5" stroke-linejoin="round" '
                      'stroke-linecap="round"%s points="%s" %s></polyline>'
                      % (colour, ' stroke-dasharray="%s"' % dashes if dashes else "",
                         " ".join("%.1f,%.1f" % point for point in points), anchors("polyline")))
        shapes += ['<circle cx="%.1f" cy="%.1f" r="4" fill="%s" %s><title %s>%s · %s %s : %d</title></circle>'
                   % (x, cy, colour, anchors("circle"), anchors("title"), _e(serie["label"]),
                      WEEKDAYS[day.weekday()], day.strftime("%d/%m"), value)
                   for (x, cy), day, value in zip(points, days, serie["values"])]
    table = ('<div class="an-sr-only"><table><caption>%s, par jour</caption><tr><th scope="col">Série</th>%s</tr>%s'
             '</table></div>'
             % (_e(CHART_LABEL), "".join('<th scope="col">%s</th>' % day.strftime("%d/%m") for day in days),
                "".join('<tr><th scope="row">%s</th>%s</tr>' % (
                    _e(serie["label"]), "".join("<td>%d</td>" % value for value in serie["values"])) for serie in drawn)))
    return ('<div class="an-key" %s>%s</div><svg class="an-chart" viewBox="0 0 720 235" role="img" aria-label="%s" '
            'data-anchor="%s-1">%s</svg>%s%s' % (anchors("chart-key"), key, _e(CHART_LABEL), anchor_slug(CHART_LABEL),
                                                 "".join(shapes), missing, table))


def _dash(dashes):
    return "dashed" if dashes.startswith("8") else "dotted" if dashes.startswith("1 ") else \
        "double" if dashes else "solid"


def _day_word(at, now):
    """The day a result was merged, in words up to the day before
    yesterday, then by its date."""
    day, today = datetime.fromtimestamp(at, tz=PARIS).date(), datetime.fromtimestamp(now, tz=PARIS).date()
    words = {today: "aujourd’hui", today - timedelta(days=1): "hier", today - timedelta(days=2): "avant-hier"}
    return words.get(day, "le %s" % day.strftime("%d/%m"))


CSS = """
:root{--an-1:#415fce;--an-2:#1c7954;--an-3:#97691e;--an-4:#8a3ea8}
@media (prefers-color-scheme: dark){:root{--an-1:#91a7ff;--an-2:#52c9b1;--an-3:#e6ba70;--an-4:#d39cf0}}
.an-title{font-size:27px;margin:0 0 6px}
.an-lead{margin:0 0 16px;color:var(--pn-muted-text)}
.pn-main .an-lead{line-height:1.6}
.an-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.an-tab{padding:8px 13px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);
  text-decoration:none;font-size:14px}
.an-tab:hover{border-color:var(--accent)}
.an-tab.on{background:var(--pn-surface-2);border-color:var(--accent)}
.an-head{margin:0 0 14px!important;color:var(--pn-muted-text)}
.an-head strong{color:var(--ink)}
.an-key{display:flex;gap:8px 20px;flex-wrap:wrap;font-size:13px;margin:12px 0;color:var(--pn-muted-text)}
.an-key span:before{content:'';display:inline-block;width:20px;height:0;margin-right:6px;vertical-align:middle;
  border-top:3px var(--dash,solid) var(--series)}
.an-chart{width:100%;height:auto;max-height:290px;display:block;margin-bottom:14px}
.an-sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);
  white-space:nowrap;border:0}
.an-sr-only *{clip-path:inset(50%)}
.an-history{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.an-history>div{border:1px solid var(--line);border-radius:8px;padding:12px 14px;min-width:0}
.an-history strong{display:block;overflow-wrap:anywhere}
.an-history small{display:block;margin-top:5px;color:var(--pn-muted-text);font-size:13px}
.an-duration{display:grid;grid-template-columns:minmax(150px,220px) minmax(0,1fr) 70px;gap:12px;align-items:center;
  padding:8px 0;border-bottom:1px solid var(--line)}
.an-track{height:10px;background:var(--pn-surface-2);border-radius:5px;overflow:hidden}
.an-bar{height:100%;background:var(--accent);border-radius:5px}
.an-bar.wait{background:var(--warn)}
.an-duration strong{text-align:right}
.an-notice{margin-top:14px;padding:12px 14px;border:1px solid var(--line);border-radius:8px;font-size:14px;
  line-height:normal;color:var(--ink)}
.an-muted{color:var(--pn-muted-text)}
.an-link{color:var(--ink)}
.an-answered{margin:6px 0 0;padding-left:20px;font-size:14px;overflow-wrap:anywhere}
.an-def{margin-top:16px;font-size:14px}
.an-def summary{cursor:pointer;color:var(--pn-muted-text)}
.an-def p{margin:8px 0 0!important}
@media (max-width:800px){
  .an-title{font-size:24px}
  .an-duration{grid-template-columns:minmax(0,1fr) auto}
  .an-duration .an-track{grid-column:1 / -1;grid-row:2}
  /* The chart shrinks with the page: its labels are drawn larger in its
     own units, so that they stay readable at 390 px. */
  .an-chart text{font-size:22px}
}
"""
