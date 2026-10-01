"""Chantier/Project shapes (spec af-oohx2x §"Suivre les projets", T19;
CONTEXT.md: Chantier, Projet, Roadmap Step).

T19's own scope stops at Livré (its title: "de Cadrage à Livré") -- Accepté
and Promu are T20's ("Chantiers acceptés et promus"), so this module only
names the five stages a chantier can reach here. A later ticket extends
:data:`STAGES` rather than this one guessing at Operator Action shapes it
does not implement.
"""
from dataclasses import dataclass, field

CADRAGE = "Cadrage"
SPEC = "Spec"
GRAPHE = "Graphe"
LIVRAISON = "Livraison"
LIVRE = "Livré"

STAGES = (CADRAGE, SPEC, GRAPHE, LIVRAISON, LIVRE)
STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}

# spec af-oohx2x .50: "une carte sans clé projet s'affiche sous « Sans
# projet » avec un défaut producteur compté" -- generalized here to any
# chantier-defining bead missing gc.project_id, not only a map bead.
SANS_PROJET = "Sans projet"


@dataclass
class Chantier:
    """One row under a project (or under "Sans projet"): a Planning Run and
    its convoy, wherever it currently sits between Cadrage and Livré."""

    id: str
    titre: str
    projet: str
    stage: str
    detail: str

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
