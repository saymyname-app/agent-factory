"""Signal de type inconnu (Spec af-fgcw0d user story 76: "qu'un signal de
type inconnu s'affiche « Signal non reconnu venant de … » avec son texte
brut en détails, afin que le cockpit n'invente jamais de sens").

    unknown_signals_of(beads) -> [UnknownSignal]

A signal is an open bead a producer of the Factory filed (``gc.source``)
that is none of the shapes the cockpit reads, and that paged no one. It is
information, not an Operator Request (GLOSSARY.md: an Operator Request "is
not information"): Pour moi shows it apart from its requests, with no
level, no gesture and no count (:mod:`cockpit.ui.home.overview`). The
cockpit never tries to interpret its raw text (its title and its
description, as written): it is shown verbatim, only in the folded
details. A signal exits the moment its bead is closed or no longer read.
"""
import dataclasses

from cockpit.requests.proposals import is_proposal
from cockpit.requests.sources._util import parse_iso
from cockpit.requests.sources.paused_sessions import LOOP_GUARD
from cockpit.text.validate import speaks_plainly

SOURCE_KEY = "gc.source"
# The producers whose beads the cockpit reads into a request of its own.
KNOWN_SOURCES = frozenset({LOOP_GUARD})
# What makes a bead one of the shapes the cockpit already reads, or one the
# Mayor was paged about first (spec af-oohx2x .9: never the operator's until
# promoted): a question to the operator, a page of the Mayor.
ROUTED_KEYS = ("gc.needs_benjamin", "gc.escalation_mayor_paged_at")


@dataclasses.dataclass(frozen=True)
class UnknownSignal:
    """``titre``: the fixed phrase « Signal non reconnu venant de … », the
    only main text; ``source``, ``texte_brut``: as the producer wrote them,
    for the folded details; ``depuis_quand``: epoch seconds or ``None``."""
    id: str
    titre: str
    source: str
    texte_brut: str
    depuis_quand: float = None


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


def unknown_signals_of(beads):
    """The signals of the tracker the cockpit has no reading for: each open
    bead whose producer (``gc.source``) is none of :data:`KNOWN_SOURCES`,
    that is no proposal and that neither asks the operator nor paged the
    Mayor; oldest first."""
    signals = []
    for bead in beads or ():
        if not isinstance(bead, dict) or bead.get("status") == "closed" or is_proposal(bead):
            continue
        metadata = bead.get("metadata") or {}
        source = metadata.get(SOURCE_KEY)
        if not isinstance(source, str) or not source or source in KNOWN_SOURCES:
            continue
        if any(metadata.get(key) for key in ROUTED_KEYS):
            continue
        signals.append(UnknownSignal(
            id=bead.get("id") or "",
            titre=_coming_from(source),
            source=source,
            texte_brut="\n\n".join(text for text in (bead.get("title"), bead.get("description"))
                                   if isinstance(text, str) and text),
            depuis_quand=parse_iso(bead.get("created_at")),
        ))
    signals.sort(key=lambda signal: (signal.depuis_quand is None, signal.depuis_quand or 0, signal.id))
    return signals
