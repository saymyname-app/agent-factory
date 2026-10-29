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
import json
import urllib.parse

from cockpit.runs.derive import AGENT, CODE, DONE, HUMAN, WAIT
from cockpit.runs.evidence import PRESENT
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
    """The status of a run, ticked when it ended in a success, crossed when
    it ended without one."""
    if run["state"] != DONE:
        return run["status"]
    return ("✕ %s" if run.get("tone") == "ended" else "✓ %s") % run["status"]


def _dot(run, anchors):
    """The dot of a run still open, beside its status."""
    return '<span class="rn-dot" %s></span>' % anchors("live-dot") if run.get("tone") in ("live", "wait") else ""


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
    dot = _dot(run, anchors)
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

def render_run_page(run, now=None, stale_at=None, job_id=None, event=None, session=None, opened=(), raw=()):
    """Main part of /runs/run?id=… (and of /runs/job, with ``job_id``): the
    head of the run, its frise, and under it the detail of the job
    ``job_id`` with its event ``event`` (its number) open, its session
    ``session`` chosen (by default its last), the sections ``opened`` open
    (configuration, prompts, system, user) and the prompts ``raw`` (system,
    user) shown raw. ``stale_at``: when the activity was last observed, if
    the reading is no longer current."""
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
            + (_render_detail(run, job, event, anchors, session, set(opened), set(raw)) if job else ""))


def _render_head(run, now, stale_at, anchors):
    crumb, back, kind, title = anchors("crumb"), anchors("back"), anchors("small"), anchors("h1")
    summary, badge = anchors("run-summary"), anchors("badge")
    tone = run.get("tone") or ""
    dot = _dot(run, anchors)
    horizon = "Temps final figé" if run["state"] == DONE else "Horizon : maintenant"
    parts = ['<span class="rn-badge %s" %s>%s%s</span>' % (tone, badge, dot, _e(_status(run))),
             "<span>Déclenché à %s (Paris)</span>" % _e(paris_time(run["start"], now)),
             '<span class="rn-mono" %s>%s</span>' % (anchors("mono"), duration(run["elapsed"])),
             "<span>%s</span>" % horizon, "<span>%s</span>" % _e(_run_usage(run))]
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
        context = _lane_context(lane) if lane["kind"] == AGENT else ""
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


def _section(anchors, title, body, name="details", open_=False, key=None):
    return ('<details class="rn-section" %s%s%s><summary %s>%s</summary>%s</details>'
            % (anchors(name), ' data-open-key="%s"' % key if key else "", " open" if open_ else "",
               anchors("summary"), _e(title), body))


def _said(text):
    return "<p>%s</p>" % _e(text)


