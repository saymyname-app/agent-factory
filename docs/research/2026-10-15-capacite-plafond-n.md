# Étude de capacité : quel plafond N de sessions de livraison (af-2se8y2)

Intent (Benjamin, ses mots, chat opérateur Claude Code, 2026-10-15) : 20:16
« et aussi pourquoi 2 seulement en meme temps ? on pourrait pas 3 ou 4 ? » ;
20:18 « non il faut etudier ca correctement avant. » (sur la proposition de
passer N à 3 tout de suite).

Mechanism (agent interpretation, po-agent/18af46c4-db1c-45d7-87a8-973a0b9b1130) :
ligne de base mesurée à N=2 sur la VM, méthode USE (Utilisation, Saturation,
Erreurs) par ressource, puis loi de Little et Universal Scalability Law. Aucun
changement de N dans cette étude : N reste à 2 jusqu'à ce que Benjamin décide.

Jargon : **N** = `max_sessions` de `config/delivery-flow.json`, partagé par
auteurs, relecteurs et évaluateurs (`docs/CONVOY_ADVANCE.md`, « The ceiling
N »). **PSI** (Pressure Stall Information) = part du temps où au moins une
tâche attend le CPU (`/proc/pressure/cpu`, ligne `some`) : 0 % = personne
n'attend, 100 % = toujours quelqu'un en file. **Cœur** = un CPU de la VM
pendant toute la durée ; la VM en a 8.

## 1. Verdict

1. **Aujourd'hui, N n'est pas ce qui limite le débit.** Depuis le 12/10, le
   nouveau flux n'a fusionné aucun ticket vert (T01 → T01R6 : 6 tentatives,
   toutes refusées, parquées ou rouges après fusion). Pendant la ligne de
   base, un seul ticket était prêt et en cours (T02) ; T59 est parqué par
   l'opérateur et T62 est sorti en Planning Exception. Le plafond n'a bloqué
   aucun départ. Il pèsera quand T02 fusionnera : 8 tickets deviennent alors
   prêts (graphe af-w2pqiv, af-46beo2).
2. **Le CPU de la VM est saturé à N=2** : 96,8 % d'utilisation, PSI CPU 68 %
   en moyenne sur 2 h (pointes à 84 % par tranche de 10 min), charge moyenne
   21,6 pour 8 cœurs. Mémoire (18 Go libres), disque et I/O (PSI io 0,9 %)
   ne limitent pas. Aucune erreur 429 ni limite de quota Anthropic dans les
   136 journaux de session des dernières 24 h.
3. **38 % du CPU est du gaspillage, pas du travail de livraison.** Les
   cockpits lancés par `bin/tdd-step` et jamais arrêtés consomment
   2,6 cœurs en continu (3 instances, dont une depuis 18:40), à travers
   161 lancements de `fake-bd` par minute. C'est le premier poste de la VM,
   devant Dolt (1,3 cœur). Bead séparé : **af-f7x7w7**.
4. **Monter N maintenant allongerait chaque étape sans ajouter de débit** :
   sur un CPU saturé, une session de plus n'obtient pas de cœur libre. Elle
   fait monter la file d'attente (PSI de 60–68 % à 72–84 % quand un second
   auteur a démarré à 22:19) et rallonge les tests de chaque ticket, ce qui
   rapproche les délais (`timeout_seconds`) et les arrêts.
5. **Recommandation** (décision de Benjamin) : (a) corriger af-f7x7w7 et
   remesurer 1 h ; (b) séparer les plafonds auteurs et vérificateurs
   (2 auteurs + 1 place réservée aux relectures et évaluations) plutôt que de
   passer le plafond commun à 3 ; (c) seulement ensuite, essai par paliers
   N=3 avec les critères d'arrêt du §6. La VM plus grosse n'est pas
   justifiée tant que 38 % du CPU part dans une fuite.

## 2. Méthode

- Fenêtre : jeudi 15/10/2026, **20:46 → 22:45 Paris** (119,5 min, 234
  fenêtres de 30 s), convoi Cockpit af-pqfxmd en fonctionnement réel, N=2.
  Rien n'a été changé dans le convoi pendant la mesure.
- Échantillonneur unique en arrière-plan sur la VM (tmux `capacity`,
  `nice 10`), [`2026-10-15-capacite-plafond-n/sampler.py`](2026-10-15-capacite-plafond-n/sampler.py) :
  toutes les 2 s, lecture de `/proc/<pid>/stat` de tous les processus et
  attribution des deltas CPU par famille (Dolt, bd, gc, claude, tests,
  cockpit, …), comptage des processus nouveaux par appelant, CPU des
  descendants récoltés (`cutime`) par parent ; toutes les 30 s une ligne
  JSON avec `/proc/stat`, PSI, mémoire, charge et les compteurs Dolt
  `SHOW GLOBAL STATUS`. Coût mesuré : **0,01 cœur**. Données brutes sur la
  VM : `~/capacity-af-2se8y2/samples.jsonl` (hors Git).
