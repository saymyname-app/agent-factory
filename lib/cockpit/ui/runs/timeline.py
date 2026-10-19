"""The timeline of a run, « frise du run » (T03R Prototype Fold, af-hd8wzb;
Spec af-2zseit, user stories 129, 131, 132 and 175; Validated Prototype
prototype/c01-parcours-20261011 at d8cb462, prototypes/c01-flow/frozen-runs).

    view = timeline_view(snapshot, run="…", job="…")
    main_html = render_timeline(view)

:func:`timeline_view` reads, from the read model's snapshot, the traces of
the runs the tracker keeps (one open bead per run, its record
``gc.run_trace``) and picks the run shown: the one ``run`` names, else the
one its trace marks open, else the last one started. :func:`render_timeline`
draws it inside the shell of :mod:`cockpit.ui.panorama.shell`, as its own
``<main>``. Neither reads a source.

What is drawn is what the trace says, and nothing else: the workflow, the
title, the status, the start (HH:MM, Paris), the elapsed seconds and the
end; one lane for the human, one for the code, then one per agent that has a
job in the run -- however many sessions it had --, with the context of its
last session when one was observed; each job at its start, as long as it
lasted (or, still open, up to the horizon of the run), with the marks of its
events, coloured by type. No job, event or verdict is added by a clock: an
open run's horizon is its elapsed time as observed. A trace that says its
observation is not confirmed, or a reading of the supervisor or the tracker
that is no longer current, keeps the last observation under a notice.

A job is selected by its control (``?job=``), a form of its own sent by GET:
the page drawn again marks it (``aria-current``) and scrolls the timeline to
it, so a refresh keeps it. The detail of a job under the timeline is T03S's;
its place is drawn empty (``inspector``), as the reference draws it.

Every part carries the anchor of the reference (``data-anchor``), named and
numbered as the frozen pages are: the first of a name bare (``lane``), the
next ones numbered from 2 (``lane-2``) -- see :class:`RunAnchors`.
"""
import html
import json
import urllib.parse

from cockpit.core.freshness import FRESH
from cockpit.ui.panorama.shell import anchor_slug

RUN_TRACE = "gc.run_trace"
TIMELINE = "/runs/run"
LOADING, ERROR, EMPTY, CONTENT = "loading", "error", "empty", "content"
LEGEND = ("Origine 0 : déclencheur · traits : outils (turquoise), contrôles (vert), sessions (violet), "
          "autres (gris) · clic : détail")
STALE_NOTICE = "Lecture périmée · dernière observation conservée, activité actuelle non confirmée."
# The width of the column of the lanes' names, and the margin after the
# track, as the reference lays them out (px).
LANE_NAME_PX, TRACK_MARGIN_PX = 165, 28
# The narrowest the track is drawn, as the reference draws it on a phone.
TRACK_MIN_PX = 780 - LANE_NAME_PX - TRACK_MARGIN_PX
# A lane: its jobs' first row at 22 px from its top, 111 px tall with one
# row; each other row 76 px lower (a job is 68 px tall).
JOB_TOP_PX, TRACK_HEIGHT_PX, ROW_PX = 22, 111, 76


class RunAnchors:
    """Numbers the anchors of one page as the frozen Runs pages do: the
    first of a name bare, ``data-anchor="lane"``, then ``lane-2``…"""

    def __init__(self):
        self._counts = {}

    def __call__(self, name):
        self._counts[name] = self._counts.get(name, 0) + 1
        count = self._counts[name]
        return 'data-anchor="%s"' % html.escape(name if count == 1 else "%s-%d" % (name, count))