def _render_detail(run, item, event, anchors, session=None, opened=frozenset(), raw=frozenset()):
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
        placed = item.get("trace_sessions") or []
        chosen = next((s for s in placed if s["name"] == session), placed[-1] if placed else None)
        sections.append(_section(anchors, "Configuration de l’agent",
                                 _configuration(run, item, lane, chosen, anchors), open_="configuration" in opened,
                                 key="configuration"))
        sections.append(_section(anchors, "Sessions du job (%d)" % len(placed) if placed else "Sessions du job",
                                 _sessions(run, item, placed, chosen), name="session-history", open_=True))
        sections.append(_section(anchors, "Description", _said(item["description"] or NOT_COLLECTED) + timing))
        sent = ((chosen or {}).get("observed") or {}).get("prompts") or []
        sections.append(_section(anchors, "Prompts envoyés (%d)" % len(sent) if sent else "Prompts envoyés",
                                 _prompts(chosen, anchors, opened, raw), open_="prompts" in opened, key="prompts"))
        usage = None
    else:
        who = "Ce job est un geste de Benjamin" if lane["kind"] == HUMAN else "Ce job est exécuté par le code"
        sections.append(_section(anchors, "Configuration de l’agent",
                                 _said("Ce job n’utilise pas un agent modèle. %s." % who)))
        sections.append(_section(anchors, "Description", _said(item["description"] or "Aucune description écrite.")
                                 + timing))
        sections.append(_section(anchors, "Prompts envoyés", _said("Sans objet : aucune instruction à un modèle.")))
        usage = _said("Aucun appel modèle pour ce job.")
    controls = item.get("controls")
    if lane["kind"] == AGENT:
        usage = _usage(item.get("usage"), anchors)
    sections.append(_section(anchors, "Contrôles (%d)" % len(controls) if controls else "Contrôles",
                             _controls(controls, lane["kind"], anchors), open_="controles" in opened,
                             key="controles"))
    sections.append(_section(anchors, "Tokens et coût", usage, open_="usage" in opened, key="usage"))
    outputs = item.get("outputs") or []
    sections.append(_section(anchors, "Sorties (%d)" % len(outputs) if outputs else "Sorties",
                             _outputs(outputs, anchors), open_="sorties" in opened, key="sorties"))
    events_anchor, events_title, events_note, events_list = (anchors("events"), anchors("h3"), anchors("muted"),
                                                              anchors("event-list"))
    rows = []
    for number, recorded in enumerate(item["events"], start=1):
        at = paris_time(recorded["at"], None, True)
        lasted = _lasted_call(recorded.get("seconds")) if recorded["kind"] == TOOLS else None
        facts = [("Instant", "%s (Paris) · %s depuis le déclencheur"
                  % (at, relative(max(0, recorded["at"] - run["start"])))),
                 ("Nature", "%s · %s" % (recorded["label"], EVENT_KINDS[recorded["kind"]])),
                 ("Contenu", recorded.get("input") or recorded["text"])]
        if recorded.get("session"):
            facts.append(("Session", recorded["session"]))
        if recorded["kind"] == TOOLS:
            facts.append(("Durée", lasted or "non collectée : rien de ce que l’outil a rendu n’est enregistré"))
        facts += [("Job", item["name"]),
                  ("Source", "trace de la session %s" % recorded["session"] if recorded.get("session")
                   else item.get("source") or "tracker")]
        content = '<dl class="rn-event-facts">%s</dl>' % "\n".join(
            "<div><dt>%s</dt><dd>%s</dd></div>" % (_e(label), _e(value)) for label, value in facts)
        rows.append('<details class="rn-event" data-run-event="%d" %s%s><summary %s><time %s>%s</time>'
                    '<span class="rn-event-type %s" %s>%s</span><span class="rn-event-label" %s>%s</span>%s</summary>%s'
                    '</details>'
                    % (number, anchors("event"), " open" if event == number else "", anchors("summary"),
                       anchors("time"), at, recorded["kind"], anchors("event-type"), _e(recorded["label"]),
                       anchors("event-label"), _e(recorded["text"]),
                       '<small class="rn-event-lasted">%s</small>\n' % _e(lasted) if lasted else "", content))
    return (
        '<div class="rn-inspector" %s><section class="rn-detail" aria-label="Détail du job %s" %s>'
        '<header class="rn-inspector-head" %s>%s</header><div class="rn-inspector-grid" %s>'
        '<div class="rn-inspector-sections" %s>%s</div>'
        '<section class="rn-events" %s><h3 %s>Événements (%d)</h3><p class="rn-muted" %s>Horaires de Paris · '
        'ouvrir un événement pour lire ce qui en est enregistré.</p><div class="rn-event-list" %s>%s</div></section>'
        '</div></section></div>%s'
    ) % (inspector, _e(item["name"]), detail, head, pills, anchors("inspector-grid"), anchors("inspector-sections"),
         "".join(sections), events_anchor, events_title, len(rows), events_note, events_list, "".join(rows), EVENT_SCRIPT)


# --- what a job did (C2b) ---------------------------------------------------------------

# The categories of a usage, in the order of the table, as named there.
USAGE_ROWS = (("input", "Entrée"), ("cache_read", "Cache lu"), ("cache_write", "Cache écrit"), ("output", "Sortie"),
              ("reasoning", "Raisonnement"), ("total", "Total"))
