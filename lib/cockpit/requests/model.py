"""The Operator Request shape (spec af-oohx2x §"Demandes opérateur : types,
niveaux, sortie").
"""
from dataclasses import dataclass, field

URGENT = "Urgent"
A_FAIRE = "À faire"
QUAND_TU_VEUX = "Quand tu veux"

# Sort order: Urgent first, then oldest to newest within a level (spec .3).
LEVEL_ORDER = {URGENT: 0, A_FAIRE: 1, QUAND_TU_VEUX: 2}

TYPE_ESCALATION = "escalation"
TYPE_PROPOSAL = "proposal"

DEFAULT_PROJECT = "usine"


@dataclass
class OperatorRequest:
    id: str
    type: str
    niveau: str
    quoi: str
    pourquoi: str
    que_faire: list
    projet: str = DEFAULT_PROJECT
    depuis_quand: float = None
    verifie_a: float = None
    lien: str = ""
    incomplete: bool = False
    missing_fields: list = field(default_factory=list)
    # Why each field in missing_fields was replaced by its fixed repli
    # ({field: [French reasons]}, from cockpit.text.validate) and, when the
    # producer did write something, its text exactly as written
    # ({field: text}) -- shown in the folded details (spec .75: « le texte
    # d'origine du producteur »), never as main text (spec .73). Without
    # these, a request refused for an identifier or an internal term read
    # as « champ manquant » with the field present (2026-10-07).
    motifs: dict = field(default_factory=dict)
    texte_origine: dict = field(default_factory=dict)
    # A proposal's optional `details` (bin/proposal-door): identifiers and
    # evidence, shown as written in the folded details only (spec .75).
    precisions: str = ""
    recommande_absent: bool = False
    # Out-of-scope touch (T13, af-cx20q9): Acquitter/Reporter (declared
    # scope lib/cockpit/actions/**) only mean anything if "Ce qui
    # t'attend" reflects them -- an acquitted Urgent still lists, a
    # deferred À faire hides until due, a deferred Urgent stays visible
    # greyed (spec .21-23). See requests/builder.py for where these are
    # set from bead metadata.
    acquittee: bool = False
    reportee: bool = False
    # False when no trace on a bead could hide the request until later
    # (a source with no bead, a chantier): Reporter is then not offered
    # rather than offered and without effect.
    reportable: bool = True
    # The bare title of what the request is about, when its "quoi" is a
    # fixed phrase around it (a chantier's name for « Pas bon → agent »).
    titre: str = ""
    # A signal of a type the cockpit does not know: what its source wrote,
    # exactly as received, shown in the folded details only (spec .76).
    texte_brut: str = ""

    def sort_key(self):
        # None (never timestamped) sorts after every real timestamp within
        # its level rather than crashing the comparison or hiding at the
        # very front (spec .3: oldest first — an unknown age is not old).
        age_key = self.depuis_quand if self.depuis_quand is not None else float("inf")
        return (LEVEL_ORDER.get(self.niveau, 99), age_key, self.id)
