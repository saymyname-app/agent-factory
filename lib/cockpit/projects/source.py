"""The "Projets" zone's one read (spec af-oohx2x §"Suivre les projets",
§"Modèle de lecture"): the declared projects and their chantiers, computed
from Beads on this source's own rhythm and held in the read model like any
other value — the page never reads Beads itself.

What is stored is the computed view as plain data (so ``/api/status`` and
``/api/projects`` can serialise it), not the beads it was computed from.
"""
from dataclasses import asdict

from cockpit.core.beads_source import read_beads_json
from cockpit.projects.anomalies import convoy_closed_with_unmerged_child
from cockpit.projects.beads import read_convoy_beads, read_map_children
from cockpit.projects.builder import build_historique_par_projet, build_projects
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.hors_chantier import HorsChantierItem, hors_chantier_par_projet
from cockpit.projects.model import Chantier, Project, RoadmapStep
from cockpit.projects.promu import read_promotion_results
from cockpit.projects.outcome import pack_folder, read_pack_sections
from cockpit.projects.stage import CONVOY_ISSUE_TYPE, MAP_LABEL, PROJECT_KEY
from convoy_state import outcome_records_of

TARGET_KEY = "planning_run_target"
SPEC_KEY = "gc.spec_id"


def read_projects(descriptors_dir, bd_bin="bd", timeout=20, clones_dir="", rig_repos=None, git_bin="git"):
    """One complete read. Raises on any failed ``bd`` call: a partial view
    would show a project with chantiers missing as if it were whole.
    ``clones_dir`` / ``rig_repos``: where the promotion of an accepted
    chantier is read (:mod:`cockpit.projects.promu`); without them it is
    unknown, said so, never taken for done."""
    descriptors = load_descriptors(descriptors_dir)
    by_id = {}
    for bead in read_beads_json(["list"], bd_bin=bd_bin, timeout=timeout) + read_convoy_beads(
        bd_bin=bd_bin, timeout=timeout
    ):
        if isinstance(bead, dict) and bead.get("id"):
            by_id.setdefault(bead["id"], bead)
    beads = list(by_id.values())
    children_by_map_id = {
        bead["id"]: read_map_children(bead["id"], bd_bin=bd_bin, timeout=timeout)
        for bead in beads
        if MAP_LABEL in (bead.get("labels") or []) and bead.get("status") != "closed"
    }
    promotion_results = read_promotion_results(descriptors, beads, rig_repos, clones_dir, git_bin=git_bin)
    pack_reads = read_dossier_pages(beads)
    projects, sans_projet = build_projects(
        descriptors, beads, children_by_map_id, promotion_results=promotion_results, pack_reads=pack_reads
    )
    targeting = read_targeting_beads(bd_bin=bd_bin, timeout=timeout)
    # A Spec closed without successor is read only here: the active
    # chantiers are built from what is open.
    closed = [bead for bead in targeting if bead.get("status") == "closed" and bead["id"] not in by_id]
    historique_projects, _ = build_historique_par_projet(descriptors, beads + closed, promotion_results,
                                                         pack_reads=pack_reads)
    value = to_value(
        projects,
        sans_projet,
        historique={p.project_id: p.chantiers for p in historique_projects},
        hors_chantier=hors_chantier_par_projet(beads),
    )
    value["roadmap_chantiers"] = roadmap_chantiers(targeting, beads)
    # spec .47: a closed chantier with a ticket not merged, for the health zone.
    value["anomalies"] = convoy_closed_with_unmerged_child(beads)
    return value


def read_targeting_beads(bd_bin="bd", timeout=20):
    """Every bead -- open or closed -- that targets a Roadmap Step: the
    Specs, which carry it as ``planning_run_target``."""
    return [bead for bead in read_beads_json(["list", "--all", "--limit", "0", "--has-metadata-key", TARGET_KEY],
                                             bd_bin=bd_bin, timeout=timeout)
            if isinstance(bead, dict) and bead.get("id")]


