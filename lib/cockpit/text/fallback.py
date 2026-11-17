"""Fixed repli (fallback) phrases, spec af-oohx2x §"Demandes opérateur" and
§"Compréhensible sans IA": ".14 En tant que Benjamin, je veux qu'une
demande sans ses champs s'affiche quand même, avec « incomplète : champ X
manquant » et un texte de repli fixe... ." These are the only fixed
strings this module owns; nothing here is generated or translated.
"""

CONTINUER_AVEC_UN_AGENT = "continuer avec un agent"

# The « … » the spec wrote in « ta décision sur … » was never filled: the
# page showed it as is (af-x7xg4s). The subject is the title, just above.
FALLBACK_POURQUOI = "Un agent demande ta décision ; il n'a pas dit pourquoi"
# A title is never « incomplète : champ quoi manquant » (af-x7xg4s): when
# neither what the producer wrote nor the title of its source can be read,
# the title says what kind of request it is.
FALLBACK_QUOI = {
    "escalation": "Un agent te pose une question",
    "proposal": "Un agent te propose une décision",
}
FALLBACK_QUOI_DEFAULT = "Un agent attend ta décision"
# An option kept, whose consequence or reason its producer wrote in words
# the main text does not show: they are in the folded details.
CONSEQUENCE_IN_DETAILS = "Conséquence écrite par l'agent : voir les détails"
RAISON_IN_DETAILS = "Raison écrite par l'agent : voir les détails"
FALLBACK_CONSEQUENCE = "Conséquence non fournie par l'agent"
FALLBACK_NO_RECOMMENDATION = "Pas de recommandation fournie"

FIELD_LABELS = {
    "quoi": "quoi",
    "pourquoi": "pourquoi",
    "que_faire": "que faire",
    "depuis_quand": "depuis quand",
}


def incomplete_label(field):
    """"incomplète : champ X manquant" (spec .14) for ``field`` (one of
    FIELD_LABELS's keys, or any French field name already)."""
    return "incomplète : champ %s manquant" % FIELD_LABELS.get(field, field)


def unreadable_label(field):
    """"incomplète : champ X illisible" for a field its producer did write,
    in words the main text does not show (af-x7xg4s: « manquant » was said
    of a field that was there)."""
    return "incomplète : champ %s illisible" % FIELD_LABELS.get(field, field)


def fallback_que_faire():
    """The fixed repli option list: a single "continuer avec un agent"
    option whose consequence is the fixed repli text (spec .14, .32)."""
    return [
        {
            "lettre": "a",
            "option": CONTINUER_AVEC_UN_AGENT,
            "consequence": FALLBACK_CONSEQUENCE,
            "recommande": False,
            "raison": "",
        }
    ]
