"""Signal de type inconnu -> Quand tu veux (T15, af-icxjc4 — Spec
af-oohx2x §"Demandes opérateur" and .76: "qu'un signal de type inconnu
s'affiche « Signal non reconnu venant de … » avec son texte brut en
détails, afin que le cockpit n'invente jamais de sens").

Input: ``signals``, one dict per unrecognised machine event a source
handed the cockpit and that matched none of its known shapes —
``{"id": str, "source": str, "texte_brut": str, "depuis_quand": iso str
or None}`` -- read from the tracker by :func:`unknown_signals_of` (B,
af-4uzgzm): an open bead a producer of the Factory filed (``gc.source``)
that is none of the shapes the cockpit reads, and that paged no one. The cockpit never tries to interpret ``texte_brut``: it is
shown verbatim, only in the folded details, exactly as received. A
signal exits the moment its emitting source stops reporting it (e.g. a
newer read no longer includes that id) — exit at-source, same rule as
every other type here.
"""
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX
from cockpit.requests.proposals import is_proposal
from cockpit.requests.sources._util import parse_iso

TYPE_SIGNAL_INCONNU = "signal_inconnu"
SOURCE_KEY = "gc.source"
# What makes a bead one of the shapes the cockpit already reads, or one the
# Mayor was paged about first (spec af-oohx2x .9: never the operator's until
# promoted): a question to the operator, a page of the Mayor.
ROUTED_KEYS = ("gc.needs_benjamin", "gc.escalation_mayor_paged_at")


def unknown_signals_of(beads, known_sources):
    """The signals of the tracker the cockpit has no reading for: each open
    bead whose producer (``gc.source``) is none of ``known_sources``, that
    is no proposal and that neither asks the operator nor paged the Mayor.
    Its raw text is its title and its description, as written."""
    signals = []
    for bead in beads or ():
        if not isinstance(bead, dict) or bead.get("status") == "closed" or is_proposal(bead):
            continue
        metadata = bead.get("metadata") or {}
        source = metadata.get(SOURCE_KEY)
        if not isinstance(source, str) or not source or source in known_sources:
            continue
        if any(metadata.get(key) for key in ROUTED_KEYS):
            continue
        signals.append({
            "id": bead.get("id") or "",
            "source": source,
            "texte_brut": "\n\n".join(text for text in (bead.get("title"), bead.get("description"))
                                       if isinstance(text, str) and text),
            "depuis_quand": bead.get("created_at"),
        })
    return signals


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
                lien=signal_id,
                texte_brut=signal.get("texte_brut") or "",
            )
        )
    requests.sort(key=lambda r: r.sort_key())
    # ``texte_brut`` is no main field (quoi/pourquoi are the fixed phrases):
    # it is kept apart, for the folded details only.
    return requests
