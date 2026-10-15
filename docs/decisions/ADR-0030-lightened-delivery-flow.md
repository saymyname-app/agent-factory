# ADR-0030 : alléger le flux de livraison D01

- Statut : Accepté (tranches L1–L7 livrées une par une ; chacune met à jour la section « État des tranches »)
- Date : 2026-10-15
- Autorité : décision de Benjamin en conversation (2026-10-15, 16:46 Paris), option B ; revue d'incident du convoi Cockpit `af-pqfxmd` (Spec `af-2zseit`), 2026-10-15
- Portée : flux de livraison D01 (`bin/convoy-advance`, `bin/convoy-state`, `bin/tdd-step`, `bin/test-review`, `bin/code-review`, `bin/ticket-evaluation`, `bin/planning-exception`, `config/delivery-flow.json`) ; epic `af-npz9v1`

Intent (Benjamin, ses mots, 2026-10-15 16:46) : « Ok allegeons et ameliorons
notre usine stp. Je ne sais pas exactement comment, mais il faut l'ameliorer
avec tes constats. » Il répondait à trois options : A garder D01 tel quel,
B alléger D01 et y garder le Cockpit, avec échéance, C livrer le Cockpit en
Direct Delivery. Il a choisi B.

Mechanism (interprétation agent) : garder ce qui a trouvé de vrais défauts
ou ce qui est déterministe et peu coûteux ; réduire ou retirer ce qui n'a
rien trouvé et a coûté des heures ou des décisions de Benjamin.

## Contexte

Quatre jours de convoi Cockpit (`af-pqfxmd`), ticket T01 et ses remplaçants
T01R1 à T01R6 :

| Étape | Ce qu'elle a trouvé | Ce qu'elle a coûté | Verdict |
|---|---|---|---|
| Revue de code (session neuve, `bin/code-review`) | De vrais défauts : T01 (un seul état pour 95 datasets), T01R3, T01R4 F1.1 | Une session par ticket | Garder |
| Régression sur la branche d'intégration (`bin/spec-integration`) | Un vrai défaut : T01R6 casse `tests/cockpit-core-test.py` (vert sur main et sur l'intégration 28f86df, rouge sur la pointe du ticket 7cf5cdd) | Déterministe, peu coûteux | Garder ; mais l'auteur, la revue et l'évaluation l'avaient tous manqué |
| Ticket Evaluation par modèle (`bin/ticket-evaluation`) | Aucun défaut que la revue avait manqué ; 1 avis favorable à tort (T01) ; 4 arrêts sans résultat | De 4 min à 7 h par ticket | Réduire |
| Borne de reprises K=3, toutes causes confondues ; Planning Exception sans option « accepter » quand elle ne nomme ni ancre ni élément | Aucune question produit | 7 décisions de Benjamin en 4 jours, 2 à 13 h de blocage chacune | Refaire |
| Relecture des tests avant le gel (`bin/test-review`) puis revue de code après | — | Deux sessions de relecture neuves par ticket | Fusionner |

## Décision

Sept tranches (L1–L7), chacune une bead enfant de `af-npz9v1`, une PR, réversible en
annulant sa PR :

1. **L1 — La régression avant le handoff.** Au handoff de l'auteur (la
   couture la plus étroite entre `bin/tdd-step green` et la fin de
   `mol-ticket-author`), le `regression_command` du profil tourne sur la
   pointe du ticket. Rouge : l'auteur continue dans la même session ; ce
   n'est ni un arrêt ni une reprise.
2. **L2 — Les reprises bornées par cause.** `bounds.resumes` de
   `config/delivery-flow.json` devient une borne par cause (`interrupted`,
   `returned` par une fusion rouge, `evaluation_no_result`, …). Une fusion
   rouge sur un défaut de code renvoie à l'auteur sans consommer le budget
   d'interruption. Un ticket n'est parqué pour Benjamin que lorsqu'une même
   cause dépasse sa borne.
