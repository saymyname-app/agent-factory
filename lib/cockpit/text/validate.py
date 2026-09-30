"""Pure-code control of the cockpit's main text (spec af-oohx2x,
"Compréhensible sans IA" and ticket T12 acceptance criteria).

Run twice: in a test (so a violation never reaches CI green) and again at
runtime on every value a producer wrote, because a test cannot see what an
agent writes after the ticket ships (spec .78 exists for the door side —
this is the cockpit's own, independent check on display).

What it refuses:
  * an identifier (af-xxxxx, #300 — spec .73) — a human reading the
    Operator Language screen must never need to decode one;
  * an internal term outside the Cockpit Lexicon (CONTEXT.md) — the fixed
    list below is drawn from the "_Avoid_" lines of the terms a cockpit
    screen is built from (bead, convoy/convoi, order, molecule, wisp, rig,
    Mayor/Maire — spec .73, .74);
  * a line over 140 characters (spec .10, .73: readable on an iPhone
    without unfolding);
  * an empty/missing value.

A failure never raises past the caller: :func:`violations` always returns a
(possibly empty) list of French reasons, because the runtime path (spec
.78: "échec à l'exécution = repli + défaut producteur compté") must fall
back to a fixed phrase, never crash the page.
"""
import re

MAX_LINE_LENGTH = 140

_IDENTIFIER_PATTERNS = (
    re.compile(r"\baf-[a-z0-9]+(?:\.[a-z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\b[a-z]{1,4}-[a-z0-9]{3,20}\b", re.IGNORECASE),
    re.compile(r"#\d+\b"),
)

# CONTEXT.md's Cockpit Lexicon is the only place domain words may be added
# ("growing it is a pull request on this file"); this is not a second
# glossary, only the small set of internal English/organisational terms a
# screen must never show (spec .73, .74), taken from CONTEXT.md's own
# "_Avoid_" lines for the canonical terms the cockpit is built from.
BANNED_INTERNAL_TERMS = frozenset(
    {
        "bead",
        "beads",
        "convoy",
        "convoi",
        "order",
        "orders",
        "molecule",
        "wisp",
        "rig",
        "rigs",
        "mayor",
        "maire",
        "gas city",
        "orchestrator",
        "harness",
        "control plane",
    }
)


def violations(label, value, max_length=MAX_LINE_LENGTH):
    """Reasons (French, possibly empty) ``value`` fails the main-text
    control for a field displayed as ``label`` (e.g. "quoi")."""
    reasons = []
    if value is None or (isinstance(value, str) and value.strip() == ""):
        reasons.append("champ « %s » manquant" % label)
        return reasons
    if not isinstance(value, str):
        reasons.append("champ « %s » illisible" % label)
        return reasons
    if "\n" in value or "\r" in value:
        reasons.append("champ « %s » doit tenir sur une seule ligne" % label)
    if len(value) > max_length:
        reasons.append(
            "champ « %s » dépasse %d caractères" % (label, max_length)
        )
    for pattern in _IDENTIFIER_PATTERNS:
        if pattern.search(value):
            reasons.append("champ « %s » contient un identifiant" % label)
            break
    lowered = value.lower()
    for term in BANNED_INTERNAL_TERMS:
        if re.search(r"\b%s\b" % re.escape(term), lowered):
            reasons.append(
                "champ « %s » contient un terme interne hors lexique (« %s »)"
                % (label, term)
            )
            break
    return reasons


def is_valid(label, value, max_length=MAX_LINE_LENGTH):
    return not violations(label, value, max_length=max_length)
