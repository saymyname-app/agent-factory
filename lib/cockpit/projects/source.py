"""The "Projets" zone's one read (spec af-oohx2x §"Suivre les projets",
§"Modèle de lecture"): the declared projects and their chantiers, computed
from Beads on this source's own rhythm and held in the read model like any
other value — the page never reads Beads itself.

What is stored is the computed view as plain data (so ``/api/status`` and
``/api/projects`` can serialise it), not the beads it was computed from.
"""
from dataclasses import asdict

from cockpit.core.beads_source import read_beads_json
from cockpit.projects.beads import read_convoy_beads, read_map_children
from cockpit.projects.builder import build_projects
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.model import Chantier, Project, RoadmapStep
from cockpit.projects.stage import MAP_LABEL


def read_projects(descriptors_dir, bd_bin="bd", timeout=20):
    """One complete read. Raises on any failed ``bd`` call: a partial view
    would show a project with chantiers missing as if it were whole."""
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
    projects, sans_projet = build_projects(descriptors, beads, children_by_map_id)
    return to_value(projects, sans_projet)


def to_value(projects, sans_projet):
    return {
        "projects": [asdict(project) for project in projects],
        "sans_projet": [asdict(chantier) for chantier in sans_projet],
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
