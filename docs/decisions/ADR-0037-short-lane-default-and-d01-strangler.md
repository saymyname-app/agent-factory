# ADR-0037 : la voie courte devient le flux par défaut ; D01 est retiré composant par composant (strangler)

- Statut : Accepté
- Date : 2026-11-16
- Autorité : Benjamin, session Claude Code Windows 1e93b356 « Analyse totale de l'usine », 16/11/2026 entre 16:38 et 16:50 Paris ; consigné sur `af-q55qqx`, décision 7
- Portée : l'ordre `convoy-advance` (mis en pause), `agents/mayor/prompt.template.md` (convois du nouveau flux), toute publication d'un graphe de tickets
- Suspend : ADR-0030 à ADR-0035 pour tout nouveau convoi, jusqu'à la porte J14 ci-dessous
- Cible : `FACTORY_OBJECTIVE.md`

Intent (Benjamin, ses mots, 16/11/2026) : « Voie courte + hybride ».
Contenu tranché dans `af-q55qqx` : bead → PR → CI → revue par un autre
fournisseur → fusion automatique sur `dev` ; les nouveaux convois D01 sont
mis en pause, sans arrêter le superviseur ; chaque composant D01 a une date
d'extinction, sauf preuve qu'il attrape des défauts ; points de bascule
entre J6 et J8, puis à J14.

Mechanism (interprétation agent) : les points 1 à 4 ci-dessous. Les étapes
J du plan (§10 du rapport, en commentaire de `af-q55qqx`) sont comptées en
jours ouvrés à partir de J0 = lundi 16/11/2026 ; les dates en découlent.

## Contexte

En 65 jours, la voie courte (PR → CI → fusion automatique, ADR-0026) a
fusionné 871 PR, médiane 18 min. Le flux D01 des convois n'a mis aucune
story sur `main` en 27 jours : 400 commits sur une branche d'intégration,
une revue de fin qui ne converge pas, aucun code SayMyName fusionné depuis
le 25/09. À périmètre égal, rien ne montre encore que D01 attrape des
défauts que la voie courte laisse passer (rapport, §3 et §4).

## Décision

1. **Flux par défaut : la voie courte.** Un travail prêt devient un bead,
   puis une PR, la CI du dépôt, une revue neuve par un autre fournisseur
   bornée à la spec, la sécurité et les données, et la fusion automatique
   sur `dev` (produit) ou `main` (usine). La promotion `dev` → `main` d'un
   produit reste à Benjamin. Aujourd'hui (CONFIGURED) : PR → CI → fusion
   automatique par `bin/pr-autopilot` ; la revue par un autre fournisseur
   arrive avec la formule « tranche courte » (J4) et le retour du second
   fournisseur (décision 8 de `af-q55qqx`, geste de Benjamin) ; d'ici là,
   une revue est faite par une session neuve et enregistrée comme du même
   fournisseur.
2. **Aucun nouveau convoi D01.** L'ordre `convoy-advance` est en pause
   depuis le 16/11/2026 16:52 Paris (`bin/order-pause`, enregistrement
   `af-t365z6`) ; le superviseur et les autres ordres tournent. Aucun graphe
   n'est plus publié avec la marque du nouveau flux (`gc.flow.mark`) : un
   nouveau travail part en beads ordinaires sur la voie courte. Le seul
   convoi marqué ouvert, `af-strhoy`, ne bouge plus ; il atterrit par une
   PR à J1 (décision 5 de `af-q55qqx`). La reprise de l'ordre
   (`bin/order-pause resume convoy-advance`) n'est permise que par une
   bascule du point 3, ou par le revert de cet ADR.
3. **Points de bascule.**
   - **J6–J8, du mardi 24 au jeudi 26/11/2026 :** 5 tranches SayMyName sur
     la voie courte et le rejeu de 5 tickets de `af-strhoy`, jugés par la
     même revue tierce. Seuils : délai médian ≤ 24 h, ≤ 30 min de Benjamin
     par tranche, ≤ 1 défaut échappé sur 5. Si la voie courte laisse passer
     au moins 2 défauts sur 5 qu'une porte D01 aurait attrapés, la porte
     D01 en cause est gardée, en version bornée.
   - **J14, vendredi 04/12/2026 :** pour chaque composant du tableau, une
     seule question : sur J6–J8 et le rejeu, a-t-il attrapé un défaut que la
     voie courte a manqué ? Non : il est retiré. Oui : il est gardé borné
     (une passe, seulement le delta, gravité figée, « je ne sais pas »
     permis, relecteur d'un autre fournisseur), avec une nouvelle date
     d'extinction écrite. Si rien ne prouve sa valeur, l'hybride devient une
     refonte minimale, et on l'assume. Cible : machinerie sous 30 000 lignes.
   La décision de bascule est technique, donc déléguée (ADR-0036) : la
   session opérateur la prend sur ces mesures, l'enregistre et la met dans
   le rapport du jour.
4. **Dates d'extinction.** Sauf preuve de valeur enregistrée à J14, chaque
   composant est retiré par une PR fusionnée au plus tard le vendredi
   11/12/2026 :

| Composant D01 | Code principal | Extinction |
|---|---|---|
| Ticket Evaluation (évaluation par modèle du ticket) | `bin/ticket-evaluation` | 11/12/2026 |
| Outcome Evaluation par modèle (pas l'acceptation de Benjamin) | `bin/outcome-evaluation` | 11/12/2026 |
| Revue de fin sur le diff assemblé | `bin/spec-end-review` | 11/12/2026 |
| Fidélité au prototype | `bin/prototype-fidelity`, `bin/prototype-conformance` | 11/12/2026 |
| Revue de graphe en deux passes | `bin/graph-review` | 11/12/2026 |
| Planning Exception | `bin/planning-exception` | 11/12/2026 |
| Tours de correction (ADR-0033 à 0035) | `bin/correction-round` | 11/12/2026 |
| Branches d'intégration | `bin/spec-integration`, `lib/integration_maintenance.py` | 11/12/2026 |
| Avance des convois et son état | `bin/convoy-advance`, `lib/convoy_state.py`, `bin/convoy-state` | 11/12/2026 |

Le test rouge prouvé par code (`bin/tdd-step`) n'est pas dans ce tableau :
l'architecture cible le garde. L'essai de la primitive amont `drain` (J13)
peut remplacer plus tôt la distribution de `convoy-advance`.

## Ce qui est retiré

Une règle ajoutée en retire une (`FACTORY_OBJECTIVE.md`, principe 5). Ce
contrat retire, pour tout nouveau travail, le flux D01 comme flux par
défaut et les règles des ADR-0030 à 0035, qui ne s'appliquent plus qu'au
convoi `af-strhoy` déjà ouvert et figé.

## Conséquences

- Le produit repart par la voie courte dès J5 (`af-zk6jl`, `dev`).
- Pendant trois semaines, deux systèmes coexistent ; le code D01 reste en
  place mais ne tourne plus. Le risque d'inertie est borné par les dates du
  tableau.
- Retour arrière : `bin/order-pause resume convoy-advance --by <acteur>
  --words "<raison>"` relance l'ordre ; le revert de la PR de cet ADR rend
  au flux D01 son statut.
