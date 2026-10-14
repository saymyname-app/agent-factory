"""What the synthetic sources of the isolated cockpit answer for one dataset
(T01R2, af-6a98ip, from T01R af-m2tr6o; Spec af-2zseit, user story 126).

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

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# How the supervisor and the tracker are read during the launch.
READ = "read"            # they answer
READ_ONCE = "read_once"  # the supervisor answers once, then no more
UNREAD = "unread"        # neither ever answers
# The views of a Panorama state (`ui.state`) that fix the reading.
UNREAD_VIEWS = ("loading", "error")
READ_ONCE_VIEWS = ("stale", "offline")
# The other views: what they show is in the text of the page. Any other
# `ui.state` is the state of the result whose dossier the overview opens.
PLAIN_VIEWS = ("content", "empty", "long", "missing")

DESCRIPTOR_CONTRACT = "agent-factory-project-descriptor/v1"
NEEDS_BENJAMIN = "gc.needs_benjamin"
PROJECT_KEY = "gc.project_id"
RESULT_STATE = "synthetic.result_state"
# The label of a bead that keeps one section of a screen as it is said.
SAID = "said"

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
    return _panorama_city(name, _fixed_time(at), ui, dataset.get("visible_text"))


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


def _panorama_city(name, at, ui, text) -> SyntheticCity:
    if not isinstance(text, str) or not text.strip():
        raise DatasetRefused("a Panorama state without the text of its page (visible_text)")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    view = ui.get("state")
    reading = UNREAD if view in UNREAD_VIEWS else READ_ONCE if view in READ_ONCE_VIEWS else READ
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
    if result_state:
        dossier = [bead for bead in tracker.beads if bead["id"] == DOSSIER]
        if not dossier:
            raise DatasetRefused(f"« {lines[0]} » opens no dossier to be in the state {result_state!r} (ui.state)")
        dossier[0]["metadata"][RESULT_STATE] = result_state
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
# dossier open under it, the cards of the projects. The activity chart and
# the last runs show nothing in a Panorama state.
INDICATORS = ("Décisions à prendre", "Résultats fusionnés", "Délai de livraison", "Vérifications CI réussies")
AWAITING, PROJECTS = "Ce qui t’attend", "Projets"
DOSSIER = "synthetic-dossier"


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
        _chantier(tracker, tracker.declare(card[0]), chantier["title"], [chantier["stage"], *card[2:]])
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


def _chantier(tracker, project: str, title: str, said) -> None:
    """The open chantier of `project`, and what the screen says of it."""
    tracker.add(f"synthetic-chantier-{project}", title, said=said, project=project, issue_type="convoy",
                labels=["approved-ticket-graph"], metadata={"gc.graph_digest": f"synthetic:{project}"})


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
    """One bead per event: « HH:MM (Paris) · projet · nature », or « HH:MM
    (Paris) · source » for a technical one, then its title and what the
    journal says of it. The lines above the first event are tabs."""
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
                    labels=[header["kind"]], project=header["project"] and tracker.declare(header["project"]))


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
