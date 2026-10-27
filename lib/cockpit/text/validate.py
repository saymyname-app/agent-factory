"""Pure-code control of the cockpit's main text (spec af-oohx2x,
"Compréhensible sans IA" and ticket T12 acceptance criteria).

Run twice: in a test (so a violation never reaches CI green) and again at
runtime on every value a producer wrote, because a test cannot see what an
agent writes after the ticket ships (spec .78 exists for the door side —
this is the cockpit's own, independent check on display).

What it refuses:
  * an identifier (af-xxxxx, #300 — spec .73) — a human reading the
    Operator Language screen must never need to decode one;
  * an internal term outside the Cockpit Lexicon (GLOSSARY.md) — the fixed
    list below is drawn from the "_Avoid_" lines of the terms a cockpit
    screen is built from (bead, convoy/convoi, order, molecule, wisp, rig,
    Mayor/Maire — spec .73, .74);
  * a line over 140 characters (spec .10, .73: readable on an iPhone
    without unfolding);
  * a sentence that is not French (spec af-fgcw0d .73: « en français (la
    langue de l'opérateur) »), told by its grammatical words, below;
  * an empty/missing value.

A failure never raises past the caller: :func:`violations` always returns a
(possibly empty) list of French reasons, because the runtime path (spec
.78: "échec à l'exécution = repli + défaut producteur compté") must fall
back to a fixed phrase, never crash the page.

One contract, two sides (2026-10-07): the doors (bin/proposal-door, through
bin/operator-text-check) run :func:`request_violations` before they write a
request, and the inbox (cockpit.requests.builder) runs the same function
before it shows one. Before that, proposal-door only checked presence, one
line and 140 characters, so four proposals written in agent jargon (bead
ids, « bead », « Mayor ») were accepted at the door and then shown as
« incomplète : champ quoi manquant » with every field present
(af-os9sh2, af-vnv59w, af-1ai5e3, af-vws964).
"""
import re

MAX_LINE_LENGTH = 140

_IDENTIFIER_PATTERNS = (
    re.compile(r"\baf-[a-z0-9]+(?:\.[a-z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\b[a-z]{1,4}-[a-z0-9]{3,20}\b", re.IGNORECASE),
    re.compile(r"#\d+\b"),
)

# GLOSSARY.md's Cockpit Lexicon is the only place domain words may be added
# ("growing it is a pull request on this file"); this is not a second
# glossary, only the small set of internal English/organisational terms a
# screen must never show (spec .73, .74), taken from GLOSSARY.md's own
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


# The grammatical words of English and of French: a sentence is told by them,
# not by its vocabulary (« export », « session », « format » are both). A
# field is not French when it holds English grammatical words and fewer
# French ones -- or, on three words or more, English ones and no French one.
# No word of one list is a word of the other language (« a », « on », « an »
# are French too and are left out).
_ENGLISH_WORDS = frozenset((
    "the", "and", "is", "are", "was", "were", "of", "for", "with", "this", "that", "these", "those", "it", "its",
    "be", "been", "not", "should", "would", "will", "has", "have", "had", "please", "from", "by", "which", "what",
    "when", "there", "their", "they", "you", "your", "we", "our", "to", "does", "do", "can", "must", "needs",
    "waiting", "into", "about",
))
_FRENCH_WORDS = frozenset((
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "et", "est", "sont", "pour", "avec", "dans", "sur",
    "ce", "cette", "ces", "qui", "que", "qu", "ne", "n", "pas", "plus", "au", "aux", "en", "il", "elle", "ils",
    "elles", "tu", "ton", "ta", "tes", "je", "j", "nous", "vous", "son", "sa", "ses", "se", "s", "à", "où", "par",
    "mais", "ou", "leur", "leurs", "t", "y", "c", "m",
))
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def speaks_french(value):
    """Whether ``value`` reads as French, as far as its grammatical words
    tell: a text without any (« Session », « x ») is not refused."""
    words = [word.lower() for word in _WORD.findall(value or "")]
    english = sum(1 for word in words if word in _ENGLISH_WORDS)
    french = sum(1 for word in words if word in _FRENCH_WORDS)
    if english == 0:
        return True
    return french > english or (french > 0 and english < 2 and len(words) < 3)


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
    if not speaks_french(value):
        reasons.append("champ « %s » n'est pas en français" % label)
    return reasons


def speaks_plainly(value):
    """Whether ``value`` is French and holds neither an identifier nor an
    internal term (spec .73): what may be shown as main text, whatever its
    length or shape."""
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return speaks_french(value) and not any(pattern.search(value) for pattern in _IDENTIFIER_PATTERNS) and not any(
        re.search(r"\b%s\b" % re.escape(term), lowered) for term in BANNED_INTERNAL_TERMS)


def is_valid(label, value, max_length=MAX_LINE_LENGTH):
    return not violations(label, value, max_length=max_length)


# The que_faire side of the same contract: what a door validates per option
# is exactly what the inbox refuses to show (spec .12, .13: every option
# with its consequence, at most one « Recommandé » with its raison).
QUE_FAIRE_LABEL = "que faire"
RAISON_LABEL = "raison de la recommandation"


def option_label(index):
    return "option %d" % (index + 1)


def consequence_label(index):
    return "conséquence de l'option %d" % (index + 1)


def que_faire_violations(options, max_length=MAX_LINE_LENGTH):
    """Reasons (French, possibly empty) an already-parsed ``que_faire``
    list fails: not a non-empty list, an item that is not an object, an
    option or consequence failing :func:`violations`, more than one
    recommended option, a recommended option without a readable raison."""
    if not isinstance(options, list) or not options:
        return ["champ « %s » manquant ou vide" % QUE_FAIRE_LABEL]
    reasons = []
    recommended = 0
    for index, item in enumerate(options):
        if not isinstance(item, dict):
            reasons.append("%s illisible" % option_label(index))
            continue
        reasons.extend(violations(option_label(index), item.get("option"), max_length))
        reasons.extend(violations(consequence_label(index), item.get("consequence"), max_length))
        if bool(item.get("recommande", False)):
            recommended += 1
            reasons.extend(violations(RAISON_LABEL, item.get("raison"), max_length))
    if recommended > 1:
        reasons.append("au plus une option « Recommandé »")
    return reasons


def request_violations(quoi, pourquoi, que_faire, max_length=MAX_LINE_LENGTH):
    """The whole contract for one request: ``{field: reasons}`` for every
    field (``quoi``, ``pourquoi``, ``que_faire``) the inbox would replace by
    its fixed repli; empty when the request displays exactly as written.
    ``que_faire`` is the parsed list (a door has the JSON; the inbox parses
    the metadata string first)."""
    failures = {}
    reasons = violations("quoi", quoi, max_length)
    if reasons:
        failures["quoi"] = reasons
    reasons = violations("pourquoi", pourquoi, max_length)
    if reasons:
        failures["pourquoi"] = reasons
    reasons = que_faire_violations(que_faire, max_length)
    if reasons:
        failures["que_faire"] = reasons
    return failures
