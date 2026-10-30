"""The runs of the factory, drawn from the tickets the delivery flow marks.

A run is one delivery of a ticket: from its dispatch to its fusion, its
stop or now. Everything it shows is already on the ticket bead, written by
the delivery flow (docs/CONVOY_STATE.md): when each agent was launched and
by which model, the TDD steps, the rounds of code review and evaluation,
the fidelity, the stop, the question to Benjamin and his answer. Nothing is
collected for the cockpit alone.

Lanes: « Humain » (a question waiting for Benjamin, then his answer),
« Code » (the mechanical steps: tests red, frozen, green, fidelity), then
one lane per agent of the run (author, reviewer, evaluator).

Intent (Benjamin, his words, 2026-10-19 19:20 Paris): « fusionne la Vue
d'ensemble sur main et enchaîne directement sur Runs puis Usine. »
Mechanism (agent interpretation): the Runs page is built directly from the
ticket beads, outside the paused convoy af-pqfxmd.
"""
import json
import subprocess
from datetime import datetime, timezone

from cockpit.core.readmodel import PARIS

MODELS = "gc.flow.models"
# How many runs the cockpit keeps: the most recently updated.
RUNS_LIMIT = 200
READ_TIMEOUT_SECONDS = 20

HUMAN, CODE, AGENT = "human", "code", "agent"
ROLES = (("author", "Auteur"), ("reviewer", "Relecteur"), ("evaluator", "Évaluateur"))
LIVE, WAIT, DONE, STOPPED = "live", "wait", "done", "stopped"
# What a fact of a run observed, when it says it: a success, a refusal, a
# stop (STOPPED), a question still waiting for Benjamin. A fact without one
# (a launch, an answer, a resume) is only what happened.
PASSED, REFUSED, WAITING = "passed", "refused", "waiting"
FACT_STATES = (PASSED, REFUSED, STOPPED, WAITING)
VERDICT_STATES = {"favorable": PASSED, "unfavorable": REFUSED}


def read_runs(bd_bin="bd", timeout=READ_TIMEOUT_SECONDS, limit=RUNS_LIMIT):
    """The ticket beads a delivery agent was launched on, the ``limit`` most
    recently updated, with their metadata (the same read shape as the other
    sources: every bead bearing the key)."""
    completed = subprocess.run(
        [bd_bin, "list", "--all", "--limit", "0", "--has-metadata-key", MODELS, "--json"],
        capture_output=True, text=True, timeout=timeout, check=True,
    )
    beads = [b for b in json.loads(completed.stdout) if isinstance(b, dict)]
    return sorted(beads, key=lambda b: b.get("updated_at") or "", reverse=True)[:limit]


def runs_from_beads(beads, now):
    """Every run the beads hold, the most recently started first."""
    runs = [run for run in (run_from_bead(bead, now) for bead in beads or [] if isinstance(bead, dict)) if run]
    return sorted(runs, key=lambda run: run["start"], reverse=True)


def _decoded(metadata):
    out = {}
    for key, value in (metadata or {}).items():
        if isinstance(value, str) and value[:1] in "{[":
            try:
                value = json.loads(value)
            except ValueError:
                pass
        out[key] = value
    return out


def _ts(value):
    """An ISO instant of the tracker as epoch seconds, or None."""
    if not isinstance(value, str) or not value or value == "none":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _at(record):
    return _ts(record.get("at")) if isinstance(record, dict) else None


def _rounds(record):
    rounds = record.get("rounds") if isinstance(record, dict) else None
    return [r for r in rounds or [] if isinstance(r, dict)]


def paris(epoch, with_day=False):
    moment = datetime.fromtimestamp(epoch, tz=PARIS)
    return moment.strftime("%d/%m %H:%M" if with_day else "%H:%M")


