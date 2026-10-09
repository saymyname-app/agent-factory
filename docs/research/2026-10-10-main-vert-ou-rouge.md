# Main toujours vert (b) ou main parfois rouge (c) : la comparaison

Ticket af-8km43c.2, 2026-10-10 01:30 (Paris). Batterie = tous les tests ; étage court = contrôles de règles + tests touchés (1 à 5 min) ; coupable = la PR qui a cassé.
(b) : la batterie passe sur « main + un lot de PR » AVANT l'entrée dans main. (c) : la PR entre après l'étage court, la batterie passe APRÈS sur main, et on annule le coupable.

| | (b) lots, main toujours vert | (c) rattrapage, main parfois rouge |
|---|---|---|
| Ce que tu verrais | Une PR attend son lot. Main n'est jamais rouge. Un lot rouge : la PR fautive retourne à son auteur, les autres repassent. | Une PR entre en quelques minutes. De temps en temps : « main rouge depuis HH:MM, PR #N annulée ». Entre les deux, l'usine tourne sur main. |
| Délai PR ouverte → fusionnée | Environ 1,5 × la batterie (attente du lot en cours + son propre lot) : 35 min aujourd'hui (batterie de 22 à 26 min, mesuré), 15 min avec une batterie de 10 min. Estimation. | La durée de l'étage court, quelle que soit la batterie : 2 à 5 min, à condition que l'étage court n'attende pas derrière la batterie sur l'unique runner. Estimation. |
| Temps de runner par PR | 0,4 à 0,7 batterie (calcul de la recherche de départ, §2.1) | Même ordre (une batterie par groupe), plus les recherches de coupable |
| Fréquence du rouge | Lot rouge : 12 % des PR ont eu un run rouge depuis le 2026-10-06 (13 sur 108, mesuré) | Main rouge : entre 1 tous les 2 jours et 3 par jour à 25 PR par jour. Estimation fragile. Durée : 1 à 2 h avec la batterie actuelle. |
| Ce qui peut casser | Une PR rouge retarde les PR saines de son lot. Un test instable éjecte une bonne PR. | La racine vivante prend main toutes les 5 min : l'usine exécute le défaut. Les branches neuves partent d'un main cassé (rouges qui ne sont pas les leurs). Un convoi qui reprend main inscrit un rouge. Un ticket se ferme, et libère ses suivants, avant la preuve. |
| Qui répare | L'auteur de la PR, comme aujourd'hui (`bin/pr-autopilot` ouvre un bead P1 sur une PR rouge). Main n'est pas touché. | Personne aujourd'hui. Pas de garde, pas d'outil d'annulation, pas de recherche du coupable, et plus de run sur main depuis le 2026-10-08. |
| À construire | Le robot de lots (former, prouver, couper en deux si rouge, faire entrer) ; la preuve de fermeture d'un ticket lue sur le lot. | Le run sur main après fusion ; la recherche du coupable ; l'annulation automatique ; un repère « dernier commit vert » que suivent la racine vivante, les branches neuves et les convois ; le choix du moment où un ticket se ferme. |
| Chez qui | bors, Rust, Shopify, Kubernetes | Google, Meta, Chromium : une personne de garde par équipe, un retour arrière en deux clics, des versions coupées sur le dernier commit vert, jamais sur la tête |

Le point qui sépare l'usine des trois grands : chez eux, un main rouge ne s'exécute pas (les versions partent du dernier commit vert). Ici main EST ce qui tourne, cinq minutes après la fusion. (c) sans le repère « dernier commit vert » reproduit l'incident du 2026-09-16 (main cassé des heures, Cockpit cassé, vu par hasard).

Variantes mixtes crédibles :

