# ADR-0025 : publication atomique et scope exclusif d'un graphe approuvé

- Statut : Accepté
- Date : 2026-09-23
- Autorité : Benjamin, approbation puis autorisation explicite du Ticket Graph Draft
- Portée : bootstrap du refactor project-agnostic de la Factory

## Contexte

Le Ticket Graph Draft approuvé doit être confié à la Factory actuelle pour
construire son successeur. Deux défauts du chemin legacy rendent une reprise
directe dangereuse : la priorité `factory` retombe volontairement sur la voie
produit lorsqu'elle paraît vide, et une publication ticket par ticket pourrait
laisser un graphe partiel. L'ancienne campagne SayMyName reste matérialisée et
ne doit pas être reprise pendant ce bootstrap.

Beads 1.2.2 sait créer un graphe complet par `bd create --graph` dans une seule
transaction Dolt. Le plan accepte les métadonnées des nœuds et les arêtes
top-level `from_key`/`to_key`; un échec annule la transaction. Cela permet de
construire les tickets, leurs blocages et le convoy dans la même écriture.

## Décision

1. `bin/ticket-graph-publish` est l'unique porte de bootstrap. Elle vérifie
   l'état approuvé, l'autorisation de publication, le digest de contenu, la
   Spec source, les IDs, critères, rigs, références de blocage et l'acyclicité.
2. Elle publie les 18 tickets approuvés et un convoy dans une seule transaction
   `bd create --graph`. Les arêtes `blocks` et `tracks`, le digest de graphe,
   le plan `delivery`, la trace Spec et le contrat d'exécution sont présents
   dans ce même plan. C01 et V01 restent hors de cette transaction, conformément
   au draft : C01 est un nouveau Planning Run après cutover et V01 son gate de
   clôture ultérieur.
3. `mayor-campaign scope <sha256:...> --mayor` active un mode `exclusive_graph` avant
   la publication et la reprise. La sentinelle sélectionne alors uniquement un
   bead portant à la fois le digest exact et `gc.plane=delivery`.
4. Dans ce mode, il n'existe aucun fallback vers produit, anciennes améliorations
   Factory, file `goal=none`, audits génératifs ou axes d'amélioration. Une
   frontière vide ou bloquée produit `scoped_graph_waiting`, sans appel modèle.
5. Le scope se retire uniquement par `mayor-campaign scope clear --mayor`, après la
   transition autorisée vers le graphe suivant ou la clôture. La priorité
   Factory/product historique conserve son fallthrough en dehors de ce mode.

## Conséquences selon ADR-0017

1. **Vérifié** — les tests prouvent validation du digest, transaction de graphe
   unique, convoy et arêtes, routage positif, exclusion de C01/V01, refus des
   anciens beads et absence de fallback produit ou génératif.
2. **Autonomie accrue** — Benjamin n'a pas à suspendre manuellement chaque ancien
   bead ni à surveiller l'instant où la voie Factory se vide.
3. **Optimisation** — état inchangé et blockers produisent un NOOP déterministe ;
   aucun modèle n'est réveillé hors de la frontière exacte du graphe.
4. **Documentation** — cette ADR, `FACTORY_TOOLS.md` et le contexte indexé
   décrivent la porte et sa reprise.

## Reprise et limites

- Activer le scope avant de publier est fail-closed : un échec de publication
  laisse une campagne scoped vide et arrêtée, jamais un fallback legacy.
- Une présence partielle portant le même digest est une erreur de cohérence et
  bloque une seconde publication au lieu de dupliquer des tickets.
- Cette porte bootstrap n'anticipe pas le câblage Q11. Elle matérialise le graphe
  approuvé pour que P01–P06 observent et choisissent ce câblage.
- Le mode exclusif ne supprime, ne ferme et ne modifie aucun ancien bead ; il les
  rend seulement inéligibles jusqu'à la levée explicite du scope.

## Liens

- Approved Spec `spec-agent-factory-project-agnostic-refactor`.
- Ticket Graph Draft `ticket-graph-draft-agent-factory-project-agnostic-refactor`.
- ADR-0023 — portes d'écriture de l'état de coordination.
- `bin/ticket-graph-publish` et `tests/ticket-graph-publish-test.py`.
- `bin/mayor-campaign` et `tests/mayor-campaign-test.py`.
