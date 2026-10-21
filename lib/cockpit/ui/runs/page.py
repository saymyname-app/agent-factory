"""The destination Runs of Panorama: the list of runs with their mini
frises, then one run in full -- its swim lanes Humain, Code and one per
agent, on the time relative to its trigger -- and, under it, the detail of
the job selected (C1, af-lzti7w; Spec af-fgcw0d, user stories 127 to 135).

The pages follow the Runs reference (prototype/c01-parcours-20261011 at
d8cb462, prototypes/c01-flow/frozen-runs) and carry its anchors, numbered
as its frozen pages number them (:class:`RunAnchors`). A card is
:func:`run_card`, the one card of a run -- the overview draws the same. A
job opens at /runs/job?run=<run>&job=<job>, its frise above it; an event
opened is kept in the address (``&event=<n>``), so a reload keeps it.

What a run holds is :mod:`cockpit.runs.workflows`'s: the page draws it and
says what is not collected, never a value of its own.
"""
import html
import urllib.parse

from cockpit.runs.derive import AGENT, CODE, DONE, HUMAN, WAIT
from cockpit.runs.workflows import CONTROLS, OTHERS, SESSIONS, TOOLS, normalized, paris_time

# The cards drawn at most; the analyses read every run the cockpit keeps.
SHOWN = 48
FILTERS = (("tous", "Tous"), ("en-cours", "En cours"), ("termines", "Terminés"))
LEGEND = ("Origine 0 : déclencheur · traits : outils (turquoise), contrôles (vert), sessions (violet), "
          "autres (gris) · clic : détail")
NOT_COLLECTED = "Pas encore disponible : donnée non collectée."
EVENT_KINDS = {TOOLS: "outil", CONTROLS: "contrôle", SESSIONS: "session", OTHERS: "autre"}
TICKS = 5


class RunAnchors:
    """Numbers the anchors of one page of Runs as its frozen pages number
    them: ``card``, then ``card-2``, ``card-3``."""

    def __init__(self):
        self._counts = {}

    def __call__(self, name):
        self._counts[name] = self._counts.get(name, 0) + 1
        count = self._counts[name]
        return 'data-anchor="%s"' % html.escape(name if count == 1 else "%s-%d" % (name, count))


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


def short(seconds):
    """A job's duration: « 18 s » under a minute, else :func:`duration`."""
    seconds = int(seconds)
    return "%d s" % seconds if seconds < 60 else duration(seconds)


def relative(seconds):
    """« +2 min 57 s » from the trigger."""
    return "+" + short(seconds)


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


def _status(run):
    return ("✓ %s" if run["state"] == DONE else "%s") % run["status"]


def _now(run, now):
    return now if now is not None else run["end"]


def _trigger(run):
    return run.get("trigger") or "non enregistré"


def _project(run):
    return run.get("project") or "non enregistré"


# --- the card -----------------------------------------------------------------------

def run_card(run, now=None, anchors=None):
    """The card of one run: its workflow, its status, its title, its step,
    a mini frise with a row per participant and a bar per job, its start
    and its duration. It opens the run. It draws any run the cockpit reads:
    its lanes, each a name and the (start, end) seconds of its jobs."""
    anchors = anchors or RunAnchors()
    elapsed = max(run["elapsed"], 1)
    tone = run.get("tone") or ""
    card, top, type_, badge = anchors("card"), anchors("card-top"), anchors("span"), anchors("badge")
    dot = '<span class="rn-dot" %s></span>' % anchors("live-dot") if tone else ""
    head = ('<div class="rn-top" %s><span %s>%s</span><span class="rn-badge %s" %s>%s%s</span></div>'
            % (top, type_, _e(run["type"]), tone, badge, dot, _e(_status(run))))
    title = ('<h2 %s>%s</h2><p %s>%s</p><p class="rn-origin" %s><span>Déclencheur : %s</span>'
             '<span>Projet : %s</span></p>'
             % (anchors("h2"), _e(run["title"]), anchors("p"), _e(run["step"]), anchors("origin"),
                _e(_trigger(run)), _e(_project(run))))
    rows = []
    mini = anchors("mini")
    for lane in run["lanes"]:
        row, label, track = anchors("mini-row"), anchors("mini-label"), anchors("mini-track")
        bars = "".join('<span class="rn-bar %s" %s style="left:%s%%;width:%s%%"></span>'
                       % (lane["kind"], anchors("mini-bar"), _n(100 * s / elapsed), _n(100 * (e - s) / elapsed))
                       for s, e in lane["jobs"])
        rows.append('<div class="rn-row" %s><span %s>%s</span><div class="rn-track" %s>%s</div></div>'
                    % (row, label, _e(lane["name"]), track, bars))
    ticks = "".join("<span>%s</span>" % _tick(t) for t in (0, elapsed / 2, elapsed))
    axis, foot, mono = anchors("mini-axis"), anchors("card-foot"), anchors("mono")
    started = paris_time(run["start"], _now(run, now)) if run.get("start") else run.get("started", "?")
    return (
        '<a class="rn-card" href="%s" %s>%s%s<div class="rn-mini" %s>%s</div><div class="rn-axis" %s>%s</div>'
        '<div class="rn-foot" %s><span>Début %s (Paris)</span><span class="rn-mono" %s>%s</span></div></a>'
    ) % (_e(run["href"]), card, head, title, mini, "".join(rows), axis, ticks, foot,
         _e(started), mono, duration(run["elapsed"]))