1. **(b) avec étage court par PR** — le choix par défaut de la carte. Le délai reste lié à la batterie : tenir 10 min en médiane demande une batterie d'environ 7 min.
2. **Branche d'attente** : les PR entrent après l'étage court dans une branche `next` qui peut être rouge ; la batterie fait avancer main jusqu'au dernier commit vert de `next`. Main reste toujours vert, l'auteur est libéré en 2 à 5 min, mais son changement ne tourne qu'après la batterie. C'est le modèle déjà construit pour les convois (branche d'intégration par Spec). Il faut quand même la recherche du coupable et l'annulation, sur `next`.
3. **(c) par classe de risque** : seules les PR qui ne touchent que la documentation, les tests ou le Cockpit entrent après l'étage court ; les autres passent par (b). C'est déjà à moitié le cas : ces PR tournent sans les tests longs.
4. **(c) complet avec repère vert** : tout ce que liste la colonne (c). Le plus rapide, le plus à construire, et le seul où une réparation urgente arrive en 5 min.

État réel à connaître avant de trancher : depuis le 2026-10-10 00:37 (Paris), la règle « PR à jour avec main » est désactivée sur le dépôt (lu en direct ; auteur du changement non identifié). Sans elle et sans run sur main, l'usine est déjà en (c), sans rattrapage.

Avis en une ligne : (b) tient la qualité sans rien construire pour réparer main ; si le délai prime, la variante 2 donne l'essentiel du gain de (c) sans qu'un main rouge tourne.

---

## Détail sourcé

Tout ce qui suit a été lu le 2026-10-10 entre 00:55 et 01:30 (Paris), en lecture seule. Aucun réglage changé, aucun run lancé ou annulé.

### 1. Ce que l'usine lit sur main aujourd'hui

| Lecteur | Ce qu'il fait de main | Source | Effet d'un main rouge |
|---|---|---|---|
| Racine vivante (le dépôt d'où tournent les outils et les ordres) | `bin/factory-guard`, lancé toutes les 5 min par `orders/factory-guard.toml`, avance la racine jusqu'à `origin/main` (avance simple, arbre propre seulement) et recharge la configuration si `city.toml`, `pack.toml`, `orders/` ou `agents/` ont changé | `bin/factory-guard`, section 3a « the live root runs what is checked out, not what is merged » | Le défaut s'exécute au plus 5 min après la fusion : 18 des 19 ordres lancent des outils de `bin/` depuis cette racine (`orders/*.toml`, lignes `exec`), dont le robot de fusion lui-même |
| Branches de travail neuves | `bin/factory-do-work-workspace` crée la branche d'un ticket depuis `origin/<branche courante>`, donc `origin/main` pour l'usine | `bin/factory-do-work-workspace`, lignes 278 à 290 | L'auteur hérite du défaut ; son run de PR est rouge pour une raison qui n'est pas la sienne. `docs/DELIVERY.md` chiffre déjà ce coût : « A false red costs an agent a diagnosis and a second run » |
| Convois marqués (livraison d'une Spec sur une branche d'intégration) | `bin/spec-integration take-up` reprend la branche protégée dans la branche d'intégration et lance la commande de régression sur le résultat | `docs/SPEC_INTEGRATION.md`, « take-up » | « Red: nothing is pushed, and the red is recorded on the convoy » ; avec `--end-round`, un tour de fin de Spec est compté. Un rouge venu de main est donc imputé au convoi |
| Fermeture d'un ticket | `bin/deliver-close` ferme le bead seulement si la PR est fusionnée et si le workflow requis a un run `pull_request` réussi sur la tête exacte de la PR | ADR-0026, point 3 ; `bin/deliver-close` lignes 289 à 300 | En (c), ce run ne serait plus que l'étage court : le ticket se ferme et libère ses suivants avant que la batterie ait parlé. ADR-0026 a été écrit contre exactement ce cas (« closed when their pull requests were merely opened ») |
| Robot de fusion | `bin/pr-autopilot` arme la fusion automatique de chaque PR ouverte, signale une PR rouge par un bead P1, remet à jour une PR en retard par passage | en-tête de `bin/pr-autopilot` | Il ne regarde pas main : il n'a aucun moyen de voir un main rouge |
| Poussée directe sur main | `bin/factory-main-gate` (crochet `pre-push`) lance la batterie avant toute poussée locale vers main | en-tête du script ; `docs/DELIVERY.md`, « Main-landing gate » | Sans effet sur les fusions de PR (appel côté GitHub) |

Fait d'histoire : l'incident qui a créé `bin/factory-main-gate`. Le 2026-09-16, un commit entré directement sur main a cassé un contrôle que les tests avaient déjà ; « both CI and the live cockpit stayed broken for hours before it was noticed » (`docs/DELIVERY.md`, « Main-landing gate »). C'est un main rouge sans garde, dans cette usine.

### 2. Ce qui existe pour réparer, ce qui manque

| Besoin | État | Preuve |
|---|---|---|
| Voir un main rouge | Manque. Le workflow ne tourne plus sur `push` depuis le 2026-10-08 (« No run on `push` to main », `.github/workflows/ci.yml`) ; `tests/ci-workflow-cost-test.sh` échoue si on le remet. Un run sur main se lance à la main (`workflow_dispatch`) ; le dernier date du 2026-10-09 04:04 (Paris) | `gh run list --branch main` |
| Chercher le coupable (couper un groupe de commits en deux) | Manque. Aucun outil de `bin/` ou `lib/` ne fait de bissection | `git grep -iE 'bisect'` : seulement une compétence de diagnostic et des documents |
| Annuler un commit de main | Manque. Aucun outil ne fait `git revert`. Sur 120 PR fusionnées, aucune n'est une annulation | `git grep 'git revert'` ; `gh pr list --state merged` |
| Retour arrière existant | Deux, sans rapport avec le code de main : `bin/enable-strict-main-protection --rollback` (le réglage du ruleset) et `bin/reversibility-check` (migrations de base des dépôts produits) | `docs/DELIVERY.md` |
| Une personne ou un rôle de garde | Manque. Les rôles qui réagissent déjà à un signal : `bin/pr-autopilot` (PR rouge → bead P1), `bin/on-order-failed`, `bin/factory-watchdog`, `bin/escalation-door` | `ls orders/` |
| Signaler une PR rouge à son auteur | Existe : c'est le chemin de (b) | `bin/pr-autopilot`, point 3 « FLAG » |

Le robot de lots de (b) a lui aussi besoin de couper un lot rouge en deux. La recherche du coupable est donc à construire dans les deux cas ; (c) ajoute l'annulation, le run sur main, le repère vert et le sort de la fermeture.

### 3. Chiffres de l'usine, revérifiés

| Mesure | Valeur | Source |
|---|---|---|
| PR ouverte → fusionnée, 2026-10-09 | médiane 56 min, 9 sur 10 sous 150 min, 24 PR (la carte dit 53 et 142 ; la recherche de départ 50 et 135 sur 22 PR, plus tôt dans la soirée) | `gh pr list --state merged` |
| Même mesure, 2026-10-06 / 10-07 / 10-08 | 18 / 54 / 35 min | idem |
| Un run réussi | médiane 25,9 min le 2026-10-09 ; 16,9 le 10-08 ; 8,4 le 10-06 (runners GitHub, 4 lots) | `gh run list` |
| Runs du 2026-10-09 | 46 annulés, 27 réussis, 2 échecs | idem |
| PR avec au moins un run rouge | 13 branches sur 108 depuis le 2026-10-06, soit 12 % | idem |
| Runs sur main après fusion, quand ils existaient | 200 runs du 2026-09-24 au 2026-10-08 : 198 verts, 2 rouges (les deux le 2026-09-30, 21:22 et 23:00) | `gh run list --event push --branch main` |
| Part des échecs que l'étage court aurait vus | 5 fichiers sur 6 dans l'échantillon du 2026-10-08 (contrôles de règles d'une seconde ou moins) | `docs/DELIVERY.md`, « What to run before a pull request » |
| Charge de l'hôte pendant la lecture | 17 à 24 sur 12 cœurs | `/proc/loadavg` |

Comment les estimations de la page sont faites (calculs de l'agent, pas d'une source) :

- Délai de (b). Un seul runner, un job à la fois. Une PR arrive pendant qu'une batterie tourne : elle attend en moyenne une demi-batterie, puis son lot dure une batterie. D'où 1,5 × la batterie si le lot est vert. Un lot rouge ajoute les batteries de la bissection.
- Délai de (c). La PR entre dès l'étage court vert : contrôles de règles (110 fichiers, 118 s de test, « about half a minute on 4 cores », `docs/DELIVERY.md`) plus les tests touchés. Sur l'unique runner, cet étage attend derrière la batterie de main si elle tourne. Les 2 à 5 min supposent donc un second job en parallèle (tickets af-8km43c.6 et .7) ou un étage court lancé sur l'hôte avant la PR, ce que les auteurs font déjà.
- Fréquence d'un main rouge en (c). Entre 2 % des PR (12 % de PR rouges, dont 5 sur 6 arrêtées par l'étage court) et 12 % (si l'étage court n'arrête plus rien, parce que les auteurs le lancent déjà avant la PR depuis le 2026-10-08). À 25 PR par jour : de 0,5 à 3 par jour. L'échantillon de 6 fichiers est trop petit pour mieux.
- Durée d'un main rouge en (c). Détection : jusqu'à deux batteries (celle en cours, puis celle qui contient le commit). Coupable : log2 du nombre de commits du groupe, en batteries. Avec 4 commits et 25 min de batterie : environ 50 min de détection et 50 min de recherche, avant l'annulation.
- Le fond de la différence : (b) lie le délai de fusion à la durée de la batterie, (c) l'en détache. Plus la batterie raccourcit, moins (c) rapporte.

### 4. Ce que coûte un main rouge chez Google, Meta et Chromium

**Google** — *Software Engineering at Google*, ch. 23 (https://abseil.io/resources/swe-book/html/ch23.html).

- Pourquoi tout n'est pas testé avant : « The main reason is that it's too expensive. » Avant la fusion, seulement les tests « fast, reliable ».
- Ce que l'étage court laisse passer : « a change that passes the presubmit has a very high likelihood (95%+) of passing the rest of the tests ». Attente moyenne avant fusion : « around 11 minutes ».
- Deux changements verts séparément peuvent casser ensemble (« mid-air collision ») : « though generally rare, it happens most days at our scale ».
- Qui répare : « each team has a "Build Cop" », chargé de garder les tests verts « regardless of who breaks them », qui doit « drop whatever they are doing and fix the build ».
- Avec quoi : le retour arrière, « the most effective tool the Build Cop has », en deux clics pour n'importe quel changement ; TAP (leur système de test) annule seul quand il est sûr du coupable ; il coupe un groupe rouge en changements isolés, ce qui « can sometimes take a while to converge ».
- Ce qui protège ce qui est livré : deux têtes, la vraie (« true head ») et la verte (« green head », le dernier changement vérifié) ; « most teams cut these at green, as opposed to true, head ».
- Le livre ne donne ni le taux de casse ni le temps de réparation.

**Meta** — Machalica et al., « Predictive Test Selection », §II-B (https://arxiv.org/abs/1810.05286) et le billet du 2018-11-21 (https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/).

- Avant la fusion, une sélection de tests (moins d'un tiers de ceux que le changement peut atteindre) ; elle laisse passer, par construction, moins de 5 % des échecs de test et moins de 0,1 % des changements fautifs.
- Après : « Once every few hours, all tests are exercised on the most recent version of master branch », pour trouver des versions sans défaut détectable ; les versions candidates des applications mobiles ne partent que de celles-là.
- Le coût dit : tester un groupe de changements d'un coup fait que « it is usually not immediately clear which of the diffs was a culprit » ; les échecs deviennent des tickets, triés vers le propriétaire du test ou l'auteur du changement.
- Chaque PR est testée sur une version de main « known to pass all automated tests » : là aussi, on ne part pas de la tête.
- L'article ne parle ni de bissection ni d'annulation.

**Chromium** — doc du jardinier (https://chromium.googlesource.com/chromium/src/+/main/docs/gardener.md).

- Le jardinier est une personne de garde, à tour de rôle, employée de Google et habilitée à fusionner. Ses priorités, dans l'ordre : l'arbre est ouvert, pas de nouveaux échecs, les anciens réparés.
- Le coût dit : « when the tree is closed nobody can make progress ». Un arbre fermé arrête toutes les fusions.
- Son pouvoir : « Revert changes that you know or suspect are causing breakages », sans attendre l'auteur.
- La page ne donne ni durée de garde, ni nombre de personnes, ni temps de réparation.

Ce que les trois ont et que l'usine n'a pas : une garde humaine, un retour arrière d'un geste, une recherche du coupable, et un repère vert d'où partent les versions et les nouveaux changements. Aucun des trois n'exécute sa propre chaîne de livraison depuis la tête de main.

### 5. Les variantes, en détail

| Variante | Main | Auteur libéré | Changement en service | À construire en plus du robot de lots |
|---|---|---|---|---|
| 1. (b) + étage court | toujours vert | après son lot (1,5 × batterie) | idem | rien |
| 2. Branche d'attente `next` | toujours vert | après l'étage court | après la batterie | la branche, l'avance de main au dernier commit vert, l'annulation sur `next` ; les branches neuves partent de main (vert) ou de `next` (à trancher) |
| 3. (c) par classe de risque | rouge possible, seulement par une PR de documentation, de tests ou du Cockpit | étage court pour ces PR, lot pour les autres | idem | le run sur main, l'annulation ; la liste des zones existe (`config/ci-long-test-blind-areas.txt`) |
| 4. (c) complet + repère vert | rouge possible | après l'étage court | après l'étage court si la racine vivante suit la tête, après la batterie si elle suit le repère vert | tout le §2 |

La variante 2 est un lot permanent : au lieu de former un lot puis de le prouver, on laisse les PR s'accumuler sur `next` et la batterie prouve ce qui s'y trouve. Elle rejoint (b) quand `next` est vert et (c) quand il est rouge, mais le rouge ne touche ni la racine vivante ni les convois.

### 6. L'état du ruleset pendant cette lecture

`gh api repos/saymyname-app/agent-factory/rulesets/23626687`, lu à 01:05 et 01:07 (Paris) : `strict_required_status_checks_policy: false`, `updated_at` 2026-10-10 00:37:13 (Paris). Réglage du dépôt : `allow_update_branch: false`. Ce sont les deux valeurs que pose `bin/enable-strict-main-protection --rollback`. La recherche de départ lisait `true` le 2026-10-09 à 23:30, et `docs/DELIVERY.md` décrit `true` comme l'état voulu depuis le 2026-09-29.

Les 12 dernières PR fusionnées (jusqu'à la #489, 00:35 Paris) contenaient toutes la tête de main au moment de leur fusion : aucune n'est entrée en retard. La #490 était ouverte, fusion automatique armée.

Conséquence si l'état dure : deux PR vertes chacune sur un main plus ancien peuvent entrer l'une après l'autre et casser main ensemble (le cas que `docs/DELIVERY.md`, « Merge safety », dit avoir fermé), et aucun run sur main ne le verrait. Cette recherche n'a rien changé et n'a pas cherché qui a fait le changement.

## Non vérifié

- Qui a désactivé « PR à jour avec main » à 00:37, et si c'est voulu (essai d'une autre session, retour arrière délibéré).
- Si `bin/pr-autopilot` protège encore contre une fusion en retard quand le ruleset n'est plus strict : son garde lit l'état `BEHIND` que GitHub calcule, et il n'est pas établi que GitHub le calcule encore sans la règle stricte.
- Toutes les estimations de délai, de fréquence et de durée d'un main rouge : calculs sur des mesures de quatre jours et sur un échantillon de 6 fichiers ; rien n'a été essayé.
- La part des échecs que l'étage court arrêterait aujourd'hui (l'échantillon date d'avant la règle qui fait lancer cet étage par l'auteur).
- Chez Google et Chromium : le taux de casse, le temps moyen de réparation, la taille des gardes. Les sources lues ne les donnent pas.
- Chromium : l'objectif « arbre ouvert 7 heures sur 8 » et l'outil de recherche du coupable (Findit) apparaissent dans d'anciennes pages, pas dans la doc du jardinier actuelle ; non repris dans la page.
- Meta : l'article a été lu dans sa version HTML (ar5iv), pas dans le PDF ; ce que fait Meta d'un main rouge au-delà du ticket n'y est pas décrit.
- La variante 2 (`next`) n'a été lue dans aucune source sous cette forme : c'est le rapprochement, par l'agent, de la « tête verte » de Google et de la branche d'intégration des convois.
- Que 18 ordres lancent des outils depuis la racine vivante est un décompte des lignes `exec` de `orders/` ; l'effet réel d'un outil cassé sur chacun n'a pas été examiné.
