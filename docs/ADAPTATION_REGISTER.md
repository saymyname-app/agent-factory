# Adaptation Register

Ce fichier est l'unique registre durable des écarts implémentés par rapport à
la Method Baseline de Matt Pocock et des contrôles ajoutés par la Factory. Le
tableau d'expériences de l'Approved Spec est son contrat de planification, pas
un second registre. Une entrée n'est conservée, remplacée ou supprimée qu'à
partir de preuves nommées ; le candidat en tête d'un prototype ne devient pas
silencieusement l'architecture de production.

## AR-001 — Orchestration Gas City de la méthode de Matt

| Champ | Enregistrement |
| --- | --- |
| Statut | **Conserver provisoirement** l'allocation `skill-loaded-planner` pendant les prochains prototypes ; ne pas encore la figer dans le kernel de planification. |
| Baseline | La méthode de Matt définit les comportements observables de `/grill`, `/to-spec` et `/to-tickets`, mais ne prescrit aucune topologie Gas City, Beads, session, agent, Formula ou Order. |
| But | Préserver une seule identité de Planning Run, un seul auteur canonique de Planning Artifacts et une seule autorité de livraison Mayor dans une Factory unique, tout en gardant le chemin simple léger et en autorisant des sessions spécialistes jetables pour le Wayfinding. |
| Adaptation sélectionnée | Le graphe Formula de Gas City possède le séquencement. Un `planning-agent` charge les skills de phase dans une `planning-session` ; une Formula `planning-decision-prototype` peut router des `decision-session` jetables. Les dépendances de Formula et les checks déterministes possèdent l'éligibilité. Les portes déterministes possèdent l'identité du Planning Run, la validation des artifacts et la publication atomique. Le Mayor ne reçoit l'autorité qu'à la frontière de continuation du convoy existante. |
| Alternative maintenue viable | `phase-specialized-roles` affecte l'entretien, le travail spécialiste et l'écriture canonique à des rôles et modèles de session distincts, avec des Formulas séparées pour simple, Wayfinding et décision. |
| Preuves | `./bin/planning-allocation-prototype run` exécute de façon déterministe les deux candidats sur les chemins simple et Wayfinding, injecte des échecs de l'auteur canonique et de validation du draft, puis atteint `CONVOY_CONTINUATION_READY` sans convoy partiel. `tests/planning-allocation-prototype-test.py` prouve le contrat. |
| Coût observé | Les deux candidats satisfont les mêmes invariants de méthode et d'échec. L'allocation retenue compte 14 unités de configuration contre 19 : 2 agents contre 4, 2 modèles de session contre 3, 2 Formulas contre 3 et 1 Order contre 2, avec les mêmes 3 skills et 4 portes déterministes. Ces nombres mesurent les liaisons à maintenir, pas les tokens ni la qualité fournisseur. |
| Réversibilité bornée | À `WAYFINDING_CLEAR`, avant l'auteur canonique, ne changer que les liaisons de session, agent, Formula et Order vers `phase-specialized-roles`. Conserver les IDs du Planning Run et de la Planning Map, les décisions résolues, les identités d'artifact réservées, les portes déterministes et l'autorité Mayor. Le prototype exécute ce retour jusqu'à la même frontière convoy. |
| Point de revue | P03 a produit la preuve : `./bin/planning-map-concurrency-prototype run` démontre une réclamation exactement-une-fois par enfant de décision sous tout ordre d'arrivée, des écritures à clé disjointe préservées sans collision, et une écriture concurrente sur la clé d'index partagée rejetée pour nouvelle tentative sans perte (`docs/PLANNING_MAP_CONCURRENCY_PROTOTYPE.md`, `tests/planning-map-concurrency-prototype-test.py`). Réévaluer maintenant conjointement avec P04 sur la continuité fournisseur/surface, avant que B03/B04 figent le kernel. P06 qualifie séparément les modèles, le coût tokens et la rétention. |
| Règle conserver / remplacer / supprimer | Conserver l'allocation minimale seulement si ces prototypes préservent décisions et auteur unique sans ambiguïté de rôle. La remplacer par `phase-specialized-roles` si le rôle partagé cause un échec de fidélité ou de reprise. Supprimer l'orchestration Gas City seulement si une Planning Exception approuvée démontre que les deux allocations violent la méthode ; ne jamais ajouter un second orchestrateur comme repli. |
