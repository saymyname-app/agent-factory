"""The four indicators of the factory and its daily volumes, computed from
the sources the cockpit reads (D, af-ten1sp; Spec af-fgcw0d, user stories
148, 149 and 150).

    view = analyses(snapshot, requests, now)

One call gives everything the Analyses show, and what the overview reuses
(ticket K): over the seven days that end today (Paris),

- ``indicators``: « Décisions ouvertes », « Résultats fusionnés », « Délai de
  livraison » and « Vérifications CI réussies », each its value, or none and
  the reason it is unavailable, then its method -- population, period,
  sources, when they were read (Paris) and calculation;
- ``volumes``: the daily counts that compare -- results merged, pull
  requests merged, tickets delivered, CI runs that succeeded --, one value
  a day, or none and the reason;
- ``results``, ``portions``, ``decisions`` and ``answered``: what the views
  list.

The sources are those the cockpit reads: the runs (``runs``: a ticket is
delivered on its merge into the integration branch), the journal
(``journal``: the decisions answered), the requests (the decisions open),
GitHub (``github``: a CI run counts on its conclusion), and the results
whose merge the flow proved (``results``: ``gc.flow.promotion``), which
neither a run nor the journal holds. Only a fresh source gives a value
(GLOSSARY.md, Freshness): one not read yet, failing or stale gives none,
never a zero nor its last known value, and says why; a count is never a
percentage.

Intent (Benjamin, his words, 2026-10-12): « Il faut présenter ce qu’on peut,
on a des métriques » ; « Bref faut pas que ca soit redondant ».
Mechanism (agent interpretation): the four indicators of the Spec, each
computed once here for every page that shows it.
"""
import json
from datetime import datetime, timedelta, timezone

from cockpit.core.freshness import FRESH, STALE
from cockpit.core.readmodel import PARIS
from cockpit.requests.journal import entries_from_value
from cockpit.runs.derive import RUNS_LIMIT, runs_from_beads

DAYS = 7
DECISIONS, RESULTS, DELAY, CI = "decisions", "results", "delay", "ci"
LABELS = {DECISIONS: "Décisions ouvertes", RESULTS: "Résultats fusionnés", DELAY: "Délai de livraison",
          CI: "Vérifications CI réussies"}
# The portions of the delay the records of the flow date: from the
# publication of the graph to the delivery of the result, to Benjamin's
# acceptance, to the proof of the merge. Each: label, whether it is a wait.
PORTIONS = (("Réalisation et vérifications", False), ("Attente de jugement", True), ("Fusion", False))
# The daily volumes, in the order they are drawn.
VOLUMES = ("Résultats fusionnés", "PR fusionnées", "Tickets livrés", "Exécutions CI réussies")
NO_REPOSITORY = "aucun dépôt GitHub n’est déclaré pour la CI du cockpit (réglage github_repo)"
# How each source says it gives no value: while its first read has not
# ended, once its read failed, once its value is older than its Validity
# window.
UNREAD = {
    "results": ("les résultats du flux sont en cours de lecture", "les résultats du flux n’ont pas pu être lus",
                "les résultats du flux ne sont plus à jour"),
    "runs": ("les runs sont en cours de lecture", "les runs n’ont pas pu être lus", "les runs ne sont plus à jour"),
    "journal": ("le journal est en cours de lecture", "le journal n’a pas pu être lu", "le journal n’est plus à jour"),
    "beads": ("les demandes sont en cours de lecture", "les demandes n’ont pas pu être lues",
              "les demandes ne sont plus à jour"),
    "github": ("GitHub est en cours de lecture", "GitHub n’a pas répondu", "la CI GitHub n’est plus à jour"),
}
# The ways of the journal that answer a decision (cockpit.ui.journal).
ANSWERING = ("escalation-door", "cockpit")


