"""Ticket de carte HITL prêt non lancé -> Quand tu veux (T15, af-icxjc4 —
Spec af-oohx2x §"Demandes opérateur").

Source: the same raw beads list :mod:`cockpit.requests.builder` reads. A
bead matches when it is a HITL card ticket (``gc.ticket_kind ==
"hitl_card"``, the same field ``ticket-graph-publish`` writes for every
ticket), ``status == "open"`` (ready, per Beads' own meaning of open: no
unmet dependency) and carries no assignee yet (not launched — an
assignee means a session already claimed it). It stops matching the
moment any of those three flips (launched, blocked again, or closed) —
exit at-source (spec .15). Never pushed.
"""
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX
from cockpit.requests.sources._util import parse_iso

TYPE_HITL_PRET = "hitl_pret_non_lance"


def _is_ready_unlaunched_hitl(bead):
    metadata = bead.get("metadata") or {}
    if metadata.get("gc.ticket_kind") != "hitl_card":
        return False
    if bead.get("status") != "open":
        return False
    return not bead.get("assignee")


def build_hitl_requests(beads, verifie_a=None):
    requests = []
    for bead in beads or []:
        if not isinstance(bead, dict) or not _is_ready_unlaunched_hitl(bead):
            continue
        bead_id = bead.get("id") or ""
        metadata = bead.get("metadata") or {}
        title = bead.get("title") or bead_id
        requests.append(
            OperatorRequest(
                id=bead_id,
                type=TYPE_HITL_PRET,
                niveau=QUAND_TU_VEUX,
                quoi="Un ticket de carte HITL est prêt, non lancé : %s" % title,
                pourquoi="Ce ticket attend d'être lancé, sans urgence.",
                que_faire=[
                    {
                        "lettre": "a",
                        "option": "Voir le ticket",
                        "consequence": "Rien ne change tant que tu ne l'as pas lancé.",
                        "recommande": False,
                        "raison": "",
                    }
                ],
                projet=metadata.get("gc.project_id") or DEFAULT_PROJECT,
                depuis_quand=parse_iso(bead.get("created_at")),
                verifie_a=verifie_a,
                lien=bead_id,
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    return requests
