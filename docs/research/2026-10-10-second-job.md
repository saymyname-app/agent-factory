# Ce qu'un second job de CI en parallèle coûte au PC et rapporte

Résumé (ticket af-8km43c.6, carte af-8km43c ; mesures du 2026-10-10 vers 01:10, heure de Paris) :

1. L'attente du runner est la première cause du délai : 53 % du temps « PR ouverte → fusionnée » des 32 PR fusionnées sur le runner du PC (1 241 min sur 2 321), 64 % en soirée saturée (médiane 94 min d'attente sur 130).
2. Avec la règle « PR à jour avec main », un second job ne retire presque rien de cette attente : une fusion exige une batterie démarrée après la fusion précédente, donc au plus une fusion par batterie, quel que soit le nombre de jobs. Le second job teste un arbre que la première fusion périme : il produit surtout des runs jetés.
3. Gain au mieux, sans aucun ralentissement : −30 % sur le cycle entre deux fusions (41 → 28 min). Avec le ralentissement mesuré d'une batterie sur 4 cœurs au lieu de 8 (+38 %) : entre 0 et −10 %. Estimations, pas des mesures.
4. Le quart du cycle saturé (105 min sur 450) part en runs périmés qui prennent le runner 3 à 5 min avant d'être annulés : cela se corrige dans `bin/pr-autopilot`, sans second job.
5. Avec la fusion par lots, une seconde batterie ne sert qu'à la recherche de la PR fautive d'un lot rouge ; ce qui sert, c'est une petite voie (2 cœurs) pour l'étage court par PR, qui sinon attend derrière la batterie du lot.
6. Coût : le PC n'a pas de cœur libre. À 01:10 les 20 processeurs de WSL sont occupés à 77-97 %, charge 40 ; l'usine seule en prend 15,6. Un second job se paie sur le premier job ou sur l'usine.
7. Mémoire : pas le frein (pic 1,40 Go par job, sur 4 Go).
8. Fait nouveau, hors du ticket : la règle « à jour avec main » a été retirée du ruleset le 2026-10-10 à 00:37 (voir §2). Sans elle un second job devient utile, mais main n'est plus couvert par une batterie.
9. Essai le moins coûteux : une batterie à la main sur les cœurs 4-11 pendant un job de CI, à une heure calme ; rien à installer.

Aucun réglage du runner, de la CI ou du ruleset n'a été changé par cette recherche : lecture seule.

## Vocabulaire

| Mot | Sens ici |
|---|---|
| Runner | le programme de GitHub qui exécute un job de CI ; ici il tourne sur le PC, dans WSL |
| Job | une exécution de la batterie pour un commit d'une PR ; le runner du PC en prend un à la fois |
| Batterie | tous les tests de `bin/ci-run-tests` (environ 20 à 33 min sur le PC) |
| Run périmé | run d'un arbre qui ne peut plus fusionner parce que main a avancé |
| Règle « à jour avec main » | réglage `strict_required_status_checks_policy` du ruleset : une PR ne fusionne que si sa branche contient le dernier commit de main |
| Processeur | processeur logique vu par WSL (un cœur physique en montre deux) |
| Cycle | temps entre deux fusions quand plusieurs PR attendent |

## 1. La machine, relue en direct

| Fait | Valeur | Source |
|---|---|---|
| Processeur du PC | Intel i7-14650HX : 16 cœurs physiques, 24 processeurs logiques ; 15,7 Go de mémoire | `Win32_Processor`, `Win32_ComputerSystem` |
| Part de WSL | 20 processeurs, 8 Go, 6 Go d'échange depuis le 2026-10-09 (12 avant) | `C:\Users\benja\.wslconfig`, `nproc` |
| Part du job | processeurs 4 à 11 (8), 4 Go, priorité basse (`CPUWeight=20`, `Nice=10`) | `config/ci-runner/factory-ci-runner.service`, `cpuset.cpus.effective` du service |
| Runner inscrit chez GitHub | 1, occupé | `gh api .../actions/runners` |

`docs/OPERATIONS.md` écrit « 8 of the host's 12 » : les 12 étaient la part de WSL
avant le 2026-10-09, pas les cœurs du PC. Les questions « 2 × 6 = tout le PC »
se posent donc sur 20 processeurs de WSL (24 pour le PC).

