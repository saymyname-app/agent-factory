"""The "Projets" zone's one read (spec af-oohx2x §"Suivre les projets",
§"Modèle de lecture"): the declared projects and their chantiers, computed
from Beads on this source's own rhythm and held in the read model like any
other value — the page never reads Beads itself.

What is stored is the computed view as plain data (so ``/api/status`` and
``/api/projects`` can serialise it), not the beads it was computed from.
"""
import json
from dataclasses import asdict

from cockpit.core.beads_source import read_beads_json
from cockpit.projects.anomalies import convoy_closed_with_unmerged_child
from cockpit.projects.beads import read_convoy_beads, read_map_children
from cockpit.projects.builder import build_historique_par_projet, build_projects
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.hors_chantier import HorsChantierItem, hors_chantier_par_projet
from cockpit.projects.model import Chantier, Project, RoadmapStep
from cockpit.projects.promu import read_promotion_results
from cockpit.projects.result import PACK_KEY, read_pack_sections
from cockpit.projects.stage import MAP_LABEL


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
    historique_projects, _ = build_historique_par_projet(descriptors, beads, promotion_results,
                                                         pack_reads=pack_reads)
    value = to_value(
        projects,
        sans_projet,
        historique={p.project_id: p.chantiers for p in historique_projects},
        hors_chantier=hors_chantier_par_projet(beads),
    )
    # spec .47: a closed chantier with a ticket not merged, for the health zone.
    value["anomalies"] = convoy_closed_with_unmerged_child(beads)
    return value


def read_dossier_pages(beads):
    """The rubrics of the dossier page of each convoy that records one
    (``gc.flow.evidence_pack``, its ``path``): ``{convoy_id: rubrics, or
    None when the page cannot be read}`` (A1,
    :func:`cockpit.projects.result.read_pack_sections`)."""
    pages = {}
    for bead in beads:
        raw = (bead.get("metadata") or {}).get(PACK_KEY)
        if not raw:
            continue
        try:
            record = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            record = None
        path = record.get("path") if isinstance(record, dict) else None
        pages[bead["id"]] = read_pack_sections(path) if isinstance(path, str) and path else None
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