def analyses(snapshot, requests, now, days=DAYS):
    """What the Analyses show over the ``days`` days that end on the day of
    ``now`` (Paris), from the read model's ``snapshot`` and the ``requests``
    the cockpit lists. See the module."""
    span = _days(now, days)
    period = "%d jours, du %s au %s (Paris)" % (days, span[0].strftime("%d/%m"), span[-1].strftime("%d/%m"))
    within = lambda at: at is not None and span[0] <= _day(at) <= span[-1]
    names = _project_names(snapshot.get("projets"))
    rows = {name: snapshot.get(name) for name in UNREAD}
    reasons = {name: _unread(row, *UNREAD[name]) for name, row in rows.items()}
    if rows["github"] is None:
        reasons["github"] = NO_REPOSITORY
    value = lambda name: None if reasons[name] else rows[name]["value"]

    results_reason = reasons["results"]
    results = sorted((r for r in map(_result, value("results") or []) if r and within(r["merged"])),
                     key=lambda r: -r["merged"])
    for result in results:
        result["project"] = names.get(result["project"], result["project"])

    # A ticket is delivered on its merge into the integration branch, as its
    # run says. The runs are the most recently updated ones: when as many as
    # the cockpit keeps were updated within the period, older merges of the
    # period may be missing, and none is counted.
    runs_reason = reasons["runs"]
    if not runs_reason and _truncated(value("runs"), span[0]):
        runs_reason = "plus de %d runs mis à jour sur la période : le cockpit n’en garde que %d" % (
            RUNS_LIMIT, RUNS_LIMIT)
    tickets = [] if runs_reason else [
        event["at"] for run in runs_from_beads(value("runs"), now) for event in run["events"]
        if event["text"].startswith("Fusionné") and within(event["at"])]

    github_reason = reasons["github"]
    github = value("github") or {}
    runs = [run for run in github.get("workflow_runs") or []
            if isinstance(run, dict) and within(_ts(run.get("created_at")))]
    completed = [run for run in runs if run.get("status") == "completed"]
    succeeded = [run for run in completed if run.get("conclusion") == "success"]
    pulls = [at for at in (_ts(pull.get("merged_at")) for pull in github.get("pull_requests") or []
                           if isinstance(pull, dict)) if within(at)]

    decisions_reason = reasons["beads"]
    journal_reason = reasons["journal"]
    answered = None if journal_reason else sorted(
        ({"title": entry.demande or entry.quoi, "answer": entry.quoi, "at": _ts(entry.quand)}
         for entry in entries_from_value(value("journal"))
         if entry.voie in ANSWERING and within(_ts(entry.quand))), key=lambda item: -item["at"])

    def per_day(moments):
        counts = {day: 0 for day in span}
        for at in moments:
            counts[_day(at)] += 1
        return [counts[day] for day in span]

    portions = []
    for (label, wait), (begin, end) in zip(PORTIONS, (("published", "delivered"), ("delivered", "accepted"),
                                                       ("accepted", "merged"))):
        measured = [r[end] - r[begin] for r in results
                    if r[begin] is not None and r[end] is not None and r[end] >= r[begin]]
        portions.append({"label": label, "wait": wait, "median": _median(measured), "count": len(measured)})
    totals = [r["merged"] - r["published"] for r in results if r["published"] is not None]
    repository = github.get("repository") or ""

    results_sources = "les résultats de chantier du flux de livraison, lus sur le tracker"
    indicators = {
        DECISIONS: _indicator(
            DECISIONS, None if decisions_reason else str(len(requests)), decisions_reason,
            population="les décisions qui t’attendent : propositions, questions et résultats à juger, "
                       "ouvertes maintenant",
            period="%s ; une décision ouverte est comptée tant qu’elle attend, même posée avant" % period,
            sources="les demandes du cockpit, lues sur le tracker ; les décisions répondues, au journal",
            read=_read(rows["beads"]),
            calculation="le nombre de demandes ouvertes, comme sur la Vue d’ensemble ; une demande répondue ne "
                        "compte plus, elle est au journal"),
        RESULTS: _indicator(
            RESULTS, None if results_reason else str(len(results)), results_reason,
            population="les résultats de chantier dont la fusion est prouvée ; les PR et les tickets ne sont "
                       "pas des résultats",
            period=period, sources="la preuve de fusion (gc.flow.promotion) des %s ; les tickets livrés, aux "
                                   "runs" % results_sources,
            read=_read(rows["results"]),
            calculation="le nombre de résultats fusionnés, un par preuve de fusion, compté le jour de la fusion "
                        "(Paris)"),
        DELAY: _indicator(
            DELAY, None if results_reason or not totals else delay_text(_median(totals)),
            results_reason or (None if totals else "aucun résultat fusionné sur la période"),
            population="les %d résultats fusionnés de la période" % len(results),
            period=period, sources="la publication du graphe, la livraison, l’acceptation et la preuve de fusion "
                                   "des %s" % results_sources, read=_read(rows["results"]),
            calculation="la médiane des délais de la publication du graphe à la preuve de fusion ; chaque portion "
                        "est la médiane de ses propres délais, mesurée sur les résultats qui la datent : elles ne "
                        "s’additionnent pas"),
        CI: _indicator(
            CI, None if github_reason or not completed else "%d %%" % round(100 * len(succeeded) / len(completed)),
            github_reason or (None if completed else "aucune exécution CI terminée sur la période"),
            population="les exécutions CI terminées de la période ; une exécution en cours n’est pas comptée",
            period=period, sources="la CI GitHub%s, toutes ses exécutions créées sur la période" % (
                " du dépôt %s" % repository if repository else ""),
            read=_read(rows["github"]),
            calculation="%d réussies sur %d terminées" % (len(succeeded), len(completed)) if not github_reason
            else "les exécutions réussies sur les exécutions terminées"),
    }
    volumes = [
        {"label": VOLUMES[0], "values": None if results_reason else per_day(r["merged"] for r in results),
         "reason": results_reason},
        {"label": VOLUMES[1], "values": None if github_reason else per_day(pulls), "reason": github_reason},
        {"label": VOLUMES[2], "values": None if runs_reason else per_day(tickets), "reason": runs_reason},
        {"label": VOLUMES[3], "values": None if github_reason else per_day(_ts(r.get("created_at")) for r in succeeded),
         "reason": github_reason},
    ]
    return {"days": span, "period": period, "indicators": indicators, "volumes": volumes, "results": results,
            "portions": portions, "decisions": [] if decisions_reason else list(requests),
            "answered": answered, "answered_reason": journal_reason, "now": now}


