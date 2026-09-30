"""Fixed repli (fallback) phrases, spec af-oohx2x §"Demandes opérateur" and
§"Compréhensible sans IA": ".14 En tant que Benjamin, je veux qu'une
demande sans ses champs s'affiche quand même, avec « incomplète : champ X
manquant » et un texte de repli fixe... ." These are the only fixed
strings this module owns; nothing here is generated or translated.
"""

CONTINUER_AVEC_UN_AGENT = "continuer avec un agent"

FALLBACK_POURQUOI = "Un agent demande ta décision sur … ; il n'a pas dit pourquoi"
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