def timeline_view(snapshot, run=None, job=None):
    """What the timeline shows: ``state`` (loading, error, empty, content),
    ``stale``, ``run`` (the trace shown, with its ``id``), ``job`` (the id of
    the job selected, or None)."""
    view = {"state": CONTENT, "stale": False, "run": None, "job": None}
    beads_row = snapshot.get("beads")
    if beads_row is None or beads_row["value"] is None:
        view["state"] = ERROR if (beads_row or {}).get("failed_at") is not None else LOADING
        return view
    traces = []
    for bead in beads_row["value"]:
        trace = _trace(bead) if isinstance(bead, dict) else None
        if trace is not None:
            traces.append(dict(trace, id=bead.get("id")))
    if not traces:
        view["state"] = EMPTY
        return view
    shown = (next((trace for trace in traces if trace["id"] == run), None)
             or next((trace for trace in traces if trace.get("open") is True), None)
             or max(traces, key=lambda trace: trace["started"]))
    view["run"] = shown
    view["job"] = job if any(j["id"] == job for j in shown["jobs"]) else None
    rows = [snapshot[name] for name in ("gc", "beads") if snapshot.get(name)]
    view["stale"] = shown.get("stale") is True or any(row["freshness"] != FRESH for row in rows)
    return view


def _trace(bead):
    """The trace of a run ``bead`` carries, or None: a record with its
    title, status, start, elapsed seconds, lanes and jobs."""
    raw = (bead.get("metadata") or {}).get(RUN_TRACE)
    if not isinstance(raw, str):
        return None
    try:
        trace = json.loads(raw)
    except ValueError:
        return None
    if not (isinstance(trace, dict) and isinstance(trace.get("title"), str) and isinstance(trace.get("status"), str)
            and isinstance(trace.get("started"), str) and isinstance(trace.get("elapsed"), (int, float))
            and isinstance(trace.get("lanes"), list) and isinstance(trace.get("jobs"), list)):
        return None
    lanes = {lane.get("id") for lane in trace["lanes"] if isinstance(lane, dict)}
    if not all(isinstance(job, dict) and job.get("lane") in lanes and isinstance(job.get("start"), (int, float))
               for job in trace["jobs"]):
        return None
    return trace


# --- how a duration is said -------------------------------------------------------

