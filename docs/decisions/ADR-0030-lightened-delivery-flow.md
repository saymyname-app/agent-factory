# ADR-0030 : alléger le flux de livraison D01

- Statut : Accepté (tranches L1–L7 livrées une par une ; chacune met à jour la section « État des tranches »)
- Date : 2026-10-15
- Autorité : décision de Benjamin en conversation (2026-10-15, 16:46 Paris), option B ; revue d'incident du convoi Cockpit `af-pqfxmd` (Spec `af-2zseit`), 2026-10-15
- Portée : flux de livraison D01 (`bin/convoy-advance`, `bin/convoy-state`, `bin/tdd-step`, `bin/test-review` (supprimé en L7), `bin/code-review`, `bin/ticket-evaluation`, `bin/planning-exception`, `config/delivery-flow.json`) ; epic `af-npz9v1`

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
   cause atteint sa borne. Coût accepté : à 7 causes bornées à 3, jusqu'à
   ~14 sessions neuves d'auteur peuvent tourner avant que Benjamin soit
   sollicité, contre 2 avant ; la mesure de L6 rapporte les reprises par
   cause et abaisse une borne qui s'avère coûteuse (par exemple `behind`).
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
  qui n'a pas atteint sa propre borne : L2 n'est pas livrée.
- Un ticket non `interface` attend une évaluation par modèle : L4 n'est pas
  livrée.

## Retour arrière

Annuler la PR de la tranche concernée ; les tranches sont indépendantes,
sauf L7 qui suppose L3–L5. Annuler toutes les PR rend le flux de
`docs/CONVOY_ADVANCE.md` d'avant le 2026-10-15.

## État des tranches

