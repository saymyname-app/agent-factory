"""Pure computation of a Chantier's stage from Beads (spec af-oohx2x
"Calcul d'étape des chantiers" / "Étapes d'un chantier"; CONTEXT.md:
Chantier). No I/O -- every function here takes an already-read bead list
(:mod:`cockpit.projects.beads`) and returns
:class:`cockpit.projects.model.Chantier` rows.

Project key resolution (spec .12, T05): a chantier's project is whichever
bead defines its current stage -- the map for Cadrage, the Spec for Spec,
the draft graph bead for Graphe, the convoy for Livraison/Livré -- reading
``metadata["gc.project_id"]`` directly. ``None`` (no key at all) is passed
through unresolved; the caller (:mod:`cockpit.projects.builder`) is the one
that turns that into "Sans projet" plus a counted producer defect, because
only it holds the shared :class:`~cockpit.requests.defects.DefectCounter`.
"""
from cockpit.projects.model import CADRAGE, GRAPHE, LIVRAISON, LIVRE, SPEC, Chantier

MAP_LABEL = "wayfinder:map"
DRAFT_GRAPH_LABEL = "ticket-graph-draft"
APPROVED_GRAPH_LABEL = "approved-ticket-graph"
DELIVERY_LABEL = "delivery-plane"
CONVOY_ISSUE_TYPE = "convoy"
PROJECT_KEY = "gc.project_id"
GRAPH_DIGEST_KEY = "gc.graph_digest"
DELIVERY_STATUS_KEY = "gc.delivery_status"
DELIVERY_STATUS_WAITING = "waiting"
DRAFT_SPEC = "DRAFT_SPEC"
APPROVED_SPEC = "APPROVED_SPEC"


def _project_of(bead):
    return (bead.get("metadata") or {}).get(PROJECT_KEY)


def _title(bead):
    return bead.get("title") or bead.get("id") or ""


def cadrage_chantiers(beads, children_by_map_id=None):
    """Étape 1 -- "carte wayfinder:map ouverte (détail : décisions x/y)".
    ``children_by_map_id``: ``{map_id: [decision beads]}``, from
    :func:`cockpit.projects.beads.read_map_children`; a map with no entry
    (read not yet attempted, or it has no children) shows 0/0."""
    children_by_map_id = children_by_map_id or {}
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        labels = bead.get("labels") or []
        if MAP_LABEL not in labels or bead.get("status") == "closed":
            continue
        children = children_by_map_id.get(bead.get("id"), [])
        total = len(children)
        closed = sum(1 for c in children if isinstance(c, dict) and c.get("status") == "closed")
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=CADRAGE,
                detail="Cadrage : %d/%d décisions" % (closed, total),
            )
        )
    return out


def spec_chantiers(beads):
    """Étape 2 -- "bead Spec en DRAFT_SPEC"."""
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        metadata = bead.get("metadata") or {}
        if metadata.get("spec_state") != DRAFT_SPEC:
            continue
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=SPEC,
                detail="Spec prête : à approuver",
            )
        )
    return out


def graphe_chantiers(beads):
    """Étape 3 -- "Spec APPROVED_SPEC, convoi pas encore publié": a draft
    graph bead (``ticket-graph-draft`` label, no ``approved-ticket-graph``
    label yet) whose source Spec is already approved."""
    by_id = {b.get("id"): b for b in beads or [] if isinstance(b, dict) and b.get("id")}
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        labels = bead.get("labels") or []
        if DRAFT_GRAPH_LABEL not in labels or APPROVED_GRAPH_LABEL in labels:
            continue
        metadata = bead.get("metadata") or {}
        spec_id = metadata.get("spec_id")
        spec_bead = by_id.get(spec_id) if spec_id else None
        if spec_bead is None or (spec_bead.get("metadata") or {}).get("spec_state") != APPROVED_SPEC:
            continue
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=GRAPHE,
                detail="Graphe de tickets : à approuver",
            )
        )
    return out


def _is_delivery_ticket(bead, digest):
    if not isinstance(bead, dict):
        return False
    if bead.get("issue_type") == CONVOY_ISSUE_TYPE:
        return False
    if DELIVERY_LABEL not in (bead.get("labels") or []):
        return False
    return (bead.get("metadata") or {}).get(GRAPH_DIGEST_KEY) == digest


def convoy_chantiers(beads):
    """Étapes 4 et 5 -- "convoi publié ouvert (mergés x/y, en cours, en
    PR)" / "convoi fermé, tous les enfants mergés". ``beads`` must include
    closed beads (:func:`cockpit.projects.beads.read_convoy_beads`) or a
    Livré convoy and any already-merged ticket under an open one are
    invisible."""
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict) or bead.get("issue_type") != CONVOY_ISSUE_TYPE:
            continue
        digest = (bead.get("metadata") or {}).get(GRAPH_DIGEST_KEY)
        tickets = [b for b in beads if _is_delivery_ticket(b, digest)]
        total = len(tickets)
        merged = sum(1 for t in tickets if t.get("status") == "closed")
        en_pr = sum(
            1
            for t in tickets
            if t.get("status") == "in_progress"
            and (t.get("metadata") or {}).get(DELIVERY_STATUS_KEY) == DELIVERY_STATUS_WAITING
        )
        en_cours = sum(1 for t in tickets if t.get("status") == "in_progress") - en_pr

        if bead.get("status") == "closed":
            detail = "Livré : %d/%d tickets mergés" % (merged, total)
            stage = LIVRE
        else:
            detail = "%d/%d tickets mergés · %d en cours · %d en PR" % (
                merged, total, en_cours, en_pr,
            )
            stage = LIVRAISON
        out.append(
            Chantier(
                id=bead.get("id") or "",
                titre=_title(bead),
                projet=_project_of(bead),
                stage=stage,
                detail=detail,
            )
        )
    return out


def build_chantiers(beads, children_by_map_id=None):
    """Every chantier at every stage this ticket computes (Cadrage à
    Livré), in no particular order -- :mod:`cockpit.projects.builder`
    groups and sorts them per project."""
    return (
        cadrage_chantiers(beads, children_by_map_id)
        + spec_chantiers(beads)
        + graphe_chantiers(beads)
        + convoy_chantiers(beads)
    )