def _indicator(key, value, reason, **method):
    return {"key": key, "label": LABELS[key], "value": value, "reason": None if value is not None else reason,
            **method}


def _unread(row, reading, failing, stale):
    """Why ``row`` gives no current value -- ``reading`` while its first
    read has not ended, ``failing`` when its read failed and no value of it
    is in its Validity window, ``stale`` when only an older last known
    value is --, or None when it gives one."""
    if row is not None and row["value"] is not None and row["freshness"] == FRESH:
        return None
    if row is not None and row["value"] is not None and row["freshness"] == STALE:
        return "%s (dernière lecture le %s)" % (stale, _when(row["read_at"]))
    if row is not None and row.get("failed_at") is not None:
        return "%s (dernier essai le %s)" % (failing, _when(row["failed_at"]))
    if row is not None and row["value"] is not None:
        return "%s (dernière lecture le %s)" % (stale, _when(row["read_at"]))
    return reading


def _truncated(beads, first_day):
    """Whether the runs read are as many as the cockpit keeps, the least
    recently updated of them within the period."""
    if len(beads or []) < RUNS_LIMIT:
        return False
    oldest = min((_ts(bead.get("updated_at")) for bead in beads if isinstance(bead, dict)),
                 key=lambda at: at if at is not None else float("inf"), default=None)
    return oldest is None or _day(oldest) >= first_day


def _read(row):
    if row is None or not row.get("read_at"):
        return "pas encore lues"
    return "lues le %s" % _when(row["read_at"])


def _when(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%d/%m à %H:%M (Paris)")


def _days(now, count):
    today = datetime.fromtimestamp(now, tz=PARIS).date()
    return [today - timedelta(days=count - 1 - i) for i in range(count)]


def _day(epoch):
    return datetime.fromtimestamp(epoch, tz=PARIS).date()


def _ts(value):
    """An ISO instant as epoch seconds, or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


def _record(metadata, key):
    value = (metadata or {}).get(key)
    if isinstance(value, str) and value[:1] in "{[":
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _result(bead):
    """A result whose merge the flow proved: title, project key, and the
    instants of its publication, delivery, acceptance and merge (None when
    the flow did not write it)."""
    metadata = bead.get("metadata") or {}
    promotion = _record(metadata, "gc.flow.promotion")
    merged = _ts((promotion or {}).get("at"))
    if merged is None:
        return None
    judgement = _record(metadata, "gc.flow.judgement") or {}
    accepted = [_ts(answer.get("at")) for answer in judgement.get("answers") or []
                if isinstance(answer, dict) and answer.get("response") == "accepted" and not answer.get("voided")]
    return {"title": bead.get("title") or "", "project": metadata.get("gc.project_id") or "",
            "published": _ts(bead.get("created_at")),
            "delivered": _ts((_record(metadata, "gc.flow.delivered") or {}).get("at")),
            "accepted": max(filter(None, accepted), default=None), "merged": merged}


def _project_names(row):
    value = (row or {}).get("value") or {}
    return {p.get("project_id"): p.get("display_name") or p.get("project_id")
            for p in value.get("projects") or [] if isinstance(p, dict)}


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def delay_text(seconds):
    """« 3 h 05 », « 45 min »: a delay to the minute, as the views write it."""
    minutes = int(round(seconds / 60))
    return "%d h %02d" % divmod(minutes, 60) if minutes >= 60 else "%d min" % minutes