| Tranche | Bead | PR | État |
|---|---|---|---|
| L0 (cette ADR) | `af-npz9v1.1` | #617 | livrée |
| L1 | `af-npz9v1.2` | #618 | livrée : `bin/tdd-step green` lance aussi le `regression_command` du profil sur la pointe ; rouge = refus simple (ni arrêt ni reprise), donc la porte `code` de `bin/ticket-author` ne passe pas et l'auteur continue |
| L2 | `af-npz9v1.3` | #621 | livrée : `bounds.resumes` une borne par cause (3 chacune : interrupted, returned, unblocked, answered, behind, evaluation_no_result, commit_after_verdict) ; tour de correction hors K (sa borne d'un tour ; deux depuis ADR-0033) ; comptes dérivés des entrées de reprise ; une levée rend les bornes par cause |
| L3 | `af-npz9v1.5` | #626 | livrée : `bin/tdd-step freeze` et `convoy-state set-tdd` ne demandent plus de relecture des tests ; `bin/convoy-advance` n'en lance ni n'en règle aucune ; la revue de code lit les tests de critère du registre `tdd_freeze` (`tests.criterion_tests`) avec les mêmes règles de refus ; un `gc.flow.test_review` d'un ticket en vol est ignoré ; `bin/test-review`, sa formule et `docs/TEST_REVIEW.md` (marqué remplacé) restent jusqu'à L7 |
| L3 (reprise) | `af-pjvsgo` | #637 | livrée : un ticket arrêté par la relecture des tests avant L3 (`test_review_refused`, `test_review_no_result`) n'est plus laissé arrêté pour toujours : `bin/convoy-advance` le reprend une fois par arrêt sous la cause `stage_removed` (bornée comme les autres, `bounds.resumes.stage_removed` = 3), lève l'arrêt (gardé sur la reprise) et retire sa demande par `bin/escalation-door clear` ; une réponse de l'opérateur à cette demande ou l'absence de reprise restante le laisse arrêté. Cas d'origine : T59 (`af-qjq1t6`). Code de transition : la cause `stage_removed` part avec L7 une fois aucun ticket arrêté ainsi |
| L2 (reprise de revue) | `af-wu6xj7` | PR à venir | en revue : un ticket arrêté `code_review_no_result` est repris par `bin/convoy-advance` une fois par arrêt (fait `stop:<raison>/<heure>`), sous la cause `code_review_no_result` bornée comme les autres (`bounds.resumes.code_review_no_result` = 3) ; la reprise retire la demande (`bin/escalation-door clear`), garde l'arrêt sur la reprise et retire le tour de revue épuisé, pour qu'une revue neuve parte sur la sortie suivante ; une réponse de l'opérateur ou l'absence de reprise restante le laisse arrêté. Cas d'origine : T59 (`af-qjq1t6`) et T62R (`af-h385tk`), arrêtés parce que le siège du relecteur était tenu (`af-epkrcv`) |
| L2 (revue dépassée) | `af-s31cvi` | PR à venir | en revue : une revue défavorable à un commit plus ancien que la pointe, sans tour de correction pris ni réponse donnée (l'auteur a été repris hors du tour), est rejouée en entier à la pointe par `bin/code-review settle` (`convoy-state open-code-review` l'accepte) ; le tour de correction s'ouvre dès que cette revue et l'évaluation ont rendu à la même pointe. Comme après une revue favorable dépassée, la revue rejouée juge tout le diff : les anciens constats ne lui sont pas reportés. Avant : la revue attendait des réponses que seule la session du tour donne, le tour attendait une revue à la pointe, et le ticket calait. Cas d'origine : T02 (`af-0gonc9`), revue défavorable à `459d668`, repris le 17/10 jusqu'à `8fcd48a` |
| L4 | `af-npz9v1.6` | #632 | livrée : `bin/ticket-evaluation settle` n'ouvre une évaluation par modèle que pour un ticket `interface` ; tout autre ticket passe le contrôle de démarrage du prefactoring (lancement et sonde de chaque jeu nommé, préflight de cycle de vie si le ticket établit la recette), sans session, sa passe `startup` porte `model: not_required` et la porte de fin de ticket l'accepte ; une évaluation par modèle ouverte avant L4 sur un ticket sans interface est retirée (son lancement annulé) puis remplacée par ce contrôle ; un démarrage réussi ne vaut plus évaluation pour un ticket devenu `interface` (il est évalué par modèle au même commit ; un produit qui n'a pas démarré reste le verdict) ; un prefactoring qui établit la recette passe aussi le préflight de cycle de vie. Reste : pour un ticket `interface`, l'Evaluator juge encore tous les critères et non la seule ligne de démonstration (`af-npz9v1.7`, avant L7) |
| L4 (ligne de démonstration) | `af-npz9v1.7` | PR à venir | en revue : pour un ticket `interface`, l'Evaluator ne juge que la ligne de démonstration ; le brief ne porte plus que les critères qu'une attente validée compare (en général aucun) ; la passe enregistrée garde `criteria` vide ou limité à ces critères ; un état rendu pour un autre critère (Evaluator briefé avant) n'est pas enregistré ; `bin/ticket-end` exige la ligne de démonstration observée avec preuve à la pointe (condition `evaluation`) et la ligne évaluée identique à celle du ticket (condition `criteria`, empreintes gelées inchangées) ; une passe déjà enregistrée avec un état par critère se lit et passe comme avant |
| L5 | `af-npz9v1.8` | #635 | livrée : `bin/tdd-step red` enregistre un critère dont tous les tests passent au commit de départ comme satisfait par le code existant (`satisfied` dans la pièce scellée `tdd_red`, avec `base` et les issues `passed`, reporté au gel, au vert et à l'amendement) et le ticket continue ; seul un ticket dont tous les critères sont déjà verts s'arrête (`criterion_already_green`) ; un test vert dans un critère encore rouge est un refus simple, sans arrêt. Toute Planning Exception de `bin/ticket-exit` offre une option « accepter » (sans ancre : « Accepter l'écart que décrit le Ticket Handoff », dont les « Écarts » ne peuvent alors être vides) ; répondue par elle, `bin/convoy-advance` lève le parcage et reprend le ticket. Un ticket arrêté `criterion_already_green` le reste après cette levée : `bin/convoy-advance` remonte alors son arrêt à l'opérateur (`tdd_stops`) au lieu de laisser le convoi caler |
| L5 (suites) | `af-npz9v1.9` | PR à venir | en revue : l'arrêt `criterion_already_green` ne se lève plus sur une Planning Exception antérieure à l'arrêt (son `at` doit suivre celui de l'arrêt) ; un auteur dont la session finit sans en lever une ne bloque plus le convoi en silence : `bin/convoy-advance` remonte l'arrêt une fois, sans doublon quand l'auteur en lève une ; la demande de cet arrêt offre « Clore ce ticket comme satisfait par le code existant » (clôture faite dans le Planning Run : aucune porte ne ferme un ticket non fusionné) au lieu d'une seconde Planning Exception ; la conséquence de l'option « accepter » de `bin/ticket-exit` distingue le cas général (le ticket reprend) du ticket arrêté tout vert (le parcage est levé, pas l'arrêt) |
| Délai par jeu | `af-vtg5kl` | #636 | livrée : le délai d'un lancement de Ticket Evaluation vaut `max(timeout_seconds, jeux × per_dataset_seconds)` (240 s par jeu, mesuré sur T02 `af-0gonc9` : 24 jeux coupés quatre fois à 3600 s) ; un seul jeu garde 3600 s |
| Outcome Evaluation aux jeux cités | `af-npz9v1.11` | #667 | en revue : décision de Benjamin (2026-10-17, « Réduire aux jeux cités ») ; `bin/outcome-evaluation` ne couvre que les jeux déclarés que nomment les user stories numérotées de la Spec, les lignes de démonstration des tickets du convoi ou une attente validée des stories, sinon le premier jeu déclaré ; délai d'un lancement `max(timeout_seconds, jeux × per_dataset_seconds)`, même fonction que la Ticket Evaluation (240 s par jeu). Avant l'Acceptance Session, un jeu non cité n'est plus parcouru ; l'Acceptance Session elle-même ne change pas |
| L6 | — | — | à faire |
| L7 | `af-npz9v1.10` | PR à venir | en revue : voir « L7 — ce qui est supprimé, ce qui reste » |

