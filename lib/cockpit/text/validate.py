"""Pure-code control of the cockpit's main text (spec af-oohx2x,
"Compréhensible sans IA" and ticket T12 acceptance criteria).

Run twice: in a test (so a violation never reaches CI green) and again at
runtime on every value a producer wrote, because a test cannot see what an
agent writes after the ticket ships (spec .78 exists for the door side —
this is the cockpit's own, independent check on display).

What it refuses:
  * an identifier (af-xxxxx, #300 — spec .73) — a human reading the
    Operator Language screen must never need to decode one;
  * an internal term outside the Cockpit Lexicon — the terms GLOSSARY.md
    itself puts out of the cockpit, on its « _Never shown in the cockpit_ »
    line of the Cockpit Lexicon (bead, convoy/convoi, order, molecule,
    wisp, rig, Mayor/Maire — spec .73, .74; af-fgcw0d .79: one vocabulary,
    the glossary's, never a second list here);
  * a line over 140 characters (spec .10, .73: readable on an iPhone
    without unfolding);
  * a sentence that is not in the Operator Language (spec af-fgcw0d .73:
    « en français (la langue de l'opérateur) »), as ``bin/operator-config
    language`` gives it (GLOSSARY.md « Operator Language »), told by its
    grammatical words, below;
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
import functools
import os
import re
import subprocess

MAX_LINE_LENGTH = 140

_IDENTIFIER_PATTERNS = (
    re.compile(r"\baf-[a-z0-9]+(?:\.[a-z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\b[a-z]{1,4}-[a-z0-9]{3,20}\b", re.IGNORECASE),
    re.compile(r"#\d+\b"),
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
# Where the glossary and the door of the operator's settings are; each can
# be pointed elsewhere, as the other doors of the cockpit can.
GLOSSARY_ENV, OPERATOR_CONFIG_ENV = "COCKPIT_GLOSSARY_FILE", "COCKPIT_OPERATOR_CONFIG_BIN"
NEVER_SHOWN = "_Never shown in the cockpit_:"
_LEXICON_ENTRY = "**Cockpit Lexicon**:"


class TextControlError(RuntimeError):
    """The glossary or the Operator Language cannot be read: the text
    control cannot say what a main text may hold."""


@functools.lru_cache(maxsize=None)
def _internal_terms(glossary):
    try:
        with open(glossary, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise TextControlError("glossaire illisible (%s) : %s" % (glossary, exc))
    entry = text.split(_LEXICON_ENTRY, 1)
    lines = entry[1].split("\n\n", 1)[0].splitlines() if len(entry) == 2 else []
    for line in lines:
        if line.startswith(NEVER_SHOWN):
            return frozenset(term.strip().lower() for term in line[len(NEVER_SHOWN):].split(",") if term.strip())
    raise TextControlError("le glossaire %s ne dit pas les termes internes du cockpit (« %s »)" % (glossary, NEVER_SHOWN))


def internal_terms():
    """The internal terms a main text never shows, lowercase, as GLOSSARY.md
    lists them under its Cockpit Lexicon (« _Never shown in the cockpit_ »):
    the glossary is the one vocabulary (af-fgcw0d .79). Raises
    :class:`TextControlError` when it cannot say them."""
    return _internal_terms(os.environ.get(GLOSSARY_ENV) or os.path.join(_REPO_ROOT, "GLOSSARY.md"))


@functools.lru_cache(maxsize=None)
def _operator_language(door):
    try:
        completed = subprocess.run([door, "language"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TextControlError("langue de l’opérateur illisible : %s" % exc)
    language = completed.stdout.strip().lower()
    if completed.returncode != 0 or not language:
        raise TextControlError("langue de l’opérateur illisible : %s" % (completed.stderr.strip() or door))
    return language


def operator_language():
    """The Operator Language, as ``bin/operator-config language`` says it
    (GLOSSARY.md: read through it, never re-parsed here), read once. Raises
    :class:`TextControlError` when it cannot be read."""
    return _operator_language(os.environ.get(OPERATOR_CONFIG_ENV) or os.path.join(_REPO_ROOT, "bin", "operator-config"))


# The grammatical words of the languages a producer may write in: a sentence
# is told by them, not by its vocabulary (« export », « session », « format »
# are several). Words two languages share (« la », « de », « en », « que »)
# tell nothing: only the words of a language that the Operator Language does
# not have count against it.
GRAMMATICAL_WORDS = {
    "fr": frozenset((
        "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "et", "est", "sont", "pour", "avec", "dans",
        "sur", "ce", "cette", "ces", "qui", "que", "qu", "ne", "n", "pas", "plus", "au", "aux", "en", "il", "elle",
        "ils", "elles", "tu", "ton", "ta", "tes", "je", "j", "nous", "vous", "son", "sa", "ses", "se", "s", "à", "où",
        "par", "mais", "ou", "leur", "leurs", "t", "y", "c", "m", "depuis", "sans", "avant", "après", "chez", "été",
        "être", "a", "ont", "était", "très", "aussi", "encore", "déjà", "non", "si", "comme", "tout", "tous",
    )),
    "en": frozenset((
        "the", "and", "is", "are", "was", "were", "of", "for", "with", "this", "that", "these", "those", "it", "its",
        "be", "been", "not", "should", "would", "will", "has", "have", "had", "please", "from", "by", "which", "what",
        "when", "there", "their", "they", "you", "your", "we", "our", "to", "does", "do", "can", "must", "needs",
        "waiting", "into", "about", "a", "an", "on", "in", "at", "before", "after",
    )),
    "es": frozenset((
        "el", "la", "los", "las", "un", "una", "unos", "unas", "del", "al", "de", "y", "es", "son", "está", "están",
        "en", "con", "para", "por", "sin", "sobre", "desde", "hace", "que", "no", "su", "sus", "tu", "tus", "este",
        "esta", "estos", "estas", "pero", "como", "muy", "hay", "fue", "se", "lo", "le", "nos", "ya", "o",
    )),
    "de": frozenset((
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "und", "ist", "sind",
        "war", "nicht", "zu", "mit", "auf", "für", "von", "im", "wird", "werden", "kein", "keine", "dein", "deine",
        "ihr", "ihre", "wir", "sie", "es", "ich", "du", "seit", "noch", "schon", "aber", "oder", "bitte",
    )),
    "it": frozenset((
        "il", "lo", "la", "gli", "le", "un", "uno", "una", "di", "del", "della", "dei", "e", "è", "sono", "in", "con",
        "per", "su", "da", "che", "non", "questo", "questa", "ma", "o", "ancora", "già",
    )),
    "pt": frozenset((
        "o", "a", "os", "as", "um", "uma", "do", "da", "dos", "das", "de", "e", "é", "são", "em", "com", "para",
        "por", "sem", "que", "não", "seu", "sua", "este", "esta", "mas", "ou", "já", "ainda", "no", "na",
    )),
}
# From so many words on, a sentence holds at least one grammatical word of
# its language: none at all is no sentence of it.
_SENTENCE_WORDS = 5
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def speaks(value, language):
    """Whether ``value`` reads as ``language``, as far as its grammatical
    words tell: it holds no more words only another language has than words
    of its own, and, on five words or more, one of its own at least. A text
    too short to tell (« Session », « Usine muette ») is not refused, nor
    any text when ``language`` is one this table does not know."""
    own = GRAMMATICAL_WORDS.get(language)
    if own is None:
        return True
    words = [word.lower() for word in _WORD.findall(value or "")]
    mine = sum(1 for word in words if word in own)
    foreign = max([sum(1 for word in words if word in theirs and word not in own)
                   for other, theirs in GRAMMATICAL_WORDS.items() if other != language] or [0])
    if foreign and foreign >= mine:
        return False
    return mine > 0 or len(words) < _SENTENCE_WORDS


def _holds_internal_term(lowered, terms):
    return next((term for term in sorted(terms) if re.search(r"\b%s\b" % re.escape(term), lowered)), None)


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
    try:
        terms, language = internal_terms(), operator_language()
    except TextControlError as exc:
        reasons.append("champ « %s » invérifiable : %s" % (label, exc))
        return reasons
    term = _holds_internal_term(value.lower(), terms)
    if term:
        reasons.append("champ « %s » contient un terme interne hors lexique (« %s »)" % (label, term))
    if not speaks(value, language):
        reasons.append("champ « %s » n'est pas dans la langue de l'opérateur" % label)
    return reasons


def speaks_plainly(value):
    """Whether ``value`` is in the Operator Language and holds neither an
    identifier nor an internal term (spec .73): what may be shown as main
    text, whatever its length or shape. ``False`` when that cannot be told."""
    if not isinstance(value, str):
        return False
    try:
        terms, language = internal_terms(), operator_language()
    except TextControlError:
        return False
    return (speaks(value, language) and not any(pattern.search(value) for pattern in _IDENTIFIER_PATTERNS)
            and not _holds_internal_term(value.lower(), terms))


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