# --- the list ------------------------------------------------------------------------

def render_runs_page(runs, filtre, checked=None, error=False, now=None):
    """Main part of /runs: the filters, then a card per run."""
    anchors = RunAnchors()
    filtre = filtre if filtre in dict(FILTERS) else "tous"
    head = ('<div class="pn-head"><small class="rn-crumb" %s>Usine / Runs</small><h1 %s>Runs</h1>'
            '<p class="rn-sub" %s>Les workflows en cours et leur historique%s.</p></div>'
            % (anchors("crumb"), anchors("h1"), anchors("muted"),
               ' · vérifié à %s (Paris)' % _e(checked) if checked else ""))
    buttons = []
    filters = anchors("filters")
    for key, label in FILTERS:
        chosen = key == filtre
        buttons.append('<a class="rn-filter%s" href="/runs?filtre=%s" %s%s>%s</a>'
                       % (" on" if chosen else "", key, anchors("chosen" if chosen else "button"),
                          ' aria-current="page"' if chosen else "", label))
    nav = '<nav class="rn-filters" aria-label="Filtrer les runs" %s>%s</nav>' % (filters, "".join(buttons))
    if runs is None:
        body = '<section class="pn-panel"><p>%s</p></section>' % (
            "Les runs n’ont pas pu être lus : le tracker ne répond pas (tracker injoignable)."
            if error else "Lecture des runs…")
    else:
        shown = _selected(runs, filtre)[:SHOWN]
        body = ('<div class="rn-grid" %s>%s</div>' % (anchors("grid"), "".join(run_card(run, now, anchors)
                                                                               for run in shown))
                if shown else '<section class="pn-panel"><p>Aucun run dans ce filtre. '
                              '<a href="/runs?filtre=tous">Voir tous les runs</a></p></section>')
    return head + nav + body


# --- one run, and the detail of a job --------------------------------------------------

def render_run_page(run, now=None, stale_at=None, job_id=None, event=None):
    """Main part of /runs/run?id=… (and of /runs/job, with ``job_id``): the
    head of the run, its frise, and under it the detail of the job
    ``job_id`` with its event ``event`` (its number) open. ``stale_at``:
    when the activity was last observed, if the reading is no longer
    current."""
    anchors = RunAnchors()
    if run is None:
        return ('<div class="pn-head"><small class="rn-crumb" %s><a href="/runs" %s>← Runs</a></small>'
                '<h1 %s>Run introuvable</h1></div><section class="pn-panel"><p>Ce run n’est pas parmi ceux que le '
                'cockpit lit. <a href="/runs">Revenir à la liste des runs</a></p></section>'
                % (anchors("crumb"), anchors("back"), anchors("h1")))
    now = _now(run, now)
    run = normalized(run, now)
    job = next((item for item in run["items"] if item["id"] == job_id), None)
    return (_render_head(run, now, stale_at, anchors) + _render_frise(run, job, anchors)
            + (_render_detail(run, job, event, anchors) if job else ""))