- Résumé : [`analyze.py`](2026-10-15-capacite-plafond-n/analyze.py), une
  seule lecture à la fin, pas de polling depuis la session.
- Durées par étape : métadonnées `gc.flow.*` des 9 tickets du nouveau flux
  qui ont tourné (T01, T01R, T01R2–R6, T02, T59). `var/factory-metrics.jsonl`
  ne contient qu'une journée (14/10), sans ticket fusionné.
- Limite : un processus qui naît et meurt entre deux lectures (2 s) n'est vu
  que par le CPU de son parent (`cutime`). 59 % du CPU occupé vient de tels
  processus courts ; la vue « descendants récoltés » les rend à leur
  appelant, mais des niveaux imbriqués (bash > gc bd > bd) se recouvrent :
  ses chiffres ne s'additionnent pas.

## 3. USE par ressource (N=2, 20:46–22:45)

| Ressource | Utilisation | Saturation | Erreurs | Limite ? |
|---|---|---|---|---|
| CPU (8 cœurs) | 96,8 % (7,63 cœurs occupés) | PSI some 67,8 % ; charge moy. 21,6, max 41,4 | — | **Oui** |
| Mémoire (23 Go) | 18,1 Go libres au minimum | PSI mémoire 0,0 % | — | Non |
| Disque / I/O | iowait 0,07 % | PSI io some 0,9 %, full 0,1 % | — | Non |
| Dolt | 1,32 cœur ; 86,9 requêtes/s dont 57 SELECT/s ; 10,9 connexions/s | 9 connexions en moyenne, 32 au maximum (plafond 256) | 0 requête lente sur 2 h | Non (mais 2e poste CPU) |
| Quota Anthropic | 2 sessions de livraison + Mayor + boucle night + revue de graphe | — | 0 erreur 429 / « usage limit » sur 24 h | Non, observé |
| Git `integration/af-2zseit` | 1 fusion dans le nouveau flux (T01R6) | — | 0 conflit récent dans `overlap-conflict-log.jsonl` | Non, pas encore exercé |

Chronologie par tranche de 10 min (cœurs) :

| Tranche | Occupés | Cockpits orphelins | Dolt | PSI CPU |
|---|---|---|---|---|
| 20:40 | 7,84 | 2,52 | 1,24 | 74 % |
| 20:50 | 7,42 | 2,73 | 0,96 | 67 % |
| 21:00 | 7,47 | 2,71 | 1,20 | 67 % |
| 21:10 | 7,53 | 2,95 | 1,55 | 59 % |
| 21:20 | 7,56 | 2,78 | 1,41 | 68 % |
| 21:30 | 7,21 | 2,88 | 1,22 | 46 % |
| 21:40 | 7,44 | 2,92 | 1,45 | 61 % |
| 21:50 | 7,80 | 2,39 | 1,18 | 81 % |
| 22:00 | 7,74 | 2,10 | 1,12 | 77 % |
| 22:10 | 7,83 | 2,57 | 1,54 | 66 % |
| 22:20 | 7,86 | 2,59 | 1,66 | 72 % |
| 22:30 | 7,90 | 2,40 | 1,42 | 84 % |
| 22:40 | 7,76 | 2,54 | 1,17 | 62 % |

Sessions de livraison observées (`gc session list`) : un auteur (T02) toute
la fenêtre, un relecteur par intermittence (deux sessions courtes vues à
21:05 et 21:49), un second auteur à partir de 22:19.

## 4. Où va le CPU

| Poste | Cœurs | Part du CPU occupé | Nature |
|---|---|---|---|
| Cockpits isolés orphelins (`cockpit run` + `fake-bd`) | 2,6 | 34–38 % | **Gaspillage** (af-f7x7w7) |
| Processus détachés récoltés par `systemd --user` | 1,8 | ≈ 24 % | Non identifié (processus dont le lanceur est mort avant eux ; à suivre dans af-f7x7w7) |
| Dolt (`dolt sql-server`) | 1,3 | 17 % | Plan de contrôle (polling) |
| Ordres lancés par `gc supervisor` (descendants) | 1,0 | 13 % | Plan de contrôle, dont `convoy-advance` 0,32 |
| Sessions Claude (outils : tests, git, bd) | 0,9 | 11 % | Travail des agents (auteurs, Mayor, night) |
| Tests (convoy-advance-test, regression, harness, ci-run-tests, tdd-step) | ≈ 2,0 | ≈ 26 % | Travail de livraison et de la boucle night |
| Boucle night (`~/night-run/run.sh`) | 0,35 | 5 % | Maintenance usine |

