# ADR-0031 : refuser un graphe de tickets sérialisé sans besoin

- Statut : Accepté
- Date : 2026-10-15
- Autorité : demande de Benjamin en conversation (2026-10-15, 18:52 et 19:22 Paris) ; Bead `af-46beo2`, correctif `af-i4w79r`
- Portée : `bin/graph-review` (revue de graphe avant approbation), consigne de découpage de `docs/PLANNING_RUN.md`

Intent (Benjamin, ses mots, 2026-10-15 18:52) : « Oui il faut plus de
parallèlisme stp. Aussi il faut voir comment on aurait pu avoir plus de
parallelisme directement (j'aurais dû verifier moi même peut etre, mais si les
agents peuvent directement créer plus de parallelisme c'est encore mieux,
j'aimerais à terme ne pas avoir à verifier) ».

Mechanism (interprétation agent) : le code mesure le chemin critique de chaque
brouillon relu et le refuse au-delà d'un tiers de ses tickets, en nommant la
chaîne ; la consigne de découpage demande qu'un ticket n'attende que ce qu'il
consomme.

## Contexte

Graphe Cockpit (Spec `af-2zseit`, convoi `af-pqfxmd`) le 15/10 : 60 tickets
ouverts, chemin critique 34, un seul ticket prêt pour un plafond de deux
auteurs. Les 88 liens avaient été écrits à la main par la session
`/to-tickets` ; aucun ne venait des fichiers chauds (aucun `scope.paths`
déclaré). Chaque surface (Usine, Pour moi, Runs, Rituels) était mise en file
indienne sans que le ticket bloqué cite un livrable de son bloqueur. Deux
passes de revue de graphe l'avaient jugé favorable : aucune question ne
mesurait le parallélisme, et `same_surface_ordered` pousse à ordonner.

## Décision

1. `bin/graph-review record` ajoute une question de graphe calculée par le
   code, jamais posée au relecteur : `critical_path_bounded`. Elle est
   défavorable quand la plus longue chaîne de `blocked_by` dépasse
   max(4, ⌈n/3⌉) tickets (n tickets du brouillon) : avec deux auteurs, au
   moins trois tickets par niveau en moyenne. La raison nomme la chaîne et les
   liens déjà impliqués par d'autres.
2. Le refus suit le circuit existant (`docs/GRAPH_REVIEW.md`) : correction et
   seconde passe ; ensuite Benjamin seul peut garder un graphe sérialisé
   (`decide --graph --decision publish` avec ses mots). La voie déléguée
   (`docs/PLANNING_DELEGATION.md`) n'accepte aucun avis défavorable : l'agent
   doit paralléliser lui-même.
3. Consigne de découpage (`docs/PLANNING_RUN.md`, étape 5) : un ticket n'attend
   que les tickets dont il consomme un livrable cité dans son texte ; une même
   surface n'est pas une dépendance.

## Ce qui ne change pas

Les portes de publication et de patch (`bin/ticket-graph-publish`), les
liens ajoutés pour les `scope.paths` qui se recouvrent, le plafond de deux
auteurs. Un patch (`bd-patch`) n'est pas relu par cette commande.

## Preuve

`tests/graph-review-test.py` : un graphe en chaîne de six tickets est refusé
avec sa chaîne et son lien redondant nommés ; le même parallélisé passe ; le
relecteur ne peut pas répondre à la question calculée. Rouge sur main, vert
avec ce changement. Mesure sur les vrais brouillons : `af-rf5658160` (graphe
Cockpit approuvé) défavorable, chemin critique 35 pour 61 tickets (au plus
21) ; `af-w2pqiv` (révision `af-46beo2`) favorable, chemin critique 9.

## Comment une mauvaise lecture se verrait

- Un graphe publié dont le chemin critique dépasse le seuil sans décision de
  Benjamin enregistrée.
- Un graphe vraiment séquentiel bloqué en voie déléguée : le seuil est trop
  bas pour ce cas ; le dire à Benjamin plutôt que de contourner.

## Retour arrière

Annuler la PR : la question calculée disparaît, les passes déjà enregistrées
la gardent comme une raison lisible sans effet sur un nouveau brouillon.
