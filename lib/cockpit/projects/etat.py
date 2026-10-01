"""Overlaid Chantier state (spec af-oohx2x §"Étapes d'un chantier": "états
superposés, par priorité : en attente de Benjamin (...) > bloqué (...) >
normal"; T20).

Pure: every input here is a plain bool/id the caller
(:mod:`cockpit.projects.stage`) already derived from beads -- this module
only applies the priority rule and the "an état without a cible renders as
a displayed defect" safety net (spec .45), never reads a bead itself.
"""

A_TOI_DE_JOUER = "a_toi_de_jouer"
PROBLEME_REMONTE = "probleme_remonte"
BLOQUE = "bloque"
NORMAL = "normal"

DEFAUT_LABEL = "défaut affiché : état sans cible d'action"

LABELS = {
    A_TOI_DE_JOUER: "à toi de jouer",
    PROBLEME_REMONTE: "problème remonté",
    BLOQUE: "bloqué",
    NORMAL: "normal",
}

# "en attente de Benjamin" états need a cible to make sense (spec .45);
# "bloqué" and "normal" never claim one.
_NEEDS_CIBLE = (A_TOI_DE_JOUER, PROBLEME_REMONTE)


def resolve(
    probleme_remonte=False,
    probleme_remonte_cible=None,
    a_toi_de_jouer=False,
    a_toi_de_jouer_cible=None,
    bloque=False,
):
    """Priority: problème remonté > à toi de jouer > bloqué > normal
    (both are "en attente de Benjamin"; spec lists NEEDS BENJAMIN's
    "problème remonté" ahead of a bloqué read since an open question is
    more specific than a schedule read). Returns ``(etat, cible)``."""
    if probleme_remonte:
        return PROBLEME_REMONTE, probleme_remonte_cible
    if a_toi_de_jouer:
        return A_TOI_DE_JOUER, a_toi_de_jouer_cible
    if bloque:
        return BLOQUE, None
    return NORMAL, None


def label(etat, cible):
    """spec .45: "qu'un état « en attente de Benjamin » sans cible
    d'action soit affiché comme un défaut" -- the only two états that
    claim a cible are checked; a never-before-seen ``etat`` value also
    renders as the defect rather than crashing the page."""
    if etat in _NEEDS_CIBLE and not cible:
        return DEFAUT_LABEL
    return LABELS.get(etat, DEFAUT_LABEL)
