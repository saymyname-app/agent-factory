"""What the synthetic sources of the isolated cockpit answer for one dataset
(T01R4, af-u2fa7b, from T01R3 af-7hk9e7, T01R2 af-6a98ip and T01R af-m2tr6o; Spec af-2zseit, user story 126).

    city = synthetic_city.from_dataset(json.loads(text))

A dataset is one frozen state of a Validated Prototype, in one of two
formats. `from_dataset` translates what it says into the answers of the
sources the cockpit reads: a supervisor (`name`, `suspended`, `sessions`,
`reading`), a tracker (`beads`) and the declared projects (`projects`).
`bin/cockpit-isolated` serves them; `docs/COCKPIT.md`, « State from the
dataset », holds the table of the rules.

Nothing here is canned: a value a source answers is written in the dataset.
A Panorama state is the text of one screen. What the cockpit has a record
for is read into that record: a request, a project and its chantier, a
ritual, an event of the journal. Every other section of the screen is kept
as it is said, one bead per section under its heading (`SAID`), until the
ticket of that screen reads it into records of its own. Only the theme and
the width a state is looked at with, the titles, tabs and banners above the
first section, and the sections that hold nothing but links are left out. A
screen or a state no rule reads is refused, never served in part.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

# How the supervisor and the tracker are read during the launch.
READ = "read"            # they answer
READ_ONCE = "read_once"  # the supervisor answers once, then no more
UNANSWERED = "unanswered"  # neither answers: the tracker's read never ends
FAILING = "failing"        # neither answers: the tracker's read fails
# The views of a Panorama state (`ui.state`) that fix the reading.
UNREAD_VIEWS = {"loading": UNANSWERED, "error": FAILING}
READ_ONCE_VIEWS = ("stale", "offline")
# The other views: what they show is in the text of the page. Any other
# `ui.state` is the state of the result whose dossier the overview opens.
PLAIN_VIEWS = ("content", "empty", "long", "missing")

DESCRIPTOR_CONTRACT = "agent-factory-project-descriptor/v1"
NEEDS_BENJAMIN = "gc.needs_benjamin"
PROJECT_KEY = "gc.project_id"
RESULT_STATE = "synthetic.result_state"
# The record of the result open under « Ce qui t’attend », and the card of a
# chantier, as the overview reads them (cockpit.ui.home.overview).
RESULT_DOSSIER = "gc.result_dossier"
PROJECT_CARD = "gc.project_card"
# The card of a run among the last runs of the overview.
RUN_CARD = "gc.run_card"
# The label of a bead that keeps one section of a screen as it is said.
SAID = "said"
# What an event bead meant for the journal carries (cockpit.ui.journal.entries).
JOURNAL_EVENT_KEY = "gc.journal_event"

# The step of the stop a Factory state is set up at (`ui.setup`).
STOP_STEP = re.compile(r"shutdownState='([a-z]+)'")
# « Usine · résultat prêt », « Projet Notes · décision »: who waits, for what.
AWAITED = re.compile(r"^(?:Projet )?(?P<project>[^·]+?) · (?P<kind>[^·]+)$")
# « 14:48 (Paris) · Usine · Proposition », « 14:36 (Paris) · ci »: one event
# of the journal, of a project or of a technical source.
JOURNAL_EVENT = re.compile(r"^(?P<time>\d\d:\d\d) \(Paris\)(?: · (?P<project>[^·]+?))? · (?P<kind>[^·]+)$")
# « Portfolio · hier »: a merged result, under its title.
MERGED = re.compile(r"^(?P<project>[^·]+?) · (?P<when>hier|avant-hier|aujourd’hui)$")
# « Usine · données et avancement simulés »: the project of a ritual.
RITUAL_PROJECT = re.compile(r"^(?P<project>[^·]+?) · ")
# « Reprise du cockpit · À juger »: the current chantier of a project.
CHANTIER = re.compile(r"^(?P<title>.+) · (?P<stage>[^·]+)$")
# The day an event of the journal is listed under, counted from the day of
# the dataset.
DAYS = {"Aujourd’hui": 0, "Hier": -1}


class DatasetRefused(ValueError):
    """The dataset is not one the isolated cockpit serves."""


@dataclass(frozen=True)
class SyntheticCity:
    name: str
    suspended: bool = False
    reading: str = READ
    beads: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    # What GitHub answers for the declared repository (`github`), or None:
    # no repository declared, GitHub is not read.
    github: dict | None = None
    # The fixed time of the dataset, the cockpit's « now » when it starts.
    started: str = ""


def from_dataset(dataset) -> SyntheticCity:
    if not isinstance(dataset, dict) or dataset.get("synthetic") is not True:
        raise DatasetRefused("not marked synthetic: only a synthetic dataset is served")
    at = dataset.get("generated_at")
    if not isinstance(at, str) or not at.strip():
        raise DatasetRefused("carries no fixed time (generated_at)")
    ui = dataset.get("ui") if isinstance(dataset.get("ui"), dict) else {}
    # A Panorama state names itself in `ui.id`, a Runs state in `state`.
    name = ui.get("id") or dataset.get("state")
    if not isinstance(name, str) or not name.strip():
        raise DatasetRefused("names no state (ui.id, or state)")
    if "fixtures" in dataset:
        return replace(_runs_city(name, at, ui, dataset["fixtures"]), started=at)
    city = _panorama_city(name, _fixed_time(at), ui, dataset.get("visible_text"), _folded(dataset.get("folded")),
                          _folded(dataset.get("drawn"), "drawn"), _run_cards(dataset.get("runs")))
    return _with_sources(replace(city, started=at), dataset.get("flow"), dataset.get("github"))


def _folded(folded, key="folded") -> dict:
    """What the parts of the page that unfold say (`folded`: the label of
    each part, the lines it shows open), or what its drawings say (`drawn`:
    the heading of each drawing, the lines its marks say -- the titles of
    the points of a chart), which its text leaves out."""
    if folded is None:
        return {}
    if not isinstance(folded, dict) or not all(
            isinstance(label, str) and isinstance(lines, list) and lines and all(isinstance(l, str) for l in lines)
            for label, lines in folded.items()):
        raise DatasetRefused("its folded parts (folded) are not each a label and the lines it shows open" if key == "folded"
                             else f"its drawings ({key}) are not each a heading and the lines it says")
    return folded


RUN_TONES = ("wait", "live", "done")
LANE_KINDS = ("human", "code", "agent")


def _run_cards(runs) -> list:
    """The cards of the last runs the overview shows (`runs`), in their
    order: each its workflow (`type`), its status and its `tone` (wait,
    live, done), its title, its step, its start (HH:MM, Paris), its
    `elapsed` seconds, and its lanes, each a name, a kind (human, code,
    agent) and the [start, end] seconds of its jobs within the run."""
    if runs is None:
        return []

    def job(span, elapsed):
        return (isinstance(span, list) and len(span) == 2 and all(isinstance(t, (int, float)) for t in span)
                and 0 <= span[0] <= span[1] <= elapsed)

    def card(run):
        return (isinstance(run, dict) and all(isinstance(run.get(key), str) and run[key]
                                              for key in ("type", "status", "title", "step", "started"))
                and run.get("tone") in RUN_TONES and isinstance(run.get("elapsed"), int) and run["elapsed"] > 0
                and isinstance(run.get("lanes"), list) and run["lanes"]
                and all(isinstance(lane, dict) and isinstance(lane.get("name"), str) and lane.get("kind") in LANE_KINDS
                        and isinstance(lane.get("jobs"), list) and all(job(span, run["elapsed"]) for span in lane["jobs"])
                        for lane in run["lanes"]))

    if not isinstance(runs, list) or not all(card(run) for run in runs):
        raise DatasetRefused("its runs (runs) are not each a card: type, status, tone, title, step, started, "
                             "elapsed and lanes of jobs within it")
    return runs


def _fixed_time(at: str) -> datetime:
    try:
        return datetime.fromisoformat(at)
    except ValueError as exc:
        raise DatasetRefused(f"its fixed time (generated_at) is not a date: {at!r}") from exc


def project_id(display_name: str) -> str:
    """The key of a project the dataset only names: « Notes » is `notes`."""
    plain = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _descriptor(display_name: str) -> dict:
    return {"contract": DESCRIPTOR_CONTRACT, "project_id": project_id(display_name), "display_name": display_name}


# Panorama: one screen, as text ----------------------------------------------

class _Tracker:
    """The beads and the declared projects read from one screen."""

    def __init__(self, at: datetime):
        self.at = at
        self.beads = []
        self.projects = {}

    def declare(self, display_name: str) -> str:
        """Declare the project the screen names; its key."""
        self.projects.setdefault(project_id(display_name), _descriptor(display_name))
        return project_id(display_name)

    def add(self, bead_id: str, title: str, said=(), project=None, at=None, metadata=None, **fields) -> None:
        """One open bead under `title`: the lines `said` of it, the project
        it belongs to (a key), when it happened if not at the fixed time."""
        bead = {"id": bead_id, "title": title, "status": "open", "issue_type": "task",
                "created_at": (at or self.at).isoformat(), "metadata": dict(metadata or {}), **fields}
        if said:
            bead["description"] = "\n".join(said)
        if project:
            bead["metadata"][PROJECT_KEY] = project
        self.beads.append(bead)

    def keep(self, sections: dict, headings, project=None) -> None:
        """Keep as said the sections of `headings` the screen shows."""
        for heading in headings:
            if sections.get(heading):
                self.add(f"synthetic-said-{project_id(heading)}", heading, said=sections[heading],
                         project=project, labels=[SAID])


def _panorama_city(name, at, ui, text, folded, drawn, runs) -> SyntheticCity:
    if not isinstance(text, str) or not text.strip():
        raise DatasetRefused("a Panorama state without the text of its page (visible_text)")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    view = ui.get("state")
    reading = UNREAD_VIEWS.get(view) or (READ_ONCE if view in READ_ONCE_VIEWS else READ)
    if reading == READ_ONCE and lines[0] not in SCREENS:
        # The banner of a reading that is no longer current, above the title.
        lines = lines[1:]
    read_screen = SCREENS.get(lines[0]) if lines else None
    if read_screen is None:
        raise DatasetRefused(f"a screen no rule reads: « {lines[0] if lines else ''} »")
    result_state = None if view is None or reading != READ or view in PLAIN_VIEWS else view
    stop_step = STOP_STEP.search(ui.get("setup") or "")
    tracker = _Tracker(at)
    read_screen(lines, tracker)
    # A drawing is kept as it is said, under its heading, on the screen that
    # shows that heading.
    undrawn = sorted(set(drawn) - set(lines))
    if undrawn:
        raise DatasetRefused(f"drawings under no heading of the screen: {undrawn}")
    for heading, said in drawn.items():
        tracker.add(f"synthetic-said-{project_id(heading)}", heading, said=said, labels=[SAID])
    if runs and "Derniers runs" not in lines:
        raise DatasetRefused("runs (runs) on a screen without « Derniers runs »")
    for number, run in enumerate(runs, start=1):
        tracker.add(f"synthetic-run-card-{number}", run["title"], issue_type="epic",
                    metadata={RUN_CARD: json.dumps(run, ensure_ascii=False)})
    dossier = next((bead for bead in tracker.beads if bead["id"] == DOSSIER), None)
    if result_state and dossier is None:
        raise DatasetRefused(f"« {lines[0]} » opens no dossier to be in the state {result_state!r} (ui.state)")
    # A result in one of its states (`ui.state`) is the panels of T02S: its
    # dossier is only marked with that state.
    record = None if dossier is None or result_state else _dossier_record(
        dossier["title"], dossier["description"].split("\n"))
    unfolding = [resource for resource in (record or {}).get("resources", []) if not resource["opens"]] + \
        (record or {}).get("reports", [])
    unread = sorted(set(folded) - {resource["label"] for resource in unfolding})
    if unread:
        raise DatasetRefused(f"folded parts that no part of the dossier unfolds: {unread}")
    for resource in unfolding:
        if resource["label"] in folded:
            resource["said"] = folded[resource["label"]]
    if result_state:
        dossier["metadata"][RESULT_STATE] = result_state
    if record is not None:
        dossier["metadata"][RESULT_DOSSIER] = json.dumps(record, ensure_ascii=False)
    return SyntheticCity(
        name=name, reading=reading,
        suspended=bool(stop_step) and stop_step.group(1) == "suspended",
        beads=tracker.beads, projects=sorted(tracker.projects.values(), key=lambda d: d["project_id"]),
    )


def _sections(lines, headings) -> dict:
    """The lines of a screen under each of its `headings`; under None, those
    above the first one. A heading shown twice is one section."""
    sections, heading = {None: []}, None
    for line in lines:
        if line in headings:
            heading = line
            sections.setdefault(heading, [])
        else:
            sections[heading].append(line)
    return sections


# « Vue d’ensemble »: four indicators, what waits for the operator and the
# dossier open under it, the cards of the projects. The activity chart says
# what the dataset's `drawn` says under its heading; the last runs are the
# cards of its `runs`.
INDICATORS = ("Décisions à prendre", "Résultats fusionnés", "Délai de livraison", "Vérifications CI réussies")
AWAITING, PROJECTS = "Ce qui t’attend", "Projets"
DOSSIER = "synthetic-dossier"
# A part of a dossier that unfolds and is its report, not one of its resources.
REPORT = "Compte rendu"


def _overview(lines, tracker) -> None:
    sections = _sections(lines, (*INDICATORS, "Activité sur 7 jours", "Derniers runs", AWAITING, PROJECTS))
    tracker.keep(sections, INDICATORS)
    dossier = _awaited(sections, tracker)
    if dossier:
        about = AWAITED.match(dossier[0])
        if not about or len(dossier) < 2:
            raise DatasetRefused(f"a dossier that names no project and title: {dossier[:2]}")
        tracker.add(DOSSIER, dossier[1], said=[dossier[0], *dossier[2:]], project=tracker.declare(about["project"]))
    card = []
    for line in sections.get(PROJECTS, []):
        if line != "→":
            card.append(line)
            continue
        chantier = CHANTIER.match(card[1]) if len(card) > 1 else None
        if not chantier:
            raise DatasetRefused(f"a project card that names no project and chantier: {card}")
        figures = card[2:]
        _chantier(tracker, tracker.declare(card[0]), chantier["title"], [chantier["stage"], *figures], card={
            "stage": chantier["stage"], "figures": figures[:-1], "release": figures[-1] if figures else None,
        })
        card = []
    if card:
        raise DatasetRefused(f"lines under « {PROJECTS} » that belong to no card: {card}")


def _awaited(sections, tracker) -> list:
    """Read what waits for the operator: as many (title, who · what) pairs
    under « Ce qui t’attend » as « Décisions à prendre » counts, one bead
    each. The lines that follow them: the dossier the page opens."""
    count = sections.get(INDICATORS[0])
    if count is None:
        return []
    if not count or not count[0].isdigit():
        raise DatasetRefused("« Décisions à prendre » is followed by no count")
    rows, found = sections.get(AWAITING, []), 0
    for title, who in zip(rows[0::2], rows[1::2]):
        awaited = AWAITED.match(who)
        if found == int(count[0]) or not awaited:
            break
        found += 1
        tracker.add(f"synthetic-request-{found}", title, project=tracker.declare(awaited["project"]), metadata={
            NEEDS_BENJAMIN: title, "gc.escalation_pourquoi": awaited["kind"],
            "gc.escalation_horodatage": tracker.at.isoformat(),
        })
    if found != int(count[0]):
        raise DatasetRefused(f"« Décisions à prendre » counts {count[0]}, « {AWAITING} » lists {found}")
    return rows[2 * found:]


def _chantier(tracker, project: str, title: str, said, card=None) -> None:
    """The open chantier of `project`, and what the screen says of it; with
    `card`, its card on the overview: its stage, its figures and the line of
    its release."""
    metadata = {"gc.graph_digest": f"synthetic:{project}"}
    if card is not None:
        metadata[PROJECT_CARD] = json.dumps(card, ensure_ascii=False)
    tracker.add(f"synthetic-chantier-{project}", title, said=said, project=project, issue_type="convoy",
                labels=["approved-ticket-graph"], metadata=metadata)


# The bar of a result to judge: the cockpit draws it, the record does not
# carry it.
RESULT_BAR = ("Essai ↗", "Avis")
OPENS = "↗"


def _dossier_record(title: str, lines) -> dict:
    """The record of the result to judge open under « Ce qui t’attend »:
    what it is about (« projet · sujet »), its title, what its panel says
    (`summary`), its resources -- that open (label, detail, « ↗ ») or that
    unfold (a label alone; what they say open is added from the dataset's
    `folded`) -- and its reports (`reports`, a part that unfolds named
    « Compte rendu … »)."""
    about, *lines = [line for line in lines if line not in RESULT_BAR]
    if not lines:
        raise DatasetRefused(f"a dossier that says nothing under its title: « {title} »")
    record = {"about": about, "title": title, "summary": lines[0], "resources": [], "reports": []}
    rest, at = lines[1:], 0
    while at < len(rest):
        if rest[at + 2:at + 3] == [OPENS]:
            record["resources"].append({"label": rest[at], "detail": rest[at + 1], "opens": True})
            at += 3
        else:
            part = {"label": rest[at], "opens": False}
            record["reports" if rest[at].startswith(REPORT) else "resources"].append(part)
            at += 1
    return record


# The page of one project (« ← Projets »): what it is and its indicators
# above the first section, its next release and next step, its current
# chantier, its roadmap and last changes. « Ressources du projet » is links.
PROJECT_SAID = ("Prochaine release", "PROCHAIN JALON", "ROADMAP", "Derniers changements")
CURRENT_CHANTIER = "CHANTIER ACTUEL"


def _project_page(lines, tracker) -> None:
    sections = _sections(lines, (*PROJECT_SAID, CURRENT_CHANTIER, "Ressources du projet"))
    about = sections[None][1:]
    if not about:
        raise DatasetRefused("a project page that names no project")
    project = tracker.declare(about[0])
    tracker.add(f"synthetic-project-{project}", about[0], said=about[1:], project=project, labels=[SAID])
    tracker.keep(sections, PROJECT_SAID, project=project)
    current = sections.get(CURRENT_CHANTIER)
    if current:
        _chantier(tracker, project, current[0], current[1:])


def _journal(lines, tracker) -> None:
    """One event bead per event, as `bd create --type event` records it,
    marked for the journal: « HH:MM (Paris) · projet · nature », or « HH:MM
    (Paris) · source » for a technical one -- its category -- then its
    title and what the journal says of it. The lines above the first event
    are tabs."""
    day, events = 0, []
    for line in lines:
        header = JOURNAL_EVENT.match(line)
        if header:
            hour, minute = header["time"].split(":")
            when = (tracker.at + timedelta(days=day)).replace(hour=int(hour), minute=int(minute), second=0)
            events.append((when, header, []))
        elif line in DAYS:
            day = DAYS[line]
        elif events:
            events[-1][2].append(line)
    for number, (when, header, said) in enumerate(events, 1):
        if not said:
            raise DatasetRefused(f"an event of the journal without a title: {header.group(0)}")
        tracker.add(f"synthetic-event-{number}", said[0], said=said[1:], at=when, issue_type="event",
                    event_kind=header["kind"], labels=[header["kind"]], metadata={JOURNAL_EVENT_KEY: header["kind"]},
                    project=header["project"] and tracker.declare(header["project"]))


# « Usine »: every section is kept as said.
FACTORY_SAID = (
    "Machine d’exécution", "Connexions", "Fournisseurs et accès API", "Agents dans le workflow",
    "Auteur livraison", "Autres rôles", "Suspension, reprise et arrêt", "Nettoyer les espaces inutilisés",
    "Ressources et libellés longs",
)


def _factory(lines, tracker) -> None:
    tracker.keep(_sections(lines, FACTORY_SAID), FACTORY_SAID)


def _rituals(lines, tracker) -> None:
    """One bead per ritual of the list: a line in capitals says how it is
    launched, the next one is its title, the others what the list says of it."""
    rituals = []
    for line in lines[1:]:
        if line == line.upper() and any(letter.isalpha() for letter in line):
            rituals.append([line])
        elif rituals:
            rituals[-1].append(line)
    for number, (launched, *said) in enumerate(rituals, 1):
        if not said:
            raise DatasetRefused(f"a ritual without a title, under « {launched} »")
        tracker.add(f"synthetic-ritual-{number}", said[0], said=[launched, *said[1:]])


def _ritual_page(lines, tracker) -> None:
    """The page of one ritual (« ← Rituels »): its title, « projet · … »,
    then its steps and what the step it is at shows."""
    project = RITUAL_PROJECT.match(lines[2]) if len(lines) > 2 else None
    if not project:
        raise DatasetRefused("a ritual page that names no ritual and project")
    tracker.add("synthetic-ritual", lines[1], said=lines[3:], project=tracker.declare(project["project"]))


# « Analyses »: the view it is on is kept as said; a merged result
# (« projet · hier », under its title) declares its project.
ANALYSES_SAID = ("Résultats fusionnés", "Où passe le temps ?")


def _analyses(lines, tracker) -> None:
    tracker.keep(_sections(lines, ANALYSES_SAID), ANALYSES_SAID)
    for line in lines:
        merged = MERGED.match(line)
        if merged:
            tracker.declare(merged["project"])


# The screens of Panorama, by the first line of their page.
SCREENS = {
    "Vue d’ensemble": _overview, "← Projets": _project_page, "Journal": _journal, "Usine": _factory,
    "Rituels": _rituals, "← Rituels": _ritual_page, "Analyses": _analyses,
}


# The records of the flow and of GitHub the Analyses read ---------------------

FLOW_MARK = "new-flow/v1"


def _with_sources(city, flow, github) -> SyntheticCity:
    """`city` with the records of the delivery flow (`flow`: its results,
    tickets and decisions) as the flow writes them on the tracker, and what
    GitHub answers (`github`: the repository, its pull requests and its
    workflow runs, as the REST API gives them)."""
    if flow is None and github is None:
        return city
    try:
        beads, projects = list(city.beads), {d["project_id"]: d for d in city.projects}

        def project(name):
            projects.setdefault(project_id(name), _descriptor(name))
            return project_id(name)

        def record(**fields):
            return json.dumps({key: value for key, value in fields.items() if value is not None}, ensure_ascii=False)

        for number, result in enumerate((flow or {}).get("results", []), 1):
            metadata = {"gc.flow.mark": FLOW_MARK, "gc.project_id": project(result["project"])}
            if result.get("delivered"):
                metadata["gc.flow.delivered"] = record(at=result["delivered"])
            if result.get("accepted"):
                metadata["gc.flow.judgement"] = json.dumps(
                    {"answers": [{"response": "accepted", "approver": "benjamin", "at": result["accepted"]}]})
            if result.get("merged"):
                metadata["gc.flow.promotion"] = record(at=result["merged"])
            beads.append({"id": f"synthetic-result-{number}", "title": result["title"], "issue_type": "convoy",
                          "status": "closed" if result.get("merged") else "open", "created_at": result["published"],
                          "labels": ["owned"], "metadata": metadata})
        for number, ticket in enumerate((flow or {}).get("tickets", []), 1):
            merge = ticket["merge"]
            beads.append({
                "id": f"synthetic-ticket-{number}", "title": ticket["title"], "issue_type": "task",
                "status": "closed" if merge["outcome"] == "merged" else "open", "created_at": ticket["dispatched"],
                "metadata": {"gc.flow.mark": FLOW_MARK, "gc.project_id": project(ticket["project"]),
                             "gc.flow.gate.dispatch": record(at=ticket["dispatched"]),
                             "gc.flow.merge": record(outcome=merge["outcome"], at=merge["at"])},
            })
        for number, decision in enumerate((flow or {}).get("decisions", []), 1):
            metadata = {"gc.escalation_pourquoi": "décision", "gc.escalation_horodatage": decision["asked"]}
            if decision.get("answered"):
                metadata["gc.escalation_response_at"] = decision["answered"]
            else:
                metadata[NEEDS_BENJAMIN] = decision["title"]
            beads.append({"id": f"synthetic-decision-{number}", "title": decision["title"], "issue_type": "task",
                          "status": "closed" if decision.get("answered") else "open", "created_at": decision["asked"],
                          "metadata": {**metadata, PROJECT_KEY: project(decision["project"])}})
        if github is not None and not (isinstance(github.get("repository"), str) and github["repository"]
                                       and isinstance(github.get("pull_requests"), list)
                                       and isinstance(github.get("workflow_runs"), list)):
            raise TypeError("github")
    except (KeyError, TypeError, AttributeError) as exc:
        raise DatasetRefused(f"its records of the flow (flow) or of GitHub (github) cannot be read: {exc!r}") from exc
    return replace(city, beads=beads, projects=sorted(projects.values(), key=lambda d: d["project_id"]),
                   github=github)


# Runs: lanes, runs and their jobs -------------------------------------------

def _runs_city(name, at, ui, fixtures) -> SyntheticCity:
    try:
        lanes = {lane["id"]: lane for lane in fixtures["lanes"]}
        beads, sessions = [], {}
        for run in fixtures["runs"]:
            run_id = f"synthetic-run-{run['id']}"
            beads.append({
                "id": run_id, "title": run["title"], "issue_type": "epic", "created_at": at,
                "status": "open" if run["end"] is None else "closed",
                "metadata": {"synthetic.run_type": run["type"], "synthetic.run_status": run["status"],
                             "synthetic.run_started": run["started"], "synthetic.run_elapsed": run["elapsed"]},
            })
            for job in run["jobs"]:
                lane, job_id = lanes[job["lane"]], f"{run_id}-{job['id']}"
                running = job["end"] is None
                beads.append({
                    "id": job_id, "title": job["name"], "issue_type": "task", "created_at": at, "parent": run_id,
                    "status": "in_progress" if running else "closed", "assignee": lane["name"],
                    "description": job["prompt"] or "", "close_reason": job["result"] or "",
                    "metadata": {"synthetic.lane": lane["id"], "synthetic.lane_kind": lane["kind"],
                                 "synthetic.lane_role": lane["role"], "synthetic.job_start": job["start"],
                                 "synthetic.job_end": job["end"]},
                })
                if lane["kind"] == "agent" and (running or lane["id"] not in sessions):
                    sessions[lane["id"]] = {
                        "id": f"synthetic-session-{lane['id']}", "template": lane["role"],
                        "session_name": lane["name"], "running": running, "last_active": at,
                        **({"active_bead": job_id} if running else {}),
                    }
    except (KeyError, TypeError) as exc:
        raise DatasetRefused(f"a Runs state whose fixtures (lanes, runs, jobs) cannot be read: {exc!r}") from exc
    return SyntheticCity(
        name=name, reading=READ_ONCE if ui.get("stale") is True else READ,
        beads=beads, sessions=[sessions[lane] for lane in lanes if lane in sessions],
    )
