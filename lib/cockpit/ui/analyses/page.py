"""The destination Analyses of Panorama: what the factory delivered, how
long it took and how its checks answered, day by day, from the runs.

It follows the Analyses reference (prototypes/c01-complete/frozen-panorama-
analysis at 632deea): a period, four views (Résultats, Délais,
Vérifications, Activité), a chart a day and the items behind it, and how
each number is defined. Every number is computed from the runs the cockpit
reads (cockpit.runs) and the journal; nothing is drawn with example values.

Intent (Benjamin, his words, 2026-10-19 19:42 Paris): « enchaîne sur la
page suivante. »
Mechanism (agent interpretation): Analyses after Journal; built directly,
outside the paused convoy af-pqfxmd.
"""
import html
from datetime import datetime, timedelta

from cockpit.core.readmodel import PARIS
from cockpit.ui.runs.page import duration

VIEWS = (("resultats", "Résultats"), ("delais", "Délais"), ("verifications", "Vérifications"),
         ("activite", "Activité"))
PERIODS = (("7", "7 jours"), ("30", "30 jours"))
DAY_NAMES = ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim")


def _e(value):
    return html.escape(str(value), quote=True)


def _days(now, count):
    today = datetime.fromtimestamp(now, tz=PARIS).date()
    return [today - timedelta(days=count - 1 - i) for i in range(count)]


def _day_of(at):
    return datetime.fromtimestamp(at, tz=PARIS).date()


def _label(day, count):
    return DAY_NAMES[day.weekday()] if count <= 7 else day.strftime("%d/%m")


def _events(runs, prefix):
    for run in runs or []:
        for event in run["events"]:
            if event["text"].startswith(prefix):
                yield run, event


def compute(runs, entries, now, period):
    """The numbers of every view over ``period`` days: per day series and
    the items behind them."""
    days = _days(now, period)
    first = days[0]
    merged = [(run, e) for run, e in _events(runs, "Fusionné") if _day_of(e["at"]) >= first]
    launched = [(run, e) for run, e in _events(runs, "Ticket lancé") if _day_of(e["at"]) >= first]
    stopped = [(run, e) for run, e in _events(runs, "Arrêt") if _day_of(e["at"]) >= first]
    reviews = [(run, e) for run, e in _events(runs, "Revue de code") if _day_of(e["at"]) >= first]
    evaluations = [(run, e) for run, e in _events(runs, "Évaluation") if _day_of(e["at"]) >= first]
    fidelity = [(run, e) for run, e in _events(runs, "Fidélité") if _day_of(e["at"]) >= first]
    answers = [e for e in entries or [] if e.get("at") and _day_of(e["at"]) >= first and e.get("kind") == "decisions"]

    def per_day(pairs, keep=lambda run, e: True):
        counts = {day: 0 for day in days}
        for run, e in pairs:
            if keep(run, e) and _day_of(e["at"]) in counts:
                counts[_day_of(e["at"])] += 1
        return [counts[day] for day in days]

    lead = []
    for run, e in merged:
        lead.append((run, e["at"] - run["start"]))
    waits = []
    for run in runs or []:
        for lane in run["lanes"]:
            if lane["kind"] == "human":
                for start, end in lane["jobs"]:
                    if end > start and _day_of(run["start"] + start) >= first:
                        waits.append((run, end - start))
    blocking = lambda run, e: "bloquant" in e["text"] and "aucun bloquant" not in e["text"]
    return {
        "days": days,
        "merged": merged, "merged_per_day": per_day(merged),
        "lead": lead, "waits": waits,
        "reviews": reviews, "reviews_blocking": per_day(reviews, blocking),
        "reviews_clear": per_day(reviews, lambda run, e: not blocking(run, e)),
        "evaluations": evaluations,
        "evaluations_ok": per_day(evaluations, lambda run, e: "favorable" in e["text"] and "défavorable" not in e["text"]),
        "fidelity": fidelity,
        "launched_per_day": per_day(launched), "stopped_per_day": per_day(stopped),
        "answers_per_day": [sum(1 for e in answers if _day_of(e["at"]) == day) for day in days],
    }