def duration(seconds):
    """« 18 s », « 7 min 30 s », « 1 h 5 min »."""
    s = max(0, int(seconds))
    if s < 60:
        return "%d s" % s
    if s < 3600:
        return "%d min %d s" % (s // 60, s % 60)
    return "%d h %d min" % (s // 3600, s % 3600 // 60)


def tick(seconds):
    """A mark of the axis: « 0s », « 1m30s », « 3m », « 1h5m »."""
    s = int(seconds)
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dm%s" % (s // 60, "%02ds" % (s % 60) if s % 60 else "")
    return "%dh%dm" % (s // 3600, s % 3600 // 60)


def _thousands(n):
    """A count with the French thousands separator (« 591 653 »)."""
    return "{:,}".format(int(n)).replace(",", " ")


# --- what the timeline draws -----------------------------------------------------------

def _total(run):
    return run["end"] if run.get("end") is not None else run["elapsed"]


def _lanes_used(run):
    """The human and the code, always; then each lane with a job in the run."""
    with_jobs = {job["lane"] for job in run["jobs"]}
    return [lane for lane in run["lanes"] if lane.get("kind") in ("human", "code") or lane["id"] in with_jobs]


def _last_session_context(lane, run):
    """The context of the last session observed in ``lane``, or None."""
    sessions = [session for job in run["jobs"] if job["lane"] == lane["id"]
                for session in (job.get("sessions") or []) if isinstance(session, dict)]
    sessions.sort(key=lambda session: session.get("from") or 0, reverse=True)
    return sessions[0].get("context") if sessions else None


def _usage_line(run):
    """The tokens the jobs of ``run`` say were used, and the cost: an empty
    list when none is known."""
    known = [job["usage"] for job in run["jobs"] if isinstance(job.get("usage"), dict) and job["usage"].get("collected")]
    if not known:
        return []
    total = sum(sum(usage.get(key) or 0 for key in ("input", "output", "reasoning", "cache_read", "cache_write"))
                for usage in known)
    complete = run.get("usage_complete") is True
    costs = [usage.get("cost") for usage in known]
    cost = ("Coût non collecté" if any(c is None for c in costs)
            else "Coût %s" % _thousands(sum(costs)))
    return ["Tokens connus %s%s" % (_thousands(total), "" if complete else " · usage partiel"), cost]


def _mark_kind(event_type):
    """The colour of an event's mark: tools, gates (contrôles), sessions,
    other."""
    if event_type == "tool_call":
        return "tools"
    if event_type.startswith("gate_"):
        return "gates"
    if event_type in ("agent_start", "session_end"):
        return "sessions"
    return "other"


def _label_px(job, total):
    """How wide (px) the control of ``job`` is drawn at most: its title in
    13 px bold, its duration in 11 px, each at a generous width per
    character, and its padding."""
    return max(len(_job_title(job)) * 8.2, len(_job_small(job, total)) * 6.8) + 26


def lane_rows(run, lane):
    """The row of each job of ``lane`` (job id -> 0, 1…): a job goes on the
    first row where the control of the job before it ends before it starts,
    measured on the narrowest track the timeline is drawn on -- a wider one
    only spreads them more --, so that no title said whole runs into
    another."""
    total = _total(run) or 1
    ends, rows = [], {}
    for job in sorted((job for job in run["jobs"] if job["lane"] == lane["id"]), key=lambda job: job["start"]):
        left = TRACK_MIN_PX * job["start"] / total
        row = next((index for index, end in enumerate(ends) if end + 8 <= left), len(ends))
        if row == len(ends):
            ends.append(0)
        ends[row] = left + _label_px(job, total)
        rows[job["id"]] = row
    return rows


def _job_title(job):
    return ("● " if job.get("end") is None else "✓ ") + job["name"]


def _job_small(job, total):
    end = job["end"] if job.get("end") is not None else total
    return duration(end - job["start"]) + (" · en cours" if job.get("end") is None else "")


def render_timeline(view):
    """The ``<main>`` of the timeline of the run of ``view``."""
    anchors = RunAnchors()
    head = '<main class="pn-main rt" %s><header class="rt-brand" %s>Cockpit <small %s>USINE + PROJETS</small></header>' % (
        anchors("shell"), anchors("brand"), anchors("small"))
    run = view["run"]
    if run is None:
        return head + '<div class="rt-app">%s</div></main>' % _without_run(view["state"])
    return head + '<div class="rt-app">%s</div></main>' % _run(view, run, anchors)


def _without_run(state):
    said = {
        LOADING: "Lecture des runs en cours…",
        ERROR: "Les runs ne sont pas lisibles : la source ne répond pas. L’état réel est inconnu.",
        EMPTY: "Aucun run observé pour l’instant.",
    }[state]
    return '<h1>Runs</h1><p class="rt-empty">%s</p>' % html.escape(said)


def _run(view, run, a):
    e = html.escape
    total = _total(run)
    finished = run.get("end") is not None
    status = run["status"]
    tone = "live" if status == "En cours" else "wait" if status == "Ta décision" else ""
    badge_anchor = a("badge")
    badge = ('<span class="rt-badge %s" %s>%s%s</span>'
             % (tone, badge_anchor, "" if finished else '<span class="rt-live-dot" %s></span>' % a("live-dot"),
                ("✓ " if finished else "") + e(status)))
    crumb = ('<div class="rt-crumb" %s><form class="pn-open" method="get" action="/runs">'
             '<button type="submit" class="rt-back" %s>← Runs</button></form><span %s>%s</span></div>'
             % (a("crumb"), a("back"), a("span"), e(run["type"])))
    title = "<h1 %s>%s</h1>" % (a("h1"), e(run["title"]))
    summary_parts = [badge, "<span %s>Déclenché à %s (Paris)</span>" % (a("span"), e(run["started"])),
                     '<strong class="rt-mono" %s>%s</strong>' % (a("mono"), duration(total)),
                     "<span %s>%s</span>" % (a("span"), "Temps final figé" if finished else "Horizon : maintenant")]
    summary_parts += ["<span %s>%s</span>" % (a("span"), e(line)) for line in _usage_line(run)]
    summary = '<div class="rt-summary" %s>%s</div>' % (a("run-summary"), "".join(summary_parts))
    current = [job["name"] for job in run["jobs"] if job.get("end") is None]
    lines = ""
    if current:
        lines += "<p %s><strong %s>%s</strong>%s</p>" % (
            a("p"), a("strong"), "Derniers jobs observés : " if view["stale"] else "Job courant : ",
            e(" · ".join(current)))
    if view["stale"]:
        lines += '<p class="rt-notice" %s>%s</p>' % (a("notice"), e(STALE_NOTICE))
    return crumb + title + summary + lines + _chart(view, run, total, a) + '<div id="inspector" %s></div>' % a(
        "inspector")


def _chart(view, run, total, a):
    e = html.escape
    box, scroll, chart = a("chart-box"), a("scroll"), a("chart")
    ticks = "".join('<span class="rt-tick" style="left:%d%%" %s>%s</span>' % (i * 20, a("tick"), tick(round(total * i / 5)))
                    for i in range(6))
    axis = ('<div class="rt-axis" %s><div class="rt-axis-title" %s>Responsable</div><div class="rt-ticks" %s>%s</div></div>'
            % (a("axis"), a("axis-title"), a("ticks"), ticks))
    lanes = []
    for lane in _lanes_used(run):
        lane_anchor, name_anchor = a("lane"), a("lane-name")
        name = "<strong %s>%s</strong><small %s>%s</small>" % (a("strong"), e(lane["name"]), a("small"), e(lane["role"]))
        if lane.get("kind") == "agent":
            context = _last_session_context(lane, run)
            name += ('<small %s>Contexte · dernière session<br>%s</small>'
                     '<span class="rt-context" %s><i style="width:%s%%" %s></i></span>'
                     % (a("small"), "non collecté" if context is None else "%s %%" % context, a("context-meter"),
                        context or 0, a("i")))
        track_anchor = a("track")
        rows = lane_rows(run, lane)
        jobs = "".join(_job(view, run, lane, job, total, rows[job["id"]], a)
                       for job in run["jobs"] if job["lane"] == lane["id"])
        height = ' style="min-height:%dpx"' % (TRACK_HEIGHT_PX + ROW_PX * max(rows.values())) if rows and max(
            rows.values()) else ""
        lanes.append('<div class="rt-lane" %s><div class="rt-lane-name" %s>%s</div><div class="rt-track"%s %s>%s</div></div>'
                     % (lane_anchor, name_anchor, name, height, track_anchor, jobs))
    return ('<div class="rt-chart-box" %s><div class="rt-scroll" %s><div class="rt-chart" %s>%s%s</div></div>'
            '<div class="rt-legend" %s>%s</div></div>'
            % (box, scroll, chart, axis, "".join(lanes), a("legend"), e(LEGEND)))


def _job(view, run, lane, job, total, row, a):
    e = html.escape
    open_job = job.get("end") is None
    end = total if open_job else job["end"]
    left, width = 100 * job["start"] / (total or 1), 100 * (end - job["start"]) / (total or 1)
    selected = view["job"] == job["id"]
    classes = " ".join(filter(None, ("rt-job", lane.get("kind", ""), "current" if open_job else "",
                                     "selected" if selected else "")))
    job_anchor = a("job")
    pick = ('<button type="submit" class="rt-pick" name="job" value="%s"%s %s><strong %s>%s</strong>'
            '<small %s>%s</small></button>'
            % (e(job["id"]), ' aria-current="true"' if selected else "", a("job-select"), a("strong"),
               e(_job_title(job)), a("small"), e(_job_small(job, total))))
    marks_anchor = a("marks")
    marks = "".join(
        '<button type="submit" class="rt-mark %s" name="job" value="%s" title="%s" aria-label="%s" %s></button>'
        % (_mark_kind(event["type"]), e(job["id"]), e(label), e("Événement " + label),
           a(anchor_slug("Événement " + label)))
        for event in (job.get("events") or []) if isinstance(event, dict) and isinstance(event.get("type"), str)
        for label in ["%s · %s" % (event["type"], event.get("label") or "")])
    return ('<div class="%s" data-job="%s" title="%s" style="left:%s%%;width:%s%%;top:%dpx" %s>'
            '<form class="rt-form" method="get" action="%s"><input type="hidden" name="run" value="%s">%s'
            '<span class="rt-marks" %s>%s</span></form></div>'
            % (classes, e(job["id"]), e("%s · %s" % (job["name"], duration(end - job["start"]))), left, width,
               JOB_TOP_PX + ROW_PX * row, job_anchor, TIMELINE, e(run["id"] or ""), pick, marks_anchor, marks))


def timeline_query(path_with_query):
    """The run and the job a request of the timeline names (``?run=``,
    ``?job=``), each None when absent."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(path_with_query).query)
    return (query.get("run") or [None])[0], (query.get("job") or [None])[0]


# The tokens of the Runs reference under its names and with its values,
# dark and light as the browser prefers -- they follow the shell's, so the
# page holds these. The others are the page's own: --rt-muted-text, the
# muted text, darker in the light theme where --muted is under 4.5:1 on the
# axis; --rt-wait-text, the text of a decision awaited, darker in the light
# theme where --human is; --rt-control-line, the box of a control, 3:1 at
# least on the background. The type of the reference: 15 px system-ui,
# normal leading, a paragraph at 1.5; durations and ticks in ui-monospace.
CSS = """
@media (prefers-color-scheme: dark){
  :root{color-scheme:dark;--bg:#0d1015;--surface:#161a21;--line:#2a313d;--ink:#e6e9ef;--muted:#8a93a4;
    --accent:#8fa3ff;--human:#e4bc6d;--code:#55b5ae;--agent:#a897eb;--ok:#4dc48b;
    --rt-muted-text:#8a93a4;--rt-wait-text:#e4bc6d;--rt-control-line:#707c91;--rt-axis:#1d222b;
    --rt-current:#1e2644;--rt-selected:#e6e9ef}
}
@media (prefers-color-scheme: light){
  :root{color-scheme:light;--bg:#f2f4f8;--surface:white;--line:#d8dde6;--ink:#151b26;--muted:#687286;
    --accent:#2b4cc0;--human:#e4bc6d;--code:#55b5ae;--agent:#a897eb;--ok:#1f7b4b;
    --rt-muted-text:#566175;--rt-wait-text:#85590f;--rt-control-line:#788396;--rt-axis:#eaeef4;
    --rt-current:#e3e8fa;--rt-selected:#151b26}
}
.rt{font:15px system-ui,sans-serif;line-height:normal;max-width:1450px;padding:24px;color:var(--ink)}
.rt button{font:inherit;line-height:inherit;color:inherit;cursor:pointer}
.rt p{line-height:1.5}
.rt :is(button,a,summary):focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rt-brand{font-size:24px;margin:4px 0 25px}
.rt-brand small{font-size:13px;letter-spacing:1px;color:var(--rt-muted-text);margin-left:10px}
.rt-crumb{color:var(--rt-muted-text);font-size:14px;display:flex;align-items:center;gap:10px}
.rt-back{border:1px solid var(--rt-control-line);background:var(--surface);border-radius:8px;padding:9px 13px}
.rt-back:hover{border-color:var(--accent)}
.rt h1{font-size:27px;margin:15px 0 9px;overflow-wrap:anywhere}
.rt-summary{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:18px 0 24px}
.rt-summary span{color:var(--rt-muted-text)}
.rt-summary strong{font-size:14px}
.rt-mono{font:13px ui-monospace,monospace}
.rt-summary .rt-badge.live{color:var(--accent)}
.rt-summary .rt-badge.wait{color:var(--rt-wait-text)}
.rt-live-dot{display:inline-block;width:7px;height:7px;border-radius:100%;background:var(--accent);margin-right:6px}
.rt-notice{color:var(--rt-wait-text);margin-top:12px}
.rt-empty{color:var(--rt-muted-text)}
.rt-chart-box{border:1px solid var(--line);border-radius:10px;background:var(--surface)}
.rt-scroll{overflow-x:auto;border-radius:10px 10px 0 0}
.rt-chart{min-width:820px}
@media (max-width:650px){.rt-chart{min-width:780px}}
.rt-axis,.rt-lane{display:grid;grid-template-columns:165px minmax(0,1fr)}
.rt-axis{height:44px;background:var(--rt-axis)}
.rt-axis-title{padding:14px 16px;color:var(--rt-muted-text);font-size:12px}
.rt-ticks{position:relative;margin-right:28px}
.rt-tick{position:absolute;top:14px;color:var(--rt-muted-text);font:12px ui-monospace,monospace;transform:translateX(-50%);white-space:nowrap}
.rt-tick:first-child{transform:none}
.rt-tick:last-child{transform:translateX(-100%)}
.rt-lane{min-height:112px;border-top:1px solid var(--line)}
.rt-lane-name{padding:20px 16px;border-right:1px solid var(--line)}
.rt-lane-name strong{display:block;font-size:14px}
.rt-lane-name small{display:block;color:var(--rt-muted-text);font-size:12px;margin-top:7px}
.rt-context{display:block;width:90%;height:3px;background:var(--line);margin-top:6px}
.rt-context i{display:block;height:3px;background:var(--accent)}
.rt-track{position:relative;margin-right:28px;min-height:111px;
  background:repeating-linear-gradient(90deg,transparent 0,transparent calc(20% - 1px),#2a313d66 20%)}
.rt-job{position:absolute;height:68px;border-radius:7px;border:1px solid #a897eb77;background:#a897eb16;min-width:10px}
.rt-job.human{border-color:#e4bc6d88;background:#e4bc6d15}
.rt-job.code{border-color:#55b5ae77;background:#55b5ae16}
.rt-job.current{border:2px solid var(--accent);background:var(--rt-current);box-shadow:0 0 0 2px #8fa3ff18}
.rt-job.selected{outline:2px solid var(--rt-selected)}
.rt-form{display:contents}
.rt-pick{display:inline-block;vertical-align:top;position:relative;z-index:1;min-width:100%;width:max-content;
  height:53px;border:0;background:transparent;border-radius:0;text-align:left;padding:8px 10px;white-space:nowrap}
.rt-pick:hover{background:#8fa3ff10}
.rt-pick strong{display:block;font-size:13px}
.rt-pick small{display:block;font-size:11px;color:var(--rt-muted-text);margin-top:6px}
.rt-marks{position:absolute;bottom:2px;left:5px;right:5px;height:12px;display:flex;justify-content:space-around;
  gap:1px;align-items:center}
.rt-mark{flex:0 1 12px;min-width:3px;height:12px;border:0;border-radius:0;padding:0;background:transparent;position:relative}
.rt-mark:after{content:'';position:absolute;left:40%;width:3px;top:2px;height:8px;background:var(--muted)}
.rt-mark.tools{display:flex;font-size:13px}
.rt-mark.tools:after{background:var(--code)}
.rt-mark.gates:after{background:var(--ok)}
.rt-mark.sessions:after{background:var(--agent)}
.rt-mark:hover{background:#ffffff25}
.rt-legend{padding:12px 18px;border-top:1px solid var(--line);font-size:13px;color:var(--rt-muted-text)}
@media (max-width:650px){
  .rt{padding:18px 12px}
  .rt-lane-name{padding:15px 10px}
  .rt-brand small{font-size:11px}
}
"""

# What the page does once drawn: the timeline scrolled to the job selected,
# and the focus put on it.
SCRIPT = """<script>
(function () {
  var selected = document.querySelector('.rt-pick[aria-current="true"]');
  if (!selected) { return; }
  var scroller = selected.closest('.rt-scroll');
  if (scroller) {
    var box = scroller.getBoundingClientRect(), at = selected.getBoundingClientRect();
    var left = at.left - box.left + scroller.scrollLeft;
    if (at.left < box.left || at.right > box.right) {
      scroller.scrollLeft = Math.max(0, left - Math.max(12, (box.width - at.width) / 2));
    }
  }
  try { selected.focus({preventScroll: true}); } catch (error) { selected.focus(); }
})();
</script>"""