## 2. Fait nouveau : la règle « à jour avec main » n'est plus active

| Quand (Paris) | État | Source |
|---|---|---|
| 2026-09-29 08:08 | `strict_required_status_checks_policy: true` | `gh api repos/saymyname-app/agent-factory/rulesets/23626687/history/51244750` |
| 2026-10-10 00:37 | `false` | même API, version 52640560 ; lu aussi sur le ruleset lui-même |

L'auteur est le compte dont l'usine tient le jeton (identifiant 80873224) : la
lecture ne dit pas si c'est Benjamin ou une session. La recherche de départ
(2026-10-09, 23:30) lisait `true`, et tous les runs mesurés ci-dessous ont
tourné sous `true` : la dernière fusion mesurée est à 00:35.

Conséquences à vérifier par la session de la carte (non vérifiées ici) :
`bin/pr-autopilot` ne remet une PR à jour que si GitHub la dit `BEHIND`, état
que GitHub ne donne que sous la règle stricte ; `.github/workflows/ci.yml` ne
lance aucun run sur `push` vers main parce que « le run de la PR a déjà testé
l'arbre exact ». Sans la règle, un commit de main peut n'être couvert par aucune
batterie. La doc GitHub le dit pour ce mode : moins de runs, mais « status
checks may fail after merging » ([règles disponibles](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)).

Les trois cas demandés sont traités sous la règle stricte (§4) ; le cas sans
elle est en §4.4.

## 3. Combien du délai vient de l'attente du runner

Source : `gh run list` (299 runs depuis le 2026-10-06), l'API des jobs de 105
runs, `gh pr list`. Fenêtre : du 2026-10-08 19:07 (premier jour du runner du
PC) au 2026-10-10 01:00. 90 runs sur le runner du PC, 32 PR fusionnées.
Pour chaque PR, chaque minute entre ouverture et fusion est classée : un de ses
jobs tourne ; un de ses runs existe mais attend le runner ; ni l'un ni l'autre.

| Fenêtre | PR | Délai médian / 9 sur 10 | Attente du runner | Job en cours | Reste | Délai sans l'attente (médian / 9 sur 10) |
|---|---|---|---|---|---|---|
| Tout | 32 | 50 / 141 min | 1 241 min = 53 % (médiane 17, 9 sur 10 sous 104) | 962 min = 41 %, dont 698 pour la batterie verte finale | 118 min = 5 % | 30 / 46 min |
| 2026-10-08 soir | 7 | 27 / 56 | 8 % | 75 % | 17 % | 27 / 46 |
| 2026-10-09 avant 17 h | 13 | 32 / 69 | 42 % (médiane 12) | 55 % | 3 % | 25 / 32 |
| 2026-10-09 17 h → 2026-10-10 01 h | 12 | 130 / 157 | 986 min = 64 % (médiane 94) | 32 % | 4 % | 39 / 52 |

19 PR sur 32 ont attendu le runner plus de 5 min. Entre batterie verte et
fusion : 0,7 min en médiane (9 sur 10 sous 3,8).

Chiffres de la recherche de départ, revérifiés pour le jour du 2026-10-09 :

| Chiffre repris | Relu |
|---|---|
| Runner occupé 178 min sur 180 de 18 h à 21 h | 178 (60, 59, 59) ; de 17 h à 1 h : 474 min sur 480 |
| 12 runs annulés n'ont jamais eu le runner | 13 sur le jour entier (un de plus après 23:30) |
| 43 annulés, 25 réussis, 2 échecs | 46, 27, 2 sur le jour entier (75 runs) |
| Batterie verte : médiane 21,5 min | 24,6 min (15,1 à 32,6) sur 24 batteries entières |
| Temps de runner : 745 min | 787 : 578 réussis, 163 annulés, 47 échecs |

Attente par heure de création du run, 2026-10-09 (médiane, en minutes) :
0 h 0,9 · 2 h 4,0 · 5 h 4,0 · 13 h 7,2 · 16 h 10,2 · 17 h 33,7 · 18 h 24,5 ·
19 h 20,6 · 20 h 25,0 · 21 h 15,3 · 22 h 23,8 · 23 h 15,8. Deux attentes
longues hors saturation (11 h : 87 min, 15 h : 62 min) viennent d'un runner
bloqué, pas d'une file (défauts af-rqovxb et af-7i1q2r, corrigés le jour même).