def _chart(days, series, title):
    """Grouped bars, one group a day; ``series``: (label, values, css class)."""
    count = len(days)
    top = max([1] + [v for _, values, _ in series for v in values])
    width, height, pad = 640, 180, 28
    group = (width - pad) / count
    bar = max(2, min(18, (group - 6) / max(1, len(series))))
    shapes = []
    for i, day in enumerate(days):
        x0 = pad + i * group + (group - bar * len(series)) / 2
        for j, (label, values, css) in enumerate(series):
            h = (height - 30) * values[i] / top
            shapes.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"><title>%s · %s : %d</title></rect>'
                          % (css, x0 + j * bar, height - 20 - h, bar - 1, h, _e(label), _label(day, count), values[i]))
        if count <= 7 or i % max(1, count // 10) == 0:
            shapes.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>' % (pad + i * group + group / 2, height - 4,
                                                                                  _label(day, count)))
    for k in (0, top):
        y = height - 20 - (height - 30) * k / top
        shapes.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text x="0" y="%.1f">%d</text>' % (pad, width, y, y, y + 4, k))
    legend = "".join('<span><i class="%s"></i>%s : %d</span>' % (css, _e(label), sum(values)) for label, values, css in series)
    return ('<figure class="an-chart"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg>'
            '<figcaption>%s</figcaption></figure>' % (width, height, _e(title), "".join(shapes), legend))


def _items(rows, empty):
    if not rows:
        return '<p class="an-muted">%s</p>' % _e(empty)
    return '<ul class="an-items">%s</ul>' % "".join(
        '<li><a href="%s">%s</a><span>%s</span></li>' % (_e(href), _e(text), _e(side)) for href, text, side in rows)


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def render_analyses(runs, entries, now, view, period, checked=None):
    view = view if view in dict(VIEWS) else "resultats"
    period = period if period in dict(PERIODS) else "7"
    data = compute(runs, entries, now, int(period))
    days = data["days"]
    tabs = "".join('<a class="an-tab%s" href="/analyses?vue=%s&periode=%s"%s>%s</a>'
                   % (" on" if key == view else "", key, period, ' aria-current="page"' if key == view else "", label)
                   for key, label in VIEWS)
    periods = "".join('<a class="an-tab%s" href="/analyses?vue=%s&periode=%s">%s</a>'
                      % (" on" if key == period else "", view, key, label) for key, label in PERIODS)
    if view == "resultats":
        n = len(data["merged"])
        head = "%d résultat%s fusionné%s sur %s · fusion prouvée par le flux" % (n, "s" * (n > 1), "s" * (n > 1), dict(PERIODS)[period])
        body = _chart(days, [("Fusionnés", data["merged_per_day"], "s1")], "Résultats fusionnés par jour") + _items(
            [(run["href"], "%s · %s" % (run["ticket"], run["title"]), datetime.fromtimestamp(e["at"], tz=PARIS).strftime("%d/%m %H:%M"))
             for run, e in sorted(data["merged"], key=lambda p: -p[1]["at"])], "Aucun résultat fusionné sur la période.")
        definition = "Un résultat fusionné est un run dont le flux a écrit la fusion (gc.flow.merge, outcome merged)."
    elif view == "delais":
        lead = _median([d for _, d in data["lead"]])
        wait = _median([d for _, d in data["waits"]])
        head = "Délai médian lancement → fusion : %s · attente médiane d’une décision : %s" % (
            duration(lead) if lead is not None else "non mesurable", duration(wait) if wait is not None else "aucune")
        body = _items([(run["href"], "%s · %s" % (run["ticket"], run["title"]), duration(d))
                       for run, d in sorted(data["lead"], key=lambda p: -p[1])], "Aucun run fusionné sur la période.") + \
            "<h3>Attentes de décision</h3>" + _items(
                [(run["href"], "%s · %s" % (run["ticket"], run["title"]), duration(d))
                 for run, d in sorted(data["waits"], key=lambda p: -p[1])], "Aucune attente de décision sur la période.")
        definition = ("Délai : du lancement du ticket (gc.flow.gate.dispatch) à sa fusion. Attente : de la question "
                      "posée à Benjamin à sa réponse, ou jusqu’à maintenant si elle attend encore.")
    elif view == "verifications":
        reviews, evals = len(data["reviews"]), len(data["evaluations"])
        head = "%d revue%s de code · %d évaluation%s · %d mesure%s de fidélité" % (
            reviews, "s" * (reviews > 1), evals, "s" * (evals > 1), len(data["fidelity"]), "s" * (len(data["fidelity"]) > 1))
        body = _chart(days, [("Revues sans bloquant", data["reviews_clear"], "s2"),
                             ("Revues avec bloquants", data["reviews_blocking"], "s3"),
                             ("Évaluations favorables", data["evaluations_ok"], "s1")], "Vérifications par jour") + _items(
            [(run["href"], "%s · %s" % (run["ticket"], e["text"]), datetime.fromtimestamp(e["at"], tz=PARIS).strftime("%d/%m %H:%M"))
             for run, e in sorted(data["reviews"] + data["evaluations"] + data["fidelity"], key=lambda p: -p[1]["at"])],
            "Aucune vérification sur la période.")
        definition = ("Revues de code (gc.flow.code_review), évaluations (gc.flow.evaluation) et mesures de fidélité "
                      "(gc.flow.verdict.fidelity) écrites sur les tickets. La CI GitHub n’est pas encore lue ici.")
    else:
        head = "%d run%s lancé%s · %d arrêt%s · %d décision%s de Benjamin" % (
            sum(data["launched_per_day"]), "s" * (sum(data["launched_per_day"]) > 1), "s" * (sum(data["launched_per_day"]) > 1),
            sum(data["stopped_per_day"]), "s" * (sum(data["stopped_per_day"]) > 1),
            sum(data["answers_per_day"]), "s" * (sum(data["answers_per_day"]) > 1))
        body = _chart(days, [("Runs lancés", data["launched_per_day"], "s1"), ("Arrêts", data["stopped_per_day"], "s3"),
                             ("Décisions", data["answers_per_day"], "s2")], "Activité par jour")
        definition = "Lancements et arrêts lus sur les tickets ; décisions lues dans le journal (réponses aux demandes)."
    when = " · vérifié à %s (Paris)" % _e(checked) if checked else ""
    return ('<div class="pn-head"><h1>Analyses</h1><p class="an-sub">Toute l’usine · %s%s</p></div>'
            '<nav class="an-tabs" aria-label="Période">%s</nav><nav class="an-tabs" aria-label="Vue">%s</nav>'
            '<section class="pn-panel"><h2>%s</h2><p class="an-head">%s</p>%s'
            '<details class="an-def"><summary>Définition et sources</summary><p>%s</p></details></section>'
            % (dict(PERIODS)[period], when, periods, tabs, _e(dict(VIEWS)[view]), _e(head), body, _e(definition)))


