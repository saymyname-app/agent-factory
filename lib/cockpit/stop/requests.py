"""Operator Requests raised by the Clean stop driver (T23, af-s5e3yo --
Spec af-oohx2x §"Demandes opérateur": "« L'arrêt n'avance plus » /
« Reprise avec écarts »" -> À faire, priorité 0).

Built directly on :class:`~cockpit.requests.model.OperatorRequest` -- this
ticket's declared scope is ``lib/cockpit/stop/**``, not
``requests/sources/**``, so wiring these into the assembled "Ce qui
t'attend" feed is left to the ticket that combines every source.
"""
from cockpit.requests.model import A_FAIRE, DEFAULT_PROJECT, OperatorRequest

TYPE_ARRET_BLOQUE = "arret_bloque"
TYPE_REPRISE_ECARTS = "reprise_ecarts"


def build_no_progress_request(started_at, perdu_preview=None):
    perdu_preview = perdu_preview or []
    if perdu_preview:
        consequence = (
            "Arrête les sessions en gardant leur ticket et leur travail assigné : %s."
            % ", ".join(perdu_preview)
        )
    else:
        consequence = "Arrête les sessions en gardant leur ticket et leur travail assigné."
    return OperatorRequest(
        id="stop:no-progress",
        type=TYPE_ARRET_BLOQUE,
        niveau=A_FAIRE,
        quoi="L'arrêt n'avance plus depuis 30 min.",
        pourquoi="Aucune session n'a progressé (commit, étape fermée, événement) depuis 30 min.",
        que_faire=[
            {
                "lettre": "a",
                "option": "Forcer l'arrêt",
                "consequence": consequence,
                "recommande": False,
                "raison": "",
            },
            {
                "lettre": "b",
                "option": "Attendre encore",
                "consequence": "Laisse les sessions en cours finir leur ticket.",
                "recommande": True,
                "raison": "Chaque session va au bout de son ticket en cours par défaut.",
            },
        ],
        projet=DEFAULT_PROJECT,
        depuis_quand=started_at,
        verifie_a=started_at,
        lien="",
    )


def build_ecarts_request(ecarts, at):
    ecarts = ecarts or []
    detail = ", ".join(ecarts) if ecarts else "aucun"
    return OperatorRequest(
        id="stop:reprise-ecarts",
        type=TYPE_REPRISE_ECARTS,
        niveau=A_FAIRE,
        quoi="Reprise avec écarts : %d travail(aux) repris autrement." % len(ecarts),
        pourquoi="Au moins un travail d'avant l'arrêt n'a pas été repris sans réattribution.",
        que_faire=[
            {
                "lettre": "a",
                "option": "Voir le détail",
                "consequence": "Affiche les tickets concernés : %s." % detail,
                "recommande": True,
                "raison": "Comprendre l'écart avant de continuer.",
            }
        ],
        projet=DEFAULT_PROJECT,
        depuis_quand=at,
        verifie_a=at,
        lien="",
    )
