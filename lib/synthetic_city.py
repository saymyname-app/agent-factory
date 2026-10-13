"""What the synthetic sources of the isolated cockpit answer for one dataset
(T01R, af-m2tr6o; Spec af-2zseit, user story 126).

    city = synthetic_city.from_dataset(json.loads(text))

A dataset is one frozen state of a Validated Prototype, in one of two
formats. `from_dataset` translates what it says into the answers of the
sources the cockpit reads: a supervisor (`name`, `suspended`, `sessions`,
`reading`), a tracker (`beads`) and the declared projects (`projects`).
`bin/cockpit-isolated` serves them; `docs/COCKPIT.md`, « State from the
dataset », holds the table of the rules.

Nothing here is canned: a value a source answers is written in the dataset.
What a dataset says that no source of the cockpit answers (theme, width,
selection, measures of the machine) is left out, and a dataset whose
content cannot be read by these rules is refused, never served in part.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# How the supervisor and the tracker are read during the launch.
READ = "read"            # they answer
READ_ONCE = "read_once"  # the supervisor answers once, then no more
UNREAD = "unread"        # neither ever answers
# The views of a Panorama state (`ui.state`) that fix the reading.
UNREAD_VIEWS = ("loading", "error")
READ_ONCE_VIEWS = ("stale", "offline")

DESCRIPTOR_CONTRACT = "agent-factory-project-descriptor/v1"
NEEDS_BENJAMIN = "gc.needs_benjamin"
PROJECT_KEY = "gc.project_id"

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
RITUAL_PHASE = re.compile(r"ritualPhase='([a-z]+)'")
# « Reprise du cockpit · À juger »: the current chantier of a project.
CHANTIER = re.compile(r"^(?P<title>.+) · (?P<stage>[^·]+)$")


class DatasetRefused(ValueError):
    """The dataset is not one the isolated cockpit serves."""


@dataclass(frozen=True)
class SyntheticCity:
    name: str
    at: str
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
    return _panorama_city(name, at, ui, dataset.get("visible_text"))


def project_id(display_name: str) -> str:
    """The key of a project the dataset only names: « Notes » is `notes`."""
    plain = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _descriptor(display_name: str) -> dict:
    return {"contract": DESCRIPTOR_CONTRACT, "project_id": project_id(display_name), "display_name": display_name}


# Panorama: the page of the state, as text ----------------------------------

def _panorama_city(name, at, ui, text) -> SyntheticCity:
    if not isinstance(text, str) or not text.strip():
        raise DatasetRefused("a Panorama state without the text of its page (visible_text)")
    lines = [line.strip() for line in text.split("\n")]
    view = ui.get("state")
    reading = UNREAD if view in UNREAD_VIEWS else READ_ONCE if view in READ_ONCE_VIEWS else READ
    stop_step = STOP_STEP.search(ui.get("setup") or "")
    beads, projects = [], {}

    def declare(display_name):
        projects.setdefault(project_id(display_name), _descriptor(display_name))
        return project_id(display_name)

    for number, (title, awaited) in enumerate(_awaited(lines), 1):
        beads.append({
            "id": f"synthetic-request-{number}", "title": title, "status": "open", "issue_type": "task",
            "created_at": at,
            "metadata": {NEEDS_BENJAMIN: title, PROJECT_KEY: declare(awaited["project"]),
                         "gc.escalation_pourquoi": awaited["kind"], "gc.escalation_horodatage": at},
        })
    for display_name, chantier in _projects(lines):
        key = declare(display_name)
        if chantier:
            beads.append({
                "id": f"synthetic-chantier-{key}", "title": chantier["title"], "status": "open",
                "issue_type": "convoy", "labels": ["approved-ticket-graph"], "created_at": at,
                "metadata": {PROJECT_KEY: key, "gc.graph_digest": f"synthetic:{key}",
                             "synthetic.stage": chantier["stage"]},
            })
    # An event of the journal and a merged result are past: the tracker
    # holds no open work for them, their project is declared.
    for event in _journal(lines):
        if event["project"]:
            declare(event["project"])
    for merged in _merged(lines):
        declare(merged["project"])
    ritual = _ritual(lines)
    if ritual:
        phase = RITUAL_PHASE.search(ui.get("setup") or "")
        beads.append({
            "id": "synthetic-ritual", "title": ritual["title"], "status": "open", "issue_type": "task",
            "created_at": at,
            "metadata": {PROJECT_KEY: declare(ritual["project"]),
                         "synthetic.ritual_phase": phase.group(1) if phase else ""},
        })
    return SyntheticCity(
        name=name, at=at, reading=reading,
        suspended=bool(stop_step) and stop_step.group(1) == "suspended",
        beads=beads, projects=sorted(projects.values(), key=lambda d: d["project_id"]),
    )


def _after(lines, heading):
    """The lines that follow the first line equal to `heading`, or None."""
    return lines[lines.index(heading) + 1:] if heading in lines else None


def _awaited(lines):
    """What waits for the operator: as many (title, who · what) pairs under
    « Ce qui t’attend » as « Décisions à prendre » counts."""
    count = _after(lines, "Décisions à prendre")
    if count is None:
        return []
    if not count or not count[0].isdigit():
        raise DatasetRefused("« Décisions à prendre » is followed by no count")
    rows = _after(lines, "Ce qui t’attend") or []
    found = []
    for title, who in zip(rows[0::2], rows[1::2]):
        match = AWAITED.match(who)
        if len(found) == int(count[0]) or not match:
            break
        found.append((title, match.groupdict()))
    if len(found) != int(count[0]):
        raise DatasetRefused(
            f"« Décisions à prendre » counts {count[0]}, « Ce qui t’attend » lists {len(found)}"
        )
    return found


def _projects(lines):
    """The projects the page shows, each with its current chantier when the
    page names one: the cards under « Projets » of the overview, or the one
    project of a project page."""
    page = _after(lines, "← Projets")
    if page is not None:
        if not page or not page[0]:
            raise DatasetRefused("a project page that names no project")
        current = _after(lines, "CHANTIER ACTUEL")
        stage = next((line for line in page[1:] if line), "")
        return [(page[0], {"title": current[0], "stage": stage} if current and current[0] else None)]
    cards = _after(lines, "Projets")
    if cards is None:
        return []
    found, card = [], []
    for line in cards:
        if line != "→":
            card.append(line)
            continue
        chantier = CHANTIER.match(card[1]) if len(card) > 1 else None
        if not card or not card[0] or not chantier:
            raise DatasetRefused(f"a project card that names no project and chantier: {card}")
        found.append((card[0], chantier.groupdict()))
        card = []
    return found


def _journal(lines):
    """The events of the journal: « HH:MM (Paris) · projet · nature », or
    « HH:MM (Paris) · source » for a technical one."""
    return [match.groupdict() for line in lines if (match := JOURNAL_EVENT.match(line))]


def _merged(lines):
    """The merged results of the analyses: « projet · quand », under a title."""
    if "Analyses" not in lines:
        return []
    return [match.groupdict() for line in lines if (match := MERGED.match(line))]


def _ritual(lines):
    """The ritual a ritual page is about, and the project it runs on."""
    page = _after(lines, "← Rituels")
    if page is None:
        return None
    page = [line for line in page if line]
    project = RITUAL_PROJECT.match(page[1]) if len(page) > 1 else None
    if not project:
        raise DatasetRefused("a ritual page that names no ritual and project")
    return {"title": page[0], "project": project.group("project")}


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
                             "synthetic.run_started": run["started"]},
            })
            for job in run["jobs"]:
                lane, job_id = lanes[job["lane"]], f"{run_id}-{job['id']}"
                running = job["end"] is None
                beads.append({
                    "id": job_id, "title": job["name"], "issue_type": "task", "created_at": at, "parent": run_id,
                    "status": "in_progress" if running else "closed", "assignee": lane["name"],
                    "description": job["prompt"] or "", "close_reason": job["result"] or "",
                    "metadata": {"synthetic.lane": lane["id"], "synthetic.lane_kind": lane["kind"]},
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
        name=name, at=at, reading=READ_ONCE if ui.get("stale") is True else READ,
        beads=beads, sessions=[sessions[lane] for lane in lanes if lane in sessions],
    )