## L7 — ce qui est supprimé, ce qui reste

Audit (2026-10-16) des chemins de D01 rendus morts par L3–L5, vérifiés
contre le code, les formules, les agents, les tests et les données vivantes
de Beads (lecture seule : 8 tickets portent un `gc.flow.test_review`, un
seul arrêt `test_review_no_result`, sur `af-qjq1t6`, en cours ; aucun
`gc.flow.verdict.test_review`, aucun arrêt `test_review_refused`, aucune
molécule `mol-test-review` ouverte).

Supprimé (producteurs et répartiteurs sans appelant depuis L3) :
`bin/test-review`, `formulas/mol-test-review.formula.toml` (et sa place
dans `config/projects/agent-factory.toml`), le bloc `test_review` de
`config/delivery-flow.json`, `docs/TEST_REVIEW.md` et ses entrées de
catalogue, `tests/test-review-test.py`,
`tests/test-review-isolated-city-test.sh`, `tests/fixtures/test-review/` ;
dans `bin/convoy-state`, `open-test-review`, `launch-test-review`,
`record-test-review` et leurs aides ; le genre de verdict `test_review`
(jamais écrit). La raison d'arrêt `test_review_refused` (jamais écrite en
vrai) reste lisible, comme `test_review_no_result` : la reprise
`stage_removed` (#637) les lit toutes deux. Les suites qui posaient une relecture pour pouvoir geler ne la posent
plus ; celles qui lisent un relevé d'avant L3 l'écrivent dans le faux
tracker (`tests/lib/ticket_proofs.py pre_l3_test_review`). L'essai
`tests/fresh-sessions-isolated-city-test.sh` garde son étape « N auteurs en
parallèle » ; sa moitié relecteur passait par `bin/test-review` et part avec
lui. Le refus d'une session qui a déjà servi reste, pour la revue de code et
la Ticket Evaluation, testé par `tests/code-review-test.py` et
`tests/ticket-evaluation-test.py` ; son texte passe de `TEST_REVIEW.md` à
`docs/CODE_REVIEW.md`.

Gardé, lu seulement (un ticket en vol peut le porter) : le relevé
`gc.flow.test_review` (`show`, le contrôle de session neuve, l'Evidence
Pack), la raison d'arrêt `test_review_no_result` et sa remontée par
`bin/convoy-advance` (`af-qjq1t6` en porte une). Aucune porte déterministe
n'est touchée : la preuve rouge/gel et le registre du harnais gelé vivent
dans `bin/tdd-step`, pas dans `bin/test-review`.

Gardé, pas encore mort :
- Couverture de l'évaluation par modèle (tous les critères jugés) : encore
  vivante pour un ticket `interface` tant que `af-npz9v1.7` n'est pas livrée.
- Planning Exception sans option « accepter » : plus aucune n'est levée
  (L5), mais la forme sans `accept_option` reste lue pour celles levées avant
  L5 ; rendre `--accept-option` obligatoire serait un durcissement, pas une
  suppression.

Retour arrière : annuler la PR de L7.
