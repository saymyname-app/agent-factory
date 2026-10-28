"""Signal de type inconnu -> Quand tu veux (T15, af-icxjc4 — Spec
af-oohx2x §"Demandes opérateur" and .76: "qu'un signal de type inconnu
s'affiche « Signal non reconnu venant de … » avec son texte brut en
détails, afin que le cockpit n'invente jamais de sens").

Input: ``signals``, one dict per unrecognised machine event a source
handed the cockpit and that matched none of its known shapes —
``{"id": str, "source": str, "texte_brut": str, "depuis_quand": iso str
or None}``. No source of Pour moi calls it: a bead of a producer the
cockpit has no reading for is information, not an Operator Request
(GLOSSARY.md); the journal keeps its place (user story 76,
:mod:`cockpit.ui.journal.panorama`). The cockpit never tries to interpret ``texte_brut``: it is
shown verbatim, only in the folded details, exactly as received. A
signal exits the moment its emitting source stops reporting it (e.g. a
newer read no longer includes that id) — exit at-source, same rule as
every other type here.
"""
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX
from cockpit.requests.sources._util import parse_iso
from cockpit.text.validate import speaks_plainly

TYPE_SIGNAL_INCONNU = "signal_inconnu"


def _coming_from(source):
    """« Signal non reconnu venant de … » (spec .76) -- the name of its
    producer only when it may be shown as main text (spec .73: it is
    written by a producer, never checked, and may read as an identifier or
    an internal term); else it is named in the details only."""
    if not source:
        return "Signal non reconnu venant d’une source inconnue"
    if speaks_plainly(source):
        return "Signal non reconnu venant de %s" % source
    return "Signal non reconnu venant d’une source nommée dans les détails"


def build_unknown_signal_requests(signals, verifie_a=None):
    requests = []
    for signal in signals or []:
        if not isinstance(signal, dict):
            continue
        signal_id = signal.get("id") or ""
        source = signal.get("source") or ""
        requests.append(
            OperatorRequest(
                id=signal_id,
                type=TYPE_SIGNAL_INCONNU,
                niveau=QUAND_TU_VEUX,
                quoi=_coming_from(source),
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
                lien=signal_id,
                texte_brut=signal.get("texte_brut") or "",
                precisions="Source : %s" % source if source else "",
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    # ``texte_brut`` is no main field (quoi/pourquoi are the fixed phrases):
    # it is kept apart, for the folded details only.
    return requests
