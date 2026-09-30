"""Builds the neutral "continuer avec un agent" prompt (spec af-oohx2x
§"Actions opérateur": "Le prompt copié est neutre, sans fournisseur
imposé ... sans chiffre de coût"; T13 AC5).

Pure text formatting -- the cockpit never executes this prompt itself
("Le cockpit n'exécute jamais le contenu d'une option : c'est l'usine
qui l'exécute, avec ses tokens"); it only builds the text a human pastes
into whatever agent session they choose to open.
"""

TOKEN_WARNING = "(utilise un agent -- consomme des tokens)"

DEFAULT_DOSSIER = "agent-factory"
DEFAULT_COMMANDE = "claude"


def build_prompt(bead_id, quoi, dossier=None, commande=None):
    """``quoi``: the request's own "quoi" field (already Operator
    Language, already validated) -- copied verbatim, never rewritten."""
    dossier = dossier or DEFAULT_DOSSIER
    commande = commande or DEFAULT_COMMANDE
    return (
        "Quoi : %s\n"
        "Identifiants : %s\n"
        "Question : reprends ce sujet et propose la suite.\n"
        "Dossier : %s\n"
        "Commande de départ : %s\n"
        "%s"
    ) % (quoi or "(non précisé)", bead_id, dossier, commande, TOKEN_WARNING)