PROVIDERS = {"codex": "Codex", "claude": "Claude Code"}
# How each provider counts, said under its table: what a total adds.
COUNTED = {
    "codex": "Codex compte le cache lu dans l’entrée et le raisonnement dans la sortie : le total est le sien, "
             "entrée plus sortie, pas la somme des lignes.",
    "claude": "Claude Code compte l’entrée, le cache écrit, le cache lu et la sortie à part, le raisonnement dans "
              "la sortie : le total est la somme des quatre, chaque message compté une fois.",
}
COST = "Non collecté"
STATES = {"passé": "good", "refusé": "bad", "en attente": "wait"}


def tokens(count):
    """« 54 537 »: a count of tokens, its thousands apart."""
    return "{:,}".format(int(count)).replace(",", "\u00a0")


def _run_usage(run):
    """What the head of a run says of its usage."""
    usage = run.get("usage")
    if not usage:
        return "Usage et coût non collectés"
    return "Tokens observés %s · usage %s · coût non collecté" % (tokens(usage["tokens"]),
                                                                  "partiel" if usage["partial"] else "complet")


def _lasted_call(seconds):
    """« 0,64 s », « 2,5 s », « 1 min 20 s »: how long a tool call lasted."""
    if not isinstance(seconds, (int, float)):
        return None
    if seconds >= 60:
        return duration(seconds)
    return "%s s" % _n(round(seconds, 2)).replace(".", ",")


def _controls(controls, kind, anchors):
    """Each attempt of the check of the job: its state, when it closed,
    what the check printed, the pieces it captured and whether the store
    still holds each."""
    if controls is None:
        if kind == HUMAN:
            return _said("Aucun contrôle : ce job est un geste de Benjamin.")
        return _said(NOT_COLLECTED)
    if not controls:
        return _said("Aucune tentative enregistrée : le contrôle n’a pas encore tourné.")
    out = []
    for number, control in enumerate(controls):
        state = control["state"]
        when = paris_time(control["end"], None, True) if control["end"] is not None else None
        title = " · ".join(part for part in ("Tentative %s" % control["attempt"], state, when) if part)
        if state == "en attente":
            body = _said("Verdict attendu ; pas de réussite enregistrée tant que la tentative n’est pas close.")
        elif control["printed"]:
            body = ('<p class="rn-muted">Ce que le contrôle a écrit :</p><pre class="rn-gate-log">%s</pre>'
                    % _e(control["printed"]))
        elif control["logged"]:
            body = _said("Le contrôle n’a rien écrit.")
        else:
            body = _said("Journal du contrôle %s." % UNCOLLECTED)
        if control["pieces"]:
            body += '<ul class="rn-pieces">%s</ul>' % "".join(
                '<li class="%s">%s · %s</li>' % ("" if piece["state"] == PRESENT else "missing", _e(piece["name"]),
                                                 _e(piece["state"]) + ("" if piece["state"] == PRESENT else
                                                                       " du magasin de preuves"))
                for piece in control["pieces"])
        elif state != "en attente":
            body += _said("Aucune pièce capturée pendant cette tentative.")
        out.append('<details class="rn-gate" %s%s><summary %s><span class="rn-gate-state %s">%s</span></summary>%s'
                   '</details>' % (anchors("gate"), " open" if number == len(controls) - 1 else "", anchors("summary"),
                                   STATES.get(state, ""), _e(title), body))
    return "".join(out)


