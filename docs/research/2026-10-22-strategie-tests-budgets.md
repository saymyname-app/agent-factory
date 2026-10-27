# Étude C : stratégie de tests et budgets de temps fondés sur des mesures (af-npz9v1)

Intent (Benjamin, ses mots, 2026-10-22 13:12 Paris) : « qu'on trouve une
méthode […] pour que ça n'arrive plus […] il faut qu'on puisse prévoir. »
Il refuse de relever la limite de 600 s à tâtons et demande une stratégie de
tests (tests propres au ticket, sélection par impact, un test rapide de bout
en bout, série complète en fin de Spec ou la nuit, défauts tardifs en
tickets de réparation) et des budgets prévus à partir de mesures (relais
« RELAIS OPÉRATEUR — PASSATION » d'`af-npz9v1`, réservation du 22/10 13:25).

Mechanism (agent interpretation) : lecture seule des preuves déjà produites
(magasin de preuves, journaux des sessions d'auteurs, code des portes),
aucune batterie lancée pendant l'étude ; stratégie et budgets proposés,
rien appliqué. Le sort de C2a (`af-k2rbw1`) et de F (`af-njwz8v`) reste la
décision de Benjamin : §6 propose seulement.

Jargon : **régression** = `launch.regression_command` du profil
(`python3 tests/cockpit-criteria/regression.py`). **Classe de critère** =
une classe `unittest` de `tests/cockpit-criteria/commands/` ; chacune lance
son propre Cockpit (et pour certaines un navigateur sans écran).
**Charge** = `load average` sur 8 vCPU. Heures : Paris (UTC+2).

## 1. Verdict

1. **La limite de 600 s n'est pas dépassée par la taille des tests seule,
   mais par la contention.** La même série, sur le même nombre de classes,
   dure environ 1,9 fois plus quand deux auteurs et une fusion font tourner
   leurs batteries en même temps (charge 35 à 108 relevée par les auteurs
   au moment des refus). La file d'attente de batteries de l'hôte, créée le
   08/10 pour exactement ce défaut (`docs/DELIVERY.md`, « batteries started
   on the host run one after the other »), ne couvre que `bin/ci-run-tests` :
   `regression.py` ne la prend pas. C'est la même catégorie de défaut,
   revenue par un autre lanceur.
2. **La taille grossit linéairement avec les classes de critère** :
   ≈ 9 s de plus par classe (8 en parallèle), ≈ 5 classes par ticket livré.
   Hors contention, la régression franchit 600 s vers le 8e ou 9e ticket
   livré du convoi ; au 14e elle dure ≈ 14 min seule, ≈ 27 min en
   contention, soit le délai de l'ordre `convoy-advance` (30 min).
3. **La pyramide est inversée** : la part qui grossit est faite de tests de
   bout en bout (un Cockpit chacun), rejoués en entier à chaque vert de
   chaque ticket, puis à chaque fusion. Un ticket paie la série de tous les
   tickets précédents, plusieurs fois.
4. **Trois délais fixes, sans lien entre eux ni avec une mesure** : 600 s
   (`bin/tdd-step`, `COMMAND_TIMEOUT`), 600 s (`bin/spec-integration`,
   `DEFAULT_TIMEOUT`), 30 min (`orders/convoy-advance.toml`). Un dépassement
   par lenteur est traité comme un refus du ticket.
5. **Réponse proposée pour C2a et F** (§6) : les relancer chacun seul, dans
   une fenêtre calme ; la courbe mesurée prévoit 6 à 7 min (marge ≈ 30 %).
   Puis la tranche T1 (§5) pour ne plus dépendre d'une fenêtre calme.

## 2. Carte réelle

### 2.1 Étapes de test d'un ticket (code lu à la racine live `6705256e`)

| Étape | Ce qui tourne | Délai | Source |
|---|---|---|---|
| `tdd-step red` | chaque test de critère du ticket, une fois, au commit de départ | 600 s par test | `bin/tdd-step` `COMMAND_TIMEOUT` |
| `tdd-step green` | les tests gelés du ticket **k = 3 fois** contre le produit à la pointe, **puis la régression entière** | 600 s par test ; **600 s pour la régression** | `check_green`, `regression_run` ; `k` dans `config/project-descriptors/agent-factory.json` |
| `tdd-step amend` | nouveau rouge des tests amendés | 600 s par test | idem |
| `tdd-step prefactoring` | la régression avant et après | 600 s chacune | idem |
| fusion (`spec-integration merge`) | la régression sur le résultat fusionné, 1 ticket par passe | 600 s | `bin/spec-integration` ; `MERGES_PER_PASS = 1` |
| fin de Spec (`spec-integration take-up`) | la régression à la pointe de la branche d'intégration | 600 s | `docs/SPEC_INTEGRATION.md` |
| passe de l'ordre | tout ce qui précède dans une passe | 30 min | `orders/convoy-advance.toml` |
| CI GitHub | toute la batterie Factory, en lots (`--shard`) ; les mesures de fidélité y sont sautées | — | `.github/workflows/ci.yml` |

`regression.py` lance en parallèle (4 à la fois) les `tests/cockpit-*-test.py`
et deux tests du lanceur, puis **seul, à la fin**, `tests/cockpit-criteria-test.py`,
qui rejoue toutes les classes de critère de tous les tickets livrés, autant à
la fois que de cœurs (8).

### 2.2 Durées mesurées sur les résultats fusionnés

Source : pièces `merged_tests` du magasin de preuves
(`~/.local/state/agent-factory-evidence/<spec>/<ticket>/merged_tests.json`,
lignes `PASS <fichier> (<s>)` écrites par `regression.py`). Classes comptées
au commit fusionné (`git show`, `^class …(…):`).

| Spec / ticket | Fusion (Paris) | Classes | `cockpit-criteria-test.py` | Autres fichiers (somme / plus long) |
|---|---|---|---|---|
| af-2zseit / T01R6 `af-ltchro` | 15/10 18:15 | 1 | 9 s | 224 / 28 s |
| af-2zseit `af-qjq1t6` | 17/10 05:01 | 2 | 11 s | 245 / 31 s |
| af-2zseit `af-h385tk` | 17/10 05:03 | 3 | 11 s | 260 / 34 s |
| af-2zseit `af-r2c0tx` | 20/10 00:16 | 6 | 65 s | 246 / 30 s |
| af-fgcw0d / A1 `af-c662qx` | 21/10 22:43 | 9 | 140 s | 238 / 29 s |
| af-fgcw0d / E `af-8rbceu` | 22/10 01:14 | 12 | 174 s | 254 / 31 s |
| af-fgcw0d / C1 `af-lzti7w` | 22/10 04:28 | 21 | 275 s | 324 / 55 s |
| af-fgcw0d / G1 `af-wrxrmg` | 22/10 13:08 | 26 | 288 s | 337 / 55 s |

- Partie parallèle ≈ somme / 4 ≈ **85 s** (bornée par le plus long, 55 s) :
  stable, elle ne fait pas le problème.
- Ajustement linéaire sur les quatre fusions du convoi :
  **critères ≈ 64 s + 9,15 s × classes**. Durée totale hors contention
  ≈ 150 s + 9,15 s × classes (6 min 15 pour G1, estimation : la durée
  totale n'est pas enregistrée).
- Classes ajoutées par ticket du convoi : 3, 3, 9, 5 → **≈ 5 par ticket**.

### 2.3 Durées au vert, sous contention

Source : journaux des sessions d'auteurs sur la VM
(`~/.claude/projects/-home-benja-agent-factory--gc-agents-delivery-author/*.jsonl`),
recherche des réponses de `tdd-step green`.

| Ticket | Refus « la commande de régression n'a pas fini en 600 s » (Paris) | Charge relevée par l'auteur |
|---|---|---|
| C1 `af-lzti7w` | 21/10 08:43 | — |
| C2a `af-k2rbw1` | 22/10 05:34, 07:40, 08:10, 08:56 | 29–39 ; 18 → 60 ; 15 → 108 |
| F `af-njwz8v` | 22/10 06:46, 07:33, 08:34 | 32 → 48 ; 12 → 65 |
| G1 `af-wrxrmg` | 22/10 10:35 | — |
| A1 `af-c662qx` | 21/10 07:33 : un **test de critère** à 600 s (`home-d01-records`) | — |

- F, lancée à la main à 00dfd2b2 (30 classes) : **11 min 42, tout vert,
  dont 549 s de critères, sous une charge de 35**. La courbe du §2.2 donne
  ≈ 340 s de critères hors contention : facteur ≈ 1,6 à 1,9.
- C2a à 52f1603b (25 classes) : verte seule en 8 min 30 (charge non notée).
  Courbe : ≈ 6 min 20.
- Contrôle de cohérence : la courbe × 1,9 à 26 classes donne ≈ 12 min, ce
  que F a mesuré.

### 2.4 Répétitions par ticket

Comptées dans les mêmes journaux (21–22/10 ; un même lancement vu deux fois
quand l'auteur le relit en arrière-plan) :

| Ticket | `tdd-step green` lancés | `amend` |
|---|---|---|
| A1 `af-c662qx` | 15 | 4 |
| C1 `af-lzti7w` | 12 | 2 |
| F `af-njwz8v` | 9 | 0 |
| C2a `af-k2rbw1`, D `af-ten1sp`, G1 `af-wrxrmg` | 7 chacun | 1, 4, 3 |
| E `af-8rbceu` | 5 | 2 |
| B `af-4uzgzm` | 2 | 1 |

S'y ajoutent 25 `regression.py` lancés à la main par les auteurs, une
régression par fusion (plus une par fusion rejouée après un rouge), deux
par `prefactoring`. Ordre de grandeur : **4 à 10 régressions entières par
ticket**, 30 à 100 min de VM chacun, sur une VM partagée par deux auteurs.

Un piège à part : 13 lancements se terminent à 600–602 s, c'est la limite
de 10 min de l'outil Bash de Claude Code au premier plan, pas `tdd-step`.
L'auteur relance alors en arrière-plan, ce qui double des batteries.
L'étude A (copies orphelines) en a la charge ; ici, seul compte que ces
relances ajoutent de la contention.

### 2.5 Projection jusqu'au 14e ticket

Hypothèses : +5 classes par ticket, 9,15 s par classe, partie parallèle
stable, facteur de contention 1,9 quand trois batteries tournent ensemble.

| Tickets livrés | Classes | Régression seule | En contention |
|---|---|---|---|
| 4 (aujourd'hui) | 26 | ≈ 6 min 15 | ≈ 12 min |
| 6 | 36 | ≈ 8 min | ≈ 15 min |
| 9 | 51 | **≈ 10 min 20 (> 600 s)** | ≈ 20 min |
| 14 (fin du convoi) | 76 | ≈ 14 min 10 | **≈ 27 min (≈ 30 min de l'ordre)** |

La Spec suivante repart de 76 classes : sans changement, chaque Spec ajoute
≈ 10 min seule.

## 3. Stratégie cible (minimale)

Principe : chaque niveau ne rejoue que ce qu'il peut casser ; le complet
tourne une fois, au bon endroit ; une lenteur n'est jamais un rouge.

| Niveau | Quand | Ce qui tourne | Ce qui n'y est plus |
|---|---|---|---|
| N0 propres au ticket | `red`, `green` | les tests gelés du ticket, k = 3 (inchangé) | — |
| N1 vert rapide | `green`, `prefactoring` | la partie parallèle (≈ 85 s) + **un test de bout en bout** (`isolated-launch-test.py::IsolatedCockpitLaunch`, lance un vrai Cockpit) + **les classes des familles touchées** | les classes des autres familles |
| N2 fusion | `spec-integration merge` | N1 + **toutes les classes de la Spec en cours** + le bout en bout | les classes des Specs livrées |
| N3 complet | fin de Spec (`take-up`) et **chaque nuit** sur chaque branche d'intégration ouverte | tout, fidélité comprise | — |

- **Sélection par impact, liste fermée** (même forme que
  `config/ci-long-test-blind-areas.txt`) : une famille = un préfixe de
  fichier de critère (`home-`, `runs-`, `factory-`, `projects-`, `request-`)
  liée à ses dossiers (`lib/cockpit/ui/<zone>`, `lib/cockpit/<zone>`). Un
  fichier changé hors de la liste (cœur, `bin/cockpit*`, harnais, fixtures)
  → toutes les familles. Pas de graphe de dépendances calculé.
- **Lenteur ≠ rouge** : un délai dépassé rend « NOT RUN » (comme
  `ci-run-tests`, sortie 75), ne compte ni comme refus du ticket, ni comme
  tour de correction, ni comme renvoi de fusion.
- **Défauts tardifs** : un rouge de N2 renvoie le ticket qui fusionne (c'est
  son défaut, détecté une étape plus tard qu'aujourd'hui) ; un rouge de N3
  (nuit ou fin de Spec) devient un ticket de réparation par la porte
  existante des tours de réparation de fin de Spec
  (`docs/CONVOY_ADVANCE.md`, Spec §8), sans rouvrir les tickets fusionnés.
- **Une batterie à la fois sur l'hôte** : `regression.py` prend le verrou de
  `ci-run-tests` ; le délai compte à partir du verrou obtenu, l'attente a
  sa propre borne.

Risque accepté : ADR-0030 L1 voulait qu'un ticket ne fusionne jamais un
rouge que son auteur aurait vu. Avec N1, un ticket qui casse une famille
qu'il ne touche pas selon la liste est vu à N2 (un renvoi au lieu d'un
refus au vert). Mesure de contrôle : renvois de cette cause par Spec ;
au-delà d'un, on élargit la liste.

## 4. Budgets dérivés des mesures

**Une source** : `config/test-budgets.json`, écrite par un outil à partir
des durées enregistrées (même modèle que `config/ci-test-seconds.tsv` et
`bin/ci-test-seconds`), lue par `tdd-step` et `spec-integration`. Plus de
constante dans le code.

| Budget | Formule | Valeur estimée aujourd'hui |
|---|---|---|
| test de critère (par test) | 1,5 × p90 des durées d'un test, verrou tenu | à mesurer (T2) ; 600 s en attendant |
| N1 vert | 1,5 × p90 des 10 derniers N1, verrou tenu | ≈ 85 + 20 + ≤ 10 classes ≈ 4 min → **≈ 6 min** |
| N2 fusion | 1,5 × (150 s + 9,15 s × classes de la Spec en fin de Spec, prévues) | convoi af-fgcw0d : ≈ 70 classes → ≈ 13 min → **≈ 20 min** |
| N3 nuit | borne de l'ordre de nuit, comme `local-only-tests` (6 h) | — |
| passe `convoy-advance` | **déduite** : ≥ attente du verrou + budget N2 + 5 min | 30 min tient si N2 ≤ 20 min et l'attente ≤ 5 min |

- **Alerte** : quand une exécution dépasse 80 % de son budget, la réponse de
  la porte le dit et une ligne va dans `var/factory-metrics.jsonl`.
- **Projection** : au départ d'une Spec, classes prévues = critères des
  tickets restants (`tests/cockpit-criteria/<ticket>-criteria.json`) ;
  budget N2 projeté au-delà de la passe de l'ordre → alerte avant le
  premier ticket, pas au 9e.
- **Unification** : les trois délais d'aujourd'hui deviennent : budget N1
  (`tdd-step`), budget N2 (`spec-integration`), passe de l'ordre déduite et
  vérifiée par un test qui échoue si l'inégalité ne tient pas.

## 5. Plan en tranches (une journée chacune, utiles seules)

| # | Tranche | Utile seule parce que | Preuve |
|---|---|---|---|
| T1 | `regression.py` prend le verrou de batterie de l'hôte ; délai compté verrou obtenu ; un dépassement rend « NOT RUN » au lieu d'un refus | supprime le facteur 1,9 et les refus par contention ; débloque C2a et F sans toucher aux 600 s | test sur le modèle de `tests/ci-run-tests-host-queue-test.sh` ; deux verts consécutifs mesurés |
| T2 | mesures : `regression.py` écrit la durée par fichier et par classe de critère dans la pièce (`tdd_green` ne garde aujourd'hui que 300 caractères) | les budgets et la projection reposent sur des chiffres, pas sur cette étude | pièce relue sur un vert |
| T3 | `config/test-budgets.json` + outil de rafraîchissement ; `tdd-step` et `spec-integration` le lisent ; alerte 80 % ; test de l'inégalité de l'ordre ; projection au départ de Spec | fin des constantes ; on voit venir le dépassement | test de l'outil ; projection affichée pour af-fgcw0d |
| T4 | niveaux N1/N2 : liste fermée familles → dossiers, repli « tout » ; fusion = Spec en cours + bout en bout | le vert ne grossit plus avec le convoi | test de sélection (fichier hors liste → tout) ; durée N1 mesurée |
| T5 | N3 : ordre de nuit sur chaque branche d'intégration ouverte ; rouge → ticket de réparation par la porte de fin de Spec ; renvoi par lenteur ne consomme aucun tour | les défauts tardifs ne bloquent plus les tickets en cours | test de l'ordre ; un rouge simulé crée un ticket |

Ordre : T1 aujourd'hui (petit, maintenance Factory). T2 puis T3. T4 avant le
6e ticket livré (régression seule ≈ 8 min, alerte 80 % du budget actuel).
T5 en dernier. Ce qui touche la règle des tours de correction (T5) se
coordonne avec l'étude B (causes racines) avant de coder.

## 6. Réponse immédiate proposée pour C2a et F (décision de Benjamin)

État vérifié 22/10 16:07 Paris : C2a et F `in_progress`, sans arrêt écrit
(`bin/convoy-state show af-strhoy`) ; leurs auteurs attendent la réponse de
l'opérateur ; aucun `tdd-step`, `regression.py` ni `spec-integration` ne
tourne ; charge 8,7.

- **a (recommandé)** — Relancer `tdd-step green` de C2a, puis celui de F,
  **un à la fois, quand aucune autre batterie ne tourne** (vérifié par
  `pgrep` juste avant). Prévu par la courbe : C2a ≈ 6 min 20 (25 classes),
  F ≈ 7 min (30 classes), sous 600 s avec ≈ 30 % de marge. Aucune limite
  relevée, aucun code. Puis T1, pour que le suivant ne dépende plus d'une
  fenêtre calme.
- **b** — Si l'un des deux est refusé alors qu'il tournait seul : budget
  ponctuel = 1,5 × la durée mesurée seule, écrit avec ses mots ; une
  hausse mesurée, pas à tâtons, en attendant T3.
- **c (déconseillé)** — Dérogation ou Planning Exception : le ticket est
  vert ; ce n'est pas un défaut du ticket.

## 7. Limites

- La durée totale d'une régression n'est pas enregistrée : « totale » =
  85 s estimées + critères mesurés.
- La charge au moment des fusions n'est pas enregistrée ; le facteur 1,9
  vient d'un seul point (F, charge 35), recoupé par la courbe.
- Le coût par classe n'est pas mesuré classe par classe (T2) : les classes
  à navigateur coûtent sans doute plus que la moyenne.
- Les comptes de `tdd-step green` viennent des journaux de session : ordre
  de grandeur, doublons possibles.