(Les lignes « descendants » se recouvrent en partie avec les tests ; ordre
de grandeur, pas une somme.)

Le travail utile des auteurs et vérificateurs (tests de critère, tdd-step,
evidence-capture, revues) représente au plus un tiers de la machine. Le
reste est du plan de contrôle ou des fuites.

## 5. Coût du polling (étape 2)

Clients du tracker lancés par minute, par appelant (moyenne sur 2 h) :

| Appelant | Lancements/min |
|---|---|
| `fake-bd` ← cockpits orphelins | 161 |
| `bd` ← `gc bd` (relais) | 14,7 |
| `bd` ← `gc` (supervisor, ordres) | 11,8 |
| `gc bd` ← `bin/convoy-advance` | 9,3 |
| `gc bd` ← `bin/convoy-state` | 6,0 |
| `gc bd` ← `cascade-nudge-on-blocker-close` | 3,3 |
| `bd` ← `bin/mail-reply-reap` | 1,9 |
| `gc` / `bd` ← `bin/idle-ready-work-wake` | 3,1 |
| `gc` ← `bin/factory-orphan-sweep` | 1,4 |
| autres (watchdog, delivery-guard, orphan-sweep…) | < 1 chacun |

Dolt reçoit 87 requêtes/s et 10,9 connexions/s : chaque appel `bd` ouvre sa
propre connexion. Une passe de `convoy-advance` (toutes les minutes) coûte
environ 0,32 cœur × 60 s ≈ 19 s de CPU, sans compter sa part de Dolt.

**Plus petite réduction, par ordre de gain :**

1. **Fuite des produits lancés (af-f7x7w7)** : ≈ 2,6 cœurs, plus le parc de
   `fixture-city` restés en vie depuis 2,5 à 3,6 jours. À corriger en
   premier, avant toute capacité.
2. **`convoy-advance` : passer de 1 min à un réveil sur événement**
   (`bead.closed`, fin de session), avec une passe de sécurité toutes les
   5 min. Gain attendu : ≈ 0,25 cœur et environ 15 lancements de `gc bd`
   par minute, à mesurer. Ne pas le faire tant que L2–L7 de la boucle night
   touchent `bin/convoy-advance` / `bin/convoy-state` (PR #621, af-npz9v1.3, a fusionné à
   21:41 Paris, pendant la ligne de base ; elle borne les reprises et ne
   change pas la charge par passe).
3. Le reste du polling (≈ 15 ordres de 2 à 15 min) pèse moins de 0,1 cœur
   chacun : pas de gain qui vaille un changement.

## 6. Modèle (étape 3)

### Loi de Little (L = λ·W)

Temps de place par ticket, mesuré sur les tentatives du nouveau flux (UTC
des `gc.flow.*`) :

