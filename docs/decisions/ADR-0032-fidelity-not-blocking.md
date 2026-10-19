# ADR-0032 : la fidélité au prototype ne bloque plus la livraison

- Statut : Accepté
- Date : 2026-10-19
- Autorité : Benjamin en conversation (2026-10-19, 16:39, 17:06 et 17:16 Paris) ; décision `af-hcriwn`, mise en œuvre `af-ledn95`
- Portée : `bin/ticket-end` (condition 4), `bin/spec-end` (condition 3), `bin/correction-round` (arrêt sur fidélité rouge, af-ckbood)
- Remplace, pour ce qui bloque : la « combinaison B » de la Spec D01 (`af-wf4w5r` §3, user story 18)

Intent (Benjamin, ses mots, 2026-10-19 16:39) : « Fidélité visuelle : ce qui
s'affiche doit ressembler au prototype, pas les noms internes du code. » Puis,
17:06 : « il faudrait pas être un peu plus permissif sur les visuels, et
peut-être ensuite on repasse plus tard » ; 17:16, sur la proposition
« fidélité non bloquante avec une passe de finition à la fin » : « je valide ».

Mechanism (interprétation agent) : la mesure tourne et reste jointe ; aucune
porte ne s'arrête sur elle ; une passe de finition visuelle, un ticket unique,
est jugée par Benjamin sur le dossier de fin.

## Contexte

T02, T02R et T02R2 (Prototype Fold de la Vue d'ensemble du Cockpit, dont
dépendent les autres tickets d'interface) ont été rouges trois fois sur la
fidélité. T02R2 au commit 99fa5cb9 : 2 392 écarts (noms de tokens, ancres
`data-anchor`, styles calculés, police), alors que ses captures en thème
sombre sont à l'œil presque identiques au prototype. Une calibration d'un
score visuel par pixels (`af-ledn95`) n'a pas séparé un livré proche (3 à 9 %)
d'un état faux (9 %) : aucun seuil de code ne remplace l'œil.

## Décision

1. `bin/ticket-end` condition 4 est toujours remplie ; son détail dit ce qui
   a été mesuré à la pointe (vert, nombre d'écarts joints, ou pas de mesure).
   La pièce de fidélité n'est exigée par la condition 7 que si elle est à la
   pointe.
2. `bin/correction-round` n'arrête plus un ticket pour une fidélité rouge.
3. `bin/spec-end` condition 3 est toujours remplie ; une mesure impossible
   est dite, pas rouge.
4. `bin/ticket-exit` ne refuse plus « terminé » sur une fidélité rouge et ne
   la mesure plus à la sortie (refus de `af-fho3ka`, PR #681, retiré le même
   jour) ; `bin/ticket-exit fidelity` la mesure pour information, code 0.
5. `bin/prototype-fidelity` et ses captures ne changent pas : les écarts sont
   lus dans le dossier de fin pour la passe de finition.

## Conséquences

Des écarts visuels peuvent s'accumuler d'un ticket à l'autre ; Benjamin les
voit ensemble à la fin. Revenir en arrière : revert de la PR de `af-ledn95`.
Un juge visuel (modèle ou code) pourra être décidé plus tard, au vu de la
passe de finition.

## Preuve

`tests/ticket-end-test.py`, `tests/spec-end-test.py`,
`tests/correction-round-test.py` : une fidélité rouge à la pointe laisse la
condition remplie et n'arrête pas le ticket.