3. **L3 — Une seule relecture.** La relecture des tests rejoint la revue de
   code : la preuve rouge/gel reste déterministe (`bin/tdd-step`, contrôle
   du harnais gelé conservé) ; un seul relecteur neuf lit les tests de
   critère et le code après le vert, avec les mêmes règles de refus (un
   constat bloquant cite un critère du ticket ou une règle du dépôt).
   L'étape `test_review` sort du flux.
4. **L4 — L'évaluation par modèle là où elle sert.** Seuls les tickets
   marqués `interface` sont évalués par modèle, et seulement sur la ligne de
   démonstration et les datasets que le ticket nomme ; les critères sont déjà
   prouvés par les tests de critère gelés. Les autres tickets enregistrent un
   verdict « non requis », de façon déterministe. La sonde de lancement reste.
5. **L5 — Pas de Planning Exception sans chemin « accepter ».** Un critère
   déjà vert au moment du rouge est enregistré comme satisfait par le code
   existant (preuve : le test passe au commit de base) et le ticket continue
   avec ses autres critères ; il ne s'arrête que si tous ses critères sont
   déjà verts. Toute demande de Planning Exception offre une option
   « accepter ». Benjamin n'est sollicité que pour une question d'intention
   ou de produit.
6. **L6 — Mesurer.** Avant/après par ticket (sessions, durée, décisions de
   Benjamin) : L6 ajoute ces champs à la ligne quotidienne de
   `bin/factory-metrics` (`var/factory-metrics.jsonl`), qui ne porte
   aujourd'hui que les tickets fusionnés, les tentatives et un ratio
   journalier de tokens.

Puis **L7** : supprimer en une PR le code de D01 devenu mort après L3–L5
(étape de relecture des tests, branches de couverture de l'évaluation).

## Ce qui reste

- Toute porte déterministe : preuve rouge/gel et K exécutions vertes
  (`bin/tdd-step`), harnais gelé, régression sur le résultat fusionné,
  porte de fin de ticket, verdicts mécaniques de fin de Spec.
- Une revue de code par une session neuve avant chaque fusion.
- Ce que Benjamin approuve ou accepte : approbation de la Spec, du graphe,
  Acceptance Session. Ces points sont hors de cette ADR ; les changer
  demande sa décision.

## Échéance

Une fois L1 à L5 fusionnées, le convoi Cockpit doit fusionner au moins
3 tickets dans `integration/af-2zseit` en 48 h sans décision de Benjamin,
mesuré par `var/factory-metrics.jsonl` (champ des décisions ajouté par L6). Sinon, le bilan recommande de passer
le Cockpit en Direct Delivery (option C), ce qui reste sa décision.

## Comment une mauvaise lecture se verrait

- Une porte déterministe est affaiblie ou retirée par une tranche : hors de
  cette ADR.
- Un ticket fusionne un rouge que son auteur aurait vu au handoff : L1 n'est
  pas livrée.
- Benjamin reçoit encore une demande sur un ticket parqué par une cause
  qui n'a pas dépassé sa propre borne : L2 n'est pas livrée.
- Un ticket non `interface` attend une évaluation par modèle : L4 n'est pas
  livrée.

## Retour arrière

Annuler la PR de la tranche concernée ; les tranches sont indépendantes,
sauf L7 qui suppose L3–L5. Annuler toutes les PR rend le flux de
`docs/CONVOY_ADVANCE.md` d'avant le 2026-10-15.

## État des tranches

| Tranche | Bead | PR | État |
|---|---|---|---|
| L0 (cette ADR) | `af-npz9v1.1` | — | en cours |
| L1 | — | — | à faire |
| L2 | — | — | à faire |
| L3 | — | — | à faire |
| L4 | — | — | à faire |
| L5 | — | — | à faire |
| L6 | — | — | à faire |
| L7 | — | — | à faire |
