# Causes racines des incidents d'usine (15–22/10/2026) et correctifs de catégorie

- Date : 22/10/2026, heure de Paris. Bead : `af-npz9v1.13` (épopée `af-npz9v1`).
- Intent (Benjamin, ses mots, 22/10 13:12 Paris) : « qu'on trouve une méthode,
  là, maintenant, pour que ça n'arrive plus, que tous ces problèmes-là ne
  puissent récidiver et ne réarriver sous une autre forme. Enfin, il faut
  qu'on puisse prévoir. »
- Mechanism (interprétation de l'agent) : étude seule. Elle classe les
  incidents, cherche dans le code les autres chemins qui portent le même
  défaut et propose une méthode. **Rien n'est mis en place ici** : la mise en
  place attend l'accord de Benjamin.
- Sources : corps et fichiers des PR #617 à #718 (aucune PR après #718 au
  22/10 16:30), beads des PR `do-work`, relais de `af-npz9v1`, notes de session
  du 21/10, code de `main` à `6705256e` et de `integration/af-fgcw0d`, lus en
  lecture seule. OBSERVÉ = lu dans une source citée ; INFÉRÉ = déduit, à
  vérifier.
- Travaux voisins, à ne pas refaire ici : copies orphelines du 22/10 (étude A),
  stratégie de tests et budgets de temps (étude C), avis sur « Pour moi » et
  « Analyses » (étude D), vérification du livré, prévision des tickets restants.

## 1. En une phrase

Sur 102 PR en 7 jours, environ 70 réparent l'usine. Presque toutes tombent dans
**trois catégories de défaut**, et chaque catégorie est revenue 5 à 7 fois sous
une autre forme, parce que chaque correctif a réparé le cas observé et a écrit
le reste « hors périmètre ». Les correctifs qui n'ont pas récidivé sont
justement ceux qui ont posé un contrôle automatique de toute la catégorie.

## 2. Les trois catégories principales

| Code | Catégorie | Invariant violé | PR | Chaînes de récidive |
|---|---|---|---|---|
| **P** | Processus ou durée sans propriétaire ni budget mesuré | Tout ce qu'un outil lance meurt avec lui ; tout délai vient d'une mesure | ≈ 19 | orphelins : #624 → #628 → #630 → #647 → #708 → #710 → 22/10 (sans PR) ; délais : #629 → #694 → #705 → #708 → tdd-step 600 s du 22/10 ; #636 → #657 → #667 |
| **I** | Impasse d'état : un arrêt ou une attente sans sortie codée | Chaque arrêt, et chaque option proposée à Benjamin, a un chemin de code qui fait bouger le ticket | ≈ 16 | #635 → #653 ; #637 → #662 ; #673 → #679 → #682 ; #687 → #711 → #718 ; #702 → #704 → #712 ; #709 |
| **D** | Doublure, instrument ou vue partielle qui ne se comporte pas comme le réel | Un faux outil refuse ce que le vrai refuse ; un instrument est étalonné avant de juger ; on juge l'état résultant, pas un morceau | ≈ 20 | fidélité : #674 → #675 → #676 → #680 → #692 → #682 ; faux `bd` : #699 → #700 ; `HOME` : #566 → #671 → #690 ; vue partielle : #656, #669, #714 |

Catégories secondaires : **R** une même règle tenue à deux endroits (deux
outils, deux sessions, un écrivain et son lecteur) qui divergent, ≈ 9 PR ;
**S** signal faux ou manquant, ≈ 4 PR ; **A** autre, ≈ 6 PR.

## 3. Table des incidents

