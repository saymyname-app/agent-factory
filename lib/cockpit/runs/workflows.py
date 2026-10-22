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
session (``agent_name`` as the supervisor lists it), so a new session of
the same agent keeps its lane and two agents of the same role keep one
each. What is not collected yet (sessions, configuration, prompts,
controls, usage, outputs: C2a and C2b) is said so, never filled in.
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from cockpit.core.readmodel import PARIS
from cockpit.runs.derive import AGENT, CODE, DONE, HUMAN, LIVE, STOPPED, WAIT, _decoded, _ts, run_from_bead, tone

READ_TIMEOUT_SECONDS = 20
# What the reads ask the tracker for: the beads bearing each key, whatever
# their status (the only read shape the cockpit uses with bd).
KEYS = ("gc.kind", "gc.root_bead_id", "gc.flow.mark", "gc.synthetic", "gc.flow.models", "gc.dispatched_via")
# The steps of a workflow that are jobs -- a plain step bears no kind; the
# others (specs, scopes, their checks, the finalizers, the cleanups) are the
# plumbing of the engine.
JOB_KINDS = (None, "ralph", "retry", "task", "check")
OPERATOR = "benjamin"
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

    seen = {}
    with ThreadPoolExecutor(max_workers=len(KEYS)) as pool:
        for beads in pool.map(read, KEYS):
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

def workflow_runs(beads, agents, now):
    """Every run the beads hold, the most recently started first.
    ``agents``: the sessions the supervisor lists (``session_name`` or
    ``name``, ``agent_name``, ``template``, ``provider``), or None."""
    beads = [b for b in beads or [] if isinstance(b, dict) and b.get("id")]
    meta = {b["id"]: _decoded(b.get("metadata")) for b in beads}
    by_id = {b["id"]: b for b in beads}
    sessions = _sessions(agents)

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
        if group["root"] is bead:
            group["tracked"] = by_id.get(tracked) or ({"id": tracked} if tracked else None)

    runs = []
    for key, group in groups.items():
        run = _run(key, group, meta, steps, attempts, sessions, now)
        if run:
            runs.append(run)
    return sorted(runs, key=lambda run: (run["start"], run["id"]), reverse=True)


def _sessions(agents):
    found = {}
    for agent in agents or []:
        if isinstance(agent, dict):
            for name in (agent.get("session_name"), agent.get("name")):
                if name:
                    found[name] = agent
    return found


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


def _run(key, group, meta, steps, attempts, sessions, now):
    root = group["root"]
    tickets = {t["id"]: run_from_bead(t, now) for t in group["tickets"]}
    if not group["roots"] and group["kind"] == "ticket":
        derived = tickets.get(root["id"])
        return normalized(derived, now) if derived else None

    jobs = []
    for workflow in group["roots"]:
        formula = meta[workflow["id"]].get("gc.formula_name") or ""
        for step in steps.get(workflow["id"], []):
            job = _job(step, meta, attempts.get(step["id"], []), sessions, formula, workflow, now)
            if job:
                jobs.append(job)
    # The facts the flow wrote on each ticket it launched: points on the
    # lanes Code and Humain.
    for derived in tickets.values():
        if derived:
            jobs += _ticket_facts(derived)
    start = _ts(root.get("created_at")) or min([j["start"] for j in jobs] or [None]) or None
    if not start:
        return None
    closed = _ts(root.get("closed_at")) if root.get("status") == "closed" else None
    for job in jobs:
        job["start"] = max(job["start"], start)
    outcomes = [_outcome(meta[t["id"]]) for t in group["tickets"]]
    state, status, step = _state(jobs, tickets, outcomes, closed)
    end = closed or now
    trigger, project = _origin(group, meta)
    title = (group.get("tracked") or {}).get("title") if group["kind"] == "workflow" else None
    return _assemble({
        "id": key, "ticket": meta[root["id"]].get("gc.ticket_id") or key, "spec": meta[root["id"]].get("gc.spec_id"),
        "type": _type(group, meta), "title": title or root.get("title") or key, "step": step, "status": status,
        "trigger": trigger, "project": project,
        "tone": tone(state, status), "state": state, "start": start, "end": max(end, start + 1),
        "branch": meta[root["id"]].get("gc.flow.branch"), "rig": meta[root["id"]].get("gc.dispatch_rig"),
        "models": {}, "workflow": True,
    }, jobs, now)


def _job(step, meta, attempts, sessions, formula, workflow, now):
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
        claim = meta[claims[-1][1]["id"]] if claims else (m if m.get("gc.session_name") else meta[workflow["id"]])
        session = sessions.get(claim.get("gc.session_name") or "") or {}
        template = session.get("template") or claim.get("gc.routed_to") or meta[workflow["id"]].get("gc.routed_to")
        who = session.get("agent_name") or claim.get("gc.session_name") or template or "Agent inconnu"
        role = ROLES.get(template, template) if template else "rôle inconnu"
        provider = session.get("provider")
        lane = {"key": "agent:%s" % who, "kind": AGENT, "who": who,
                "role": "%s · %s" % (role, provider) if provider else role}
    name = (STEP_NAMES.get(m.get("gc.step_id")) if formula == "mol-ticket-author" else None) or step.get("title") or "?"
    sessions = [(at, meta[attempt["id"]].get("gc.session_name"), meta[attempt["id"]].get("gc.attempt"))
                for at, attempt in claims if at and meta[attempt["id"]].get("gc.session_name")]
    if not claims and m.get("gc.session_name") and begin:
        sessions = [(begin, m["gc.session_name"], None)]
    # A step whose closing runs a check: the outcome of each attempt closed.
    checked = [(_ts(attempt.get("closed_at")), meta[attempt["id"]].get("gc.attempt"), meta[attempt["id"]].get("gc.outcome"))
               for _, attempt in claims if m.get("gc.check_mode") and attempt.get("status") == "closed"
               and _ts(attempt.get("closed_at"))]
    return {"id": step["id"], "name": name, "lane": lane, "start": begin, "end": end,
            "description": step.get("description") or step.get("close_reason") or "",
            "source": "étape %s du workflow %s" % (step["id"], workflow["id"]),
            "sessions": sessions, "checked": checked, "check": m.get("gc.kind") == "check",
            "outcome": m.get("gc.outcome")}


def _ticket_facts(derived):
    """The facts of a ticket as jobs: each event of the lanes Code and
    Humain a point."""
    jobs = []
    for number, event in enumerate(derived["events"]):
        lane = {"Code": CODE, "Humain": HUMAN}.get(event["lane"])
        if not lane:
            continue
        kind = CONTROLS if event["text"].startswith(("Tests", "Fidélité")) else OTHERS
        jobs.append({"id": "%s-fait-%d" % (derived["id"], number + 1), "name": event["text"],
                     "lane": {"key": lane, "kind": lane}, "start": event["at"], "end": event["at"], "point": kind,
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
        items.append({**job, "lane": lane["key"], "open": job["end"] is None and run["state"] != DONE,
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
                         "start": start + s, "end": start + e if (e < run["elapsed"] or run["state"] == DONE) else None,
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