| Étape | Mesuré | Source |
|---|---|---|
| Départ → rouge (tests de critère écrits) | 7–8 min | T01R2, R3, R4, R6 |
| Rouge → gel (relecture des tests) | 3–4 min | idem |
| Gel → vert (implémentation, k exécutions) | 49–54 min ; T02 : plus de 5 h et non fini | T01R2, R3 ; T02 |
| Fin d'auteur → verdict de revue de code | 5–7 min | T01, T01R2, R3, R4, R6 |
| Ticket Evaluation | 5 min (datasets du ticket) ; 115 min (95 datasets, avant #602) | T01R6 ; T01R4 |
| Fusion → tests fusionnés | 4 min | T01R6 |

Un ticket qui passe du premier coup tient environ **1,1 h de place
d'auteur + 0,2 h de place de vérificateur ≈ 1,3 place·h**. D'où le débit
maximal théorique, si le CPU suivait et que le graphe offrait assez de
tickets prêts :

| N | Débit max (tickets/h) | 60 tickets |
|---|---|---|
| 2 | 1,5 | ≈ 40 h |
| 3 | 2,3 | ≈ 26 h |
| 4 | 3,1 | ≈ 20 h |

Observé : 0 ticket vert fusionné en 3,5 jours, et T02 occupe sa place
depuis 16:17 UTC (plus de 4,5 h). Avec L ≈ 1–2 et W ≈ 5 h, λ ≈ 0,2–0,4
ticket/h au mieux. **L'écart entre 1,5 et 0,3 ne vient pas de N mais des
échecs, des reprises et de la durée de la phase verte.**

### Universal Scalability Law

X(N) = λ₁·N / (1 + σ(N−1) + κN(N−1)), où σ est la contention (attente d'une
ressource partagée : ici le CPU) et κ la cohérence (coût d'échange entre
sessions : conflits Git, relectures croisées). Il faut au moins trois
points (N, débit mesuré) pour ajuster σ et κ. **Nous n'en avons aucun :**
le débit mesuré est nul à N=2, et N=1 n'a jamais tourné dans ce flux.
**L'USL ne peut pas être ajustée honnêtement aujourd'hui.** Ce qu'on peut
dire, qualitativement : avec un CPU à 97 % et un PSI à 68 %, σ est déjà
grand. Chaque session de plus allonge les autres (PSI de 60–68 % à 72–84 %
avec le second auteur à 22:19), et le débit plafonne ou baisse au lieu de
croître.

Prévision chiffrable, par le CPU :
- **N=3 aujourd'hui** : pas de cœur libre, donc tests plus lents pour les
  trois sessions, débit inchangé ou moindre, plus d'arrêts pour délai.
- **N=3 après af-f7x7w7** : ≈ 2,6 cœurs libérés (≈ 1/3 de la machine) ;
  une session d'auteur en phase de tests consomme de l'ordre de 1 à 2 cœurs
  (tdd-step + evidence-capture + harness + regression). Une troisième
  session tient alors, avec un PSI attendu revenu sous 50 %, à vérifier.
- **N=4** : demande de l'ordre de 2 auteurs de plus que la capacité
  libérée ; plausible seulement si la réduction du polling (§5, point 2)
  et l'identification des 1,8 cœur détachés libèrent encore 1 à 2 cœurs,
  ou sur une VM plus grosse.

### Plafonds séparés auteurs / vérificateurs

Oui, à recommander. Une relecture ou une évaluation dure 5–15 min, un
auteur 1 h ou plus. Avec un plafond commun, deux auteurs actifs bloquent la
revue d'un ticket fini : sa place d'auteur est rendue, mais la revue attend
qu'une place se libère, et la fusion recule d'autant (`docs/CONVOY_ADVANCE.md`).
Réserver une place aux vérificateurs (2 auteurs + 1) raccourcit W sans
ajouter de charge auteur. C'est un changement de contrat (un seul réglage
devient deux) : décision de Benjamin, puis maintenance usine.

## 7. Essai par paliers (étape 4, pas lancé)

Seulement après accord de Benjamin, et après af-f7x7w7 :

1. Remesurer 1 h à N=2 avec le même échantillonneur (référence propre).
2. N=3 (ou 2 auteurs + 1 vérificateur) sur une fenêtre fixe de 3 h avec au
   moins 3 tickets prêts. Retour à 2 dès qu'un critère d'arrêt tombe :
   - PSI CPU moyen > 75 % sur 30 min ;
   - durée d'un même test de critère (harness) > 1,5 × sa valeur à N=2 ;
   - un ticket arrêté pour délai (`*_no_result`) ;
   - un conflit Git sur `integration/af-2zseit` non absorbé par le tour de
     correction.
3. Comparer débit, W par étape, PSI et échecs ; un point (N, X) de plus
   pour l'USL.

## 8. Apport d'une VM plus grosse

Elle ajouterait du CPU, la seule ressource limitante. Mais aujourd'hui elle
paierait surtout la fuite (2,6 cœurs) et le plan de contrôle (≈ 2,3 cœurs).
Après af-f7x7w7, une VM 8 cœurs a de la place pour N=3. Une VM plus grosse
ne se justifie que si l'essai N=3 atteint ses critères d'arrêt par le CPU
seul. Dépense : décision de Benjamin.

## 9. Ce que cette étude n'a pas pu établir

- Débit réel à N=2 : nul pendant la fenêtre, faute de ticket arrivé au
  bout. À remesurer quand T02 et ses 8 successeurs tourneront.
- Origine des 1,8 cœur récoltés par `systemd --user` : processus détachés
  dont le lanceur est mort, sans nom attribué par l'échantillonneur.
- L4 de l'allègement D01 (évaluation réduite) n'avait pas fusionné à la fin
  de la fenêtre (`origin/main` = 7edf692 ; #621 = L3, af-npz9v1.3, fusionnée
  à 21:41 Paris). Quand il
  fusionnera, la charge des évaluations changera : la référence est à
  refaire.