def _render_head(run, now, stale_at, anchors):
    crumb, back, kind, title = anchors("crumb"), anchors("back"), anchors("small"), anchors("h1")
    summary, badge = anchors("run-summary"), anchors("badge")
    tone = run.get("tone") or ""
    dot = '<span class="rn-dot" %s></span>' % anchors("live-dot") if tone else ""
    horizon = "Temps final figé" if run["state"] == DONE else "Horizon : maintenant"
    parts = ['<span class="rn-badge %s" %s>%s%s</span>' % (tone, badge, dot, _e(_status(run))),
             "<span>Déclenché à %s (Paris)</span>" % _e(paris_time(run["start"], now)),
             '<span class="rn-mono" %s>%s</span>' % (anchors("mono"), duration(run["elapsed"])),
             "<span>%s</span>" % horizon, "<span>Usage et coût non collectés</span>"]
    origin = ('<p class="rn-origin" %s><span>Déclencheur : %s</span><span>Projet : %s</span></p>'
              % (anchors("origin"), _e(_trigger(run)), _e(_project(run))))
    out = ('<div class="pn-head rn-head"><small class="rn-crumb" %s><a href="/runs" %s>← Runs</a> · '
           '<span %s>%s</span></small><h1 %s>%s</h1><div class="rn-summary" %s>%s</div>'
           % (crumb, back, kind, _e(run["type"]), title, _e(run["title"]), summary, "".join(parts))) + origin
    if run["state"] != DONE:
        current = [item["name"] for item in run["items"] if item["open"]]
        said = "Derniers jobs observés" if stale_at else "Job courant"
        if run["state"] == WAIT and not current:
            current = [run["step"]]
        out += '<p class="rn-current" %s>%s : %s</p>' % (anchors("p"), said, _e(" · ".join(current) or run["step"]))
        if stale_at:
            out += ('<p class="rn-notice" role="status" %s>Lecture périmée · dernière observation à %s (Paris), '
                    'activité actuelle non confirmée.</p>' % (anchors("notice"), _e(paris_time(stale_at, now, True))))
    return out + "</div>"


def _job_href(run, item, event=None):
    query = {"run": run["id"], "job": item["id"]}
    if event:
        query["event"] = event
    return "/runs/job?" + urllib.parse.urlencode(query)


# The frise is drawn on a track of TRACK pixels, whatever the screen: its box
# scrolls when the screen is narrower. A job is a box at its start, as wide
# as its time, and at least as wide as its name, its duration and its
# events need to be read and clicked (a target of MARK pixels each): the
# bar at its top keeps its real duration. Two boxes of a lane that would
# overlap are drawn on two rows of it.
TRACK = 720
NAME_MAX = 240          # a name wider than that wraps
NAME_CHAR, SMALL_CHAR, BOX_PAD = 8.2, 6.8, 24
LINE, BOX_BASE, MARK, MARK_GAP, ROW_GAP, GAP = 17, 78, 24, 2, 10, 8