def _usage(usage, anchors):
    """The usage of the job by provider and category, its cost, whether it
    is complete, and what each session counted."""
    if not usage or not usage["sessions"]:
        return _said("Usage non collecté : aucune session n’est enregistrée pour ce job.")
    if not usage["providers"]:
        return _said("Usage non collecté : aucun compteur de tokens n’est enregistré par le fournisseur.")
    out = []
    for provider, counts in sorted(usage["providers"].items()):
        rows = "".join("<tr><th scope=\"row\">%s</th><td>%s</td><td>%s</td></tr>"
                       % (label, tokens(counts[key]) if key in counts else "non fourni", COST)
                       for key, label in USAGE_ROWS)
        out.append('<table class="rn-usage" %s><caption>%s</caption><thead><tr><th scope="col">Catégorie</th>'
                   '<th scope="col">Tokens</th><th scope="col">Coût</th></tr></thead><tbody>%s</tbody></table>'
                   '<p class="rn-muted">%s Aucun tarif n’est collecté : le coût n’est pas calculé.</p>'
                   % (anchors("usage"), _e(PROVIDERS.get(provider, provider)), rows,
                      _e(COUNTED.get(provider, "Catégories telles que le fournisseur les donne."))))
    sessions = usage["sessions"]
    counted = [line for line in sessions if line["total"] is not None]
    if usage["complete"]:
        out.append(_said("Usage complet : %d session%s sur %d, chacune comptée jusqu’à son arrêt."
                         % (len(counted), "" if len(counted) == 1 else "s", len(sessions))))
    else:
        out.append(_said("Usage partiel : %d session%s sur %d avec un compteur%s."
                         % (len(counted), "" if len(counted) == 1 else "s", len(sessions),
                            ", une session encore en cours" if any(line["running"] for line in sessions) else "")))
    out.append('<ul class="rn-usage-sessions">%s</ul>' % "".join(
        "<li><strong>%s</strong> · %s</li>" % (
            _e(line["name"]),
            UNCOLLECTED if line["total"] is None else "%s tokens%s" % (tokens(line["total"]),
                                                                        " · en cours" if line["running"] else ""))
        for line in sessions))
    return "".join(out)


def _outputs(outputs, anchors):
    """The structured output each attempt recorded, as recorded, its
    validity and the artifacts it names."""
    if not outputs:
        return _said("Aucune sortie enregistrée · sortie structurée %se." % UNCOLLECTED)
    out = []
    for number, output in enumerate(outputs):
        valid = "valide" if output["valid"] else "non valide"
        text = (json.dumps(output["parsed"], ensure_ascii=False, indent=2) if output["valid"] else output["text"])
        artifacts = ('<p class="rn-muted">Artefacts : %s</p>' % " · ".join(_e(a) for a in output["artifacts"])
                     if output["artifacts"] else _said("Aucun artefact nommé."))
        out.append('<details class="rn-output" %s%s><summary %s>Sortie · tentative %s · <span class="%s">%s</span>'
                   '</summary><pre class="rn-output-text">%s</pre>%s</details>'
                   % (anchors("output"), " open" if number == len(outputs) - 1 else "", anchors("summary"),
                      _e(output["attempt"]), "good" if output["valid"] else "bad", valid, _e(text), artifacts))
    return "".join(out)


# --- what the trace of the sessions observed (C2a) --------------------------------------

UNCOLLECTED = "non collecté"
PROMPT_TITLES = {"system": "Prompt système", "user": "Prompt utilisateur"}


