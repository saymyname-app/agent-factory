# Réduire structurellement le temps de CI de l'usine sans perdre en qualité

Recherche du 2026-10-09 (heures de Paris), session opérateur po-agent/1258478a.
Branche jamais fusionnée `research/ci-time-reduction`. Aucun réglage de CI, du
ruleset ou du runner n'a été changé : lecture, mesures et sources seulement.

Intent (Benjamin, ses mots, chat live, 2026-10-09 vers 23:10 Paris, session
opérateur de T32 po-agent/736b05c5) : « il faut reflechir comment réduire
structurellement les temps de CI, tout en conservant la qualité, sachant qu'on
est dans une software factory. On peut potentiellement faire moins de test à
des moments voir pas du tout, et rattrapper avec IA ensuite. Genre soit toute
la spec entiere testée à la fin, soit par groupe, soit autre. Il faut
s'inspirer des gens sur internet. Reduire le temps des CI aussi, verifier si
les tests ecrits sont tous bien faits dans les meilleures pratiques. […] temps
global à reduire = nombre de CI * taille des CI * vitesse d'execution des CI *
CI en parallèles * CI jetées car bug * autres facteurs. […] mettre 5 jours
pour une refacto comme celle là c'est 10 fois trop. »
Mechanism (interprétation de l'agent, non confirmée par lui) : cette recherche
sourcée, puis un Planning Run (`docs/PLANNING_RUN.md`). Ne veut PAS dire :
qu'un levier ci-dessous est choisi, qu'un test peut être retiré, ni que la
porte de fusion peut changer sans sa décision.

## Vocabulaire

| Mot | Sens ici |
|---|---|
| Run | une exécution de la CI sur un commit d'une PR |
| Batterie | tous les tests de `bin/ci-run-tests` (161 fichiers mesurés) |
| Test long | fichier de test de 30 s ou plus (`docs/OPERATIONS.md`) |
| File de fusion par lots | un outil fusionne « main + N PR » sur une branche temporaire, lance un seul run, et fait entrer les N PR si c'est vert ; si c'est rouge il coupe le lot en deux pour trouver la fautive (bissection) |
| CI à deux étages | un étage court avant la fusion, la batterie entière ensuite sur un groupe de changements |
| Sélection par impact | ne lancer que les tests que le changement peut atteindre |

## 1. Ce qui est mesuré (2026-10-09, à 23:30)

Sources : `gh run list`, l'API des jobs de chaque run, `gh pr list`,
`config/ci-test-seconds.tsv` (run 37872828394), le ruleset, `bin/ci-runner status`.

| Mesure | Valeur |
|---|---|
| Runs du jour | 43 annulés, 25 réussis, 2 échecs, 3 en cours ou en attente |
| PR fusionnées du jour | 22 ; 2,77 runs par PR fusionnée, dont 1,59 annulé |
| PR ouverte → fusionnée | médiane 50 min ; 9 sur 10 sous 135 min ; maximum 267 min (PR 484 : 8 runs, 5 annulés, 2 échecs) |
| Même mesure le 2026-10-06 (runners GitHub, 4 lots, batterie de 8 min) | médiane 18 min, 35 PR fusionnées |
| Un run réussi sur le runner du PC | médiane 21,5 min (de 16 à 55 min selon la charge de l'hôte) |
| Temps de runner consommé | 745 min sur 1 402 (53 % du jour) : 517 réussis, 153 annulés, 47 échecs, 28 en cours |
| Runner saturé | 18 h-21 h : 178 min occupées sur 180 ; 21 h-0 h : 138 sur 150 |
| Runs annulés | 12 n'ont jamais eu le runner ; les 31 autres ont tourné 4,3 min en médiane |
| Batterie | 161 fichiers, 7 535 s cumulées ; 21 fichiers de 100 s ou plus font 89 % ; le plus long, 923 s, est le plancher d'un run |
| Porte de fusion | ruleset `AF-main-protection` : contrôle requis `Tests`, `strict_required_status_checks_policy: true` (PR à jour avec main) ; `cancel-in-progress` par PR ; `bin/pr-autopilot` remet à jour une PR en retard par tick |
| Plan GitHub | organisation `team`, dépôt privé |

Lecture, facteur par facteur de la formule de Benjamin :

| Facteur | État | Poids |
|---|---|---|
| Nombre de CI | 2,77 runs par PR ; chaque fusion rend toutes les autres PR « en retard », donc à relancer | fort |
| CI jetées | 43 sur 70, mais seulement 20 % du temps de runner : le coût est l'attente relancée, pas la machine | fort sur le délai, faible sur la machine |
| Taille | la batterie entière sur 6 PR sur 10 ; sélection limitée à `docs/` et au Cockpit | fort |
| Vitesse | 21,5 min ; plancher 923 s tant que le plus gros fichier n'est pas coupé | moyen |
| Parallèle | un job à la fois, 8 processeurs ; plus de cœurs n'aide plus (mesuré : 4 → 8 cœurs = −27 %) | faible tant que la vitesse n'a pas bougé |
| Autre | CI verte ≠ critère tenu : T43 et T46 relus après fusion par une session neuve ont un critère non tenu, CI verte (commentaires de af-m23wru ; le chiffre « 5 sur 7 » du brief n'a pas été recompté ici) | fort sur la qualité |

Cause structurelle : « PR à jour avec main » + un runner qui prend un job à la
fois + une batterie de 21 min = au plus une fusion par run quand plusieurs PR
attendent, et chaque fusion relance les autres. Le débit plafonne et le délai
croît avec le nombre de PR ouvertes en même temps.

Non mesuré : la part de la CI dans les 5 jours de D01 (le reste : écriture,
revues, réparations, charge de l'hôte). L'objectif « 10 fois » ne peut donc pas
être promis sur la seule CI.

## 2. Pratiques, sources primaires

Facteurs : N nombre de runs, T taille, V vitesse, P parallèle, J runs jetés, A autre.

### 2.1 Fusionner par groupes

| Pratique | Source | Facteur | Exige | Risque qualité | Compensation |
|---|---|---|---|---|---|
| File de fusion GitHub | [doc](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue), [condition d'accès](https://raw.githubusercontent.com/github/docs/main/data/reusables/gated-features/merge-queue.md) | J↓ ; N inchangé (un run par entrée de file) | dépôt public, ou privé sur Enterprise Cloud ; événement `merge_group` | aucun pour main | la PR fautive sort, celles derrière sont reconstruites |
| Lots + bissection (bors-ng) | [dépôt](https://github.com/bors-ng/bors-ng) (projet déprécié, renvoie à la file GitHub) | N↓, J↓ | un robot à soi | aucun pour main ; une PR rouge retarde le lot | lot coupé en deux jusqu'à isoler la fautive |
| Rollups de Rust | [forge Rust](https://forge.rust-lang.org/release/rollups.html) | N↓ | étiquette de risque par PR | un rollup rouge coûte un run entier | PR risquées exclues du lot (`rollup=never`) |
| Lots Mergify, Aviator, Trunk | [Mergify](https://docs.mergify.com/merge-queue/batches/), [Aviator](https://docs.aviator.co/mergequeue/concepts/batching), [Trunk](https://docs.trunk.io/merge-queue/optimizations/batching) | N↓ | service payant ; « à jour avec main » retiré (Mergify) | on perd la preuve que chaque PR passe seule | bissection ; Trunk conseille moins de 10 % de lots rouges |
| CI en deux temps de Mergify | [doc](https://docs.mergify.com/merge-queue/two-step/) | T↓ sur la PR, N↓ pour la batterie | deux noms de contrôle | l'échec coûteux arrive tard | exemple de la doc : 5 PR × 30 min = 30 min au lieu de 2 h 30 |
| Lots Shopify | [blog](https://shopify.engineering/successfully-merging-work-1000-developers) | N↓ | outil maison | un test instable éjecte de bonnes PR | éjection seulement après 3 échecs de suite |
| Prow Tide (Kubernetes) | [doc](https://docs.prow.k8s.io/docs/components/core/tide/) | N↓, J↓ | Prow | lot rouge = pas de fusion | repli sur les PR vertes une par une |
| Spéculation en parallèle (Zuul, SubmitQueue d'Uber) | [Zuul](https://zuul-ci.org/docs/zuul/latest/gating.html), [Uber 2025](https://arxiv.org/abs/2501.03440) | P↑, J↑ | beaucoup de machines | aucun pour main | fenêtre réduite de moitié à chaque échec |
| Tout tester en fin de branche longue | contre-indication : [DORA trunk-based](https://dora.dev/capabilities/trunk-based-development/), [DORA petits lots](https://dora.dev/capabilities/working-in-small-batches/) | N↓↓ | branche longue | grosses fusions, régressions, phase de stabilisation | DORA : fusion au tronc au moins chaque jour, 3 branches actives au plus |

Fait décisif : la file de fusion native de GitHub n'est pas disponible pour un
dépôt privé d'une organisation sur le plan Team. Et même disponible, elle lance
un run par PR : sur un seul runner elle retire les runs jetés, pas le nombre.
La spéculation en parallèle n'apporte rien avec un seul job à la fois.

Arithmétique des lots (calcul de l'agent, pas d'une source) : un lot de N PR
coûte 1 run ; il est vert avec la probabilité (1−p)^N ; rouge, la bissection
coûte environ 1,5 × log2 N runs.

| p (PR rouge) | N | Lot vert | Runs par PR |
|---|---|---|---|
| 5 % | 4 | 81 % | 0,39 |
| 5 % | 8 | 66 % | 0,31 |
| 10 % | 4 | 66 % | 0,51 |
| 10 % | 8 | 43 % | 0,45 |
| 20 % | 4 | 41 % | 0,69 |

Ici p vaut 9 à 46 % selon le jour (échecs par PR fusionnée, 2026-10-01 au
2026-10-09) : un lot de 4 donne 0,4 à 0,7 batterie par PR contre 2,77 runs
aujourd'hui. Au-delà de 4 à 8 PR le gain s'aplatit.

### 2.2 CI à deux étages

| Pratique | Source | Facteur | Exige | Risque qualité | Compensation |
|---|---|---|---|---|---|
| Google TAP : court avant, tout après | [SWE at Google ch. 23](https://abseil.io/resources/swe-book/html/ch23.html) | T↓ avant fusion, N↓ après | tests triés rapides/lents ; recherche du coupable | main peut être rouge un temps | bissection du groupe, retour arrière, versions coupées sur le dernier commit vert ; un changement qui passe l'étage court a plus de 95 % de chances de passer le reste |
| Meta : stabilisation | [article](https://arxiv.org/abs/1810.05286) | T↓ | historique | moins de 5 % d'échecs de tests manqués, par conception | tous les tests sur le tronc toutes les quelques heures |
| Chromium : jardinier | [doc](https://chromium.googlesource.com/chromium/src/+/main/docs/gardener.md) | étage après fusion | une personne de garde | arbre fermé = tout le monde bloqué | trouver le coupable et annuler |

Une file par lots donne le même gain que les deux étages sans la fenêtre « main
rouge » : la batterie tourne sur « main + lot » avant l'entrée dans main.

### 2.3 Sélection par impact et cache

| Pratique | Source | Facteur | Exige | Risque qualité | Compensation |
|---|---|---|---|---|---|
| Graphe de dépendances (Bazel, TAP) | [SWE ch. 23](https://abseil.io/resources/swe-book/html/ch23.html), [Memon 2017](https://research.google/pubs/taming-google-scale-continuous-testing/) | T↓ | graphe déclaré | dépendance non déclarée | tout après fusion ; 91 % des cibles affectées n'échouent jamais ; au-delà de 10 arêtes du changement presque rien ne casse |
| Sélection prédictive (Meta) | [article](https://arxiv.org/abs/1810.05286), [blog](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/) | T↓ (moins d'un tiers des tests) | gros historique | plus de 99,9 % des changements fautifs vus, pas 100 % | stabilisation périodique |
| Carte test → fichiers par observation | [Fowler/Hammant](https://martinfowler.com/articles/rise-test-impact-analysis.html), [Microsoft TIA](https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis), [pytest-testmon](https://testmon.org/) | T↓ | chaque test lancé seul sous observation ; carte mise à jour par la CI seule | fichiers lus hors du champ du capteur | tout relancer sur fichier inconnu ; run complet périodique ; valider en lançant la sélection puis tout et en comparant |
| Mode observation avant de s'y fier | [CloudBees Smart Tests](https://docs.cloudbees.com/docs/cloudbees-smart-tests/latest/send-data-to-smart-tests/subset/observe-subset-behavior) | aucun au début | enregistrer ce que la sélection aurait manqué | aucun | la batterie tourne toujours pendant la mesure |
| Cache de résultats par empreinte des entrées | [Bazel](https://bazel.build/remote/caching), [Gradle](https://docs.gradle.org/current/userguide/build_cache.html), [Nx](https://nx.dev/concepts/how-caching-works) | T↓ (test inchangé = coût nul) | entrées déclarées, test hermétique | succès périmé si une entrée n'est pas dans la clé | les échecs ne sont jamais réutilisés |

L'usine a déjà le capteur : le « bandeau » (`bwrap`, dates d'accès) dit quelles
zones un test long a lues. Il sert aujourd'hui à 5 zones ; rien dans les
sources lues ne décrit ce capteur précis (non vérifié), mais c'est le même
principe que la carte par observation.

### 2.4 Tests lents, découpage, tests instables

| Pratique | Source | Facteur | Exige | Risque qualité | Compensation |
|---|---|---|---|---|---|
| Couper par cas, pas par fichier | [Knapsack Pro](https://docs.knapsackpro.com/ruby/split-by-test-examples/), [CircleCI](https://circleci.com/docs/guides/optimize/parallelism-faster-jobs/) | P↑ | cas indépendants | aucun | durées mesurées |
| Pyramide : descendre les tests, peu de bout en bout | [Google 2015](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html), [Fowler](https://martinfowler.com/articles/practical-test-pyramid.html), [SWE ch. 11](https://abseil.io/resources/swe-book/html/ch11.html) | V↑, T↓ | un point d'entrée plus bas | retirer le seul test qui voyait un défaut | ajouter le test bas avant de retirer le haut |
| Décor construit une fois, puis copié | [fixtures pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html), [modèles PostgreSQL](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html) | V↑ | tests qui ne modifient pas le décor commun | contamination entre tests | copie par test |
| Tests de mutation avant de retirer un test | [Google 2018](https://research.google/pubs/state-of-mutation-testing-at-google/), [PIT](https://pitest.org/) | T↓ (preuve avant retrait) | mutation des lignes changées | coûteux partout | seulement sur le diff |
| Réduction de suite | [Yoo & Harman](https://onlinelibrary.wiley.com/doi/abs/10.1002/stvr.430) | T↓ | couverture par test | études contradictoires sur la perte de détection | aucune consensuelle |
| Quarantaine des tests instables | [Google 2016](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html), [GitHub](https://github.blog/engineering/reducing-flaky-builds-by-18x/), [Atlassian](https://www.atlassian.com/blog/atlassian-engineering/taming-test-flakiness-how-we-built-a-scalable-tool-to-detect-and-manage-flaky-tests) | J↓ | taux d'instabilité suivi | masquer un vrai défaut | ticket avec responsable et échéance ; le test continue de tourner hors porte |

Chez Google, 0,5 % des petits tests sont instables contre 14 % des grands.

### 2.5 Équipes qui livrent avec des agents IA

| Pratique | Source | Facteur | Risque | Compensation |
|---|---|---|---|---|
| Contrôles rapides que l'agent lance avant de s'arrêter | [Claude Code](https://code.claude.com/docs/en/best-practices), [Spotify](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3) | N↓, J↓ | code plausible mais faux | ne pas livrer ce qu'on ne peut pas vérifier |
| Tours de CI plafonnés, lint et sous-ensemble d'abord | [Stripe](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents) | N↓, T↓ | correction incomplète | un humain relit chaque PR |
| Relecteur IA à contexte neuf | [Anthropic, harnais](https://www.anthropic.com/engineering/harness-design-long-running-apps), [Code Review](https://code.claude.com/docs/en/code-review) | A (coût ajouté) | approuve du travail défectueux ; invente des écarts | critères explicites ; ne bloque jamais seul |
| Scénarios cachés à l'agent qui code | [StrongDM](https://factory.strongdm.ai/) | A | score probabiliste | milliers de scénarios |
| Portes minimales, corriger après | [OpenAI](https://openai.com/index/harness-engineering/) | N↓, J↓ | dérive | agents de nettoyage ; OpenAI dit que ce n'est pas généralisable sans leur investissement |

« Moins tester par changement et rattraper par une relecture IA » : aucune
source lue ne dit le faire. Google et Meta reportent, mais vers une batterie
entière déterministe. DORA 2025 relie l'IA à plus de débit et à moins de
stabilité, faute de tests automatiques rapides. Les agents contournent les
tests (StrongDM : `return true` ; Spotify : tests instables désactivés).
Conclusion des sources : la relecture IA voit une autre classe de défauts
(critère non tenu) et s'ajoute aux tests ; elle ne les remplace pas.

## 3. Audit par échantillon des tests longs (lecture seule, rien lancé)

Six fichiers lus en détail, douze survolés. Les décomptes sont statiques, donc
des minimums ; les parts sont des estimations.

| Fichier | s | Cas | s/cas | Coût dominant |
|---|---|---|---|---|
| `convoy-advance-test.py` | 923 | 131 | 7,0 | 202 passes entières de `bin/convoy-advance`, chacune relance jusqu'à 14 outils |
| `fixture-city-oracle-test.py` | 796 | 45 | 17,7 | 46 parcours entiers du flux ; un même scénario parcouru 8 fois, un autre 4 fois |
| `convoy-stops-fixture-city-test.py` | 595 | 28 | 21,3 | publication et décor refaits par test, puis 51 passes réelles |
| `convoy-state-test.py` | 523 | 303 | 1,7 | environ 2 370 lancements directs ; 250 refus vérifiés par deux lectures de plus chacun |
| `ticket-evaluation-test.py` | 504 | 58 | 8,7 | décor identique refait : 9 lancements, puis 27 dans 51 tests sur 58 |
| `spec-integration-test.py` | 406 | 65 | 6,2 | même schéma : 8 lancements, puis 33 dans 24 tests |

| Cause, par ordre | Preuve | Remède sans retirer d'assertion | Effet | Risque |
|---|---|---|---|---|
| 1. Les outils se relancent entre eux (chaque lecture d'état = un processus + un faux `gc`) | 14 000 processus dans un fichier (`docs/OPERATIONS.md`) | passer l'état déjà lu aux étapes d'une même passe | fort | moyen : la relecture protège contre un état périmé ; la carte af-jnjqn4 a été arrêtée sur ce sujet (gain réel 1 à 2 %, 11 à 20 % pour la lecture unique du bead) |
| 2. Décor identique reconstruit à chaque cas | 6 fichiers ; plus de la moitié des lancements directs sont du décor | étendre à ces fichiers l'instantané déjà utilisé par 5 autres (`stage()`, archive restaurée) | fort (estimé 30 à 50 % sur ces fichiers) | faible : l'instantané est écrit par les vrais outils |
| 3. Le parcours entier comme unité de test | oracle : 17,7 s par parcours | un parcours par scénario distinct, plusieurs tests lisent son résultat | moyen (environ 10 parcours) | faible |
| 4. Trois couches prouvent le même comportement de bout en bout | fichier de l'outil, `convoy-advance-test`, puis oracle | à mesurer (mutation, couverture) avant tout retrait | inconnu | retirer un test est la décision de Benjamin |
| 5. Git par commandes pour le décor | 9 lancements par commit | un seul `git fast-import` | faible à moyen | nul |
| 6. Attentes fixes | aucune (`time.sleep` absent ; sondes de 0,1 s) | rien | nul | nul |

Plancher du run : couper `convoy-advance-test.py` (vers la ligne 1394) et
`convoy-state-test.py` (vers la ligne 2082) ne gagne aucun temps processeur
mais retire le plancher de 923 s ; les cas sont indépendants.
Aucun cache de résultat ou de décor entre fichiers ni entre runs.
La règle « seules les lignes de commande sont exercées » n'est écrite que dans
l'en-tête de 20 fichiers de test et dans la Spec af-wf4w5r (Testing Decisions).

## 4. Ce que cela donne pour l'usine

| Levier | Facteur | Gain attendu (estimation) | Décision de Benjamin ? |
|---|---|---|---|
| A. Batterie une fois par lot de PR (« main + lot »), étage court par PR | N, J | 2,77 runs entiers par PR → 0,4 à 0,7 | oui : le ruleset change (« à jour avec main » retiré, remplacé par le lot) |
| B. La branche d'intégration par Spec de D01 joue déjà ce rôle pour les convois marqués | N, J | même ordre, par Spec | à trancher : quels tests à chaque fusion de ticket, la batterie entière ou la sélection |
| C. Sélection par carte test → fichiers observée par le bandeau, en mode observation d'abord | T | étage court de 2 à 5 min | oui au moment de s'y fier |
| D. Instantané de décor, parcours d'oracle partagés, deux fichiers coupés | V | batterie de 21 min → environ 10 min | non (assertions inchangées) |
| E. Relecture des critères par session neuve à chaque ticket | A (qualité) | voit ce que la CI verte ne voit pas | déjà dans D01 (Ticket Evaluation) |
| F. Retirer des tests redondants après mesure | T | inconnu | oui |
| G. Second job en parallèle | P | faible avant D | oui (part du PC) |

Points que la recherche ne tranche pas :
- A et B se recouvrent : faut-il une file par lots pour les PR hors Spec
  (maintenance, réparations) et la branche d'intégration pour les Specs, ou un
  seul mécanisme ?
- `bin/deliver-close` exige la CI verte sur la tête exacte de la PR de chaque
  ticket (ADR-0026) : un lot change cette preuve.
- DORA déconseille « tout tester à la fin d'une branche longue » ; D01 y répond
  en reprenant la branche protégée avant chaque fusion de ticket. Non mesuré.
- Le taux de PR rouges (9 à 46 % par jour) fixe la taille de lot utile.

## 5. Non vérifié

- La part de la CI dans la durée de D01.
- Le chiffre « 5 réparations sur 7 avec un critère non tenu » (T43 et T46 lus ; les autres non recomptés).
- Les parts de temps par cause dans l'audit (rien n'a été lancé).
- Sources non atteintes : le texte d'origine de la règle de Graydon Hoare, l'article Uber de 2019, les pratiques internes de Meta sur la fusion, Chromium Findit.
- Le comportement de la file GitHub sur un seul runner (non essayé, et non disponible ici).
- Des blogs tiers décrivent la taille de groupe de la file GitHub comme un lot de CI ; la doc officielle dit le contraire.
