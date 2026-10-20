"""The destination Runs of Panorama: the list of runs with their mini
frises, then one run in full -- its swim lanes and what happened, in order.

The list follows the Runs reference (prototypes/c01-complete/runs.html at
632deea): a card a run, three a row, with its workflow, status, title, step,
mini frise and duration; filters « Tous », « En cours », « Terminés ». A
card opens its run (/runs/run?id=<bead>).
"""
import html

from cockpit.runs.derive import DONE, paris

FILTERS = (("tous", "Tous"), ("en-cours", "En cours"), ("termines", "Terminés"))


def _e(value):
    return html.escape(str(value), quote=True)


def _n(value):
    return ("%.2f" % value).rstrip("0").rstrip(".")


def duration(seconds):
    """« 8 min 12 s », « 2 h 05 min », « 3 j 4 h »."""
    seconds = int(seconds)
    if seconds < 3600:
        return "%d min %d s" % divmod(seconds, 60)
    hours, rest = divmod(seconds, 3600)
    if hours < 48:
        return "%d h %02d min" % (hours, rest // 60)
    return "%d j %d h" % divmod(hours, 24)


def _tick(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        minutes, rest = divmod(seconds, 60)
        return "%dm%02ds" % (minutes, rest) if rest else "%dm" % minutes
    hours, rest = divmod(seconds, 3600)
    return "%dh%02d" % (hours, rest // 60)


def _selected(runs, filtre):
    if filtre == "en-cours":
        return [run for run in runs if run["state"] != DONE]
    if filtre == "termines":
        return [run for run in runs if run["state"] == DONE]
    return list(runs)


def run_card(run):
    elapsed = max(run["elapsed"], 1)
    tone = run.get("tone") or ""
    dot = '<span class="rn-dot"></span>' if tone else ""
    rows = []
    for lane in run["lanes"]:
        bars = "".join('<span class="rn-bar %s" style="left:%s%%;width:%s%%"></span>'
                       % (lane["kind"], _n(100 * s / elapsed), _n(100 * (e - s) / elapsed))
                       for s, e in lane["jobs"])
        rows.append('<div class="rn-row"><span>%s</span><div class="rn-track">%s</div></div>' % (_e(lane["name"]), bars))
    ticks = "".join("<span>%s</span>" % _tick(t) for t in (0, elapsed / 2, elapsed))
    return (
        '<a class="rn-card" href="%s"><div class="rn-top"><span>%s</span><span class="rn-badge %s">%s%s</span></div>'
        '<h2>%s</h2><p>%s</p><div class="rn-mini">%s</div><div class="rn-axis">%s</div>'
        '<div class="rn-foot"><span>Début %s (Paris)</span><span class="rn-mono">%s</span></div></a>'
    ) % (_e(run["href"]), _e(run["type"]), tone, dot, _e(run["status"]), _e(run["title"]), _e(run["step"]),
         "".join(rows), ticks, _e(run["started"]), duration(run["elapsed"]))


def render_runs_page(runs, filtre, checked=None, error=False):
    """Main part of /runs."""
    filtre = filtre if filtre in dict(FILTERS) else "tous"
    buttons = "".join('<a class="rn-filter%s" href="/runs?filtre=%s"%s>%s</a>'
                      % (" on" if key == filtre else "", key, ' aria-current="page"' if key == filtre else "", label)
                      for key, label in FILTERS)
    if runs is None:
        body = '<section class="pn-panel"><p>%s</p></section>' % (
            "Les runs n’ont pas pu être lus (tracker injoignable)." if error else "Lecture des runs…")
    else:
        shown = _selected(runs, filtre)
        body = ('<div class="rn-grid">%s</div>' % "".join(run_card(run) for run in shown) if shown
                else '<section class="pn-panel"><p>Aucun run dans ce filtre.</p></section>')
    when = ' · vérifié à %s (Paris)' % _e(checked) if checked else ""
    return ('<div class="pn-head"><small class="rn-crumb">Usine / Runs</small><h1>Runs</h1>'
            '<p class="rn-sub">Les livraisons de tickets, en cours et passées%s.</p></div>'
            '<nav class="rn-filters" aria-label="Filtrer les runs">%s</nav>%s') % (when, buttons, body)


def render_run_page(run):
    """Main part of /runs/run?id=…: the run's frise, then its events."""
    if run is None:
        return ('<div class="pn-head"><small class="rn-crumb"><a href="/runs">Runs</a></small><h1>Run introuvable</h1></div>'
                '<section class="pn-panel"><p>Ce run n’est pas parmi ceux que le cockpit lit.</p></section>')
    elapsed = max(run["elapsed"], 1)
    lanes = []
    for lane in run["lanes"]:
        bars = []
        for s, e in lane["jobs"]:
            label = "%s → %s" % (paris(run["start"] + s), paris(run["start"] + e)) if e > s else paris(run["start"] + s)
            bars.append('<span class="rn-bar %s%s" style="left:%s%%;width:%s%%" title="%s"></span>'
                        % (lane["kind"], " point" if e <= s else "", _n(100 * s / elapsed),
                           _n(100 * (e - s) / elapsed), _e("%s · %s" % (lane["title"], label))))
        lanes.append('<div class="rn-lane"><span title="%s">%s</span><div class="rn-track big">%s</div></div>'
                     % (_e(lane["title"]), _e(lane["title"]), "".join(bars)))
    ticks = "".join("<span>%s</span>" % paris(run["start"] + elapsed * i / 4) for i in range(5))
    events = "".join('<tr><td class="rn-mono">%s</td><td>%s</td><td>%s</td></tr>'
                     % (paris(e["at"], with_day=True), _e(e["lane"]), _e(e["text"])) for e in run["events"])
    facts = [("Statut", run["status"]), ("Début", "%s (Paris)" % run["started"]), ("Durée", duration(run["elapsed"])),
             ("Ticket", "%s · %s" % (run["ticket"], run["id"]))]
    if run.get("branch"):
        facts.append(("Branche", run["branch"]))
    if run.get("spec"):
        facts.append(("Spec", run["spec"]))
    dl = "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (_e(k), _e(v)) for k, v in facts)
    return (
        '<div class="pn-head"><small class="rn-crumb"><a href="/runs">Runs</a> / %s</small><h1>%s</h1>'
        '<p class="rn-sub">%s</p></div>'
        '<section class="pn-panel"><dl class="rn-facts">%s</dl></section>'
        '<section class="pn-panel"><h2>Frise du run</h2><div class="rn-frise"><div class="rn-frise-in">%s'
        '<div class="rn-axis big">%s</div></div></div>'
        '<p class="rn-legend"><span class="rn-key human"></span>Humain <span class="rn-key code"></span>Code '
        '<span class="rn-key agent"></span>Agents · heures de Paris</p></section>'
        '<section class="pn-panel"><h2>Ce qui s’est passé</h2><div class="rn-scroll"><table class="rn-events">'
        '<thead><tr><th>Quand (Paris)</th><th>Piste</th><th>Événement</th></tr></thead><tbody>%s</tbody></table>'
        '</div></section>'
    ) % (_e(run["ticket"]), _e(run["title"]), _e(run["step"]), dl, "".join(lanes), ticks,
         events or '<tr><td colspan="3">Aucun événement écrit.</td></tr>')


CSS = """
:root{--rn-human:#c9962f;--rn-code:#2f9c94;--rn-agent:#8b75e0;--rn-wait:#85590f}
@media (prefers-color-scheme: dark){:root{--rn-human:#e4bc6d;--rn-code:#55b5ae;--rn-agent:#a897eb;--rn-wait:#e4bc6d}}
.rn-crumb{display:block;margin-bottom:8px;font-size:13px;color:var(--pn-muted-text)}
.rn-crumb a{color:inherit}
.rn-sub{margin:0 0 18px;color:var(--pn-muted-text)}
.rn-filters{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.rn-filter{padding:9px 14px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);text-decoration:none;font-size:14px}
.rn-filter.on{background:var(--pn-surface-2);border-color:var(--accent)}
.rn-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.rn-card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px;color:inherit;text-decoration:none}
.rn-card:hover{border-color:var(--accent)}
.rn-card h2{margin:12px 0 7px;font-size:18px;overflow-wrap:anywhere}
.rn-card p{margin:0 0 14px;font-size:14px;line-height:1.5;color:var(--pn-muted-text);overflow-wrap:anywhere}
.rn-top,.rn-foot{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--pn-muted-text)}
.rn-foot{margin-top:15px;font-size:13px}
.rn-badge{color:var(--ok);white-space:nowrap}.rn-badge.live{color:var(--accent)}.rn-badge.wait{color:var(--pn-warn-text)}
.rn-dot{display:inline-block;width:7px;height:7px;border-radius:100%;background:currentColor;margin-right:6px}
.rn-mono{font:13px ui-monospace,monospace}
.rn-mini{display:grid;gap:6px;font-size:11px}
.rn-row{display:grid;grid-template-columns:70px 1fr;gap:8px;align-items:center}
.rn-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rn-track{height:8px;position:relative;border-bottom:1px solid var(--line);
  background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),var(--line) 25%)}
.rn-bar{position:absolute;height:5px;border-radius:4px;top:1px;background:var(--rn-agent);min-width:3px}
.rn-bar.code{background:var(--rn-code)}.rn-bar.human{background:var(--rn-human)}
.rn-axis{margin:8px 0 0 78px;display:flex;justify-content:space-between;color:var(--pn-muted-text);font-size:10px}
.rn-facts{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin:0}
.rn-facts dt{font-size:12px;color:var(--pn-muted-text)}.rn-facts dd{margin:4px 0 0;overflow-wrap:anywhere}
.rn-frise{overflow-x:auto}.rn-frise-in{min-width:640px;display:grid;gap:12px}
.rn-lane{display:grid;grid-template-columns:200px 1fr;gap:12px;align-items:center;font-size:13px}
.rn-lane span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rn-track.big{height:22px}
.rn-track.big .rn-bar{height:14px;top:3px;min-width:4px}
.rn-track.big .rn-bar.point{width:6px!important;margin-left:-3px;border-radius:2px}
.rn-axis.big{margin:0 0 0 212px;font-size:12px}
.rn-legend{margin-top:14px!important;font-size:13px;color:var(--pn-muted-text)}
.rn-key{display:inline-block;width:12px;height:8px;border-radius:3px;margin:0 4px 0 10px;background:var(--rn-agent)}
.rn-key.human{background:var(--rn-human);margin-left:0}.rn-key.code{background:var(--rn-code)}
.rn-scroll{overflow-x:auto}
.rn-events{border-collapse:collapse;width:100%;font-size:14px}
.rn-events th{text-align:left;font-size:12px;color:var(--pn-muted-text);font-weight:600;padding:6px 10px 6px 0;border-bottom:1px solid var(--line)}
.rn-events td{padding:8px 10px 8px 0;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
.rn-events td:first-child,.rn-events td:nth-child(2){white-space:nowrap}
@media (max-width:1100px){.rn-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.rn-grid{grid-template-columns:1fr}.rn-lane{grid-template-columns:110px 1fr}.rn-axis.big{margin-left:122px}}
"""
