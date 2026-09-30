"""Rituel dû -> Quand tu veux (T15, af-icxjc4 — Spec af-oohx2x §"Demandes
opérateur"). "lu par la commande de statut de chaque descripteur": the
wiring ticket polls each project's ritual status command (``bin/
rituals-status``, ``docs/rituals.toml``) at the rituals Validity window
(1 h) and hands this module the parsed result — never the raw process
output.

Input shape (one dict per ritual, whatever the status command reports):
``{"id": str, "titre": str, "due": bool, "depuis_quand": iso str or
None, "projet": str or None}``. A ritual is a request exactly while
``due`` is true — exit is at-source: the next poll after the ritual is
performed drops ``due`` to false and the request stops appearing (spec
.15), no cockpit-side bookkeeping involved. Never pushed (spec: "jamais"
for the Quand tu veux row).
"""
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX
from cockpit.requests.sources._util import parse_iso

TYPE_RITUEL_DU = "rituel_du"


def build_ritual_requests(rituals, verifie_a=None):
    requests = []
    for ritual in rituals or []:
        if not isinstance(ritual, dict) or not ritual.get("due"):
            continue
        ritual_id = ritual.get("id") or ""
        titre = ritual.get("titre") or ritual_id
        requests.append(
            OperatorRequest(
                id=ritual_id,
                type=TYPE_RITUEL_DU,
                niveau=QUAND_TU_VEUX,
                quoi="Un rituel est dû : %s" % titre,
                pourquoi="Ce rituel attend d'être fait, sans urgence.",
                que_faire=[
                    {
                        "lettre": "a",
                        "option": "Voir le rituel",
                        "consequence": "Rien ne change tant que tu ne l'as pas fait.",
                        "recommande": False,
                        "raison": "",
                    }
                ],
                projet=ritual.get("projet") or DEFAULT_PROJECT,
                depuis_quand=parse_iso(ritual.get("depuis_quand")),
                verifie_a=verifie_a,
                lien=ritual_id,
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    return requests