def _box(item, elapsed):
    """(left, width, height) of the box of a job, in pixels."""
    left = TRACK * item["offset"] / elapsed
    span = TRACK * min(item["lasted"], elapsed - item["offset"]) / elapsed
    name = (len(item["name"]) + 2) * NAME_CHAR
    lasted = len(_lasted(item)) * SMALL_CHAR
    marks = len(item["events"]) * (MARK + MARK_GAP) - MARK_GAP + 10
    width = max(span, min(name, NAME_MAX) + BOX_PAD, lasted + BOX_PAD, marks, 56)
    lines = max(1, -(-int(name) // int(width - BOX_PAD)))
    return left, width, BOX_BASE + LINE * (lines - 1)


def _lasted(item):
    return "%s · en cours" % short(item["lasted"]) if item["open"] else short(item["lasted"])


def _rows(items, elapsed):
    """Each job of a lane with its box and its row, the first row where it
    overlaps no box: [(item, left, width, height, row)]."""
    ends, placed = [], []
    for item in items:
        left, width, height = _box(item, elapsed)
        row = next((index for index, end in enumerate(ends) if end + GAP <= left), len(ends))
        if row == len(ends):
            ends.append(0)
        ends[row] = left + width
        placed.append((item, left, width, height, row))
    return placed


def _render_frise(run, selected, anchors):
    elapsed = max(run["elapsed"], 1)
    box, scroll, chart = anchors("chart-box"), anchors("scroll"), anchors("chart")
    axis, axis_title, ticks_anchor = anchors("axis"), anchors("axis-title"), anchors("ticks")
    ticks = "".join('<span class="rn-tick">%s</span>' % _tick(elapsed * i / TICKS) for i in range(TICKS + 1))
    lanes, widest = [], TRACK
    for lane in run["lanes"]:
        lane_anchor, name, track = anchors("lane"), anchors("lane-name"), anchors("track")
        context = ('<small>Contexte · dernière session : non collecté</small>' if lane["kind"] == AGENT else "")
        placed = _rows(lane["items"], elapsed)
        heights = {}
        for _, _, _, height, row in placed:
            heights[row] = max(heights.get(row, 0), height)
        tops = {row: 16 + sum(heights[r] + ROW_GAP for r in range(row)) for row in heights}
        jobs = []
        for item, left, width, height, row in placed:
            widest = max(widest, left + width)
            job, select, marks = anchors("job"), anchors("job-select"), anchors("marks")
            mark = "●" if item["open"] else "✓"
            lasted = _lasted(item)
            drawn = "".join(
                '<a class="rn-mark %s" href="%s" %s aria-label="Événement · %s · %s à %s (Paris)" title="%s · %s"></a>'
                % (event["kind"], _e(_job_href(run, item, number)), anchors("mark"), _e(event["label"]),
                   _e(event["text"]), paris_time(event["at"], None, True), _e(event["label"]), _e(event["text"]))
                for number, event in enumerate(item["events"], start=1))
            span = TRACK * min(item["lasted"], elapsed - item["offset"]) / elapsed
            current = item is selected
            jobs.append(
                '<div class="rn-job %s%s%s" %s style="left:%spx;top:%spx;width:%spx;height:%spx">'
                '<span class="rn-span" style="width:%spx" aria-hidden="true"></span>'
                '<a class="rn-job-select" href="%s" title="%s" %s%s><strong>%s %s</strong><small>%s</small></a>'
                '<div class="rn-marks" %s>%s</div></div>'
                % (lane["kind"], " open" if item["open"] else "", " selected" if current else "", job,
                   _n(left), tops[row], _n(width), height, _n(max(span, 3)),
                   _e(_job_href(run, item)), _e("%s · %s" % (item["name"], lasted)), select,
                   ' aria-current="true"' if current else "", mark,
                   _e(item["name"]), _e(lasted), marks, drawn))
        height = max(111, 16 + sum(heights[r] + ROW_GAP for r in heights) + 6)
        lanes.append('<div class="rn-lane" %s><div class="rn-lane-name" %s><strong>%s</strong><small>%s</small>%s</div>'
                     '<div class="rn-track" %s style="height:%spx">%s</div></div>'
                     % (lane_anchor, name, _e(lane["who"]), _e(lane["role"]), context, track, height, "".join(jobs)))
    return (
        '<section class="rn-chart-box" %s><h2 class="rn-hidden">Frise du run</h2>'
        '<div class="rn-scroll" %s role="region" aria-label="Frise du run : faire défiler pour tout voir">'
        '<div class="rn-chart" %s style="width:calc(var(--rn-name) + %spx)"><div class="rn-axis-row" %s>'
        '<span class="rn-axis-title" %s>Responsable</span>'
        '<div class="rn-ticks" %s style="width:%spx">%s</div></div>%s</div></div>'
        '<p class="rn-legend" %s>%s</p></section>'
    ) % (box, scroll, chart, int(widest + 28), axis, axis_title, ticks_anchor, TRACK, ticks, "".join(lanes),
         anchors("legend"), LEGEND)


def _section(anchors, title, body, name="details"):
    return ('<details class="rn-section" %s><summary %s>%s</summary>%s</details>'
            % (anchors(name), anchors("summary"), _e(title), body))


def _said(text):
    return "<p>%s</p>" % _e(text)


def _render_detail(run, item, event, anchors):
    lane = next(lane for lane in run["lanes"] if lane["key"] == item["lane"])
    inspector, detail, head = anchors("inspector"), anchors("detail"), anchors("inspector-head")
    state = "En cours" if item["open"] else "Terminé"
    kind = {HUMAN: "humain", CODE: "code"}.get(lane["kind"], "agent")
    pills = ('<div><h2 %s>%s</h2><span class="rn-pill%s">%s</span><span class="rn-pill">%s</span></div>'
             '<div><span class="rn-pill">Responsable %s</span><span class="rn-pill">%s</span>'
             '<a class="rn-close" href="%s" aria-label="Fermer le détail du job">×</a></div>'
             % (anchors("h2"), _e(item["name"]), "" if item["open"] else " good", state,
                _e(short(item["lasted"]) + (" · en cours" if item["open"] else "")), _e(lane["who"]), kind,
                _e(run["href"])))
    sections = []
    end = "en cours" if item["open"] else relative(item["offset"] + item["lasted"])
    timing = '<p class="rn-muted">Début %s · fin %s</p>' % (relative(item["offset"]), end)
    if lane["kind"] == AGENT:
        sections.append(_section(anchors, "Configuration de l’agent", _said(NOT_COLLECTED)))
        sections.append(_section(anchors, "Sessions du job", _said(NOT_COLLECTED), name="session-history"))
        sections.append(_section(anchors, "Description", _said(item["description"] or NOT_COLLECTED) + timing))
        sections.append(_section(anchors, "Prompts envoyés", _said(NOT_COLLECTED)))
        usage = _said(NOT_COLLECTED)
    else:
        who = "Ce job est un geste de Benjamin" if lane["kind"] == HUMAN else "Ce job est exécuté par le code"
        sections.append(_section(anchors, "Configuration de l’agent",
                                 _said("Ce job n’utilise pas un agent modèle. %s." % who)))
        sections.append(_section(anchors, "Description", _said(item["description"] or "Aucune description écrite.")
                                 + timing))
        sections.append(_section(anchors, "Prompts envoyés", _said("Sans objet : aucune instruction à un modèle.")))
        usage = _said("Aucun appel modèle pour ce job.")
    sections.append(_section(anchors, "Contrôles", _said(NOT_COLLECTED)))
    sections.append(_section(anchors, "Tokens et coût", usage))
    sections.append(_section(anchors, "Sorties", _said(NOT_COLLECTED)))
    events_anchor, events_title, events_note, events_list = (anchors("events"), anchors("h3"), anchors("muted"),
                                                              anchors("event-list"))
    rows = []
    for number, recorded in enumerate(item["events"], start=1):
        at = paris_time(recorded["at"], None, True)
        content = ('<dl class="rn-event-facts"><div><dt>Instant</dt><dd>%s (Paris) · %s depuis le déclencheur</dd></div>'
                   '<div><dt>Nature</dt><dd>%s · %s</dd></div><div><dt>Contenu</dt><dd>%s</dd></div>'
                   '<div><dt>Job</dt><dd>%s</dd></div><div><dt>Source</dt><dd>%s</dd></div></dl>'
                   % (at, relative(max(0, recorded["at"] - run["start"])), _e(recorded["label"]),
                      EVENT_KINDS[recorded["kind"]], _e(recorded["text"]), _e(item["name"]),
                      _e(item.get("source") or "tracker")))
        rows.append('<details class="rn-event" data-run-event="%d" %s%s><summary %s><time %s>%s</time>'
                    '<span class="rn-event-type %s" %s>%s</span><span class="rn-event-label" %s>%s</span></summary>%s'
                    '</details>'
                    % (number, anchors("event"), " open" if event == number else "", anchors("summary"),
                       anchors("time"), at, recorded["kind"], anchors("event-type"), _e(recorded["label"]),
                       anchors("event-label"), _e(recorded["text"]), content))
    return (
        '<div class="rn-inspector" %s><section class="rn-detail" aria-label="Détail du job %s" %s>'
        '<header class="rn-inspector-head" %s>%s</header><div class="rn-inspector-grid" %s>'
        '<div class="rn-inspector-sections" %s>%s</div>'
        '<section class="rn-events" %s><h3 %s>Événements (%d)</h3><p class="rn-muted" %s>Horaires de Paris · '
        'ouvrir un événement pour lire ce qui en est enregistré.</p><div class="rn-event-list" %s>%s</div></section>'
        '</div></section></div>%s'
    ) % (inspector, _e(item["name"]), detail, head, pills, anchors("inspector-grid"), anchors("inspector-sections"),
         "".join(sections), events_anchor, events_title, len(rows), events_note, events_list, "".join(rows), EVENT_SCRIPT)


# An event opened or closed is written in the address, so a reload of the
# page opens the same one; opening one closes the others.
EVENT_SCRIPT = """<script>
document.querySelectorAll('[data-run-event]').forEach(function (item) {
  item.addEventListener('toggle', function () {
    var address = new URL(location.href);
    if (item.open) {
      document.querySelectorAll('[data-run-event][open]').forEach(function (other) {
        if (other !== item) { other.open = false; }
      });
      address.searchParams.set('event', item.getAttribute('data-run-event'));
    } else if (address.searchParams.get('event') === item.getAttribute('data-run-event')) {
      address.searchParams.delete('event');
    }
    history.replaceState(null, '', address.toString());
  });
});
</script>"""


CSS = """
:root{--rn-human:#9a6f1c;--rn-code:#1f7f78;--rn-agent:#6a51c9;--rn-ok:#1c7954;--rn-other:#5f5f5f;--rn-name:165px}
@media (prefers-color-scheme: dark){:root{--rn-human:#e4bc6d;--rn-code:#55b5ae;--rn-agent:#a897eb;--rn-ok:#55c89d;--rn-other:#a3a3a3}}
.rn-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.rn-crumb{display:block;margin-bottom:8px;font-size:13px;color:var(--pn-muted-text)}
.rn-crumb a{color:inherit}
.rn-sub{margin:0 0 18px;color:var(--pn-muted-text)}
.rn-muted{color:var(--pn-muted-text);font-size:13px}
.rn-filters{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.rn-filter{padding:9px 14px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);text-decoration:none;font-size:14px}
.rn-filter.on{background:var(--pn-surface-2);border-color:var(--accent)}
.rn-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.rn-card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px;color:inherit;text-decoration:none}
.rn-card:hover{border-color:var(--accent)}
.rn-card:focus-visible,.rn-filter:focus-visible,.rn-close:focus-visible,.rn-crumb a:focus-visible,
.rn-section>summary:focus-visible,.rn-event>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rn-origin{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;color:var(--pn-muted-text);overflow-wrap:anywhere}
.rn-card .rn-origin{margin:-6px 0 14px;font-size:12px}
.rn-head .rn-origin{margin:0 0 6px}
.rn-head h1{overflow-wrap:anywhere}
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
.rn-track{position:relative}
.rn-row .rn-track{height:8px;border-bottom:1px solid var(--line);
  background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),var(--line) 25%)}
.rn-bar{position:absolute;height:5px;border-radius:4px;top:1px;background:var(--rn-agent);min-width:3px}
.rn-bar.code{background:var(--rn-code)}.rn-bar.human{background:var(--rn-human)}
.rn-axis{margin:8px 0 0 78px;display:flex;justify-content:space-between;color:var(--pn-muted-text);font-size:10px}
.rn-summary{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:14px 0 8px;color:var(--pn-muted-text)}
.rn-summary .rn-badge{font-weight:600}
.rn-current{margin:6px 0 0;color:var(--pn-muted-text)}
.rn-notice{margin:10px 0 0;color:var(--pn-warn-text)}
.rn-chart-box{margin-top:20px;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
.rn-scroll{overflow-x:auto;border-radius:10px 10px 0 0}
.rn-axis-row,.rn-lane{display:grid;grid-template-columns:var(--rn-name) minmax(0,1fr)}
.rn-axis-row{height:44px;background:var(--pn-surface-2)}
.rn-axis-title{padding:14px 16px;color:var(--pn-muted-text);font-size:12px}
.rn-ticks{display:flex;justify-content:space-between;align-items:center;color:var(--pn-muted-text);font:12px ui-monospace,monospace}
.rn-lane{min-height:112px;border-top:1px solid var(--line)}
.rn-lane-name{padding:18px 16px;border-right:1px solid var(--line);min-width:0}
.rn-lane-name strong{display:block;font-size:14px;overflow-wrap:anywhere}
.rn-lane-name small{display:block;color:var(--pn-muted-text);font-size:12px;margin-top:6px;overflow-wrap:anywhere}
.rn-lane .rn-track{min-height:111px;background-repeat:no-repeat;
  background-image:repeating-linear-gradient(90deg,transparent 0,transparent 143px,var(--line) 143px,var(--line) 144px);
  background-size:721px 100%}
.rn-job{position:absolute;border-radius:7px;border:1px solid var(--rn-agent);
  background:color-mix(in srgb,var(--rn-agent) 10%,var(--surface))}
.rn-job.human{border-color:var(--rn-human);background:color-mix(in srgb,var(--rn-human) 10%,transparent)}
.rn-job.code{border-color:var(--rn-code);background:color-mix(in srgb,var(--rn-code) 10%,transparent)}
.rn-job.selected{outline:2px solid var(--ink);outline-offset:1px}
.rn-span{position:absolute;left:-1px;top:-1px;height:4px;border-radius:7px 0 0 0;background:var(--rn-agent)}
.rn-job.human .rn-span{background:var(--rn-human)}.rn-job.code .rn-span{background:var(--rn-code)}
.rn-job-select{display:block;padding:8px 10px 0;color:inherit;text-decoration:none;border-radius:6px 6px 0 0}
.rn-job-select:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.rn-job strong{display:block;font-size:13px;line-height:17px;overflow-wrap:anywhere}
.rn-job small{display:block;font-size:11px;line-height:14px;color:var(--pn-muted-text);margin-top:3px;white-space:nowrap}
.rn-marks{position:absolute;left:5px;bottom:3px;height:24px;display:flex;gap:2px;align-items:center}
.rn-mark{flex:0 0 24px;width:24px;height:24px;position:relative;border-radius:4px}
.rn-mark:focus-visible{outline:2px solid var(--accent);outline-offset:0}
.rn-mark::after{content:'';position:absolute;left:10px;width:4px;top:5px;height:14px;border-radius:2px;background:var(--rn-other)}
.rn-mark.tools::after{background:var(--rn-code)}.rn-mark.controls::after{background:var(--rn-ok)}
.rn-mark.sessions::after{background:var(--rn-agent)}
.rn-legend{margin:0!important;padding:12px 18px;border-top:1px solid var(--line);font-size:13px;color:var(--pn-muted-text)}
.rn-detail{margin-top:20px;border:1px solid var(--line);border-radius:10px;padding:20px;background:var(--surface)}
.rn-inspector-head{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding-bottom:16px;border-bottom:1px solid var(--line)}
.rn-inspector-head>div{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rn-inspector-head h2{margin:0;font-size:18px;overflow-wrap:anywhere}
.rn-pill{border:1px solid var(--line);border-radius:25px;padding:5px 9px;font-size:12px;color:var(--pn-muted-text)}
.rn-pill.good{color:var(--ok)}
.rn-close{display:inline-grid;place-items:center;width:32px;height:32px;border:1px solid var(--pn-control-line);border-radius:8px;color:var(--ink);text-decoration:none;font-size:18px}
.rn-inspector-grid{display:grid;grid-template-columns:minmax(0,0.42fr) minmax(0,0.58fr);gap:20px;margin-top:18px}
.rn-section{padding:14px 0;border-bottom:1px solid var(--line)}
.rn-section>summary,.rn-event>summary{cursor:pointer}
.rn-section>summary{font-weight:600;font-size:14px}
.rn-section p{font-size:14px;margin:10px 0 0;overflow-wrap:anywhere}
.rn-events h3{margin:0;font-size:16px}
.rn-event-list{max-height:570px;overflow:auto}
.rn-event{border-bottom:1px solid var(--line)}
.rn-event>summary{display:grid;grid-template-columns:66px 92px minmax(0,1fr);gap:8px;font:12px ui-monospace,monospace;padding:12px 0;align-items:center}
.rn-event-label{overflow-wrap:anywhere}
.rn-event-type{color:var(--rn-other)}
.rn-event-type.tools{color:var(--rn-code)}.rn-event-type.controls{color:var(--rn-ok)}.rn-event-type.sessions{color:var(--rn-agent)}
.rn-event-facts{display:grid;gap:8px;margin:4px 0 14px;font-size:13px}
.rn-event-facts dt{font-size:12px;color:var(--pn-muted-text)}.rn-event-facts dd{margin:2px 0 0;overflow-wrap:anywhere}
@media (max-width:1100px){.rn-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.rn-grid{grid-template-columns:1fr}.rn-inspector-grid{grid-template-columns:1fr}
  :root{--rn-name:120px}.rn-lane-name{padding:14px 10px}
  .rn-detail{padding:15px}.rn-event>summary{grid-template-columns:62px 70px minmax(0,1fr);font-size:11px}}
"""