CSS = """
:root{--an-1:#415fce;--an-2:#1c7954;--an-3:#97691e}
@media (prefers-color-scheme: dark){:root{--an-1:#91a7ff;--an-2:#52c9b1;--an-3:#e6ba70}}
.an-sub{margin:0 0 16px;color:var(--pn-muted-text)}
.an-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.an-tab{padding:8px 13px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);text-decoration:none;font-size:13px}
.an-tab.on{background:var(--pn-surface-2);border-color:var(--accent)}
.an-head{margin:0 0 14px!important;color:var(--pn-muted-text)}
.an-chart{margin:0 0 16px}.an-chart svg{width:100%;height:auto;max-height:240px}
.an-chart rect.s1{fill:var(--an-1)}.an-chart rect.s2{fill:var(--an-2)}.an-chart rect.s3{fill:var(--an-3)}
.an-chart text{fill:var(--pn-muted-text);font-size:11px}.an-chart line{stroke:var(--line)}
.an-chart figcaption{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--pn-muted-text)}
.an-chart figcaption i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.an-chart i.s1{background:var(--an-1)}.an-chart i.s2{background:var(--an-2)}.an-chart i.s3{background:var(--an-3)}
.an-items{list-style:none;margin:0;padding:0}
.an-items li{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
.an-items a{color:var(--ink);overflow-wrap:anywhere}.an-items span{color:var(--pn-muted-text);white-space:nowrap}
.pn-panel h3{font-size:15px;margin:18px 0 6px}
.an-muted{color:var(--pn-muted-text)}
.an-def{margin-top:14px;font-size:13px}.an-def summary{cursor:pointer;color:var(--pn-muted-text)}
"""