Les PR qui exécutent une décision sans corriger un défaut (ADR-0030 L0–L7 :
#617, #618 en partie, #621, #626, #632, #645, #652, #654 ; ADR-0032 #682 ;
#623, #633, #640, #644, #646, #678 essai à 3 auteurs ; #627, #642, #643
outillage ; #683, #684, #697 Cockpit ; #668 relecteur Codex ; #691, #701
ordres ; #698 abandon de convoi ; #712 deux tours) ne sont pas des incidents.
Elles apparaissent quand un incident y mène.

| PR | Date | Symptôme | Cause | Correctif | Cat. | Lié à |
|---|---|---|---|---|---|---|
| #618 | 15/10 | T01R6 casse un test du Cockpit, vu seulement à la fusion | La régression ne tournait qu'après la fusion | Régression au départ de l'auteur | D | #708 |
| #619 | 15/10 | Graphe Cockpit en file indienne (chemin critique 34) | Aucune question ne mesurait le parallélisme | Contrôle calculé `critical_path_bounded` (correctif de classe) | A | #620, #656 |
| #620 | 15/10 | 17 tickets refusés « même surface » | Question de relecture contraire à ADR-0031 | Question réécrite | R | #619 |
| #622 | 15/10 | T59 ne peut pas prouver son rouge | Portes absentes des points d'entrée du profil | Profil complété | A | — |
| #624 | 15/10 | Cockpits vivants des jours, 2,7 cœurs | `finally` jamais exécuté sous SIGKILL | `--owner-pid` pour 4 outils de `bin/` ; 3 exclus ; résidu « pendant le démarrage » nommé | P | #628 |
| #625 | 15/10 | Révision de graphe publiée sans relecture | La porte ne relisait que la 1re publication | Même porte pour la révision | R | — |
| #628 | 16/10 | 3,2 cœurs encore pris | Le résidu nommé par #624 était le chemin principal | Garde dès le 1er enregistrement | P | #624 |
| #629 | 16/10 | Plus aucune passe ne finit | Contrôle de fidélité > 5 min, repart de zéro | (bead af-pxijl6) | P | #694 |
| #630 | 16/10 | 3 Cockpits arrêtés à la main | `stop` refusait un dépôt supprimé ; produits d'évaluation « hors sujet » (af-30zwwu, **toujours ouvert**) | `stop` accepte | P | af-30zwwu |
| #631 | 16/10 | 34 lectures de convoi par minute | `settle` relit tout pour chaque ticket | Filtre | P | — |
| #635 | 16/10 | Décisions de Benjamin sans objet | Planning Exception sans option « accepter » | Option toujours offerte | I | #653 |
| #636 | 16/10 | T02 coupé 4 fois à 3 600 s | Délai fixe, 24 jeux de 3 min | Délai par jeu ; `outcome-evaluation` écrit « hors périmètre » | P | #657, #667 |
| #637 | 16/10 | T59 arrêté à vie | L'étape qui l'a arrêté n'existe plus ; « nothing lifts the stop » | Cause de reprise `stage_removed` | I | #662 |
| #639 | 16/10 | Réparation d'un test invisible au vert | Gel de tout `tests/` | Gel des seuls tests de critère | A | — |
| #641 | 16/10 | CI rouge après un contrôle local vert | Le contrôle local ne lançait que les tests modifiés | Tests qui nomment le fichier | D | #696 |
| #647 | 16/10 | 24 copies du Cockpit à la fois, VM saturée | Fidélité lançait tous les états ensemble | Un état à la fois | P | #708 |
| #648 | 16/10 | R1 refusé deux fois | Tests du lanceur hors dépôt Git | Tests sur un dépôt qu'ils possèdent | D | — |
| #650 | 16/10 | Ticket débloqué retombe sur le même défaut | La reprise `unblocked` ne prenait pas l'intégration | Fusion de l'intégration | I | — |
| #651 | 16/10 | 7 fausses alertes « faux succès » | Échecs déjà pris en charge | Filtre | S | #717 |
| #655 | 16/10 | `--help` écrit une ligne de métriques | Analyse d'arguments maison | argparse | A | — |
| #656 | 17/10 | Histoires « orphelines » dans une révision | Le relecteur ne voit que les tickets changés ; même limite écrite « hors périmètre » pour le chemin critique | Question retirée pour une révision | D | #669 |
| #657 | 17/10 | T02 épuise 2 lancements | Attente d'un jeu comptée contre l'Evaluator | Attente déduite | P | #636 |
| #658 | 17/10 | Coût d'évaluation invisible au graphe | — | Contrôle calculé | P | #636 |
| #659 | 17/10 | Tickets Cockpit qui réparent l'usine | Pas de règle | Règle « défaut d'usine sur main » | R | #660 |
| #660 | 17/10 | Deux réparations du même défaut | Chaque blocage publiait sa réparation | Rattacher à la réparation ouverte | R | #659 |
| #661 | 17/10 | Siège de relecteur tenu, revues expirées | Session servie gardée chaude par Gas City | Ordre qui libère le siège ; auteur « non couvert » | P | #662 |
| #662 | 17/10 | T59, T62R arrêtés à vie | Rien ne levait `code_review_no_result` | Cause de reprise | I | #637 |
| #664 | 17/10 | Passes en échec, relevé illisible | Mesure de fidélité tronquée | (bead af-2cpwkh) | D | #665, #680 |
| #665 | 17/10 | `Argument list too long` | 2,7 Mo en un argument ; limite du noyau absente des faux | Relevé borné ; 3 « constats hors ticket » | D | #680 |
| #666 | 17/10 | Convoi immobile | Revue défavorable antérieure au tour : chacun attend l'autre | Revue rejouée | I | #718 |
| #667 | 17/10 | (prévu) évaluation de fin sur 95 jeux | Le « hors périmètre » de #636 | Même règle de délai | P | #636 |
| #669 | 17/10 | Remplacement refusé | Lecture d'un brouillon partiel, pas du graphe résultant | Graphe résultant | D | #656 |
| #670, #663, #707, #634 | 16–21/10 | Tests nocturnes de cité isolée rouges (1, 2, 5, 8 échecs) | Divers (beads `[local-only-tests]`), non relus ici | — | A | — |
| #672 | 18/10 | Retrait de deux tickets impossible | Autorisation posée pour une seule décision | `--decision` répété | I | — |
| #673 | 18/10 | T02R attend sans fin, personne prévenu | Fidélité rouge, revue et évaluation vertes : aucune sortie | Arrêt + demande | I | #679, #682 |
| #674 | 18/10 | T02R rouge sur des états d'un autre ticket | Fidélité mesurée sur tous les états ; thème clair « hors périmètre » | États nommés | D | #675 |
| #675 | 19/10 | Thème clair faux | Outil jamais essayé sur ce prototype | « non mesurable » | D | #676 |
| #676 | 19/10 | Tous les tickets d'interface rouges | Suite de #675 | Convention de thème | D | #692 |
| #677 | 19/10 | Réponse d'agent signée Benjamin | Acteur écrit en dur | `--actor` obligatoire | A | — |
| #679 | 19/10 | Option « passer outre » trompeuse | L'arrêt ne nommait qu'une condition rouge | Toutes les conditions nommées | S | #673 |
| #680 | 19/10 | Preuve de fidélité disparue | Mesure sous `/tmp` effacée | Pièce jointe scellée | D | #665 |
| #681 | 19/10 | Fidélité rendue bloquante | Décision contraire prise dans une autre session | Défait par #682 une heure après | R | #693 |
| #685 | 19/10 | 11 brouillons approuvés restent « À faire » | Le lecteur lit une étiquette que l'écrivain ne pose jamais | Lecture des clés d'approbation | R | — |
| #686 | 19/10 | Tout ticket amendé refusé à la fusion | `ticket-end` lit la pièce de rouge d'avant l'amendement | Pièce d'amendement | R | #703 |
| #687 | 19/10 | T02R2 bloqué après dérogation | Quatre verrous « un ticket arrêté ne fait rien » | Évaluation d'un arrêt dérogé | I | #711, #718 |
| #688 | 19/10 | Tickets immobiles vus 2–3 h après | Aucune alerte « personne ne bouge ce ticket » | Contrôle 9 du gardien + test en tableau (correctif de classe) | S | #687 |
| #689 | 19/10 | Tests de critère rouges en CI seulement | Le CI n'a pas le navigateur des hôtes | Navigateur et profil AppArmor | D | — |
| #690 | 19/10 | Garde rouge alors que la preuve existe | `HOME` = racine de la cité sous un contrôle Gas City | Résolution unique + lint (correctif de classe, 3e occurrence) | D | #566, #671 |
| #692 | 20/10 | Défauts de l'outil trouvés par le run | Instrument jamais étalonné | `calibrate` à l'approbation de la Spec (correctif de classe) | D | #674–#676 |
| #693 | 20/10 | #681 contre une décision | Personne ne regarde ce que l'autre change | `bin/factory-fix-preflight` (collisions) | R | #681 |
| #694 | 20/10 | `convoy-advance` tuée 5 fois à 300 s | La passe attend le verrou sur son délai ; attend la fidélité | Passe sautée ; plus d'attente | P | #705, #708 |
| #695 | 20/10 | Test d'ordres rouge | L'ordre en pause n'existe plus pour `gc order show` | Test adapté | R | — |
| #696 | 20/10 | Contrôle local de 2 h | Les tests qui nomment le fichier (#641) font ¼ de la batterie | Laissés au CI | P | #641 |
| #699, #700 | 20/10 | Retrait d'un ticket bloqué impossible | `bd` refuse de fermer un ticket bloqué ; **le faux `bd` acceptait** | `--force` ; faux rendu fidèle (deux outils, deux PR) | D | — |
| #702 | 20/10 | D arrêté malgré la réponse « a » | L'option « a » n'avait aucun code derrière | Cause `amendment_granted` | I | #704 |
| #703 | 21/10 | Vert impossible | `amend` et `green` ne lisent pas le même ensemble de fichiers | Aides du périmètre comptées | R | #686 |
| #704 | 21/10 | Arrêt garanti | Constat sur un test gelé après l'amendement unique | Un amendement par tour | I | #712 |
| #705 | 21/10 | `convoy-advance` en échec (délai) | (bead af-ebqm1y) | Verrou de passe | P | #694 |
| #706 | 21/10 | `pr-autopilot` en échec | Budget de temps épuisé | (bead af-qe1bqx) | P | — |
| #708 | 21/10 | Aucune fusion, batteries empilées, charge 55 | Ordre tué à 300 s, régression jusqu'à 600 s ; `subprocess.run` ne tue que l'enfant | Délai 30 min ; groupe tué **dans `spec-integration` seulement** ; `--owner-pid` **pour les tests de critère seulement** | P | 22/10 |
| #709 | 21/10 | D parqué, aucune réponse ne lève | Lever un parcage d'évaluation n'avait aucun chemin | Réponse « a » = prouvé par le test | I | — |
| #710 | 21/10 | Une batterie sature encore la VM | Cockpit de test relit ses sources toutes les 0,2 s | 1 s | P | #708 |
| #711 | 21/10 | F, G1 bloqués à vie | `at_work()` exclut tout arrêté ; `returned` refusé | Reprise d'un arrêt dérogé | I | #718 |
| #713 | 22/10 | `convoy-advance` en échec | Fidélité : produit qui ne répond pas fait échouer la passe | (bead af-al1pvd) | P | #694 |
| #714 | 22/10 | G1 refusé pour les lignes d'A1 | Diff lu depuis la base du rouge, pas depuis l'intégration prise | Base = merge-base | D | — |
| #715 | 22/10 | Critères de B impossibles | Le Cockpit d'essai remplaçait les portes par `/bin/false` | Portes réelles sur un faux suivi | D | #716 |
| #716 | 22/10 | Toutes les fusions du convoi refusées | #715 en conflit avec l'intégration | Déplacement | R | #715 |
| #717 | 22/10 | 3 fausses demandes à Benjamin | Bead d'échec fermé promu | Filtre | S | #651 |
| #718 | 22/10 | F, G1 immobiles des heures | Deux outils refusent d'ouvrir la revue que la fusion attend | Dérogation = verdict favorable | I | #666, #711 |
| — | 22/10 | 24 copies orphelines, charge 141 | Autre lanceur que celui corrigé par #708 (voir § 4.1) | Arrêtées à la main | P | #708 |

## 4. Où ailleurs ? Les autres chemins qui portent le même défaut

Recherche faite le 22/10 sur `main` à `6705256e` et sur `integration/af-fgcw0d`.

### 4.1 P — processus et durées

OBSERVÉ :

- `bin/tdd-step:414` (`run_test`) et `bin/tdd-step:742` (`regression_run`) :
  `subprocess.run(..., timeout=COMMAND_TIMEOUT)` (600 s), sans session propre
  ni `killpg`. C'est le défaut que #708 a corrigé dans `bin/spec-integration`
  seulement. Au délai, Python tue `regression.py` et laisse vivre ses enfants
  (un processus par fichier de test, `tests/cockpit-criteria/regression.py:48`).
  Chacun de ces enfants est le propriétaire (`--owner-pid`) du Cockpit qu'il a
  lancé : tant qu'il vit, la garde de #624 ne tue rien.
- Même forme : `bin/ticket-author:116` (`run`, délais 180 s et 600 s),
  `bin/fixture-city-oracle:1173` (600 s), `lib/evaluation_observations.py:12`
  (90 s), `bin/provider-failover` (13 délais, aucun arrêt de groupe).
- `lib/evaluation_observations.py:74` lance `project-launch start` sans
  `--owner-pid`, détaché par conception ; le bead `af-30zwwu` (« produits
  préparés d'évaluation vivants après un test tué ») est ouvert depuis le
  16/10.
- Le test de #624 (« tout lanceur de `bin/` possède son produit ») ne lit que
  `bin/` : `lib/` et `tests/` lui échappent.
- Délais : une vingtaine de constantes écrites à la main (600 s dans
  `tdd-step`, `spec-integration`, `spec-end`, `evidence-capture`,
  `ticket-author`, `ticket-exit` ; 3 600 s ; ordres de 60 s à 6 h). Seules les
  évaluations (#636, #667) dérivent leur délai d'une mesure.

INFÉRÉ, à vérifier par l'étude A : les 24 copies du 22/10 au matin viennent de
ce chemin. Le même matin, `tdd-step green` a refusé C2a et F au-delà de 600 s
(relais du 22/10 13:25). Ce refus tue `regression.py` et laisse ses tests et
leurs Cockpits vivants sur une VM saturée, où un test peut attendre longtemps.

### 4.2 I — impasses d'état

OBSERVÉ dans `lib/convoy_state.py:380-460` : 8 raisons d'arrêt, 4 seulement
ont une cause de reprise (`RESUMABLE_STOPS`).

- `evaluation_outage` : aucune cause de reprise.
- `criterion_already_green` : l'option « Clore ce ticket comme satisfait »
  n'a aucune porte. #653 l'a écrit comme écart, le 16/10.
- `outcome_evaluation_no_result`, `outcome_evaluation_outage`,
  `story_unobservable` (fin de Spec) : aucun chemin de reprise trouvé par leur
  nom dans `bin/` et `lib/`. **Prévision** : le premier de ces arrêts en fin de
  Spec `af-fgcw0d` demandera une maintenance, comme #637, #662 et #709.
- `still_refused` sans dérogation complète : seules sorties, `grant` s'il
  reste un tour, ou une Planning Exception. C'est le cas de D (Analyses)
  aujourd'hui.
- Porte manquante côté Spec : « relancer un ordre mis en pause » (écart 1 de
  B, Pour moi).

Le test en tableau de #688 couvre les fins du travail d'auteur. Il ne couvre ni
les arrêts d'évaluation ou de fin de Spec, ni les options proposées dans les
demandes.

### 4.3 D — doublures, instruments, vues partielles

OBSERVÉ :

- 38 faux exécutables sous `tests/fixtures/` (`bd`, `gc`, `gh`, navigateurs,
  `fake-bd` du Cockpit, `synthetic-city/bd` ajouté par #715…).
  `tests/fake-tool-contract-test.py` (local seulement) compare les formes de
  commande des faux « déclarés » au vrai outil, et le comportement d'un seul
  faux (le `bd` de la porte de publication). #700 a trouvé un autre faux `bd`
  qui fermait un ticket bloqué. Les autres faux `bd` n'ont pas de contrôle de
  comportement ; lesquels sont « déclarés » reste à vérifier.
- Instruments de jugement : `prototype-fidelity` a son étalonnage (#692).
  La relecture de code n'est pas reproductible : un constat (F3.3 de C1) existait
  déjà au commit jugé favorable (note du 21/10). Aucun instrument n'est rejoué
  sur un cas connu.
- Vues partielles : #656 (révision), #669 (brouillon), #714 (diff) ont chacun
  corrigé un lecteur. #656 a écrit que `critical_path_bounded` mesure toujours
  la révision seule.

### 4.4 R — une règle à deux endroits

`wanted_round` (`bin/code-review`) et `open-code-review`
(`lib/convoy_state.py`) recodent la même règle : #666 et #718 ont dû changer les
deux. `ticket-end` et `tdd-step` lisent la preuve du rouge (#686, #703).
`ticket-evaluation` et `ticket-end` ont chacun leur lecture des « jeux nommés »
(#674). Chaque paire est un futur #686.

## 5. Pourquoi la méthode actuelle produit des correctifs locaux

1. **La consigne interdit de chercher ailleurs.** Chaque proposition de
   maintenance du Mayor porte, écrit par `bin/proposal-door:266` : « corriger
   ce défaut constaté, rien d'autre (ADR-0017 : pas de refactor, d'audit ni de
   « pendant que j'y suis ») ». ADR-0029 dit la même chose. La règle visait
   l'auto-amélioration sans défaut ; lue par un agent, elle interdit aussi de
   corriger les autres occurrences du défaut constaté.
2. **Le prompt du pilote de nuit (21–22/10) borne l'action au ticket.** « Chaque
   action doit débloquer un ticket nommé ou une cause observée au moins deux
   fois. Sinon, note-la dans le relais et ne la fais pas. » ; « Pas de
   refactor, d'outil nouveau, de doc ou de test sans lien avec un blocage du
   convoi. » Le correctif de classe (un lint, un test en tableau) n'est lié à
   aucun ticket : il est exclu. #708 s'est donc arrêté aux tests de critère.
3. **« Hors périmètre » est écrit, puis revient.** Les PR nomment souvent le
   reste : #624 « résidu : un propriétaire tué pendant le démarrage » → #628 le
   lendemain ; #636 « `outcome-evaluation` garde un délai fixe, hors
   périmètre » → #667 ; #674 « hors périmètre : le thème clair » → #675 et #676
   la même nuit ; #630 « non corrigé ici : af-30zwwu » → toujours ouvert ;
   #661 « l'auteur n'est pas couvert » ; #665 « constats hors ticket ». Le
   reste est vu, nommé, puis personne ne le porte.
4. **Le preflight répond à « qui d'autre change ces fichiers ? », pas à « où
   ailleurs est ce défaut ? ».** `bin/factory-fix-preflight` (#693) cherche les
   collisions. Aucune étape ne demande la catégorie ni une recherche.
5. **La preuve est le cas observé.** Le modèle de PR est « Cas réel : T02R… »,
   puis un test rouge qui reproduit ce cas. Le test prouve l'instance, pas la
   classe. Il n'y a pas de modèle de PR (`.github/` ne contient que
   `workflows/`), et le contrôle local lui-même est centré sur les fichiers
   modifiés (#641, #696).
6. **Le rythme pousse au local.** Une maintenance débloque un ticket
   visible ; un correctif de classe ne débloque rien de visible ce soir-là.
   Avec un seul « oui » de Benjamin par incident, la voie rapide gagne toujours.

Les contre-exemples confirment le diagnostic. #690 (`HOME`, 3e occurrence) se
dit « correctif de classe » et ajoute un lint qui refuse toute nouvelle
occurrence : pas de récidive depuis. Pareil pour #619 (contrôle calculé), #688
(test en tableau), #692 (étalonnage) et `fake-tool-contract-test` (af-kiy7lm).
Chaque fois, un contrôle automatique échoue sur la prochaine occurrence, où
qu'elle soit.

## 6. Méthode cible minimale (proposée, non mise en place)

Quatre changements, chacun petit.

1. **Registre des catégories** : `docs/DEFECT_CLASSES.md`, une entrée par
   catégorie (P, I, D, R, S pour commencer), avec quatre champs seulement :
   l'invariant en une phrase, le contrôle automatique qui le tient (ou
   « aucun, pourquoi »), les occurrences connues (PR), et les occurrences
   encore ouvertes (§ 4). Lu par les agents comme le reste de
   `docs/CONTEXT_INDEX.md`.
2. **Preflight** : `bin/factory-fix-preflight --class <code>` en plus des
   chemins. Il affiche l'invariant et les occurrences ouvertes, lance le
   contrôle de la catégorie s'il existe, et sort en refus si la catégorie est
   absente du registre (le correctif crée alors l'entrée).
3. **Forme des PR de maintenance** : trois lignes obligatoires.
   - `Catégorie :` un code du registre ;
   - `Où ailleurs :` la recherche faite et ce qu'elle a trouvé ;
   - `Contrôle de catégorie :` le test ou lint qui échouera sur la prochaine
     occurrence, ou pourquoi il n'y en a pas.
   Tenue par `bin/pr-autopilot`, qui arme déjà la fusion : sans ces trois
   lignes, il n'arme pas (porte existante, pas de nouvel outil).
4. **Consigne aux agents** : remplacer « corriger ce défaut constaté, rien
   d'autre » (`bin/proposal-door`, ADR-0029) et toute consigne de pilote du type
   « débloquer un ticket nommé » par : « Corriger le défaut **et toutes ses
   occurrences de la même catégorie**, avec un contrôle qui tient la
   catégorie. Ne jamais limiter une correction au cas observé. Hors périmètre
   = une autre catégorie, jamais une autre occurrence. » La limite
   d'ADR-0017 (pas de refactor ni d'audit sans défaut) reste.

Premiers contrôles de catégorie proposés (chacun une tranche d'environ une
journée, chacun à décider) :

| Cat. | Contrôle | Ce qu'il attrape aujourd'hui |
|---|---|---|
| P | Un seul lanceur borné (`lib/`, session propre + `killpg`) et un lint qui refuse `subprocess.run/Popen(..., timeout=` ailleurs dans `bin/`, `lib/`, `tests/cockpit-criteria/` ; le test de #624 étendu à `lib/` et `tests/` | `tdd-step` ×2, `ticket-author`, `fixture-city-oracle`, `evaluation_observations`, `provider-failover` |
| P | Délais lus dans un registre avec leur mesure d'origine (étude C) | ≈ 20 constantes sans mesure |
| I | Test en tableau : chaque raison d'arrêt et de parcage × chaque option offerte → un chemin qui change l'état, ou « reste à Benjamin, porte X » | `evaluation_outage`, `criterion_already_green`, 3 arrêts de fin de Spec, porte « relancer un ordre » |
| D | `fake-tool-contract-test` étendu au comportement : chaque faux `bd`/`gc` rejoue une liste de scénarios à côté du vrai (fermer un bloqué, dépendances, taille d'argument) ; tout instrument de jugement étalonné sur un cas connu avant usage (forme de #692) | les faux `bd` non déclarés ; la relecture non reproductible |
| R | Une règle, une fonction : lint sur les paires connues (`wanted_round`/`open-code-review`, preuve du rouge, jeux nommés) | 3 paires |

## 7. Rendre les incidents prévisibles

- **Avant** : les contrôles de catégorie tournent en CI. Une nouvelle
  occurrence (un nouveau lanceur sans propriétaire, un nouvel arrêt sans
  sortie) est refusée à sa PR, avant de bloquer un ticket.
- **Au départ d'un convoi** : lancer les contrôles de catégorie sur la branche
  d'intégration et la Spec. Exemple d'aujourd'hui : la fin de Spec `af-fgcw0d`
  passera par trois arrêts sans reprise (§ 4.2) ; c'est prévisible maintenant.
- **Après** : chaque PR d'incident porte sa catégorie ; `factory-metrics`
  compte les incidents par catégorie. Une catégorie qui revient alors qu'elle
  a un contrôle signale un contrôle incomplet : on rouvre l'entrée du
  registre, pas un ticket.

## 8. Limites

- Classement fait par un seul agent, sur les corps de PR ; une PR peut toucher
  deux catégories (la première est retenue). Les comptes sont approximatifs
  (≈).
- Les PR `do-work` sans corps ont été lues par leur bead ; les quatre beads de
  tests nocturnes (#634, #663, #670, #707) n'ont pas été analysés.
- La cause des copies du 22/10 (§ 4.1) est INFÉRÉE ; l'étude A la vérifie.
- Rien n'a été exécuté sur la VM en dehors de lectures (`grep`, `git show`,
  `gc bd show`).
