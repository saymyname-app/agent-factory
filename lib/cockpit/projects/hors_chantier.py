"""Travail hors chantier (spec af-oohx2x §"Étapes d'un chantier": "Le
travail hors chantier (bugs, propositions, correctifs directs) n'a pas
d'étape ; il apparaît dans « Ce qui t'attend » ou sur la page projet.",
T22, af-9tfjsc). Pure code: reads the same already-read bead list
:mod:`cockpit.projects.stage` consumes and returns rows with no
stage/stepper -- the page projet's own section for this (T22,
:mod:`cockpit.ui.projects.project_page`), distinct from "Ce qui t'attend"
(:mod:`cockpit.requests.builder`), which is the other place the same spec
line names for the same beads.

A bead qualifies when it is open, carries a project key
(``gc.project_id``), and is NOT chantier-defining: not a ``wayfinder:map``
card, not a bead with ``spec_state`` metadata (a Spec), not a
``ticket-graph-draft``/``approved-ticket-graph`` bead, not a convoy, and
not a delivery ticket tracked by one (``delivery-plane`` label) -- those
already appear inside their own chantier (:mod:`cockpit.projects.stage`),
never duplicated here.

Three recognised kinds, the spec's own list: un bug (``issue_type ==
"bug"``), une proposition (the ``proposal`` label proposal-door already
uses -- same literal as :data:`cockpit.requests.builder.PROPOSAL_LABEL`),
un correctif direct (the ``correctif-direct`` label, this ticket's own
convention since no other producer sets one yet). A qualifying bead of
none of the three is left out here -- it is not this ticket's job to
invent a fourth kind; it stays reachable through "Ce qui t'attend" or
"Sans projet" via its own existing path, never silently lost from the
cockpit as a whole.
"""
from dataclasses import dataclass

from cockpit.projects.stage import (
    APPROVED_GRAPH_LABEL,
    CONVOY_ISSUE_TYPE,
    DELIVERY_LABEL,
    DRAFT_GRAPH_LABEL,
    MAP_LABEL,
    PROJECT_KEY,
)

BUG_ISSUE_TYPE = "bug"
PROPOSAL_LABEL = "proposal"
CORRECTIF_DIRECT_LABEL = "correctif-direct"

KIND_BUG = "Bug"
KIND_PROPOSITION = "Proposition"
KIND_CORRECTIF_DIRECT = "Correctif direct"


@dataclass
class HorsChantierItem:
    """One row of hors-chantier work (spec: "n'a pas d'étape") -- no
    ``stage``/``stage_index`` field at all, unlike
    :class:`cockpit.projects.model.Chantier`, so a renderer can never
    accidentally put one in a stepper."""

    id: str
    titre: str
    projet: str
    kind: str


def _is_chantier_defining(bead):
    labels = bead.get("labels") or []
    if MAP_LABEL in labels or DRAFT_GRAPH_LABEL in labels or APPROVED_GRAPH_LABEL in labels:
        return True
    if "spec_state" in (bead.get("metadata") or {}):
        return True
    if bead.get("issue_type") == CONVOY_ISSUE_TYPE:
        return True
    if DELIVERY_LABEL in labels:
        return True
    return False


def _kind(bead):
    if bead.get("issue_type") == BUG_ISSUE_TYPE:
        return KIND_BUG
    labels = bead.get("labels") or []
    if PROPOSAL_LABEL in labels:
        return KIND_PROPOSITION
    if CORRECTIF_DIRECT_LABEL in labels:
        return KIND_CORRECTIF_DIRECT
    return None


def hors_chantier_items(beads):
    """Every hors-chantier item across every project, in bead order --
    :mod:`cockpit.ui.projects.project_page`'s caller groups by
    ``projet``."""
    out = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        if bead.get("status") == "closed":
            continue
        projet = (bead.get("metadata") or {}).get(PROJECT_KEY)
        if not projet:
            continue
        if _is_chantier_defining(bead):
            continue
        kind = _kind(bead)
        if kind is None:
            continue
        out.append(
            HorsChantierItem(
                id=bead.get("id") or "",
                titre=bead.get("title") or bead.get("id") or "",
                projet=projet,
                kind=kind,
            )
        )
    return out


def hors_chantier_par_projet(beads):
    """``{project_id: [HorsChantierItem, ...]}`` -- the shape
    :func:`cockpit.ui.projects.project_page.render_project_page` wants for
    a single project (``by_projet.get(project.project_id, [])``)."""
    by_projet = {}
    for item in hors_chantier_items(beads):
        by_projet.setdefault(item.projet, []).append(item)
    return by_projet