Ce que le runner a fait entre deux fusions, de 17:05 à 00:35 (11 cycles, 450 min) :

| Emploi du runner | Minutes | Part |
|---|---|---|
| La batterie verte qui fusionne | 286 | 64 % |
| Runs périmés annulés (2 à 4 par cycle, 3 à 5 min chacun) | 105 | 23 % |
| Batteries rouges (2) | 47 | 10 % |
| Libre | 12 | 3 % |

Cycle : 41 min en moyenne, 38 en médiane (de 33 à 61). Cause des runs périmés :
après une fusion, le runner prend aussitôt le run suivant de la file, qui teste
l'ancien main ; `bin/pr-autopilot` passe toutes les 3 min (`orders/pr-autopilot.toml`)
et ne remet à jour qu'une PR en retard par passage (`BEHIND_UPDATED_THIS_TICK`),
ce qui annule le run pris. D'où des annulations à 198, 258 ou 318 s.

## 4. Ce qu'un second job rapporterait

### 4.1 Aujourd'hui : une batterie par PR, règle « à jour avec main »

Loi : pour fusionner, une PR doit avoir une batterie verte démarrée après la
fusion précédente. Le débit est borné à une fusion par durée de batterie, avec
un, deux ou dix jobs. Deux batteries lancées côte à côte sur le même main : la
première verte fusionne, la seconde teste un arbre périmé et sa PR doit être
remise à jour puis relancée. La seconde ne sert que si la première est rouge.

