# Quels tests de la batterie sont pertinents, lesquels font double emploi

Ticket af-8km43c.8 (carte af-8km43c), 2026-10-10, heures de Paris. Lecture seule : aucun test lancé, rien modifié.

## Résumé

1. Historique de CI (1 081 runs, du 2026-09-15 21:47 au 2026-10-10 00:24) : 86 exécutions rouges. 17 des 21 fichiers longs (4 384 s sur 6 694) n'y ont jamais été rouges ; 4 l'ont été, chaque fois pour un vrai défaut du changement.
2. Cette preuve est faible : 20 des 21 fichiers longs ont entre 1 et 4 jours, et jusqu'au 2026-10-08 22:35 la batterie était lancée à la main avant la PR, donc les rouges n'arrivaient pas en CI.
3. Les rouges de CI viennent surtout des tests courts : catalogue ou liste périmés (22 exécutions), tests du Cockpit instables sous charge (13), règles écrites violées (11).
4. Aucun fichier long n'est un double exact d'un autre. Le double emploi est d'une autre nature : la même règle est prouvée à 2 ou 3 étages, et chaque étage refait tout le décor par des lancements réels.
5. Classement des 21 fichiers longs : garder tel quel 1 263 s (8 fichiers) ; accélérer sans changer les vérifications 4 313 s (11) ; descendre d'un étage 523 s (1) ; fusionner ou retirer en partie, preuve manquante, 595 s (1) ; retrait d'un fichier entier 0 s.
6. Forme de la batterie : aucun test « petit » (un seul processus) parmi les 6 694 s ; 2 314 s (31 %) aux deux étages les plus hauts. C'est la forme que les sources déconseillent.
7. Cause : la consigne. La Spec af-wf4w5r et la clause `test_method` de chaque ticket demandent « un test par refus et par passage » en ligne de commande et « tout critère qui peut être observé [au plus haut] y est observé ». Aucune consigne ne parle de durée, d'étage ni de décor partagé.
8. Mesure qui prouverait un retrait : mutation par échantillon (100 mutants d'un outil, environ 10 h de PC au repos pour la question « convoy-stops peut-il partir »). La mutation complète est hors de portée (des semaines de calcul).
9. Constat annexe : l'étape de CI « Syntax check » ne peut pas échouer sur un script shell (`|| true`) ; le 2026-10-06 une erreur de syntaxe de `bin/escalation-door` y a été affichée puis a rougi 8 fichiers de test.

## Vocabulaire

| Mot | Sens ici |
|---|---|
| Fichier long | fichier de test de 100 s ou plus dans `config/ci-test-seconds.tsv` (21 fichiers) |
| Étage | niveau où un test entre dans le code : fonction appelée dans le même processus (bas), ligne de commande d'un outil (milieu), parcours du flux entier (haut) |
| Seam | point d'entrée convenu pour tester (mot de la Spec af-wf4w5r). Seam 1 : Fixture City Oracle, le projet d'essai qui parcourt tout le flux. Seam 2 : la ligne de commande de chaque outil sur un faux tracker |
| Décor | l'état qu'un test construit avant de vérifier (dépôt Git jetable, faux tracker, ticket amené à un stade donné) |
| Test instable | rouge puis vert sur le même commit, sans changement |
| Test de mutation | on introduit une faute dans le code ; si aucun test ne rougit, la ligne n'est pas réellement vérifiée |
| Exécution rouge | une tentative de run en échec (un run relancé compte une fois par tentative) |

## 1. Ce que dit l'historique de CI

Source : `gh api repos/saymyname-app/agent-factory/actions/workflows/ci.yml/runs` (1 081 runs, tous ceux que GitHub garde), jobs en échec de chaque tentative, journal de chaque job. Chiffres de `config/ci-test-seconds.tsv` revérifiés sur `origin/main` (6122051) : 161 fichiers, 7 535 s, 21 fichiers de 100 s ou plus = 6 694 s (88,8 %).

Fenêtre : 2026-09-15 21:47 → 2026-10-10 00:24. 951 runs verts, 71 rouges, 58 annulés, 1 en cours ; 14 runs relancés. 86 exécutions rouges en comptant les tentatives.

### 1.1 Les 86 exécutions rouges, par cause

| Cause | Exécutions | Fichiers | Verdict |
|---|---|---|---|
| Liste d'inscription des tests périmée | 15 | `ci-registration-test.sh` (« runs nowhere — add it to ci.yml ») | catalogue périmé ; la découverte automatique des tests l'a remplacée le 2026-09-29, plus aucun rouge depuis |
| Catalogue généré périmé | 5 (+1 dans un run annulé) | `generate-docs-catalogue-test.py` | catalogue périmé |
| Index ou budget de contexte | 8 | `operator-context-test.sh` (AGENTS.md au-delà de 8 Ko ×5, index des ADR incomplet ×2, prompt qui nomme un projet ×1) | 2 catalogues périmés, 6 règles violées : vrai défaut |
| Règles écrites | 5 | `sandbox-isolation-check-test.sh` ×3, `bin-stderr-lint-test.py` ×2 | vrai défaut |
| Ancien test du Cockpit (fichier disparu) | 7 | `factory-cockpit-test.py` | vrai défaut de données, 3 fois sur `push` à main (même défaut que la PR) |
| Cockpit, attente dépassée ou connexion refusée | 13 | `cockpit-actions-test.py` ×8 (« condition not met within 5s »), `cockpit-core` ×2, `cockpit-health` ×2, `cockpit-depots` ×1 | instable : 4 fois vert sur le même commit ; les autres, même message, non relancés |
| Test instable hors Cockpit | 6 | `factory-dispatch-guard-test.sh` ×4 (3 tentatives rouges puis verte, même commit), `role-qualification-oracle-test.py` ×2 (ordre d'un dictionnaire) | instable |
| Vrai défaut vu par un test court | 10 | `provider-failover` ×2, `ticket-graph-publish-test` ×2, `saymyname-product-status` ×2, `factory-work-dispatch` ×2, `factory-live-root-guard` ×1, `factory-guard-liveness` ×1 | vrai défaut |
| Environnement du runner | 13 | quota de minutes épuisé (6 runs, 2026-10-08 02:37 à 06:35), runner du PC perdu (2), `bwrap` interdit sur le runner (2, oracle), certificat (1), `gc` absent (1), sonde d'isolement (1) | pas un test |
| Vrai défaut vu par un fichier long | 5 | voir 1.2 | vrai défaut |

Total 86 : la somme des lignes fait 87, un run (2026-10-07 12:16) portant deux causes.
Le décompte par cause est le mien, fait sur le message d'échec de chaque journal ; il n'a pas été relu par un second lecteur.

### 1.2 Les fichiers longs dans cet historique

| Fichier long | Rouge en CI | Quand, sur quelle PR | Nature | Seul à le voir ? |
|---|---|---|---|---|
| `fixture-city-oracle-test.py` | 1 (+2 d'environnement le 2026-09-23) | 2026-10-08 17:09, `do-work/af-ji2ruy` (T25, revue de fin) | vrai défaut : la nouvelle condition « revue de fin » cassait le parcours entier (« revue de fin absente ») | oui : aucun autre fichier rouge dans ce run |
| `tdd-step-test.py` | 2 | 2026-10-09 20:14 et 21:03, `do-work/af-kwodm8` | vrai défaut : 5 cas `prefactoring` ne trouvaient plus `tests/regression.py` du projet d'essai | oui |
| `spec-integration-test.py` | 1 | 2026-10-06 19:17, `do-work/af-gmz9s1` (T18) | vrai défaut, sur la PR qui crée l'outil et son test (10 cas) | oui |
| `convoy-advance-test.py` | 1 | 2026-10-06 13:58, `maint/escalation-door-clear-date` | vrai défaut : erreur de syntaxe dans `bin/escalation-door` (10 cas) | non : 7 fichiers courts rouges dans le même run |
| Les 17 autres | 0 | | | |

Jamais rouges en CI (17 fichiers, 4 384 s) : `convoy-stops-fixture-city` 595, `convoy-state` 523, `ticket-evaluation` 504, `outcome-evaluation` 291, `owner-answer` 290, `evidence-pack` 266, `code-review` 250, `ticket-graph-publish-coverage` 213, `correction-round` 209, `ticket-exit` 204, `ticket-author` 198, `test-review` 180, `ticket-end` 153, `spec-end-review` 145, `prototype-fidelity` 124, `acceptance-session` 121, `spec-end` 118.

### 1.3 Limites de cette preuve

| Limite | Effet |
|---|---|
| Âge : `fixture-city-oracle-test.py` date du 2026-09-23 ; les 20 autres ont été créés entre le 2026-10-06 06:07 et le 2026-10-09 02:54 | « jamais rouge » porte sur 1 à 4 jours |
| Jusqu'au 2026-10-08 vers 22:35, une livraison lançait la batterie entière avant sa PR (`docs/DELIVERY.md`) | les rouges des fichiers longs étaient vus et corrigés avant la CI ; ils ne sont dans aucun journal lu ici |
| 26 journaux de jobs absents (quota, runner perdu) ; 15 jobs de runs annulés sans journal | aucun test n'y a tourné, ou résultat inconnu |
| Les fichiers longs ne tournent pas sur une PR qui ne touche que `docs/` ou le Cockpit (depuis le 2026-10-08) | moins d'occasions de rougir |

Conclusion bornée : l'historique prouve que 3 fichiers longs ont été seuls à voir un vrai défaut (oracle, tdd-step, spec-integration). Il ne prouve l'inutilité d'aucun des 17 autres.

## 2. Ce que chaque fichier long est seul à vérifier

Lecture statique sur `origin/main` : en-tête de chaque fichier, outils réels nommés, noms des 1 184 cas des 21 fichiers (53 % des 2 217 cas Python de la batterie pour 89 % du temps, soit 5,7 s par cas), corps des cas appariés.

### 2.1 Fait de structure

Les outils du flux sont des scripts d'un seul fichier dans `bin/` (500 à 2 600 lignes), qui se lancent entre eux par ligne de commande : `bin/convoy-advance` nomme 14 autres outils, `bin/ticket-evaluation` 6, `bin/spec-end` 7. Un seul a son code dans un module importable : `bin/convoy-state` (24 lignes) appelle `lib/convoy_state.py` (6 860 lignes, `main(argv)`).

Conséquence : sauf pour `convoy-state`, il n'existe pas aujourd'hui d'étage plus bas que la ligne de commande. « Descendre d'un étage » demande donc, pour 20 fichiers sur 21, soit de charger le script comme module (les tests le font déjà entre eux par `SourceFileLoader`), soit de changer le code.

Autre conséquence : le test d'un outil construit son décor avec les vrais outils d'amont. `ticket-evaluation-test.py` nomme 8 outils réels, `correction-round-test.py` 9, `spec-end-test.py` 12. Ce sont des tests d'intégration larges, pas des tests d'un outil.

### 2.2 Tableau des 21 fichiers

| Fichier | s | Cas | s/cas | Seul à vérifier | Déjà vérifié ailleurs | Décor |
|---|---|---|---|---|---|---|
| `convoy-advance-test.py` | 923 | 135 | 6,8 | l'ordre des démarrages, le plafond N, les arrêts et reprises du convoi, les incidents | l'issue de chaque outil appelé (revue de fin sans résultat, sortie « interrompu », pas de fermeture par PR fusionnée) est aussi dans le fichier de l'outil | refait par cas ; `ticket_proofs` |
| `fixture-city-oracle-test.py` | 796 | 45 | 17,7 | le flux entier du graphe publié à l'acceptation ; 22 cas plus anciens sur la publication et l'isolement | l'abandon et l'acceptation du convoi : aussi dans `convoy-stops` et `owner-answer` | un parcours entier par cas |
| `convoy-stops-fixture-city-test.py` | 595 | 28 | 21,3 | les arrêts sur le graphe réel de la Fixture City, publié par la vraie porte | chaque arrêt est déjà dans `convoy-advance-test` sur faux tracker ; la fin de Spec dans `spec-end-test`, l'acceptation dans l'oracle | publication et décor refaits par cas |
| `convoy-state-test.py` | 523 | 303 | 1,7 | toutes les règles d'écriture de l'état | 9 refus au moins sont re-prouvés par le fichier de l'outil qui écrit | léger, mais 2 lectures de plus par refus |
| `ticket-evaluation-test.py` | 504 | 58 | 8,7 | les verdicts de l'évaluation d'un ticket | cycle lancement, relance, arrêt : même forme que 4 autres outils | refait par cas ; `ticket_proofs` |
| `spec-integration-test.py` | 406 | 65 | 6,2 | la fusion d'un ticket dans la branche d'intégration | refus « sans branche d'intégration » aussi dans `convoy-state-test` | refait par cas ; `ticket_proofs` |
| `outcome-evaluation-test.py` | 291 | 37 | 7,9 | l'évaluation de fin | cycle lancement, relance, arrêt | harnais de `spec-end-test` |
| `owner-answer-test.py` | 290 | 35 | 8,3 | l'enregistrement de la réponse de Benjamin | refus « autre que l'approbateur déclaré » : même forme dans `correction-round-test` | harnais repris |
| `evidence-pack-test.py` | 266 | 29 | 9,2 | la page du dossier de preuves | | instantané (`stage`) |
| `code-review-test.py` | 250 | 43 | 5,8 | les constats bloquants et leur traitement | 11 cas de même nom ou presque dans `test-review-test`, 7 dans `spec-end-review-test` | refait par cas ; `ticket_proofs` |
| `ticket-graph-publish-coverage-test.py` | 213 | 70 | 3,0 | la couverture des user stories à la publication | 2 refus aussi dans `convoy-state-test` | léger |
| `correction-round-test.py` | 209 | 32 | 6,5 | le tour de correction et la dérogation | 3 refus de dérogation aussi dans `convoy-state-test` | refait par cas ; `ticket_proofs` |
| `ticket-exit-test.py` | 204 | 54 | 3,8 | les cinq sorties d'un ticket et le Handoff | « sortie hors liste fermée » aussi dans `convoy-state-test` | copie par cas |
| `ticket-author-test.py` | 198 | 30 | 6,6 | les étapes de l'auteur | rouge, gel, vert : dans `tdd-step-test` | produit lancé par cas |
| `tdd-step-test.py` | 185 | 66 | 2,8 | rouge, gel, vert, preuve du seam | 2 refus aussi dans `convoy-state-test` | copie par cas |
| `test-review-test.py` | 180 | 30 | 6,0 | la relecture des tests avant gel | même cycle que `code-review-test` | copie par cas |
| `ticket-end-test.py` | 153 | 29 | 5,3 | les neuf conditions de fermeture d'un ticket | | instantané |
| `spec-end-review-test.py` | 145 | 23 | 6,3 | la revue de fin | même cycle que `code-review-test` | instantané |
| `prototype-fidelity-test.py` | 124 | 24 | 5,2 | la fidélité au prototype | | produit lancé par cas |
| `acceptance-session-test.py` | 121 | 20 | 6,1 | la session d'acceptation | | instantané |
| `spec-end-test.py` | 118 | 28 | 4,2 | les trois verdicts mécaniques de fin de Spec | | instantané |

### 2.3 Doubles concrets (corps des cas lus)

| Règle | Étage bas | Étage du dessus | Ce qui diffère |
|---|---|---|---|
| Dérogation refusée sur un ticket non arrêté | `convoy-state-test.py` `test_an_override_is_refused_on_a_ticket_that_is_not_stopped` | `correction-round-test.py`, même nom | même message attendu (« n'est pas arrêté ») ; le second passe par `bin/correction-round` |
| Vert refusé sans gel | `convoy-state-test.py` `test_green_and_amendment_are_refused_without_a_freeze` | `tdd-step-test.py` `test_green_refused_without_a_freeze` | même mot attendu (« gel ») |
| Sortie hors liste fermée | `convoy-state-test.py` `test_ticket_exit_outside_the_closed_list_is_refused` | `ticket-exit-test.py` `test_an_exit_outside_the_closed_list_is_refused` | même valeur refusée (`done`) |
| User stories refusées sur un prefactoring | `convoy-state-test.py` `test_mark_refuses_user_stories_on_a_prefactoring_or_a_repair` | `ticket-graph-publish-coverage-test.py` `test_refuses_user_stories_on_a_prefactoring_or_a_repair` | le second passe par la porte de publication |
| Session morte sans sortie = « interrompu » | `ticket-exit-test.py` `test_a_session_ended_without_an_exit_is_read_as_interrupted` | `convoy-advance-test.py` `test_a_session_that_ended_without_an_exit_is_resumed_as_interrupted` | le second vérifie en plus la reprise |
| Revue de fin sans résultat : relance puis arrêt, signalé une fois | `spec-end-review-test.py` `test_an_end_review_without_result_is_launched_once_more_then_stopped_and_raised_once` | `convoy-advance-test.py` `test_an_end_review_without_result_is_an_outcome_of_the_pass_then_stopped_and_raised_once` | mêmes trois actions attendues, même relecture de la liste d'escalade |
| PR fusionnée et CI verte ne ferment pas un ticket | `ticket-end-test.py` `test_merged_pull_request_and_green_ci_do_not_close_a_ticket` | `convoy-advance-test.py` `test_a_merged_pull_request_and_a_green_ci_close_no_ticket_of_a_marked_convoy` | |
| Borne des Planning Exceptions ouvertes lue dans les réglages | `convoy-advance-test.py` `test_the_bound_of_the_open_planning_exceptions_is_the_one_of_the_settings` | `convoy-stops-fixture-city-test.py` `test_the_bound_of_the_open_planning_exceptions_is_read_in_the_settings_of_the_flow` | même réglage, graphe réel au lieu du faux tracker |
| Convoi abandonné : fermé avec la raison, branche protégée immobile | `convoy-stops-fixture-city-test.py` `test_an_abandoned_convoy_is_closed_with_the_reason_and_the_protected_branch_does_not_move` | `fixture-city-oracle-test.py` `test_an_abandoned_convoy_is_closed_with_its_reason_and_the_protected_branch_does_not_move` | deux parcours entiers pour la même observation |
| Enregistrement refusé hors session en lecture seule | `code-review-test.py` `test_record_is_refused_outside_a_read_only_reviewer_session` | `test-review-test.py`, même nom | deux outils, même règle, code non partagé |

Lecture de ces doubles :

- Un cas du dessus n'est pas inutile par nature : il prouve que l'outil transmet le refus de l'étage bas. Mais il paie le décor entier pour une vérification d'une ligne.
- `convoy-stops-fixture-city-test.py` est un étage que la Spec n'a pas prévu (« Aucun seam nouveau ») : il se place entre le seam 2 et le seam 1 et refait des deux côtés. C'est le seul fichier dont l'objet entier est couvert par ses deux voisins.
- `code-review`, `test-review`, `spec-end-review`, `ticket-evaluation`, `outcome-evaluation` écrivent chacun le même cycle (lancer, attendre, relancer une fois, arrêter, signaler une fois), sans module commun (seul `delivery_role_identity` est partagé). Le double emploi des tests suit celui du code : 23 cas de noms identiques ou presque entre les trois fichiers de revue. Le remède est dans le code, pas dans les tests.
- `test_a_convoy_without_the_mark_is_not_touched` existe dans 9 fichiers : un par outil, légitime et peu coûteux.

Échantillon des courts (140 fichiers, 841 s) : 104 fichiers sous 5 s font 118 s, dont 81 scripts shell (223 s en tout) ; ce sont eux qui ont rougi le plus souvent (1.1). Onze fichiers du Cockpit (environ 180 s) démarrent un serveur local et attendent des délais fixes de 5 à 15 s : source des 13 rouges instables. Aucun double entre courts et longs n'a été cherché au-delà des noms.

## 3. Écarts aux pratiques sourcées

Sources lues : *Software Engineering at Google*, [ch. 11](https://abseil.io/resources/swe-book/html/ch11.html) et [ch. 12](https://abseil.io/resources/swe-book/html/ch12.html) ; Fowler, [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html). Le corps du billet Google « Just say no to more end-to-end tests » n'a pas pu être lu (voir « Non vérifié »).

| Pratique (source) | Ici | Écart |
|---|---|---|
| Petit test = un seul processus, sans entrée-sortie ; environ 80 % de tests étroits, 15 % moyens, 5 % de bout en bout (SWE ch. 11) | aucun petit test dans les 6 694 s : chaque cas lance des processus | la base de la pyramide manque |
| Plus on monte, moins il y a de tests (Fowler) | parcours entiers 1 434 s (oracle, convoy-stops, second projet), orchestrateur 923 s, outils avec amont réel 4 674 s, règles et courts 504 s | 31 % du temps aux deux étages du haut ; forme en sablier inversé |
| « Push your tests as far down the test pyramid as you can » ; un test haut déjà couvert plus bas se retire (Fowler, « Avoid Test Duplication ») | la Spec dit du seam le plus haut : « tout critère qui peut y être observé y est observé » | consigne inverse |
| Un rouge vu en haut sans rouge en bas appelle un test bas (Fowler) | le rouge de l'oracle du 2026-10-08 n'a pas donné de cas bas | non appliqué |
| Tester par l'interface publique, celle que voit l'utilisateur du module (SWE ch. 12) | « seules les lignes de commande sont exercées » (22 fichiers, 5 699 s) | la règle maison confond interface publique et frontière de processus : `main(argv)` appelé dans le même processus est la même interface |
| Les grands tests sont des contrôles de cohérence, pas le moyen principal de trouver les défauts (SWE ch. 11) | « un test par refus et par passage » à l'étage de la ligne de commande | chaque cas limite est payé au prix d'un test moyen |
| Vitesse et déterminisme d'abord ; un test perd sa valeur vers 1 % d'instabilité (SWE ch. 11) | `cockpit-actions-test.py` : 8 rouges sur environ 450 runs depuis le 2026-09-30, soit près de 2 % | au-dessus du seuil |
| Le décor commun sert à construire l'objet testé ; les valeurs qui comptent restent dans le test (SWE ch. 12) | décor refait par cas dans 10 fichiers ; instantané dans 5 | le remède (instantané copié) est compatible avec la source |
| La couverture dit qu'une ligne a tourné, pas ce qui a été vérifié (SWE ch. 11) | | une mesure de couverture seule ne peut pas justifier un retrait |

Ce que coûte la règle « seules les lignes de commande » : un cas ne peut rien vérifier sans lancer un processus (40 ms pour `bin/convoy-state`, 11 ms pour le faux `gc`, chiffres de `docs/OPERATIONS.md`), un fichier en lance environ 14 000, et le décor ne peut être construit que par les vrais outils d'amont. La règle protège une chose réelle : un test qui ne casse pas quand on réécrit l'intérieur d'un outil.

## 4. Comment les tests sont demandés aux auteurs

| Consigne | Ce qu'elle dit des tests | Effet |
|---|---|---|
| Spec af-wf4w5r, « Testing Decisions » | seam 1 « le plus haut ; tout critère qui peut y être observé y est observé » ; seam 2 « un test par refus et par passage, qui relit l'état après » ; « jamais ses fonctions internes » | pousse vers le haut et vers l'exhaustif |
| Clause `test_method` du contrat de chaque ticket (lue sur af-gfyj6k) | reprend les trois seams mot pour mot ; « Aucun test ne lit une fonction interne » | c'est la consigne que l'auteur des 20 fichiers a reçue |
| `formulas/mol-do-work.formula.toml` (les tickets de l'usine ont été livrés par elle) | quoi lancer avant la PR ; rien sur la façon d'écrire un test | aucun frein |
| `formulas/mol-ticket-author.formula.toml` (nouveau flux, pour les projets) | « write every criterion test of the ticket first » ; périmètre de test du profil ; rien sur durée, étage, décor | aucun frein |
| Skill `tdd` (`skills/engineering/tdd/SKILL.md`) | tests par l'interface publique ; seams convenus d'avance « instead of every edge case » ; exemple « integration-style » | contredit par « un test par refus » ; n'a pas de règle de durée |
| `docs/TDD_STEP.md` | preuve mécanique du rouge, du gel, du vert, du seam | vérifie l'ordre, pas le coût |
| `docs/TEST_REVIEW.md` | le relecteur répond : le test observe-t-il son critère, échouerait-il si le critère était faux | aucune question sur le double emploi, l'étage ou la durée |

Ce qui manque, dans toutes ces consignes (recherche des mots durée, budget, lent, étage, pyramide, décor partagé : aucune occurrence utile) :

- un budget de durée par cas et par fichier, avec un contrôle qui rougit au-delà ;
- l'étage imposé : quelle règle se prouve en bas, laquelle a droit à un parcours entier ;
- le décor partagé : `tests/lib/ticket_proofs.py` et `stage()` existent mais aucune consigne ne dit de s'en servir ;
- la question « cette règle est-elle déjà prouvée plus bas » dans la relecture des tests ;
- un plafond de taille : `convoy-state-test.py` a reçu 25 commits en 4 jours, chaque ticket y ajoute ses cas.

## 5. Quelle mesure prouverait qu'un test peut partir, et son coût ici

Rien n'a été lancé ; tout est estimé.

| Mesure | Outil | Faisable ici ? | Coût estimé | Ce qu'elle prouve |
|---|---|---|---|---|
| Rejouer l'historique : qui était seul rouge | fait en 1.2 | oui, gratuit | nul | 3 fichiers longs seuls détecteurs ; 4 événements, trop peu pour conclure sur les autres |
| Mutation complète d'un outil | [cosmic-ray](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html) : `module-path` (fichier ou dossier), `test-command` (une commande), `timeout` | oui pour `lib/convoy_state.py` ; à vérifier pour les scripts de `bin/` sans extension | non : de l'ordre de milliers de mutants × 523 s pour `convoy-state` seul, soit des semaines de calcul | tout |
| Mutation par échantillon | cosmic-ray, 100 mutants tirés au hasard par outil | oui | un outil et son fichier : 100 × 250 s ≈ 7 h de calcul, environ 1 h sur 8 cœurs au repos. Question « `convoy-stops` peut-il partir » (mutants de `bin/convoy-advance`, trois fichiers à 2 314 s) : 64 h de calcul, environ 10 h sur le PC au repos | pour chaque mutant, quels fichiers rougissent ; un fichier jamais seul à tuer un mutant est candidat |
| Mutation à la main | 20 fautes écrites par un agent dans un outil | oui, aucun outil à installer ; seule voie pour les scripts bash (`escalation-door`, `dispatch-door`) | 20 × 250 s ≈ 1,4 h par outil | moins neutre : l'agent choisit les fautes |
| [mutmut](https://mutmut.readthedocs.io/en/latest/) | exige pytest et `fork`, choisit les tests par fonction appelée dans le processus | non : les tests sont des scripts `unittest` qui lancent des processus | | |
| Couverture par test | [coverage.py](https://coverage.readthedocs.io/en/latest/config.html) 7.10 ou plus : `patch = subprocess`, contexte statique `[run] context` nourri par une variable d'environnement posée par chaque cas | à essayer ; coverage n'est pas dans l'image du runner (Python 3.12 et PyYAML seulement) | une batterie instrumentée : environ le double, soit 40 min sur 8 cœurs au repos | quelles lignes un seul fichier atteint ; nécessaire, pas suffisant (une ligne atteinte n'est pas une ligne vérifiée) |
| Sélection puis tout, en observation | journal de ce qu'une sélection aurait lancé, comparé aux rouges réels | oui, la CI lance déjà tout | nul en machine ; au rythme observé (5 rouges de fichiers longs en 4 jours) il faut plusieurs semaines pour 30 événements | ce que la sélection aurait manqué |

Ordre conseillé : mutation par échantillon sur `bin/convoy-advance` (la seule question de retrait ouverte), l'hôte au repos ; couverture par test seulement si l'on veut ensuite descendre des cas un par un.

## 6. Classement des 21 fichiers longs

Aucun retrait n'est décidé ici : c'est la décision de Benjamin.

| Classe | Fichiers | Secondes | Raison |
|---|---|---|---|
| Garder tel quel | `tdd-step` 185, `ticket-exit` 204, `ticket-graph-publish-coverage` 213, `ticket-end` 153, `spec-end-review` 145, `prototype-fidelity` 124, `acceptance-session` 121, `spec-end` 118 | 1 263 | seul fichier de leur outil ; 5,3 s par cas ou moins, ou décor déjà en instantané |
| Accélérer sans changer les vérifications | `convoy-advance` 923, `fixture-city-oracle` 796, `ticket-evaluation` 504, `spec-integration` 406, `outcome-evaluation` 291, `owner-answer` 290, `evidence-pack` 266, `code-review` 250, `correction-round` 209, `ticket-author` 198, `test-review` 180 | 4 313 | décor refait par cas ou parcours entier par cas ; l'instantané copié existe déjà dans 5 fichiers ; `convoy-advance` est aussi à couper en deux (plancher du run) |
| Descendre d'un étage | `convoy-state` 523 | 523 | son code est déjà un module (`lib/convoy_state.py`) : les 303 cas peuvent appeler `main(argv)` dans le processus, mêmes arguments, mêmes vérifications ; demande d'assouplir la règle « lignes de commande » |
| Fusionner avec `fixture-city-oracle-test.py` et `convoy-advance-test.py`, ou retirer en partie | `convoy-stops-fixture-city` 595 | 595 | étage non prévu par la Spec, 21,3 s par cas, jamais rouge ; preuve qui manque : mutation par échantillon de `bin/convoy-advance` montrant qu'il n'est seul à tuer aucun mutant |
| Candidat au retrait, fichier entier | aucun | 0 | |

Total 6 694 s. Gain attendu de la classe « accélérer » : 30 à 50 % selon la recherche du 2026-10-09 (estimation, non remesurée), soit 1 300 à 2 150 s.

Cas candidats au retrait à l'intérieur des fichiers gardés : les étages du dessus du tableau 2.3 (environ 10 cas lus, quelques dizaines probables). Gain faible tant que le décor est refait par cas ; même preuve manquante.

## 7. Ce que cela fait apparaître pour la carte

| Sujet | Constat | À qui |
|---|---|---|
| Retrait | aucun fichier entier n'est prouvé retirable ; la seule question ouverte est `convoy-stops-fixture-city-test.py` (595 s) | Benjamin, ticket af-8km43c.9 : autoriser ou non la mesure par mutation (10 h de PC au repos) avant de trancher |
| Règle « seules les lignes de commande » | confirmée par lui le 2026-10-06 avec les seams ; la lire comme « interface publique, processus ou non » ouvre l'étage bas | Benjamin : la règle change de sens |
| Consigne d'écriture | la clause `test_method` et la phrase « tout critère qui peut y être observé y est observé » produisent la forme actuelle | Spec de la carte : budget par cas, étage par type de règle, décor partagé, question de double emploi dans la relecture des tests |
| Code en double | cinq outils réécrivent le cycle lancer, relancer, arrêter | hors carte (temps de CI seul) ; à verser à af-8cfygl |
| Tests du Cockpit instables | 13 rouges sur attente dépassée | bug de test : délais fixes sous charge ; à traiter avant la fusion par lots, où un rouge instable coûte un lot |
| Étape « Syntax check » | `bash -n "$f" && echo "ok $f" \|\| true` ne peut pas échouer | bug de CI ; une ligne à corriger, non faite ici (lecture seule) |

## Non vérifié

- Les rouges vus à la main avant la PR (avant le 2026-10-08 22:35) : aucun journal lu ; la valeur réelle des 17 fichiers « jamais rouges » est donc inconnue.
- Le classement par cause des 86 exécutions : fait par un seul lecteur, sur le message d'échec ; les 9 rouges du Cockpit non relancés sont classés instables par ressemblance du message, pas par preuve.
- Les parts de temps par cause (décor, lancements) et le gain de 30 à 50 % : repris de la recherche du 2026-10-09, non remesurés ; rien n'a été lancé.
- Les secondes par étage de la section 3 : classement fait sur l'en-tête et les outils nommés de chaque fichier.
- Le gain d'un appel dans le processus pour `convoy-state-test.py` : non chiffré ; `lib/convoy_state.py` lit peut-être son environnement à l'import, ce qui gênerait.
- Les doubles : cherchés par ressemblance des noms entre les 21 fichiers longs, puis 20 corps lus. Des doubles sous des noms différents, et entre fichiers courts et longs, ne sont pas vus.
- cosmic-ray sur un script sans extension `.py`, et le nombre de mutants par outil : non essayés. Le contexte de couverture par test à travers les processus : composition de deux réglages documentés, non essayée.
- Le billet Google « Just say no to more end-to-end tests » : la page n'a rendu que les commentaires ; son contenu n'est cité nulle part ici. Le chapitre 11 du livre couvre le même propos.
- Le chiffre « 450 runs » de `cockpit-actions-test.py` : nombre approché des runs depuis le 2026-09-30, annulés compris, sans retirer ceux qui n'ont pas lancé ce fichier.
- `factory-guard-liveness-test.sh` (1 rouge) est classé vrai défaut sur son seul message ; la cause n'a pas été recherchée.
- Aucun outil de mutation maintenu pour bash n'a été cherché au-delà de ce constat d'absence dans les sources lues.