def _percent(observed):
    value = (observed or {}).get("context_pct")
    return "%s %%" % _n(float(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _lane_context(lane):
    """« Contexte · dernière session : 7 % · gpt-6.1-sol »: what the trace
    observed of the last session of the agent in the run."""
    last = lane.get("last_session") or {}
    observed = last.get("observed") or {}
    said = " · ".join(part for part in (_percent(observed), observed.get("model")) if part) or UNCOLLECTED
    return '<small>Contexte · dernière session : %s</small>' % _e(said)


def _configuration(run, item, lane, chosen, anchors):
    """The configuration in effect for the session `chosen`, as observed,
    then the one declared for the role of the job: never one for the
    other."""
    def rows(pairs):
        return '<dl class="rn-config">%s</dl>' % "".join(
            "<div><dt>%s</dt><dd>%s</dd></div>" % (_e(label), _e(value if value else UNCOLLECTED))
            for label, value in pairs)

    if chosen is None:
        effective = _said("Aucune session n’est enregistrée pour ce job : configuration effective %s." % UNCOLLECTED)
    else:
        observed = chosen.get("observed") or {}
        window = observed.get("context_window")
        context = _percent(observed)
        if context and isinstance(window, (int, float)):
            context += " d’une fenêtre de %s tokens" % "{:,}".format(int(window)).replace(",", "\u202f")
        environment = " · ".join(part for part in (observed.get("work_dir"), observed.get("permission_mode") and
                                                   "permissions %s" % observed["permission_mode"]) if part)
        effective = rows((("Agent", "%s · %s" % (lane["who"], lane["role"])), ("Session", chosen["name"]),
                          ("Fournisseur", observed.get("provider")), ("Modèle", observed.get("model")),
                          ("Effort", observed.get("effort")), ("Outils", " · ".join(observed.get("tools") or [])),
                          # No source reports the mission of a session: the
                          # name of its job is not one.
                          ("Environnement", environment), ("Mission", None), ("Contexte observé", context)))
    declared = (run.get("declared") or {}).get(item.get("role") or "")
    if declared:
        when = declared.get("at")
        said = rows((("Agent", declared.get("agent")), ("Fournisseur", declared.get("provider")),
                     ("Modèle", declared.get("model"))))
        said += ('<p class="rn-muted">Écrite par l’usine quand la session a pris le ticket%s.</p>'
                 % (" (%s)" % _e(when) if when else ""))
    else:
        said = _said("Aucune configuration n’est déclarée pour ce rôle sur le ticket : %s." % UNCOLLECTED)
    return ('<h4 class="rn-config-title">Configuration effective</h4>%s'
            '<h4 class="rn-config-title">Configuration déclarée</h4>%s' % (effective, said))


def _session_href(run, item, name):
    return "/runs/job?" + urllib.parse.urlencode({"run": run["id"], "job": item["id"], "session": name})


def _sessions(run, item, placed, chosen):
    """The sessions of the job, in the order they ran: each a link that
    shows its own configuration and prompts, the one shown saying so. An
    end the supervisor did not record is said not collected (in progress
    for the last session of a job that runs), and so is a start."""
    if not placed:
        return _said("Aucune session n’est enregistrée pour ce job : %s." % UNCOLLECTED)
    out = []
    for session in placed:
        observed = session.get("observed") or {}
        if session["end"] is not None:
            end = relative(session["end"] - run["start"])
        else:
            end = "en cours" if item["open"] and session is placed[-1] else UNCOLLECTED
        said = "%s · contexte observé %s" % (observed.get("model") or "modèle %s" % UNCOLLECTED,
                                             _percent(observed) or UNCOLLECTED)
        out.append('<a class="rn-session" href="%s" data-session-link%s><strong>%s%s</strong><small>%s → %s</small>'
                   '<span>%s</span></a>'
                   % (_e(_session_href(run, item, session["name"])),
                      ' aria-current="true"' if session is chosen else "", _e(session["name"]),
                      ' <em class="rn-session-shown">Affichée</em>' if session is chosen else "",
                      relative(session["start"] - run["start"]) if session["start"] is not None else UNCOLLECTED,
                      end, _e(said)))
    return ('<div class="rn-sessions">%s</div><p class="rn-muted">Historique du job ; la lane affiche seulement la '
            'dernière session de cet agent dans le run.</p>' % "".join(out))


def _rendered(text):
    """A prompt as it reads: its titles, its paragraphs, its lists."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            out.append("<h5>%s</h5>" % _e(stripped.lstrip("#").strip()))
        elif stripped.startswith(("- ", "* ")):
            out.append("<p>• %s</p>" % _e(stripped[2:]))
        else:
            out.append("<p>%s</p>" % _e(stripped))
    return "".join(out)


def _prompts(chosen, anchors, opened, raw):
    """What the session `chosen` was sent, exactly: each prompt rendered or
    raw, with its version; what no trace recorded is said not collected."""
    if chosen is None:
        return _said("Aucune session n’est enregistrée pour ce job : prompts %ss." % UNCOLLECTED)
    sent = (chosen.get("observed") or {}).get("prompts") or []
    if not sent:
        return _said("Aucun prompt n’est enregistré pour la session %s : %s." % (chosen["name"], UNCOLLECTED))
    out = ['<p class="rn-muted">Session %s · le texte exact transmis, avec sa version.</p>' % _e(chosen["name"])]
    if not any(prompt["role"] == "system" for prompt in sent):
        out.append(_said("Prompt système : %s (le fournisseur de la session ne l’enregistre pas)." % UNCOLLECTED))
    for prompt in sent:
        role = prompt["role"]
        lines = len(prompt["text"].splitlines()) or 1
        shown_raw = role in raw
        out.append(
            '<details class="rn-prompt" %s data-open-key="%s"%s><summary %s>%s<span>%d ligne%s · version %s</span>'
            '</summary><div class="rn-format" role="group" aria-label="Affichage du %s">'
            '<button type="button" data-format="rendered" data-role="%s" aria-pressed="%s">Rendu</button>'
            '<button type="button" data-format="raw" data-role="%s" aria-pressed="%s">Brut</button></div>'
            '<div class="rn-prompt-rendered" %s%s>%s</div><pre class="rn-prompt-raw" %s%s>%s</pre></details>'
            % (anchors("prompt-section"), role, " open" if role in opened else "", anchors("summary"),
               PROMPT_TITLES.get(role, "Prompt"), lines, "" if lines == 1 else "s", _e(prompt["version"]),
               _e(PROMPT_TITLES.get(role, "prompt").lower()), role, "false" if shown_raw else "true", role,
               "true" if shown_raw else "false", anchors("prompt-rendered"), " hidden" if shown_raw else "",
               _rendered(prompt["text"]), anchors("prompt-raw"), "" if shown_raw else " hidden", _e(prompt["text"])))
    return "".join(out)


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

// The sections open and the prompts shown raw are written in the address,
// and carried by a session chosen in the history: a reload, or another
// session, keeps them.
function rnKeep(address) {
  var open = [], raw = [];
  document.querySelectorAll('[data-open-key]').forEach(function (item) {
    if (item.open && open.indexOf(item.getAttribute('data-open-key')) < 0) { open.push(item.getAttribute('data-open-key')); }
  });
  document.querySelectorAll('[data-format="raw"][aria-pressed="true"]').forEach(function (button) {
    raw.push(button.getAttribute('data-role'));
  });
  address.searchParams.set('ouvert', open.join(','));
  if (raw.length) { address.searchParams.set('brut', raw.join(',')); } else { address.searchParams.delete('brut'); }
  return address;
}
document.querySelectorAll('[data-open-key]').forEach(function (item) {
  item.addEventListener('toggle', function () {
    history.replaceState(null, '', rnKeep(new URL(location.href)).toString());
  });
});
document.querySelectorAll('.rn-format button').forEach(function (button) {
  button.addEventListener('click', function () {
    var prompt = button.closest('.rn-prompt'), raw = button.getAttribute('data-format') === 'raw';
    prompt.querySelector('.rn-prompt-rendered').hidden = raw;
    prompt.querySelector('.rn-prompt-raw').hidden = !raw;
    prompt.querySelectorAll('.rn-format button').forEach(function (other) {
      other.setAttribute('aria-pressed', String(other === button));
    });
    history.replaceState(null, '', rnKeep(new URL(location.href)).toString());
  });
});
document.querySelectorAll('[data-session-link]').forEach(function (link) {
  link.addEventListener('click', function () {
    link.href = rnKeep(new URL(link.href, location.href)).toString();
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
.rn-badge.ended{color:var(--pn-muted-text)}
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
.rn-event>summary{display:grid;grid-template-columns:66px 92px minmax(0,1fr) auto;gap:8px;font:12px ui-monospace,monospace;padding:12px 0;align-items:center}
.rn-event-label{overflow-wrap:anywhere}
.rn-event-type{color:var(--rn-other)}
.rn-event-type.tools{color:var(--rn-code)}.rn-event-type.controls{color:var(--rn-ok)}.rn-event-type.sessions{color:var(--rn-agent)}
.rn-event-facts{display:grid;gap:8px;margin:4px 0 14px;font-size:13px}
.rn-event-facts dt{font-size:12px;color:var(--pn-muted-text)}.rn-event-facts dd{margin:2px 0 0;overflow-wrap:anywhere}
.rn-config-title{margin:14px 0 6px;font-size:13px;font-weight:600}
.rn-config{display:grid;gap:8px;margin:0;font-size:13px}
.rn-config>div{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px}
.rn-config dt{color:var(--pn-muted-text)}.rn-config dd{margin:0;overflow-wrap:anywhere}
.rn-sessions{display:grid;gap:8px;margin-top:12px}
.rn-session{display:grid;gap:3px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;color:inherit;text-decoration:none;font-size:13px}
.rn-session strong{font:13px ui-monospace,monospace;overflow-wrap:anywhere}
.rn-session small{color:var(--pn-muted-text);font-size:12px}
.rn-session span{overflow-wrap:anywhere}
.rn-session[aria-current]{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.rn-session-shown{margin-left:8px;padding:1px 6px;border:1px solid currentColor;border-radius:4px;font:600 11px system-ui,sans-serif;font-style:normal;white-space:nowrap}
.rn-session:hover{border-color:var(--accent)}
.rn-session:focus-visible,.rn-prompt>summary:focus-visible,.rn-format button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* A prompt of a closed section is not laid out: its title is no control to reach. */
.rn-section:not([open]) .rn-prompt{display:none}
.rn-prompt{margin-top:12px;border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0}
.rn-prompt>summary{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;cursor:pointer;font-weight:600;font-size:13px}
.rn-prompt>summary span{font-size:12px;font-weight:400;color:var(--pn-muted-text);overflow-wrap:anywhere}
.rn-format{display:flex;gap:6px;margin:12px 0}
.rn-format button{padding:5px 10px;font-size:12px;border:1px solid var(--pn-control-line);border-radius:6px;background:transparent;color:var(--ink);cursor:pointer;min-height:24px}
.rn-format button[aria-pressed="true"]{border-color:var(--accent);background:var(--pn-surface-2)}
.rn-prompt-rendered{overflow-wrap:anywhere;font-size:13px}
.rn-prompt-rendered h5{font-size:14px;margin:14px 0 6px}
.rn-prompt-rendered p{margin:4px 0}
.rn-prompt-raw{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace;background:var(--pn-surface-2);padding:10px;border-radius:6px}
/* What a job did (C2b): its controls, its usage, its outputs, the duration of a tool call. */
.rn-section:not([open]) .rn-gate,.rn-section:not([open]) .rn-output{display:none}
.rn-gate,.rn-output{margin-top:12px;border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0}
.rn-gate>summary,.rn-output>summary{cursor:pointer;font-weight:600;font-size:13px;overflow-wrap:anywhere}
.rn-gate>summary:focus-visible,.rn-output>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rn-gate-state.good,.rn-output .good{color:var(--ok)}.rn-gate-state.bad,.rn-output .bad{color:var(--pn-warn-text)}
.rn-gate-state.wait{color:var(--pn-muted-text)}
.rn-gate-log,.rn-output-text{margin:8px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace;background:var(--pn-surface-2);padding:10px;border-radius:6px}
.rn-pieces,.rn-usage-sessions{margin:10px 0 0;padding-left:18px;font-size:13px;overflow-wrap:anywhere}
.rn-pieces li.missing{color:var(--pn-warn-text)}
.rn-usage{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}
.rn-usage caption{text-align:left;font-weight:600;padding-bottom:4px}
.rn-usage th,.rn-usage td{border-bottom:1px solid var(--line);padding:8px 3px;text-align:right;font-weight:400}
.rn-usage th:first-child{text-align:left}.rn-usage thead th{color:var(--pn-muted-text);font-size:12px}
.rn-usage tbody tr:last-child th,.rn-usage tbody tr:last-child td{font-weight:600}
.rn-event-lasted{font-size:11px;color:var(--pn-muted-text);white-space:nowrap}
@media (max-width:800px){.rn-config>div{grid-template-columns:1fr;gap:2px}}
@media (max-width:1100px){.rn-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:800px){.rn-grid{grid-template-columns:1fr}.rn-inspector-grid{grid-template-columns:1fr}
  :root{--rn-name:120px}.rn-lane-name{padding:14px 10px}
  .rn-detail{padding:15px}.rn-event>summary{grid-template-columns:62px 70px minmax(0,1fr) auto;font-size:11px}}
"""