| Variante | Cycle estimé (aujourd'hui 41 min) | D'où vient le chiffre |
|---|---|---|
| Second job sans aucun ralentissement (borne haute) | 28 min, −30 % | batterie verte médiane de la soirée, 26 min, plus un demi-passage de l'autopilote ; les runs périmés tournent à côté |
| Deux jobs de 4 processeurs chacun | 37 min, −8 % | une batterie sur 4 processeurs : 27 min 11 s contre 19 min 43 s sur 8 (`docs/OPERATIONS.md`), soit +38 % |
| Deux jobs sur les mêmes 8 processeurs | entre les deux | non mesuré |

Débit en fusions (calcul de l'agent) : un job donne (1−p)/T, deux jobs
(1−p²)/T′, p étant la part de batteries rouges. Avec T = 20 min, T′ = 27 min :
p = 20 % → 0,040 contre 0,036 fusion par minute (le second job fait perdre) ;
p = 46 % → 0,027 contre 0,029 (gain de 8 %). Sur la soirée mesurée, p = 2 sur 13.

Runs jetés : aujourd'hui 46 runs annulés sur 75 mais 21 % du temps de runner,
parce qu'un run périmé est annulé en 3 à 5 min. Avec deux jobs, le second
tourne presque une batterie entière avant d'être périmé : environ une batterie
jetée par PR fusionnée, soit la moitié du temps de runner. Réponse à la
question posée : oui, sous cette règle, deux jobs en parallèle produisent
surtout des runs jetés.

Deux gains réels mais petits : une PR rouge l'apprend sans attendre son tour
(47 min de batteries rouges sur la soirée) ; un run réduit (docs seules, 2 à
4 min) ne patiente plus derrière une batterie — mais sa fusion périme la
batterie en cours.

Levier sans second job : les 105 min de runs périmés (23 % du cycle) se
retirent en ne laissant pas le runner prendre un run périmé (remettre à jour la
PR suivante au moment de la fusion, ou annuler les runs en file des PR en
retard). Même gain que la borne haute du second job, sans cœur de plus.

### 4.2 Avec la fusion par lots (une batterie par lot « main + lot »)

Le lot absorbe la file : toutes les PR qui attendent entrent dans le lot
suivant, l'attente est bornée à une batterie environ et le runner n'est plus
saturé par le nombre de PR (12 PR en 7 h 30 = 3 à 4 lots de 4, au lieu de 11
batteries vertes et 35 runs jetés).

| Usage d'un second job | Vaut-il le coût |
|---|---|
| Seconde batterie sur le lot suivant, lancée avant le verdict du premier (spéculation) | faible : jetée si le premier lot est rouge |
| Les deux moitiés d'un lot rouge testées en même temps | oui quand un lot est rouge (9 à 46 % des PR sont rouges selon le jour, recherche de départ) : la PR fautive est trouvée en moitié moins de temps |
| Étage court par PR (contrôles de règles, tests choisis) pendant la batterie du lot | oui : sans voie à lui, l'étage court de 2 à 5 min attend 20 à 30 min derrière la batterie |

Le besoin n'est donc pas « deux batteries » mais « une voie pour la batterie
du lot et une petite voie pour l'étage court ». À trancher dans le ticket
af-8km43c.5 (comment un lot se forme) avant af-8km43c.7.

### 4.3 Avec une batterie deux fois plus courte (environ 10 min)

Le cycle tombe vers 15 min (10 min + passage de l'autopilote + runs périmés).
La demande de la soirée (12 PR en 7 h 30) occupe alors le runner à moins de
50 % au lieu de 99 % : la file se vide seule. Le second job garde la même
structure (un run sur deux jeté sous la règle stricte) pour un gain en minutes
divisé par deux. C'est le levier qui rend le second job inutile, pas l'inverse.

### 4.4 Sans la règle « à jour avec main » (état du ruleset depuis 00:37)

Chaque PR fusionne dès que sa propre batterie est verte : plus de run périmé,
environ 1,2 run par PR au lieu de 2,9. La file devient une file simple et un
second job la raccourcit vraiment. Estimation par la formule d'une file à un
serveur (calcul de l'agent, soirée : 12 PR en 450 min, batterie de 25 min,
occupation 67 %) : attente moyenne 25 min avec un job, soit 50 min de bout en
bout ; avec deux jobs de 4 processeurs (batterie de 34 min, attente de quelques
minutes), environ 37 min : −25 %. Le prix n'est pas le PC mais la qualité :
main reçoit des fusions qu'aucune batterie n'a testées ensemble. C'est le
niveau (c) de la carte, que Benjamin n'a pas choisi.

## 5. Le coût pour le PC

Mesures en lecture, 2026-10-10 à 01:10, un job de CI en cours, l'usine qui livre :

| Mesure | Valeur | Source |
|---|---|---|
| Charge (1, 5, 15 min) sur 20 processeurs | 40,6 · 33,1 · 27,7 (17,4 à 01:05, 33,5 à 01:07) | `/proc/loadavg` |
| Occupation de chaque processeur sur 5 s | 77 à 97 %, les 20 | `/proc/stat` |
| Tâches qui attendent un processeur | 50 % du temps sur 10 s, 33 % sur 5 min | `/proc/pressure/cpu` |
| Qui consomme, à cet instant | l'usine (`gc`, `bd`, `dolt`) : 15,6 processeurs ; le job : 1 | `ps` |
| Le job depuis 17:50 le 2026-10-09 (runner occupé 99 % du temps) | 147 566 s de processeur en 7 h 20 : 5,6 processeurs en moyenne sur ses 8 | `cpu.stat` du service |
| Mémoire du job | pic 1,40 Go sur 4 ; aucun dépassement | `memory.peak`, `memory.events` |
| Mémoire de WSL | 4,5 Go pris sur 7,9 ; 3,4 disponibles ; aucune attente mémoire | `free`, `/proc/pressure/memory` |
| Durée d'une batterie verte | 19 min 43 s la nuit du 2026-10-09 ; 20 à 33 min en soirée | API des jobs |

Lecture : il n'y a pas de processeur libre à donner. La batterie est déjà
jusqu'à 65 % plus lente en soirée que la nuit, sans second job.

| Partage | Processeurs | Effet sur une batterie | Effet sur l'usine et le PC |
|---|---|---|---|
| A. Deux jobs dans la part actuelle (processeurs 4-11, 4 Go communs) | 8, inchangé | chaque job lance 8 fichiers de test à la fois, donc 16 sur 8 processeurs quand les deux tournent : vers 27 min ou plus chacun (estimé ; deux fichiers longs côte à côte : 481 s → 824 s mesuré sur 2 cœurs) | la part passe de 5,6 à 8 processeurs pris en moyenne ; plafond inchangé |
| B. Deux parts de 4 (4-7 et 8-11), 2 Go chacune | 8, inchangé | 27 min chacune (mesuré pour 4 processeurs, une nuit) | comme A, plus prévisible |
| C. Deux parts de 6 ou de 8 | 12 à 16 des 20 de WSL | 20 à 23 min chacune (estimé) | l'usine garde 4 à 8 processeurs alors qu'elle en prend 15,6 ; Windows en garde 4 |

Effet sur l'usine, ce qui est connu : le 2026-10-08 de 06:00 à 06:22, trois
batteries à la fois (WSL avait 12 processeurs) : cinq ordres de l'usine en
échec de 06:12 à 06:43, dont deux par connexion perdue à la base Beads
(`gc events --type order.failed`), et des appels `wsl.exe` figés
(`docs/OPERATIONS.md`). Depuis la correction de `escalation-door-sweep`
(af-io8tb7, fusionnée à 13:09 le 2026-10-09), aucun ordre n'a échoué par délai
dépassé, soirée saturée comprise (deux « context canceled » à 17:49 sont un
redémarrage). L'effet d'un second job sur la vitesse des agents qui livrent
n'est mesuré nulle part.

Mémoire : deux jobs à 1,4 Go de pic tiennent dans 4 Go ; deux fois 4 Go
prendraient toute la mémoire de WSL. La construction hebdomadaire de l'image
(1,9 Go) ne doit pas tomber pendant deux jobs.

Usage du PC par Benjamin : rien n'a jamais été mesuré avec un jeu en cours. La
règle reste `./bin/ci-runner pause` avant un jeu ; avec deux jobs, `pause`
attend la fin de deux batteries au lieu d'une.

## 6. Ce qu'il faudrait changer (rien n'a été fait)

| Fichier | Aujourd'hui | À changer pour deux jobs |
|---|---|---|
| `config/ci-runner/runner-loop` | une boucle, un conteneur nommé `factory-ci-job`, un tube `handoff` | deux boucles ou deux conteneurs nommés ; un verrou pour que la construction de l'image ne parte pas deux fois ni pendant un job de l'autre |
| `config/ci-runner/factory-ci-runner.service` | un service, `AllowedCPUs=4-11`, `MemoryMax=4G` | variante A : rien ; variante B ou C : un service par voie (unité modèle `factory-ci-runner@.service`), chacun ses processeurs et sa mémoire |
| `bin/ci-runner` (broker, `status`, `pause`) | demande à GitHub un runner d'un seul job chaque fois que la boucle est libre ; `status` et le nettoyage supposent un seul runner | un tube par voie, ou deux lecteurs du même tube ; `status` compte deux runners |
| `config/ci-runner/isolation-probe.sh` | refuse plus de 8 processeurs vus par le job | A : inchangé ; B : 4 ; C : la nouvelle limite |
| `tests/ci-runner-test.sh` | tient `AllowedCPUs=4-11`, `MemoryMax=4G`, `-le 8`, le lot unique | suivre les nouveaux chiffres |
| `.github/workflows/ci.yml` | sur le PC, un seul lot | garder un seul lot : avec deux runners et deux lots, deux runs peuvent tenir chacun un runner avec leur job `Tests` qui attend un second lot, et se bloquer l'un l'autre |
| `config/ci-runner/root-install` | installe un service | installation en root à refaire : geste ADMIN de Benjamin |
| `docs/SECURITY.md` | un conteneur par job, jeté après | écrire que deux jobs de deux PR tournent côte à côte sous le même compte `factory-ci`, séparés par leurs conteneurs seulement ; même confiance (branches du dépôt), à accepter par écrit |
| `docs/OPERATIONS.md` | « one job at a time », « 8 of the host's 12 » | la part du PC décidée par Benjamin, et les 20 processeurs de WSL |

Côté GitHub, rien ne s'y oppose (doc officielle) :

| Fait | Source |
|---|---|
| Un runner éphémère reçoit un seul job, puis GitHub le désinscrit | [référence des runners auto-hébergés](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) |
| Un runner « just-in-time » se crée par `POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig` (nom, groupe, étiquettes ; droit d'administration du dépôt) ; la page ne fixe pas de nombre maximal | [API REST des runners](https://docs.github.com/en/rest/actions/self-hosted-runners) |
| Un job va à un runner en ligne et libre qui porte ses étiquettes ; sinon il attend, 24 h au plus | référence des runners |
| GitHub recommande les runners éphémères pour ajuster leur nombre, pas les runners persistants | référence des runners |
| La règle stricte demande plus de runs : la branche doit être remise à jour après chaque fusion d'un autre | [règles disponibles](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |

La doc ne dit rien de plusieurs runners sur une même machine : c'est permis
par construction (chaque runner est un programme à part), le partage de la
machine est l'affaire de l'hôte.

## 7. Ce qui ne peut être su qu'en l'essayant

| Question | Pourquoi une mesure passée ne suffit pas |
|---|---|
| Durée de deux batteries côte à côte sur 8 processeurs | les fichiers longs se ralentissent entre eux de façon non linéaire ; la seule mesure est sur 2 cœurs |
| Effet sur les agents qui livrent et sur les ordres | la charge est déjà à 40 ; aucun point au-delà depuis que WSL a 20 processeurs |
| Effet sur Windows et sur un jeu | jamais mesuré, même avec un job |
| Cycle réel entre deux fusions | dépend de l'autopilote et de la règle de fusion, qui vient de changer |

Essai le moins coûteux, réversible, sans root et sans toucher au runner : à une
heure calme, pendant un job de CI, lancer une batterie à la main bornée aux
mêmes processeurs et à la même priorité (`taskset -c 4-11 nice -n 10
bin/ci-run-tests --jobs 8`, dans un worktree). `docs/OPERATIONS.md` (« A battery
by hand and a CI job at the same time ») dit que les deux ne s'attendent pas.
Relever : la durée des deux batteries, `/proc/loadavg` et `/proc/pressure/cpu`
toutes les 15 s, `gc events --type order.failed`, le pic mémoire. Coût : une
batterie (30 à 45 min). Retour : Ctrl-C. Il reproduit la variante A, la plus
dure pour les batteries ; il ne dit rien du cycle de fusion.

Essai suivant seulement si le premier est bon : deux voies réelles pendant un
jour (PR sur `config/ci-runner/`, installation root par Benjamin), retour par la
réinstallation de la version d'avant.

## 8. Ce que la recherche fait apparaître pour la carte

- La décision af-8km43c.7 (« oui ou non, quelle part du PC ») dépend d'abord de
  la porte de fusion : sous la règle stricte la réponse est non ; avec des lots
  la question devient « une petite voie pour l'étage court » ; sans règle un
  second job vaut environ −25 %, au prix du niveau de qualité.
- L'état du ruleset a changé pendant la carte (§2), alors que la carte dit
  qu'aucun réglage ne change avant la Spec : à éclaircir avec Benjamin.
- Les runs périmés qui prennent le runner (23 % du cycle saturé) sont un défaut
  de l'autopilote corrigeable seul, si la règle stricte revient.
- `docs/OPERATIONS.md` décrit un PC de 12 cœurs ; WSL a 20 processeurs depuis
  le 2026-10-09 et le PC 24.

## Non vérifié

- Tous les cycles et gains « avec second job » sont des calculs de l'agent : aucun essai n'a été fait.
- La durée de deux batteries côte à côte ; l'effet sur les agents, sur Windows, sur un jeu.
- Qui a changé le ruleset à 00:37 et pourquoi ; ce que font l'autopilote et les fusions depuis (aucune fusion n'a eu lieu entre 00:37 et la mesure).
- Que GitHub ne donne l'état `BEHIND` que sous la règle stricte (lu dans les commentaires de `bin/pr-autopilot`, pas dans la doc GitHub).
- L'ordre dans lequel GitHub sert les jobs en file quand deux runners sont libres.
- La correspondance entre les processeurs 4-11 de WSL et les cœurs physiques (rapides ou économes) du PC : elle peut expliquer une part du « −27 % seulement » de 4 à 8.
- Les mesures de charge sont un instant (01:05 à 01:11) d'une nuit où l'usine livre beaucoup ; une journée calme donnerait d'autres chiffres.
- Le taux de PR rouges (9 à 46 %) est repris de la recherche de départ sans recomptage.