def run_from_bead(bead, now):
    """One run: ``id``, ``ticket``, ``type``, ``title``, ``step``, ``status``,
    ``tone`` (:func:`tone`), ``state`` (live / wait / done / stopped), ``start``, ``end``,
    ``elapsed``, ``started``, ``lanes`` (``name``, ``kind``, ``jobs``: spans
    in seconds from the start, ``labels``), ``events`` (``at``, ``lane``,
    ``text``), ``models``, ``branch``; None for a bead no agent ran on."""
    m = _decoded(bead.get("metadata"))
    models = m.get(MODELS) if isinstance(m.get(MODELS), dict) else {}
    dispatch = _at(m.get("gc.flow.gate.dispatch"))
    launches = [_at(models.get(role)) for role, _ in ROLES]
    start = dispatch or min([t for t in launches if t] or [0]) or None
    if not start:
        return None
    events = []

    def event(at, lane, text, state=None):
        """A fact of the run; ``state``, what it observed when it says one
        (:data:`FACT_STATES`)."""
        if at:
            events.append({"at": at, "lane": lane, "text": text, **({"state": state} if state else {})})

    closed = _ts(bead.get("closed_at")) if bead.get("status") == "closed" else None
    stop = m.get("gc.flow.stop") if isinstance(m.get("gc.flow.stop"), dict) else None
    exit_ = m.get("gc.flow.exit") if isinstance(m.get("gc.flow.exit"), dict) else None
    asked = _ts(m.get("gc.escalation_horodatage"))
    answered = _ts(m.get("gc.escalation_response_at"))
    waiting = bool(asked and (not answered or answered < asked) and not closed)

    # The end of the run: its closing, else now while anything is open.
    marks = [start]
    event(dispatch, "Code", "Ticket lancé")
    for key, text in (("gc.flow.tdd.red", "Tests rouges prouvés"), ("gc.flow.tdd.freeze", "Tests gelés"),
                      ("gc.flow.tdd.green", "Tests verts")):
        event(_at(m.get(key)), "Code", text, PASSED)
    amendment = m.get("gc.flow.tdd.amendment")
    if isinstance(amendment, dict):
        event(_at(amendment), "Code", "Tests amendés : %s" % amendment.get("reason", ""))
    fidelity = m.get("gc.flow.verdict.fidelity")
    if isinstance(fidelity, dict):
        event(_at(fidelity), "Code", "Fidélité au prototype : %s" % _verdict(fidelity.get("state")),
              VERDICT_STATES.get(fidelity.get("state")))
    agent_lanes = []
    for role, label in ROLES:
        record = models.get(role)
        if not isinstance(record, dict) or not _at(record):
            continue
        begin = _at(record)
        name = "%s · %s" % (label, record.get("model") or record.get("agent") or "?")
        event(begin, label, "%s lancé (%s)" % (label, record.get("model") or record.get("agent") or "modèle inconnu"))
        ends = []
        if role == "author":
            if exit_:
                ends.append(_at(exit_))
                event(_at(exit_), label, "Auteur sorti : %s" % exit_.get("exit", "?"))
            correction = m.get("gc.flow.correction")
            if isinstance(correction, dict):
                event(_at(correction), label, "Tour de correction : %s" % ", ".join(correction.get("blocking_findings") or []))
        elif role == "reviewer":
            for r in _rounds(m.get("gc.flow.code_review")):
                blocking = [f.get("id") for f in r.get("findings") or [] if isinstance(f, dict) and f.get("blocking")]
                ends.append(_at(r))
                event(_at(r), label, "Revue de code : %s" % (
                    "%d bloquant(s) %s" % (len(blocking), ", ".join(filter(None, blocking))) if blocking else "aucun bloquant"))
        else:
            for r in _rounds(m.get("gc.flow.evaluation")):
                ends.append(_at(r))
                event(_at(r), label, "Évaluation : %s" % (r.get("outcome") or r.get("verdict") or "?"))
        ends = [t for t in ends if t]
        live = not ends and not closed and not stop
        end = max(ends) if ends else (now if live else begin)
        agent_lanes.append({"name": label, "title": name, "kind": AGENT, "spans": [(begin, max(end, begin))]})
    if stop:
        event(_at(stop), "Code", "Arrêt : %s" % (stop.get("detail") or stop.get("reason") or "?"), STOPPED)
    for entry in (m.get("gc.flow.resume") or {}).get("entries", []) if isinstance(m.get("gc.flow.resume"), dict) else []:
        if isinstance(entry, dict):
            event(_at(entry), "Code", "Reprise : %s" % entry.get("cause", "?"))
    if asked:
        event(asked, "Humain", "Question à Benjamin : %s" % (m.get("gc.escalation_pourquoi") or "décision attendue"),
              WAITING if waiting else None)
    if answered and asked and answered >= asked:
        event(answered, "Humain", "Réponse de Benjamin : option %s" % (m.get("gc.escalation_response_option") or "?"))
    for entry in (m.get("gc.flow.overrides") or {}).get("entries", []) if isinstance(m.get("gc.flow.overrides"), dict) else []:
        if isinstance(entry, dict):
            event(_at(entry), "Humain", "Dérogation accordée : %s" % entry.get("finding", "?"))
    merge = m.get("gc.flow.merge") if isinstance(m.get("gc.flow.merge"), dict) else None
    if merge and merge.get("outcome", "merged") != "merged":
        merge = None
    withdrawn = m.get("gc.flow.gate.withdrawn") if isinstance(m.get("gc.flow.gate.withdrawn"), dict) else None
    if merge:
        event(_at(merge) or closed, "Code", "Fusionné dans %s" % (merge.get("into") or merge.get("target") or "l’intégration"),
              PASSED)
    if withdrawn:
        event(_at(withdrawn) or closed, "Humain", "Retiré du graphe%s" % (
            " : %s" % withdrawn.get("reason") if withdrawn.get("reason") else ""))
    if closed and not merge and not withdrawn:
        event(closed, "Code", "Fermé : %s" % (bead.get("close_reason") or "sans raison écrite"))

    marks += [e["at"] for e in events] + [end for lane in agent_lanes for _, end in lane["spans"]]
    if closed:
        end = closed
    elif waiting or any(lane["spans"][-1][1] == now for lane in agent_lanes):
        end = now
    else:
        end = max(marks)
    end = max(end, start + 1)

    human_spans = []
    if asked:
        human_spans.append((asked, answered if answered and answered >= asked else end))
    for e in events:
        if e["lane"] == "Humain" and e["at"] != asked:
            human_spans.append((e["at"], e["at"]))
    code_spans = [(e["at"], e["at"]) for e in events if e["lane"] == "Code"]
    lanes = [{"name": "Humain", "title": "Humain", "kind": HUMAN, "spans": human_spans},
             {"name": "Code", "title": "Code", "kind": CODE, "spans": code_spans}] + agent_lanes
    for lane in lanes:
        lane["jobs"] = [(max(0, int(s - start)), max(0, int(min(e, end) - start))) for s, e in lane["spans"]]

    state, status, step = _state(bead, closed, stop, exit_, waiting, agent_lanes, now, merge, withdrawn)
    ticket = m.get("gc.ticket_id") or bead.get("id")
    title = bead.get("title") or ""
    if " — " in title and title.split(" — ", 1)[0].strip() == ticket:
        title = title.split(" — ", 1)[1]
    return {
        "id": bead.get("id"), "ticket": ticket, "spec": m.get("gc.spec_id"),
        "type": "Livraison · %s" % ticket, "title": title, "step": step, "status": status,
        "tone": tone(state, status), "state": state,
        "start": start, "end": end, "elapsed": int(end - start),
        "started": paris(start, with_day=True), "lanes": lanes,
        "events": sorted(events, key=lambda e: e["at"]), "models": models,
        "branch": m.get("gc.flow.branch"), "rig": m.get("gc.dispatch_rig"), "href": "/runs/run?id=%s" % bead.get("id"),
    }


