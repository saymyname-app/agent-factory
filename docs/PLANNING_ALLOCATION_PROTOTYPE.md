# Prototype d'allocation de la planification

## Résultat

P02 sélectionne provisoirement `skill-loaded-planner`, la plus petite de deux
allocations Gas City viables. C'est le résultat borné d'un prototype, pas le
kernel de planification de production. Les deux candidats préservent une seule
identité de Planning Run, un seul auteur canonique et une seule autorité de
livraison Mayor. Tous deux s'arrêtent à la frontière existante
`convoy-continuation`.

L'allocation retenue représente 14 unités de configuration maintenues, contre
19 pour `phase-specialized-roles`. La réduction vient du chargement des mêmes
skills de phase dans un seul rôle de planification, plutôt que d'un rôle et
d'un modèle de session par phase. Les portes déterministes et la Method
Baseline restent identiques.

## Exécution

```bash
./bin/planning-allocation-prototype validate
./bin/planning-allocation-prototype run
python3 tests/planning-allocation-prototype-test.py
```

`run` émet un résultat JSON déterministe unique : allocation complète, traces
simple et Wayfinding, checks de fidélité calculés, deux injections d'échec,
comptage de maintenance, choix provisoire, trace de retour borné et digest de
contenu. La source des candidats est
`config/planning-allocation-prototype.json`.

## Allocations comparées

| Responsabilité | `phase-specialized-roles` | `skill-loaded-planner` (choix provisoire) |
| --- | --- | --- |
| Conversation humaine | `planning-interviewer` dans `interactive-grilling-session` | `planning-agent` dans `planning-session` |
| Travail spécialiste | `planning-specialist` dans des `decision-specialist-session` jetables | Le même `planning-agent`, défini par capacité, dans des `decision-session` jetables |
| Auteur canonique | `planning-artifact-writer` dans `canonical-writer-session` | `planning-agent` dans l'unique liaison d'auteur du run ; la porte artifact déterministe rejette un auteur concurrent |
| Séquencement | Formulas Gas City séparées pour simple, Wayfinding et décision | Une Formula de Planning Run et une Formula de décision |
| Éligibilité | Orders de run et de frontière, arêtes de dépendance et checks déterministes | Un Order de run, arêtes de dépendance et checks déterministes |
| Validation | Portes de Planning Run, artifact, validation et publication atomique | Les mêmes quatre portes déterministes |
| Autorité de livraison | Mayor, uniquement après que la publication validée expose la continuation du convoy | Identique |
| Liaisons maintenues | 19 | 14 |

Le planning agent exécute ; il n'orchestre pas. Le graphe Formula de Gas City
possède le séquencement et l'éligibilité, tandis que le code déterministe
possède les transitions d'état et la validation. Aucun candidat n'importe
`planning-base`, ne fabrique des projections requirements/plan ni n'introduit
un second Work Graph ou orchestrateur.

## Chemins observés

La trace simple crée un Planning Run, établit la Shared Understanding dans la
session interactive, écrit et valide une Spec et un Ticket Graph Draft par
l'unique liaison d'auteur, publie atomiquement puis expose la continuation du
convoy au Mayor.

La trace Wayfinding crée le même type de Planning Run borné, trace une Planning
Map, route deux décisions spécialistes indépendantes, attend leurs deux arêtes,
valide `WAYFINDING_CLEAR` de façon déterministe, puis réutilise le même chemin
d'auteur et de publication. Chaque événement indique explicitement où
s'exécutent conversation humaine, travail spécialiste, skill, séquencement,
éligibilité et validation ; rien n'est déduit du seul nom d'un agent.

Deux échecs injectés rendent la limite de reprise observable :

- Un auteur canonique indisponible arrête le run à `WRITER_RETRYABLE`. Aucun
  artifact n'est approuvé et aucun convoy n'existe.
- Un Ticket Graph Draft rejeté arrête le run à
  `TICKET_GRAPH_DRAFT_INVALID`. La porte de publication atomique n'a pas été
  appelée ; il n'existe donc aucun nœud publié ni convoy à nettoyer.

## Retour borné

Le choix reste réversible à `WAYFINDING_CLEAR`, avant le début de l'écriture
canonique. Le prototype mène le candidat retenu jusqu'à la résolution des
décisions, ne change que les liaisons de session, agent, Formula et Order de la
phase suivante, puis termine avec `phase-specialized-roles`. L'identité du
Planning Run et de la Map, les décisions résolues, les identités d'artifact
réservées, les portes déterministes et l'autorité Mayor ne changent pas. Il ne
faut ni migration d'état, ni second auteur, ni deuxième décomposition.

Ce retour est volontairement étroit. Après le début de l'auteur canonique, un
changement d'allocation devient une Planning Exception ; il ne doit pas être
déguisé en simple retry.

## Portée des preuves

- **TARGET** : toute la méthode de planification et livraison de l'Approved
  Spec project-agnostic.
- **CONFIGURED** : deux allocations candidates, le plus petit choix provisoire
  et un checkpoint de retour.
- **OBSERVED** : les traces déterministes simple, Wayfinding, échec d'auteur,
  échec de validation et retour, jusqu'à la continuation du convoy.
- **PROVEN** : dans ce prototype, les invariants de topologie, les autorités
  uniques, la publication fail-closed, la sortie déterministe et la comparaison
  des unités de maintenance.

Ne sont pas prouvés ici : qualité des modèles live, écritures concurrentes de
Planning Map, continuité entre fournisseurs ou surfaces, et kernel de
planification futur. P03, P04, P06, B03 et B04 en gardent la responsabilité.
Le [Fixture City Oracle](FIXTURE_CITY_ORACLE.md) reste la couture de comportement
public indépendante de la topologie ; P02 sélectionne seulement l'allocation
minimale à conserver pour les prototypes suivants.

## Conformité ADR-0017

- **Vérifiée** : le test exécute les chemins positifs, les deux échecs et le
  retour ; les tests de publication atomique et du Fixture City Oracle restent
  verts à la même frontière.
- **Autonomie accrue** : le validateur calcule la viabilité et refuse
  `planning-base`, un second orchestrateur, plusieurs Mayors, une liaison hors
  allocation ou un choix qui n'est pas le plus petit. Les prochains agents
  n'ont pas à refaire cette comparaison de mémoire.
- **Optimisation nommée** : 5 liaisons de configuration en moins, soit 26 % de
  la surface candidate (19 vers 14), sans retirer de skill ni de porte.
- **Deux publics** : cette page française expose l'usage et les limites à
  Benjamin ; `docs/CONTEXT_INDEX.md`, la sortie structurée et les tests rendent
  le contrat découvrable et exploitable par les agents.

L'adaptation implémentée et sa règle de revue vivent dans l'unique
[Adaptation Register](ADAPTATION_REGISTER.md#ar-001--orchestration-gas-city-de-la-méthode-de-matt).
