"""Signal de type inconnu -> Quand tu veux (T15, af-icxjc4 — Spec
af-oohx2x §"Demandes opérateur" and .76: "qu'un signal de type inconnu
s'affiche « Signal non reconnu venant de … » avec son texte brut en
détails, afin que le cockpit n'invente jamais de sens").

Input: ``signals``, one dict per unrecognised machine event a source
handed the cockpit and that matched none of its known shapes —
``{"id": str, "source": str, "texte_brut": str, "depuis_quand": iso str
or None}``. The cockpit never tries to interpret ``texte_brut``: it is
shown verbatim, only in the folded details, exactly as received. A
signal exits the moment its emitting source stops reporting it (e.g. a
newer read no longer includes that id) — exit at-source, same rule as
every other type here.
"""
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX
from cockpit.requests.sources._util import parse_iso

TYPE_SIGNAL_INCONNU = "signal_inconnu"


def build_unknown_signal_requests(signals, verifie_a=None):
    requests = []
    for signal in signals or []:
        if not isinstance(signal, dict):
            continue
        signal_id = signal.get("id") or ""
        source_name = signal.get("source") or "une source inconnue"
        requests.append(
            OperatorRequest(
                id=signal_id,
                type=TYPE_SIGNAL_INCONNU,
                niveau=QUAND_TU_VEUX,
                quoi="Signal non reconnu venant de %s" % source_name,
                pourquoi="Ce signal ne correspond à aucun type connu du cockpit.",
                que_faire=[
                    {
                        "lettre": "a",
                        "option": "Voir le texte brut",
                        "consequence": "Affiche le signal tel que reçu, sans interprétation.",
                        "recommande": False,
                        "raison": "",
                    }
                ],
                projet=DEFAULT_PROJECT,
                depuis_quand=parse_iso(signal.get("depuis_quand")),
                verifie_a=verifie_a,
                lien="",
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    # ``texte_brut`` deliberately does not become part of any
    # OperatorRequest field above (quoi/pourquoi are the fixed phrases) —
    # the raw text belongs only in folded details. Callers that render
    # this list keep the raw text alongside by index/id from ``signals``;
    # returning it here as a request field would tempt a renderer into
    # treating it as trusted display text instead of an opaque blob.
    return requests
