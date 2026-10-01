"""Chantier/Project shapes (spec af-oohx2x §"Suivre les projets", T19/T20;
CONTEXT.md: Chantier, Projet, Roadmap Step).

T19 ("de Cadrage à Livré") named the first five stages. T20 ("Chantiers
acceptés et promus") adds Accepté and Promu, the overlaid état (à toi de
jouer / problème remonté / bloqué / normal, :mod:`cockpit.projects.etat`),
and the historique fields (``termine``/``abandonne``) -- see
:mod:`cockpit.projects.stage` for how each is computed.
"""
from dataclasses import dataclass, field

CADRAGE = "Cadrage"
SPEC = "Spec"
GRAPHE = "Graphe"
LIVRAISON = "Livraison"
LIVRE = "Livré"
ACCEPTE = "Accepté"
PROMU = "Promu"

STAGES = (CADRAGE, SPEC, GRAPHE, LIVRAISON, LIVRE, ACCEPTE, PROMU)
STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}

# spec af-oohx2x .50: "une carte sans clé projet s'affiche sous « Sans
# projet » avec un défaut producteur compté" -- generalized here to any
# chantier-defining bead missing gc.project_id, not only a map bead.
SANS_PROJET = "Sans projet"


@dataclass
class Chantier:
    """One row under a project (or under "Sans projet"): a Planning Run and
    its convoy, wherever it currently sits between Cadrage and Promu.

    ``etat``/``etat_cible`` (T20, :mod:`cockpit.projects.etat`): the
    overlaid state and the chantier id the cockpit links to for it -- an
    "à toi de jouer"/"problème remonté" état with no cible renders as a
    displayed defect (spec .45), never silently drops.
    ``promu_masque``: true when the project's rig has no promotion branch
    configured (spec .41) -- Accepté is this chantier's last applicable
    stage, Promu never applies.
    ``termine``/``abandonne``: historique membership (spec .46); a
    terminé or abandonné chantier is excluded from the active lists
    :mod:`cockpit.projects.stage`'s stage functions return.
    """

    id: str
    titre: str
    projet: str
    stage: str
    detail: str
    etat: str = "normal"
    etat_cible: str = None
    promu_masque: bool = False
    termine: bool = False
    abandonne: bool = False
    raison_abandon: str = None
    planning_run_target: str = None

    @property
    def stage_index(self):
        return STAGE_INDEX[self.stage]


@dataclass
class RoadmapStep:
    id: str
    title: str
    status: str


@dataclass
class Project:
    project_id: str
    display_name: str
    roadmap_step: RoadmapStep = None
    # Freshness of the roadmap read (spec .13/.62): the epoch the clone was
    # last read successfully, or None while never read. Set alongside
    # roadmap_unknown_since -- exactly one of the two carries a value once a
    # read has been attempted.
    roadmap_read_at: float = None
    roadmap_unknown_since: float = None
    chantiers: list = field(default_factory=list)
    # "dev a N commits d'avance" (spec .42, T20), one entry per rig this
    # project declares a promotion branch for; a rig absent here means its
    # gap was never read (unknown, not zero -- spec .62).
    ecart_commits_par_rig: dict = field(default_factory=dict)
