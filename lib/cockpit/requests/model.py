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
    recommande_absent: bool = False

    def sort_key(self):
        # None (never timestamped) sorts after every real timestamp within
        # its level rather than crashing the comparison or hiding at the
        # very front (spec .3: oldest first — an unknown age is not old).
        age_key = self.depuis_quand if self.depuis_quand is not None else float("inf")
        return (LEVEL_ORDER.get(self.niveau, 99), age_key, self.id)
