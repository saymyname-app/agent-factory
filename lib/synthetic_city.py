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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

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
    # A Runs state: the moment the state shows (its clock starts there, then
    # runs), and what it selects -- the filter, the run, the job, the event
    # the cockpit opens when the address names none.
    clock_start: str | None = None
    view: dict = field(default_factory=dict)


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
        return _runs_city(name, at, ui, dataset["fixtures"])
    return _panorama_city(name, _fixed_time(at), ui, dataset.get("visible_text"), _folded(dataset.get("folded")),
                          _folded(dataset.get("drawn"), "drawn"), _run_cards(dataset.get("runs")))


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


# Runs: lanes, runs and their jobs -------------------------------------------
#
# Each run is written as the tracker holds a workflow, so the cockpit reads
# it as it reads one in service (cockpit.runs.workflows): a « Livraison
# D01 » is a convoy carrying the new-flow mark, published by Benjamin, its
# ticket, and the workflows run on it -- the author's on an input convoy
# that tracks the ticket, the code review and the Ticket Evaluation on an
# input convoy that tracks the bead the dispatch door wrote to launch them
# (its description names the convoy and the ticket); a « Maintenance » is
# a workflow root of the formula mol-do-work run on the work Benjamin
# asked for. Each job is a step of one of those roots: Benjamin's a plain
# step routed to him, the code's a check (passed once closed), an agent's a
# ralph step whose closing runs a check, claimed by an attempt of the
# session of that agent (passed once closed) -- one session per agent, as
# the supervisor lists it (its agent, its template and its provider, from
# the lane's name and role « Relectrice · Claude »). The datasets name no project: their runs
# are of the Factory's own, RUN_PROJECT.

RUN_FORMULAS = {"Livraison D01": "mol-ticket-author", "Maintenance": "mol-do-work"}
RUN_FILTERS = {"all": "tous", "active": "en-cours", "completed": "termines"}
RUN_PROJECT = "agent-factory"
RUN_TRIGGERED_BY = "benjamin"
# The workflows of a D01 other than the author's, by the role of the agent
# of their jobs: (formula, the title the dispatch door gives its bead).
DISPATCHED = (("Relect", "mol-code-review", "Revue de code"), ("Évaluat", "mol-ticket-evaluation", "Ticket Evaluation"))


def _runs_city(name, at, ui, fixtures) -> SyntheticCity:
    moment = _fixed_time(at)
    if moment.tzinfo is None:
        raise DatasetRefused(f"its fixed time (generated_at) has no offset: {at!r}")
    try:
        lanes = {lane["id"]: lane for lane in fixtures["lanes"]}
        beads, sessions, opened, view = [], {}, [], {}
        for run in fixtures["runs"]:
            beads += _run_records(run, lanes, moment, sessions, opened, ui, view)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise DatasetRefused(f"a Runs state whose fixtures (lanes, runs, jobs) cannot be read: {exc!r}") from exc
    if ui.get("filter") in RUN_FILTERS:
        view["filter"] = RUN_FILTERS[ui["filter"]]
    if isinstance(ui.get("selected_event"), int):
        view["event"] = ui["selected_event"]
    clock = max(opened, default=moment)
    return SyntheticCity(
        name=name, reading=READ_ONCE if ui.get("stale") is True else READ,
        beads=beads, sessions=[sessions[lane] for lane in lanes if lane in sessions],
        clock_start=clock.isoformat(), view=view,
    )


