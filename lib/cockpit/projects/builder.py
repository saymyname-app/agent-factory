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
from cockpit.projects.stage import build_chantiers, build_historique

SANS_PROJET_DEFECT = "chantier %s sans clé projet déclarée"


def _new_projects(descriptors, roadmap_reads=None, ecart_reads=None):
    roadmap_reads = roadmap_reads or {}
    ecart_reads = ecart_reads or {}
    projects_by_id = {}
    projects = []
    for descriptor in descriptors:
        project = Project(project_id=descriptor["project_id"], display_name=descriptor["display_name"])
        read = roadmap_reads.get(descriptor["project_id"])
        if read:
            project.roadmap_step = read.get("step")
            project.roadmap_read_at = read.get("read_at")
            project.roadmap_unknown_since = read.get("unknown_since")
        project.ecart_commits_par_rig = dict(ecart_reads.get(descriptor["project_id"]) or {})
        projects_by_id[descriptor["project_id"]] = project
        projects.append(project)
    return projects, projects_by_id


def _place(chantier, descriptors, projects_by_id):
    """The project a chantier belongs to: its own project key, else the
    project declaring the rig its tickets are dispatched to (spec
    "Données de projet"); ``None`` means "Sans projet"."""
    if chantier.projet:
        matches = [d for d in descriptors if d["project_id"] == chantier.projet]
    else:
        matches = [d for d in descriptors if chantier.rig and chantier.rig in (d.get("rigs") or [])]
    if not matches:
        return None
    descriptor = matches[0]
    chantier.projet = descriptor["project_id"]
    if not descriptor.get("promotion_branch"):
        # spec .41: no promotion branch declared -- Promu never applies,
        # at any stage, so the stepper never shows it.
        chantier.promu_masque = True
    return projects_by_id[chantier.projet]


def build_projects(
    descriptors, beads, children_by_map_id=None, roadmap_reads=None, promotion_results=None, defects=None,
):
    """``descriptors``: :func:`cockpit.projects.descriptors.load_descriptors`
    output. ``beads``: the merged open + gc.graph_digest bead list. ``roadmap_reads``:
    ``{project_id: {"step": RoadmapStep|None, "read_at": epoch|None,
    "unknown_since": epoch|None}}``, one entry per project whose roadmap was
    attempted -- a missing entry means "never attempted", rendered the same
    as unknown with no age. ``promotion_results`` (T20): ``{convoy_id:
    {"masque": bool, "promu": True|False|None}}``, threaded straight into
    :func:`cockpit.projects.stage.build_chantiers`. ``defects``: an
    optional :class:`cockpit.requests.defects.DefectCounter` for
    §"Sans projet"'s counted producer defect.

    Returns ``(projects, sans_projet)``: ``projects`` is a list of
    :class:`~cockpit.projects.model.Project` in descriptor order;
    ``sans_projet`` is the list of orphan
    :class:`~cockpit.projects.model.Chantier`."""
    projects, projects_by_id = _new_projects(descriptors, roadmap_reads)

    sans_projet = []
    for chantier in build_chantiers(beads, children_by_map_id, promotion_results):
        project = _place(chantier, descriptors, projects_by_id)
        if project is None:
            sans_projet.append(chantier)
            if defects is not None:
                defects.record_once(chantier.id, SANS_PROJET_DEFECT % chantier.id)
        else:
            project.chantiers.append(chantier)

    return projects, sans_projet


def build_historique_par_projet(descriptors, beads, promotion_results=None, defects=None):
    """The historique counterpart of :func:`build_projects` (spec .46):
    terminé convoy chantiers plus abandonné cadrage/spec/graphe ones,
    grouped the same way. Returns ``(projects, sans_projet)`` with each
    project's ``chantiers`` holding only its historique rows -- never
    mixed with :func:`build_projects`' active ones, so a caller rendering
    "l'actif" never has to filter ``termine``/``abandonne`` itself."""
    projects, projects_by_id = _new_projects(descriptors)

    sans_projet = []
    for chantier in build_historique(beads, promotion_results):
        project = _place(chantier, descriptors, projects_by_id)
        if project is None:
            sans_projet.append(chantier)
            if defects is not None:
                defects.record_once(chantier.id, SANS_PROJET_DEFECT % chantier.id)
        else:
            project.chantiers.append(chantier)

    return projects, sans_projet