# A run ended that is not a success: abandoned, or closed without a merge.
UNSUCCESSFUL = ("Abandonné", "Fermé")


def tone(state, status):
    """How the status of a run is drawn: « live » or « wait » while it is
    open, « ended » when it ended without success, else None (a success,
    or stopped)."""
    if state == DONE:
        return "ended" if status in UNSUCCESSFUL else None
    return {LIVE: "live", WAIT: "wait"}.get(state)


def _verdict(state):
    return {"favorable": "favorable", "unfavorable": "défavorable"}.get(state, state or "?")


def _state(bead, closed, stop, exit_, waiting, agent_lanes, now, merge=None, withdrawn=None):
    """(state, status, step) of a run."""
    if closed or withdrawn:
        if merge:
            return DONE, "Fusionné", "Livré · historique disponible"
        if withdrawn:
            return DONE, "Abandonné", "Retiré ou remplacé · historique disponible"
        return DONE, "Fermé", bead.get("close_reason") or "Fermé sans fusion · historique disponible"
    if waiting:
        return WAIT, "Ta décision", "Décision attendue"
    if stop:
        return STOPPED, "Arrêté", stop.get("detail") or stop.get("reason") or "Arrêté"
    running = [lane["name"] for lane in agent_lanes if lane["spans"][-1][1] == now]
    if running:
        return LIVE, "En cours", "%s au travail" % " · ".join(running)
    if exit_:
        return LIVE, "En cours", "Vérifications après la sortie de l'auteur"
    return LIVE, "En cours", "En attente d'un agent"
