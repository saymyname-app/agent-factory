# ADR-0029 : deux classes de proposition — la maintenance se corrige, la décision remonte

- Statut : Accepté
- Date : 2026-10-07
- Autorité : décision de Benjamin en conversation (2026-10-07, 02:30 Paris), analyse du Cockpit « Ce qui t'attend » (13 items, 4 périmés, 5 de maintenance)
- Portée : Mayor, `bin/proposal-door`, Cockpit (« Ce qui t'attend »), ordres producteurs de propositions

Intent (Benjamin, ses mots, 2026-10-07) : « oui pour R1, enregistre la décision et lance la puce », en réponse à la recommandation R1 : « deux classes de proposition à la création : maintenance (ordres, gardes, tests, docs) et décision (comportement, méthode, dépense, ce que tu vois). La classe maintenance ne t'est pas montrée : elle devient un bead bug que le Mayor dispatche sous l'autorisation du 16/09 ».

Mechanism (interprétation agent) : ci-dessous.

## Contexte

Deux règles de Benjamin se contredisent dans la pratique :

- 2026-09-16, autorisation permanente (fichier opérateur) : la maintenance de
  l'usine (scripts, tests, docs) se fait en branche + batterie verte, PR
  ouvert sans demander, fusion automatique sur CI verte.
- 2026-09-25/26, prompt du Mayor (« Improvements are proposals ») : aucune
  amélioration sans graphe approuvé ; toute idée devient une proposition ;
  « agents propose, Benjamin decides ».

Résultat observé le 2026-10-07 : sur 8 propositions ouvertes dans le Cockpit,
5 sont des filtres d'ordres ou de gardes (watchdog, idle-wake,
delivery-guard, dispatch-door-guard, deliver-close) que la première règle
couvrait déjà ; 4 sont périmées parce qu'une proposition n'a pas d'état
« résolue » et que la correction a fusionné par un autre chemin (escalade,
bead bug, ticket D01). Benjamin arbitre des décisions qui ne sont pas de
son niveau, et ne voit pas celles qui le sont.

## Décision

1. Toute proposition porte une **classe** à la création, choisie par le
   producteur et validée par `bin/proposal-door` :
   - `maintenance` : corrige un défaut constaté de l'usine sans changer un
     comportement visible de Benjamin ni une règle de méthode — ordres,
     gardes, formules, tests, docs, filtres de pages, seuils techniques.
   - `decision` : change ce que Benjamin voit ou doit faire, une règle de
     méthode (pin upstream, flux de planification), une dépense, un
     consentement, une donnée personnelle, un effet irréversible, ou un
     comportement produit.
2. Une proposition `maintenance` **n'entre pas** dans « Ce qui t'attend ».
   Elle devient un bead bug autorisé par la présente ADR
   (`gc.authorized_by=ADR-0029`), dispatché par le Mayor par la porte de
   dispatch habituelle, livré en PR vérifiée par CI et fusionné par
   `pr-autopilot` sur vert. Elle reste visible dans la zone santé du Cockpit
   et dans le journal.
3. Une proposition `decision` entre dans « Ce qui t'attend » en « Quand tu
   veux » et porte **obligatoirement** une option « Recommandé » avec sa
   raison (R3). `proposal-door` refuse l'écriture sinon.
4. Une proposition sans champs (créée avant la porte) n'entre plus dans
   « Ce qui t'attend » : elle est signalée dans la zone santé comme
   anomalie à reformuler par la porte ou à fermer (R5).
5. Une proposition résolue par une livraison qui la cite se ferme en état
   « résolue par <PR> » (R2, chantier séparé déjà lancé) ; l'ordre
   `upstream-skills-check` remplace sa proposition précédente et ne propose
   rien quand le pin est déjà au tag signalé.
6. En cas de doute sur la classe, le producteur choisit `decision`. Un
   bead `maintenance` qui, en cours de travail, touche un comportement
   visible de Benjamin est arrêté et reconverti en `decision` par la porte
   de Planning Exception (ADR-0028), jamais poursuivi.

## Ce que cela ne veut pas dire

- Pas d'auto-amélioration libre : le Mayor ne lance que la correction d'un
  défaut constaté et tracé (observation, bead, mail), jamais un refactor,
  un audit ou un « pendant que j'y suis ». ADR-0017 (quatre conditions)
  reste en vigueur.
- Rien ne contourne la CI, la porte de dispatch ni la règle « jamais de
  merge rouge ».
- La décision 2026-09-25 « agents propose, Benjamin decides » reste vraie
  pour la classe `decision` ; elle est précisée, pas annulée.

## Comment une mauvaise lecture se verrait

- Une proposition `maintenance` change ce que Benjamin voit ou doit faire :
  classe mal choisie, à reconvertir (point 6).
- « Ce qui t'attend » contient encore des items sans recommandation ou sans
  champs : les points 3 et 4 ne sont pas livrés.
- Le Mayor ouvre un chantier d'amélioration sans défaut constaté sous
  `ADR-0029` : abus, à traiter comme violation de ADR-0017.

## Retour arrière

Supprimer le champ de classe dans `proposal-door` et le filtre du Cockpit ;
toutes les propositions redeviennent visibles et « agents propose, Benjamin
decides » reprend son sens de 2026-09-26. Les beads bug déjà livrés
restent livrés.

## Conséquences

- Mayor prompt : « Improvements are proposals » distingue les deux classes
  et donne la règle de choix et l'autorisation `ADR-0029` pour
  `maintenance`.
- `bin/proposal-door create` : champ `classe` obligatoire ; recommandation
  obligatoire pour `decision`.
- Cockpit : filtre de « Ce qui t'attend » (points 2 et 4), zone santé.
- Ordres producteurs (`upstream-skills-check`, `overlap-conflict-log`) :
  classe déclarée.
- Tests de contrat producteur → lecteur.