def _utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_records(run, lanes, moment, sessions, opened, ui, view) -> list:
    """The beads of one run of the fixtures; its open agents' sessions in
    `sessions`, the moment it is shown at in `opened` when it is open, what
    the state selects of it in `view`."""
    formula = RUN_FORMULAS.get(run["type"])
    if formula is None:
        raise DatasetRefused(f"a run of a type no workflow has: {run['type']!r}")
    hours, minutes = run["started"].split(":")
    start = moment.replace(hour=int(hours), minute=int(minutes), second=0, microsecond=0)

    def at(offset):
        return _utc(start + timedelta(seconds=offset))

    def ended(end):
        return {"status": "closed", "closed_at": at(end)} if end is not None else {"status": "open"}

    key, records = run["id"], []
    if run["end"] is None:
        opened.append(start + timedelta(seconds=run["elapsed"]))

    def workflow(suffix, workflow_formula, tracked, title):
        """A workflow root of `workflow_formula` run on an input convoy that
        tracks `tracked`; its id."""
        root_id, wrapper = f"synthetic-workflow-{key}{suffix}", f"synthetic-input-{key}{suffix}"
        records.append({"id": wrapper, "title": f"input convoy for {tracked}", "issue_type": "convoy",
                        "created_at": at(0), "status": "open", "metadata": {"gc.synthetic": "true"},
                        "dependencies": [{"issue_id": wrapper, "depends_on_id": tracked, "type": "tracks"}]})
        records.append({"id": root_id, "title": title, "issue_type": "task", "created_at": at(0), **ended(run["end"]),
                        "metadata": {"gc.kind": "workflow", "gc.formula_name": workflow_formula,
                                     "gc.input_convoy_id": wrapper}})
        return root_id

    def dispatched(suffix, workflow_formula, title, said):
        """The bead the dispatch door writes to launch `workflow_formula`."""
        bead_id = f"synthetic-dispatch-{key}{suffix}"
        records.append({"id": bead_id, "title": title, "description": said, "issue_type": "task",
                        "created_at": at(0), "created_by": RUN_TRIGGERED_BY, **ended(run["end"]),
                        "metadata": {"gc.dispatched_via": "dispatch-door", "gc.dispatch_formula": workflow_formula,
                                     "gc.dispatch_rig": RUN_PROJECT}})
        return bead_id

    roots = {}
    if formula == "mol-ticket-author":
        run_id, ticket_id, digest = f"synthetic-run-{key}", f"synthetic-ticket-{key}", f"sha256:synthetic-{key}"
        records.append({"id": run_id, "title": run["title"], "issue_type": "convoy", "created_at": at(0),
                        "created_by": RUN_TRIGGERED_BY, **ended(run["end"]),
                        "metadata": {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": digest,
                                     "gc.project_id": RUN_PROJECT, "gc.spec_id": f"synthetic-spec-{key}"}})
        ticket = {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": digest, "gc.ticket_id": key}
        if run["status"] == "Fusionné":
            ticket["gc.flow.merge"] = json.dumps({"at": at(run["end"]), "outcome": "merged"})
        elif run["status"] == "Abandonné":
            ticket["gc.flow.gate.withdrawn"] = json.dumps({"at": at(run["end"])})
        records.append({"id": ticket_id, "title": run["title"], "issue_type": "task", "created_at": at(0),
                        **ended(run["end"]), "metadata": ticket})
        roots[None] = workflow("", formula, ticket_id, formula)
        for prefix, workflow_formula, title in DISPATCHED:
            if any(lanes[job["lane"]]["role"].startswith(prefix) for job in run["jobs"]):
                said = f"{title} of ticket {ticket_id}.\n\nconvoy: {run_id}\nticket: {ticket_id}\n"
                suffix = f"-{workflow_formula}"
                launched = dispatched(suffix, workflow_formula, f"{title} — {ticket_id}", said)
                roots[prefix] = workflow(suffix, workflow_formula, launched, workflow_formula)
    else:
        work = dispatched("", formula, run["title"], f"{run['title']}.\n")
        run_id = roots[None] = workflow("", formula, work, formula)
    if ui.get("run") == key:
        view["run"] = run_id
    for job in run["jobs"]:
        lane = lanes[job["lane"]]
        root_id = next((root for prefix, root in roots.items() if prefix and lane["role"].startswith(prefix)),
                       roots[None])
        step_id = f"{root_id}-{job['id']}"
        step = {"gc.root_bead_id": root_id, "gc.step_id": job["id"]}
        passed = {"gc.outcome": "pass"} if job["end"] is not None else {}
        if lane["kind"] == "human":
            step.update({"gc.routed_to": "benjamin"})
        elif lane["kind"] == "code":
            step.update({"gc.kind": "check", **passed})
        else:
            step.update({"gc.kind": "ralph", "gc.check_mode": "exec", **passed})
        records.append({"id": step_id, "title": job["name"], "issue_type": "task", "created_at": at(job["start"]),
                        "description": job["prompt"] or "", "close_reason": job["result"] or "",
                        **ended(job["end"]), "metadata": step})
        if lane["kind"] == "agent":
            template, _, provider = lane["role"].partition(" · ")
            session = f"synthetic-session-{lane['id']}"
            records.append({"id": f"{step_id}-attempt-1", "title": job["name"], "issue_type": "task",
                            "created_at": at(job["start"]), **ended(job["end"]),
                            "metadata": {"gc.logical_bead_id": step_id, "gc.root_bead_id": root_id, "gc.attempt": "1",
                                         "gc.session_name": session, "gc.routed_to": template,
                                         "gc.claimed_at": at(job["start"]), **passed}})
            running = job["end"] is None and run["end"] is None
            if running or lane["id"] not in sessions:
                sessions[lane["id"]] = {
                    "id": session, "name": session, "session_name": session, "agent_name": lane["name"],
                    "template": template, "provider": provider or None, "running": running,
                    "last_active": _utc(moment), **({"active_bead": step_id} if running else {}),
                }
        if ui.get("run") == key and ui.get("selected_job") == job["id"]:
            view["job"] = step_id
    return records
