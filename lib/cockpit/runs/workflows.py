"""The runs of the destination Runs: one run per complete workflow, from its
trigger to its end or now (C1, af-lzti7w; Spec af-fgcw0d, user stories 127
to 135).

    beads = read_workflow_beads(bd_bin)
    runs = workflow_runs(beads, agents, now)
    run, job = find_job(runs, run_id, job_id)

Everything a run shows is a fact the code already recorded in the tracker,
or a session the supervisor lists; nothing is collected for the cockpit
alone, and the clock only moves the horizon of what is still open.

What a run is
-------------
- **A D01 delivery**: a convoy carrying the new-flow mark (``gc.flow.mark``)
  and the tickets of its graph (same ``gc.graph_digest``). Its jobs are the
  steps of the workflows run for those tickets -- a workflow root
  (``gc.kind=workflow``) whose input convoy (``gc.input_convoy_id``) tracks
  one of them, or tracks the bead the dispatch door wrote to launch it (a
  code review, a Ticket Evaluation, a correction round, a resume: its
  description names the ``convoy:`` and the ``ticket:``) -- and the facts
  the flow wrote on each ticket (tests proven red, frozen, green; a
  question to Benjamin and his answer; the merge).
- **A delivery of the old flow**: a ticket an agent was launched on
  (``gc.flow.models``) whose convoy carries no mark: one run, read as
  :mod:`cockpit.runs.derive` reads it.
- **Any other workflow** (maintenance, planning, …): its root and its steps,
  named after the bead it was run on when the tracker holds it.

Each run says what triggered it -- the publication of the graph of its
Spec, or the bead its workflow was run on, and who wrote it -- and its
project (``gc.project_id`` of the convoy, else the rig the work was
dispatched to); what the tracker does not hold is said « non enregistré ».

A job is a step of a workflow (under ``gc.root_bead_id``: a plain step,
which bears no ``gc.kind``, or one of kind ralph, retry, task or check): a
step routed to the operator (``gc.routed_to`` benjamin) is Benjamin's, a
check is the code's, any other is the agent's whose session claimed it (a
plain step carries ``gc.session_name`` and ``gc.claimed_at`` itself; the
attempts of a ralph or retry step, ``gc.logical_bead_id``, carry them). Its start is its first claim
(else its creation), its end its closing; an open job lasts up to now.

The events of a job are what was recorded of it: its start and its end
(« autre »), each session that claimed it (« session »), a check run and
its outcome (``gc.outcome`` of a check step, or of each attempt of a step
whose closing runs a check, ``gc.check_mode``: « contrôle »). Tool calls are not collected
yet (C2b): no event is drawn « outil ».

Lanes: « Humain », « Code », then one per logical agent -- the agent of the
session (``agent_name`` as the supervisor lists it, else as the bead of a
session it no longer lists says it), so a new session of the same agent
keeps its lane and two agents of the same role keep one each. A job of an
agent no session is recorded for is drawn on the lane of the agent of its
workflow when one agent alone worked it; its detail says that no session
is recorded. Each lane of an agent carries the last session of that agent
in the run (C2a).

Each job says what it recorded -- passed, refused, stopped, waiting, open,
or ended without an outcome -- and the ticket it serves; only a success is
a success.

The sessions of a job (C2a, af-k2rbw1) are those the tracker records of it
(its claims) and those the trace of the sessions saw working it or one of
its attempts (cockpit.runs.trace: the bead a session works while it runs,
each bead the supervisor's log says a session took -- the tracker keeps one
session per bead), in the order they began: each from its
claim, or its creation when it was created later (a session that took
over an attempt), to when the supervisor stopped it -- a start neither
recorded (a session the trace alone saw, with no creation) is none, never
the beginning of the job, and an end it did not record is none, never the
beginning of the next session or the end of the job. What the trace observed of each -- its configuration, what it was
sent -- is carried as it is; a session the trace has nothing of has
nothing observed. The configuration declared for the role of a job is the
one the flow wrote on the ticket when its session took it
(``gc.flow.models``). What is not collected yet (controls, usage, outputs:
C2b) is said so, never filled in.
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.projects.decisions import decisions_line
from cockpit.runs.derive import (AGENT, CODE, DONE, HUMAN, LIVE, PASSED, REFUSED, STOPPED, WAIT, WAITING, _decoded, _ts,
                                 run_from_bead, tone)
from cockpit.runs.trace import _epoch

READ_TIMEOUT_SECONDS = 20
# What the reads ask the tracker for: the beads bearing each key, whatever
# their status (the only read shape the cockpit uses with bd).
KEYS = ("gc.kind", "gc.root_bead_id", "gc.flow.mark", "gc.synthetic", "gc.flow.models", "gc.dispatched_via")
# The steps of a workflow that are jobs -- a plain step bears no kind; the
# others (specs, scopes, their checks, the finalizers, the cleanups) are the
# plumbing of the engine.
JOB_KINDS = (None, "ralph", "retry", "task", "check")
OPERATOR = "benjamin"
# The agent of a session neither the supervisor nor the tracker names any
# more (its session bead removed).
UNRECORDED_AGENT = "Agent non enregistré"
# The agent of a session the supervisor no longer lists, when the tracker
# could not be asked for the beads of the ended sessions: not known, which
# is not an agent seen absent.
UNKNOWN_AGENT = "Agent inconnu · sessions terminées illisibles"
# What the read of the runs holds, beside the beads, when that read failed.
SESSIONS_UNREAD = "cockpit:ended-sessions-unread"
NEW_FLOW = "new-flow/"
DONE_STEP = "Exécution terminée · historique disponible"
UNRECORDED = "non enregistré"
# The lines of a bead the dispatch door wrote that name the work it
# launched (bin/dispatch-door, « convoy: … », « ticket: … »).
CONVOY_LINE, TICKET_LINE = re.compile(r"^convoy: (\S+)$", re.M), re.compile(r"^ticket: (\S+)$", re.M)
# What a check step recorded of its end (gc.outcome).
OUTCOMES = {"pass": "passé", "fail": "refusé"}

# The type of a workflow, by its formula; any other is a « Workflow ».
TYPES = (("mol-do-work", "Maintenance"), ("mol-planning", "Planification"), ("mol-graph-review", "Planification"),
         ("mol-polecat", "Ancien flux"))
# The role of an agent, by its template (the others are said as written).
ROLES = {"delivery-author": "Auteur", "delivery-reviewer": "Relecteur", "delivery-evaluator": "Évaluateur"}
# The steps of the author's workflow, named as the Runs reference names
# them; the steps of other formulas keep their title.
STEP_NAMES = {"workspace": "Prendre le ticket", "red": "Préparer les tests", "code": "Réaliser",
              "demonstration": "Démontrer", "exit": "Rendre le ticket"}

# A session as the tracker keeps it: a bead of that type, named after its
# logical agent (``agent_name``: delivery-author-2, the slot of a pool) --
# the agent a new session of the same slot works for again.
SESSION, SESSION_AGENT = "session", "agent_name"
# The model a session was started with: the ``--model`` of its command, as
# the supervisor lists it and as its bead keeps it.
MODEL_FLAG = re.compile(r"(?:^|\s)--model[ =](\S+)")
# What a check or a step recorded of its end (gc.outcome), as a state.
OUTCOME_STATES = {"pass": PASSED, "fail": REFUSED}

# The role of the agent of a job, by the formula of its workflow: the key
# under which the flow records the configuration declared for it
# (gc.flow.models).
FORMULA_ROLES = (("mol-ticket-author", "author"), ("mol-code-review", "reviewer"),
                 ("mol-ticket-evaluation", "evaluator"))

# The kinds of event, as the legend of the frise colours them.
TOOLS, CONTROLS, SESSIONS, OTHERS = "tools", "controls", "sessions", "others"


def read_workflow_beads(bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
    """Every bead a run is read from: one read per key of :data:`KEYS`,
    merged by id. The reads run side by side: « revérifier maintenant »
    waits for every source, and six reads one after the other made it wait
    six times as long as the other sources."""
    def read(key):
        completed = subprocess.run(
            [bd_bin, "list", "--all", "--limit", "0", "--has-metadata-key", key, "--json"],
            capture_output=True, text=True, timeout=timeout, check=True,
        )
        return json.loads(completed.stdout) or []

    def ended_sessions():
        # The sessions the supervisor no longer lists: their beads, which
        # the tracker keeps apart (ephemeral). A read that fails is said
        # (:data:`SESSIONS_UNREAD`): their agents are unknown, never seen
        # absent.
        try:
            completed = subprocess.run(
                [bd_bin, "list", "--all", "--limit", "0", "--include-ephemeral", "--has-metadata-key", SESSION_AGENT,
                 "--json"], capture_output=True, text=True, timeout=timeout, check=True,
            )
            return [b for b in json.loads(completed.stdout) or []
                    if isinstance(b, dict) and b.get("issue_type") == SESSION]
        except (OSError, subprocess.SubprocessError, ValueError):
            return [{"id": SESSIONS_UNREAD, "issue_type": SESSIONS_UNREAD}]

    seen = {}
    with ThreadPoolExecutor(max_workers=len(KEYS) + 1) as pool:
        sessions = pool.submit(ended_sessions)
        for beads in [*pool.map(read, KEYS), sessions.result()]:
            for bead in beads:
                if isinstance(bead, dict) and bead.get("id"):
                    seen[bead["id"]] = bead
    return list(seen.values())


def paris_time(epoch, now=None, seconds=False):
    """« 15:00 » -- with the day, « 12/10 15:00 », when it is not today."""
    moment = datetime.fromtimestamp(epoch, tz=PARIS)
    clock = moment.strftime("%H:%M:%S" if seconds else "%H:%M")
    if now is not None and datetime.fromtimestamp(now, tz=PARIS).date() != moment.date():
        return moment.strftime("%d/%m ") + clock
    return clock


def find_job(runs, run_id, job_id):
    """(the run of id ``run_id``, its job ``job_id``); None for what is not
    found."""
    run = next((r for r in runs or [] if r["id"] == run_id), None)
    job = next((j for j in (run or {}).get("items", []) if j["id"] == job_id), None)
    return run, job


# --- the runs ------------------------------------------------------------------------

def workflow_runs(beads, agents, now, trace=None):
    """Every run the beads hold, the most recently started first.
    ``agents``: the sessions the supervisor lists (``session_name`` or
    ``name``, ``agent_name``, ``template``, ``provider``), or None;
    ``trace``: what the trace of the sessions holds
    (:meth:`cockpit.runs.trace.SessionTrace.read`), or None."""
    beads = [b for b in beads or [] if isinstance(b, dict) and b.get("id")]
    # A job whose agent the read could not find: unknown when the beads of
    # the ended sessions were not read, else no longer recorded.
    absent = UNKNOWN_AGENT if any(b["id"] == SESSIONS_UNREAD for b in beads) else UNRECORDED_AGENT
    beads = [b for b in beads if b["id"] != SESSIONS_UNREAD]
    meta = {b["id"]: _decoded(b.get("metadata")) for b in beads}
    by_id = {b["id"]: b for b in beads}
    trace = trace or {}
    sessions = _sessions(agents, beads)
    for name, observed in trace.items():
        sessions.setdefault(name, {key: observed.get(key) for key in ("session_name", "agent_name", "template",
                                                                       "provider")})

    steps, attempts = {}, {}
    for bead in beads:
        m = meta[bead["id"]]
        if m.get("gc.logical_bead_id"):
            attempts.setdefault(m["gc.logical_bead_id"], []).append(bead)
        elif m.get("gc.root_bead_id") and m.get("gc.kind") in JOB_KINDS:
            steps.setdefault(m["gc.root_bead_id"], []).append(bead)

    convoys = {meta[b["id"]].get("gc.graph_digest"): b for b in beads
               if b.get("issue_type") == "convoy" and str(meta[b["id"]].get("gc.flow.mark", "")).startswith(NEW_FLOW)}
    groups, of_ticket = {}, {}
    for convoy in convoys.values():
        groups[convoy["id"]] = {"kind": "d01", "root": convoy, "tickets": [], "roots": []}
    for bead in beads:
        m = meta[bead["id"]]
        if bead.get("issue_type") == "convoy" or not (m.get("gc.flow.mark") or m.get("gc.flow.models")):
            continue
        convoy = convoys.get(m.get("gc.graph_digest")) if m.get("gc.flow.mark") else None
        key = convoy["id"] if convoy else bead["id"]
        groups.setdefault(key, {"kind": "ticket", "root": bead, "tickets": [], "roots": []})["tickets"].append(bead)
        of_ticket[bead["id"]] = key
    d01 = {convoy["id"] for convoy in convoys.values()}
    for bead in beads:
        m = meta[bead["id"]]
        if m.get("gc.kind") != "workflow":
            continue
        tracked = _tracked(by_id.get(m.get("gc.input_convoy_id")))
        key = of_ticket.get(tracked) or _launched_for(by_id.get(tracked), of_ticket, d01) or bead["id"]
        group = groups.setdefault(key, {"kind": "workflow", "root": bead, "tickets": [], "roots": []})
        group["roots"].append(bead)
        served = tracked if tracked in of_ticket else _ticket_named(by_id.get(tracked), of_ticket)
        if served:
            group.setdefault("served", {})[bead["id"]] = served
        if group["root"] is bead:
            group["tracked"] = by_id.get(tracked) or ({"id": tracked} if tracked else None)

    runs = []
    for key, group in groups.items():
        run = _run(key, group, meta, steps, attempts, sessions, now, trace, absent)
        if run:
            runs.append(run)
    return sorted(runs, key=lambda run: (run["start"], run["id"]), reverse=True)


def waiting_on(runs, decisions):
    """``runs`` with the open decisions of the chantier each one delivers
    (``decisions``: :func:`cockpit.projects.decisions.chantier_decisions`,
    by chantier id -- the convoy of a D01 run is its id): a run still open
    whose chantier has some waits for Benjamin and says how many
    (``decisions``), as the page of its project does. The runs are copied,
    never changed."""
    out = []
    for run in runs or []:
        count = (decisions or {}).get(run["id"], 0)
        if count and run["state"] != DONE:
            run = dict(run, state=WAIT, status="Ta décision", step=decisions_line(count),
                       tone=tone(WAIT, "Ta décision"), decisions=count)
        out.append(run)
    return out


def _sessions(agents, beads):
    """Each session by its id and its name: those the supervisor lists, then
    the beads of those it no longer lists -- ``agent_name``, ``template``,
    ``provider``, ``command`` alike."""
    found = {}
    for bead in beads:
        if bead.get("issue_type") != SESSION:
            continue
        m = _decoded(bead.get("metadata"))
        if not m.get(SESSION_AGENT):
            continue
        said = {"agent_name": m[SESSION_AGENT], "template": m.get("template"), "provider": m.get("provider"),
                "command": m.get("command")}
        for name in (bead["id"], m.get("session_name")):
            if name:
                found[name] = said
    for agent in agents or []:
        if isinstance(agent, dict):
            for name in (agent.get("id"), agent.get("session_name"), agent.get("name")):
                if name:
                    found[name] = agent
    return found


def _ticket_named(bead, of_ticket):
    """The ticket a bead the dispatch door wrote launched work for, when the
    run holds it; None."""
    found = TICKET_LINE.search((bead or {}).get("description") or "")
    return found.group(1) if found and found.group(1) in of_ticket else None


def _ticket_label(bead, meta):
    """How a job names the ticket it serves: its label in the graph
    (``gc.ticket_id``), else its title."""
    title = bead.get("title") or bead["id"]
    label = meta[bead["id"]].get("gc.ticket_id")
    if label:
        return label
    return title.split(" — ", 1)[1] if " — " in title else title


def _launched_for(bead, of_ticket, d01):
    """The run a bead the dispatch door wrote launched work for: the run of
    the ticket it names, else the D01 convoy it names; None."""
    said = (bead or {}).get("description") or ""
    ticket, convoy = TICKET_LINE.search(said), CONVOY_LINE.search(said)
    if ticket and ticket.group(1) in of_ticket:
        return of_ticket[ticket.group(1)]
    return convoy.group(1) if convoy and convoy.group(1) in d01 else None


def _origin(group, meta):
    """(what triggered the run, its project), as the tracker holds them."""
    root = group["root"]
    m = meta[root["id"]]
    if group["kind"] == "d01":
        who = root.get("created_by")
        spec = m.get("gc.spec_id")
        trigger = "Graphe publié" + (" · Spec %s" % spec if spec else "") + (" par %s" % who if who else "")
        return trigger, m.get("gc.project_id") or m.get("gc.dispatch_rig") or UNRECORDED
    if group["kind"] == "ticket":
        return "Lancement de %s" % (m.get("gc.ticket_id") or root["id"]), m.get("gc.dispatch_rig") or UNRECORDED
    tracked = group.get("tracked")
    if not tracked:
        return "Déclencheur %s" % UNRECORDED, m.get("gc.dispatch_rig") or UNRECORDED
    tm = _decoded(tracked.get("metadata"))
    who = tracked.get("created_by")
    trigger = "%s (%s)" % (tracked["title"], tracked["id"]) if tracked.get("title") else "Travail %s" % tracked["id"]
    return (trigger + (" par %s" % who if who else ""),
            tm.get("gc.project_id") or tm.get("gc.dispatch_rig") or m.get("gc.dispatch_rig") or UNRECORDED)


def _tracked(convoy):
    """The bead an input convoy tracks, or None."""
    for dependency in (convoy or {}).get("dependencies") or []:
        if isinstance(dependency, dict) and dependency.get("type") == "tracks":
            return dependency.get("depends_on_id")
    return None


def _type(group, meta):
    if group["kind"] == "d01":
        return "Livraison D01"
    if group["kind"] == "ticket":
        return "Livraison · %s" % (meta[group["root"]["id"]].get("gc.ticket_id") or group["root"]["id"])
    formula = meta[group["root"]["id"]].get("gc.formula_name") or ""
    return next((label for prefix, label in TYPES if formula.startswith(prefix)), "Workflow")


def _run(key, group, meta, steps, attempts, sessions, now, trace, absent=UNRECORDED_AGENT):
    root = group["root"]
    tickets = {t["id"]: run_from_bead(t, now) for t in group["tickets"]}
    if not group["roots"] and group["kind"] == "ticket":
        derived = tickets.get(root["id"])
        return normalized(derived, now) if derived else None

    labels = {t["id"]: _ticket_label(t, meta) for t in group["tickets"]}
    jobs = []
    for workflow in group["roots"]:
        formula = meta[workflow["id"]].get("gc.formula_name") or ""
        served = labels.get((group.get("served") or {}).get(workflow["id"]))
        for step in steps.get(workflow["id"], []):
            job = _job(step, meta, attempts.get(step["id"], []), sessions, formula, workflow, now, absent)
            if job:
                jobs.append(dict(job, ticket=served))
    _place_sessions(jobs, sessions, trace, now)
    # The facts the flow wrote on each ticket it launched: points on the
    # lanes Code and Humain.
    for ticket_id, derived in tickets.items():
        if derived:
            jobs += _ticket_facts(derived, labels.get(ticket_id))
    start = _ts(root.get("created_at")) or min([j["start"] for j in jobs] or [None]) or None
    if not start:
        return None
    closed = _ts(root.get("closed_at")) if root.get("status") == "closed" else None
    _unrecorded_lanes(jobs, closed or now)
    for job in jobs:
        job["start"] = max(job["start"], start)
    outcomes = [_outcome(meta[t["id"]]) for t in group["tickets"]]
    state, status, step = _state(jobs, tickets, outcomes, closed)
    end = closed or now
    trigger, project = _origin(group, meta)
    title = (group.get("tracked") or {}).get("title") if group["kind"] == "workflow" else None
    declared = {}
    for ticket in group["tickets"]:
        models = meta[ticket["id"]].get("gc.flow.models")
        if isinstance(models, str):
            try:
                models = json.loads(models)
            except ValueError:
                models = None
        if isinstance(models, dict):
            declared.update({role: value for role, value in models.items() if isinstance(value, dict)})
    return _last_sessions(_assemble({
        "id": key, "ticket": meta[root["id"]].get("gc.ticket_id") or key, "spec": meta[root["id"]].get("gc.spec_id"),
        "type": _type(group, meta), "title": title or root.get("title") or key, "step": step, "status": status,
        "trigger": trigger, "project": project,
        "tone": tone(state, status), "state": state, "start": start, "end": max(end, start + 1),
        "branch": meta[root["id"]].get("gc.flow.branch"), "rig": meta[root["id"]].get("gc.dispatch_rig"),
        "models": {}, "workflow": True, "declared": declared,
    }, jobs, now))


def _job(step, meta, attempts, sessions, formula, workflow, now, absent=UNRECORDED_AGENT):
    m = meta[step["id"]]
    claims = sorted((_ts(meta[a["id"]].get("gc.claimed_at")) or _ts(a.get("created_at")) or 0, a) for a in attempts)
    begin = (claims[0][0] if claims else None) or _ts(m.get("gc.claimed_at")) or _ts(step.get("created_at"))
    if not begin:
        return None
    end = _ts(step.get("closed_at")) if step.get("status") == "closed" else None
    routed = m.get("gc.routed_to") or ""
    if routed == OPERATOR:
        lane = {"key": HUMAN, "kind": HUMAN}
    elif m.get("gc.kind") == "check":
        lane = {"key": CODE, "kind": CODE}
    else:
        claim = meta[claims[-1][1]["id"]] if claims and meta[claims[-1][1]["id"]].get("gc.session_name") else (
            m if m.get("gc.session_name") else meta[workflow["id"]])
        session = sessions.get(claim.get("gc.session_id") or "") or sessions.get(claim.get("gc.session_name") or "") or {}
        template = session.get("template") or claim.get("gc.routed_to") or meta[workflow["id"]].get("gc.routed_to")
        role = ROLES.get(template, template) if template else "rôle inconnu"
        model = MODEL_FLAG.search(session.get("command") or "")
        # The model the session ran with, else its provider when only that
        # is known.
        known = model.group(1) if model else session.get("provider")
        lane = {"kind": AGENT, "role": "%s · %s" % (role, known) if known else role}
        if session.get("agent_name"):
            lane.update(key="agent:%s" % session["agent_name"], who=session["agent_name"])
        else:
            # Neither the supervisor nor the tracker says its agent (`absent`
            # says why): :func:`_unrecorded_lanes` gives it a lane.
            lane.update(key=None, who=absent,
                        session=claim.get("gc.session_id") or claim.get("gc.session_name") or step["id"])
    name = (STEP_NAMES.get(m.get("gc.step_id")) if formula == "mol-ticket-author" else None) or step.get("title") or "?"
    sessions = [(at, meta[attempt["id"]].get("gc.session_name"), meta[attempt["id"]].get("gc.attempt"))
                for at, attempt in claims if at and meta[attempt["id"]].get("gc.session_name")]
    if not claims and m.get("gc.session_name") and begin:
        sessions = [(begin, m["gc.session_name"], None)]
    # A step whose closing runs a check: the outcome of each attempt closed.
    checked = [(_ts(attempt.get("closed_at")), meta[attempt["id"]].get("gc.attempt"), meta[attempt["id"]].get("gc.outcome"))
               for _, attempt in claims if m.get("gc.check_mode") and attempt.get("status") == "closed"
               and _ts(attempt.get("closed_at"))]
    # What the step ended in: its own outcome, else that of its last attempt.
    outcome = m.get("gc.outcome") or (meta[claims[-1][1]["id"]].get("gc.outcome") if claims else None)
    if lane["kind"] == AGENT and not sessions:
        lane["unattributed"] = True
    role = next((key for prefix, key in FORMULA_ROLES if formula.startswith(prefix)), None)
    return {"id": step["id"], "name": name, "lane": lane, "start": begin, "end": end,
            "workflow": workflow["id"], "role": role, "beads": [step["id"], *(a["id"] for _, a in claims)],
            "description": step.get("description") or step.get("close_reason") or "",
            "source": "étape %s du workflow %s" % (step["id"], workflow["id"]),
            "sessions": sessions, "checked": checked, "check": m.get("gc.kind") == "check",
            "outcome": outcome, "state": OUTCOME_STATES.get(outcome)}


def _unrecorded_lanes(jobs, horizon):
    """Give a lane to each job whose agent is not said: the sessions of one
    role share a lane « Agent non enregistré » (or « Agent inconnu … ») one
    after the
    other -- a new session is not an agent of its own --, and a session at
    work while every such lane is busy opens the next, since two sessions at
    once are two agents."""
    spans = {}
    for job in jobs:
        lane = job["lane"]
        if lane.get("kind") == AGENT and lane.get("key") is None:
            begin, end = spans.get(lane["session"], (job["start"], job["start"]))
            spans[lane["session"]] = (min(begin, job["start"]), max(end, job["end"] if job["end"] is not None else horizon))
    taken, keys = {}, {}
    for session, (begin, end) in sorted(spans.items(), key=lambda kv: (kv[1], kv[0])):
        role, absent = next((j["lane"]["role"], j["lane"]["who"]) for j in jobs if j["lane"].get("session") == session)
        ends = taken.setdefault(role, [])
        number = next((n for n, last in enumerate(ends) if last <= begin), len(ends))
        if number == len(ends):
            ends.append(end)
        ends[number] = end
        keys[session] = (role, number, absent)
    for job in jobs:
        lane = job["lane"]
        if lane.get("kind") == AGENT and lane.get("key") is None:
            role, number, absent = keys[lane["session"]]
            who = absent if number == 0 else "%s (%d)" % (absent, number + 1)
            job["lane"] = {"key": "unrecorded:%s:%d" % (role, number), "kind": AGENT, "who": who, "role": role}


def _place_sessions(jobs, sessions, trace, now):
    """Give each job of an agent its sessions (``trace_sessions``: each its
    name, its start and end or None, what the trace observed of it or None), and a
    job no session is recorded for the lane of the one agent of its
    workflow, when one agent alone worked it."""
    for job in jobs:
        if job["lane"]["kind"] != AGENT:
            continue
        found = {name: at for at, name, _ in job.get("sessions") or []}
        for name, observed in trace.items():
            if name not in found and set(observed.get("beads") or []) & set(job["beads"]):
                found[name] = None
        # A session begins when it was created, not before: the tracker keeps
        # the first claim of an attempt that a later session took over.
        for name in found:
            created = _epoch((trace.get(name) or {}).get("created_at"))
            if created:
                found[name] = max(found[name] or 0, created)
        if found and job["lane"].get("unattributed"):
            first = sessions.get(min(found, key=lambda name: (found[name] or 0, name))) or {}
            if first.get("agent_name"):
                job["lane"] = dict(job["lane"], key="agent:%s" % first["agent_name"], who=first["agent_name"])
                job["lane"].pop("unattributed")
        ordered = sorted(found.items(), key=lambda pair: (max(pair[1] or 0, job["start"]), pair[0]))
        placed = []
        for name, at in ordered:
            begin = max(at, job["start"]) if at is not None else None
            end = (trace.get(name) or {}).get("ended_at")
            placed.append({"name": name, "start": begin, "end": max(end, begin or end) if end is not None else None,
                           "observed": trace.get(name)})
        job["trace_sessions"] = placed
    for job in jobs:
        if not job["lane"].get("unattributed"):
            continue
        # A lane whose agent is not said yet is keyed by its session.
        others = {other["lane"]["key"] or other["lane"]["session"]: other["lane"] for other in jobs
                  if other is not job and other["workflow"] == job["workflow"] and other["lane"]["kind"] == AGENT
                  and not other["lane"].get("unattributed")}
        if len(others) == 1:
            job["lane"] = dict(next(iter(others.values())))


def _last_sessions(run):
    """Each lane of an agent with the last session of that agent in the
    run (``last_session``: its name and what the trace observed of it, or
    None)."""
    if run is None:
        return run
    for lane in run["lanes"]:
        if lane["kind"] != AGENT:
            continue
        placed = [s for item in lane["items"] for s in item.get("trace_sessions") or []]
        last = max(placed, key=lambda s: (s["start"] if s["start"] is not None else -1, s["name"]), default=None)
        lane["last_session"] = last
    return run


def _ticket_facts(derived, label=None):
    """The facts of a ticket as jobs: each event of the lanes Code and
    Humain a point, with what it observed and the ticket (``label``)."""
    jobs = []
    for number, event in enumerate(derived["events"]):
        lane = {"Code": CODE, "Humain": HUMAN}.get(event["lane"])
        if not lane:
            continue
        kind = CONTROLS if event["text"].startswith(("Tests", "Fidélité")) else OTHERS
        jobs.append({"id": "%s-fait-%d" % (derived["id"], number + 1), "name": event["text"],
                     "lane": {"key": lane, "kind": lane}, "start": event["at"], "end": event["at"], "point": kind,
                     "state": event.get("state"), "ticket": label,
                     "description": event["text"], "source": "fait écrit sur le ticket %s" % derived["id"]})
    return jobs


def _outcome(m):
    """What the flow recorded of the end of a ticket: merged, withdrawn, or
    None."""
    merge = m.get("gc.flow.merge")
    if isinstance(merge, dict) and merge.get("outcome", "merged") == "merged":
        return "merged"
    if isinstance(m.get("gc.flow.gate.withdrawn"), dict):
        return "withdrawn"
    return None


def _state(jobs, tickets, outcomes, closed):
    """(state, status, step) of a run: ``outcomes``, what each of its
    tickets ended in; ``closed``, when its root closed."""
    if closed:
        if "merged" in outcomes:
            return DONE, "Fusionné", DONE_STEP
        if outcomes and all(outcome == "withdrawn" for outcome in outcomes):
            return DONE, "Abandonné", DONE_STEP
        return DONE, "Terminé", DONE_STEP
    open_jobs = sorted((j for j in jobs if j["end"] is None), key=lambda j: j["start"])
    waiting = [j["name"] for j in open_jobs if j["lane"]["kind"] == HUMAN]
    if waiting or any(d and d["state"] == WAIT for d in tickets.values()):
        return WAIT, "Ta décision", " · ".join(waiting) or "Décision attendue"
    if open_jobs:
        return LIVE, "En cours", " · ".join(j["name"] for j in open_jobs)
    if any(d and d["state"] == STOPPED for d in tickets.values()):
        return STOPPED, "Arrêté", "Arrêté"
    return LIVE, "En cours", "En attente d'un agent"


# --- the shape the pages draw -------------------------------------------------------

def _events(job, now):
    """The events of a job: what was recorded of it -- its start and its
    end, each session that claimed it, a check and its outcome; a fact of
    a ticket is one event."""
    if job.get("point"):
        return [{"at": job["start"], "kind": job["point"], "label": "Fait", "text": job["name"]}]
    if job.get("check"):
        events = [{"at": job["start"], "kind": CONTROLS, "label": "Contrôle", "text": "%s : lancé" % job["name"]}]
        if job["end"] is not None:
            said = OUTCOMES.get(job.get("outcome"), "terminé, issue %s" % UNRECORDED)
            events.append({"at": job["end"], "kind": CONTROLS, "label": "Contrôle", "text": "%s : %s" % (job["name"], said)})
        return events
    events = [{"at": job["start"], "kind": OTHERS, "label": "Début", "text": job["name"]}]
    who = job["lane"].get("who")
    for at, session, attempt in job.get("sessions") or []:
        text = "%s · session %s" % (who, session) if who else "Session %s" % session
        events.append({"at": max(at, job["start"]), "kind": SESSIONS, "label": "Session",
                       "text": text + (" · tentative %s" % attempt if attempt else "")})
    for at, attempt, outcome in job.get("checked") or []:
        said = OUTCOMES.get(outcome, "issue %s" % UNRECORDED)
        events.append({"at": max(at, job["start"]), "kind": CONTROLS, "label": "Contrôle",
                       "text": "Contrôle de l’étape%s : %s" % (" · tentative %s" % attempt if attempt else "", said)})
    if job["end"] is not None:
        events.append({"at": job["end"], "kind": OTHERS, "label": "Fin", "text": job["name"]})
    order = {OTHERS: 0, SESSIONS: 1, CONTROLS: 2}
    # The same instant: the start first, then the session, the check, the end.
    return sorted(events, key=lambda event: (event["at"], event["label"] == "Fin", order[event["kind"]]))


# The states a job is drawn in: what it observed (passed, refused, stopped,
# waiting), open while it runs, ended when it closed without saying more.
OPEN, ENDED = "open", "ended"


def _item_state(job, is_open):
    """The state a job is drawn in: a question waiting stays waiting, any
    other open job is open; a closed one says what it recorded, else
    ended -- never a success it did not record."""
    if job.get("state") == WAITING or not is_open:
        return job.get("state") or ENDED
    return OPEN


def _assemble(run, jobs, now):
    """``run`` with its lanes and jobs as the pages draw them: Humain and
    Code, even without a job, then the agents in the order they began."""
    start, end = run["start"], run["end"]
    lanes = {HUMAN: {"key": HUMAN, "kind": HUMAN, "who": "Benjamin", "role": "Humain", "name": "Humain"},
             CODE: {"key": CODE, "kind": CODE, "who": "Code", "role": "Contrôles et transitions", "name": "Code"}}
    order = [HUMAN, CODE]
    items = []
    for job in sorted(jobs, key=lambda j: (j["start"], j["id"])):
        lane = job["lane"]
        if lane["key"] not in lanes:
            lanes[lane["key"]] = {**lane, "name": lane["who"]}
            order.append(lane["key"])
        stop = job["end"] if job["end"] is not None else (end if run["state"] == DONE else now)
        is_open = job["end"] is None and run["state"] != DONE
        items.append({**job, "lane": lane["key"], "open": is_open, "state": _item_state(job, is_open),
                      "offset": max(0, job["start"] - start), "lasted": max(0, stop - job["start"]),
                      "events": _events(job, now)})
    drawn = []
    for key in order:
        lane = dict(lanes[key])
        mine = [item for item in items if item["lane"] == key]
        lane["title"] = "%s · %s" % (lane["who"], lane["role"])
        lane["items"] = mine
        lane["jobs"] = [(int(i["offset"]), int(min(i["offset"] + i["lasted"], end - start))) for i in mine]
        drawn.append(lane)
    run.update({"lanes": drawn, "items": items, "elapsed": int(end - start), "href": "/runs/run?id=%s" % run["id"],
                "started_at": start, "events": [dict(e, lane=i["lane"]) for i in items for e in i["events"]]})
    return run


def normalized(run, now):
    """A run of :mod:`cockpit.runs.derive` (a delivery of the old flow) in
    the shape the pages draw: each span of a lane a job, each event of a
    lane on the job it falls in. A run already in that shape is returned
    as it is."""
    if run is None or run.get("items") is not None:
        return run
    start = run["start"]
    jobs = []
    for number, lane in enumerate(run["lanes"]):
        key = {HUMAN: HUMAN, CODE: CODE}.get(lane["kind"], "agent:%s" % lane["name"])
        who, role = (("Benjamin", "Humain") if lane["kind"] == HUMAN else ("Code", "Contrôles et transitions")
                     if lane["kind"] == CODE else (lane["name"], lane["title"].split(" · ", 1)[-1]))
        mine = [e for e in run["events"] if e["lane"] == lane["name"]]
        for index, (s, e) in enumerate(lane["jobs"]):
            near = [ev for ev in mine if s <= ev["at"] - start <= e] or (mine if index == len(lane["jobs"]) - 1 else [])
            jobs.append({"id": "%s-%d-%d" % (run["id"], number + 1, index + 1),
                         "name": near[0]["text"] if s == e and near else lane["title"],
                         "lane": {"key": key, "kind": lane["kind"], "who": who, "role": role},
                         # A fact is an instant, never open: only a span reaching now is.
                         "start": start + s,
                         "end": start + e if (s == e or e < run["elapsed"] or run["state"] == DONE) else None,
                         "state": near[0].get("state") if s == e and near else None, "ticket": run.get("ticket"),
                         "description": " · ".join(ev["text"] for ev in near), "source": "ticket %s" % run["id"],
                         "facts": near})
    out = dict(run, models=run.get("models") or {})
    out.setdefault("trigger", "Lancement de %s" % (run.get("ticket") or run["id"]))
    out.setdefault("project", run.get("rig") or UNRECORDED)
    out = _assemble(out, jobs, now if run["state"] != DONE else run["end"])
    for item in out["items"]:
        recorded = [{"at": ev["at"], "kind": _kind(ev["text"]), "label": "Fait", "text": ev["text"]}
                    for ev in item.get("facts") or []]
        item["events"] = recorded or item["events"]
    out["events"] = run["events"]
    return out


def _kind(text):
    if " lancé" in text:
        return SESSIONS
    if text.startswith(("Tests", "Fidélité", "Revue de code", "Évaluation")):
        return CONTROLS
    return OTHERS
