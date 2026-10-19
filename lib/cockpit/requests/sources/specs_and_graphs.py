"""Spec ou graphe à approuver -> À faire (T15, af-icxjc4 — Spec af-oohx2x
§"Demandes opérateur : types, niveaux, sortie": "Spec ou graphe à
approuver | À faire | priorité 0").

Source: the same raw beads list :mod:`cockpit.requests.builder` already
reads. Two bead shapes match, both drawn from the tools that own these
states (``docs/SPEC_APPROVE.md``, ``bin/spec-approve``,
``bin/ticket-graph-publish``):

  * a **Spec bead**: ``metadata.spec_state == "DRAFT_SPEC"``. It stops
    matching the moment ``spec-approve bd-approve`` sets
    ``spec_state=APPROVED_SPEC`` — exit is at-source, same rule as
    escalations and proposals (spec .15).
  * a **Ticket Graph Draft bead**: label ``ticket-graph-draft`` present,
    no approval recorded, and not the convoy itself. Approval is the
    metadata ``bd-approve`` writes (``approved_by``, ``approved_evidence``,
    ``approved_digest``), the same rule ``ticket-graph-publish`` reads;
    ``ticket-graph-publish`` puts ``approved-ticket-graph`` on the tickets
    it creates, never on the draft bead, so the label alone left every
    approved and published draft in the inbox (19/10/2026: 11 of them).
    A published convoy keeps the draft label; it is not a draft either.

This is a fixed-phrase type (spec: "des phrases fixes dans le code pour
chaque type d'événement machine") — the cockpit invents nothing beyond
the bead's own title, and the request never offers an "Approuver" action
(spec .37, "jamais l'approbation dans le cockpit"): its one option is
always a prompt to copy, pointing at the bead via ``lien``.
"""
from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, OperatorRequest
from cockpit.requests.sources._util import copy_prompt_option, parse_iso

TYPE_SPEC_A_APPROUVER = "spec_a_approuver"
TYPE_GRAPHE_A_APPROUVER = "graphe_a_approuver"

DRAFT_GRAPH_LABEL = "ticket-graph-draft"
APPROVED_GRAPH_LABEL = "approved-ticket-graph"


def _is_draft_spec(bead):
    metadata = bead.get("metadata") or {}
    return metadata.get("spec_state") == "DRAFT_SPEC"


APPROVAL_KEYS = ("approved_by", "approved_evidence", "approved_digest")


def _is_draft_graph(bead):
    labels = bead.get("labels") or []
    if DRAFT_GRAPH_LABEL not in labels or APPROVED_GRAPH_LABEL in labels:
        return False
    if bead.get("issue_type") == "convoy":
        return False
    metadata = bead.get("metadata") or {}
    return not any(str(metadata.get(key) or "").strip() for key in APPROVAL_KEYS)


def _request_for(bead, req_type, quoi, pourquoi, prompt_label, verifie_a):
    bead_id = bead.get("id") or ""
    metadata = bead.get("metadata") or {}
    return OperatorRequest(
        id=bead_id,
        type=req_type,
        niveau=A_FAIRE,
        quoi=quoi,
        pourquoi=pourquoi,
        que_faire=copy_prompt_option(prompt_label),
        projet=metadata.get("gc.project_id") or DEFAULT_PROJECT,
        depuis_quand=parse_iso(bead.get("created_at")),
        verifie_a=verifie_a,
        lien=bead_id,
    )


def build_specs_and_graphs_requests(beads, verifie_a=None):
    """``beads``: the raw list the beads source last read. Returns one
    request per matching Spec or Ticket Graph Draft bead, already sorted
    (Urgent first, then oldest first — here every request is À faire, so
    this is just oldest first)."""
    requests = []
    for bead in beads or []:
        if not isinstance(bead, dict):
            continue
        title = bead.get("title") or bead.get("id") or ""
        if _is_draft_spec(bead):
            requests.append(
                _request_for(
                    bead,
                    TYPE_SPEC_A_APPROUVER,
                    "Une Spec attend ton approbation : %s" % title,
                    "Seul toi peux approuver une Spec — décision de ton niveau.",
                    "Copier un prompt pour approuver cette Spec avec un agent",
                    verifie_a,
                )
            )
        elif _is_draft_graph(bead):
            requests.append(
                _request_for(
                    bead,
                    TYPE_GRAPHE_A_APPROUVER,
                    "Un graphe de tickets attend ton approbation : %s" % title,
                    "Seul toi peux approuver ou publier un graphe — décision de ton niveau.",
                    "Copier un prompt pour approuver ce graphe avec un agent",
                    verifie_a,
                )
            )
    requests.sort(key=lambda r: r.sort_key())
    return requests
