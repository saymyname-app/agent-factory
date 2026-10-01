"""Livré non Accepté / Accepté non Promu as Quand tu veux Operator
Requests (spec af-oohx2x §"Demandes opérateur : types, niveaux, sortie":
"Livré non Accepté et Accepté non Promu sont des demandes Quand tu veux";
T20).

Reuses :class:`cockpit.requests.model.OperatorRequest` (import only --
that module's own wiring into "Ce qui t'attend" is
lib/cockpit/requests/**, out of this ticket's declared scope,
gc.scope_paths: lib/cockpit/projects/**, lib/cockpit/ui/projects/**) so a
future ticket can fold these straight in the same way
:mod:`cockpit.requests.sources.hitl` already folds in ready HITL tickets.

Exit is at-source, same as every other request (spec .15): a chantier
stops producing a demande the moment it leaves Livré/Accepté-non-promu
(accepted, promu, or termine/abandonne) -- there is no cockpit-side flag
to clear."""
from cockpit.projects.model import ACCEPTE, LIVRE
from cockpit.requests.model import DEFAULT_PROJECT, OperatorRequest, QUAND_TU_VEUX

TYPE_LIVRE_NON_ACCEPTE = "chantier_livre_non_accepte"
TYPE_ACCEPTE_NON_PROMU = "chantier_accepte_non_promu"


def _livre_non_accepte(chantier, verifie_a):
    return OperatorRequest(
        id=chantier.id,
        type=TYPE_LIVRE_NON_ACCEPTE,
        niveau=QUAND_TU_VEUX,
        quoi="Le chantier %s est livré, non accepté." % chantier.titre,
        pourquoi="Benjamin doit accepter ce chantier livré, ou le corriger.",
        que_faire=[
            {
                "lettre": "a",
                "option": "Accepter",
                "consequence": "Trace l'acceptation ; le chantier passe à Accepté.",
                "recommande": True,
                "raison": "Rien ne bloque son acceptation.",
            },
            {
                "lettre": "b",
                "option": "Pas bon -> agent",
                "consequence": "Copie un prompt de correction, sans rouvrir le graphe gelé.",
                "recommande": False,
                "raison": "",
            },
        ],
        projet=chantier.projet or DEFAULT_PROJECT,
        verifie_a=verifie_a,
        lien=chantier.id,
    )


def _accepte_non_promu(chantier, verifie_a):
    return OperatorRequest(
        id=chantier.id,
        type=TYPE_ACCEPTE_NON_PROMU,
        niveau=QUAND_TU_VEUX,
        quoi="Le chantier %s est accepté, pas encore promu." % chantier.titre,
        pourquoi="La branche de promotion n'a pas encore reçu tous ses commits de merge.",
        que_faire=[
            {
                "lettre": "a",
                "option": "Voir le chantier",
                "consequence": "Rien ne change tant que la promotion n'a pas eu lieu.",
                "recommande": False,
                "raison": "",
            }
        ],
        projet=chantier.projet or DEFAULT_PROJECT,
        verifie_a=verifie_a,
        lien=chantier.id,
    )


def chantier_demandes(chantiers, verifie_a=None):
    """Every active (not ``termine``/``abandonne``) chantier currently
    Livré-non-Accepté or Accepté-non-Promu, as Quand tu veux
    :class:`~cockpit.requests.model.OperatorRequest` rows."""
    out = []
    for chantier in chantiers or []:
        if chantier.termine or chantier.abandonne:
            continue
        if chantier.stage == LIVRE:
            out.append(_livre_non_accepte(chantier, verifie_a))
        elif chantier.stage == ACCEPTE and not chantier.promu_masque:
            out.append(_accepte_non_promu(chantier, verifie_a))
    out.sort(key=lambda r: r.sort_key())
    return out
