"""Assembles the "Projets" section's data (spec af-oohx2x §"Accueil",
§"Suivre les projets", T19): every declared project, its current Roadmap
Step, and its active chantiers -- plus "Sans projet" for any chantier whose
defining bead carries no project key (spec .50).

Pure function of already-read inputs (descriptors, beads, roadmap reads) --
no I/O of its own, so it is exercised directly by tests; a caller wires
:mod:`cockpit.projects.descriptors`, :mod:`cockpit.projects.beads` and
:mod:`cockpit.projects.roadmap`'s I/O to these parameters.
"""
from cockpit.projects.model import Project
from cockpit.projects.stage import build_chantiers

SANS_PROJET_DEFECT = "chantier %s sans clé projet déclarée"


def build_projects(descriptors, beads, children_by_map_id=None, roadmap_reads=None, defects=None):
    """``descriptors``: :func:`cockpit.projects.descriptors.load_descriptors`
    output. ``beads``: the merged open + gc.graph_digest bead list. ``roadmap_reads``:
    ``{project_id: {"step": RoadmapStep|None, "read_at": epoch|None,
    "unknown_since": epoch|None}}``, one entry per project whose roadmap was
    attempted -- a missing entry means "never attempted", rendered the same
    as unknown with no age. ``defects``: an optional
    :class:`cockpit.requests.defects.DefectCounter` for §"Sans projet"'s
    counted producer defect.

    Returns ``(projects, sans_projet)``: ``projects`` is a list of
    :class:`~cockpit.projects.model.Project` in descriptor order;
    ``sans_projet`` is the list of orphan
    :class:`~cockpit.projects.model.Chantier`."""
    roadmap_reads = roadmap_reads or {}
    projects_by_id = {}
    projects = []
    for descriptor in descriptors:
        project = Project(project_id=descriptor["project_id"], display_name=descriptor["display_name"])
        read = roadmap_reads.get(descriptor["project_id"])
        if read:
            project.roadmap_step = read.get("step")
            project.roadmap_read_at = read.get("read_at")
            project.roadmap_unknown_since = read.get("unknown_since")
        projects_by_id[descriptor["project_id"]] = project
        projects.append(project)

    sans_projet = []
    for chantier in build_chantiers(beads, children_by_map_id):
        project = projects_by_id.get(chantier.projet) if chantier.projet else None
        if project is None:
            sans_projet.append(chantier)
            if defects is not None:
                defects.record_once(chantier.id, SANS_PROJET_DEFECT % chantier.id)
        else:
            project.chantiers.append(chantier)

    return projects, sans_projet