def roadmap_chantiers(targeting, beads):
    """``{project_id: {step id: [{"id", "closed", "merged"}]}}``: for each
    Spec that targets a Roadmap Step, its chantier -- the Spec and the
    convoys published from it (``gc.spec_id``). It is closed when the Spec
    and every such convoy are closed; merged when one of those convoys
    records the proof of its merge (the promotion of the D01 flow, read
    by :func:`convoy_state.outcome_records_of`). The project is the Spec's,
    else its convoy's. E, af-8rbceu: what the roadmap of a project is held
    to (:func:`cockpit.projects.roadmap.roadmap_rows`)."""
    convoys_by_spec = {}
    for bead in beads:
        spec_id = (bead.get("metadata") or {}).get(SPEC_KEY)
        if bead.get("issue_type") == CONVOY_ISSUE_TYPE and spec_id:
            convoys_by_spec.setdefault(spec_id, []).append(bead)
    out = {}
    for spec in targeting:
        metadata = spec.get("metadata") or {}
        target = metadata.get(TARGET_KEY)
        convoys = convoys_by_spec.get(spec["id"], [])
        project = metadata.get(PROJECT_KEY) or next(
            ((c.get("metadata") or {}).get(PROJECT_KEY) for c in convoys if (c.get("metadata") or {}).get(PROJECT_KEY)),
            None)
        if not isinstance(target, str) or not target or not project:
            continue
        merged = False
        for convoy in convoys:
            promotion = (outcome_records_of(convoy) or {}).get("promotion")
            merged = merged or (isinstance(promotion, dict) and "unruled" not in promotion)
        closed = spec.get("status") == "closed" and all(c.get("status") == "closed" for c in convoys)
        out.setdefault(project, {}).setdefault(target, []).append({"id": spec["id"], "closed": closed, "merged": merged})
    return out


def read_dossier_pages(beads):
    """The rubrics of the dossier page of each convoy that records an
    Evidence Pack (its folder, :func:`cockpit.projects.outcome.pack_folder`):
    ``{convoy_id: rubrics, or None when the page cannot be read}`` (A1,
    :func:`cockpit.projects.outcome.read_pack_sections`)."""
    pages = {}
    for bead in beads:
        folder = pack_folder(bead)
        if folder is not None:
            pages[bead["id"]] = read_pack_sections(folder)
    return pages


def to_value(projects, sans_projet, historique=None, hors_chantier=None):
    """``historique`` / ``hors_chantier``: per project id, what only the
    project page shows (spec .46, .49)."""
    return {
        "projects": [asdict(project) for project in projects],
        "sans_projet": [asdict(chantier) for chantier in sans_projet],
        "historique": {pid: [asdict(c) for c in rows] for pid, rows in (historique or {}).items()},
        "hors_chantier": {pid: [asdict(i) for i in rows] for pid, rows in (hors_chantier or {}).items()},
    }


def from_value(value):
    """``(projects, sans_projet)`` back as model objects for the renderer."""
    projects = []
    for raw in (value or {}).get("projects") or []:
        raw = dict(raw)
        step = raw.get("roadmap_step")
        raw["roadmap_step"] = RoadmapStep(**step) if step else None
        raw["chantiers"] = [Chantier(**chantier) for chantier in raw.get("chantiers") or []]
        projects.append(Project(**raw))
    sans_projet = [Chantier(**chantier) for chantier in (value or {}).get("sans_projet") or []]
    return projects, sans_projet


def project_page_data(value, project_id):
    """``(project, hors_chantier, historique)`` for one project's page, or
    ``None`` when no declared project has this id. ``historique`` is a
    :class:`~cockpit.projects.model.Project` holding only the terminé and
    abandonné chantiers, the shape
    :func:`cockpit.ui.projects.page.render_historique_section` takes."""
    projects, _ = from_value(value)
    project = next((p for p in projects if p.project_id == project_id), None)
    if project is None:
        return None
    hors_chantier = [HorsChantierItem(**raw) for raw in (value.get("hors_chantier") or {}).get(project_id) or []]
    historique = Project(
        project_id=project.project_id,
        display_name=project.display_name,
        chantiers=[Chantier(**raw) for raw in (value.get("historique") or {}).get(project_id) or []],
    )
    return project, hors_chantier, historique
