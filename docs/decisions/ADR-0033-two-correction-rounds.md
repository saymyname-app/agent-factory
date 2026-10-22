# ADR-0033 : deux tours de correction par ticket

- Statut : Accepté
- Date : 2026-10-21
- Autorité : Benjamin en conversation (2026-10-21, vers 22:50 Paris) ; mise en œuvre `af-bv0ikr`
- Portée : `bin/correction-round`, `bin/convoy-state` (`open-correction`, `grant-correction`, `open-code-review`), `bin/code-review`, `config/delivery-flow.json` (`bounds.correction_rounds`), formule `mol-ticket-correction`
- Remplace, pour le nombre de tours : « un seul tour de correction » d'ADR-0030 (L2) et de la Spec D01 (`af-wf4w5r` §8)

Intent (Benjamin, ses mots, 2026-10-21 vers 22:50 Paris) : « B. Deux tours
(Recommandé) », à la question « Règle des tours de correction : laquelle ? »,
dont l'option disait : deux tours de correction automatiques et un amendement
de tests par tour avant de te remonter un ticket ; C1 et D repartent seuls,
sans dérogation.

Mechanism (interprétation agent) : la borne `bounds.correction_rounds` vaut 2
(absente : 1) ; encore refusé après un tour qui en laisse un, le ticket prend
le suivant, rassemblé comme le premier ; un tour ouvert après le dernier
amendement autorise un amendement (af-vsni1n, inchangé), donc un amendement
par tour ; un ticket arrêté sous l'ancienne règle reçoit son second tour par
`correction-round grant`, avec les mots de l'approbateur.

## Contexte

Mesure du 21/10 (`bin/convoy-state show`) :

- Ancien convoi Cockpit `af-pqfxmd` : 12 tickets démarrés, 4 fusionnés (dont
  un par dérogation). 9 sont passés par le tour unique ; 2 seulement ont
  ensuite été acceptés sans l'opérateur. 5 arrêts « encore refusé », 4
  « évaluation sans résultat » (lancement, corrigé depuis).
- Convoi `af-strhoy` : 5 tickets démarrés, 0 fusionné ; la revue a refusé les
  5 au premier passage (8 à 12 constats bloquants chacun). C1 (`af-lzti7w`)
  était accepté à 10:26 Paris ; renvoyé par une fusion rouge due à la lenteur
  de la VM, sa revue rejouée a trouvé 5 constats nouveaux, dont un présent au
  commit accepté, et il s'est arrêté. G1 (`af-wrxrmg`) : même renvoi, puis
  amendement épuisé. D (`af-ten1sp`) : 2 constats restés après son tour.

Deux causes : une revue rejouée juge tout le diff et trouve du nouveau d'un
passage à l'autre ; un renvoi causé par l'usine consomme le budget du ticket.

Variantes présentées : garder la règle ; deux tours ; deux tours et une
seconde revue limitée aux constats déjà donnés et au code changé ; seulement
rendre un tour après un renvoi causé par l'usine. Benjamin a choisi la
deuxième.

## Décision

1. `bounds.correction_rounds = 2` dans `config/delivery-flow.json`.
2. `bin/correction-round settle` : encore refusé après un tour qui en laisse
   un, attend que les deux contrôles aient rendu à la pointe, puis ouvre le
   tour suivant et l'envoie à une session neuve d'auteur ; après le dernier,
   arrête le ticket comme avant.
3. Un tour ouvert sur un jugement défavorable reprend les constats que le
   jugement garde ; il n'y répond pas : la revue est rejouée en entier sur sa
   pointe. Un tour ouvert sur une revue rejouée se répond et se juge comme le
   premier.
4. `bin/correction-round grant` lève, avec les mots de l'approbateur
   déclaré, l'arrêt `still_refused` d'un ticket qui a encore un tour, et
   retire sa demande.

## Conséquences

Un ticket difficile coûte jusqu'à une session d'auteur, une revue et une
évaluation de plus avant d'arriver à l'opérateur. La revue pouvant trouver
du nouveau au second tour, des arrêts restent possibles : si les seconds
tours en trouvent régulièrement, la variante « seconde revue ciblée » se
décide sur cette mesure. Revenir en arrière : `bounds.correction_rounds = 1`.

## Preuve

`tests/correction-round-test.py` : un second tour s'ouvre après un jugement
défavorable et après une revue rejouée ; encore refusé après lui, le ticket
s'arrête ; `grant` lève un arrêt pris sous un seul tour et le tour suivant
part. Les tests d'un seul tour tournent sous `correction_rounds = 1`.
